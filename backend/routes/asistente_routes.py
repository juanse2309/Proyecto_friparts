"""
Rutas del Asistente de Dashboard (NL -> consulta de datos reales).
"""
from flask import Blueprint, jsonify, request, session
import logging

from backend.core.sql_database import rollback_seguro
from backend.core.tenant import get_tenant_from_request
from backend.services.asistente_service import AsistenteService
from backend.utils.auth_middleware import require_role, obtener_identidad_segura, ROL_ADMINS, ROL_COMERCIALES, ROL_JEFES

logger = logging.getLogger(__name__)

asistente_bp = Blueprint('asistente_bp', __name__)


@asistente_bp.route('/asistente/preguntar', methods=['POST'])
@require_role(ROL_ADMINS + ROL_COMERCIALES + ROL_JEFES)
def preguntar():
    """Recibe una pregunta en lenguaje natural y delega toda la logica a AsistenteService."""
    try:
        body = request.get_json(silent=True) or {}
        pregunta = str(body.get('pregunta', '')).strip()
        if not pregunta:
            return jsonify({'success': False, 'error': "Falta el parametro 'pregunta'."}), 400

        contexto_dashboard = {'desde': body.get('desde'), 'hasta': body.get('hasta')}

        user, role = obtener_identidad_segura(request)
        user_id = session.get('user_id') or session.get('usuario_id') or 0
        tenant = get_tenant_from_request()

        resultado = AsistenteService.responder(pregunta, contexto_dashboard, user, user_id, role, tenant)
        return jsonify(resultado), 200 if resultado.get('success') else 400

    except Exception as e:
        rollback_seguro()
        logger.error(f"Error en /api/dashboard/asistente/preguntar: {e}")
        return jsonify({'success': False, 'error': 'No fue posible procesar la pregunta.'}), 500
