"""
Servicio de Explosión de Materiales (BOM – Bill of Materials) SQL-Native.

Calcula los descuentos de inventario para un ensamble/kit a partir
de la ficha técnica definida en la tabla nueva_ficha_maestra de PostgreSQL.
"""
import re
import logging
from typing import List, Dict, Optional
from backend.models.sql_models import FichaMaestra
from backend.core.sql_database import db

logger = logging.getLogger(__name__)

from backend.utils.formatters import normalizar_codigo

# ──────────────────────────────────────────────
#  Traducción de código de componente
# ──────────────────────────────────────────────
def traducir_codigo_componente(codigo_raw: str) -> str:
    """
    Aplica la regla de traducción de códigos de la ficha técnica
    al código real de inventario (SQL-Native).
    """
    if not codigo_raw: return ""
    
    # 1. Normalizar usando la función inteligente
    codigo_norm = normalizar_codigo(codigo_raw)
    
    # 2. Casos especiales legacy (opcional, pero ayuda)
    if str(codigo_raw).upper().startswith("C-"):
        numero = codigo_raw[2:].strip()
        return f"CAR{numero}"

    return codigo_norm

# ──────────────────────────────────────────────
#  Función principal: calcular_descuentos_ensamble (SQL)
# ──────────────────────────────────────────────
def calcular_descuentos_ensamble(
    codigo_kit: str,
    cantidad_armada: int
) -> Dict:
    """
    Explota la BOM de un ensamble (kit) usando PostgreSQL.
    Cruce inteligente via normalizar_codigo().
    """
    resultado = {
        "success": False,
        "kit": None,
        "cantidad_armada": cantidad_armada,
        "componentes": [],
        "error": None,
    }

    if not codigo_kit:
        resultado["error"] = "Código de kit no proporcionado"
        return resultado

    # 1. Normalizar código del kit
    codigo_norm = normalizar_codigo(codigo_kit)
    resultado["kit"] = codigo_norm
    
    try:
        # 2. Consultar Ficha Maestra en SQL — Búsqueda ESTRICTA (no LIKE global)
        # Estrategia: coincidencia exacta → FR-código → filtrar sub-recetas (CB...)
        codigo_limpio = re.sub(r'^FR-?', '', str(codigo_norm), flags=re.IGNORECASE).strip()
        
        # Intento 1: Exacto con prefijo FR- (ej. "FR-9380", "FR-9380 ")
        query = FichaMaestra.query.filter(
            FichaMaestra.producto.ilike(f"FR-{codigo_limpio}%")
        ).all()
        
        # Intento 2: Exacto sin prefijo (ej. "9380")
        if not query:
            query = FichaMaestra.query.filter(
                FichaMaestra.producto == codigo_limpio
            ).all()
        
        # Intento 3: Coincidencia exacta con código normalizado original
        if not query:
            query = FichaMaestra.query.filter(
                (FichaMaestra.producto == codigo_kit) |
                (FichaMaestra.producto == codigo_norm)
            ).all()
        
        if not query:
            logger.warning(f" [BOM SQL] No se encontró ficha estricta para {codigo_kit}")
            resultado["error"] = f"Ficha técnica no encontrada para {codigo_kit}"
            return resultado
        
        # Filtrar sub-recetas: excluir filas donde el PRODUCTO empiece con CB
        query = [row for row in query if not str(row.producto).strip().upper().startswith('CB')]
        if not query:
            resultado["error"] = f"Solo se encontraron sub-recetas (CB) para {codigo_kit}, no un ensamble"
            return resultado

        componentes_ficha = []
        for row in query:
            subpro_raw = str(row.subproducto).strip()
            
            # Tarea 1: Normalización de Códigos para el Cruce (Extraer primera palabra)
            codigo_limpio_receta = subpro_raw.split(' ')[0]
            subpro_norm = normalizar_codigo(codigo_limpio_receta)
            
            # Evitar auto-referencia
            if subpro_norm == codigo_norm:
                continue
                
            qty_por_kit = float(row.cantidad or 0)
            if qty_por_kit <= 0: continue

            componentes_ficha.append({
                "codigo_ficha": subpro_raw,
                "codigo_inventario": subpro_norm, # Este debe cruzar con Producto.codigo_sistema
                "cantidad_por_kit": qty_por_kit,
                "cantidad_total_descontar": qty_por_kit * cantidad_armada
            })

        if not componentes_ficha:
            resultado["error"] = f"La ficha de {codigo_kit} no tiene componentes válidos"
            return resultado

        resultado["success"] = True
        resultado["componentes"] = componentes_ficha
        logger.info(f" [BOM SQL] Explosión exitosa para {codigo_kit}: {len(componentes_ficha)} items")
        return resultado

    except Exception as e:
        logger.error(f" [BOM SQL] Error crítico: {e}")
        resultado["error"] = str(e)
        return resultado
