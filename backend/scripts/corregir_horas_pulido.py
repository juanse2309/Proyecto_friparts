# -*- coding: utf-8 -*-
"""
Corrección Dirigida: Horas de Pulido con error de digitación (07:00-17:00)
-----------------------------------------------------------------------------
Aplica SOLO los 110 registros de db_pulido marcados como 'ALTA' confianza en
candidatos_correccion_tiempo_v2.xlsx (única hipótesis +/-12h que cae dentro
de la ventana real de turno 07:00-17:00 — ver exportar_candidatos_correccion_tiempo.py).

Aprobado explícitamente por el usuario el 2026-08-03: proceder solo con Pulido;
Inyección queda pendiente de revisión adicional y NO se toca aquí.

Por cada registro corregido, recalcula duracion_segundos / tiempo_total_minutos /
segundos_por_unidad con la MISMA fórmula que usa pulido_routes.py al guardar
(incluye el descuento de pausas programadas Desayuno/Almuerzo), para no dejar
esos campos derivados desincronizados de hora_inicio/hora_fin.

Seguridad:
  - Antes de tocar la BD, escribe un backup JSON de las filas afectadas
    (estado completo pre-corrección) en backend/scripts/backups/.
  - Todo el UPDATE corre en una sola transacción.

Ejecutar manualmente:
    python backend/scripts/corregir_horas_pulido.py
"""

import os
import sys
import json
import logging
from datetime import datetime

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
                     handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("CorregirHorasPulido")

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurada. Defínela en tu .env o entorno.")

ANIO_DESDE = '2026-01-01'
ANIO_HASTA = '2027-01-01'
LIMITE_SEG = 12 * 3600
PULIDO_VENTANA = (7 * 3600, 17 * 3600)  # 07:00 - 17:00, en segundos del día

# Debe coincidir EXACTO con PulidoService._VENTANAS_PAUSAS_PROGRAMADAS
# (backend/services/pulido_service.py) — única fuente de verdad en producción.
VENTANAS_PAUSAS_PROGRAMADAS = (
    ("DESAYUNO", "09:00", "09:20"),
    ("ALMUERZO", "13:00", "13:40"),
)

BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'backups')


