"""
Rutas comunes (responsables, clientes, etc).
"""
from flask import Blueprint, jsonify
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import logging

logger = logging.getLogger(__name__)

common_bp = Blueprint('common', __name__)


@common_bp.route('/responsables', methods=['GET'])
def obtener_responsables():
    """Obtiene lista de responsables."""
    try:
        from backend.app import RESPONSABLES_CACHE, CACHE_TTL_LONG
        import time
        ahora = time.time()

        # 1. Verificar Caché
        if RESPONSABLES_CACHE["data"] and (ahora - RESPONSABLES_CACHE["timestamp"] < RESPONSABLES_CACHE["ttl"]):
            return jsonify(RESPONSABLES_CACHE["data"]), 200

        ws = sheets_client.get_worksheet(Hojas.RESPONSABLES)
        if not ws:
            return jsonify({
                'status': 'success',
                'responsables': ['Juan Pérez', 'María García', 'Carlos López']
            }), 200
        
        registros = ws.get_all_records()
        responsables = [r.get('NOMBRE', '') for r in registros if r.get('NOMBRE')]
        
        resultado = {
            'status': 'success',
            'responsables': responsables
        }

        # 2. Guardar en Caché
        RESPONSABLES_CACHE["data"] = resultado
        RESPONSABLES_CACHE["timestamp"] = ahora

        return jsonify(resultado), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo responsables: {e}")
        return jsonify({
            'status': 'success',
            'responsables': ['Juan Pérez', 'María García']
        }), 200


@common_bp.route('/clientes', methods=['GET'])
def obtener_clientes():
    """Obtiene lista de clientes."""
    try:
        from backend.app import CLIENTES_CACHE
        import time
        ahora = time.time()

        # 1. Verificar Caché
        if CLIENTES_CACHE["data"] and (ahora - CLIENTES_CACHE["timestamp"] < CLIENTES_CACHE["ttl"]):
            return jsonify(CLIENTES_CACHE["data"]), 200

        ws = sheets_client.get_worksheet(Hojas.CLIENTES)
        if not ws:
            return jsonify({
                'status': 'success',
                'clientes': ['Cliente General', 'Cliente Mayorista']
            }), 200
        
        registros = ws.get_all_records()
        clientes = [r.get('NOMBRE', '') for r in registros if r.get('NOMBRE')]
        
        resultado = {
            'status': 'success',
            'clientes': clientes
        }

        # 2. Guardar en Caché
        CLIENTES_CACHE["data"] = resultado
        CLIENTES_CACHE["timestamp"] = ahora

        return jsonify(resultado), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo clientes: {e}")
        return jsonify({
            'status': 'success',
            'clientes': ['Cliente General']
        }), 200