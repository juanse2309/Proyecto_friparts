"""
pulido_service.py
================
Capa de servicio exclusiva para analítica de Pulido.
Toda la lógica de negocio (volumen físico, eficiencia, deduplicación, normalización)
reside aquí. Las rutas solo invocan métodos y retornan JSON.
"""
import logging
from backend.core.sql_database import db
from backend.models.sql_models import ProduccionPulido
from backend.utils.formatters import sql_normalizar_codigo_fr
from backend.utils.time_utils import get_colombia_time
from backend.services.audit_service import TurnoInvalidoException
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Pulido no tiene turno nocturno: jornada única 07:00-17:00 (10h de span).
# Confirmado por el usuario el 2026-08-03 tras auditoría de horas mal digitadas.
DURACION_MAXIMA_TURNO_HORAS = 10

# TTL del Garbage Collector pasivo de sesiones zombi (ver PulidoService.limpiar_sesiones_zombis).
# Una sesión que lleva más de este tiempo en TRABAJANDO/EN_PROCESO/PAUSADO se asume abandonada
# (tablet apagada, crash de red, turno olvidado) y se autocierra para no bloquear al operario.
PULIDO_SESSION_TTL_HOURS = 14

ESTADOS_SESION_ACTIVA_GC = ['TRABAJANDO', 'EN_PROCESO', 'PAUSADO']


def _num(v, cast=float):
    """Convierte un valor numérico de forma segura."""
    try:
        return cast(v or 0)
    except (TypeError, ValueError):
        return cast(0)


