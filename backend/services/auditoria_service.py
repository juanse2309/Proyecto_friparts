"""
auditoria_service.py — Motor de conciliación de Órdenes de Producción.

Cruza las OP reales de World Office (db_op_wo_staging, poblada por
agente_wo_comercial.py) contra lo que planta reporta en Inyección, Pulido y
Ensamble, por la tupla (numero_op, codigo_producto) -- una OP es una
máquina/un día y agrupa varias referencias, nunca una sola.

Nota sobre Ensamble (2026-08-20, auditoria de datos reales): las OP con
prefijo 'ENS-'/'EMP-' en WO corresponden a Ensamble/Empaque, no a
Inyección/Pulido -- se descartó el cambio global de comparación por dígitos
(un muestreo de 50 'faltantes_en_planta' mostró que ignorar el prefijo en
Inyección/Pulido da 16% de coincidencias, pero solo 4% son reales al validar
también el producto; el resto son choques numéricos casuales entre OP
distintas -- hubiera introducido más falsos negativos de los que arregla).
En cambio, se confirmó que Ensamble.op_numero SI guarda el numero sin
prefijo (mismo patrón que Inyección/Pulido) y que el 85-94% de las OP
'ENS-'/'EMP-' faltantes tienen match ahí. Por eso la extracción de dígitos
se aplica EXCLUSIVAMENTE a este cruce de Ensamble, nunca a Inyección/Pulido.
"""
from datetime import timedelta

from sqlalchemy import func, or_, not_

from backend.core.sql_database import db
from backend.models.sql_models import OpWoStaging, ProduccionInyeccion, ProduccionPulido, Ensamble
from backend.utils.formatters import sql_expr_codigo_sin_prefijo_fr
from backend.utils.time_utils import get_colombia_time

# Regla estricta 1: valores de orden_produccion que NO son una OP real de WO
# -- 'SIN OP' es el placeholder de captura manual; 'OP-IMPREVISTA-*' lo genera
# la propia app (pedidos_service.py) cuando alistamiento no tenía OP asignada
# al momento de repartir. Ninguno de los dos debe evaluarse como anomalía:
# no son un typo de operario, son una ausencia de dato declarada por el sistema.
_ORDEN_PRODUCCION_NO_REAL = 'SIN OP'
_PREFIJO_OP_SINTETICA = 'OP-IMPREVISTA%'

# Regla estricta 2: margen de gracia antes de reportar una OP como huérfana.
_HORAS_MARGEN_GRACIA = 24


