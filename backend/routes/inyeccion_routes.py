import uuid
import logging
from flask import Blueprint, jsonify, request
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_JEFES, _obtener_usuario_activo
from backend.services.audit_service import OwnershipMismatchException, ValidadorRequeridoException, TurnoInvalidoException
from backend.services.inyeccion_service import InyeccionService, LoteInyeccionNoEncontradoException, ProgramacionNoEncontradaException

logger = logging.getLogger(__name__)
inyeccion_bp = Blueprint('inyeccion_bp', __name__)


@inyeccion_bp.route('/api/inyeccion/lote', methods=['POST'])
@require_role(ROL_ADMINS + ROL_JEFES + ['INYECCION', 'ENSAMBLE', 'PULIDO', 'AUXILIAR INVENTARIO', 'STAFF FRIMETALS', 'CALIDAD'])
def registrar_inyeccion_lote():
    """
    PASO 1-4: SQL-First Validation Workflow (controller delgado).
    Parsea el request, delega toda la orquestación a InyeccionService.registrar_lote
    y traduce el resultado (o las excepciones de negocio) a JSON.
    """
    data = request.json or {}
    usuario_activo = _obtener_usuario_activo()

    try:
        resultado = InyeccionService.registrar_lote(data, usuario_activo)
        return jsonify(resultado), 200

    except OwnershipMismatchException as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "INYECCION_SESSION_OWNERSHIP_MISMATCH",
            "responsable_db": e.responsable_db,
            "responsable_in": e.responsable_in
        }), 409

    except ValidadorRequeridoException as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "VALIDADOR_REQUERIDO"
        }), 400

    except TurnoInvalidoException as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "TURNO_DURACION_INVALIDA"
        }), 400

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f" ❌ Error en registrar_inyeccion_lote: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@inyeccion_bp.route('/api/inyeccion/iniciar_turno', methods=['POST'])
def iniciar_turno_inyeccion():
    """
    [DEPRECATED] Lógica de lotes en vivo eliminada.
    Se mantiene ruta como dummy para retrocompatibilidad segura.
    """
    return jsonify({
        "success": True,
        "message": "Turno iniciado (Flujo Directo)",
        "id_inyeccion": f"INY-DUMMY-{uuid.uuid4().hex[:4].upper()}"
    }), 201

@inyeccion_bp.route('/api/inyeccion/validar/<id_inyeccion>', methods=['POST'])
@require_role(ROL_ADMINS + ROL_JEFES + ['AUXILIAR INVENTARIO', 'STAFF FRIMETALS', 'CALIDAD'])
def validar_lote_inyeccion(id_inyeccion):
    """
    Controller delgado: parsea el request, delega a InyeccionService.validar_lote
    y traduce el resultado (o las excepciones de negocio) a JSON.
    """
    data = request.get_json(silent=True) or {}
    usuario_activo = _obtener_usuario_activo()

    try:
        resultado = InyeccionService.validar_lote(id_inyeccion, data, usuario_activo)
        return jsonify(resultado), 200

    except LoteInyeccionNoEncontradoException as e:
        return jsonify({"success": False, "error": e.message}), 404

    except OwnershipMismatchException as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "INYECCION_SESSION_OWNERSHIP_MISMATCH",
            "responsable_db": e.responsable_db,
            "responsable_in": e.responsable_in
        }), 409

    except ValidadorRequeridoException as e:
        return jsonify({"success": False, "error": e.message, "code": "VALIDADOR_REQUERIDO"}), 400

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f"❌ Error validando lote {id_inyeccion}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@inyeccion_bp.route('/api/inyeccion/dashboard_stats', methods=['GET'])
@require_role(ROL_ADMINS + ['JEFE INYECCION', 'INYECCION'])
def get_inyeccion_stats():
    # Placeholder
    return jsonify({"success": True, "message": "Estadísticas de inyección (WIP)"})


@inyeccion_bp.route('/api/programacion/guardar', methods=['POST'])
def guardar_programacion_diaria():
    """
    Controller delgado: parsea el request, delega a InyeccionService.guardar_programacion
    y traduce el resultado (o las excepciones de negocio) a JSON.
    """
    data = request.get_json()

    try:
        resultado = InyeccionService.guardar_programacion(data)
        return jsonify(resultado), 201

    except ValueError as val_err:
        logger.warning(f"⚠️ Error de validación en guardar_programacion_diaria: {val_err}")
        return jsonify({"success": False, "error": str(val_err)}), 400

    except Exception as e:
        logger.error(f"❌ Error crítico en guardar_programacion_diaria: {e}")
        return jsonify({"success": False, "error": "Error interno del servidor al guardar la programación"}), 500


