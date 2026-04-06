"""
Servicio de Explosión de Materiales (BOM – Bill of Materials).

Calcula los descuentos de inventario para un ensamble/kit a partir
de la ficha técnica definida en NUEVA_FICHA_MAESTRA.

Reglas de traducción de códigos:
  ┌─────────────────┬──────────────────────┐
  │ SubProducto      │ Código real inventario │
  ├─────────────────┼──────────────────────┤
  │ C-7025…         │ CAR7025              │
  │ I-7025…         │ INT-7025             │
  │ 7025… (número)  │ 7025                 │
  └─────────────────┴──────────────────────┘
"""
import re
import logging
from typing import List, Dict, Optional

from backend.core.database import sheets_client
from backend.config.settings import Hojas

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  Traducción de código de componente
# ──────────────────────────────────────────────
def traducir_codigo_componente(codigo_raw: str) -> str:
    """
    Aplica la regla de traducción de códigos de la ficha técnica
    al código real de inventario.

    Args:
        codigo_raw: valor tal como aparece en la columna SubProducto
                    de NUEVA_FICHA_MAESTRA (ej. "C-7025", "I-7025", "7025").

    Returns:
        Código traducido listo para buscar en inventario.

    Ejemplos:
        >>> traducir_codigo_componente("C-7025")
        'CAR7025'
        >>> traducir_codigo_componente("I-7025")
        'INT-7025'
        >>> traducir_codigo_componente("7025")
        '7025'
    """
    codigo = codigo_raw.strip()

    if codigo.upper().startswith("C-"):
        # C-7025  →  CAR7025  (se elimina el guión)
        numero = codigo[2:].strip()
        return f"CAR{numero}"

    if codigo.upper().startswith("I-"):
        # I-7025  →  INT-7025
        numero = codigo[2:].strip()
        return f"INT-{numero}"
    # 0. Red de seguridad: si viene con "/" o "|", tomar la primera parte
    if "/" in codigo:
        codigo = codigo.split("/")[0].strip()
    elif "|" in codigo:
        codigo = codigo.split("|")[0].strip()

    # 1. REGLA UNIVERSAL: Quedarse solo con el primer bloque de texto (ante nombres descriptivos largos)
    # Ejemplo: "FR-9303 BUJE PARA ENSAMBLE" -> "FR-9303"
    codigo = codigo.strip().split(' ')[0]

    # Si empieza por dígito, es un buje directo
    if codigo and codigo[0].isdigit():
        return codigo

    # REGLA DE LIMPIEZA ESPECÍFICA: Si el código empieza por CAR, INT o CB
    codigo_upper = codigo.upper()
    if codigo_upper.startswith(("CAR", "INT", "CB")):
        # Recortar en el primer guion (pero no espacio, ya se encargó la regla universal)
        partes = re.split(r'[-]', codigo)
        if partes and partes[0]:
            # EXCEPCIÓN: Si es "INT-", necesitamos el segundo bloque para que sea "INT-7025"
            if codigo_upper.startswith("INT-") and len(partes) > 1:
                return f"INT-{partes[1].strip().upper()}"
            return partes[0].strip().upper()

    # Cualquier otro caso (incluyendo FR-XXXX, CB-XXXX, etc.): devolver tal cual
    return codigo.upper().strip()



# ──────────────────────────────────────────────
#  Helper: parsear cantidad de la ficha
# ──────────────────────────────────────────────
def _parsear_cantidad(valor) -> int:
    """Convierte un valor de la hoja a entero, tolerando strings y vacíos."""
    if isinstance(valor, (int, float)):
        return int(valor)
    if isinstance(valor, str):
        limpio = valor.strip().replace(",", "").replace(".", "")
        if limpio.isdigit():
            return int(limpio)
    return 0