class AuditoriaService:

    @staticmethod
    def obtener_conciliacion_ops():
        """
        Devuelve un dict con dos listas:
          - faltantes_en_planta: OP activa en WO (anulado=false), con más de
            _HORAS_MARGEN_GRACIA de antigüedad, sin ningún reporte local en
            Inyección, Pulido ni Ensamble para esa (numero_op, codigo_producto).
          - anomalias: reportes locales (Inyección/Pulido) con una
            orden_produccion que no existe en db_op_wo_staging, excluyendo los
            valores de la Regla 1.

        Todas las comparaciones de código usan sql_expr_codigo_sin_prefijo_fr
        para unificar 'FR-9306'/'9306' -- mismo criterio ya usado en
        pedidos_routes.py, nunca se infiere ni se inventa prefijo.
        """
        faltantes = AuditoriaService._query_faltantes_en_planta().all()
        anomalias_inyeccion = AuditoriaService._query_anomalias(
            ProduccionInyeccion, ProduccionInyeccion.orden_produccion, ProduccionInyeccion.id_codigo, 'INYECCION'
        ).all()
        anomalias_pulido = AuditoriaService._query_anomalias(
            ProduccionPulido, ProduccionPulido.orden_produccion, ProduccionPulido.codigo, 'PULIDO'
        ).all()

        return {
            "faltantes_en_planta": [
                {
                    "numero_op": f.numero_op,
                    "codigo_producto": f.codigo_producto,
                    "cantidad_wo": float(f.cantidad or 0),
                    "fecha": f.fecha.strftime('%Y-%m-%d') if f.fecha else None,
                    "bodega": f.bodega,
                }
                for f in faltantes
            ],
            "anomalias": [
                AuditoriaService._serializar_anomalia(f, f.orden_produccion, f.id_codigo, 'INYECCION')
                for f in anomalias_inyeccion
            ] + [
                AuditoriaService._serializar_anomalia(f, f.orden_produccion, f.codigo, 'PULIDO')
                for f in anomalias_pulido
            ],
        }

    @staticmethod
    def _serializar_anomalia(fila, orden_produccion_reportada, codigo_producto, origen):
        return {
            "origen": origen,
            "orden_produccion_reportada": str(orden_produccion_reportada or '').strip(),
            "codigo_producto": str(codigo_producto or '').strip(),
            "responsable": getattr(fila, 'responsable', None),
        }

    @staticmethod
    def _query_faltantes_en_planta():
        wo = OpWoStaging
        limite_gracia = get_colombia_time() - timedelta(hours=_HORAS_MARGEN_GRACIA)

        existe_en_inyeccion = (
            db.session.query(ProduccionInyeccion.id)
            .filter(
                func.trim(ProduccionInyeccion.orden_produccion) == wo.numero_op,
                sql_expr_codigo_sin_prefijo_fr(ProduccionInyeccion.id_codigo) == sql_expr_codigo_sin_prefijo_fr(wo.codigo_producto),
            )
            .exists()
        )
        existe_en_pulido = (
            db.session.query(ProduccionPulido.id)
            .filter(
                func.trim(ProduccionPulido.orden_produccion) == wo.numero_op,
                sql_expr_codigo_sin_prefijo_fr(ProduccionPulido.codigo) == sql_expr_codigo_sin_prefijo_fr(wo.codigo_producto),
            )
            .exists()
        )

        # Ensamble: comparacion por SOLO digitos (aislada a este cruce, ver
        # nota de modulo) -- Ensamble.op_numero guarda el numero sin el
        # prefijo 'ENS-'/'EMP-' que si trae wo.numero_op para estos casos.
        op_wo_digitos = func.regexp_replace(wo.numero_op, '[^0-9]', '', 'g')
        existe_en_ensamble = (
            db.session.query(Ensamble.id)
            .filter(
                func.regexp_replace(Ensamble.op_numero, '[^0-9]', '', 'g') == op_wo_digitos,
                op_wo_digitos != '',
                sql_expr_codigo_sin_prefijo_fr(Ensamble.id_codigo) == sql_expr_codigo_sin_prefijo_fr(wo.codigo_producto),
            )
            .exists()
        )

        return (
            db.session.query(wo)
            .filter(
                wo.anulado.is_(False),
                wo.fecha < limite_gracia,
                not_(existe_en_inyeccion),
                not_(existe_en_pulido),
                not_(existe_en_ensamble),
            )
        )

    @staticmethod
    def _query_anomalias(modelo, columna_op, columna_codigo, origen):
        """
        NOT EXISTS correlacionado -- nunca JOIN directo entre la tabla local y
        db_op_wo_staging, para no multiplicar filas si una OP+producto tiene
        más de una fila en staging (una OP real trae varias referencias, así
        que un JOIN plano sí generaría un producto cartesiano aquí).
        """
        op_normalizada = func.trim(columna_op)
        es_no_real = or_(
            func.upper(op_normalizada) == _ORDEN_PRODUCCION_NO_REAL,
            func.upper(op_normalizada).like(_PREFIJO_OP_SINTETICA),
        )

        existe_en_wo = (
            db.session.query(OpWoStaging.id)
            .filter(
                OpWoStaging.numero_op == op_normalizada,
                sql_expr_codigo_sin_prefijo_fr(OpWoStaging.codigo_producto) == sql_expr_codigo_sin_prefijo_fr(columna_codigo),
            )
            .exists()
        )

        return (
            db.session.query(modelo)
            .filter(
                columna_op.isnot(None),
                op_normalizada != '',
                not_(es_no_real),
                not_(existe_en_wo),
            )
        )
