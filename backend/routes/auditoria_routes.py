from flask import Blueprint
import logging

from backend.core.responses import api_success, api_error
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_JEFES
from backend.services.auditoria_service import AuditoriaService

auditoria_bp = Blueprint('auditoria', __name__)
logger = logging.getLogger(__name__)

ROLES_AUDITORIA = ROL_ADMINS + ROL_JEFES


@auditoria_bp.route('/api/auditoria/conciliacion-ops', methods=['GET'])
@require_role(ROLES_AUDITORIA)
def conciliacion_ops():
    """Conciliación OP World Office vs. reportes de planta (Inyección/Pulido)."""
    try:
        resultado = AuditoriaService.obtener_conciliacion_ops()
        return api_success(data=resultado)
    except Exception as e:
        logger.error(f"❌ Error en conciliación de OP: {e}")
        return api_error("Error interno consultando la conciliación de OP", status_code=500)
