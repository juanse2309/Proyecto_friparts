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
    Quita cualquier prefijo (FR-, MT-, CAR-, etc.) y devuelve la parte restante.
    Uso: consultas contra db_programacion y db_distribucion_op_pedidos
    donde los códigos se almacenan como '9890'.
    """
    if codigo is None:
        return ""
    cod = str(codigo).strip().upper()
    return re.sub(r'^[A-Z]+-', '', cod).strip()


def preservar_o_normalizar_prefijo(codigo: str, prefijo_defecto: str = "FR-") -> str:
    """
    Garantiza que el código tenga un prefijo válido para db_productos.
    Si el código ya tiene un prefijo (ej. MT-, CAR-), lo respeta intacto.
    Si viene numérico limpio (ej. 9890), le inyecta el prefijo_defecto.
    """
    if codigo is None:
        return ""
    cod = str(codigo).strip().upper()
    if not cod:
        return ""
    
    # Si ya comienza con letras seguidas de guion (ej. MT-7008, FR-9890)
    if re.match(r'^[A-Z]+-', cod):
        return cod
        
    # Si es un número sin prefijo, aplicamos el default
    return f"{prefijo_defecto}{cod}"


def limpiar_cadena(texto: str) -> str:
    """Limpia una cadena de texto eliminando espacios extras."""
    if not texto:
        return ""
    return ' '.join(str(texto).strip().split())