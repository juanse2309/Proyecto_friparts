"""
pulido_service.py
================
Capa de servicio exclusiva para analítica de Pulido.
Toda la lógica de negocio (volumen físico, eficiencia, deduplicación, normalización)
reside aquí. Las rutas solo invocan métodos y retornan JSON.
"""
import logging
import uuid
from datetime import datetime, date, time
from backend.core.sql_database import db
from backend.models.sql_models import ProduccionPulido, PausasPulido, Producto
from backend.utils.formatters import sql_normalizar_codigo_fr, normalizar_codigo
from backend.utils.time_utils import get_colombia_time
from backend.services.audit_service import TurnoInvalidoException
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Pulido no tiene turno nocturno: jornada única 07:00-17:00 (10h de span).
# Confirmado por el usuario el 2026-08-03 tras auditoría de horas mal digitadas.
DURACION_MAXIMA_TURNO_HORAS = 10

# Pausas fijas de Friparts (descontadas automáticamente del tiempo efectivo
# del flujo MES). Movido desde app.py junto con el resto del dominio.
_PAUSAS_FIJAS_FRIPARTS = [
    {"nombre": "Pausa Activa 1", "inicio": "07:00", "fin": "07:05", "minutos": 5},
    {"nombre": "Desayuno",        "inicio": "09:00", "fin": "09:15", "minutos": 15},
    {"nombre": "Pausa Activa 2", "inicio": "11:00", "fin": "11:05", "minutos": 5},
    {"nombre": "Almuerzo",        "inicio": "12:30", "fin": "13:15", "minutos": 45},
    {"nombre": "Pausa Activa 3", "inicio": "15:00", "fin": "15:05", "minutos": 5},
]


