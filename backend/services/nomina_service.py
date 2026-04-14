"""
nomina_service.py - Servicio centralizado para la lógica de nómina y cortes.

Responsabilidades:
  - Leer la hoja CORTES_NOMINA y determinar la fecha de corte más reciente.
  - Filtrar registros de CONTROL_ASISTENCIA posteriores al corte.
  - Consolidar horas por operario (estrictamente > fecha corte).
"""

import logging
from datetime import datetime

from backend.core.database import sheets_client
from backend.config.settings import Hojas

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────

def _parse_fecha_corte(fecha_str: str):
    """
    Parsea la fecha de corte en formato ISO completo o parcial.
    Ejemplo válido: '2026-03-30T19:13:38' → datetime(2026, 3, 30, 19, 13, 38)
    """
    if not fecha_str:
        return None

    fecha_str = fecha_str.strip()

    # ISO completo con hora
    if 'T' in fecha_str:
        try:
            return datetime.fromisoformat(fecha_str)
        except ValueError:
            pass
        # Fallback: solo la parte de fecha
        try:
            return datetime.strptime(fecha_str.split('T')[0], '%Y-%m-%d')
        except ValueError:
            pass

    # Solo fecha
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(fecha_str.split(' ')[0], fmt)
        except ValueError:
            continue

    logger.warning(f"No se pudo parsear la fecha de corte: '{fecha_str}'")
    return None


def _parse_fecha_registro(fecha_str: str):
    """
    Parsea la fecha de un registro de asistencia.
    El frontend guarda en formato YYYY-MM-DD; la hoja podría tener DD/MM/YYYY.
    Se interpreta como las 00:00:00 del día para la comparación estricta.
    """
    if not fecha_str or not isinstance(fecha_str, str):
        return None

    fecha_str = fecha_str.strip()

    if '-' in fecha_str:
        try:
            return datetime.strptime(fecha_str, '%Y-%m-%d')
        except ValueError:
            pass
    else:
        try:
            return datetime.strptime(fecha_str, '%d/%m/%Y')
        except ValueError:
            pass

    return None


def _parse_hours(val) -> float:
    """Convierte un valor de horas (posiblemente con coma decimal de Excel) a float."""
    if not val:
        return 0.0
    try:
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0


# ── API pública ──────────────────────────────────────────────────────────

def get_ultima_fecha_corte():
    """
    Lee la hoja CORTES_NOMINA y devuelve la fecha del último corte como datetime,
    o None si no hay cortes registrados.
    """
    try:
        ws_cortes = sheets_client.get_worksheet(Hojas.CORTES_NOMINA)
        if not ws_cortes:
            logger.info("Hoja CORTES_NOMINA no encontrada; sin fecha de corte.")
            return None

        cortes = sheets_client.get_all_records_seguro(ws_cortes)
        if not cortes:
            logger.info("Hoja CORTES_NOMINA vacía; sin fecha de corte.")
            return None

        # El último registro es el corte más reciente
        ultimo_corte = cortes[-1]

        # Buscar la columna cuyo nombre contiene 'FECHA'
        fecha_str = ""
        for k, v in ultimo_corte.items():
            if 'FECHA' in str(k).upper():
                fecha_str = str(v).strip()
                break

        fecha_dt = _parse_fecha_corte(fecha_str)

        if fecha_dt:
            logger.info(f"Última fecha de corte detectada: {fecha_dt.isoformat()}")
        else:
            logger.warning(f"No se pudo interpretar la fecha de corte: '{fecha_str}'")

        return fecha_dt

    except Exception as e:
        logger.warning(f"Error leyendo CORTES_NOMINA: {e}")
        return None


def filtrar_registros_post_corte(registros: list, ultima_fecha_corte):
    """
    Filtra una lista de registros de CONTROL_ASISTENCIA devolviendo
    SOLO los que sean estrictamente posteriores a `ultima_fecha_corte`.

    Args:
        registros: lista de dicts (cada fila de la hoja).
        ultima_fecha_corte: datetime o None.

    Returns:
        Lista filtrada de registros (dicts originales).
    """
    if not ultima_fecha_corte:
        # Sin corte previo → todos los registros son válidos
        return registros

    filtrados = []
    for r in registros:
        fecha_str = str(r.get('FECHA', '')).strip()
        if not fecha_str:
            continue

        fecha_reg = _parse_fecha_registro(fecha_str)
        if not fecha_reg:
            continue

        # Filtro estricto: solo registros con fecha MAYOR al corte
        if fecha_reg > ultima_fecha_corte:
            filtrados.append(r)

    return filtrados


def consolidar_horas(registros_filtrados: list) -> dict:
    """
    Agrupa los registros filtrados por colaborador y suma horas ordinarias/extras.

    Returns:
        dict  { 'NOMBRE': {'ordinarias': float, 'extras': float}, … }
        Si un operario no tiene registros, simplemente no aparece (equivale a 0).
    """
    consolidado = {}

    for r in registros_filtrados:
        colab = str(r.get('COLABORADOR', 'Desconocido')).strip()
        if not colab:
            continue

        h_ord = _parse_hours(r.get('HORAS_ORDINARIAS', r.get('HORAS ORDINARIAS', 0)))
        h_ext = _parse_hours(r.get('HORAS_EXTRAS', r.get('HORAS EXTRAS', 0)))

        if colab not in consolidado:
            consolidado[colab] = {'ordinarias': 0.0, 'extras': 0.0}

        consolidado[colab]['ordinarias'] = round(consolidado[colab]['ordinarias'] + h_ord, 2)
        consolidado[colab]['extras'] = round(consolidado[colab]['extras'] + h_ext, 2)

    return consolidado


def construir_detalle_diario(registros_filtrados: list) -> list:
    """
    Construye la lista de detalle diario para exportar en CSV.

    Returns:
        Lista de dicts ordenada por (colaborador, fecha).
    """
    detalle = []
    for r in registros_filtrados:
        fecha_str = str(r.get('FECHA', '')).strip()
        colab = str(r.get('COLABORADOR', 'Desconocido')).strip()

        detalle.append({
            'colaborador': colab,
            'fecha': fecha_str,
            'ingreso': r.get('INGRESO_REAL', r.get('INGRESO REAL', '')),
            'salida': r.get('SALIDA_REAL', r.get('SALIDA REAL', '')),
            'horas_ordinarias': _parse_hours(r.get('HORAS_ORDINARIAS', r.get('HORAS ORDINARIAS', 0))),
            'horas_extras': _parse_hours(r.get('HORAS_EXTRAS', r.get('HORAS EXTRAS', 0))),
            'motivo': r.get('MOTIVO', ''),
            'comentarios': r.get('COMENTARIOS', '')
        })

    detalle.sort(key=lambda x: (x['colaborador'], x['fecha']))
    return detalle
