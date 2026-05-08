from flask import Blueprint, jsonify, request
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

        # Sincronización de PNC Detallado (vaya esa info donde debe)
        pnc_detail = data.get('pnc_detail', [])
        if pnc_detail:
            # Limpiar registros previos de PNC vinculados a este id_pulido
            db.session.query(PncInyeccion).filter_by(id_inyeccion=id_pulido).delete()
            db.session.query(PncPulido).filter_by(id_pulido=id_pulido).delete()
            db.session.query(PncEnsamble).filter_by(id_ensamble=id_pulido).delete()

            for pnc_item in pnc_detail:
                proc = pnc_item.get('proceso', '').upper()
                cant = float(pnc_item.get('cantidad') or 0)
                crit = pnc_item.get('criterio', '')
                if cant <= 0: continue

                if proc == 'INYECCION':
                    db.session.add(PncInyeccion(
                        id_pnc_inyeccion=uuid.uuid4().hex[:8],
                        id_inyeccion=id_pulido,
                        id_codigo=registro.codigo,
                        cantidad=cant,
                        criterio=crit
                    ))
                elif proc == 'PULIDO':
                    db.session.add(PncPulido(
                        id_pnc_pulido=uuid.uuid4().hex[:8],
                        id_pulido=id_pulido,
                        codigo=registro.codigo,
                        cantidad=cant,
                        criterio=crit
                    ))
                elif proc == 'ENSAMBLE':
                    db.session.add(PncEnsamble(
                        id_pnc_ensamble=uuid.uuid4().hex[:8],
                        id_ensamble=id_pulido,
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
        return jsonify({"success": False, "error": str(e)}), 500

@pulido_bp.route('/api/pulido/session_active', methods=['GET'])
def get_active_pulido_session():
    try:
        responsable = request.args.get('responsable')
        if not responsable:
            return jsonify({"success": False, "error": "Falta responsable"}), 400
        
        # FIX Efecto Daniela: Filtrar por estado EN_PROCESO/PAUSADO,
        # NO por hora_fin=None (registros migrados no tienen hora_fin)
        sesion = ProduccionPulido.query.filter(
            ProduccionPulido.responsable == responsable,
            ProduccionPulido.estado.in_(['EN_PROCESO', 'PAUSADO', 'PAUSADO_COLA', 'TRABAJANDO'])
        ).order_by(ProduccionPulido.id.desc()).first()

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
                    "estado": sesion.estado
                }
            })
        
        return jsonify({"success": True, "session": None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@pulido_bp.route('/api/pulido/dashboard_stats', methods=['GET'])
@require_role(ROL_ADMINS + ['JEFE PULIDO', 'PULIDO'])
def get_pulido_stats():
    # Placeholder
    return jsonify({"success": True, "message": "Estadísticas de pulido (WIP)"})
