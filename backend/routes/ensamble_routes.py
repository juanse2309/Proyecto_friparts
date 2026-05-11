from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import uuid
from backend.core.sql_database import db
from backend.models.sql_models import ProgramacionEnsamble, Ensamble, Producto, OperacionLog, PncEnsamble
from backend.services.bom_service import calcular_descuentos_ensamble
from sqlalchemy import text

ensamble_bp = Blueprint('ensamble_bp', __name__)
logger = logging.getLogger(__name__)

@ensamble_bp.route('/api/ensamble/programacion', methods=['GET'])
def listar_programacion():
    try:
        # Listar todas las programaciones no completadas primero
        schedules = ProgramacionEnsamble.query.order_by(
            ProgramacionEnsamble.estado.desc(), 
            ProgramacionEnsamble.fecha_programada.asc()
        ).all()
        
        res = []
        for s in schedules:
            res.append({
                'id_prog': s.id_prog,
                'id_codigo': s.id_codigo,
                'cantidad_objetivo': s.cantidad_objetivo,
                'cantidad_realizada': s.cantidad_realizada,
                'fecha_programada': s.fecha_programada.strftime('%Y-%m-%d') if s.fecha_programada else '',
                'estado': s.estado
            })
        return jsonify({'success': True, 'data': res})
    except Exception as e:
        logger.error(f"Error al listar programación ensamble: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ensamble_bp.route('/api/ensamble/programacion', methods=['POST'])
def crear_programacion():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        id_codigo = data.get('id_codigo')
        cantidad_objetivo = int(data.get('cantidad_objetivo', 0))
        fecha_str = data.get('fecha_programada')
        
        if not id_codigo or cantidad_objetivo <= 0 or not fecha_str:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        
        fecha_prog = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        nueva_prog = ProgramacionEnsamble(
            id_codigo=id_codigo,
            cantidad_objetivo=cantidad_objetivo,
            fecha_programada=fecha_prog,
            estado='PENDIENTE'
        )
        db.session.add(nueva_prog)
        db.session.commit()
        
        return jsonify({'success': True, 'id_prog': nueva_prog.id_prog})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al crear programación ensamble: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ensamble_bp.route('/api/ensamble/bom_stock/<id_codigo>', methods=['GET'])
def obtener_bom_con_stock(id_codigo):
    try:
        # 1. Obtener la BOM
        bom_res = calcular_descuentos_ensamble(id_codigo, 1) # Cantidad 1 para ver el ratio
        
        if not bom_res.get('success'):
            return jsonify(bom_res), 404
        
        componentes = bom_res.get('componentes', [])
        resultado = []
        
        for comp in componentes:
            codigo_inv = comp['codigo_inventario']
            # 2. Consultar stock en db_productos
            producto = Producto.query.filter_by(codigo_sistema=codigo_inv).first()
            
            stock = float(producto.p_terminado or 0) if producto else 0
            # Cuántos alcanza a armar con ese stock (stock / cantidad_por_kit)
            ratio = float(comp['cantidad_por_kit'])
            alcanza = int(stock // ratio) if ratio > 0 else 0
            
            resultado.append({
                'componente': comp['codigo_ficha'],
                'codigo_inventario': codigo_inv,
                'stock_almacen': stock,
                'cantidad_por_unidad': ratio,
                'alcanza_para': alcanza
            })
            
        return jsonify({
            'success': True,
            'id_codigo': id_codigo,
            'componentes': resultado
        })
    except Exception as e:
        logger.error(f"Error al obtener BOM con stock: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ensamble_bp.route('/api/ensamble/tareas_pendientes', methods=['GET'])
def tareas_pendientes():
    try:
        tareas = ProgramacionEnsamble.query.filter(
            ProgramacionEnsamble.estado != 'COMPLETADO'
        ).order_by(ProgramacionEnsamble.fecha_programada.asc()).all()
        
        res = []
        for t in tareas:
            faltante = max(0, t.cantidad_objetivo - t.cantidad_realizada)
            res.append({
                'id_prog': t.id_prog,
                'id_codigo': t.id_codigo,
                'cantidad_objetivo': t.cantidad_objetivo,
                'cantidad_realizada': t.cantidad_realizada,
                'faltante': faltante,
                'fecha_programada': t.fecha_programada.strftime('%Y-%m-%d') if t.fecha_programada else '',
                'estado': t.estado
            })
        return jsonify({'success': True, 'data': res})
    except Exception as e:
        logger.error(f"Error al listar tareas pendientes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ensamble_bp.route('/api/ensamble/reportar', methods=['POST'])
def reportar_ensamble():
    """
    Registra producción de ensamble con descuento selectivo de componentes y PNC.
    Garantiza integridad transaccional.
    """
    try:
        data = request.get_json()
        id_prog = data.get('id_prog') 
        
        # 1. Captura de Datos Maestro (Casting Robusto para evitar Error 500 PG Type 25)
        id_codigo = data.get('id_codigo')
        cantidad = int(data.get('cantidad', 0) or 0)
        responsable = data.get('responsable', 'OPERARIO')
        observaciones = data.get('observaciones', '')
        fecha_str = data.get('fecha')
        hora_inicio_str = data.get('hora_inicio')
        hora_fin_str = data.get('hora_fin')
        es_manual = id_prog is None
        
        # Logística y Calidad
        buje_origen = data.get('buje_origen', '')
        qty_valor = float(data.get('qty', 1) or 1)
        almacen_origen = data.get('almacen_origen', 'P. TERMINADO').upper()
        almacen_destino = data.get('almacen_destino', 'PRODUCTO ENSAMBLADO').upper()
        op_numero = data.get('op_numero', '')
        pnc_cant = int(data.get('pnc', 0) or 0)
        pnc_detalles = data.get('pnc_detalles', '')
        componentes_filtro = data.get('componentes_seleccionados', []) 
        
        if not id_codigo or cantidad <= 0:
            return jsonify({'success': False, 'error': 'Producto o cantidad inválidos'}), 400

        # Parsing de Tiempos
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else datetime.now().date()
        h_inicio = datetime.combine(fecha_obj, datetime.strptime(hora_inicio_str, '%H:%M').time()) if hora_inicio_str else datetime.now()
        h_fin = datetime.combine(fecha_obj, datetime.strptime(hora_fin_str, '%H:%M').time()) if hora_fin_str else datetime.now()

        # 2. Explosión de Materiales (BOM)
        bom_res = calcular_descuentos_ensamble(id_codigo, cantidad)
        
        # 3. Descuento Selectivo de Componentes
        if bom_res.get('success'):
            for comp in bom_res['componentes']:
                cod_comp = comp['codigo_inventario']
                
                # SÓLO descontar si el operario lo marcó (o si no viene filtro, por defecto todos)
                if componentes_filtro and cod_comp not in componentes_filtro:
                    continue
                
                cant_desc = comp['cantidad_total_descontar']
                
                producto_comp = Producto.query.filter(
                    (Producto.codigo_sistema == cod_comp) | (Producto.id_codigo == cod_comp)
                ).with_for_update().first()
                
                if producto_comp:
                    if 'TERMINADO' in almacen_origen:
                        producto_comp.p_terminado = float(producto_comp.p_terminado or 0) - cant_desc
                    elif 'ENSAMBLADO' in almacen_origen:
                        producto_comp.producto_ensamblado = float(producto_comp.producto_ensamblado or 0) - cant_desc
                    elif 'PULIR' in almacen_origen:
                        producto_comp.por_pulir = float(producto_comp.por_pulir or 0) - cant_desc
                    
                    db.session.add(OperacionLog(
                        modulo='ENSAMBLE', operario=responsable, accion='CONSUMO_INSUMO',
                        detalles=f"Descontado {cant_desc} de {cod_comp} (Selección Manual)"
                    ))
        
        # 4. Incremento de Producto Terminado
        producto_final = Producto.query.filter(
            (Producto.codigo_sistema == id_codigo) | (Producto.id_codigo == id_codigo)
        ).with_for_update().first()
        
        if producto_final:
            if 'ENSAMBLADO' in almacen_destino:
                producto_final.producto_ensamblado = float(producto_final.producto_ensamblado or 0) + cantidad
            elif 'TERMINADO' in almacen_destino:
                producto_final.p_terminado = float(producto_final.p_terminado or 0) + cantidad

        # 5. Registro de PNC (Si aplica)
        id_ens_uuid = uuid.uuid4().hex[:8]
        if pnc_cant > 0:
            nuevo_pnc = PncEnsamble(
                id_ensamble=id_ens_uuid,
                id_codigo=id_codigo,
                cantidad=pnc_cant,
                criterio=pnc_detalles,
                codigo_ensamble=id_codigo
            )
            db.session.add(nuevo_pnc)

        # 6. Registro de Historial Ensamble
        nuevo_ensamble = Ensamble(
            id_ensamble=id_ens_uuid,
            id_codigo=id_codigo,
            responsable=responsable,
            cantidad=cantidad,
            fecha=fecha_obj,
            hora_inicio=h_inicio,
            hora_fin=h_fin,
            observaciones=f"{'[MANUAL] ' if es_manual else f'[PROGRAMADO] '} {observaciones}",
            op_numero=op_numero,
            buje_origen=buje_origen,
            qty=qty_valor,
            almacen_para_descargar=almacen_origen,
            almacen_destino=almacen_destino,
            estado='VALIDADO' if es_manual else 'FINALIZADO',
            departamento='Ensamble'
        )
        db.session.add(nuevo_ensamble)
        
        # 7. Actualizar Meta Programada
        if id_prog:
            prog = ProgramacionEnsamble.query.get(id_prog)
            if prog:
                prog.cantidad_realizada += (cantidad + pnc_cant) # Contamos ambos para el avance? O solo buenos?
                # Usualmente se cuenta lo realizado total para la meta, pero depende de la política.
                # Aquí sumamos la cantidad reportada como buena.
                if prog.cantidad_realizada >= prog.cantidad_objetivo:
                    prog.estado = 'COMPLETADO'
                else:
                    prog.estado = 'EN_PROCESO'
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Reporte procesado correctamente.',
            'id_ensamble': id_ens_uuid
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ ERROR REPORTE ENSAMBLE: {e}")
        return jsonify({'success': False, 'error': f"Error: {str(e)}"}), 500