@inyeccion_bp.route('/api/pedidos/pendientes/<codigo>', methods=['GET'])
def obtener_pedidos_pendientes(codigo):
    """
    Controller delgado: delega la consulta a InyeccionService.obtener_pedidos_pendientes
    y traduce el resultado (o las excepciones de negocio) a JSON.
    """
    try:
        resultado = InyeccionService.obtener_pedidos_pendientes(codigo)
        return jsonify(resultado), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f"❌ Error en obtener_pedidos_pendientes para el código {codigo}: {e}")
        return jsonify({"success": False, "error": "Error interno del servidor al consultar pedidos"}), 500


@inyeccion_bp.route('/api/produccion/verificar_demanda/<codigo>', methods=['GET'])
def verificar_demanda_b2b(codigo):
    """
    Controller delgado: delega la consulta a InyeccionService.obtener_demanda_b2b
    y traduce el resultado (o las excepciones de negocio) a JSON.
    """
    try:
        resultado = InyeccionService.obtener_demanda_b2b(codigo)
        return jsonify(resultado), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f"❌ Error en verificar_demanda para {codigo}: {e}")
        return jsonify({"success": False, "error": "Error interno al verificar la demanda"}), 500



@inyeccion_bp.route('/api/mes/pendientes_validacion', methods=['GET'])
def mes_pendientes_validacion():
    """Obtiene todos los lotes en estado PENDIENTE/FINALIZADO para validación."""
    resultado = InyeccionService.obtener_pendientes_validacion()
    status_code = 200 if resultado.get('success') else 500
    return jsonify(resultado), status_code


@inyeccion_bp.route('/api/mes/iniciar_trabajo', methods=['POST'])
@require_role(ROL_ADMINS + ['INYECCION', 'ENSAMBLE'])
def mes_iniciar_trabajo():
    """
    Controller delgado: parsea el request, delega a InyeccionService.iniciar_trabajo
    y traduce el resultado (o las excepciones de negocio) a JSON.
    """
    data = request.get_json() or {}
    usuario_activo = _obtener_usuario_activo()

    try:
        resultado = InyeccionService.iniciar_trabajo(data, usuario_activo)
        return jsonify(resultado), 200

    except ProgramacionNoEncontradaException as e:
        return jsonify({"success": False, "error": e.message}), 404

    except OwnershipMismatchException as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "INYECCION_SESSION_OWNERSHIP_MISMATCH",
            "responsable_db": e.responsable_db,
            "responsable_in": e.responsable_in
        }), 409

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f"❌ Error al iniciar trabajo en el MES: {e}")
        return jsonify({"success": False, "error": "Error interno al iniciar el trabajo"}), 500


@inyeccion_bp.route('/api/mes/reportar', methods=['POST'])
@require_role(ROL_ADMINS + ['INYECCION', 'ENSAMBLE'])
def mes_reportar():
    """
    Controller delgado: parsea el request, delega a InyeccionService.reportar_trabajo
    y traduce el resultado (o las excepciones de negocio) a JSON.
    """
    data = request.get_json() or {}
    usuario_activo = _obtener_usuario_activo()

    try:
        resultado = InyeccionService.reportar_trabajo(data, usuario_activo)
        return jsonify(resultado), 200

    except LoteInyeccionNoEncontradoException as e:
        return jsonify({"success": False, "error": e.message}), 404

    except OwnershipMismatchException as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "INYECCION_SESSION_OWNERSHIP_MISMATCH",
            "responsable_db": e.responsable_db,
            "responsable_in": e.responsable_in
        }), 409

    except TurnoInvalidoException as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "TURNO_DURACION_INVALIDA"
        }), 400

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f"❌ Error al reportar turno en el MES: {e}")
        return jsonify({"success": False, "error": "Error interno al finalizar el turno"}), 500


@inyeccion_bp.route('/api/pnc/registrar_inyeccion', methods=['POST'])
def registrar_pnc_inyeccion():
    """
    Controller delgado: parsea el request, delega a InyeccionService.registrar_pnc
    y traduce el resultado (o las excepciones de negocio) a JSON.
    """
    data = request.get_json() or {}

    try:
        resultado = InyeccionService.registrar_pnc(data)
        return jsonify(resultado), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f"❌ Error en registrar_pnc_inyeccion: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


