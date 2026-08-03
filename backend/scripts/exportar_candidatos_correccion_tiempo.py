# -*- coding: utf-8 -*-
"""
Exportador de Candidatos de Corrección: Anomalías de Tiempo (Pulido/Inyección)
-------------------------------------------------------------------------------
NO modifica la base de datos. Toma los registros detectados por
detectar_anomalias_tiempo.py y arma un Excel con una hora "sugerida" para que
un supervisor de planta apruebe o corrija manualmente cada fila antes de que
cualquier UPDATE toque la BD.

Reglas de negocio confirmadas por el usuario (2026-08-03):
  - PULIDO: turno único 07:00-17:00, sin turno nocturno. Cualquier hora fuera
    de esa ventana es candidata a corrección por ±12h (heurística de "se
    comieron el 1" al escribir la hora en formato 24h, ej. 3:20 en vez de
    13:20). Se exige que AMBAS horas (inicio y fin) queden dentro de la
    ventana tras el ajuste.
  - INYECCIÓN: sí existe turno nocturno legítimo. Los registros "invertidos"
    (hora_fin < hora_inicio) con duración <=12h NO se tocan — son turnos de
    noche válidos. Solo se proponen candidatos para los que exceden 12h de
    duración, sin importar la hora del día.

La columna 'aprobado_SI_NO' queda vacía a propósito: el supervisor debe
llenarla y, si la sugerencia no es correcta, escribir la hora real en
'hora_inicio_corregida' / 'hora_fin_corregida'. Ese Excel revisado es el único
input válido para un script de corrección posterior (aún no escrito).

Ejecutar manualmente:
    python backend/scripts/exportar_candidatos_correccion_tiempo.py
"""

import os
from datetime import datetime

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurada. Defínela en tu .env o entorno.")

ANIO_DESDE = '2026-01-01'
ANIO_HASTA = '2027-01-01'
LIMITE_SEG = 12 * 3600

PULIDO_VENTANA = (7 * 3600, 17 * 3600)          # 07:00 - 17:00, en segundos del día
INYECCION_RANGO_PLAUSIBLE = (3 * 3600, 12 * 3600)  # duración de turno aceptable

SALIDA_XLSX = os.path.join(os.path.dirname(__file__), '..', '..', 'candidatos_correccion_tiempo_v2.xlsx')


def _seg_del_dia(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60


def _shift_hora(dt: datetime, delta_horas: int) -> datetime:
    """Desplaza solo la hora del dia (mod 24), preservando fecha y minuto.
    Evita que +/-12h con timedelta arrastre la FECHA y contamine el calculo
    de duracion con un artefacto de +/-24h."""
    nueva_hora = (dt.hour + delta_horas) % 24
    return dt.replace(hour=nueva_hora)


def _duracion(hi: datetime, hf: datetime) -> int:
    diff = int((hf - hi).total_seconds())
    if diff < 0:
        diff += 86400
    return diff


def _sugerir_pulido(hi: datetime, hf: datetime):
    """Exige que, tras desplazar +/-12h un solo campo, AMBAS horas caigan en 07:00-17:00
    y la duracion resultante quepa en el span de la ventana (<=10h)."""
    lo, hi_lim = PULIDO_VENTANA
    span_max = hi_lim - lo
    candidatos = []
    # +12h y -12h dan la MISMA hora en reloj de 24h (mod 24) -> una sola hipotesis por campo.
    for campo, delta in [('hora_inicio', 12), ('hora_fin', 12)]:
        hi2 = _shift_hora(hi, delta) if campo == 'hora_inicio' else hi
        hf2 = _shift_hora(hf, delta) if campo == 'hora_fin' else hf

        if not (lo <= _seg_del_dia(hi2) <= hi_lim and lo <= _seg_del_dia(hf2) <= hi_lim):
            continue
        dur = _duracion(hi2, hf2)
        if not (0 < dur <= span_max):
            continue
        candidatos.append({
            'campo': campo, 'delta': delta,
            'hora_inicio_sugerida': hi2, 'hora_fin_sugerida': hf2,
            'duracion_sugerida_seg': dur,
        })

    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]
    # Ambiguo (más de una hipótesis cae en ventana): no forzar, dejar en manual.
    return None


def _sugerir_inyeccion(hi: datetime, hf: datetime):
    """Solo se llama para filas con duracion > 12h. No hay ventana horaria (turno nocturno es válido)."""
    lo, hi_lim = INYECCION_RANGO_PLAUSIBLE
    candidatos = []
    # +12h y -12h dan la MISMA hora en reloj de 24h (mod 24) -> una sola hipotesis por campo.
    for campo, delta in [('hora_inicio', 12), ('hora_fin', 12)]:
        hi2 = _shift_hora(hi, delta) if campo == 'hora_inicio' else hi
        hf2 = _shift_hora(hf, delta) if campo == 'hora_fin' else hf

        dur = _duracion(hi2, hf2)
        if lo <= dur <= hi_lim:
            candidatos.append({
                'campo': campo, 'delta': delta,
                'hora_inicio_sugerida': hi2, 'hora_fin_sugerida': hf2,
                'duracion_sugerida_seg': dur,
                'distancia_8h': abs(dur - 8 * 3600),
            })

    if not candidatos:
        return None
    return min(candidatos, key=lambda c: c['distancia_8h'])


SQL_PULIDO = """
    SELECT id, id_pulido, responsable, fecha, hora_inicio, hora_fin, duracion_segundos
    FROM db_pulido
    WHERE fecha >= %(desde)s AND fecha < %(hasta)s
      AND hora_inicio IS NOT NULL AND hora_fin IS NOT NULL
      AND (duracion_segundos > %(limite)s OR hora_fin < hora_inicio)
    ORDER BY fecha DESC;
"""

