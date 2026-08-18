"""
Servicio de Ejecución de Rayada (subproceso de Ensamble).
Control de tiempos de proceso por referencia de carcaza.
"""
import logging
import uuid
from backend.core.sql_database import db
from backend.models.sql_models import ProduccionRayada
from backend.services.audit_service import AuditService
from backend.utils.formatters import preservar_o_normalizar_prefijo
from backend.utils.time_utils import get_colombia_time

logger = logging.getLogger(__name__)


class RayadaService:

    @staticmethod
    def iniciar(data):
        """Persistencia inmediata EN_PROCESO en db_rayada."""
        if not data:
            raise ValueError('No data provided')

        id_codigo = preservar_o_normalizar_prefijo(data.get('id_codigo', ''))
        if not id_codigo:
            raise ValueError('Referencia de carcaza requerida')

        try:
            ahora = get_colombia_time()
            id_rayada = data.get('id_rayada') or f"RAY-{uuid.uuid4().hex[:8].upper()}"

            existente = db.session.query(ProduccionRayada).filter_by(id_rayada=id_rayada).first()
            if existente:
                return {'ya_registrado': True, 'id_rayada': id_rayada}

            responsable = AuditService.resolver_y_validar_propietario(None, data.get('responsable'))

            # Hora de inicio real capturada por el operario (registro retroactivo
            # permitido); si no la manda, se usa la hora del servidor.
            h_inicio = data.get('hora_inicio')
            if h_inicio:
                try:
                    hi_h, hi_m = h_inicio.split(':')
                    dt_inicio = ahora.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0).replace(tzinfo=None)
                except Exception:
                    dt_inicio = ahora.replace(tzinfo=None)
            else:
                dt_inicio = ahora.replace(tzinfo=None)

            nuevo = ProduccionRayada(
                id_rayada=id_rayada,
                id_ensamble=data.get('id_ensamble'),
                id_codigo=id_codigo,
                responsable=responsable,
                op_numero=data.get('op_numero', ''),
                fecha=ahora.date(),
                hora_inicio=dt_inicio,
                estado='EN_PROCESO'
            )
            db.session.add(nuevo)
            db.session.commit()

            logger.debug(f"✅ [Rayada] Inicio persistido: {id_rayada} ({responsable})")
            return {'ya_registrado': False, 'id_rayada': id_rayada}
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en RayadaService.iniciar: {e}")
            raise

    @staticmethod
    def finalizar(data):
        """Cierra la sesión de rayada: cantidad + hora_fin, calcula métricas de tiempo."""
        if not data:
            raise ValueError('No data provided')

        id_rayada = data.get('id_rayada')
        cantidad = int(data.get('cantidad', 0) or 0)
        if not id_rayada or cantidad <= 0:
            raise ValueError('id_rayada y cantidad requeridos')

        try:
            ahora = get_colombia_time()

            registro = db.session.query(ProduccionRayada).filter_by(id_rayada=id_rayada).first()
            if not registro:
                raise ValueError(f"No existe sesión de rayada '{id_rayada}'")

            # Puede levantar OwnershipMismatchException — se propaga sin transformar
            responsable = AuditService.resolver_y_validar_propietario(registro, data.get('responsable'))

            registro.responsable = responsable
            registro.cantidad = cantidad

            # dt_inicio SIEMPRE viene del registro persistido en iniciar() -- hora_fin
            # es independiente y no requiere que el payload de finalizar reenvíe hora_inicio.
            dt_inicio = registro.hora_inicio or ahora.replace(tzinfo=None)
            dt_fin = ahora.replace(tzinfo=None)
            h_fin = data.get('hora_fin')
            if h_fin:
                try:
                    hf_h, hf_m = h_fin.split(':')
                    dt_fin = ahora.replace(hour=int(hf_h), minute=int(hf_m), second=0, microsecond=0).replace(tzinfo=None)
                except Exception as e_time:
                    logger.warning(f"Error calculando hora_fin rayada: {e_time}")

            duracion_s = int((dt_fin - dt_inicio).total_seconds())
            if duracion_s < 0:
                duracion_s += 86400  # Cruce de medianoche

            registro.hora_inicio = dt_inicio
            registro.hora_fin = dt_fin
            registro.duracion_segundos = duracion_s
            registro.tiempo_total_minutos = round(duracion_s / 60.0, 2)
            registro.segundos_por_unidad = round(duracion_s / cantidad, 2) if cantidad > 0 else 0.0
            registro.pnc_cantidad = int(data.get('pnc_cantidad', 0) or 0)
            registro.observaciones = data.get('observaciones', registro.observaciones)
            registro.estado = 'FINALIZADO'

            db.session.commit()
            logger.info(f"✅ RAYADA FINALIZADA: {id_rayada} ({duracion_s}s)")
            return {'id_rayada': id_rayada}
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en RayadaService.finalizar: {e}")
            raise
