from flask import Blueprint, jsonify, request, session
import logging
from backend.utils.auth_middleware import require_role, ROL_ADMINS
from backend.services.auth_service import (
    AuthService,
    UsuarioNoEncontradoException,
    CredencialesInvalidasException,
    CuentaPendienteException,
    CuentaInactivaException,
    AccesoDenegadoException,
    CorreoDuplicadoException,
    NitDuplicadoException,
)

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


def restore_session_from_token():
    """
    Hook `before_request`: si la sesión Flask no tiene 'user'/'role' (típico
    en PWA standalone que no comparte cookies con el navegador), intenta
    restaurarla desde el JWT del header `Authorization: Bearer`. Movido desde
    app.py — es lógica de autenticación, no de arranque de la aplicación.
    """
    import os
    # Ignorar endpoints estáticos o de login
    if request.path.startswith('/static/') or request.path.startswith('/api/auth/login') or request.path.startswith('/api/auth/metals/login'):
        return

    # Si la sesión ya existe, perfecto
    if 'user' in session and 'role' in session:
        return

    # Fallback PWA Standalone: Buscar Header Authorization
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            import jwt
            secret = os.environ.get('JWT_PWA_SECRET')
            if not secret:
                raise RuntimeError("JWT_PWA_SECRET no configurada")
            payload = jwt.decode(token, secret, algorithms=['HS256'])

            session['user'] = payload['user']
            session['role'] = payload['role']
            logger.info(f"🔄 Sesión restaurada vía JWT para PWA (Usuario: {payload['user']})")
        except Exception as e:
            logger.warning(f"Error decodificando JWT PWA: {e}")


# ====================================================================
# FRIMETALS AUTH
# ====================================================================

@auth_bp.route('/api/auth/metals/responsables', methods=['GET'])
def get_metals_responsables():
    """Obtiene lista de responsables de Metales."""
    try:
        resultado = AuthService.obtener_responsables_metals()
        return jsonify({'status': 'success', 'success': True, 'data': resultado})
    except Exception as e:
        logger.error(f"Error fetching metals responsables SQL: {e}")
        return jsonify({'status': 'error', 'success': False, 'message': 'No fue posible obtener los responsables de Metales.'}), 500


@auth_bp.route('/api/auth/metals/login', methods=['POST'])
def metals_login():
    """Login para Metales."""
    data = request.json or {}
    try:
        resultado = AuthService.login_metals(data.get('responsable'), str(data.get('password', '')).strip())

        session['user'] = resultado['session']['user']
        session['role'] = resultado['session']['role']

        return jsonify({
            "success": True,
            "pwa_token": resultado['pwa_token'],
            "user": resultado['user']
        })
    except UsuarioNoEncontradoException as e:
        return jsonify({"success": False, "message": e.message}), 404
    except CredencialesInvalidasException as e:
        return jsonify({"success": False, "message": e.message}), 401
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error in metals SQL login: {e}")
        return jsonify({"success": False, "message": "Error interno al iniciar sesión."}), 500


# ====================================================================
# STAFF AUTH (Responsables)
# ====================================================================

@auth_bp.route('/api/auth/responsables', methods=['GET'])
def get_responsables():
    """Obtiene lista de operarios y staff administrativo."""
    try:
        return jsonify(AuthService.obtener_responsables_staff())
    except Exception as e:
        logger.error(f"Error fetching responsables from SQL: {e}")
        return jsonify({"error": "No fue posible obtener los responsables."}), 500