SQL_INYECCION = """
    SELECT id, id_inyeccion, responsable, fecha_inicia AS fecha,
           fecha_inicia AS hora_inicio, fecha_fin AS hora_fin, duracion_segundos
    FROM db_inyeccion
    WHERE fecha_inicia >= %(desde)s AND fecha_inicia < %(hasta)s
      AND hora_inicio IS NOT NULL AND hora_termina IS NOT NULL
      AND (duracion_segundos > %(limite)s OR fecha_fin < fecha_inicia)
    ORDER BY fecha_inicia DESC;
"""


def _fila_base(tabla, r, hi, hf):
    return {
        'tabla': tabla,
        'id_bd': r['id'],
        'id_registro': r.get('id_pulido') or r.get('id_inyeccion'),
        'responsable': r['responsable'],
        'fecha': r['fecha'],
        'hora_inicio_actual': hi,
        'hora_fin_actual': hf,
        'duracion_actual_h': round((r['duracion_segundos'] or 0) / 3600.0, 2),
    }


def _armar_filas_pulido(filas):
    out = []
    for r in filas:
        hi, hf = r['hora_inicio'], r['hora_fin']
        sugerencia = _sugerir_pulido(hi, hf) if hi and hf else None
        fila = _fila_base('PULIDO', r, hi, hf)
        fila.update({
            'sugerencia_campo': sugerencia['campo'] if sugerencia else '',
            'sugerencia_delta_h': sugerencia['delta'] if sugerencia else '',
            'hora_inicio_sugerida': sugerencia['hora_inicio_sugerida'] if sugerencia else '',
            'hora_fin_sugerida': sugerencia['hora_fin_sugerida'] if sugerencia else '',
            'duracion_sugerida_h': round(sugerencia['duracion_sugerida_seg'] / 3600.0, 2) if sugerencia else '',
            'motivo': 'Fuera de ventana 07:00-17:00 (Pulido no tiene turno nocturno)',
            'confianza': 'ALTA (unica hipotesis +/-12h cae en 07:00-17:00)' if sugerencia else 'BAJA (ninguna o mas de una hipotesis encaja, revisar manual)',
            'aprobado_SI_NO': '',
            'hora_inicio_corregida': '',
            'hora_fin_corregida': '',
            'observacion_supervisor': '',
        })
        out.append(fila)
    return out


def _armar_filas_inyeccion(filas):
    out = []
    for r in filas:
        hi, hf = r['hora_inicio'], r['hora_fin']
        dur = r['duracion_segundos'] or 0

        if dur <= LIMITE_SEG:
            # Invertido pero <=12h: turno nocturno legítimo, no se toca.
            fila = _fila_base('INYECCION', r, hi, hf)
            fila.update({
                'sugerencia_campo': '', 'sugerencia_delta_h': '',
                'hora_inicio_sugerida': '', 'hora_fin_sugerida': '',
                'duracion_sugerida_h': '',
                'motivo': 'Cruza medianoche pero duracion <=12h: turno nocturno legitimo, NO tocar',
                'confianza': 'NO ES ANOMALIA (turno nocturno valido)',
                'aprobado_SI_NO': '', 'hora_inicio_corregida': '', 'hora_fin_corregida': '',
                'observacion_supervisor': '',
            })
            out.append(fila)
            continue

        sugerencia = _sugerir_inyeccion(hi, hf) if hi and hf else None
        fila = _fila_base('INYECCION', r, hi, hf)
        fila.update({
            'sugerencia_campo': sugerencia['campo'] if sugerencia else '',
            'sugerencia_delta_h': sugerencia['delta'] if sugerencia else '',
            'hora_inicio_sugerida': sugerencia['hora_inicio_sugerida'] if sugerencia else '',
            'hora_fin_sugerida': sugerencia['hora_fin_sugerida'] if sugerencia else '',
            'duracion_sugerida_h': round(sugerencia['duracion_sugerida_seg'] / 3600.0, 2) if sugerencia else '',
            'motivo': f'Duracion > 12h ({round(dur/3600.0,1)}h), imposible en cualquier turno',
            'confianza': 'ALTA (heuristica +/-12h da turno 3-12h)' if sugerencia else 'BAJA (revisar manualmente, sin sugerencia clara)',
            'aprobado_SI_NO': '', 'hora_inicio_corregida': '', 'hora_fin_corregida': '',
            'observacion_supervisor': '',
        })
        out.append(fila)
    return out


def main():
    params = {'desde': ANIO_DESDE, 'hasta': ANIO_HASTA, 'limite': LIMITE_SEG}
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SQL_PULIDO, params)
            filas_pulido = cur.fetchall()

            cur.execute(SQL_INYECCION, params)
            filas_iny = cur.fetchall()
    finally:
        conn.close()

    filas = _armar_filas_pulido(filas_pulido) + _armar_filas_inyeccion(filas_iny)
    df = pd.DataFrame(filas)

    with pd.ExcelWriter(SALIDA_XLSX, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='candidatos', index=False)
        resumen = df.groupby(['tabla', 'confianza']).size().reset_index(name='n')
        resumen.to_excel(writer, sheet_name='resumen', index=False)

    print(f"Generado: {SALIDA_XLSX}")
    print(f"Total filas: {len(df)}")
    print(df.groupby(['tabla', 'confianza']).size())


if __name__ == '__main__':
    main()
