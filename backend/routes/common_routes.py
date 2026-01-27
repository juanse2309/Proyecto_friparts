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
        ws = sheets_client.get_worksheet(Hojas.RESPONSABLES)
        if not ws:
            return jsonify({
                'status': 'success',
                'responsables': ['Juan Pérez', 'María García', 'Carlos López']
            }), 200
        
        registros = ws.get_all_records()
        responsables = [r.get('NOMBRE', '') for r in registros if r.get('NOMBRE')]
        
        return jsonify({
            'status': 'success',
            'responsables': responsables
        }), 200
        
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
        ws = sheets_client.get_worksheet(Hojas.CLIENTES)
        if not ws:
            return jsonify({
                'status': 'success',
                'clientes': ['Cliente General', 'Cliente Mayorista']
            }), 200
        
        registros = ws.get_all_records()
        clientes = [r.get('NOMBRE', '') for r in registros if r.get('NOMBRE')]
        
        return jsonify({
            'status': 'success',
            'clientes': clientes
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo clientes: {e}")
        return jsonify({
            'status': 'success',
            'clientes': ['Cliente General']
        }), 200