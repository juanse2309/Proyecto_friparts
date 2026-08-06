from flask import Blueprint, jsonify, request
import logging

from backend.services.pnc_service import PncService, PncDatosInvalidosException

pnc_bp = Blueprint('pnc_bp', __name__)
logger = logging.getLogger(__name__)


@pnc_bp.route('/api/pnc', methods=['POST'])
def registrar_pnc():
    """Registra un evento PNC en la tabla db_pnc de SQL y descuenta inventario."""
    data = request.json
    try:
        resultado = PncService.registrar(data)
        return jsonify({
            "success": True,
            "mensaje": resultado['mensaje'],
            "id_pnc": resultado['id_pnc']
        }), 201
    except PncDatosInvalidosException as e:
        return jsonify({"success": False, "error": e.message}), 400
    except Exception as e:
        logger.error(f" ❌ ERROR /api/pnc: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@pnc_bp.route('/api/pnc/criterios', methods=['GET'])
def obtener_criterios_pnc():
    """Catálogo canónico de criterios por área, para que el frontend no hardcodee el suyo."""
    try:
        return jsonify({"success": True, "criterios": PncService.obtener_catalogos_criterios()}), 200
    except Exception as e:
        logger.error(f" ❌ Error en /api/pnc/criterios: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@pnc_bp.route('/api/obtener_pnc', methods=['GET'])
def obtener_pnc():
    """Obtiene todos los registros de PNC consolidados desde SQL."""
    try:
        return jsonify(PncService.obtener_consolidado()), 200
    except Exception as e:
        logger.error(f" ❌ Error en obtener_pnc SQL: {e}")
        return jsonify([]), 200


@pnc_bp.route('/api/resolver_pnc/<id_pnc>', methods=['POST'])
def resolver_pnc(id_pnc):
    """Marca un PNC como resuelto (simulado; no hay columna de estado oficial todavía)."""
    return jsonify({"success": True, "mensaje": PncService.resolver(id_pnc)}), 200
