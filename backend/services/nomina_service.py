"""
nomina_service.py - Servicio centralizado para la lógica de nómina y cortes (SQL-First).

Responsabilidades:
  - Leer la tabla cortes_nomina para determinar la fecha de corte más reciente.
  - Filtrar registros de db_asistencia posteriores al corte.
  - Consolidar horas por operario (estrictamente > fecha corte).
"""

import logging
from datetime import datetime
from backend.core.sql_database import db
from backend.models.sql_models import CorteNomina, RegistroAsistencia
from sqlalchemy import func

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────

def _parse_hours(val) -> float:
    """Convierte un valor de horas a float."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ── API pública ──────────────────────────────────────────────────────────

def get_ultima_fecha_corte():
    """
    Lee la tabla cortes_nomina de SQL y devuelve la fecha del último corte.
    """
    try:
        # Obtener el registro con la fecha_corte más reciente
        ultimo = db.session.query(CorteNomina).order_by(CorteNomina.fecha_corte.desc()).first()
        if not ultimo:
            logger.info("No se encontraron registros en cortes_nomina.")
            return None

        # Ya es un objeto date/datetime en SQL
        return ultimo.fecha_corte

    except Exception as e:
        logger.warning(f"Error leyendo cortes_nomina SQL: {e}")
        return None


def filtrar_registros_post_corte(registros: list, ultima_fecha_corte):
    """
    Filtra una lista de registros de db_asistencia.
    (En SQL-First, preferimos filtrar directamente en la query, 
    pero mantenemos esta función para compatibilidad si se recibe una lista).
    """
    if not ultima_fecha_corte:
        return registros

    # Asegurar que ultima_fecha_corte sea date para comparación
    if isinstance(ultima_fecha_corte, datetime):
        ultima_fecha_corte = ultima_fecha_corte.date()

    filtrados = []
    for r in registros:
        fecha_reg = r.fecha if hasattr(r, 'fecha') else r.get('fecha')
        if not fecha_reg: continue
        
        # Convertir a date si es string
        if isinstance(fecha_reg, str):
            try:
                fecha_reg = datetime.strptime(fecha_reg, '%Y-%m-%d').date()
            except: continue
        
        if fecha_reg > ultima_fecha_corte:
            filtrados.append(r)

    return filtrados


def consolidar_horas(registros_filtrados: list) -> list:
    """
    Agrupa los registros filtrados por colaborador y suma horas ordinarias/extras.
    Retorna una lista de diccionarios con redondeo a 2 decimales.
    """
    consolidado_dict = {}

    for r in registros_filtrados:
        # Soporta tanto objetos modelo como diccionarios
        colab = r.colaborador if hasattr(r, 'colaborador') else r.get('colaborador', 'Desconocido')
        h_ord = _parse_hours(r.horas_ordinarias if hasattr(r, 'horas_ordinarias') else r.get('horas_ordinarias', 0))
        h_ext = _parse_hours(r.horas_extras if hasattr(r, 'horas_extras') else r.get('horas_extras', 0))

        if colab not in consolidado_dict:
            consolidado_dict[colab] = {'ordinarias': 0.0, 'extras': 0.0}

        consolidado_dict[colab]['ordinarias'] += h_ord
        consolidado_dict[colab]['extras'] += h_ext

    # Convertir a lista de dicts para el frontend
    resultado = []
    for nombre, horas in consolidado_dict.items():
        resultado.append({
            'colaborador': nombre,
            'horas_ordinarias': round(horas['ordinarias'], 2),
            'horas_extras': round(horas['extras'], 2)
        })
        
    return resultado


def construir_detalle_diario(registros_filtrados: list) -> list:
    """
    Construye la lista de detalle diario para exportar.
    """
    detalle = []
    for r in registros_filtrados:
        colab = r.colaborador if hasattr(r, 'colaborador') else r.get('colaborador', 'Desconocido')
        fecha = r.fecha if hasattr(r, 'fecha') else r.get('fecha')
        
        # Formatear fecha para el CSV
        if hasattr(fecha, 'strftime'):
            fecha_str = fecha.strftime('%Y-%m-%d')
        else:
            fecha_str = str(fecha)

        detalle.append({
            'colaborador': colab,
            'fecha': fecha_str,
            'ingreso': r.ingreso_real if hasattr(r, 'ingreso_real') else r.get('ingreso_real', ''),
            'salida': r.salida_real if hasattr(r, 'salida_real') else r.get('salida_real', ''),
            'horas_ordinarias': _parse_hours(r.horas_ordinarias if hasattr(r, 'horas_ordinarias') else r.get('horas_ordinarias', 0)),
            'horas_extras': _parse_hours(r.horas_extras if hasattr(r, 'horas_extras') else r.get('horas_extras', 0)),
            'motivo': r.motivo if hasattr(r, 'motivo') else r.get('motivo', ''),
            'comentarios': r.comentarios if hasattr(r, 'comentarios') else r.get('comentarios', '')
        })

    detalle.sort(key=lambda x: (x['colaborador'], x['fecha']))
    return detalle
