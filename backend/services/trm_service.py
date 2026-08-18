# -*- coding: utf-8 -*-
"""
Servicio de consulta de TRM (Tasa Representativa del Mercado) oficial,
publicada por la Superintendencia Financiera de Colombia vía datos.gov.co.

Usada por el módulo de pedidos para convertir a pesos los precios que un
vendedor ingresa en dólares en pedidos de exportación -- ver
backend/routes/pedidos_routes.py (endpoint /api/pedidos/trm_actual) y
frontend/static/js/modules/pedidos.js (botón "Consultar TRM").
"""
import time
import logging
import requests

logger = logging.getLogger(__name__)

TRM_API_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"
CACHE_TTL_SEGUNDOS = 4 * 3600  # La TRM oficial solo cambia una vez al dia


class TrmNoDisponibleError(Exception):
    pass


_cache = {"valor": None, "vigencia_desde": None, "vigencia_hasta": None, "timestamp": 0}


def obtener_trm_oficial() -> dict:
    """
    Retorna {"trm": float, "vigencia_desde": str, "vigencia_hasta": str}
    con la TRM oficial vigente.

    Cachea en memoria del proceso por CACHE_TTL_SEGUNDOS para no golpear la
    API pública en cada click del botón "Consultar TRM" -- la TRM oficial
    solo cambia una vez al día. Si la API falla y hay un valor cacheado
    (aunque esté vencido), se retorna ese valor en vez de romper el flujo de
    creación de pedidos.
    """
    ahora = time.time()
    if _cache["valor"] is not None and (ahora - _cache["timestamp"]) < CACHE_TTL_SEGUNDOS:
        return {
            "trm": _cache["valor"],
            "vigencia_desde": _cache["vigencia_desde"],
            "vigencia_hasta": _cache["vigencia_hasta"],
        }

    try:
        resp = requests.get(
            TRM_API_URL,
            params={"$order": "vigenciadesde DESC", "$limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        datos = resp.json()
        if not datos:
            raise TrmNoDisponibleError("La API de TRM oficial no devolvió datos")

        valor = float(datos[0]["valor"])
        vigencia_desde = datos[0].get("vigenciadesde")
        vigencia_hasta = datos[0].get("vigenciahasta")

        _cache.update({
            "valor": valor,
            "vigencia_desde": vigencia_desde,
            "vigencia_hasta": vigencia_hasta,
            "timestamp": ahora,
        })
        return {"trm": valor, "vigencia_desde": vigencia_desde, "vigencia_hasta": vigencia_hasta}

    except (requests.exceptions.RequestException, KeyError, ValueError, IndexError) as e:
        logger.error(f"[trm_service] Error consultando TRM oficial: {e}")
        if _cache["valor"] is not None:
            logger.warning("[trm_service] Usando ultimo valor de TRM cacheado por fallo de red.")
            return {
                "trm": _cache["valor"],
                "vigencia_desde": _cache["vigencia_desde"],
                "vigencia_hasta": _cache["vigencia_hasta"],
            }
        raise TrmNoDisponibleError(f"No fue posible consultar la TRM oficial: {e}")
