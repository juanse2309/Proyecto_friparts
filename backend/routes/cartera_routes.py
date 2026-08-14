import logging
from flask import Blueprint, send_file, jsonify
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_COMERCIALES
from backend.core.sql_database import rollback_seguro

logger = logging.getLogger(__name__)

cartera_bp = Blueprint('cartera', __name__)


@cartera_bp.route('/api/cartera/cliente/<identificacion>', methods=['GET'])
@require_role(ROL_ADMINS + ROL_COMERCIALES)
def obtener_cartera_cliente(identificacion):
    """
    Detalle de facturas con saldo pendiente de un cliente puntual (por NIT).
    Alimenta el modal de Gestion Pedidos. Antes sin restriccion de rol -- por
    NIT expone facturas y saldos de terceros, se protege igual que el resto
    del blueprint (ROL_ADMINS + ROL_COMERCIALES).
    """
    try:
        from backend.services.cartera_service import CarteraService

        facturas = CarteraService.obtener_cartera_cliente(identificacion)
        return jsonify({"success": True, "facturas": facturas}), 200
    except Exception as e:
        rollback_seguro()
        logger.error(f"Error obteniendo cartera del cliente {identificacion}: {e}")
        return jsonify({"success": False, "error": "No fue posible obtener la cartera del cliente."}), 500


@cartera_bp.route('/api/cartera/factura/<numero_documento>', methods=['GET'])
@require_role(ROL_ADMINS + ROL_COMERCIALES)
def obtener_detalle_factura(numero_documento):
    """
    Detalle de una factura/documento World Office puntual (encabezado, items
    y totales) para la vista de consulta tipo WO por número de factura.
    """
    try:
        from backend.services.cartera_service import CarteraService

        detalle = CarteraService.obtener_detalle_factura(numero_documento)
        if not detalle:
            return jsonify({"success": False, "error": "Factura no encontrada o no sincronizada."}), 404

        return jsonify({"success": True, **detalle}), 200
    except Exception as e:
        rollback_seguro()
        logger.error(f"Error obteniendo detalle de factura {numero_documento}: {e}")
        return jsonify({"success": False, "error": "No fue posible obtener el detalle de la factura."}), 500


@cartera_bp.route('/api/cartera/listar', methods=['GET'])
@require_role(ROL_ADMINS + ROL_COMERCIALES)
def listar_cartera_agrupada():
    """Listado completo de cartera agrupado por cliente, con edades 30-60-90."""
    try:
        from backend.services.cartera_service import CarteraService

        clientes = CarteraService.obtener_cartera_agrupada()
        return jsonify({"success": True, "clientes": clientes}), 200
    except Exception as e:
        rollback_seguro()
        logger.error(f"Error listando cartera agrupada: {e}")
        return jsonify({"success": False, "error": "No fue posible obtener el listado de cartera."}), 500


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