@auth_bp.route('/api/obtener_responsables', methods=['GET'])
def obtener_responsables():
    """
    Retorna lista de responsables activos para dropdowns generales.
    Prioriza db_usuarios, fallback a db_asistencia. Movido desde app.py:
    no es un endpoint de sesión/credenciales, pero sí de gestión de usuarios.

    Acepta ?rol=<texto> opcional para acotar el catálogo a un área operativa
    (ILIKE sobre db_usuarios.rol, ej. ?rol=PULIDO). Sin ese parámetro devuelve
    el catálogo general; en ambos casos excluye cuentas administrativas/de
    sistema (ver AuthService.obtener_responsables_generales).
    """
    try:
        rol_filtro = request.args.get('rol', '').strip() or None
        return jsonify(AuthService.obtener_responsables_generales(rol_filtro)), 200
    except Exception as e:
        logger.error(f"❌ Error obteniendo responsables SQL: {e}")
        return jsonify([]), 200


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login para Staff (Operarios/Admin)."""
    data = request.json or {}
    try:
        resultado = AuthService.login_staff(data.get('responsable'), str(data.get('password', '')).strip())

        session['user'] = resultado['session']['user']
        session['role'] = resultado['session']['role']

        return jsonify({
            "success": True,
            "pwa_token": resultado['pwa_token'],
            "user": resultado['user']
        })
    except UsuarioNoEncontradoException as e:
        return jsonify({"success": False, "message": e.message}), 404
    except CuentaPendienteException as e:
        return jsonify({"success": False, "message": e.message}), 401
    except CuentaInactivaException as e:
        return jsonify({"success": False, "message": e.message}), 401
    except CredencialesInvalidasException as e:
        return jsonify({"success": False, "message": e.message}), 401
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error in SQL login: {e}")
        return jsonify({"success": False, "message": "Error interno al iniciar sesión."}), 500


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout_staff():
    """Logout general (solo limpia la sesión Flask, no toca la base de datos)."""
    session.clear()
    return jsonify({"success": True, "message": "Sesión cerrada correctamente"}), 200


@auth_bp.route('/api/auth/session/status', methods=['GET'])
def get_session_status():
    """Consulta el estado de la sesión Flask activa (no toca la base de datos)."""
    if 'role' in session:
        return jsonify({'success': True, 'role': session['role'], 'user': session.get('user')}), 200
    return jsonify({'success': False}), 401


# ====================================================================
# CLIENT AUTH (Portal B2B)
# ====================================================================

@auth_bp.route('/api/admin/clientes/crear', methods=['POST'])
@require_role(ROL_ADMINS)
def crear_cuenta_cliente():
    """ADMIN: Crea una cuenta de cliente."""
    data = request.json or {}
    try:
        resultado = AuthService.crear_cuenta_cliente(
            nit=str(data.get('nit', '')).strip(),
            nombre_empresa=str(data.get('nombre_empresa', '')).strip(),
            email=str(data.get('email', '')).strip().lower(),
        )
        return jsonify({
            "success": True,
            "message": "Cuenta de cliente creada en SQL",
            "password_temporal": resultado['password_temporal']
        })
    except CorreoDuplicadoException as e:
        return jsonify({"success": False, "message": e.message}), 400
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creando cliente SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@auth_bp.route('/api/auth/client/login', methods=['POST'])
def login_client():
    """Login para Clientes B2B."""
    data = request.json or {}
    try:
        resultado = AuthService.login_cliente(
            str(data.get('email', '')).strip().lower(),
            str(data.get('password', '')).strip(),
        )

        session['user'] = resultado['session']['user']
        session['role'] = resultado['session']['role']

        return jsonify({
            "success": True,
            "pwa_token": resultado['pwa_token'],
            "requires_password_change": resultado['requires_password_change'],
            "user": resultado['user']
        })
    except (UsuarioNoEncontradoException, CredencialesInvalidasException) as e:
        return jsonify({"success": False, "message": e.message}), 401
    except CuentaPendienteException as e:
        return jsonify({"success": False, "message": e.message}), 401
    except AccesoDenegadoException as e:
        return jsonify({"success": False, "message": e.message}), 403
    except CuentaInactivaException as e:
        return jsonify({"success": False, "message": e.message}), 401
    except Exception as e:
        logger.error(f"Error in client SQL login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@auth_bp.route('/api/auth/client/register', methods=['POST'])
def register_client():
    """Registro público para Clientes B2B con patrón Sandboxing."""
    data = request.json or {}
    try:
        AuthService.registrar_cliente(
            email=str(data.get('email', '')).strip().lower(),
            password=str(data.get('password', '')).strip(),
            nit=str(data.get('nit', '')).strip(),
            nombre_empresa=str(data.get('nombre_empresa', '')).strip(),
        )
        return jsonify({"success": True})
    except CorreoDuplicadoException as e:
        return jsonify({"success": False, "message": e.message}), 400
    except NitDuplicadoException as e:
        return jsonify({"success": False, "message": e.message}), 400
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error en el registro público de cliente: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@auth_bp.route('/api/auth/client/change-password', methods=['POST'])
def change_password_client():
    """Cambio de contraseña de un CLIENTE autenticado."""
    data = request.json or {}
    try:
        AuthService.cambiar_password_cliente(
            email=str(data.get('email', '')).strip().lower(),
            old_password=str(data.get('old_password', '')).strip(),
            new_password=str(data.get('new_password', '')).strip(),
        )
        return jsonify({"success": True, "message": "Contraseña actualizada correctamente en SQL."})
    except UsuarioNoEncontradoException as e:
        return jsonify({"success": False, "message": e.message}), 404
    except CredencialesInvalidasException as e:
        return jsonify({"success": False, "message": e.message}), 401
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating SQL password: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@auth_bp.route('/api/admin/clientes/listar', methods=['GET'])
@require_role(ROL_ADMINS)
def listar_clientes():
    """ADMIN: Lista todos los clientes registrados."""
    try:
        return jsonify({"success": True, "clientes": AuthService.listar_clientes()})
    except Exception as e:
        logger.error(f"Error listing clients SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@auth_bp.route('/api/admin/clientes/reset-password', methods=['POST'])
@require_role(ROL_ADMINS)
def reset_password_admin():
    """ADMIN: Resetea la contraseña de un cliente (vuelve a su NIT)."""
    data = request.json or {}
    try:
        resultado = AuthService.resetear_password_cliente(str(data.get('email', '')).strip().lower())
        return jsonify({
            "success": True,
            "message": "Contraseña reseteada en SQL",
            "password_temporal": resultado['password_temporal']
        })
    except UsuarioNoEncontradoException as e:
        return jsonify({"success": False, "message": e.message}), 404
    except Exception as e:
        logger.error(f"Error resetting password SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@auth_bp.route('/api/admin/clientes/toggle-estado', methods=['POST'])
@require_role(ROL_ADMINS)
def toggle_estado_cliente():
    """ADMIN: Activa/Desactiva una cuenta de cliente."""
    data = request.json or {}
    try:
        resultado = AuthService.toggle_estado_cliente(
            str(data.get('email', '')).strip().lower(),
            str(data.get('estado', 'ACTIVO')).strip().upper(),
        )
        return jsonify({"success": True, "message": f"Cuenta {'activada' if resultado['activo'] else 'desactivada'} en SQL"})
    except UsuarioNoEncontradoException as e:
        return jsonify({"success": False, "message": e.message}), 404
    except Exception as e:
        logger.error(f"Error toggling state SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