class TrabajoPulidoNoEncontradoException(Exception):
    """Se lanza cuando no existe el registro de ProduccionPulido esperado por el flujo MES."""
    def __init__(self, message="No se encontró el trabajo de pulido"):
        self.message = message
        super().__init__(self.message)


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
    # FLUJO MES (estado/iniciar/finalizar/pausar/reanudar) — movido desde app.py
    # ---------------------------------------------------------------
    @staticmethod
    def _calcular_minutos_pausas_fijas(inicio_trabajo, fin_trabajo):
        """Calcula cuántos minutos de pausas fijas de Friparts se cruzaron con el horario de trabajo."""
        try:
            if not inicio_trabajo or not fin_trabajo:
                return 0, []

            if isinstance(inicio_trabajo, str):
                try:
                    if 'T' in inicio_trabajo:
                        inicio_trabajo = datetime.fromisoformat(inicio_trabajo)
                    else:
                        inicio_trabajo = datetime.strptime(inicio_trabajo[:19], '%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.error(f"Error parseando inicio_trabajo '{inicio_trabajo}': {e}")
                    return 0, []

            if isinstance(fin_trabajo, str):
                try:
                    if 'T' in fin_trabajo:
                        fin_trabajo = datetime.fromisoformat(fin_trabajo)
                    else:
                        fin_trabajo = datetime.strptime(fin_trabajo[:19], '%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.error(f"Error parseando fin_trabajo '{fin_trabajo}': {e}")
                    fin_trabajo = get_colombia_time()

            if hasattr(inicio_trabajo, 'date'):
                fecha_ref = inicio_trabajo.date()
            elif isinstance(inicio_trabajo, date):
                fecha_ref = inicio_trabajo
            else:
                fecha_ref = date.today()

            total_minutos_pausa = 0
            detalles = []

            for pausa in _PAUSAS_FIJAS_FRIPARTS:
                try:
                    h_ini, m_ini = map(int, pausa["inicio"].split(':'))
                    h_fin, m_fin = map(int, pausa["fin"].split(':'))

                    pausa_inicio = datetime.combine(fecha_ref, time(h_ini, m_ini))
                    pausa_fin = datetime.combine(fecha_ref, time(h_fin, m_fin))

                    if not isinstance(inicio_trabajo, datetime):
                        inicio_dt = datetime.combine(inicio_trabajo, time(0, 0))
                    else:
                        inicio_dt = inicio_trabajo

                    if not isinstance(fin_trabajo, datetime):
                        fin_dt = datetime.combine(fin_trabajo, time(23, 59, 59))
                    else:
                        fin_dt = fin_trabajo

                    start_inter = max(inicio_dt, pausa_inicio)
                    end_inter = min(fin_dt, pausa_fin)

                    if start_inter < end_inter:
                        m = int((end_inter - start_inter).total_seconds() / 60)
                        if m > 0:
                            total_minutos_pausa += m
                            detalles.append({"nombre": pausa["nombre"], "minutos": m})
                except Exception as e_p:
                    logger.error(f"Error procesando pausa {pausa.get('nombre')}: {e_p}")

            return total_minutos_pausa, detalles
        except Exception as e_global:
            logger.error(f"Error global en _calcular_minutos_pausas_fijas: {e_global}")
            return 0, []

    @staticmethod
    def obtener_estado_multitarea(responsable):
        """Todos los trabajos EN_PROCESO/PAUSADO de un operario (multitasking)."""
        if not responsable:
            return {'en_curso': False, 'lista': []}
        try:
            trabajos = db.session.query(ProduccionPulido).filter(
                ProduccionPulido.responsable == responsable,
                ProduccionPulido.estado.in_(['EN_PROCESO', 'PAUSADO'])
            ).order_by(ProduccionPulido.id.desc()).all()

            if not trabajos:
                return {'en_curso': False, 'lista': []}

            lista_final = []
            for t in trabajos:
                hora_str = "--:--"
                if t.hora_inicio:
                    try:
                        hora_str = t.hora_inicio.strftime('%H:%M') if hasattr(t.hora_inicio, 'strftime') else str(t.hora_inicio)[11:16]
                    except Exception:
                        pass
                lista_final.append({
                    'id': t.id,
                    'producto': t.codigo,
                    'hora_inicio': hora_str,
                    'estado': t.estado
                })

            return {
                'en_curso': any(t.estado == 'EN_PROCESO' for t in trabajos),
                'lista': lista_final,
                'datos': lista_final[0]  # Retrocompatibilidad UI actual
            }
        except Exception as e:
            logger.error(f"Error en PulidoService.obtener_estado_multitarea: {e}")
            raise

    @staticmethod
    def iniciar_trabajo(responsable, producto_raw):
        """Inicia un nuevo trabajo de pulido; auto-pausa cualquier trabajo EN_PROCESO existente (multitasking)."""
        if not responsable or not producto_raw:
            raise ValueError('Falta responsable o producto')
        try:
            codigo_sistema = normalizar_codigo(producto_raw)
            ahora = get_colombia_time()
            fecha_actual = ahora.date()

            trabajo_activo = db.session.query(ProduccionPulido).filter_by(
                responsable=responsable, estado='EN_PROCESO'
            ).first()

            if trabajo_activo:
                trabajo_activo.estado = 'PAUSADO'
                db.session.add(PausasPulido(
                    id_pulido=trabajo_activo.id,
                    motivo='Multitarea (NUEVO TRABAJO)',
                    hora_inicio=ahora
                ))
                logger.info(f"⏸️ AUTO-PAUSA por multitasking: {trabajo_activo.codigo}")

            hora_inicio_str = ahora.strftime('%H:%M')
            nuevo_trabajo = ProduccionPulido(
                id_pulido=f"PUL-{uuid.uuid4().hex[:8].upper()}",
                fecha=fecha_actual,
                fecha_registro=ahora,
                codigo=codigo_sistema,
                responsable=responsable,
                hora_inicio=ahora,
                estado='EN_PROCESO'
            )
            db.session.add(nuevo_trabajo)
            db.session.commit()

            logger.info(f"✅ Trabajo de pulido iniciado: {codigo_sistema} por {responsable}")
            return {'id': nuevo_trabajo.id, 'hora_inicio': hora_inicio_str}
        except Exception as e:
            db.session.rollback()
            if not isinstance(e, ValueError):
                logger.error(f"❌ Error en PulidoService.iniciar_trabajo: {e}")
            raise

    @staticmethod
    def finalizar_trabajo(data):
        """Cierra el registro de pulido, calcula tiempos/mermas y actualiza inventario."""
        responsable = data.get('responsable')
        producto_raw = data.get('producto')
        if not responsable or not producto_raw:
            raise ValueError('Falta responsable o producto')

        try:
            total_canastilla = float(data.get('total_canastilla', 0))
            orden_produccion = data.get('orden_produccion', '')
            observaciones = data.get('observaciones', '')
            codigo_sistema = normalizar_codigo(producto_raw)

            trabajo = db.session.query(ProduccionPulido).filter(
                ProduccionPulido.responsable == responsable,
                ProduccionPulido.codigo == codigo_sistema,
                ProduccionPulido.estado == 'EN_PROCESO'
            ).order_by(ProduccionPulido.id.desc()).first()

            if not trabajo:
                raise TrabajoPulidoNoEncontradoException("No se encontró un trabajo activo para este producto")

            ahora = get_colombia_time()
            trabajo.hora_fin = ahora
            trabajo.estado = 'FINALIZADO'
            trabajo.cantidad_real = total_canastilla

            def_iny = data.get('defectos_inyeccion', [])
            pnc_i = sum(float(d.get('cantidad', 0)) for d in def_iny)
            trabajo.pnc_inyeccion = int(pnc_i)

            def_pul = data.get('defectos_pulido', [])
            pnc_p = sum(float(d.get('cantidad', 0)) for d in def_pul)
            trabajo.pnc_pulido = int(pnc_p)

            trabajo.orden_produccion = orden_produccion
            trabajo.observaciones = observaciones

            # --- Cálculo de Tiempos Avanzado ---
            try:
                inicio_t = trabajo.hora_inicio
                if isinstance(inicio_t, str):
                    try:
                        if 'T' in inicio_t:
                            inicio_t = datetime.fromisoformat(inicio_t)
                        else:
                            inicio_t = datetime.strptime(inicio_t[:19], '%Y-%m-%d %H:%M:%S')
                    except Exception as ex:
                        logger.error(f"Error parseando hora_inicio en finalizar: {ex}")
                        inicio_t = ahora

                diff_bruta = ahora - inicio_t
                minutos_brutos = int(diff_bruta.total_seconds() / 60)

                pausas_manuales = db.session.query(PausasPulido).filter_by(id_pulido=trabajo.id).all()
                total_manuales_min = 0
                for p in pausas_manuales:
                    if p.hora_inicio and p.hora_fin:
                        diff_p = p.hora_fin - p.hora_inicio
                        total_manuales_min += int(diff_p.total_seconds() / 60)

                total_fijas_min, _ = PulidoService._calcular_minutos_pausas_fijas(trabajo.hora_inicio, ahora)

                trabajo.tiempo_total_minutos = max(0, minutos_brutos - total_manuales_min - total_fijas_min)

                logger.info(f"⏱️ TIEMPOS: Bruto={minutos_brutos}m, Manuales={total_manuales_min}m, Fijas={total_fijas_min}m. Efectivo={trabajo.tiempo_total_minutos}m")
            except Exception as e_time:
                logger.error(f"Error calculando tiempos de pulido: {e_time}")
                trabajo.tiempo_total_minutos = 0

            # --- Actualización de inventario (SQL-Native) ---
            producto_inv = db.session.query(Producto).filter_by(codigo_sistema=codigo_sistema).first()
            if producto_inv:
                original_por_pulir = float(producto_inv.por_pulir or 0)
                producto_inv.por_pulir = max(0, original_por_pulir - total_canastilla)
                buenas = total_canastilla - pnc_i - pnc_p
                original_terminado = float(producto_inv.p_terminado or 0)
                producto_inv.p_terminado = original_terminado + buenas
                logger.info(f"📦 [INVENTARIO UPD] {codigo_sistema}: Pulido -> Terminado (+{buenas})")

            # --- Registrar Detalles de PNC Dual ---
            from backend.services.pnc_service import PncService
            if def_iny:
                for d in def_iny:
                    PncService.registrar_pnc_detalle(
                        tipo_proceso="inyeccion",  # Se marca como inyección aunque se detectó en pulido
                        id_operacion=trabajo.id,
                        codigo_producto=codigo_sistema,
                        cantidad_pnc=float(d.get('cantidad', 0)),
                        criterio_pnc=d.get('motivo', 'Falta Material'),
                        observaciones=f"Auditado en Pulido - {observaciones}"
                    )
            if def_pul:
                for d in def_pul:
                    PncService.registrar_pnc_detalle(
                        tipo_proceso="pulido",
                        id_operacion=trabajo.id,
                        codigo_producto=codigo_sistema,
                        cantidad_pnc=float(d.get('cantidad', 0)),
                        criterio_pnc=d.get('motivo', 'Mal Pulido'),
                        observaciones=f"Reporte Pulido - {observaciones}"
                    )

            db.session.commit()
            return {'buenas': trabajo.cantidad_real, 'tiempo_efectivo': trabajo.tiempo_total_minutos}
        except Exception as e:
            db.session.rollback()
            if not isinstance(e, (ValueError, TrabajoPulidoNoEncontradoException)):
                logger.error(f"❌ Error en PulidoService.finalizar_trabajo: {e}")
            raise

    @staticmethod
    def pausar_trabajo(responsable, motivo='Otras'):
        """Registra una pausa manual en el flujo MES de pulido."""
        if not responsable:
            raise ValueError('Falta responsable')
        try:
            trabajo = db.session.query(ProduccionPulido).filter(
                ProduccionPulido.responsable == responsable,
                ProduccionPulido.estado == 'EN_PROCESO'
            ).order_by(ProduccionPulido.id.desc()).first()

            if not trabajo:
                raise TrabajoPulidoNoEncontradoException("No hay un trabajo activo para pausar")

            trabajo.estado = 'PAUSADO'

            ahora = get_colombia_time()
            db.session.add(PausasPulido(
                id_pulido=trabajo.id,
                motivo=motivo,
                hora_inicio=ahora
            ))
            db.session.commit()

            logger.info(f"⏸️ TRABAJO PAUSADO: {trabajo.codigo} por {responsable} (Motivo: {motivo})")
        except Exception as e:
            db.session.rollback()
            if not isinstance(e, (ValueError, TrabajoPulidoNoEncontradoException)):
                logger.error(f"❌ Error en PulidoService.pausar_trabajo: {e}")
            raise

    @staticmethod
    def reanudar_trabajo(responsable, id_fuerte=None):
        """Finaliza una pausa y vuelve a poner el trabajo en proceso (soporta multitarea)."""
        if not responsable:
            raise ValueError('Falta responsable')
        try:
            ahora = get_colombia_time()

            trabajos_activos = db.session.query(ProduccionPulido).filter(
                ProduccionPulido.responsable == responsable,
                ProduccionPulido.estado == 'EN_PROCESO',
                ProduccionPulido.id != id_fuerte
            ).all()

            for t_activo in trabajos_activos:
                t_activo.estado = 'PAUSADO'
                db.session.add(PausasPulido(
                    id_pulido=t_activo.id,
                    motivo='Reemplazo de Tarea (Auto)',
                    hora_inicio=ahora
                ))
                logger.info(f"⏸️ Auto-Pausa: {t_activo.codigo} (Operario: {responsable})")

            if id_fuerte:
                trabajo = db.session.query(ProduccionPulido).filter_by(id=id_fuerte, responsable=responsable).first()
            else:
                trabajo = db.session.query(ProduccionPulido).filter_by(responsable=responsable, estado='PAUSADO').order_by(ProduccionPulido.id.desc()).first()

            if not trabajo:
                raise TrabajoPulidoNoEncontradoException("No se encontró el trabajo para reanudar")

            trabajo.estado = 'EN_PROCESO'

            pausa_activa = db.session.query(PausasPulido).filter(
                PausasPulido.id_pulido == trabajo.id,
                PausasPulido.hora_fin == None
            ).order_by(PausasPulido.id.desc()).first()

            if pausa_activa:
                pausa_activa.hora_fin = ahora
                logger.info(f"▶️ TRABAJO REANUDADO: {trabajo.codigo} (ID: {trabajo.id})")

            db.session.commit()

            hora_str = trabajo.hora_inicio.strftime('%H:%M') if hasattr(trabajo.hora_inicio, 'strftime') else str(trabajo.hora_inicio)[:16]
            return {'hora_inicio': hora_str, 'id': trabajo.id}
        except Exception as e:
            db.session.rollback()
            if not isinstance(e, (ValueError, TrabajoPulidoNoEncontradoException)):
                logger.error(f"❌ Error en PulidoService.reanudar_trabajo: {e}")
            raise

    @staticmethod
    def obtener_resumen_pausas(responsable, id_trabajo=None):
        """Detalle de pausas (manuales + fijas programadas) de un trabajo específico."""
        try:
            if id_trabajo:
                trabajo = db.session.query(ProduccionPulido).filter_by(id=id_trabajo).first()
            else:
                trabajo = db.session.query(ProduccionPulido).filter(
                    ProduccionPulido.responsable == responsable,
                    ProduccionPulido.estado.in_(['EN_PROCESO', 'PAUSADO'])
                ).order_by(ProduccionPulido.id.desc()).first()

            if not trabajo:
                raise TrabajoPulidoNoEncontradoException("No se encontró el trabajo activo")

            pausas_db = db.session.query(PausasPulido).filter_by(id_pulido=trabajo.id).all()
            resumen_manuales = []
            total_manuales = 0
            for p in pausas_db:
                if p.hora_inicio and p.hora_fin:
                    dur = int((p.hora_fin - p.hora_inicio).total_seconds() / 60)
                    resumen_manuales.append({'motivo': p.motivo, 'duracion': dur})
                    total_manuales += dur

            ahora = get_colombia_time()
            total_fijas, detalles_fijas = PulidoService._calcular_minutos_pausas_fijas(trabajo.hora_inicio, ahora)

            return {
                'pausas_manuales': resumen_manuales,
                'total_manuales_min': total_manuales,
                'total_fijas_min': total_fijas,
                'pausas_fijas_detalle': detalles_fijas,
                'orden_produccion': trabajo.orden_produccion or ''
            }
        except Exception as e:
            if not isinstance(e, TrabajoPulidoNoEncontradoException):
                logger.error(f"❌ Error en PulidoService.obtener_resumen_pausas: {e}")
            raise

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
