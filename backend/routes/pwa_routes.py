import os
import json
import logging
from flask import Blueprint, jsonify, request, session, render_template
from backend.core.sql_database import db
from backend.models.sql_models import SuscripcionesPush
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
