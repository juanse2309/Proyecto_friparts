from flask import Blueprint, request, jsonify
import logging

from backend.services.materia_prima_service import MateriaPrimaService

materia_prima_bp = Blueprint('materia_prima_bp', __name__)
logger = logging.getLogger(__name__)


@materia_prima_bp.route('/api/mezcla', methods=['POST'])
def handle_mezcla():
    """Registra una nueva mezcla de material."""
    data = request.get_json() or {}
    try:
        resultado = MateriaPrimaService.registrar_mezcla(data)
        return jsonify({'success': True, 'mensaje': 'Mezcla registrada correctamente en SQL', 'lote': resultado['lote']}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f" Error en /api/mezcla SQL: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@materia_prima_bp.route('/api/molido', methods=['POST'])
def registrar_molido():
    """Registra un nuevo pesaje de molido (Recuperado/Contaminado)."""
    data = request.get_json() or {}
    try:
        MateriaPrimaService.registrar_molido(data)
        return jsonify({'success': True, 'mensaje': 'Molido registrado correctamente en SQL'}), 200
    except Exception as e:
        logger.error(f" Error en /api/molido SQL: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
