# -*- coding: utf-8 -*-
"""
Corrección Dirigida: Horas de Inyección con error de digitación
-----------------------------------------------------------------------------
Reglas de negocio confirmadas por el usuario (2026-08-03):
  - Turno normal: 06:00-18:00 (incluye horas extra habituales, nunca más allá).
  - Excepción con fecha: entre 2026-06-22 y 2026-07-10 hubo turno real hasta
    las 22:00, así que esos días la ventana válida es 06:00-22:00.

A diferencia de Pulido, aquí se prueban 3 hipótesis por registro (no 2):
  1) Solo hora_inicio corrida +12h
  2) Solo hora_termina corrida +12h
  3) AMBAS corridas +12h (caso observado: el operario escribió las dos horas
     con el reloj de 12h invertido, ej. 18:02 / 5:58 en vez de 06:02 / 17:58)
Si más de una hipótesis cae dentro de la ventana, se considera ambigua y NO
se corrige automáticamente — queda para revisión manual.

IMPORTANTE: se usan las columnas de TEXTO hora_inicio/hora_termina como fuente
de verdad (son las que edita el operario). Las columnas fecha_inicia/fecha_fin
(DateTime) NO se tocan aquí: para muchos registros antiguos su componente de
hora nunca quedó sincronizado con hora_inicio/hora_termina (quedó en 00:00),
así que "corregirlas" sin entender cada consumidor histórico es más riesgo
que beneficio. Se corrige solo lo que el negocio realmente mira y edita.

Solo aplica a Inyección. NO toca Pulido (ya corregido en corregir_horas_pulido.py).

Seguridad:
  - Backup JSON de las filas afectadas antes de tocar la BD.
  - Todo el UPDATE corre en una sola transacción.

Ejecutar manualmente:
    python backend/scripts/corregir_horas_inyeccion.py
"""

import os
import re
import sys
import json
import logging
from datetime import date, datetime

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
                     handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("CorregirHorasInyeccion")

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurada. Defínela en tu .env o entorno.")

ANIO_DESDE = '2026-01-01'
ANIO_HASTA = '2027-01-01'

VENTANA_NORMAL = (6 * 60, 18 * 60)       # 06:00-18:00, en minutos del día
VENTANA_EXCEPCION = (6 * 60, 22 * 60)    # 06:00-22:00
EXCEPCION_DESDE = date(2026, 6, 22)
EXCEPCION_HASTA = date(2026, 7, 10)

BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'backups')

_RE_HORA = re.compile(r'^(\d{1,2}):(\d{2})')


