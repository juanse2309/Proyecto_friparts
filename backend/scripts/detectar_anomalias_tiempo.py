# -*- coding: utf-8 -*-
"""
Auditoría de Solo Lectura: Anomalías AM/PM en Pulido e Inyección
------------------------------------------------------------------
Detecta turnos con duración imposible (>12h) o con hora_fin < hora_inicio
(síntoma clásico de confundir la hora de un campo de 24h, ej. escribir 08
en vez de 20). NO modifica ningún dato — solo SELECT para revisión gerencial.

Ejecutar manualmente:
    python backend/scripts/detectar_anomalias_tiempo.py
"""

import os
import sys
import psycopg2
import psycopg2.extras

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurada. Defínela en tu .env o entorno.")

ANIO = 2026
LIMITE_HORAS = 12

SQL_PULIDO = """
    SELECT
        id_pulido,
        responsable,
        fecha,
        hora_inicio,
        hora_fin,
        duracion_segundos,
        ROUND(duracion_segundos / 3600.0, 2) AS horas,
        (hora_fin < hora_inicio) AS invertido
    FROM db_pulido
    WHERE fecha >= %(desde)s AND fecha < %(hasta)s
      AND hora_inicio IS NOT NULL AND hora_fin IS NOT NULL
      AND (
            duracion_segundos > %(limite_seg)s
            OR hora_fin < hora_inicio
      )
    ORDER BY fecha DESC;
"""

SQL_INYECCION = """
    SELECT
        id_inyeccion,
        responsable,
        fecha_inicia,
        hora_inicio,
        hora_termina AS hora_fin,
        duracion_segundos,
        ROUND(duracion_segundos / 3600.0, 2) AS horas,
        (fecha_fin < fecha_inicia) AS invertido
    FROM db_inyeccion
    WHERE fecha_inicia >= %(desde)s AND fecha_inicia < %(hasta)s
      AND hora_inicio IS NOT NULL AND hora_termina IS NOT NULL
      AND (
            duracion_segundos > %(limite_seg)s
            OR fecha_fin < fecha_inicia
      )
    ORDER BY fecha_inicia DESC;
"""


def _imprimir_tabla(titulo, filas):
    print(f"\n=== {titulo}: {len(filas)} registro(s) sospechoso(s) ===")
    if not filas:
        return
    for r in filas:
        print(dict(r))


def main():
    params = {
        'desde': f'{ANIO}-01-01',
        'hasta': f'{ANIO + 1}-01-01',
        'limite_seg': LIMITE_HORAS * 3600,
    }
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_PULIDO, params)
            filas_pulido = cur.fetchall()

            cur.execute(SQL_INYECCION, params)
            filas_iny = cur.fetchall()
    finally:
        conn.close()

    _imprimir_tabla("PULIDO", filas_pulido)
    _imprimir_tabla("INYECCIÓN", filas_iny)


if __name__ == '__main__':
    main()
