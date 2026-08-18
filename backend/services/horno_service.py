"""
Servicio de Ejecución de Hornos (subproceso de Ensamble).
Registro de temperatura de ingreso/salida y tiempo de curado por lote.
"""
import logging
import uuid
from backend.core.sql_database import db
from backend.models.sql_models import ProduccionHorno
from backend.services.audit_service import AuditService
from backend.utils.formatters import preservar_o_normalizar_prefijo
from backend.utils.time_utils import get_colombia_time

logger = logging.getLogger(__name__)


class HornoService:

    @staticmethod
    def iniciar(data):
        """Persistencia inmediata EN_HORNO en db_hornos (ingreso del lote)."""
        if not data:
            raise ValueError('No data provided')

        id_codigo = preservar_o_normalizar_prefijo(data.get('id_codigo', ''))
        if not id_codigo:
            raise ValueError('Código requerido')

        try:
            ahora = get_colombia_time()
            id_horno_registro = data.get('id_horno_registro') or f"HOR-{uuid.uuid4().hex[:8].upper()}"

            existente = db.session.query(ProduccionHorno).filter_by(id_horno_registro=id_horno_registro).first()
            if existente:
                return {'ya_registrado': True, 'id_horno_registro': id_horno_registro}

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

            nuevo = ProduccionHorno(
                id_horno_registro=id_horno_registro,
                id_ensamble=data.get('id_ensamble'),
                id_codigo=id_codigo,
                horno_numero=data.get('horno_numero'),
                responsable=responsable,
                cantidad=int(data.get('cantidad', 0) or 0),
                temperatura_ingreso_c=data.get('temperatura_ingreso_c'),
                op_numero=data.get('op_numero', ''),
                fecha=ahora.date(),
                hora_inicio=dt_inicio,
                estado='EN_HORNO'
            )
            db.session.add(nuevo)
            db.session.commit()

            logger.debug(f"✅ [Horno] Ingreso persistido: {id_horno_registro} ({responsable})")
            return {'ya_registrado': False, 'id_horno_registro': id_horno_registro}
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en HornoService.iniciar: {e}")
            raise

    @staticmethod
    def finalizar(data):
        """Cierra el registro de horno: hora_fin + temperatura de salida, calcula tiempo de curado."""
        if not data:
            raise ValueError('No data provided')

        id_horno_registro = data.get('id_horno_registro')
        if not id_horno_registro:
            raise ValueError('id_horno_registro requerido')

        try:
            ahora = get_colombia_time()

            registro = db.session.query(ProduccionHorno).filter_by(id_horno_registro=id_horno_registro).first()
            if not registro:
                raise ValueError(f"No existe registro de horno '{id_horno_registro}'")

            # Puede levantar OwnershipMismatchException — se propaga sin transformar
            responsable = AuditService.resolver_y_validar_propietario(registro, data.get('responsable'))

            registro.responsable = responsable
            if data.get('cantidad') is not None:
                registro.cantidad = int(data.get('cantidad', 0) or 0)
            registro.temperatura_salida_c = data.get('temperatura_salida_c', registro.temperatura_salida_c)

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
                    logger.warning(f"Error calculando hora_fin horno: {e_time}")

            duracion_s = int((dt_fin - dt_inicio).total_seconds())
            if duracion_s < 0:
                duracion_s += 86400  # Cruce de medianoche

            registro.hora_inicio = dt_inicio
            registro.hora_fin = dt_fin
            registro.duracion_segundos = duracion_s
            registro.tiempo_total_minutos = round(duracion_s / 60.0, 2)
            registro.pnc_cantidad = int(data.get('pnc_cantidad', 0) or 0)
            registro.observaciones = data.get('observaciones', registro.observaciones)
            registro.estado = 'FINALIZADO'

            db.session.commit()
            logger.info(f"✅ HORNO FINALIZADO: {id_horno_registro} ({duracion_s}s)")
            return {'id_horno_registro': id_horno_registro}
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en HornoService.finalizar: {e}")
            raise
