import logging
from flask import Blueprint, send_file, jsonify
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_COMERCIALES
from backend.core.sql_database import rollback_seguro

logger = logging.getLogger(__name__)

cartera_bp = Blueprint('cartera', __name__)


@cartera_bp.route('/api/cartera/exportar-edades', methods=['GET'])
@require_role(ROL_ADMINS + ROL_COMERCIALES)
def exportar_edades_cartera():
    """
    Genera y descarga el reporte de edades de cartera (Corriente, 1-30, 31-60,
    61-90, +90 dias) en Excel. Es informativo: no aplica bloqueos de despacho.
    """
    try:
        from backend.services.cartera_service import CarteraService

        buffer = CarteraService.generar_reporte_edades_excel()

        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='edades_cartera.xlsx'
        )
    except Exception as e:
        rollback_seguro()
        logger.error(f"Error generando reporte de edades de cartera: {e}")
        return jsonify({"success": False, "error": "No fue posible generar el reporte de edades de cartera."}), 500
