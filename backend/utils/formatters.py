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
    Regla estricta:
    - Si el código YA contiene CUALQUIER prefijo (ej. MT-, CB-, CAR-), se retorna intacto.
    - SOLO si el código es un número puro y huérfano (ej. '7008'), se le inyecta el prefijo_defecto.
    """
    if codigo is None:
        return ""
    cod = str(codigo).strip().upper()
    if not cod:
        return ""
    
    # Si el código es un número puro (ej. "7008")
    if cod.isdigit():
        return f"{prefijo_defecto}{cod}"
        
    # Si ya tiene letras, guiones, o cualquier otro prefijo, lo retornamos exactamente igual
    return cod


def limpiar_cadena(texto: str) -> str:
    """Limpia una cadena de texto eliminando espacios extras."""
    if not texto:
        return ""
    return ' '.join(str(texto).strip().split())


def resolver_operario(payload_name: str) -> str:
    """
    Resuelve el operario responsable aplicando la jerarquía universal:
    1. Si payload_name no está vacío/nulo/undefined, se limpia y se retorna.
    2. Fallback: Se busca en session['user'] (o 'user_name').
    3. Si ambos fallan, retorna 'SISTEMA'.
    """
    from flask import session
    if payload_name is not None:
        val = str(payload_name).strip()
        if val and val.lower() not in ('null', 'undefined', 'none'):
            return val
    
    session_user = session.get('user') or session.get('user_name')
    if session_user is not None:
        val_sess = str(session_user).strip()
        if val_sess and val_sess.lower() not in ('null', 'undefined', 'none'):
            return val_sess
            
    return 'SISTEMA'