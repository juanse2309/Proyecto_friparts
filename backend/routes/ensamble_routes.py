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

@ensamble_bp.route('/api/ensamble/session_active', methods=['GET'])
def get_active_ensamble_session():
    """Busca si el operario tiene un trabajo activo en db_ensambles."""
    responsable = request.args.get('responsable')
    if not responsable:
        return jsonify({"success": False, "error": "Responsable requerido"}), 400
    
    try:
        # Buscar en db_ensambles (plural como exige DBeaver)
        sesion = Ensamble.query.filter(
            Ensamble.responsable == responsable,
            Ensamble.estado.in_(['EN_PROCESO', 'PAUSADO', 'TRABAJANDO'])
        ).order_by(Ensamble.id.desc()).first()
        
        if sesion:
            return jsonify({
                "success": True,
                "session": {
                    "id_ensamble": sesion.id_ensamble,
                    "id_codigo": sesion.id_codigo,
                    "orden_produccion": sesion.op_numero,
                    "cantidad": float(sesion.cantidad or 0),
                    "estado": sesion.estado,
                    "hora_inicio_dt": sesion.hora_inicio.isoformat() if sesion.hora_inicio else None,
                    "tiempo_pausa_acumulado": sesion.tiempo_pausa_acumulado or 0,
                    "hora_pausa": sesion.hora_pausa.isoformat() if sesion.hora_pausa else None
                }
            })
        return jsonify({"success": True, "session": None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
            op_numero=data.get('op_numero'),
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
def reportar_ensamble_multi():
    """Lógica para procesar múltiples registros de ensamble (Producto + Componentes)."""
    try:
        data = request.get_json()
        registros_data = data.get('registros', [])
        
        if not registros_data:
            return jsonify({'success': False, 'error': 'No se recibieron registros'}), 400

        id_ensamble_global = registros_data[0].get('id_ensamble')
        
        # 1. Identificar el registro principal (es_final = True)
        main_reg = next((r for r in registros_data if r.get('es_final')), registros_data[0])
        estado_final = main_reg.get('estado', 'EN_PROCESO')
        responsable = main_reg.get('responsable', 'OPERARIO')
        
        logger.info(f"[ENSAMBLE-MULTI] Procesando {len(registros_data)} registros para id_ensamble={id_ensamble_global}")

        for reg_data in registros_data:
            id_codigo_ancla = reg_data.get('id_codigo')
            buje_detalle = reg_data.get('buje_ensamble')
            cantidad = float(reg_data.get('cantidad', 0) or 0)
            es_final_flag = reg_data.get('es_final', False) # Flag local para lógica interna
            
            # UPSERT: Solo intentamos recuperar el registro si es el producto final (fila de sesión)
            registro = None
            if es_final_flag:
                # Usamos id_ensamble y buje_ensamble (que para el final es igual al id_codigo)
                registro = Ensamble.query.filter_by(
                    id_ensamble=id_ensamble_global, 
                    buje_ensamble=buje_detalle
                ).first()
            
            if not registro:
                registro = Ensamble(id_ensamble=id_ensamble_global, id_codigo=id_codigo_ancla)
                if es_final_flag:
                    # Si es nuevo y es el final, marcamos el inicio de la operación
                    registro.hora_inicio = datetime.now()
                db.session.add(registro)

            # Mapeo de datos (solo columnas físicas en db_ensambles)
            registro.id_codigo = id_codigo_ancla
            registro.buje_ensamble = buje_detalle
            registro.responsable = responsable
            registro.cantidad = cantidad
            registro.qty = float(reg_data.get('qty', 1) or 1) # Persistir ratio/factor
            registro.estado = reg_data.get('estado', 'FINALIZADO')
            registro.op_numero = reg_data.get('op_numero', '')
            registro.observaciones = reg_data.get('observaciones', '')
            registro.buje_origen = reg_data.get('buje_origen', '')
            registro.almacen_para_descargar = reg_data.get('almacen_para_descargar')
            registro.almacen_destino = reg_data.get('almacen_destino')
            registro.fecha = datetime.strptime(reg_data.get('fecha'), '%Y-%m-%d').date() if reg_data.get('fecha') else datetime.now().date()

            # Lógica de Inventario (Basada en el DETALLE: buje_ensamble)
            if estado_final == 'FINALIZADO' or registro.estado == 'CONSUMO':
                producto_db = Producto.query.filter(
                    (Producto.codigo_sistema == buje_detalle) | (Producto.id_codigo == buje_detalle)
                ).with_for_update().first()

                if producto_db:
                    # Descontar si hay origen
                    if registro.almacen_para_descargar:
                        almacen = registro.almacen_para_descargar.upper()
                        if 'TERMINADO' in almacen:
                            producto_db.p_terminado = float(producto_db.p_terminado or 0) - cantidad
                        elif 'ENSAMBLADO' in almacen:
                            producto_db.producto_ensamblado = float(producto_db.producto_ensamblado or 0) - cantidad
                        
                        db.session.add(OperacionLog(
                            modulo='ENSAMBLE', operario=responsable, accion='CONSUMO_MULTI',
                            detalles=f"Descontado {cantidad} de {buje_detalle} para ensamble {id_ensamble_global}"
                        ))

                    # Incrementar si hay destino
                    if registro.almacen_destino:
                        almacen = registro.almacen_destino.upper()
                        if 'ENSAMBLADO' in almacen:
                            producto_db.producto_ensamblado = float(producto_db.producto_ensamblado or 0) + cantidad
                        elif 'TERMINADO' in almacen:
                            producto_db.p_terminado = float(producto_db.p_terminado or 0) + cantidad

                        db.session.add(OperacionLog(
                            modulo='ENSAMBLE', operario=responsable, accion='ENTRADA_MULTI',
                            detalles=f"Ingresado {cantidad} de {buje_detalle} desde ensamble {id_ensamble_global}"
                        ))

            # Lógica de Tiempos y KPIs (Exclusiva del producto final usando el flag local)
            if es_final_flag:
                if estado_final == 'PAUSADO':
                    registro.hora_pausa = datetime.now()
                elif estado_final in ['EN_PROCESO', 'TRABAJANDO', 'FINALIZADO'] and registro.hora_pausa:
                    diff = datetime.now() - registro.hora_pausa
                    registro.tiempo_pausa_acumulado = (registro.tiempo_pausa_acumulado or 0) + int(diff.total_seconds())
                    registro.hora_pausa = None

                if estado_final == 'FINALIZADO':
                    registro.hora_fin = datetime.now()
                    # Parsing de horas manuales si vienen del frontend
                    h_ini_str = reg_data.get('hora_inicio')
                    h_fin_str = reg_data.get('hora_fin')
                    if h_ini_str:
                        registro.hora_inicio = datetime.combine(registro.fecha, datetime.strptime(h_ini_str, '%H:%M').time())
                    if h_fin_str:
                        registro.hora_fin = datetime.combine(registro.fecha, datetime.strptime(h_fin_str, '%H:%M').time())

                    # KPIs
                    if registro.hora_inicio and registro.hora_fin:
                        duracion = (registro.hora_fin - registro.hora_inicio).total_seconds() - (registro.tiempo_pausa_acumulado or 0)
                        registro.duracion_segundos = int(max(0, duracion))
                        registro.tiempo_total_minutos = round(registro.duracion_segundos / 60, 2)
                        if cantidad > 0:
                            registro.segundos_por_unidad = round(duracion / cantidad, 2)

                    # Registro de PNC
                    pnc_cant = int(reg_data.get('pnc', 0) or 0)
                    if pnc_cant > 0:
                        db.session.add(PncEnsamble(
                            id_ensamble=id_ensamble_global, id_codigo=id_codigo_ancla, 
                            cantidad=pnc_cant, criterio=reg_data.get('pnc_detalles', ''),
                            codigo_ensamble=id_codigo_ancla
                        ))

        db.session.commit()

        # 4. Sincronizar Programación (Solo si hay id_prog válido)
        id_prog = main_reg.get('id_prog')
        op_numero = main_reg.get('op_numero')
        id_prod_final = main_reg.get('id_codigo')

        if id_prog:
            # Recalcular total producido para esta meta
            total_realizado = db.session.query(db.func.sum(Ensamble.cantidad)).filter(
                Ensamble.id_codigo == id_prod_final,
                Ensamble.op_numero == op_numero,
                Ensamble.estado == 'FINALIZADO'
            ).scalar() or 0
            
            prog = ProgramacionEnsamble.query.get(id_prog)
            if prog:
                prog.cantidad_realizada = total_realizado
                if estado_final == 'FINALIZADO' and total_realizado >= prog.cantidad_objetivo:
                    prog.estado = 'COMPLETADO'
                elif prog.estado == 'PENDIENTE':
                    prog.estado = 'EN_PROCESO'
                db.session.commit()

        return jsonify({
            'success': True, 
            'message': f'Se procesaron {len(registros_data)} registros con éxito.',
            'id_ensamble': id_ensamble_global
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ ERROR REPORTE MULTI-ENSAMBLE: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
