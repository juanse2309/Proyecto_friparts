"""
Helpers numéricos puros, compartidos por los repositorios SQL (BaseRepository,
ProductoRepository, VentasRepository, DashboardRepository). Sin dependencias
de Flask/SQLAlchemy/DB — funciones de conversión aisladas y reutilizables.
"""


def _num(value):
    """Convierte Decimal/None a float para JSON-serializable."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_float(val):
    """Convierte cualquier valor (str, Decimal, None, formato WO) a float sin lanzar excepciones."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        from decimal import Decimal
        if isinstance(val, Decimal):
            return float(val)
        # Limpiar formatos WO: "$1.500,00" → "1500.00"
        cleaned = str(val).replace('$', '').replace(' ', '').strip()
        if not cleaned or cleaned.lower() in ('none', 'nan', 'n/a', '-'):
            return 0.0
        # Formato europeo con punto como separador de miles y coma decimal
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        return float(cleaned)
    except Exception:
        return 0.0
