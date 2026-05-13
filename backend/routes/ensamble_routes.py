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
def reportar_ensamble_upsert():
    """Lógica Upsert unificada para reportar avance o finalizar ensamble."""
    try:
        data = request.get_json()
        id_ensamble = data.get('id_ensamble')
        id_codigo = data.get('id_codigo')
        cantidad = int(data.get('cantidad', 0) or 0)
        estado_final = data.get('estado', 'EN_PROCESO')
        responsable = data.get('responsable', 'OPERARIO')
        qty_val = float(data.get('qty', 1) or 1)
        
        # LOG DE DIAGNÓSTICO — Confirmar estado recibido
        logger.info(f"[ENSAMBLE-REPORTE] estado='{estado_final}' | id_codigo={id_codigo} | cantidad={cantidad} | id_ensamble={id_ensamble}")
        
        # Captura Completa de Variables (Evita Variables Huérfanas)
        fecha_str = data.get('fecha')
        hora_inicio_str = data.get('hora_inicio')
        hora_fin_str = data.get('hora_fin')
        observaciones = data.get('observaciones', '')
        buje_origen = data.get('buje_origen', '')
        almacen_origen = data.get('almacen_origen', 'P. TERMINADO').upper()
        almacen_destino = data.get('almacen_destino', 'PRODUCTO ENSAMBLADO').upper()
        pnc_cant = int(data.get('pnc', 0) or 0)
        pnc_detalles = data.get('pnc_detalles', '')
        componentes_filtro = data.get('componentes_seleccionados', []) 
        
        if not id_codigo or (cantidad < 0 and estado_final != 'PAUSADO'):
            return jsonify({'success': False, 'error': 'Producto o cantidad inválidos'}), 400

        # 2. Lógica UPSERT: Buscar o Crear
        registro = Ensamble.query.filter_by(id_ensamble=id_ensamble).first() if id_ensamble else None
        is_new = False
        
        if not registro:
            is_new = True
            id_ensamble = id_ensamble or uuid.uuid4().hex[:8]
            registro = Ensamble(id_ensamble=id_ensamble, hora_inicio=datetime.now())
            db.session.add(registro)

        # 3. Mapeo de Datos y Persistencia de Pausa
        registro.id_codigo = id_codigo
        registro.responsable = responsable
        registro.cantidad = cantidad
        registro.op_numero = data.get('op_numero', '')
        registro.estado = estado_final
        registro.qty = qty_val
        registro.fecha = datetime.now().date()
        
        if estado_final == 'PAUSADO':
            registro.hora_pausa = datetime.now()
        elif estado_final in ['EN_PROCESO', 'TRABAJANDO', 'FINALIZADO'] and registro.hora_pausa:
            diff = datetime.now() - registro.hora_pausa
            registro.tiempo_pausa_acumulado = (registro.tiempo_pausa_acumulado or 0) + int(diff.total_seconds())
            registro.hora_pausa = None

        # 4. Finalización y Descarga BOM (SOLO en FINALIZADO)
        if estado_final == 'FINALIZADO':
            registro.hora_fin = datetime.now()
            
            # Parsing de Tiempos
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else datetime.now().date()
            h_inicio = datetime.combine(fecha_obj, datetime.strptime(hora_inicio_str, '%H:%M').time()) if hora_inicio_str else datetime.now()
            h_fin = datetime.combine(fecha_obj, datetime.strptime(hora_fin_str, '%H:%M').time()) if hora_fin_str else datetime.now()
            
            registro.fecha = fecha_obj
            registro.hora_inicio = h_inicio
            registro.hora_fin = h_fin
            registro.observaciones = observaciones
            registro.buje_origen = buje_origen
            registro.almacen_para_descargar = almacen_origen
            registro.almacen_destino = almacen_destino

            # Explosión de Materiales (BOM)
            bom_res = calcular_descuentos_ensamble(id_codigo, cantidad)
            
            if bom_res.get('success'):
                for comp in bom_res['componentes']:
                    cod_comp = comp['codigo_inventario']
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
                        
                        db.session.add(OperacionLog(
                            modulo='ENSAMBLE', operario=responsable, accion='CONSUMO_INSUMO',
                            detalles=f"Descontado {cant_desc} de {cod_comp} (Cierre Final)"
                        ))

            # Registro de PNC (Si aplica al finalizar)
            if pnc_cant > 0:
                db.session.add(PncEnsamble(
                    id_ensamble=id_ensamble, id_codigo=id_codigo, 
                    cantidad=pnc_cant, criterio=pnc_detalles, codigo_ensamble=id_codigo
                ))
            # 4. Incremento de Producto Terminado (SOLO al finalizar)
            producto_final = Producto.query.filter(
                (Producto.codigo_sistema == id_codigo) | (Producto.id_codigo == id_codigo)
            ).with_for_update().first()
            
            if producto_final:
                if 'ENSAMBLADO' in almacen_destino:
                    producto_final.producto_ensamblado = float(producto_final.producto_ensamblado or 0) + cantidad
                elif 'TERMINADO' in almacen_destino:
                    producto_final.p_terminado = float(producto_final.p_terminado or 0) + cantidad

            # 5. CÁLCULO DE MÉTRICAS (KPIs)
            if registro.hora_inicio and registro.hora_fin:
                diff_total = (registro.hora_fin - registro.hora_inicio).total_seconds()
                duracion_real = diff_total - (registro.tiempo_pausa_acumulado or 0)
                
                registro.duracion_segundos = int(max(0, duracion_real))
                registro.tiempo_total_minutos = round(registro.duracion_segundos / 60, 2)
                if cantidad > 0:
                    registro.segundos_por_unidad = round(registro.duracion_segundos / cantidad, 2)

        # Mapeo de Trazabilidad (blindado contra NULLs con defaults explícitos)
        registro.buje_ensamble = id_codigo or registro.buje_ensamble or ''
        registro.buje_origen = buje_origen or registro.buje_origen or ''
        registro.almacen_para_descargar = almacen_origen or registro.almacen_para_descargar or 'P. TERMINADO'
        registro.almacen_destino = almacen_destino or registro.almacen_destino or 'PRODUCTO ENSAMBLADO'
        registro.op_numero = data.get('op_numero') or registro.op_numero or ''

        # Cálculo de consumo_total (cantidad × suma de factores BOM)
        try:
            bom_consumo = calcular_descuentos_ensamble(id_codigo, cantidad)
            if bom_consumo.get('success') and cantidad > 0:
                total_consumo = sum(
                    float(c.get('cantidad_total_descontar', 0))
                    for c in bom_consumo.get('componentes', [])
                )
                registro.consumo_total = round(total_consumo, 4)
        except Exception as bom_err:
            logger.warning(f"[ENSAMBLE] No se pudo calcular consumo_total: {bom_err}")

        # --- GUARDADO FINAL ---
        db.session.commit()
        
        # 7. SINCRONIZACIÓN DE PROGRAMACIÓN (Recálculo Atómico con Fallback)
        op_actual = data.get('op_numero') or registro.op_numero
        if op_actual or id_codigo:
            total_op = db.session.query(db.func.sum(Ensamble.cantidad)).filter(
                Ensamble.id_codigo == id_codigo,
                Ensamble.estado.in_(['FINALIZADO', 'EN_PROCESO', 'TRABAJANDO', 'PAUSADO'])
            )
            
            if op_actual:
                total_op = total_op.filter(Ensamble.op_numero == op_actual)
            
            total_final = total_op.scalar() or 0
            
            # Intento de UPDATE con Fallback: Primero por OP, luego por Código+Fecha
            meta = None
            if op_actual:
                meta = db.session.execute(text("SELECT id_prog FROM db_programacion_ensamble WHERE op_numero = :op"), {"op": op_actual}).first()
            
            if not meta:
                meta = db.session.execute(text("SELECT id_prog FROM db_programacion_ensamble WHERE id_codigo = :cod AND fecha_programada = :f"), {"cod": id_codigo, "f": registro.fecha}).first()

            if meta:
                # Si es FINALIZADO y la cantidad cubre el objetivo, cerrar la meta
                nuevo_estado_prog = None
                if estado_final == 'FINALIZADO':
                    meta_row = db.session.execute(
                        text("SELECT cantidad_objetivo FROM db_programacion_ensamble WHERE id_prog = :id"),
                        {"id": meta[0]}
                    ).first()
                    if meta_row and total_final >= (meta_row[0] or 0):
                        nuevo_estado_prog = 'COMPLETADO'
                
                if nuevo_estado_prog:
                    db.session.execute(text(
                        "UPDATE db_programacion_ensamble "
                        "SET cantidad_realizada = :total, estado = :est, op_numero = :op "
                        "WHERE id_prog = :id"
                    ), {"total": total_final, "est": nuevo_estado_prog, "op": op_actual or '', "id": meta[0]})
                    logger.info(f"[ENSAMBLE] Meta {meta[0]} cerrada como COMPLETADO ({total_final} unidades)")
                else:
                    db.session.execute(text(
                        "UPDATE db_programacion_ensamble "
                        "SET cantidad_realizada = :total, op_numero = :op "
                        "WHERE id_prog = :id"
                    ), {"total": total_final, "op": op_actual or '', "id": meta[0]})
                db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Reporte procesado y métricas calculadas.',
            'id_ensamble': id_ensamble
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ ERROR REPORTE ENSAMBLE: {e}")
        return jsonify({'success': False, 'error': f"Error: {str(e)}"}), 500
