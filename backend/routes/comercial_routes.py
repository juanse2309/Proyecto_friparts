import logging
from flask import Blueprint, jsonify, request, render_template, session
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_COMERCIALES, obtener_identidad_segura
from backend.services.comercial_service import ComercialHistoricoService

logger = logging.getLogger(__name__)

comercial_bp = Blueprint('comercial', __name__)

ROLES_PERMITIDOS_COMERCIAL = ROL_ADMINS + ROL_COMERCIALES + ['GERENCIA']

@comercial_bp.route('/comercial/historico', methods=['GET'])
@require_role(ROLES_PERMITIDOS_COMERCIAL)
def render_comercial_historico():
    """Rinde la plantilla HTML independiente para la Analítica Comercial Histórica."""
    return render_template('comercial_historico.html')

@comercial_bp.route('/api/comercial/historico', methods=['GET'])
@require_role(ROLES_PERMITIDOS_COMERCIAL)
def api_obtener_comercial_historico():
    """
    Endpoint dedicado para la extracción analítica de ventas históricas.
    Retorna agregaciones pre-calculadas en PostgreSQL con aislamiento por rol.
    """
    try:
        user_name, user_role = obtener_identidad_segura(request)
        user_id = session.get('user_id') or session.get('usuario_id') or 0
        
        start_year = request.args.get('start_year', default=2024, type=int)
        end_year = request.args.get('end_year', default=2026, type=int)

        data = ComercialHistoricoService.obtener_analitica_historica(
            user_id=user_id,
            username=user_name,
            user_role=user_role,
            start_year=start_year,
            end_year=end_year
        )

        return jsonify(data), 200

    except Exception as e:
        logger.error(f"[COMERCIAL_ROUTES] Error en /api/comercial/historico: {e}")
        return jsonify({'success': False, 'error': 'Error interno extrayendo datos analíticos', 'detalle': str(e)}), 500
