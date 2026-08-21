"""
auditoria_service.py — Conciliación de Órdenes de Producción de INYECCIÓN.

Cruza las OP de inyección de World Office (db_op_wo_staging, poblada por
agente_wo_comercial.py) contra lo que planta reportó en db_inyeccion, en las
DOS direcciones, y las enriquece con la señal EPT de World Office.

Decisiones de alcance (tomadas contra datos reales, 2026-08-21):

1. SOLO INYECCIÓN. El prefijo del número de OP separa la etapa de forma
   limpia en World Office:
       sin prefijo / 'OP-'  -> inyección  (92% y 89% se reportan en db_inyeccion)
       'EMP-' / 'ENS-'      -> ensamble   (87% y 92% se reportan en db_ensambles)
   Pulido y Ensamble quedan fuera a propósito: mezclarlos producía un único
   número inflado donde no se distinguía un hallazgo real del ruido.

2. PREFIJO DE DIVISIÓN -- tres niveles de tolerancia, cada uno verificado
   contra datos reales antes de aplicarlo:

   a) Exacto (tolerando solo 'FR-' via sql_expr_codigo_sin_prefijo_fr).

   b) "Pelado": el código local no lleva NINGÚN prefijo de división (ej.
      planta guardó '7002' en vez de 'MT-7002'). Se verificó que ninguna OP
      de World Office repite el mismo número con dos prefijos distintos, así
      que no hay forma de que un pelado calce con el producto equivocado.

   c) 'FR-' local contra 'MT-'/'KIT-' en World Office -- la línea de motos:
      catálogo local y World Office nombran el MISMO objeto con prefijo
      distinto (confirmado: "MT-7016 BUJE CAMPANA SUZUKI DR 650" es idéntico
      a lo que planta reporta como "FR-7016" en esa OP). Es una confusión de
      catálogo, no de etapa productiva.

   DELIBERADAMENTE NO se tolera 'FR-' local contra 'CB-'/'CM-' en World
   Office. Ahí la diferencia SÍ puede ser real: CB/CM es la pieza cruda de
   máquina, FR es la pieza ya ensamblada -- son etapas productivas distintas,
   no un simple alias de catálogo. Se encontraron 28 casos así y se dejaron
   fuera a propósito: son ambiguos (podrían ser catálogo mal puesto, o podría
   ser que ensamble genuinamente no ha corrido) y colapsarlos a ciegas
   escondería justo el tipo de hallazgo que esta vista existe para mostrar.

3. SEÑAL EPT. La EPT es la entrada a inventario que genera la OP; su
   encabezado la referencia por número en la nota. Se expone el número de
   documento EPT y la cantidad que entró, comparada contra la de la OP.

4. VISTA INVERSA (reportado en la app, no existe en World Office): mismo
   criterio de match (2a+2b+2c) pero de app hacia WO, con el mismo margen de
   gracia de 24h -- un reporte de hace minutos todavía no tuvo tiempo de que
   el agente (corre cada 30 min) traiga su OP si es que existe.
   Filtra los valores ya conocidos como "no son una OP real" ('SIN OP',
   'OP-IMPREVISTA-*', generados por la propia app cuando no hay OP asignada).
"""
from datetime import timedelta

from sqlalchemy import func, not_, or_

from backend.core.sql_database import db
from backend.models.sql_models import OpWoStaging, ProduccionInyeccion
from backend.utils.formatters import sql_expr_codigo_sin_prefijo_fr
from backend.utils.time_utils import get_colombia_time

# Margen de gracia: una OP/reporte de las últimas horas todavía no tiene por
# qué cruzar (ni la OP se ha reportado en planta, ni el agente -cada 30 min-
# ha tenido tiempo de traerla de World Office).
_HORAS_MARGEN_GRACIA = 24

# Prefijos de número de OP que corresponden a ensamble/empaque, no a inyección.
_PREFIJOS_NO_INYECCION = ('EMP-%', 'ENS-%', 'AJ-%')

# Prefijos de división conocidos -- se usan SOLO para reconocer un código
# "pelado" (que no lleva ninguno) o para extraer el prefijo real de WO,
# nunca para inventarle uno a un código que no lo trae.
_PREFIJOS_DIVISION_REGEX = r'^(FR|MT|CB|CM|KIT|CAR|INT|ENS|BF|BSLA|BLA|IM|PS|PL|AL)-?'

# Prefijos de WO que son alias de catálogo de 'FR-' (mismo objeto, distinto
# nombre comercial) -- ver punto 2c del docstring. CB/CM quedan fuera adrede.
_PREFIJOS_ALIAS_DE_FR = ('MT', 'KIT')

# Valores que la app puede guardar en orden_produccion sin que sean una OP
# real: 'SIN OP' es el placeholder de captura manual; 'OP-IMPREVISTA-*' lo
# genera pedidos_service.py cuando alistamiento no tenía OP asignada.
_ORDEN_PRODUCCION_NO_REAL = 'SIN OP'
_PREFIJO_OP_SINTETICA = 'OP-IMPREVISTA%'


