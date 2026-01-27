"""Utilidades de formateo y normalización de datos."""

def to_int(valor, default=0):
    """Convierte un valor a entero de forma segura."""
    try:
        if valor is None:
            return default
        if isinstance(valor, (int, float)):
            return int(valor)
        valor = str(valor).strip().replace(',', '')
        if valor == '':
            return default
        return int(float(valor))
    except:
        return default


def to_float(valor, default=0.0):
    """Convierte un valor a float de forma segura."""
    try:
        if valor is None:
            return default
        if isinstance(valor, (int, float)):
            return float(valor)
        valor = str(valor).strip().replace(',', '')
        if valor == '':
            return default
        return float(valor)
    except:
        return default


def normalizar_codigo(codigo: str) -> str:
    """
    Normaliza un código de producto.
    Extrae la parte numérica después del guion.
    
    Ejemplos:
        normalizar_codigo("FR-9304") -> "9304"
        normalizar_codigo("INY-1050") -> "1050"
        normalizar_codigo("9304") -> "9304"
    """
    if not codigo:
        return ""
    
    codigo = str(codigo).strip().upper()
    
    # Si contiene guion, tomar la parte después del último guion
    if '-' in codigo:
        return codigo.split('-')[-1].strip()
    
    return codigo


def limpiar_cadena(texto: str) -> str:
    """Limpia una cadena de texto eliminando espacios extras."""
    if not texto:
        return ""
    return ' '.join(str(texto).strip().split())