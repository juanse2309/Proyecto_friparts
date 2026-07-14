import os
import logging
from flask import Blueprint, jsonify, request, session, render_template
from backend.services.notification_service import NotificationService

pwa_bp = Blueprint('pwa', __name__)
logger = logging.getLogger(__name__)

@pwa_bp.route('/admin/notificaciones', methods=['GET'])
def render_notificaciones_admin():
    """Renderiza el panel de envío de notificaciones (Protegido)."""
    role = session.get('role', '')
    if role not in ['ADMIN', 'ADMINISTRADOR', 'ADMINISTRACION', 'MARKETING']:
        return "Acceso denegado: Se requieren privilegios de administrador o marketing.", 403
    return render_template('admin/notificaciones_push.html')

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
        print(f"DEBUG PUSH: Suscripción recibida desde {request.remote_addr}")

        # Extraemos el usuario desde la cookie de sesión de Flask
        usuario_id = session.get('user')
        if not usuario_id:
            return jsonify({"success": False, "message": "Usuario no autenticado"}), 401

        if not raw_json:
            return jsonify({"success": False, "message": "No se recibió un JSON válido"}), 400

        # Acepta tanto si viene el objeto directo como si viene envuelto
        suscripcion = raw_json.get('subscription') or raw_json

        if not suscripcion.get('endpoint') or not suscripcion.get('keys'):
            return jsonify({"success": False, "message": "Estructura de suscripción inválida"}), 400

        # Delegamos en el NotificationService puro
        NotificationService.guardar_suscripcion(usuario_id, suscripcion)
        return jsonify({"success": True, "message": "Suscripción guardada exitosamente"}), 200

    except Exception as e:
        logger.error(f"Error en /api/pwa/suscribir: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@pwa_bp.route('/api/pwa/admin/enviar', methods=['POST'])
def enviar_masivo():
    """Recibe datos para enviar una notificación masiva (Protegido)."""
    try:
        role = session.get('role', '')
        if role not in ['ADMIN', 'ADMINISTRADOR', 'ADMINISTRACION', 'MARKETING']:
            return jsonify({"status": "error", "message": "Acceso denegado"}), 403

        data = request.json
        titulo = data.get('titulo', 'Notificación Friparts')
        mensaje = data.get('mensaje', '')
        url_destino = data.get('url_destino', '/')
        segmento = data.get('segmento', 'Todos')

        payload_dict = {
            "title": titulo,
            "body": mensaje,
            "url": url_destino,
            "segmento": segmento
        }

        # Delegar ejecución al motor asíncrono
        NotificationService.enviar_notificacion_masiva(payload_dict)

        # Retornar inmediatamente (HTTP 202 Accepted)
        return jsonify({"status": "procesando"}), 202

    except Exception as e:
        logger.error(f"Error en /api/pwa/admin/enviar: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@pwa_bp.route('/api/pwa/debug/info', methods=['GET'])
def debug_pwa_info():
    """Retorna métricas para validar el estado de Web Push (Solo Admin)."""
    try:
        role = session.get('role', '')
        if role not in ['ADMIN', 'ADMINISTRADOR', 'ADMINISTRACION']:
            return jsonify({"success": False, "message": "Acceso denegado"}), 403

        from backend.models.sql_models import SuscripcionesPush
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
    """Dispara un mensaje a la última suscripción generada para pruebas en caliente."""
    try:
        from backend.models.sql_models import SuscripcionesPush
        import json
        from pywebpush import webpush, WebPushException

        # Obtener la suscripción más reciente
        ultima_sub = SuscripcionesPush.query.order_by(SuscripcionesPush.creado_en.desc()).first()
        
        if not ultima_sub:
            return jsonify({"success": False, "message": "No hay suscripciones en la BD."}), 404

        payload = {
           "title": "🚨 FriTech: Prueba de Planta",
           "body": "El puente de notificaciones PWA está operando al 100% en FRITECH.",
           "icon": "/static/img/icon-192.png",
           "badge": "/static/img/icon-192.png"
        }

        try:
            sub_info = ultima_sub.suscripcion_info
            if isinstance(sub_info, str):
                sub_info = json.loads(sub_info)
                
            webpush(
                subscription_info=sub_info,
                data=json.dumps(payload),
                vapid_private_key=os.environ.get("VAPID_PRIVATE_KEY"),
                vapid_claims={"sub": os.environ.get("VAPID_SUBJECT", "mailto:soporte@fritech.com")}
            )
            return jsonify({
                "success": True, 
                "message": "Notificación disparada con éxito.",
                "endpoint_usado": sub_info.get("endpoint")
            }), 200
        except WebPushException as ex:
            return jsonify({"success": False, "message": "Error WebPush", "detail": repr(ex)}), 500
    except Exception as e:
        logger.error(f"Error en /api/pwa/test-notificacion: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
