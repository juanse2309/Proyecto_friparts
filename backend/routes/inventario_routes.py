"""
Rutas de inventario.
Endpoints REST para operaciones de inventario.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventario_service import inventario_service
import logging

logger = logging.getLogger(__name__)

# Crear blueprint
inventario_bp = Blueprint('inventario', __name__)


@inventario_bp.route('/entrada', methods=['POST'])
def registrar_entrada():
    """Registra una entrada de inventario."""
    try:
        datos = request.get_json()
        
        if not datos:
            return jsonify({
                "status": "error",
                "message": "No se recibieron datos"
            }), 400
        
        resultado = inventario_service.registrar_entrada(datos)
        
        status_code = 200 if resultado["status"] == "success" else 400
        return jsonify(resultado), status_code
        
    except Exception as e:
        logger.error(f"Error en entrada: {e}")
        return jsonify({
            "status": "error",
            "message": "Error interno del servidor"
        }), 500


@inventario_bp.route('/salida', methods=['POST'])
def registrar_salida():
    """Registra una salida de inventario."""
    try:
        datos = request.get_json()
        
        if not datos:
            return jsonify({
                "status": "error",
                "message": "No se recibieron datos"
            }), 400
        
        resultado = inventario_service.registrar_salida(datos)
        
        status_code = 200 if resultado["status"] == "success" else 400
        return jsonify(resultado), status_code
        
    except Exception as e:
        logger.error(f"Error en salida: {e}")
        return jsonify({
            "status": "error",
            "message": "Error interno del servidor"
        }), 500