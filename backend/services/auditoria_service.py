"""
auditoria_service.py — Conciliación de Órdenes de Producción de INYECCIÓN.

Cruza las OP de inyección de World Office (db_op_wo_staging, poblada por
agente_wo_comercial.py) contra lo que planta reportó en db_inyeccion, y las
enriquece con la señal EPT de World Office.

Decisiones de alcance (tomadas contra datos reales, 2026-08-21):

1. SOLO INYECCIÓN. El prefijo del número de OP separa la etapa de forma
   limpia en World Office:
       sin prefijo / 'OP-'  -> inyección  (92% y 89% se reportan en db_inyeccion)
       'EMP-' / 'ENS-'      -> ensamble   (87% y 92% se reportan en db_ensambles)
   Pulido y Ensamble quedan fuera a propósito: mezclarlos producía un único
   número inflado donde no se distinguía un hallazgo real del ruido.

2. COMPARACIÓN DE PRODUCTO POR CÓDIGO EXACTO (tolerando solo 'FR-'). NO se
   colapsan prefijos de división. Se verificó que la app reporta bien la
   cadena productiva: 'CB9829' en inyección/pulido y 'FR-9829' en ensamble,
   igual que World Office. Colapsar 'CB' contra 'FR' borraría esa distinción
   —que es real: buje crudo de máquina vs. buje ya ensamblado— y daría por
   cuadrada una OP de ensamble con un reporte de inyección.

3. SEÑAL EPT. La EPT es la entrada a inventario que genera la OP. Su cantidad
   se compara contra la de la OP: 1.411 OP tienen cantidades distintas, que es
   el descuadre de inventario que reporta planta. Se expone como dato de cada
   fila, no como lista aparte -- responde "esta OP no se reportó en la app,
   ¿pero World Office sí registró entrada?".
"""
from datetime import timedelta

from sqlalchemy import func, not_, or_

from backend.core.sql_database import db
from backend.models.sql_models import OpWoStaging, ProduccionInyeccion
from backend.utils.formatters import sql_expr_codigo_sin_prefijo_fr
from backend.utils.time_utils import get_colombia_time

# Margen de gracia: una OP de hoy todavía no tiene por qué estar reportada.
_HORAS_MARGEN_GRACIA = 24

# Prefijos de número de OP que corresponden a ensamble/empaque, no a inyección.
_PREFIJOS_NO_INYECCION = ('EMP-%', 'ENS-%', 'AJ-%')


class AuditoriaService:

    @staticmethod
    def obtener_conciliacion_ops():
        """
        Devuelve las OP de inyección de World Office que planta no reportó en
        db_inyeccion, enriquecidas con la señal EPT.

        Cada fila trae:
          - cantidad_wo   : lo que la OP mandó producir
          - cantidad_ept  : lo que World Office registró como entrada (None si no hay EPT)
          - estado_ept    : lectura ya interpretada de esas dos cantidades
        """
        faltantes = AuditoriaService._query_faltantes_inyeccion().all()
        return {
            "faltantes_inyeccion": [
                AuditoriaService._serializar(f) for f in faltantes
            ]
        }

    @staticmethod
    def _serializar(fila):
        cant_wo = float(fila.cantidad or 0)
        cant_ept = float(fila.cantidad_ept) if fila.cantidad_ept is not None else None

        if cant_ept is None:
            estado_ept = 'SIN_EPT'
        elif abs(cant_ept - cant_wo) < 0.5:
            estado_ept = 'COMPLETA'
        elif cant_ept < cant_wo:
            estado_ept = 'PARCIAL'
        else:
            estado_ept = 'EXCEDE'

        return {
            "numero_op": fila.numero_op,
            "codigo_producto": fila.codigo_producto,
            "cantidad_wo": cant_wo,
            "cantidad_ept": cant_ept,
            "diferencia_ept": (cant_ept - cant_wo) if cant_ept is not None else None,
            "estado_ept": estado_ept,
            "fecha": fila.fecha.strftime('%Y-%m-%d') if fila.fecha else None,
            "bodega": fila.bodega,
        }

    @staticmethod
    def _query_faltantes_inyeccion():
        wo = OpWoStaging
        limite_gracia = get_colombia_time() - timedelta(hours=_HORAS_MARGEN_GRACIA)

        # NOT EXISTS correlacionado, nunca JOIN: una OP trae varias referencias,
        # un JOIN plano multiplicaría filas.
        # El TRIM + recorte de '.0' cubre las filas donde orden_produccion se
        # guardó con formato de float ('303747.0'): son ~600 en planta y sin
        # esto nunca cruzan contra el '303747' de World Office.
        op_local = func.regexp_replace(func.trim(ProduccionInyeccion.orden_produccion), r'\.0+$', '')
        existe_en_inyeccion = (
            db.session.query(ProduccionInyeccion.id)
            .filter(
                op_local == wo.numero_op,
                sql_expr_codigo_sin_prefijo_fr(ProduccionInyeccion.id_codigo)
                == sql_expr_codigo_sin_prefijo_fr(wo.codigo_producto),
            )
            .exists()
        )

        es_de_ensamble = or_(*[wo.numero_op.like(p) for p in _PREFIJOS_NO_INYECCION])

        return (
            db.session.query(wo)
            .filter(
                wo.anulado.is_(False),
                wo.fecha < limite_gracia,
                not_(es_de_ensamble),
                not_(existe_en_inyeccion),
            )
            .order_by(wo.fecha.desc())
        )
