"""
pulido_service.py
================
Capa de servicio exclusiva para analítica de Pulido.
Toda la lógica de negocio (volumen físico, eficiencia, deduplicación, normalización)
reside aquí. Las rutas solo invocan métodos y retornan JSON.
"""
import logging
from backend.core.sql_database import db
from backend.utils.formatters import sql_normalizar_codigo_fr
from sqlalchemy import text

logger = logging.getLogger(__name__)


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

    @staticmethod
    def _normalizar_nombre(nombre: str) -> str:
        """Normaliza a UPPER + TRIM para unificar variantes de escritura."""
        return (nombre or '').upper().strip()

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
