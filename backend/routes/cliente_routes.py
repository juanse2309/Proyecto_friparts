from flask import Blueprint, jsonify
import logging

from backend.repositories.cliente_repository import ClienteRepository
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_COMERCIALES, ROL_JEFES

cliente_bp = Blueprint('cliente_bp', __name__)
logger = logging.getLogger(__name__)


@cliente_bp.route('/api/obtener_clientes', methods=['GET'])
@require_role(ROL_ADMINS + ROL_COMERCIALES + ROL_JEFES)
def obtener_clientes():
    """Retorna lista de clientes desde db_clientes (SQL-Native)."""
    try:
        return jsonify(ClienteRepository.get_all()), 200
    except Exception as e:
        logger.error(f"❌ Error obteniendo clientes SQL: {e}")
        return jsonify([]), 200
