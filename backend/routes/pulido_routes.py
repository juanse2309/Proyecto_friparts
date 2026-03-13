from flask import Blueprint, jsonify
from backend.utils.auth_middleware import require_role

pulido_bp = Blueprint('pulido_bp', __name__)

@pulido_bp.route('/api/pulido/dashboard_stats', methods=['GET'])
@require_role(['admin', 'pulido'])
def get_pulido_stats():
    # Placeholder
    return jsonify({"success": True, "message": "Estadísticas de pulido (WIP)"})
