"""
⛔ SCRIPT RETIRADO — no debe ejecutarse.

Agregaba el prefijo 'FR-' a las filas de db_inyeccion cuyo id_codigo era un
número puro (ej. '9843'). Esa premisa quedó invalidada: un código numérico NO
implica división FriParts, y reetiquetarlo pisa referencias de motos y otras
divisiones que solo se distinguen por el contexto de la orden de producción.

preservar_o_normalizar_prefijo() ya no antepone 'FR-' salvo opt-in explícito
del llamador, así que este script hoy sería un no-op silencioso. Se conserva el
archivo como lápida para que nadie lo "arregle" reintroduciendo la inyección
automática de prefijos.

El cruce histórico entre '9843' y 'FR-9843' se resuelve en las CONSULTAS
(sql_normalizar_codigo_fr / sql_expr_codigo_sin_prefijo_fr en
backend/utils/formatters.py), no mutando el dato persistido.

Si alguna vez hace falta re-etiquetar referencias por división, debe hacerse
contra la lista maestra de SKUs —nunca con una heurística sobre el formato del
código.
"""
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_MOTIVO = (
    "Script retirado: anteponer 'FR-' a un id_codigo numérico reetiqueta "
    "referencias de otras divisiones (MT-, CAR-...). Ver el docstring del módulo."
)


def normalizar_prefijo_inyeccion(aplicar=False):
    raise RuntimeError(_MOTIVO)


if __name__ == "__main__":
    logger.error(f"⛔ {_MOTIVO}")
    sys.exit(1)
