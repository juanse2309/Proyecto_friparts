"""
Rutas de dashboard.
"""
from flask import Blueprint, jsonify
from backend.repositories.dashboard_repository import dashboard_repo
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/', methods=['GET'])
def obtener_dashboard():
    """Obtiene estadísticas del dashboard."""
    try:
        estadisticas = dashboard_repo.obtener_estadisticas()
        
        return jsonify({
            'status': 'success',
            'produccion': estadisticas.get('produccion', {}),
            'ventas': estadisticas.get('ventas', {}),
            'stock_critico': estadisticas.get('stock', {}),
            'pnc': estadisticas.get('pnc', {})
        }), 200
        
    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Error obteniendo datos'
        }), 500