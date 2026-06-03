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
    Normaliza un código de producto SIN prefijo.
    Uso: consultas contra db_programacion y db_distribucion_op_pedidos
    donde los códigos se almacenan como '9890' (sin FR-).
    """
    if codigo is None:
        return ""
    cod = str(codigo).strip().upper()
    cod = cod.replace("FR-", "")
    return cod.strip()


def con_prefijo_fr(codigo: str) -> str:
    """
    Garantiza que el código tenga el prefijo 'FR-'.
    Uso: campos que apuntan a db_productos (maestro con prefijo), db_pulido.codigo
    y db_bujes_revueltos.id_codigo. Asegura coherencia con el inventario.
    """
    if codigo is None:
        return ""
    cod = str(codigo).strip().upper()
    if not cod.startswith("FR-"):
        cod = f"FR-{cod}"
    return cod


def limpiar_cadena(texto: str) -> str:
    """Limpia una cadena de texto eliminando espacios extras."""
    if not texto:
        return ""
    return ' '.join(str(texto).strip().split())