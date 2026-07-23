from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import uuid
import json
from backend.core.sql_database import db
from backend.models.sql_models import ProgramacionEnsamble, Ensamble, Producto, OperacionLog, PncEnsamble
from backend.services.bom_service import calcular_descuentos_ensamble
from sqlalchemy import text
from backend.services.audit_service import AuditService, OwnershipMismatchException
from backend.config.constants import FALLBACK_OPERARIO

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
        
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy import text

        stmt = insert(ProgramacionEnsamble).values(
            id_codigo=id_codigo,
            cantidad_objetivo=cantidad_objetivo,
            op_numero=data.get('op_numero'),
            fecha_programada=fecha_prog,
            estado='PENDIENTE'
        )

        # UPSERT ante conflicto en uq_programacion_ensamble
        stmt = stmt.on_conflict_do_update(
            index_elements=['fecha_programada', 'id_codigo', text("COALESCE(op_numero, '')")],
            set_={
                'cantidad_objetivo': stmt.excluded.cantidad_objetivo,
                'estado': stmt.excluded.estado
            }
        ).returning(ProgramacionEnsamble.id_prog)

        res = db.session.execute(stmt).fetchone()
        db.session.commit()
        
        id_prog_val = res[0] if res else None
        return jsonify({'success': True, 'id_prog': id_prog_val})
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
        
        movimientos_inventario = []
        
        # 1. Identificar el registro principal (es_final = True)
        main_reg = next((r for r in registros_data if r.get('es_final')), registros_data[0])
        estado_final = main_reg.get('estado', 'EN_PROCESO')
        
        # Buscar si ya existe el registro final en DB para validar propiedad
        registro_final_db = Ensamble.query.filter_by(
            id_ensamble=id_ensamble_global, 
            buje_ensamble=main_reg.get('buje_ensamble')
        ).first()

        # Guard de ownership centralizado con AuditService
        try:
            responsable = AuditService.resolver_y_validar_propietario(registro_final_db, main_reg.get('responsable'))
        except OwnershipMismatchException as e:
            return jsonify({
                "success": False,
                "error": e.message,
                "code": "ENSAMBLE_SESSION_OWNERSHIP_MISMATCH",
                "responsable_db": e.responsable_db,
                "responsable_in": e.responsable_in
            }), 409
        
        logger.info(f"[ENSAMBLE-MULTI] Procesando {len(registros_data)} registros para id_ensamble={id_ensamble_global}")

        for reg_data in registros_data:
            id_codigo_ancla = reg_data.get('id_codigo')
            buje_detalle = reg_data.get('buje_ensamble')
            cantidad = float(reg_data.get('cantidad', 0) or 0)
            es_final_flag = reg_data.get('es_final', False) # Flag local para lógica interna
            
            # UPSERT: Solo intentamos recuperar el registro si es el producto final (fila de sesión)
            registro = None
            if es_final_flag:
                registro = registro_final_db
            
            if not registro:
                # Si no es el final o es nuevo, buscar si existe por combinación
                if not es_final_flag:
                    registro = Ensamble.query.filter_by(
                        id_ensamble=id_ensamble_global, 
                        buje_ensamble=buje_detalle
                    ).first()
                if not registro:
                    registro = Ensamble(id_ensamble=id_ensamble_global, id_codigo=id_codigo_ancla)
                    if es_final_flag:
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
                from backend.app import registrar_entrada, registrar_salida
                # Descontar si hay origen
                if registro.almacen_para_descargar:
                    almacen = registro.almacen_para_descargar.upper()
                    bodega = "P. TERMINADO" if 'TERMINADO' in almacen else "PRODUCTO ENSAMBLADO"
                    res_mov = registrar_salida(buje_detalle, cantidad, bodega)
                    if res_mov and "error" not in res_mov:
                        movimientos_inventario.append(res_mov)
                    
                    db.session.add(OperacionLog(
                        modulo='ENSAMBLE', operario=responsable, accion='CONSUMO_MULTI',
                        detalles=f"Descontado {cantidad} de {buje_detalle} para ensamble {id_ensamble_global}"
                    ))

                # Incrementar si hay destino
                if registro.almacen_destino:
                    almacen = registro.almacen_destino.upper()
                    bodega = "PRODUCTO ENSAMBLADO" if 'ENSAMBLADO' in almacen else "P. TERMINADO"
                    res_mov = registrar_entrada(buje_detalle, cantidad, bodega)
                    if res_mov and "error" not in res_mov:
                        movimientos_inventario.append(res_mov)

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

                    # --- PROCESAMIENTO AVANZADO DE PNC POR COMPONENTE (BOM) ---
                    pnc_cant = int(reg_data.get('pnc', 0) or 0)
                    if pnc_cant > 0:
                        pnc_detalles_raw = reg_data.get('pnc_detalles', [])
                        
                        # Si viene como string debido al formateo del payload, parsearlo de forma segura
                        if isinstance(pnc_detalles_raw, str):
                            try:
                                pnc_detalles_list = json.loads(pnc_detalles_raw)
                            except Exception:
                                pnc_detalles_list = []
                        else:
                            pnc_detalles_list = pnc_detalles_raw

                        # Si logramos extraer la lista desglosada del BOM
                        if pnc_detalles_list and isinstance(pnc_detalles_list, list):
                            for item in pnc_detalles_list:
                                comp_codigo = item.get('codigo_componente')
                                comp_cant = int(item.get('cantidad', 0) or 0)
                                comp_criterio = item.get('criterio', 'NO ESPECIFICADO')
                                
                                if comp_cant > 0:
                                    nuevo_pnc_comp = PncEnsamble(
                                        id_ensamble=id_ensamble_global, 
                                        id_codigo=id_codigo_ancla,       # El producto padre original
                                        cantidad=comp_cant, 
                                        criterio=comp_criterio,
                                        codigo_ensamble=comp_codigo       # <--- ¡ESTE ES EL CAMBIO CLAVE! Guardamos el código del componente hijo (BOM)
                                    )
                                    db.session.add(nuevo_pnc_comp)
                        else:
                            # Lógica de respaldo (Fallback) si por alguna razón el array llegó vacío pero marcaron cantidad general
                            db.session.add(PncEnsamble(
                                id_ensamble=id_ensamble_global, 
                                id_codigo=id_codigo_ancla, 
                                cantidad=pnc_cant, 
                                criterio=str(pnc_detalles_raw) or "Defecto general sin desglose",
                                codigo_ensamble=id_codigo_ancla
                            ))

        # --- Propagación de avances a cubetas FIFO (db_distribucion_op_pedidos) ---
        op_actual = main_reg.get('op_numero')
        id_prod_final = main_reg.get('id_codigo')
        cantidad_real = float(main_reg.get('cantidad', 0) or 0)

        if estado_final == 'FINALIZADO' and op_actual and str(op_actual).strip() != 'SIN OP' and cantidad_real > 0:
            from backend.models.sql_models import DistribucionOpPedidos
            
            op_limpia = str(op_actual or '').strip()
            codigo_limpio = str(id_prod_final or '').replace('FR-', '').strip()
            
            # Buscar las cubetas por OP y Referencia ordenadas de forma ascendente
            cubetas = db.session.query(DistribucionOpPedidos).filter(
                DistribucionOpPedidos.op_world_office == op_limpia,
                DistribucionOpPedidos.codigo_producto == codigo_limpio
            ).order_by(DistribucionOpPedidos.id_distribucion.asc()).all()

            piezas_por_repartir = cantidad_real
            
            # Validación y creación de cubeta de contingencia (Nivelación Retroactiva)
            if not cubetas and piezas_por_repartir > 0:
                # Intentar buscar el id_pedido de otra cubeta asociada a la misma OP
                pedido_asoc = db.session.query(DistribucionOpPedidos.id_pedido).filter(
                    DistribucionOpPedidos.op_world_office == op_limpia
                ).first()
                id_pedido_final = pedido_asoc[0] if (pedido_asoc and pedido_asoc[0]) else f"PED-IMPREVISTO-{op_limpia}"
                
                logger.info(f" ⚠️ [ENSAMBLE-CONTINGENCIA] Creando cubeta temporal para OP: {op_limpia}, Producto: {codigo_limpio}, Pedido: {id_pedido_final}")
                nueva_cubeta = DistribucionOpPedidos(
                    op_world_office=op_limpia,
                    id_pedido=id_pedido_final,
                    codigo_producto=codigo_limpio,
                    cant_requerida=piezas_por_repartir,
                    cant_inyectada=piezas_por_repartir,
                    cant_pulida=piezas_por_repartir,
                    cant_ensamblada=piezas_por_repartir,
                    cant_alistada=0
                )
                db.session.add(nueva_cubeta)
                db.session.flush() # Sincronizar temporalmente en sesión
                cubetas = [nueva_cubeta]
                piezas_por_repartir = 0.0 # Consumido por completo
            
            logger.info(f" 📦 [ENSAMBLE-FIFO] Propagando {piezas_por_repartir} piezas a {len(cubetas)} cubetas. OP: {op_limpia}, Producto: {codigo_limpio}")

            for cubeta in cubetas:
                if piezas_por_repartir <= 0:
                    break
                
                # Cuánto le falta a esta cubeta en la etapa de ensamble
                falta = max(0, (cubeta.cant_requerida or 0) - (cubeta.cant_ensamblada or 0))
                if falta > 0:
                    if piezas_por_repartir >= falta:
                        cubeta.cant_ensamblada = (cubeta.cant_ensamblada or 0) + falta
                        piezas_por_repartir -= falta
                    else:
                        cubeta.cant_ensamblada = (cubeta.cant_ensamblada or 0) + piezas_por_repartir
                        piezas_por_repartir = 0

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
            'id_ensamble': id_ensamble_global,
            'movimientos_inventario': movimientos_inventario
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ ERROR REPORTE MULTI-ENSAMBLE: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ensamble_bp.route('/api/pnc/registrar_ensamble', methods=['POST'])
def registrar_pnc_ensamble():
    """
    Registra (o limpia) el desglose de PNC de Ensamble en db_pnc_ensamble.
    Body JSON:
      id_ensamble - ID de la sesión de ensamble
      id_codigo   - Código del producto final
      defectos    - {
          "Mal Ajuste / Pieza Suelta": N,
          "Componente Faltante": N,
          "Daño en Empaque / Fisura": N
        }
    """
    try:
        data = request.get_json() or {}
        id_ensamble = data.get('id_ensamble')
        id_codigo   = data.get('id_codigo')
        defectos    = data.get('defectos', {})

        if not id_ensamble or not id_codigo:
            return jsonify({"success": False, "error": "id_ensamble e id_codigo son obligatorios"}), 400

        # Eliminar registro previo para esta sesión + producto
        db.session.query(PncEnsamble).filter_by(id_ensamble=id_ensamble, id_codigo=id_codigo).delete()

        # Mapear los 3 criterios específicos de Ensamble
        mal_ajuste  = float(defectos.get("Mal Ajuste / Pieza Suelta", 0) or 0)
        faltante    = float(defectos.get("Componente Faltante", 0) or 0)
        dano_emp    = float(defectos.get("Daño en Empaque / Fisura", 0) or 0)
        total_pnc   = mal_ajuste + faltante + dano_emp

        # Sync pnc on the parent Ensamble record
        registro_ens = Ensamble.query.filter_by(
            id_ensamble=id_ensamble,
            buje_ensamble=id_codigo
        ).first()

        # Guard de ownership centralizado con AuditService
        try:
            responsable = AuditService.resolver_y_validar_propietario(registro_ens, data.get('responsable') or data.get('operario'))
        except OwnershipMismatchException as e:
            return jsonify({
                "success": False,
                "error": e.message,
                "code": "ENSAMBLE_SESSION_OWNERSHIP_MISMATCH",
                "responsable_db": e.responsable_db,
                "responsable_in": e.responsable_in
            }), 409

        if total_pnc > 0:
            criterio_str = (
                f"Mal Ajuste: {int(mal_ajuste)}, "
                f"Comp. Faltante: {int(faltante)}, "
                f"Daño/Fisura: {int(dano_emp)}"
            )
            nuevo_pnc = PncEnsamble(
                id_pnc_ensamble=uuid.uuid4().hex[:8],
                id_ensamble=id_ensamble,
                id_codigo=id_codigo,
                cantidad=total_pnc,
                criterio=criterio_str,
                codigo_ensamble=id_codigo
            )
            db.session.add(nuevo_pnc)

            if registro_ens:
                registro_ens.pnc = int(round(total_pnc))

            db.session.commit()
            logger.info(f"✅ PNC Ensamble registrado para {id_codigo} en {id_ensamble}: Total={total_pnc}")
            return jsonify({
                "success": True,
                "message": "PNC de Ensamble registrado en db_pnc_ensamble",
                "total_pnc": total_pnc
            }), 200
        else:
            db.session.commit()
            return jsonify({
                "success": True,
                "message": "Sin defectos de PNC para Ensamble",
                "total_pnc": 0
            }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error registrando PNC Ensamble: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