class PulidoService:
    """Analítica completa del módulo de Pulido."""

    # ---------------------------------------------------------------
    # Constante interna: lista normalizada de responsables ignorados
    # ---------------------------------------------------------------
    _IGNORAR = {
        'SISTEMA', 'SIN RESPONSABLE', 'ADMIN', '',
        'NOHEMY', 'LAURA JIMENEZ', 'LAURA JIMÉNEZ',
        'EDIMAR MENDEZ', 'EDIMAR MÉNDEZ', 'EDIMAR',
        'JUAN SEBASTIAN NOVOA CEPEDA', 'JUAN SEBASTIAN NOVOA', 'JUAN SEBASTIÁN NOVOA CEPEDA',
        'JUAN SEBASTIAN', 'JUAN SEBASTIÁN', 'NOVOA'
    }

    # ---------------------------------------------------------------
    # Placeholders que NO identifican a una persona. Deliberadamente
    # separado de _IGNORAR: esa lista excluye operarias REALES de los
    # KPIs, y usarla aquí rechazaría registros legítimos suyos.
    # ---------------------------------------------------------------
    _RESPONSABLES_PLACEHOLDER = {'', 'SISTEMA', 'SIN RESPONSABLE', 'NONE', 'NULL', 'ADMIN'}

    @staticmethod
    def _normalizar_nombre(nombre: str) -> str:
        """Normaliza a UPPER + TRIM para unificar variantes de escritura."""
        return (nombre or '').upper().strip()

    @staticmethod
    def resolver_operaria_responsable(registro) -> str:
        """
        Resuelve la operaria a la que se atribuye una merma de db_pnc_pulido.

        Única fuente válida: `db_pulido.responsable` del turno que produjo la
        merma — la operaria que físicamente procesó las piezas. No se acepta
        NULL ni un placeholder genérico: una merma sin dueño es justamente el
        vacío de trazabilidad que la columna `responsable` vino a cerrar, y
        rellenarla con 'SISTEMA' o el nombre del área lo reintroduce disfrazado.

        :param registro: instancia de ProduccionPulido (o None).
        :raises ValueError: si no hay una persona real que atribuir.
        """
        nombre = str(getattr(registro, 'responsable', '') or '').strip()
        if not nombre or PulidoService._normalizar_nombre(nombre) in PulidoService._RESPONSABLES_PLACEHOLDER:
            raise ValueError(
                "No se puede registrar PNC de pulido sin una operaria responsable "
                "identificada en el turno (db_pulido.responsable)"
            )
        return nombre

    @staticmethod
    def resolver_operario_inyeccion_origen(registro):
        """
        Rastrea el operario de INYECCIÓN que fabricó las piezas que este turno de
        pulido está procesando, para atribuirle la merma de inyección detectada
        durante el pulido (db_pnc_inyeccion.responsable).

        NO se usa `db_trazabilidad_lotes.responsable`: esa columna guarda al
        programador de planta (`ProgramacionInyeccion.responsable_planta`), no a
        quien operó la máquina. Verificado contra datos reales — para el mismo
        lote, trazabilidad dice 'Juan Sebastian Novoa Cepeda' (supervisor) e
        inyección dice 'Oscar Prieto' (operario). La trazabilidad sirve solo como
        puente hacia `id_inyeccion`; el operario real vive en db_inyeccion.

        Estrategias, en orden:
          1. db_pulido.lote -> db_trazabilidad_lotes.id_lote -> id_inyeccion
             -> db_inyeccion.responsable   (flujo MES con lote en vivo)
          2. orden_produccion + código normalizado -> db_inyeccion.responsable,
             tomando el lote más reciente  (flujo directo, sin lote MES)

        La estrategia 2 no es un adorno: hoy `db_pulido.lote` guarda una FECHA
        ('9/4/2026'), no un id_lote, así que la vía 1 no resuelve ninguno de los
        registros históricos y sin el fallback la columna seguiría en NULL.

        :return: nombre del operario de inyección, o None si no es rastreable.
                 Deliberadamente NO inventa un valor: atribuir la merma a la
                 pulidora o a un genérico es peor que dejar el campo vacío.
        """
        from backend.models.sql_models import TrazabilidadLote, ProduccionInyeccion

        codigo = str(getattr(registro, 'codigo', '') or '').strip()
        if not codigo:
            return None

        def _responsable_valido(nombre):
            nombre = str(nombre or '').strip()
            if not nombre or PulidoService._normalizar_nombre(nombre) in PulidoService._RESPONSABLES_PLACEHOLDER:
                return None
            return nombre

        # ── Estrategia 1: puente por lote de trazabilidad ──────────────
        lote = str(getattr(registro, 'lote', '') or '').strip()
        if lote and lote != 'SIN LOTE':
            fila = db.session.execute(
                text(f"""
                    SELECT i.responsable
                    FROM db_trazabilidad_lotes t
                    JOIN db_inyeccion i
                      ON i.id_inyeccion = t.id_inyeccion
                     AND {sql_normalizar_codigo_fr('i.id_codigo')} = {sql_normalizar_codigo_fr('t.id_codigo')}
                    WHERE t.id_lote = :lote
                      AND {sql_normalizar_codigo_fr('t.id_codigo')} = UPPER(TRIM(:codigo))
                      AND i.responsable IS NOT NULL
                    ORDER BY i.fecha_inicia DESC NULLS LAST
                    LIMIT 1
                """),
                {'lote': lote, 'codigo': codigo}
            ).fetchone()
            if fila and _responsable_valido(fila[0]):
                return _responsable_valido(fila[0])

        # ── Estrategia 2: cruce por OP + referencia ────────────────────
        op = str(getattr(registro, 'orden_produccion', '') or '').strip()
        if op and op != 'SIN OP':
            fila = db.session.execute(
                text(f"""
                    SELECT i.responsable
                    FROM db_inyeccion i
                    WHERE i.orden_produccion = :op
                      AND {sql_normalizar_codigo_fr('i.id_codigo')} = UPPER(TRIM(:codigo))
                      AND i.responsable IS NOT NULL
                    ORDER BY i.fecha_inicia DESC NULLS LAST
                    LIMIT 1
                """),
                {'op': op, 'codigo': codigo}
            ).fetchone()
            if fila and _responsable_valido(fila[0]):
                return _responsable_valido(fila[0])

        logger.warning(
            f"⚠️ [PNC-Inyeccion] No se pudo rastrear el operario de inyección del turno "
            f"{getattr(registro, 'id_pulido', '?')} (lote={lote!r}, OP={op!r}, cod={codigo!r}). "
            f"La merma queda sin atribuir en vez de asignarse a un dueño incorrecto."
        )
        return None

    @staticmethod
    def validar_duracion_turno(segundos_segmento: int) -> None:
        """
        Rechaza duraciones de turno imposibles para Pulido (jornada única 07:00-17:00,
        sin turno nocturno). Debe llamarse con el delta CRUDO hora_fin-hora_inicio
        (ya con el wraparound de medianoche aplicado si corresponde), antes de sumar
        tiempo_acumulado_ms o descontar pausas.
        """
        limite_seg = DURACION_MAXIMA_TURNO_HORAS * 3600
        if segundos_segmento > limite_seg:
            raise TurnoInvalidoException(
                horas_calculadas=segundos_segmento / 3600.0,
                horas_maximas=DURACION_MAXIMA_TURNO_HORAS,
            )

    # ---------------------------------------------------------------
    # GARBAGE COLLECTOR DE SESIONES (TTL)
    # ---------------------------------------------------------------
    @staticmethod
    def limpiar_sesiones_zombis(responsable=None):
        """
        Garbage Collector pasivo (TTL): autocierra sesiones de Pulido en
        TRABAJANDO/EN_PROCESO/PAUSADO que superan PULIDO_SESSION_TTL_HOURS de
        antigüedad. Se invoca antes de cualquier evaluación de "sesión activa"
        (iniciar turno, consultar estado, session_active) para que un turno
        abandonado no bloquee indefinidamente al operario en un lote nuevo.

        Antigüedad = ahora - (fecha_registro o hora_inicio como fallback).
        Retorna la cantidad de sesiones autocerradas.
        """
        try:
            ahora = get_colombia_time()
            query = db.session.query(ProduccionPulido).filter(
                ProduccionPulido.estado.in_(ESTADOS_SESION_ACTIVA_GC)
            )
            if responsable:
                query = query.filter(ProduccionPulido.responsable == responsable)

            cerradas = 0
            for sesion in query.all():
                referencia = sesion.fecha_registro or sesion.hora_inicio
                if not referencia:
                    continue
                horas_abierta = (ahora - referencia).total_seconds() / 3600.0
                if horas_abierta > PULIDO_SESSION_TTL_HOURS:
                    sesion.estado = 'DESCARTADO_AUTO'
                    logger.info(
                        f"🛡️ [TTL Garbage Collector] Sesión ID {sesion.id_pulido} de {sesion.responsable} "
                        f"autocerrada por superar {PULIDO_SESSION_TTL_HOURS}h"
                    )
                    cerradas += 1

            if cerradas:
                db.session.commit()
            return cerradas
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en PulidoService.limpiar_sesiones_zombis: {e}")
            return 0

    @staticmethod
    def _es_responsable_ignorado(nombre: str) -> bool:
        """
        Determina si un responsable debe ser purgado de los KPIs y Rankings de Pulido.

        Solo coincidencia EXACTA contra _IGNORAR (ya cubre todas las variantes de
        tildes necesarias). Antes existía un fallback por substring que buscaba
        fragmentos genéricos ('EDIMAR', 'JUAN SEBASTIAN', 'NOVOA') dentro del nombre
        normalizado — ese mecanismo fue el que invisibilizó a la operaria activa
        'LAURA LIZETH VARGAS R.' en cuanto el patrón coincidía con un substring de su
        nombre. Se elimina por completo: cualquier variante real que deba ignorarse
        debe agregarse explícitamente a _IGNORAR, nunca por coincidencia parcial.
        """
        if not nombre:
            return True
        norm = PulidoService._normalizar_nombre(nombre)
        return norm in PulidoService._IGNORAR

    # ---------------------------------------------------------------
    # RANKING: Leaderboard por Volumen (Piezas) y Eficiencia
    # ---------------------------------------------------------------
    @staticmethod
    def get_ranking_leaderboard(desde=None, hasta=None, limit: int = 20) -> dict:
        """
        Retorna el diccionario 'pulido_profundo' listo para el frontend.

        Estructura de cada entrada:
        {
            "NOMBRE OPERARIA": {
                "buenas": int,
                "pnc": int,
                "eficiencia": float,          # % (Tiempo Std / Tiempo Real * 100)
                "yield_calidad": float,        # % (buenas / (buenas+pnc) * 100)
                "minutos": int,
                "insight": str
            }
        }

        Fuente de datos:
        - db_pulido: registros FINALIZADOS (estado IN ('FINALIZADO','APROBADO'))
        - db_costos: tiempo_estandar por referencia
        - Deduplicación: UPPER(TRIM(responsable)) evita duplicados por case.
        - El JOIN con db_costos usa UPPER(TRIM) en ambos lados para evitar misses.
        """
        try:
            params = {'lim': limit}
            filt = " AND p.estado IN ('FINALIZADO', 'APROBADO')"
            if desde and hasta:
                filt += " AND p.fecha BETWEEN :desde AND :hasta"
                params['desde'] = desde
                params['hasta'] = hasta

            sql = f"""
                SELECT
                    UPPER(TRIM(p.responsable))                                        AS responsable,
                    SUM(COALESCE(p.cantidad_real, 0))                                 AS buenas,
                    SUM(COALESCE(p.pnc_pulido, 0) + COALESCE(p.pnc_inyeccion, 0))    AS pnc,
                    SUM(COALESCE(p.tiempo_total_minutos, 0))                          AS t_real,
                    -- t_std solo suma cantidad_real de lotes CON tiempo_total_minutos capturado:
                    -- t_real tampoco incluye los lotes sin tiempo, así que ambos lados de la
                    -- razón de eficiencia deben compartir la misma población o el ratio se dispara.
                    SUM(
                        CASE WHEN COALESCE(p.tiempo_total_minutos, 0) > 0 THEN COALESCE(p.cantidad_real, 0) ELSE 0 END
                        * COALESCE(
                            NULLIF(
                                regexp_replace(
                                    REPLACE(COALESCE(c.tiempo_estandar::TEXT,'0'), ',', '.'),
                                    '[^0-9.]', '', 'g'
                                ), ''
                            )::NUMERIC, 0
                        )
                    )                                                                  AS t_std
                FROM db_pulido p
                LEFT JOIN db_costos c
                       ON {sql_normalizar_codigo_fr('p.codigo')} = {sql_normalizar_codigo_fr('c.referencia')}
                WHERE 1=1 {filt}
                GROUP BY UPPER(TRIM(p.responsable))
                ORDER BY buenas DESC
                LIMIT :lim
            """
            rows = db.session.execute(text(sql), params).fetchall()

            resultado = {}
            for r in rows:
                nombre = PulidoService._normalizar_nombre(str(r[0] or 'Desconocido'))
                if PulidoService._es_responsable_ignorado(nombre):
                    continue
                buenas  = _num(r[1], int)
                pnc     = _num(r[2], int)
                t_real  = _num(r[3], float)
                t_std   = _num(r[4], float)

                # None (no 0) cuando no hay ningun lote con tiempo_total_minutos capturado:
                # "sin dato" no es lo mismo que "0% de rendimiento".
                eficiencia   = round((t_std / t_real * 100), 1) if t_real > 0 else None
                total        = buenas + pnc
                yield_cal    = round((buenas / total * 100), 1) if total > 0 else 100

                resultado[nombre] = {
                    # ── Métrica VOLUMÉTRICA (física) ────────────────────
                    "buenas":            buenas,        # alias canónico para el leaderboard
                    "piezas_producidas": buenas,        # alias explícito — SOLO unidades OK
                    "pnc":               pnc,
                    # ── Eficiencia y calidad ─────────────────────────────
                    "eficiencia":        eficiencia,
                    "yield_calidad":     yield_cal,
                    "minutos":           int(t_real),
                    "insight":           PulidoService._generar_insight(nombre, buenas, pnc, eficiencia, yield_cal)
                }
            return resultado

        except Exception as e:
            db.session.rollback()
            logger.error(f"[PulidoService.get_ranking_leaderboard] {e}")
            return {}

    # ---------------------------------------------------------------
    # DETALLE POR REFERENCIA (modal de operaria)
    # ---------------------------------------------------------------
    @staticmethod
    def get_detalle_por_referencia(desde=None, hasta=None) -> dict:
        """
        Retorna: { "NOMBRE": { "REF": { cantidad_total, costo_unidad } } }
        """
        try:
            params = {}
            filt = " AND p.estado IN ('FINALIZADO', 'APROBADO')"
            if desde and hasta:
                filt += " AND p.fecha BETWEEN :desde AND :hasta"
                params['desde'] = desde
                params['hasta'] = hasta

            ref_norm = sql_normalizar_codigo_fr('p.codigo')
            sql = f"""
                SELECT
                    UPPER(TRIM(p.responsable))                                         AS responsable,
                    {ref_norm}                                                          AS referencia,
                    SUM(COALESCE(p.cantidad_real, 0))                                  AS qty,
                    MAX(COALESCE(
                        NULLIF(
                            regexp_replace(
                                REPLACE(COALESCE(c.costo_total::TEXT,'0'), ',', '.'),
                                '[^0-9.]', '', 'g'
                            ), ''
                        )::NUMERIC, 0
                    ))                                                                  AS costo_u
                FROM db_pulido p
                LEFT JOIN db_costos c
                       ON {ref_norm} = {sql_normalizar_codigo_fr('c.referencia')}
                WHERE 1=1 {filt}
                GROUP BY 1, 2
                ORDER BY 1, qty DESC
            """
            rows = db.session.execute(text(sql), params).fetchall()

            refs_map: dict = {}
            for r in rows:
                resp  = PulidoService._normalizar_nombre(str(r[0] or 'Desconocido'))
                ref   = str(r[1] or 'Sin Referencia').strip()
                qty   = _num(r[2], int)
                costo = _num(r[3], float)
                if PulidoService._es_responsable_ignorado(resp):
                    continue
                if resp not in refs_map:
                    refs_map[resp] = {}
                refs_map[resp][ref] = {
                    "cantidad_total": qty,
                    "costo_unidad":   costo
                }
            return refs_map

        except Exception as e:
            db.session.rollback()
            logger.error(f"[PulidoService.get_detalle_por_referencia] {e}")
            return {}

    # ---------------------------------------------------------------
    # MÉTODO COMPUESTO: DTO completo para el dashboard
    # ---------------------------------------------------------------
    @staticmethod
    def get_analytics_completo(desde=None, hasta=None) -> dict:
        """
        DTO único que el endpoint /api/dashboard/stats consume.
        Retorna:
        {
            "operario_referencia": { "NOMBRE": { "REF": {...} } }
        }
        """
        return {
            "operario_referencia": PulidoService.get_detalle_por_referencia(desde, hasta)
        }

    # ---------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------
    @staticmethod
    def _generar_insight(nombre: str, buenas: int, pnc: int, eficiencia: float, yield_cal: float) -> str:
        total = buenas + pnc
        if total == 0:
            return f"{nombre} no tiene registros en el período."
        partes = []
        if yield_cal >= 98:
            partes.append(f"Excelente calidad ({yield_cal}% yield).")
        elif yield_cal < 90:
            partes.append(f"⚠️ Yield bajo ({yield_cal}%). Revisar causas de PNC.")
        if eficiencia is None:
            partes.append("Sin lotes con tiempo capturado para calcular eficiencia.")
        elif eficiencia >= 100:
            partes.append(f"Eficiencia sobre estándar ({eficiencia}%).")
        elif eficiencia > 0 and eficiencia < 70:
            partes.append(f"Eficiencia por debajo del 70% ({eficiencia}%).")
        partes.append(f"{buenas:,} piezas OK en el período.")
        return " ".join(partes) if partes else f"{nombre}: {buenas:,} piezas OK."