def _seg_del_dia(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60


def _shift_hora(dt: datetime, delta_horas: int) -> datetime:
    nueva_hora = (dt.hour + delta_horas) % 24
    return dt.replace(hour=nueva_hora)


def _sugerir_pulido(hi: datetime, hf: datetime):
    lo, hi_lim = PULIDO_VENTANA
    span_max = hi_lim - lo
    candidatos = []
    for campo in ('hora_inicio', 'hora_fin'):
        hi2 = _shift_hora(hi, 12) if campo == 'hora_inicio' else hi
        hf2 = _shift_hora(hf, 12) if campo == 'hora_fin' else hf
        if not (lo <= _seg_del_dia(hi2) <= hi_lim and lo <= _seg_del_dia(hf2) <= hi_lim):
            continue
        dur = int((hf2 - hi2).total_seconds())
        if not (0 < dur <= span_max):
            continue
        candidatos.append({'campo': campo, 'hora_inicio': hi2, 'hora_fin': hf2, 'duracion_seg': dur})
    if len(candidatos) == 1:
        return candidatos[0]
    return None


def _descuento_pausas(hi: datetime, hf: datetime) -> int:
    if not hi or not hf or hf <= hi or hi.date() != hf.date():
        return 0
    total = 0
    for _nombre, ini_str, fin_str in VENTANAS_PAUSAS_PROGRAMADAS:
        h_i, m_i = (int(x) for x in ini_str.split(':'))
        h_f, m_f = (int(x) for x in fin_str.split(':'))
        ventana_ini = hi.replace(hour=h_i, minute=m_i, second=0, microsecond=0)
        ventana_fin = hi.replace(hour=h_f, minute=m_f, second=0, microsecond=0)
        solape_ini = max(hi, ventana_ini)
        solape_fin = min(hf, ventana_fin)
        solape_seg = int((solape_fin - solape_ini).total_seconds())
        if solape_seg > 0:
            total += solape_seg
    return total


SQL_SELECT = """
    SELECT id, id_pulido, responsable, fecha, hora_inicio, hora_fin,
           duracion_segundos, tiempo_total_minutos, segundos_por_unidad,
           cantidad_real, observaciones
    FROM db_pulido
    WHERE fecha >= %(desde)s AND fecha < %(hasta)s
      AND hora_inicio IS NOT NULL AND hora_fin IS NOT NULL
      AND (duracion_segundos > %(limite)s OR hora_fin < hora_inicio)
    FOR UPDATE;
"""

SQL_UPDATE = """
    UPDATE db_pulido
    SET hora_inicio = %(hora_inicio)s,
        hora_fin = %(hora_fin)s,
        duracion_segundos = %(duracion_segundos)s,
        tiempo_total_minutos = %(tiempo_total_minutos)s,
        segundos_por_unidad = %(segundos_por_unidad)s,
        observaciones = %(observaciones)s
    WHERE id = %(id)s;
"""


def main():
    params = {'desde': ANIO_DESDE, 'hasta': ANIO_HASTA, 'limite': LIMITE_SEG}
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_SELECT, params)
            filas = cur.fetchall()

            correcciones = []
            for r in filas:
                sugerencia = _sugerir_pulido(r['hora_inicio'], r['hora_fin'])
                if not sugerencia:
                    continue  # BAJA / ambiguo: fuera de alcance de esta corrección

                hi2, hf2 = sugerencia['hora_inicio'], sugerencia['hora_fin']
                dur_bruta = sugerencia['duracion_seg']
                descuento = _descuento_pausas(hi2, hf2)
                dur_final = max(0, dur_bruta - descuento)
                cant = float(r['cantidad_real'] or 0)
                seg_x_u = round(dur_final / cant, 2) if cant > 0 else 0.0

                tag = json.dumps({
                    "corregido_am_pm": True,
                    "campo_original": sugerencia['campo'],
                    "hora_inicio_original": r['hora_inicio'].strftime('%Y-%m-%d %H:%M'),
                    "hora_fin_original": r['hora_fin'].strftime('%Y-%m-%d %H:%M'),
                    "fecha_correccion": datetime.now().strftime('%Y-%m-%d'),
                }, ensure_ascii=False)
                obs_nueva = (r['observaciones'] or '').strip()
                obs_nueva = (obs_nueva + f"\n[CORRECCION_HORA]{tag}[/CORRECCION_HORA]").strip()

                correcciones.append({
                    'id': r['id'],
                    'id_pulido': r['id_pulido'],
                    'responsable': r['responsable'],
                    'hora_inicio_pre': r['hora_inicio'],
                    'hora_fin_pre': r['hora_fin'],
                    'hora_inicio': hi2,
                    'hora_fin': hf2,
                    'duracion_segundos_pre': r['duracion_segundos'],
                    'duracion_segundos': dur_final,
                    'tiempo_total_minutos_pre': float(r['tiempo_total_minutos'] or 0),
                    'tiempo_total_minutos': round(dur_final / 60.0, 2),
                    'segundos_por_unidad': seg_x_u,
                    'observaciones': obs_nueva,
                })

            if not correcciones:
                logger.info("No hay registros ALTA pendientes de corregir (¿ya se aplicó antes?).")
                conn.rollback()
                return

            # --- Backup pre-corrección ---
            os.makedirs(BACKUP_DIR, exist_ok=True)
            backup_path = os.path.join(
                BACKUP_DIR,
                f"pulido_pre_correccion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump([{
                    'id': c['id'], 'id_pulido': c['id_pulido'], 'responsable': c['responsable'],
                    'hora_inicio': c['hora_inicio_pre'].isoformat(),
                    'hora_fin': c['hora_fin_pre'].isoformat(),
                    'duracion_segundos': c['duracion_segundos_pre'],
                    'tiempo_total_minutos': c['tiempo_total_minutos_pre'],
                } for c in correcciones], f, ensure_ascii=False, indent=2)
            logger.info(f"Backup pre-corrección escrito: {backup_path} ({len(correcciones)} filas)")

            for c in correcciones:
                cur.execute(SQL_UPDATE, {
                    'id': c['id'],
                    'hora_inicio': c['hora_inicio'],
                    'hora_fin': c['hora_fin'],
                    'duracion_segundos': c['duracion_segundos'],
                    'tiempo_total_minutos': c['tiempo_total_minutos'],
                    'segundos_por_unidad': c['segundos_por_unidad'],
                    'observaciones': c['observaciones'],
                })
                dur_pre_h = (c['duracion_segundos_pre'] or 0) / 3600
                logger.info(
                    f"{c['id_pulido']} ({c['responsable']}): "
                    f"{c['hora_inicio_pre'].strftime('%H:%M')}-{c['hora_fin_pre'].strftime('%H:%M')} "
                    f"({dur_pre_h:.2f}h) -> "
                    f"{c['hora_inicio'].strftime('%H:%M')}-{c['hora_fin'].strftime('%H:%M')} "
                    f"({c['duracion_segundos']/3600:.2f}h)"
                )

        conn.commit()
        logger.info(f"OK: {len(correcciones)} registros de Pulido corregidos y confirmados en BD.")
    except Exception:
        conn.rollback()
        logger.exception("Error durante la corrección. Se hizo ROLLBACK, ningún cambio quedó aplicado.")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
