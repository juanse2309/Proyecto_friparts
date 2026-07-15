import os
import json
import logging
import threading
from flask import Blueprint, jsonify, request, session, render_template
from backend.core.sql_database import db
from backend.models.sql_models import SuscripcionesPush, Usuario
from backend.services.notification_service import NotificationService

pwa_bp = Blueprint('pwa', __name__)
logger = logging.getLogger(__name__)

@pwa_bp.route('/api/pwa/vapid-public', methods=['GET'])
def get_vapid_public():
    """Retorna la llave pública VAPID para suscribir clientes."""
    public_key = os.environ.get('VAPID_PUBLIC_KEY')
    if not public_key:
        return jsonify({"success": False, "message": "VAPID key no configurada"}), 500
    return jsonify({"success": True, "vapid_public_key": public_key}), 200

@pwa_bp.route('/api/pwa/suscribir', methods=['POST'])
def suscribir():
    """Recibe y guarda la suscripción Push del cliente."""
    try:
        raw_json = request.get_json(silent=True)

        usuario_id = session.get('user')
        if not usuario_id:
            return jsonify({"success": False, "message": "Usuario no autenticado"}), 401

        if not raw_json:
            return jsonify({"success": False, "message": "No se recibió un JSON válido"}), 400

        # Acepta tanto si viene el objeto directo como si viene envuelto
        suscripcion = raw_json.get('subscription') or raw_json

        if not suscripcion.get('endpoint') or not suscripcion.get('keys'):
            return jsonify({"success": False, "message": "Estructura de suscripción inválida"}), 400

        NotificationService.guardar_suscripcion(usuario_id, suscripcion)
        return jsonify({"success": True, "message": "Suscripción guardada exitosamente"}), 200

    except Exception as e:
        logger.error(f"Error en /api/pwa/suscribir: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ====================================================================
# ENVÍO MASIVO (Panel Administrativo integrado en SPA)
# ====================================================================

@pwa_bp.route('/api/pwa/enviar-masivo', methods=['POST'])
def enviar_masivo():
    """Recibe datos para enviar una notificación masiva. Protegido por rol."""
    try:
        role = session.get('role', '')
        if role not in ['ADMIN', 'ADMINISTRADOR', 'ADMINISTRACION', 'MARKETING']:
            return jsonify({"success": False, "message": "Acceso denegado"}), 403

        data = request.json
        titulo = data.get('title', data.get('titulo', 'Notificación FriTech'))
        mensaje = data.get('body', data.get('mensaje', ''))
        url_destino = data.get('url_destino', '/')
        segmento = data.get('segmento', 'Todos')

        payload_dict = {
            "title": titulo,
            "body": mensaje,
            "icon": "/static/img/icon-192.png",
            "badge": "/static/img/icon-192.png",
            "url": url_destino,
            "segmento": segmento,
            "requireInteraction": False,
            "urgency": "high"
        }

        # Delegar ejecución al motor asíncrono
        NotificationService.enviar_notificacion_masiva(payload_dict)

        # Retornar inmediatamente (HTTP 202 Accepted)
        return jsonify({"success": True, "status": "procesando", "message": "Notificaciones encoladas para envío en segundo plano."}), 202

    except Exception as e:
        logger.error(f"Error en /api/pwa/enviar-masivo: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Mantener compatibilidad con el endpoint anterior
@pwa_bp.route('/api/pwa/admin/enviar', methods=['POST'])
def enviar_masivo_legacy():
    """Alias de compatibilidad para el endpoint antiguo."""
    return enviar_masivo()

# ====================================================================
# DEBUG Y PRUEBAS
# ====================================================================

@pwa_bp.route('/api/pwa/debug/info', methods=['GET'])
def debug_pwa_info():
    """Retorna métricas para validar el estado de Web Push (Solo Admin)."""
    try:
        role = session.get('role', '')
        if role not in ['ADMIN', 'ADMINISTRADOR', 'ADMINISTRACION']:
            return jsonify({"success": False, "message": "Acceso denegado"}), 403

        total_suscripciones = SuscripcionesPush.query.count()
        
        vapid_pub_exists = bool(os.environ.get('VAPID_PUBLIC_KEY'))
        vapid_priv_exists = bool(os.environ.get('VAPID_PRIVATE_KEY'))

        return jsonify({
            "success": True,
            "metrics": {
                "total_suscripciones": total_suscripciones,
                "keys_status": {
                    "public_key_loaded": vapid_pub_exists,
                    "private_key_loaded": vapid_priv_exists
                }
            }
        }), 200
    except Exception as e:
        logger.error(f"Error en /api/pwa/debug/info: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@pwa_bp.route('/api/pwa/test-notificacion', methods=['POST'])
def test_notificacion():
    """Dispara un mensaje de prueba a la última suscripción registrada."""
    try:
        from pywebpush import webpush, WebPushException

        ultima_sub = SuscripcionesPush.query.order_by(SuscripcionesPush.id.desc()).first()
        
        if not ultima_sub:
            return jsonify({"success": False, "message": "No hay suscripciones en la BD."}), 404

        payload = {
           "title": "🚨 FriTech: Prueba de Planta",
           "body": "El puente de notificaciones PWA está operando al 100% en FRITECH.",
           "icon": "/static/img/icon-192.png",
           "badge": "/static/img/icon-192.png",
           "requireInteraction": False,
           "urgency": "high"
        }

        sub_info = {
            "endpoint": ultima_sub.endpoint,
            "keys": {
                "p256dh": ultima_sub.p256dh,
                "auth": ultima_sub.auth
            }
        }

        try:
            webpush(
                subscription_info=sub_info,
                data=json.dumps(payload),
                vapid_private_key=os.environ.get("VAPID_PRIVATE_KEY"),
                vapid_claims={"sub": os.environ.get("VAPID_SUBJECT", "mailto:soporte@fritech.com")}
            )
            return jsonify({
                "success": True, 
                "message": "Notificación disparada con éxito.",
                "endpoint_usado": sub_info["endpoint"][:80] + "..."
            }), 200
        except WebPushException as ex:
            # Auto-limpieza si el token expiró
            if ex.response is not None and ex.response.status_code in [404, 410]:
                db.session.delete(ultima_sub)
                db.session.commit()
                return jsonify({"success": False, "message": "Token expirado. Suscripción eliminada automáticamente."}), 410
            return jsonify({"success": False, "message": "Error WebPush", "detail": repr(ex)}), 500
    except Exception as e:
        logger.error(f"Error en /api/pwa/test-notificacion: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@pwa_bp.route('/api/pwa/test-push', methods=['POST'])
def test_push_individual():
    """Ruta de prueba que envía un Push al usuario actual en sesión invocando el motor principal."""
    usuario_id = session.get('user')
    if not usuario_id:
        return jsonify({"success": False, "message": "Usuario no autenticado"}), 401

    try:
        titulo = "🚀 Prueba de Push Exitosa"
        cuerpo = f"Hola {usuario_id}, tu motor nativo de notificaciones PWA funciona perfectamente."
        
        exito = NotificationService.enviar_notificacion_push(
            user_id=usuario_id,
            titulo=titulo,
            cuerpo=cuerpo,
            url_destino='/'
        )
        
        if exito:
            return jsonify({"success": True, "message": f"Notificación enviada a todos los dispositivos de {usuario_id}"}), 200
        else:
            return jsonify({"success": False, "message": "No se encontraron suscripciones válidas o falló el envío"}), 404
            
    except Exception as e:
        logger.error(f"Error en /api/pwa/test-push: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ====================================================================
# BROADCAST B2B MARKETING (Asíncrono)
# ====================================================================

def _worker_broadcast(app, titulo, cuerpo, url_destino, image_url, destino):
    """Función worker que ejecuta el envío masivo en un hilo separado."""
    with app.app_context():
        try:
            # Segmentación dinámica según el destino seleccionado
            if destino == 'todos':
                # Sin filtro de rol: todas las suscripciones registradas
                suscripciones = SuscripcionesPush.query.all()
            elif destino == 'planta':
                # Personal operativo de la fábrica
                roles_planta = ['INYECCION', 'PULIDO', 'ENSAMBLE', 'MEZCLA',
                                'CALIDAD', 'JEFE', 'SUPERVISOR', 'OPERARIO', 'MOLIDO']
                filtros_rol = [Usuario.rol.ilike(f'%{r}%') for r in roles_planta]
                suscripciones = db.session.query(SuscripcionesPush).join(
                    Usuario, SuscripcionesPush.user_id == Usuario.username
                ).filter(
                    db.or_(*filtros_rol)
                ).all()
            else:
                # Default: solo clientes
                suscripciones = db.session.query(SuscripcionesPush).join(
                    Usuario, SuscripcionesPush.user_id == Usuario.username
                ).filter(
                    Usuario.rol.ilike('cliente')
                ).all()

            logger.info(f"[BROADCAST] Segmento='{destino}'. Endpoints encontrados: {len(suscripciones)}")

            import os
            from pywebpush import webpush, WebPushException

            vapid_private_key = os.environ.get('VAPID_PRIVATE_KEY')
            vapid_subject = os.environ.get('VAPID_SUBJECT', 'mailto:admin@friparts.com')

            if not vapid_private_key:
                logger.error("[BROADCAST B2B] VAPID_PRIVATE_KEY no configurada.")
                return

            payload_dict = {
                "title": titulo,
                "body": cuerpo,
                "icon": "/static/img/icon-192.png",
                "badge": "/static/img/icon-192.png",
                "data": {"url": url_destino}
            }
            if image_url:
                payload_dict["image"] = image_url

            payload_str = json.dumps(payload_dict)
            enviados = 0

            for sub in suscripciones:
                sub_info = {
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
                }
                try:
                    webpush(
                        subscription_info=sub_info,
                        data=payload_str,
                        vapid_private_key=vapid_private_key,
                        vapid_claims={"sub": vapid_subject}
                    )
                    enviados += 1
                except WebPushException as ex:
                    if ex.response is not None and ex.response.status_code in [404, 410]:
                        logger.warning(f"[BROADCAST B2B] Endpoint muerto ({sub.user_id}). Eliminando...")
                        try:
                            db.session.delete(sub)
                            db.session.commit()
                        except Exception as e_del:
                            db.session.rollback()
                            logger.error(f"[BROADCAST B2B] Error limpiando suscripción: {e_del}")
                    else:
                        logger.error(f"[BROADCAST B2B] Error WebPush para {sub.user_id}: {ex}")
                except Exception as e:
                    logger.error(f"[BROADCAST B2B] Error inesperado para {sub.user_id}: {e}")

            logger.info(f"[BROADCAST B2B] Finalizado. Enviados: {enviados}/{len(suscripciones)}")
        except Exception as e:
            logger.error(f"[BROADCAST B2B] Error fatal en worker: {e}")
        finally:
            # Liberar conexión al pool de SQLAlchemy (previene Connection Pool Leak)
            db.session.remove()


@pwa_bp.route('/api/pwa/broadcast', methods=['POST'])
def broadcast_clientes():
    """Broadcast masivo a todos los clientes B2B. Retorna 202 inmediatamente."""
    role = session.get('role', '')
    if role not in ['ADMIN', 'ADMINISTRADOR', 'ADMINISTRACION', 'MARKETING']:
        return jsonify({"success": False, "message": "Acceso denegado"}), 403

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "message": "JSON requerido"}), 400

        titulo = data.get('titulo', 'Friparts')
        cuerpo = data.get('cuerpo', '')
        url_destino = data.get('url_destino', '/')
        image_url = data.get('image_url') or None
        destino = data.get('destino', 'clientes')

        # Validar destino contra valores permitidos
        if destino not in ('todos', 'planta', 'clientes'):
            destino = 'clientes'

        # Guard: Protección contra Payload Overflow (límite 4KB Push API)
        if image_url:
            if image_url.startswith('data:image'):
                logger.warning(f"[BROADCAST] image_url rechazada: base64 embebido detectado.")
                return jsonify({"success": False, "message": "No se permiten imágenes base64 embebidas. Usa una URL pública."}), 400
            if len(image_url) > 250:
                logger.warning(f"[BROADCAST] image_url rechazada: {len(image_url)} chars (máx 250).")
                return jsonify({"success": False, "message": f"La URL de imagen es demasiado larga ({len(image_url)} chars). Máximo 250."}), 400

        if not cuerpo:
            return jsonify({"success": False, "message": "El campo 'cuerpo' es obligatorio"}), 400

        from flask import current_app
        app = current_app._get_current_object()

        hilo = threading.Thread(
            target=_worker_broadcast,
            args=(app, titulo, cuerpo, url_destino, image_url, destino),
            daemon=True
        )
        hilo.start()

        return jsonify({
            "success": True,
            "status": "procesando",
            "destino": destino,
            "message": f"Campaña encolada para segmento '{destino}' en segundo plano."
        }), 202

    except Exception as e:
        logger.error(f"Error en /api/pwa/broadcast: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ====================================================================
# VISTA: Panel de Marketing Push
# ====================================================================

@pwa_bp.route('/marketing-push')
def vista_marketing_push():
    """Sirve la interfaz de Marketing Push para administradores."""
    role = session.get('role', '')
    if role not in ['ADMIN', 'ADMINISTRADOR', 'ADMINISTRACION', 'MARKETING']:
        return jsonify({"success": False, "message": "Acceso denegado"}), 403
    return render_template('marketing_push.html')
