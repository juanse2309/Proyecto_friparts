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


import re

def normalizar_codigo(codigo: str) -> str:
    """
    Normaliza un código de producto con EXPRESIONES REGULARES (Regex).
    Elimina cualquier prefijo alfanumérico seguido de un guion (MT-, INY-, KIT-, etc.).
    
    Ejemplos:
        normalizar_codigo("FR-9304")   -> "9304"
        normalizar_codigo("KIT-7025")  -> "7025"
        normalizar_codigo("BSL-1050")  -> "1050"
        normalizar_codigo("9304")      -> "9304"
    """
    if not codigo:
        return ""
    
    # 1. Convertir a string, limpiar espacios y pasar a mayúsculas
    codigo_str = str(codigo).strip().upper()
    
    # 2. Regex: Busca letras mayúsculas al inicio seguidas de un guion y las borra
    # Ejemplo: "MT-7004" -> "7004", "BSL-123" -> "123"
    codigo_limpio = re.sub(r'^[A-Z]+-', '', codigo_str)
    
    return codigo_limpio.strip()


def limpiar_cadena(texto: str) -> str:
    """Limpia una cadena de texto eliminando espacios extras."""
    if not texto:
        return ""
    return ' '.join(str(texto).strip().split())