from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import text
from io import BytesIO
from backend.utils.auth_middleware import require_role, ROL_ADMINS
from backend.models.sql_models import db, ProduccionPulido, PncInyeccion, PncPulido, PncEnsamble, BujeRevuelto
from backend.utils.formatters import normalizar_codigo
import uuid
from datetime import datetime
import pytz
import logging
import json

logger = logging.getLogger(__name__)
pulido_bp = Blueprint('pulido_bp', __name__)

@pulido_bp.route('/api/pulido', methods=['POST'])
def registrar_pulido():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        colombia_tz = pytz.timezone('America/Bogota')
        ahora = datetime.now(colombia_tz)

        # Lógica de Upsert (Evitar duplicados por id_pulido)
        id_pulido = data.get('id_pulido')
        registro = ProduccionPulido.query.filter_by(id_pulido=id_pulido).first() if id_pulido else None

        # Guard de ownership: evita que un operario sobrescriba el registro de otro
        incoming_responsable = (data.get('responsable') or '').strip()
        if registro and registro.responsable and incoming_responsable:
            if str(registro.responsable).strip().upper() != incoming_responsable.upper():
                return jsonify({
                    "success": False,
                    "error": "La sesión pertenece a otro operario. Cierra sesión y vuelve a ingresar.",
                    "code": "PULIDO_SESSION_OWNERSHIP_MISMATCH",
                    "id_pulido": id_pulido,
                    "responsable_db": registro.responsable,
                    "responsable_in": incoming_responsable
                }), 409

        if not registro:
            # Si no existe (o fue borrado de la DB), crear uno nuevo para evitar Error 500
            if id_pulido:
                logger.warning(f" [RECOVERY] id_pulido {id_pulido} no encontrado en DB. Creando nuevo registro.")
            registro = ProduccionPulido(id_pulido=id_pulido or f"PUL-{ahora.strftime('%Y%m%d%H%M%S')}")
            db.session.add(registro)

        # Mapeo y Estandarización
        registro.fecha = datetime.strptime(data.get('fecha_inicio', ahora.strftime('%Y-%m-%d')), '%Y-%m-%d').date()
        registro.codigo = normalizar_codigo(data.get('codigo_producto'))
        registro.responsable = data.get('responsable')
        registro.cantidad_real = float(data.get('cantidad_real') or 0)
        registro.pnc_inyeccion = int(data.get('pnc_inyeccion') or 0)
        registro.pnc_pulido = int(data.get('pnc_pulido') or 0)
        registro.criterio_pnc_inyeccion = data.get('criterio_pnc_inyeccion')
        registro.criterio_pnc_pulido = data.get('criterio_pnc_pulido')
        registro.orden_produccion = data.get('orden_produccion') or 'SIN OP'
        registro.observaciones = data.get('observaciones', '')
        registro.estado = data.get('estado', 'FINALIZADO')
        registro.departamento = 'Pulido'  # Estandarización exigida
        registro.lote = data.get('lote') or 'SIN LOTE'
        registro.cantidad_recibida = float(data.get('cantidad_recibida') or 0)
        registro.almacen_destino = data.get('almacen_destino', 'P. TERMINADO')

        # Validación de consistencia (Bujes Buenos + PNC <= Total)
        # Se usa <= porque puede haber otros tipos de PNC no mapeados a columnas fijas
        total_reportado = registro.cantidad_real + registro.pnc_inyeccion + registro.pnc_pulido
        if registro.cantidad_recibida < total_reportado:
            logger.warning(f" [VALIDATION] Inconsistencia en {id_pulido}: Total {registro.cantidad_recibida} < Suma {total_reportado}")
            # No bloqueamos el guardado para evitar pérdida de datos en planta, pero registramos el evento.
            # Opcional: podrías retornar error 400 aquí si prefieres rigidez total.


        # Manejo de Horas y Cálculos de Tiempo
        colombia_tz = pytz.timezone('America/Bogota')
        ahora = datetime.now(colombia_tz)

        if data.get('hora_inicio'):
            h_h, h_m = data['hora_inicio'].split(':')
            dt_ini = ahora.replace(hour=int(h_h), minute=int(h_m), second=0, microsecond=0)
            registro.hora_inicio = dt_ini.replace(tzinfo=None) # Guardar como naive Bogota
        
        if data.get('hora_fin'):
            h_h, h_m = data['hora_fin'].split(':')
            dt_fin = ahora.replace(hour=int(h_h), minute=int(h_m), second=0, microsecond=0)
            registro.hora_fin = dt_fin.replace(tzinfo=None) # Guardar como naive Bogota

        # Cálculo de Métricas (Usando objetos localizados para precisión)
        if data.get('hora_inicio') and data.get('hora_fin'):
            hi_h, hi_m = data['hora_inicio'].split(':')
            hf_h, hf_m = data['hora_fin'].split(':')
            
            t_ini = ahora.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0)
            t_fin = ahora.replace(hour=int(hf_h), minute=int(hf_m), second=0, microsecond=0)
            
            # Tiempo del segmento actual
            diff = t_fin - t_ini
            segundos_segmento = int(diff.total_seconds())
            if segundos_segmento < 0: segundos_segmento += 86400
            
            # Sumar tiempo acumulado de sesiones previas (enviado desde el frontend en ms)
            tiempo_acumulado_ms = float(data.get('tiempo_acumulado_ms') or 0)
            segundos_totales = segundos_segmento + int(tiempo_acumulado_ms / 1000)

            # Descuento automático por pausas programadas (enviado por frontend, en ms)
            descuento_programado_ms = float(data.get('descuento_programado_ms') or 0)
            if descuento_programado_ms > 0:
                segundos_totales = max(0, segundos_totales - int(descuento_programado_ms / 1000))
            
            registro.duracion_segundos = segundos_totales
            registro.tiempo_total_minutos = float(round(segundos_totales / 60.0, 2))
            
            cant = float(registro.cantidad_real or 0)
            if cant > 0:
                registro.segundos_por_unidad = float(round(segundos_totales / cant, 2))
            else:
                registro.segundos_por_unidad = 0.0
            
            # Persistir evidencia del descuento en observaciones (sin migración de DB)
            try:
                detalle = data.get('detalle_descuento_programado')
                if isinstance(detalle, str):
                    detalle = json.loads(detalle)
                if isinstance(detalle, list) and descuento_programado_ms > 0:
                    payload = {
                        "descuento_programado_min": round(descuento_programado_ms / 60000.0, 2),
                        "detalle": detalle
                    }
                    tag = f"[AUTO_BREAK]{json.dumps(payload, ensure_ascii=False)}[/AUTO_BREAK]"
                    obs = (registro.observaciones or "")
                    # Reemplazar tag si ya existía
                    if "[AUTO_BREAK]" in obs and "[/AUTO_BREAK]" in obs:
                        pre = obs.split("[AUTO_BREAK]")[0]
                        post = obs.split("[/AUTO_BREAK]")[-1]
                        registro.observaciones = (pre + tag + post).strip()
                    else:
                        registro.observaciones = (obs + "\n" + tag).strip() if obs else tag
            except Exception as e:
                logger.warning(f"[AUTO_BREAK] No se pudo persistir detalle: {e}")

            logger.info(f" [TIME-DEBUG] {id_pulido} -> Seg: {segundos_segmento}s, Acum: {tiempo_acumulado_ms}ms, DescProg: {descuento_programado_ms}ms, Total: {segundos_totales}s")
        else:
            registro.duracion_segundos = 0
            registro.tiempo_total_minutos = 0.0
            registro.segundos_por_unidad = 0.0

        db.session.flush() # Asegurar que el registro principal tenga ID en la sesión
 
        # Sincronización de PNC Detallado (vaya esa info donde debe)
        pnc_detail = data.get('pnc_detail', [])
        if pnc_detail:
            # Limpiar registros previos de PNC vinculados a este id_pulido
            # Usar registro.id_pulido que es el identificador confirmado en este punto
            db.session.query(PncInyeccion).filter_by(id_inyeccion=registro.id_pulido).delete()
            db.session.query(PncPulido).filter_by(id_pulido=registro.id_pulido).delete()
            db.session.query(PncEnsamble).filter_by(id_ensamble=registro.id_pulido).delete()

            for pnc_item in pnc_detail:
                proc = pnc_item.get('proceso', '').upper()
                cant = float(pnc_item.get('cantidad') or 0)
                crit = pnc_item.get('criterio', '')
                if cant <= 0: continue

                if proc == 'INYECCION':
                    db.session.add(PncInyeccion(
                        id_pnc_inyeccion=uuid.uuid4().hex[:8],
                        id_inyeccion=registro.id_pulido,
                        id_codigo=registro.codigo,
                        cantidad=cant,
                        criterio=crit
                    ))
                elif proc == 'PULIDO':
                    db.session.add(PncPulido(
                        id_pnc_pulido=uuid.uuid4().hex[:8],
                        id_pulido=registro.id_pulido,
                        codigo=registro.codigo,
                        cantidad=cant,
                        criterio=crit
                    ))
                elif proc == 'ENSAMBLE':
                    db.session.add(PncEnsamble(
                        id_pnc_ensamble=uuid.uuid4().hex[:8],
                        id_ensamble=registro.id_pulido,
                        id_codigo=registro.codigo,
                        cantidad=cant,
                        criterio=crit
                    ))

        db.session.flush() # Asegurar que el registro principal tenga ID en la sesión

        # ---------------------------------------------------------
        # Manejo de Bujes Revueltos (NUEVO)
        # ---------------------------------------------------------
        revueltos_list = data.get('revueltos', [])
        logger.info(f" [REVUELTOS-DEBUG] Payload recibido: {revueltos_list}")
        logger.info(f" [REVUELTOS] Procesando {len(revueltos_list)} items para {registro.id_pulido}")
        
        # Limpiar registros previos de revueltos vinculados a este id_pulido
        db.session.query(BujeRevuelto).filter_by(id_pulido=registro.id_pulido).delete()

        for rev_item in revueltos_list:
            cod_rev = normalizar_codigo(rev_item.get('id_codigo'))
            cant_rev = float(rev_item.get('cantidad') or 0)
            logger.info(f" [REVUELTOS] Intentando agregar: {cod_rev} | Cant: {cant_rev}")
            
            if cant_rev <= 0 or not cod_rev: 
                logger.warning(f" [REVUELTOS] Item omitido por validación: {rev_item}")
                continue

            db.session.add(BujeRevuelto(
                id_bujes_revueltos=uuid.uuid4().hex[:8],
                id_pulido=registro.id_pulido,
                id_codigo=cod_rev,
                cantidad=cant_rev,
                codigo_ensamble=cod_rev,
                responsable=registro.responsable
            ))
            logger.info(f" [REVUELTOS] Registro agregado a sesión: {cod_rev}")

        db.session.commit()

        return jsonify({
            "success": True, 
            "message": "Registro de pulido sincronizado",
            "id_pulido": registro.id_pulido,
            "upsert": "UPDATE" if id_pulido and registro.id else "INSERT"
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"❌ [PULIDO-ERROR] Error crítico al registrar: {str(e)}\n{error_trace}")
        return jsonify({
            "success": False, 
            "error": str(e),
            "detail": "Error interno al procesar el reporte de pulido (Revisa logs del servidor)"
        }), 500

@pulido_bp.route('/api/pulido/session_active', methods=['GET'])
def get_active_pulido_session():
    try:
        # Forzar limpieza de caché de sesión para obtener datos frescos de la DB
        db.session.remove()
        
        if request.args.get('ping') == 'true':
            return jsonify({"success": True, "ping": "pong"}), 200

        responsable = request.args.get('responsable')
        if not responsable:
            return jsonify({"success": False, "error": "Falta responsable"}), 400
        
        # FIX Efecto Daniela: Filtrar por estado EN_PROCESO/PAUSADO,
        # NO por hora_fin=None (registros migrados no tienen hora_fin)
        query = ProduccionPulido.query.filter(ProduccionPulido.responsable == responsable)
        
        id_especifico = request.args.get('id_pulido')
        if id_especifico:
            query = query.filter(ProduccionPulido.id_pulido == id_especifico)
        else:
            query = query.filter(ProduccionPulido.estado.in_(['EN_PROCESO', 'PAUSADO', 'PAUSADO_COLA', 'TRABAJANDO']))
            
        sesion = query.order_by(ProduccionPulido.id.desc()).first()

        if sesion:
            return jsonify({
                "success": True,
                "session": {
                    "id_pulido": sesion.id_pulido,
                    "codigo": sesion.codigo,
                    "lote": sesion.lote,
                    "orden_produccion": sesion.orden_produccion,
                    "hora_inicio_dt": sesion.hora_inicio.isoformat() if sesion.hora_inicio else None,
                    "duracion_segundos": sesion.duracion_segundos or 0,
                    "estado": sesion.estado,
                    "tiempo_pausa_acumulado": sesion.tiempo_pausa_acumulado or 0,
                    "hora_pausa": sesion.hora_pausa.isoformat() if (sesion.estado == 'PAUSADO' and sesion.hora_pausa) else None
                }
            })
        
        return jsonify({"success": True, "session": None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@pulido_bp.route('/api/pulido/tareas_pendientes', methods=['GET'])
def get_pulido_tareas_pendientes():
    try:
        responsable = request.args.get('responsable')
        if not responsable:
            return jsonify({"success": False, "error": "Falta responsable"}), 400
        
        tareas = ProduccionPulido.query.filter(
            ProduccionPulido.responsable == responsable,
            ProduccionPulido.estado.in_(['PENDIENTE', 'PAUSADO_COLA'])
        ).order_by(ProduccionPulido.id.desc()).all()
        
        return jsonify({
            "success": True,
            "tareas": [{
                "id_pulido": t.id_pulido,
                "codigo": t.codigo,
                "lote": t.lote,
                "orden_produccion": t.orden_produccion,
                "estado": t.estado
            } for t in tareas]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@pulido_bp.route('/api/pulido/pausar', methods=['POST'])
def pausar_pulido():
    """Registra el inicio de la pausa en el servidor."""
    data = request.json
    id_pulido = data.get('id_pulido')
    try:
        registro = ProduccionPulido.query.filter_by(id_pulido=id_pulido).first()
        if not registro: return jsonify({"success": False, "error": "No encontrado"}), 404
        
        # Blindaje: Forzar timestamp del servidor
        registro.estado = 'PAUSADO'
        registro.hora_pausa = datetime.now()
        db.session.add(registro) # Asegurar marcaje para commit
        db.session.commit()
        
        logger.info(f" [PAUSA] Actividad {id_pulido} pausada a las {registro.hora_pausa}")
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@pulido_bp.route('/api/pulido/reanudar', methods=['POST'])
def reanudar_pulido():
    """Calcula el tiempo de la pausa y lo suma al acumulador."""
    data = request.json
    id_pulido = data.get('id_pulido')
    try:
        registro = ProduccionPulido.query.filter_by(id_pulido=id_pulido).first()
        if not registro: return jsonify({"success": False, "error": "No encontrado"}), 404
        
        if registro.hora_pausa:
            diferencia = datetime.now() - registro.hora_pausa
            segundos_pausa = int(diferencia.total_seconds())
            registro.tiempo_pausa_acumulado = (registro.tiempo_pausa_acumulado or 0) + segundos_pausa
            
        registro.estado = 'TRABAJANDO'
        registro.hora_pausa = None
        db.session.commit()
        return jsonify({"success": True, "acumulado": registro.tiempo_pausa_acumulado})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@pulido_bp.route('/api/pulido/swap_task', methods=['POST'])
def swap_pulido_task():
    try:
        data = request.get_json()
        responsable = str(data.get('responsable') or "")
        id_raw = data.get('id_pulido')

        # Registro de depuración para Render
        logger.info(f" [SWAP-DEBUG] Recibido id_pulido: {id_raw} (Tipo: {type(id_raw)})")

        # Blindaje definitivo contra [object Object] o diccionarios
        if isinstance(id_raw, dict):
            id_nuevo = str(id_raw.get('id_pulido') or "")
        elif str(id_raw) == "[object Object]":
            logger.error(" [SWAP-ERROR] El frontend envió un string '[object Object]'")
            return jsonify({"success": False, "error": "ID de tarea inválido (object)"}), 400
        else:
            id_nuevo = str(id_raw or "")
        
        if not responsable or not id_nuevo or id_nuevo == "None":
            return jsonify({"success": False, "error": "Datos incompletos o ID nulo"}), 400

        # 1. Pausar TODO lo que esté TRABAJANDO para este operario
        # Usamos datetime.now() para asegurar precisión en el registro de pausa
        now = datetime.now()
        trabajos_activos = ProduccionPulido.query.filter(
            ProduccionPulido.responsable == responsable,
            ProduccionPulido.estado == 'TRABAJANDO'
        ).all()
        
        for t in trabajos_activos:
            t.estado = 'PAUSADO_COLA'
            t.hora_pausa = now
            db.session.add(t)
            
        # 2. Activar la nueva tarea
        nueva_tarea = ProduccionPulido.query.filter_by(id_pulido=id_nuevo).first()
        if nueva_tarea:
            nueva_tarea.estado = 'TRABAJANDO'
            nueva_tarea.hora_pausa = None # Limpiar pausa para reanudación
            db.session.add(nueva_tarea)
            
        db.session.commit()
        return jsonify({"success": True, "message": "Intercambio realizado con éxito"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Pulido-Swap] Error crítico: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
@pulido_bp.route('/api/pulido/historial', methods=['GET'])
def get_pulido_historial():
    """
    Endpoint para el historial detallado de Pulido con filtros dinámicos.
    """
    try:
        # 1. Parámetros
        f_inicio = request.args.get('fecha_inicio', '')
        f_fin = request.args.get('fecha_fin', '')
        operario = request.args.get('operario', '')
        id_codigo = request.args.get('id_codigo', '')

        # 2. Base Query con Casts explícitos para evitar OID 25 (TEXT)
        sql = """
            SELECT 
                id,
                id_pulido::TEXT as id_pulido,
                fecha,
                codigo::TEXT as codigo,
                responsable::TEXT as responsable,
                cantidad_real,
                pnc_inyeccion,
                pnc_pulido,
                hora_inicio,
                hora_fin,
                orden_produccion::TEXT as orden_produccion,
                observaciones::TEXT as observaciones,
                cantidad_recibida
            FROM db_pulido
            WHERE 1=1
        """
        params = {}

        # 3. Filtros Dinámicos
        if f_inicio and f_fin:
            sql += " AND CAST(fecha AS DATE) BETWEEN :f_inicio AND :f_fin"
            params['f_inicio'] = f_inicio
            params['f_fin'] = f_fin
        elif f_inicio:
            sql += " AND CAST(fecha AS DATE) >= :f_inicio"
            params['f_inicio'] = f_inicio
        elif f_fin:
            sql += " AND CAST(fecha AS DATE) <= :f_fin"
            params['f_fin'] = f_fin

        if operario and operario.upper() != 'TODOS':
            sql += " AND UPPER(TRIM(responsable)) LIKE :operario"
            params['operario'] = f"%{operario.strip().upper()}%"

        if id_codigo and id_codigo.upper() != 'TODOS':
            sql += " AND UPPER(TRIM(codigo)) LIKE :codigo"
            params['codigo'] = f"%{id_codigo.strip().upper()}%"

        sql += " ORDER BY fecha DESC, id DESC"

        # 4. Ejecución y Conversión Inmediata a Diccionario (Clean Data)
        result = db.session.execute(text(sql), params)
        resultados = [dict(row._mapping) for row in result]

        # 5. Batch Pre-fetch de Revueltos (v5.2 - Zero queries in loop)
        all_ids = [str(r.get('id_pulido') or '').strip() for r in resultados]
        all_ids = [pid for pid in all_ids if pid]  # Filtrar vacíos

        revueltos_map = {}  # { id_pulido: [ {id_codigo, cantidad}, ... ] }
        if all_ids:
            # Una sola consulta para TODOS los revueltos
            placeholders = ', '.join([f':pid_{i}' for i in range(len(all_ids))])
            sql_revs = f"SELECT id_pulido::TEXT as id_pulido, id_codigo::TEXT as id_codigo, COALESCE(cantidad, 0) as cantidad FROM db_bujes_revueltos WHERE id_pulido IN ({placeholders})"
            params_revs = {f'pid_{i}': pid for i, pid in enumerate(all_ids)}
            revs_raw = db.session.execute(text(sql_revs), params_revs)
            for rv in revs_raw:
                rv_dict = dict(rv._mapping)
                pid = str(rv_dict['id_pulido'])
                if pid not in revueltos_map:
                    revueltos_map[pid] = []
                revueltos_map[pid].append(rv_dict)

        # 6. Mapeo para el Frontend (cero consultas en el bucle)
        data = []
        for r in resultados:
            p_id = str(r.get('id_pulido') or '').strip()

            # Lookup directo en memoria
            revs = revueltos_map.get(p_id, [])
            det_revueltos = ""
            if revs:
                det_revueltos = " | REVUELTOS: " + ", ".join([f"{str(rv['id_codigo'])}({float(rv['cantidad'] or 0)})" for rv in revs])

            obs = str(r.get('observaciones') or '').strip()
            detalle_final = f"Obs: {obs}{det_revueltos}" if obs else det_revueltos.strip(" | ")

            data.append({
                'id': int(r['id']),
                'Fecha': r['fecha'].strftime('%d/%m/%Y') if r['fecha'] else '',
                'Tipo': 'PULIDO',
                'Producto': str(r['codigo'] or ''),
                'Responsable': str(r['responsable'] or 'SISTEMA'),
                'cantidad_real': float(r['cantidad_real'] or 0),
                'Cant': float(r['cantidad_real'] or 0),
                'Orden': str(r['orden_produccion'] or p_id or '-'),
                'Extra': str(f"OP: {r['orden_produccion'] or ''}"),
                'Detalle': str(detalle_final.strip()),
                'HORA_INICIO': r['hora_inicio'].strftime('%H:%M') if r['hora_inicio'] else '',
                'HORA_FIN': r['hora_fin'].strftime('%H:%M') if r['hora_fin'] else '',
                'hoja': 'db_pulido',
                'fila': int(r['id']),
                'cantidad_recibida': float(r['cantidad_recibida'] or 0),
                'pnc_inyeccion': int(r['pnc_inyeccion'] or 0),
                'pnc_pulido': int(r['pnc_pulido'] or 0)
            })

        return jsonify(data)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en api/pulido/historial: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@pulido_bp.route('/api/pulido/stats', methods=['GET'])
@require_role(ROL_ADMINS + ['JEFE PULIDO', 'PULIDO'])
def get_pulido_stats():
    # Placeholder
    return jsonify({"success": True, "message": "Estadísticas de pulido (WIP)"})


@pulido_bp.route('/api/pulido/exportar_excel', methods=['GET'])
def exportar_excel_pulido():
    """
    Exportación profesional a Excel del historial de Pulido.
    Usa openpyxl para estilos avanzados (cabecera, cebreado, alertas PNC).
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    try:
        # 1. Parámetros (mismos filtros que el historial)
        f_inicio = request.args.get('fecha_inicio', '')
        f_fin = request.args.get('fecha_fin', '')
        operario = request.args.get('operario', '')
        id_codigo = request.args.get('id_codigo', '')

        # 2. Query con casts
        sql = """
            SELECT
                id, id_pulido::TEXT as id_pulido, fecha,
                codigo::TEXT as codigo, responsable::TEXT as responsable,
                cantidad_real, pnc_inyeccion, pnc_pulido,
                hora_inicio, hora_fin,
                orden_produccion::TEXT as orden_produccion,
                observaciones::TEXT as observaciones,
                cantidad_recibida
            FROM db_pulido
            WHERE 1=1
        """
        params = {}

        if f_inicio and f_fin:
            sql += " AND CAST(fecha AS DATE) BETWEEN :f_inicio AND :f_fin"
            params['f_inicio'] = f_inicio
            params['f_fin'] = f_fin
        elif f_inicio:
            sql += " AND CAST(fecha AS DATE) >= :f_inicio"
            params['f_inicio'] = f_inicio
        elif f_fin:
            sql += " AND CAST(fecha AS DATE) <= :f_fin"
            params['f_fin'] = f_fin

        if operario and operario.upper() != 'TODOS':
            sql += " AND UPPER(TRIM(responsable)) LIKE :operario"
            params['operario'] = f"%{operario.strip().upper()}%"

        if id_codigo and id_codigo.upper() != 'TODOS':
            sql += " AND UPPER(TRIM(codigo)) LIKE :codigo"
            params['codigo'] = f"%{id_codigo.strip().upper()}%"

        sql += " ORDER BY fecha DESC, id DESC"

        result = db.session.execute(text(sql), params)
        resultados = [dict(row._mapping) for row in result]

        # 3. Crear Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Historial Pulido"

        # --- ESTILOS ---
        header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
        header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        thin_border = Border(
            left=Side(style='thin', color='D5D8DC'),
            right=Side(style='thin', color='D5D8DC'),
            top=Side(style='thin', color='D5D8DC'),
            bottom=Side(style='thin', color='D5D8DC')
        )
        zebra_fill = PatternFill(start_color='F2F3F4', end_color='F2F3F4', fill_type='solid')
        pnc_fill = PatternFill(start_color='FADBD8', end_color='FADBD8', fill_type='solid')
        data_align = Alignment(horizontal='center', vertical='center')
        text_align = Alignment(horizontal='left', vertical='center', wrap_text=True)

        # --- CABECERA ---
        columnas = [
            'Fecha', 'Hora Inicio', 'Hora Fin', 'Operario', 'Referencia',
            'Orden/OP', 'Cant. Recibida', 'Cantidad OK', 'PNC Iny', 'PNC Pul', 'Observaciones'
        ]
        for col_idx, titulo in enumerate(columnas, 1):
            cell = ws.cell(row=1, column=col_idx, value=titulo)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        # --- FILAS DE DATOS ---
        for row_idx, r in enumerate(resultados, 2):
            fecha_str = r['fecha'].strftime('%d/%m/%Y') if r['fecha'] else ''
            h_inicio = r['hora_inicio'].strftime('%H:%M') if r['hora_inicio'] else ''
            h_fin = r['hora_fin'].strftime('%H:%M') if r['hora_fin'] else ''
            cant_recibida = float(r['cantidad_recibida'] or 0)
            cant_ok = int(r['cantidad_real'] or 0)
            pnc_i = int(r['pnc_inyeccion'] or 0)
            pnc_p = int(r['pnc_pulido'] or 0)

            fila = [
                fecha_str,
                h_inicio,
                h_fin,
                str(r['responsable'] or 'SISTEMA'),
                str(r['codigo'] or ''),
                str(r['orden_produccion'] or r['id_pulido'] or '-'),
                round(cant_recibida, 1) if cant_recibida != int(cant_recibida) else int(cant_recibida),
                cant_ok,
                pnc_i,
                pnc_p,
                str(r['observaciones'] or '')
            ]

            for col_idx, valor in enumerate(fila, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=valor)
                cell.border = thin_border

                # Alineación: texto a la izquierda, números al centro
                if col_idx in (4, 5, 6, 11):  # Operario, Referencia, Orden, Observaciones
                    cell.alignment = text_align
                else:
                    cell.alignment = data_align

            # Cebreado (filas pares)
            if row_idx % 2 == 0:
                for col_idx in range(1, len(columnas) + 1):
                    ws.cell(row=row_idx, column=col_idx).fill = zebra_fill

            # Alerta PNC (fondo rojo claro si > 0)
            if pnc_i > 0:
                ws.cell(row=row_idx, column=9).fill = pnc_fill
                ws.cell(row=row_idx, column=9).font = Font(bold=True, color='C0392B')
            if pnc_p > 0:
                ws.cell(row=row_idx, column=10).fill = pnc_fill
                ws.cell(row=row_idx, column=10).font = Font(bold=True, color='C0392B')

        # --- AUTO-AJUSTE DE ANCHOS ---
        anchos = [12, 11, 11, 22, 18, 18, 14, 13, 9, 9, 40]
        for i, w in enumerate(anchos, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        # Inmovilizar primera fila
        ws.freeze_panes = 'A2'

        # 4. Generar archivo en memoria
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        fecha_archivo = datetime.now().strftime('%Y-%m-%d')
        filename = f"Historial_Pulido_{fecha_archivo}.xlsx"

        logger.info(f"📊 [Excel] Exportando {len(resultados)} registros de Pulido")

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error exportando Excel Pulido: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
