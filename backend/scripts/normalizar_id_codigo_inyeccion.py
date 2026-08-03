"""
Script de normalización para db_inyeccion: agrega el prefijo 'FR-' a las filas
cuyo id_codigo quedó guardado como número puro (ej. '9843') por el bug ya
corregido en InyeccionService.registrar_lote (ver backend/models/sql_models.py,
ProduccionInyeccion._sanitizar_id_codigo).

Auditoría previa confirmó que estas filas NO son duplicados de otra fila —
son reportes de producción reales y distintos (id_inyeccion, orden_produccion
y horas propios) que solo tienen el id_codigo mal formateado. Por eso este
script SOLO actualiza id_codigo in situ, nunca borra ni fusiona filas.

Códigos con otro formato (CB-, CM-, CAR-, PL-, sufijos como '9881B', etc.) se
dejan intactos: preservar_o_normalizar_prefijo() solo agrega 'FR-' cuando el
código es 100% numérico, igual que en el resto del código base.

Por defecto corre en modo DRY-RUN (solo reporta, no modifica nada).
Para aplicar los cambios: python -m backend.scripts.normalizar_id_codigo_inyeccion --apply
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app import app
from backend.core.sql_database import db
from backend.models.sql_models import ProduccionInyeccion
from backend.utils.formatters import preservar_o_normalizar_prefijo


def normalizar_prefijo_inyeccion(aplicar=False):
    with app.app_context():
        modo = "APLICANDO CAMBIOS" if aplicar else "DRY-RUN (solo reporte)"
        logger.info(f"🚀 Buscando id_codigo numéricos sin prefijo 'FR-' en db_inyeccion... [{modo}]")

        candidatos = ProduccionInyeccion.query.filter(
            ProduccionInyeccion.id_codigo.op('~')(r'^[0-9]+$')
        ).all()

        if not candidatos:
            logger.info("✅ No se encontraron filas con id_codigo numérico sin prefijo.")
            return

        logger.info(f"🔍 Encontradas {len(candidatos)} filas a normalizar.")

        for fila in candidatos:
            codigo_original = fila.id_codigo
            codigo_nuevo = preservar_o_normalizar_prefijo(codigo_original)

            logger.info(
                f"id {fila.id} | id_inyeccion={fila.id_inyeccion} | responsable={fila.responsable} | "
                f"estado={fila.estado} | id_codigo: {codigo_original!r} -> {codigo_nuevo!r}"
            )

            if aplicar:
                fila.id_codigo = codigo_nuevo

        if aplicar:
            db.session.commit()
            logger.info(f"✨ {len(candidatos)} filas normalizadas y confirmadas en la base de datos.")
        else:
            logger.info(f"Ningún cambio fue escrito (DRY-RUN). {len(candidatos)} filas se actualizarían con --apply.")


if __name__ == "__main__":
    normalizar_prefijo_inyeccion(aplicar='--apply' in sys.argv)
