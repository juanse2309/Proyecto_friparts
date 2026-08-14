from flask import Blueprint, request, jsonify
import logging

from backend.services.materia_prima_service import MateriaPrimaService
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_JEFES, ROL_OPERARIOS

materia_prima_bp = Blueprint('materia_prima_bp', __name__)
logger = logging.getLogger(__name__)

ROLES_PLANTA = ROL_ADMINS + ROL_JEFES + ROL_OPERARIOS


@materia_prima_bp.route('/api/mezcla', methods=['POST'])
@require_role(ROLES_PLANTA)
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
@require_role(ROLES_PLANTA)
def registrar_molido():
    """Registra un nuevo pesaje de molido (Recuperado/Contaminado)."""
    data = request.get_json() or {}
    try:
        MateriaPrimaService.registrar_molido(data)
        return jsonify({'success': True, 'mensaje': 'Molido registrado correctamente en SQL'}), 200
    except Exception as e:
        logger.error(f" Error en /api/molido SQL: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
