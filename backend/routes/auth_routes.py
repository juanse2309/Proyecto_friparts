from flask import Blueprint, jsonify, request, session
from backend.core.sql_database import db
from backend.models.sql_models import Usuario
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import uuid
import datetime
import time 

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# ====================================================================
# FRIMETALS AUTH
# ====================================================================

@auth_bp.route('/api/auth/metals/responsables', methods=['GET'])
def get_metals_responsables():
    """Obtiene lista de responsables de Metales desde SQL (db_usuarios)."""
    try:
        from backend.models.sql_models import Usuario
        
        # Consultar usuarios activos filtrados por departamento o rol específico si existe
        # Por ahora, usamos el campo 'departamento' si existe en el modelo
        users = Usuario.query.filter(Usuario.activo == True).all()
        
        usuarios = []
        for u in users:
            # Filtro básico: si el username o departamento sugieren que es de metales
            usuarios.append({
                "nombre": u.username,
                "departamento": getattr(u, 'departamento', 'Planta'),
                "documento": "" # SQL no suele tener documento en Usuario por ahora
            })
        
        return jsonify(usuarios)
    except Exception as e:
        logger.error(f"Error fetching metals responsables SQL: {e}")
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/api/auth/metals/login', methods=['POST'])
def metals_login():
    """Login para Metales usando SQL centralizado"""
    try:
        data = request.json
        usuario_nombre = data.get('responsable')
        password = str(data.get('password', '')).strip() # ⚡ Limpiar espacios

        if not usuario_nombre or not password:
            return jsonify({"success": False, "message": "Faltan datos"}), 400

        user = Usuario.query.filter_by(username=usuario_nombre, activo=True).first()
        
        # --- DEBUG LOGIN ---
        print("--- DEBUG LOGIN ---")
        print(f"1. Usuario buscado: '{usuario_nombre}'")
        print(f"2. ¿Usuario encontrado en BD?: {user is not None}")
        if user:
            print(f"3. Hash/Password en BD: '{user.password_hash}'")
        print(f"4. Contraseña enviada por frontend: '{password}'")
        print("-------------------")

        if not user:
             return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        
        if check_password_hash(user.password_hash, password):
            # Validar que sea un rol permitido para metales (o admin)
            rol_lower = user.rol.lower()
            
            # Escribir sesión Flask
            session['user'] = user.username
            session['role'] = rol_lower

            user.ultimo_acceso = datetime.datetime.utcnow()
            db.session.commit()

            return jsonify({
                "success": True,
                "user": {
                    "nombre": user.username,
                    "rol": user.rol.capitalize(),
                    "tipo": "METALS_STAFF"
                }
            })
        else:
            return jsonify({"success": False, "message": "Contraseña incorrecta"}), 401
    except Exception as e:
        logger.error(f"Error in metals SQL login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ====================================================================
# HELPER: Sheets Interaction
# ====================================================================
def get_client_users_sheet():
    """DEPRECATED: Usar Usuario.query en su lugar."""
    return None

# ====================================================================
# STAFF AUTH (Responsables)
# ====================================================================

@auth_bp.route('/api/auth/responsables', methods=['GET'])
def get_responsables():
    """Obtiene lista de operarios y staff administrativo desde SQL"""
    try:
        # Consultar usuarios que no sean clientes
        users = Usuario.query.filter(Usuario.rol != 'cliente', Usuario.activo == True).all()
        
        responsables = []
        for u in users:
            responsables.append({
                "nombre": u.username,
                "departamento": u.rol.capitalize(),
                "rol": u.rol
            })
            
        return jsonify(responsables)

    except Exception as e:
        logger.error(f"Error fetching responsables from SQL: {e}")
        return jsonify({"error": str(e)}), 500

# ====================================================================
# HELPER: Credential Normalization
# ====================================================================
def normalize_credential(value):
    """
    Normaliza una credencial (documento o password) para comparacion robusta.
    Maneja el caso comun de Excel/Sheets donde '12345' viene como 12345.0
    """
    if value is None:
        return ""
    
    s_val = str(value).strip()
    
    # Si termina en .0, quitarlo (ej: "1003456789.0" -> "1003456789")
    if s_val.endswith(".0"):
        s_val = s_val[:-2]

    # Quitar puntos y comas para comparacion agnostica de formato (1.234.567 == 1234567)
    s_val = s_val.replace(".", "").replace(",", "")
        
    return s_val

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login para Staff (Operarios/Admin) usando SQL"""
    try:
        data = request.json
        usuario_nombre = data.get('responsable')
        password = str(data.get('password', '')).strip() # ⚡ Limpiar espacios

        if not usuario_nombre or not password:
            return jsonify({"success": False, "message": "Faltan datos"}), 400

        user = Usuario.query.filter_by(username=usuario_nombre, activo=True).first()
        
        # --- DEBUG LOGIN ---
        print("--- DEBUG LOGIN ---")
        print(f"1. Usuario buscado: '{usuario_nombre}'")
        print(f"2. ¿Usuario encontrado en BD?: {user is not None}")
        if user:
            print(f"3. Hash/Password en BD: '{user.password_hash}'")
        print(f"4. Contraseña enviada por frontend: '{password}'")
        print("-------------------")

        if not user:
             return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

        if check_password_hash(user.password_hash, password):
             # Guardar rol en sesión en MAYÚSCULAS para matching estricto
             session['user'] = user.username
             session['role'] = user.rol.upper()
             
             # Espejo/Log opcional en Sheets (Si se desea implementar luego)
             user.ultimo_acceso = datetime.datetime.utcnow()
             db.session.commit()
             
             # Determinar rol a retornar (Estandarizado a ADMIN para administradores)
             rol_display = "ADMIN" if user.rol.lower() in ['admin', 'administrador', 'administracion'] else user.rol.capitalize()
             
             return jsonify({
                 "success": True, 
                 "user": {
                     "nombre": user.username,
                     "rol": rol_display,
                     "tipo": "STAFF"
                 }
             })
        else:
             return jsonify({"success": False, "message": "Contraseña incorrecta."}), 401

    except Exception as e:
        logger.error(f"Error in SQL login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ====================================================================

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout_staff():
    """Logout general"""
    session.clear()
    return jsonify({"success": True, "message": "Sesión cerrada correctamente"}), 200

@auth_bp.route('/api/auth/session/status', methods=['GET'])
def get_session_status():
    if 'role' in session:
        return jsonify({'success': True, 'role': session['role'], 'user': session.get('user')}), 200
    return jsonify({'success': False}), 401

# ====================================================================
# CLIENT AUTH (Portal B2B)
# ====================================================================

@auth_bp.route('/api/admin/clientes/crear', methods=['POST'])
def crear_cuenta_cliente():
    """CUENTA CLIENTE: Crea entrada en tabla Usuarios SQL"""
    try:
        data = request.json
        nit = str(data.get('nit', '')).strip()
        nombre_empresa = str(data.get('nombre_empresa', '')).strip()
        email = str(data.get('email', '')).strip().lower()
        
        if not nit or not email:
            return jsonify({"success": False, "message": "NIT y Email son obligatorios"}), 400
        
        # Verificar si existe
        if Usuario.query.filter_by(username=email).first():
            return jsonify({"success": False, "message": "El correo ya está registrado"}), 400

        # Password temporal: NIT
        hashed_pw = generate_password_hash(nit, method='scrypt')
        
        new_user = Usuario(
            username=email,
            password_hash=hashed_pw,
            nombre_completo=nombre_empresa,
            rol='cliente',
            nit_empresa=nit
        )
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Cuenta de cliente creada en SQL",
            "password_temporal": nit
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creando cliente SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ====================================================================
# HELPER: Data Enrichment
# ====================================================================
def enrich_client_data(user_data):
    """
    Intenta completar dirección y ciudad desde db_clientes en SQL.
    """
    nit = user_data.get('nit', '')
    if not nit:
        return user_data

    try:
        from backend.models.sql_models import DbClientes
        # Buscar por identificación
        match = DbClientes.query.filter(DbClientes.identificacion.ilike(f"%{nit}%")).first()
        
        if match:
            if not user_data.get('direccion'):
                user_data['direccion'] = match.direccion
            if not user_data.get('ciudad'):
                user_data['ciudad'] = match.ciudad
            logger.info(f"✅ Datos enriquecidos para {nit} desde SQL (db_clientes)")
    except Exception as e:
        logger.error(f"⚠️ Error enriqueciendo datos desde SQL: {e}")
            
    return user_data

@auth_bp.route('/api/auth/client/login', methods=['POST'])
def login_client():
    """Login para Clientes B2B usando SQL"""
    try:
        data = request.json
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', '')).strip()

        user = Usuario.query.filter_by(username=email, rol='cliente', activo=True).first()
                
        if not user:
             return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401
             
        if not check_password_hash(user.password_hash, password):
            return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401

        session['user'] = user.username
        session['role'] = 'cliente'
        
        return jsonify({
            "success": True,
            "requires_password_change": False, # Simplificado para SQL
            "user": {
                "nombre": user.nombre_completo,
                "email": user.username,
                "nit": user.nit_empresa,
                "rol": "Cliente",
                "tipo": "CLIENTE"
            }
        })

    except Exception as e:
        logger.error(f"Error in client SQL login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/auth/client/change-password', methods=['POST'])
def change_password_client():
    """Cambio de contraseña CLIENTE en SQL"""
    try:
        data = request.json
        email = str(data.get('email', '')).strip().lower()
        old_password = str(data.get('old_password', '')).strip()
        new_password = str(data.get('new_password', '')).strip()

        if not new_password:
             return jsonify({"success": False, "message": "La nueva contraseña es obligatoria"}), 400

        user = Usuario.query.filter_by(username=email, rol='cliente').first()
        
        if not user:
             return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

        if not check_password_hash(user.password_hash, old_password):
             return jsonify({"success": False, "message": "La contraseña actual es incorrecta"}), 401

        # Actualizar contraseña
        user.password_hash = generate_password_hash(new_password, method='scrypt')
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Contraseña actualizada correctamente en SQL."
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating SQL password: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/admin/clientes/listar', methods=['GET'])
def listar_clientes():
    """ADMIN: Lista todos los clientes registrados en SQL"""
    try:
        users = Usuario.query.filter_by(rol='cliente').all()
        
        clientes = []
        for u in users:
            clientes.append({
                "nit": u.nit_empresa,
                "nombre_empresa": u.nombre_completo,
                "email": u.username,
                "estado": "ACTIVO" if u.activo else "INACTIVO",
                "ultimo_acceso": u.ultimo_acceso.strftime("%Y-%m-%d %H:%M:%S") if u.ultimo_acceso else ""
            })
        
        return jsonify({"success": True, "clientes": clientes})
        
    except Exception as e:
        logger.error(f"Error listing clients SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/admin/clientes/reset-password', methods=['POST'])
def reset_password_admin():
    """ADMIN: Resetea la contraseña de un cliente en SQL"""
    try:
        data = request.json
        email = str(data.get('email', '')).strip().lower()
        
        user = Usuario.query.filter_by(username=email, rol='cliente').first()
        if not user:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        
        # Reset a NIT
        hashed_pw = generate_password_hash(user.nit_empresa, method='scrypt')
        user.password_hash = hashed_pw
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Contraseña reseteada en SQL",
            "password_temporal": user.nit_empresa
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting password SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/admin/clientes/toggle-estado', methods=['POST'])
def toggle_estado_cliente():
    """ADMIN: Activa/Desactiva una cuenta de cliente en SQL"""
    try:
        data = request.json
        email = str(data.get('email', '')).strip().lower()
        nuevo_estado = str(data.get('estado', 'ACTIVO')).strip().upper()
        
        user = Usuario.query.filter_by(username=email, rol='cliente').first()
        if not user:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        
        user.activo = (nuevo_estado == 'ACTIVO')
        db.session.commit()
        
        return jsonify({"success": True, "message": f"Cuenta {'activada' if user.activo else 'desactivada'} en SQL"})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling state SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
