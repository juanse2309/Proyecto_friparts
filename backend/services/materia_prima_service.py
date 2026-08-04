"""
Servicio de Materia Prima (Mezcla y Molido).
Extraído de backend/app.py — dominio autocontenido, sin dependencias
cruzadas con otros servicios (cada método escribe en un único modelo).
"""
import logging
from datetime import datetime
from backend.core.sql_database import db
from backend.models.sql_models import Mezcla, Molido
from backend.utils.formatters import resolver_operario
from backend.utils.time_utils import get_colombia_time

logger = logging.getLogger(__name__)


class MateriaPrimaService:

    @staticmethod
    def registrar_mezcla(data: dict) -> dict:
        """
        Registra una mezcla de material (virgen/molido/pigmento) con lote
        interno autogenerado. Devuelve {'lote': str}.
        """
        try:
            try:
                virgen = round(float(data.get('virgen', 0) or 0), 2)
                molido = round(float(data.get('molido', 0) or 0), 2)
                pigmento = round(float(data.get('pigmento', 0) or 0), 2)

                f_str = data.get('fecha', '')
                ahora = get_colombia_time()
                fecha_dt = datetime.strptime(f_str, '%Y-%m-%d').date() if f_str else ahora.date()
                hora_str = ahora.strftime('%H:%M:%S')

                lote_interno = f"M-{fecha_dt.strftime('%Y%m%d')}-{ahora.strftime('%H%M')}"
            except Exception as e:
                raise ValueError('Formato de datos numéricos o fecha inválido') from e

            responsable = resolver_operario(data.get('responsable'))

            nueva_mezcla = Mezcla(
                fecha=fecha_dt,
                hora=hora_str,
                responsable=responsable,
                maquina=data.get('maquina', 'PROCESO GRAL'),
                virgen_kg=virgen,
                molido_kg=molido,
                pigmento_kg=pigmento,
                lote_interno=lote_interno,
                observaciones=data.get('observaciones', '')
            )
            db.session.add(nueva_mezcla)
            db.session.commit()

            logger.info(f" ✅ Mezcla Lote {lote_interno} guardada en PostgreSQL.")
            return {'lote': lote_interno}
        except Exception as e:
            db.session.rollback()
            if not isinstance(e, ValueError):
                logger.error(f" Error en MateriaPrimaService.registrar_mezcla: {str(e)}")
            raise

    @staticmethod
    def registrar_molido(data: dict) -> None:
        """Registra un pesaje de molido (Recuperado/Contaminado)."""
        try:
            peso = round(float(data.get('peso', 0) or 0), 2)
            tipo = data.get('tipo', 'Recuperado')
            responsable = resolver_operario(data.get('responsable'))
            obs = data.get('observaciones', '')

            nuevo_molido = Molido(
                fecha_registro=get_colombia_time(),
                responsable=responsable,
                peso_kg=peso,
                tipo_material=tipo,
                observaciones=obs
            )
            db.session.add(nuevo_molido)
            db.session.commit()

            logger.info(f" ✅ Molido ({tipo}) registrado: {peso}kg por {responsable}")
        except Exception as e:
            db.session.rollback()
            logger.error(f" Error en MateriaPrimaService.registrar_molido: {str(e)}")
            raise