# ──────────────────────────────────────────────
#  Función principal: calcular_descuentos_ensamble
# ──────────────────────────────────────────────
def calcular_descuentos_ensamble(
    codigo_kit: str,
    cantidad_armada: int
) -> Dict:
    """
    Explota la BOM de un ensamble (kit) y calcula las cantidades
    a descontar de inventario por cada componente.

    Args:
        codigo_kit:      Código del kit.  Se acepta con o sin prefijo ENS-
                         (ej. "ENS-7025" o "7025"; se normaliza a "ENS-7025").
        cantidad_armada: Número de kits que el operario reportó como armados.

    Returns:
        dict con la estructura:
        {
            "success": True/False,
            "kit": "ENS-7025",
            "cantidad_armada": 10,
            "componentes": [
                {
                    "codigo_ficha": "C-7025",       # como aparece en la ficha
                    "codigo_inventario": "CAR7025",  # traducido
                    "cantidad_por_kit": 2,
                    "cantidad_total_descontar": 20   # cantidad_por_kit × cantidad_armada
                },
                ...
            ],
            "error": None
        }

    Raises:
        No lanza excepciones; los errores se informan dentro del dict retornado.
    """
    resultado = {
        "success": False,
        "kit": None,
        "cantidad_armada": cantidad_armada,
        "componentes": [],
        "error": None,
    }

    # ── 1. Normalizar código del kit para búsqueda ────────────────
    codigo_crudo = str(codigo_kit).strip().upper()
    
    # Código para reporte (mantiene ENS-)
    resultado["kit"] = f"ENS-{codigo_crudo.replace('ENS-', '')}"
    
    # Código limpio para búsqueda (quitamos FR- y ENS- para máxima flexibilidad)
    codigo_busqueda = codigo_crudo.replace("ENS-", "").replace("FR-", "").strip()

    # ── 2. Validar cantidad_armada ────────────────────────────────
    if not isinstance(cantidad_armada, (int, float)) or int(cantidad_armada) <= 0:
        resultado["error"] = f"cantidad_armada debe ser un entero positivo (recibido: {cantidad_armada})"
        logger.error(resultado["error"])
        return resultado
    cantidad_armada = int(cantidad_armada)
    resultado["cantidad_armada"] = cantidad_armada

    # ── 3. Leer NUEVA_FICHA_MAESTRA ───────────────────────────────
    try:
        ws = sheets_client.get_worksheet(Hojas.NUEVA_FICHA_MAESTRA)
        if not ws:
            resultado["error"] = "No se pudo abrir la hoja NUEVA_FICHA_MAESTRA."
            logger.error(resultado["error"])
            return resultado

        registros = sheets_client.get_all_records_seguro(ws)
    except Exception as e:
        resultado["error"] = f"Error al leer NUEVA_FICHA_MAESTRA: {e}"
        logger.error(resultado["error"])
        return resultado

    # ── 4. Filtrar componentes del kit ────────────────────────────
    componentes_ficha = []
    
    logger.debug(f"Iniciando filtrado en NUEVA_FICHA_MAESTRA para: '{codigo_busqueda}'")
    
    for idx, fila in enumerate(registros):
        producto_raw = str(fila.get("Producto", "")).strip()
        if not producto_raw:
            continue
            
        producto_upper = producto_raw.upper()
        
        # Limpiamos el valor de la celda (ej. "FR-9380 [KIT]" -> "9380 [KIT]")
        celda_limpia = producto_upper.replace("ENS-", "").replace("FR-", "").strip()
        
        # Filtrado estricto: El primer token de la celda debe coincidir exactamente con el código buscado
        # Esto evita que "FR-9380" coincida con una descripción de tubo que mencione "9380" en la mitad.
        celda_tokens = celda_limpia.split()
        if not celda_tokens or celda_tokens[0] != codigo_busqueda:
            continue

        subproducto = str(fila.get("SubProducto", "")).strip()
        cantidad_bom = _parsear_cantidad(fila.get("Cantidad", 0))

        # Ignorar filas vacías, de totales o donde el subproducto sea igual al producto (buje base)
        if not subproducto or "total" in subproducto.lower():
            continue
            
        # Evitar auto-referencia si el subproducto es el mismo que el producto buscado
        subpro_limpio = subproducto.upper().replace("ENS-", "").replace("FR-", "").strip()
        if subpro_limpio == codigo_busqueda:
            logger.debug(f"Fila {idx+2}: Ignorando auto-referencia '{subproducto}'")
            continue

        logger.debug(f"Fila {idx+2}: Match encontrado -> {subproducto} (qty: {cantidad_bom})")
        
        componentes_ficha.append({
            "codigo_ficha": subproducto,
            "cantidad_por_kit": cantidad_bom,
        })

    if not componentes_ficha:
        resultado["error"] = (
            f"No se encontraron componentes para el kit '{codigo_kit}' "
            f"en NUEVA_FICHA_MAESTRA."
        )
        logger.warning(resultado["error"])
        return resultado

    # ── 5. Traducir códigos y calcular cantidades ─────────────────
    for comp in componentes_ficha:
        codigo_ficha_raw = comp["codigo_ficha"]
        
        # Detectar componentes alternativos separados por "/"
        if "/" in codigo_ficha_raw:
            alternativas_raw = [a.strip() for a in codigo_ficha_raw.split("/") if a.strip()]
            opciones = [traducir_codigo_componente(a) for a in alternativas_raw]
            
            # El primero es el principal (default)
            comp["codigo_inventario"] = opciones[0]
            comp["opciones_alternativas"] = opciones
            comp["tiene_alternativas"] = True
            logger.info(f"  🔀 Componente alternativo detectado: {opciones}")
        else:
            comp["codigo_inventario"] = traducir_codigo_componente(codigo_ficha_raw)
            comp["opciones_alternativas"] = None
            comp["tiene_alternativas"] = False
        
        comp["cantidad_total_descontar"] = comp["cantidad_por_kit"] * cantidad_armada

    resultado["success"] = True
    resultado["componentes"] = componentes_ficha

    logger.info(
        f"BOM explosionado: kit={codigo_kit}, armados={cantidad_armada}, "
        f"componentes={len(componentes_ficha)}"
    )
    return resultado
