from flask import Blueprint, jsonify
from backend.utils.auth_middleware import require_role

inyeccion_bp = Blueprint('inyeccion_bp', __name__)

@inyeccion_bp.route('/api/inyeccion/dashboard_stats', methods=['GET'])
@require_role(['admin', 'inyeccion'])
def get_inyeccion_stats():
    # Placeholder
    return jsonify({"success": True, "message": "Estadísticas de inyección (WIP)"})
