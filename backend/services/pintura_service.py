"""
Servicio de Ejecución de Pintura (subproceso de Ensamble).
Registra ml de insumo consumido y calcula rendimiento (ml/unidad).
"""
import logging
import uuid
from backend.core.sql_database import db
from backend.models.sql_models import ProduccionPintura
from backend.services.audit_service import AuditService
from backend.utils.formatters import preservar_o_normalizar_prefijo
from backend.utils.time_utils import get_colombia_time

logger = logging.getLogger(__name__)


class PinturaService:

    @staticmethod
    def iniciar(data):
        """Persistencia inmediata EN_PROCESO en db_pintura."""
        if not data:
            raise ValueError('No data provided')

        id_codigo = preservar_o_normalizar_prefijo(data.get('id_codigo', ''))
        if not id_codigo:
            raise ValueError('Código requerido')

        try:
            ahora = get_colombia_time()
            id_pintura = data.get('id_pintura') or f"PIN-{uuid.uuid4().hex[:8].upper()}"

            existente = db.session.query(ProduccionPintura).filter_by(id_pintura=id_pintura).first()
            if existente:
                return {'ya_registrado': True, 'id_pintura': id_pintura}

            responsable = AuditService.resolver_y_validar_propietario(None, data.get('responsable'))

            nuevo = ProduccionPintura(
                id_pintura=id_pintura,
                id_ensamble=data.get('id_ensamble'),
                id_codigo=id_codigo,
                responsable=responsable,
                insumo_pintura=data.get('insumo_pintura'),
                op_numero=data.get('op_numero', ''),
                fecha=ahora.date(),
                hora_inicio=ahora.replace(tzinfo=None),
                estado='EN_PROCESO'
            )
            db.session.add(nuevo)
            db.session.commit()

            logger.debug(f"✅ [Pintura] Inicio persistido: {id_pintura} ({responsable})")
            return {'ya_registrado': False, 'id_pintura': id_pintura}
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en PinturaService.iniciar: {e}")
            raise

    @staticmethod
    def finalizar(data):
        """
        Cierra la sesión de pintura: registra cantidad + ml de insumo utilizado
        y calcula rendimiento_ml_unidad (con guarda contra división por cero) y
        las métricas de tiempo estándar del módulo.
        """
        if not data:
            raise ValueError('No data provided')

        id_pintura = data.get('id_pintura')
        cantidad = int(data.get('cantidad', 0) or 0)
        if not id_pintura or cantidad <= 0:
            raise ValueError('id_pintura y cantidad requeridos')

        ml_insumo_utilizado = float(data.get('ml_insumo_utilizado', 0) or 0)

        try:
            ahora = get_colombia_time()

            registro = db.session.query(ProduccionPintura).filter_by(id_pintura=id_pintura).first()
            if not registro:
                raise ValueError(f"No existe sesión de pintura '{id_pintura}'")

            # Puede levantar OwnershipMismatchException — se propaga sin transformar
            responsable = AuditService.resolver_y_validar_propietario(registro, data.get('responsable'))

            registro.responsable = responsable
            registro.cantidad = cantidad
            registro.ml_insumo_utilizado = ml_insumo_utilizado
            # Guarda obligatoria: rendimiento solo es calculable si hay unidades pintadas.
            registro.rendimiento_ml_unidad = round(ml_insumo_utilizado / cantidad, 4) if cantidad > 0 else 0.0

            dt_inicio = registro.hora_inicio or ahora.replace(tzinfo=None)
            dt_fin = ahora.replace(tzinfo=None)
            h_ini = data.get('hora_inicio')
            h_fin = data.get('hora_fin')
            if h_ini and h_fin:
                try:
                    hi_h, hi_m = h_ini.split(':')
                    hf_h, hf_m = h_fin.split(':')
                    dt_inicio = ahora.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0).replace(tzinfo=None)
                    dt_fin = ahora.replace(hour=int(hf_h), minute=int(hf_m), second=0, microsecond=0).replace(tzinfo=None)
                except Exception as e_time:
                    logger.warning(f"Error calculando tiempos pintura: {e_time}")

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
            logger.info(f"✅ PINTURA FINALIZADA: {id_pintura} (rendimiento={registro.rendimiento_ml_unidad} ml/u)")
            return {
                'id_pintura': id_pintura,
                'rendimiento_ml_unidad': float(registro.rendimiento_ml_unidad or 0)
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en PinturaService.finalizar: {e}")
            raise