def _parse_hora(s):
    if not s:
        return None
    m = _RE_HORA.match(s.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h, mi


def _fmt_hora(h, m):
    return f"{h:02d}:{m:02d}"


def _ventana_para(fecha_d: date):
    if EXCEPCION_DESDE <= fecha_d <= EXCEPCION_HASTA:
        return VENTANA_EXCEPCION
    return VENTANA_NORMAL


def _shift12(hm):
    h, m = hm
    return ((h + 12) % 24, m)


def _min(hm):
    return hm[0] * 60 + hm[1]


def _sugerir_inyeccion(hi, hf, fecha_d: date):
    """hi, hf: tuplas (h,m). Devuelve dict con hi/hf sugeridas o None si no hay
    una única hipótesis inequívoca dentro de la ventana del día."""
    lo, hi_lim = _ventana_para(fecha_d)
    span_max = hi_lim - lo

    hipotesis = {
        'hora_inicio': (_shift12(hi), hf),
        'hora_termina': (hi, _shift12(hf)),
        'ambas': (_shift12(hi), _shift12(hf)),
    }

    candidatos = []
    for campo, (hi2, hf2) in hipotesis.items():
        if not (lo <= _min(hi2) <= hi_lim and lo <= _min(hf2) <= hi_lim):
            continue
        dur = _min(hf2) - _min(hi2)
        if not (0 < dur <= span_max):
            continue
        candidatos.append({'campo': campo, 'hora_inicio': hi2, 'hora_fin': hf2, 'duracion_min': dur})

    if len(candidatos) == 1:
        return candidatos[0]
    return None


SQL_SELECT = """
    SELECT id, id_inyeccion, responsable, fecha_inicia, hora_inicio, hora_termina,
           duracion_segundos, tiempo_total_minutos, cantidad_real, observaciones
    FROM db_inyeccion
    WHERE fecha_inicia >= %(desde)s AND fecha_inicia < %(hasta)s
      AND hora_inicio IS NOT NULL AND hora_termina IS NOT NULL
    FOR UPDATE;
"""

SQL_UPDATE = """
    UPDATE db_inyeccion
    SET hora_inicio = %(hora_inicio)s,
        hora_termina = %(hora_termina)s,
        duracion_segundos = %(duracion_segundos)s,
        tiempo_total_minutos = %(tiempo_total_minutos)s,
        segundos_por_unidad = %(segundos_por_unidad)s,
        observaciones = %(observaciones)s
    WHERE id = %(id)s;
"""


def main():
    params = {'desde': ANIO_DESDE, 'hasta': ANIO_HASTA}
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_SELECT, params)
            filas = cur.fetchall()

            total_evaluadas = 0
            fuera_de_ventana = 0
            correcciones = []
            for r in filas:
                hi = _parse_hora(r['hora_inicio'])
                hf = _parse_hora(r['hora_termina'])
                if not hi or not hf:
                    continue
                total_evaluadas += 1
                fecha_d = r['fecha_inicia'].date()
                lo, hi_lim = _ventana_para(fecha_d)
                if lo <= _min(hi) <= hi_lim and lo <= _min(hf) <= hi_lim:
                    continue  # ya está dentro de ventana, no es anomalía

                fuera_de_ventana += 1
                sugerencia = _sugerir_inyeccion(hi, hf, fecha_d)
                if not sugerencia:
                    continue  # ambiguo o sin hipótesis válida: fuera de alcance

                hi2, hf2 = sugerencia['hora_inicio'], sugerencia['hora_fin']
                dur_seg_final = sugerencia['duracion_min'] * 60
                cant = float(r['cantidad_real'] or 0)
                tiempo_min = round(dur_seg_final / 60.0, 2)
                seg_x_u = round(dur_seg_final / cant, 2) if (dur_seg_final > 0 and cant > 0) else 0.0

                tag = json.dumps({
                    "corregido_am_pm": True,
                    "campo_original": sugerencia['campo'],
                    "hora_inicio_original": r['hora_inicio'],
                    "hora_termina_original": r['hora_termina'],
                    "fecha_correccion": datetime.now().strftime('%Y-%m-%d'),
                }, ensure_ascii=False)
                obs_nueva = (r['observaciones'] or '').strip()
                obs_nueva = (obs_nueva + f"\n[CORRECCION_HORA]{tag}[/CORRECCION_HORA]").strip()

                correcciones.append({
                    'id': r['id'],
                    'id_inyeccion': r['id_inyeccion'],
                    'responsable': r['responsable'],
                    'fecha': fecha_d,
                    'hora_inicio_pre': r['hora_inicio'],
                    'hora_termina_pre': r['hora_termina'],
                    'hora_inicio': _fmt_hora(*hi2),
                    'hora_termina': _fmt_hora(*hf2),
                    'duracion_segundos': dur_seg_final,
                    'tiempo_total_minutos': tiempo_min,
                    'segundos_por_unidad': seg_x_u,
                    'observaciones': obs_nueva,
                })

            logger.info(f"Evaluadas: {total_evaluadas} | Fuera de ventana: {fuera_de_ventana} | "
                        f"Con corrección inequívoca: {len(correcciones)} | "
                        f"Ambiguas/sin sugerencia: {fuera_de_ventana - len(correcciones)}")

            if not correcciones:
                logger.info("Nada que corregir.")
                conn.rollback()
                return

            os.makedirs(BACKUP_DIR, exist_ok=True)
            backup_path = os.path.join(
                BACKUP_DIR,
                f"inyeccion_pre_correccion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump([{
                    'id': c['id'], 'id_inyeccion': c['id_inyeccion'], 'responsable': c['responsable'],
                    'fecha': c['fecha'].isoformat(),
                    'hora_inicio': c['hora_inicio_pre'], 'hora_termina': c['hora_termina_pre'],
                } for c in correcciones], f, ensure_ascii=False, indent=2)
            logger.info(f"Backup pre-corrección escrito: {backup_path} ({len(correcciones)} filas)")

            for c in correcciones:
                cur.execute(SQL_UPDATE, {
                    'id': c['id'],
                    'hora_inicio': c['hora_inicio'],
                    'hora_termina': c['hora_termina'],
                    'duracion_segundos': c['duracion_segundos'],
                    'tiempo_total_minutos': c['tiempo_total_minutos'],
                    'segundos_por_unidad': c['segundos_por_unidad'],
                    'observaciones': c['observaciones'],
                })
                logger.info(
                    f"{c['id_inyeccion']} ({c['responsable']}, {c['fecha']}): "
                    f"{c['hora_inicio_pre']}-{c['hora_termina_pre']} -> "
                    f"{c['hora_inicio']}-{c['hora_termina']} "
                    f"({c['duracion_segundos']/3600:.2f}h)"
                )

        conn.commit()
        logger.info(f"OK: {len(correcciones)} registros de Inyección corregidos y confirmados en BD.")
    except Exception:
        conn.rollback()
        logger.exception("Error durante la corrección. Se hizo ROLLBACK, ningún cambio quedó aplicado.")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