class AuditoriaService:

    @staticmethod
    def obtener_conciliacion_ops():
        """
        Devuelve las dos direcciones de la conciliación de inyección:
          - faltantes_inyeccion : OP de World Office sin reporte en la app.
          - reportadas_sin_wo   : reportes de la app cuya OP no existe en WO.
        """
        faltantes = AuditoriaService._query_faltantes_inyeccion().all()
        sin_wo = AuditoriaService._query_reportadas_sin_wo().all()
        return {
            "faltantes_inyeccion": [AuditoriaService._serializar_faltante(f) for f in faltantes],
            "reportadas_sin_wo": [AuditoriaService._serializar_sin_wo(f) for f in sin_wo],
        }

    # --- Serialización ---

    @staticmethod
    def _serializar_faltante(fila):
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
            "numero_ept": fila.numero_ept,
            "diferencia_ept": (cant_ept - cant_wo) if cant_ept is not None else None,
            "estado_ept": estado_ept,
            "fecha": fila.fecha.strftime('%Y-%m-%d') if fila.fecha else None,
            "bodega": fila.bodega,
        }

    @staticmethod
    def _serializar_sin_wo(fila):
        return {
            "orden_produccion_reportada": (fila.orden_produccion or '').strip(),
            "codigo_producto": (fila.id_codigo or '').strip(),
            "cantidad_reportada": float(fila.cantidad_real or 0),
            "responsable": fila.responsable,
            "fecha": fila.fecha_inicia.strftime('%Y-%m-%d') if fila.fecha_inicia else None,
        }

    # --- Reglas de match compartidas (ver punto 2 del docstring) ---

    @staticmethod
    def _existe_exacto(op_local, codigo_local_col, wo_numero_op, wo_codigo_col):
        return (
            op_local == wo_numero_op,
            sql_expr_codigo_sin_prefijo_fr(codigo_local_col) == sql_expr_codigo_sin_prefijo_fr(wo_codigo_col),
        )

    @staticmethod
    def _existe_pelado(op_local, codigo_local_upper, wo_numero_op, wo_codigo_col):
        return (
            op_local == wo_numero_op,
            codigo_local_upper.op('~')(r'^[0-9]'),
            codigo_local_upper == func.regexp_replace(
                func.upper(func.trim(wo_codigo_col)), _PREFIJOS_DIVISION_REGEX, ''
            ),
        )

    @staticmethod
    def _existe_alias_fr(op_local, codigo_local_upper, wo_numero_op, wo_codigo_col):
        wo_codigo_upper = func.upper(func.trim(wo_codigo_col))
        wo_prefijo = func.substring(wo_codigo_upper, r'^[A-Z]+')
        wo_nucleo = func.regexp_replace(wo_codigo_upper, _PREFIJOS_DIVISION_REGEX, '')
        return (
            op_local == wo_numero_op,
            codigo_local_upper.op('~')(r'^FR-?'),
            wo_prefijo.in_(_PREFIJOS_ALIAS_DE_FR),
            func.regexp_replace(codigo_local_upper, r'^FR-?', '') == wo_nucleo,
        )

    # --- Queries ---

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
        codigo_local = func.upper(func.trim(ProduccionInyeccion.id_codigo))

        existe = or_(
            db.session.query(ProduccionInyeccion.id)
              .filter(*AuditoriaService._existe_exacto(op_local, ProduccionInyeccion.id_codigo, wo.numero_op, wo.codigo_producto))
              .exists(),
            db.session.query(ProduccionInyeccion.id)
              .filter(*AuditoriaService._existe_pelado(op_local, codigo_local, wo.numero_op, wo.codigo_producto))
              .exists(),
            db.session.query(ProduccionInyeccion.id)
              .filter(*AuditoriaService._existe_alias_fr(op_local, codigo_local, wo.numero_op, wo.codigo_producto))
              .exists(),
        )

        es_de_ensamble = or_(*[wo.numero_op.like(p) for p in _PREFIJOS_NO_INYECCION])

        return (
            db.session.query(wo)
            .filter(
                wo.anulado.is_(False),
                wo.fecha < limite_gracia,
                not_(es_de_ensamble),
                not_(existe),
            )
            .order_by(wo.fecha.desc())
        )

    @staticmethod
    def _query_reportadas_sin_wo():
        """Espejo de _query_faltantes_inyeccion: de la app hacia World Office."""
        wo = OpWoStaging
        limite_gracia = get_colombia_time() - timedelta(hours=_HORAS_MARGEN_GRACIA)
        op_local = func.regexp_replace(func.trim(ProduccionInyeccion.orden_produccion), r'\.0+$', '')
        codigo_local = func.upper(func.trim(ProduccionInyeccion.id_codigo))

        es_no_real = or_(
            func.upper(op_local) == _ORDEN_PRODUCCION_NO_REAL,
            func.upper(op_local).like(_PREFIJO_OP_SINTETICA),
        )

        # Mismas 3 reglas de _query_faltantes_inyeccion, en la direccion
        # opuesta: aqui wo.id es la columna a proyectar en el EXISTS y
        # wo.codigo_producto es, a la vez, el "codigo local" a pelar/alias
        # desde el punto de vista de World Office.
        existe = or_(
            db.session.query(wo.id)
              .filter(*AuditoriaService._existe_exacto(wo.numero_op, wo.codigo_producto, op_local, ProduccionInyeccion.id_codigo))
              .exists(),
            db.session.query(wo.id)
              .filter(wo.numero_op == op_local,
                      codigo_local.op('~')(r'^[0-9]'),
                      codigo_local == func.regexp_replace(func.upper(func.trim(wo.codigo_producto)), _PREFIJOS_DIVISION_REGEX, ''))
              .exists(),
            db.session.query(wo.id)
              .filter(*AuditoriaService._existe_alias_fr(wo.numero_op, codigo_local, op_local, wo.codigo_producto))
              .exists(),
        )

        return (
            db.session.query(ProduccionInyeccion)
            .filter(
                ProduccionInyeccion.orden_produccion.isnot(None),
                op_local != '',
                ProduccionInyeccion.fecha_inicia < limite_gracia,
                not_(es_no_real),
                not_(existe),
            )
            .order_by(ProduccionInyeccion.fecha_inicia.desc())
        )
