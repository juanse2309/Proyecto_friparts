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
import time
import logging
from typing import List, Dict, Optional

import gspread

from backend.core.database import sheets_client
from backend.config.settings import Hojas

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  Caché en memoria para NUEVA_FICHA_MAESTRA
# ──────────────────────────────────────────────
_FICHA_MAESTRA_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": 600,  # 10 minutos
}


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
    
    # Código para reporte (normalizado con ENS- para coherencia en logs)
    resultado["kit"] = f"ENS-{codigo_crudo.replace('ENS-', '')}"
    
    # ALIAS SEGURO: Quedarse únicamente con el primer bloque de texto
    # (Ejemplo: "FR-9380 [KIT]" -> "FR-9380")
    # Utilizamos .split() sin argumentos para eliminar cualquier tipo de espacio en blanco (tabs, espacios múltiples)
    codigo_base = codigo_crudo.split()[0] if codigo_crudo.split() else ""
    
    # Crear lista de variaciones exactas permitidas para evitar discrepancias de prefijo FR, ENS, MT, DE
    variaciones_permitidas = [codigo_base]
    
    # Variante Súper Blanca (Sin espacios ni guiones para comparación agresiva)
    def super_clean(s):
        return str(s).upper().replace(" ", "").replace("-", "").strip()
    
    codigo_base_clean = super_clean(codigo_base)
    
    # ── 1.1 Expandir variaciones según prefijos comunes ────────────────
    # Si tiene FR-, añadimos el número solo
    if codigo_base.startswith("FR-"):
        variaciones_permitidas.append(codigo_base.replace("FR-", ""))
    elif codigo_base.startswith("MT-"):
        variaciones_permitidas.append(codigo_base.replace("MT-", ""))
    elif codigo_base.startswith("DE-"):
        variaciones_permitidas.append(codigo_base.replace("DE-", ""))
    
    # Si es solo el número, añadimos los prefijos posibles
    else:
        # Solo añadimos alias si no es un código ya prefijado (CAR, INT, etc)
        if not any(codigo_base.startswith(p) for p in ["CAR", "INT", "CB"]):
            variaciones_permitidas.append(f"FR-{codigo_base}")
            variaciones_permitidas.append(f"ENS-{codigo_base}")
            variaciones_permitidas.append(f"MT-{codigo_base}")

    # Asegurar que todas las variaciones estén en mayúsculas y limpias
    variaciones_permitidas = list(set([v.upper().strip() for v in variaciones_permitidas]))
    variaciones_super_clean = [super_clean(v) for v in variaciones_permitidas]
    
    logger.debug(f" [BOM Debug] Variaciones permitidas: {variaciones_permitidas}")
    logger.debug(f" [BOM Debug] Variaciones Super-Clean: {variaciones_super_clean}")
    
    logger.debug(f" [BOM Debug] Variaciones permitidas para búsqueda: {variaciones_permitidas}")
    codigo_busqueda = codigo_base # Para logs

    # ── 2. Validar cantidad_armada ────────────────────────────────
    if not isinstance(cantidad_armada, (int, float)) or int(cantidad_armada) <= 0:
        resultado["error"] = f"cantidad_armada debe ser un entero positivo (recibido: {cantidad_armada})"
        logger.error(resultado["error"])
        return resultado
    cantidad_armada = int(cantidad_armada)
    resultado["cantidad_armada"] = cantidad_armada

    # ── 3. Leer NUEVA_FICHA_MAESTRA (con Caché TTL) ──────────────
    try:
        ahora = time.time()
        cache_valido = (
            _FICHA_MAESTRA_CACHE["data"] is not None
            and (ahora - _FICHA_MAESTRA_CACHE["timestamp"]) < _FICHA_MAESTRA_CACHE["ttl"]
        )

        if cache_valido:
            registros = _FICHA_MAESTRA_CACHE["data"]
            logger.debug(f" [BOM Cache] Usando caché de NUEVA_FICHA_MAESTRA ({len(registros)} registros, edad: {int(ahora - _FICHA_MAESTRA_CACHE['timestamp'])}s)")
        else:
            ws = sheets_client.get_worksheet(Hojas.NUEVA_FICHA_MAESTRA)
            if not ws:
                resultado["error"] = "No se pudo abrir la hoja NUEVA_FICHA_MAESTRA."
                resultado["error_tipo"] = "conexion"
                logger.error(resultado["error"])
                return resultado

            registros = sheets_client.get_all_records_seguro(ws)
            # Actualizar caché
            _FICHA_MAESTRA_CACHE["data"] = registros
            _FICHA_MAESTRA_CACHE["timestamp"] = ahora
            logger.info(f" [BOM Cache] Caché de NUEVA_FICHA_MAESTRA actualizado: {len(registros)} registros")

    except gspread.exceptions.APIError as api_err:
        status_code = getattr(api_err, 'response', None)
        status_code = status_code.status_code if status_code else 'desconocido'
        resultado["error"] = f"Límite de peticiones a Google superado (HTTP {status_code}). Intente en 1 minuto."
        resultado["error_tipo"] = "quota"
        logger.error(f" [BOM] Error de cuota Google Sheets: {api_err}")
        # Si hay caché viejo, usarlo como fallback de emergencia
        if _FICHA_MAESTRA_CACHE["data"] is not None:
            registros = _FICHA_MAESTRA_CACHE["data"]
            logger.warning(f" [BOM Cache] Usando caché EXPIRADO como fallback de emergencia ({len(registros)} registros)")
            resultado.pop("error", None)
            resultado.pop("error_tipo", None)
        else:
            return resultado
    except Exception as e:
        resultado["error"] = f"Error al leer NUEVA_FICHA_MAESTRA: {e}"
        resultado["error_tipo"] = "conexion"
        logger.error(resultado["error"])
        return resultado

    # ── 4. Filtrar componentes del kit ────────────────────────────
    componentes_ficha = []
    
    logger.debug(f"Iniciando filtrado en NUEVA_FICHA_MAESTRA para: '{codigo_busqueda}'")
    
    for idx, fila in enumerate(registros):
        # Intentar con "Producto Final" (columna real) y fallback a "Producto"
        producto_raw = str(fila.get("Producto Final", fila.get("Producto", ""))).strip()
        if not producto_raw:
            continue
            
        producto_upper = producto_raw.upper()
        
        # Comparación Nivel 1: Primer bloque (Token matching)
        # (Ejemplo: "FR-9380 BUJE..." -> "FR-9380")
        codigo_celda = producto_upper.split()[0] if producto_upper.split() else ""
        
        # Comparación Nivel 2: Super Clean (Comparación agresiva sin distractores)
        codigo_celda_clean = super_clean(codigo_celda)
        
        # LOG DE AUDITORÍA (Solo para depuración de casos difíciles como MT)
        if "MT" in producto_upper or "7011" in producto_upper:
             logger.debug(f" [BOM Trial] Fila {idx+2}: Celda='{codigo_celda}', Clean='{codigo_celda_clean}' vs Target='{codigo_base_clean}'")

        # Coincidencia: Ya sea por token exacto o por versión super-limpia
        match_encontrado = (codigo_celda in variaciones_permitidas) or (codigo_celda_clean in variaciones_super_clean)
        
        if not match_encontrado:
            continue
            
        logger.info(f" [BOM Match] ¡Coincidencia encontrada para '{codigo_kit}'! Fila {idx+2}: '{producto_raw}'")

        subproducto = str(fila.get("SubProducto", "")).strip()
        cantidad_bom = _parsear_cantidad(fila.get("Cantidad", 0))

        # Ignorar filas vacías, de totales o donde el subproducto sea igual al producto (buje base)
        if not subproducto or "total" in subproducto.lower():
            continue
            
        # Evitar auto-referencia si el subproducto es el mismo que el producto buscado (buje base)
        # Aplicamos la misma lógica de primer bloque para el subproducto
        subpro_base = subproducto.upper().split(' ')[0]
        if subpro_base == codigo_busqueda:
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
