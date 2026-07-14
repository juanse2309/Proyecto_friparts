import logging
from backend.core.sql_database import db
from backend.models.sql_models import SuscripcionesPush

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def guardar_suscripcion(usuario_id, suscripcion_data):
        """
        Guarda o actualiza una suscripción Push en la base de datos SQL.
        """
        try:
            endpoint = suscripcion_data.get('endpoint')
            keys = suscripcion_data.get('keys', {})
            p256dh = keys.get('p256dh')
            auth = keys.get('auth')

            if not endpoint or not p256dh or not auth:
                raise ValueError("Datos de suscripción incompletos")

            # Buscar si ya existe el endpoint para actualizarlo (evita duplicados)
            sub = SuscripcionesPush.query.filter_by(endpoint=endpoint).first()
            if sub:
                sub.usuario_id = usuario_id
                sub.p256dh = p256dh
                sub.auth = auth
            else:
                sub = SuscripcionesPush(
                    usuario_id=usuario_id,
                    endpoint=endpoint,
                    p256dh=p256dh,
                    auth=auth
                )
                db.session.add(sub)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error guardando suscripción push: {e}")
            raise e

    @staticmethod
    def enviar_notificacion_masiva(payload_dict):
        """
        Delega el envío iterativo de notificaciones al executor en background.
        """
        from flask import current_app
        from backend.services.task_manager import pwa_executor
        
        # Obtenemos el objeto real de la app para el contexto de background
        app = current_app._get_current_object()
        pwa_executor.submit(NotificationService._tarea_envio_masivo, app, payload_dict)

    @staticmethod
    def _tarea_envio_masivo(app, payload_dict):
        import os
        import json
        from pywebpush import webpush, WebPushException

        with app.app_context():
            from backend.models.sql_models import Usuario
            from backend.core.sql_database import db

            logger.info("Iniciando envío masivo de notificaciones Push...")
            segmento = payload_dict.get('segmento', 'Todos')
            
            # Construir query con JOIN a la tabla Usuario para poder filtrar
            query = db.session.query(SuscripcionesPush).join(
                Usuario, SuscripcionesPush.usuario_id == Usuario.username
            )

            if segmento == 'Clientes':
                query = query.filter(Usuario.rol.ilike('cliente'))
            elif segmento == 'Empleados':
                query = query.filter(~Usuario.rol.ilike('cliente'))
            
            suscripciones = query.all()
            logger.info(f"==> Suscripciones encontradas en BD para segmento '{segmento}': {len(suscripciones)}")

            vapid_private_key = os.environ.get('VAPID_PRIVATE_KEY')
            vapid_subject = os.environ.get('VAPID_SUBJECT', 'mailto:admin@friparts.com')

            if not vapid_private_key:
                logger.error("VAPID_PRIVATE_KEY no está configurada.")
                return

            payload_str = json.dumps(payload_dict)

            for sub in suscripciones:
                sub_info = {
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                }
                try:
                    webpush(
                        subscription_info=sub_info,
                        data=payload_str,
                        vapid_private_key=vapid_private_key,
                        vapid_claims={"sub": vapid_subject}
                    )
                except WebPushException as ex:
                    # AUTO-LIMPIEZA ATÓMICA
                    if ex.response is not None and ex.response.status_code in [404, 410]:
                        logger.warning(f"Suscripción inactiva detectada (usuario_id {sub.usuario_id}). Eliminando...")
                        try:
                            db.session.delete(sub)
                            db.session.commit()
                        except Exception as delete_ex:
                            db.session.rollback()
                            logger.error(f"Error limpiando suscripción {sub.id}: {delete_ex}")
                    else:
                        logger.error(f"Error enviando notificación a {sub.usuario_id}: {ex}")
                except Exception as e:
                    logger.error(f"Error inesperado enviando push a {sub.usuario_id}: {e}")
            
            logger.info(f"Envío masivo finalizado. Segmento: {segmento}. Total intentados: {len(suscripciones)}")
