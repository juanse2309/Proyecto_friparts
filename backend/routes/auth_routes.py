from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import uuid
import datetime

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# ====================================================================
# HELPER: Sheets Interaction
# ====================================================================
def get_client_users_sheet():
    """Obtiene o crea la hoja de usuarios clientes."""
    try:
        # Se asume que sheets_client.get_worksheet usa el nombre exacto
        ws = sheets_client.get_worksheet("USUARIOS_CLIENTES")
        # Si get_worksheet retorna None o lanza excepcion si no existe
        return ws
    except Exception:
        return None

# ====================================================================
# STAFF AUTH (Responsables)
# ====================================================================

@auth_bp.route('/api/auth/responsables', methods=['GET'])
def get_responsables():
    try:
        ws = sheets_client.get_worksheet("RESPONSABLES")
        if not ws:
            return jsonify({"error": "Hoja RESPONSABLES no encontrada"}), 500

        records = ws.get_all_records()
        
        usuarios = []
        for row in records:
            usuarios.append({
                "nombre": row.get("RESPONSABLE", ""),
                "departamento": row.get("DEPARTAMENTO", ""),
                "documento": str(row.get("DOCUMENTO", ""))
            })
            
        return jsonify(usuarios)

    except Exception as e:
        logger.error(f"Error fetching responsables: {e}")
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login para Staff (Operarios/Admin)"""
    try:
        data = request.json
        usuario_nombre = data.get('responsable')
        password = data.get('password') # Documento

        if not usuario_nombre or not password:
            return jsonify({"success": False, "message": "Faltan datos"}), 400

        ws = sheets_client.get_worksheet("RESPONSABLES")
        if not ws:
            return jsonify({"success": False, "message": "Error interno: Hoja no encontrada"}), 500

        records = ws.get_all_records()
        
        user_found = None
        for row in records:
            if row.get("RESPONSABLE") == usuario_nombre:
                user_found = row
                break
        
        if not user_found:
             return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

        # Verificacion Híbrida (Hash o Texto Plano)
        doc_real = str(user_found.get("DOCUMENTO", "")).strip()
        pwd_input = str(password).strip()
        
        # Intentar obtener columna CONTRASEÑA, si no existe o vacia, usar DOCUMENTO
        stored_password = str(user_found.get("CONTRASEÑA", "")).strip()
        if not stored_password:
            stored_password = doc_real
        
        auth_success = False
        
        # 1. Intentar verificar como Hash
        if stored_password.startswith('scrypt:') or stored_password.startswith('pbkdf2:'):
            if check_password_hash(stored_password, pwd_input):
                auth_success = True
        # 2. Fallback: Texto plano (Documento/Pass)
        elif stored_password == pwd_input:
            auth_success = True
            
        if auth_success:
             rol = user_found.get("DEPARTAMENTO", "Invitado")
             print(f"🔐 Login Staff Index: {usuario_nombre} - Rol: {rol}")
             return jsonify({
                 "success": True, 
                 "user": {
                     "nombre": usuario_nombre,
                     "rol": rol,
                     "tipo": "STAFF"
                 }
             })
        else:
             print(f"🔐 Fallo login Staff: {usuario_nombre}")
             return jsonify({
                 "success": False, 
                 "message": "Credenciales incorrectas."
             }), 401

    except Exception as e:
        logger.error(f"Error in login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ====================================================================
# CLIENT AUTH (Portal B2B)
# ====================================================================

@auth_bp.route('/api/auth/client/register', methods=['POST'])
def register_client():
    try:
        data = request.json
        nit = str(data.get('nit', '')).strip()
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', '')).strip()
        nombre_contacto = str(data.get('nombre', '')).strip()

        if not nit or not email or not password:
            return jsonify({"success": False, "message": "NIT, Email y Contraseña son obligatorios"}), 400

        # 1. (ELIMINADO) Ya no se valida contra la hoja CLIENTES estricta, se confía en el registro.
        # Se usará el nombre ingresado como Nombre Empresa.
        nombre_empresa = nombre_contacto
        
        # 2. Verificar si ya tiene cuenta en USUARIOS_CLIENTES
        ws_users = sheets_client.get_worksheet("USUARIOS_CLIENTES")
        if not ws_users:
            return jsonify({"success": False, "message": "Error interno: Hoja de usuarios no configurada."}), 500
            
        users_records = ws_users.get_all_records()
        for u in users_records:
            if str(u.get('EMAIL')).lower() == email:
                return jsonify({"success": False, "message": "El correo ya está registrado."}), 400
            if str(u.get('NIT_EMPRESA') or u.get('NIT')) == nit: # Chequear nombres de columna
                # Opcional: permitir multiples cuentas por NIT? Por ahora NO.
                return jsonify({"success": False, "message": "Este NIT ya tiene una cuenta registrada."}), 400

        # 3. Crear usuario
        hashed_pw = generate_password_hash(password)
        new_id = str(uuid.uuid4())
        fecha_registro = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Columnas esperadas en USUARIOS_CLIENTES:
        # ID, NIT_EMPRESA, NOMBRE_EMPRESA, EMAIL, PASSWORD_HASH, ESTADO, FECHA_REGISTRO, NOMBRE_CONTACTO
        new_user_row = [
            new_id,          # ID
            nit,             # NIT_EMPRESA
            nombre_empresa,  # NOMBRE_EMPRESA
            email,           # EMAIL
            hashed_pw,       # PASSWORD_HASH
            "ACTIVO",        # ESTADO
            fecha_registro,  # FECHA_REGISTRO
            nombre_contacto  # NOMBRE_CONTACTO
        ]
        
        ws_users.append_row(new_user_row)
        
        return jsonify({
            "success": True,
            "message": "Registro exitoso. Ya puede iniciar sesión."
        })

    except Exception as e:
        logger.error(f"Error registering client: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/auth/client/login', methods=['POST'])
def login_client():
    try:
        data = request.json
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', '')).strip()

        ws_users = sheets_client.get_worksheet("USUARIOS_CLIENTES")
        if not ws_users:
             return jsonify({"success": False, "message": "Sistema de clientes no disponible"}), 500
             
        records = ws_users.get_all_records()
        user_found = None
        
        for row in records:
            if str(row.get('EMAIL')).lower() == email:
                user_found = row
                break
                
        if not user_found:
             return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401
             
        # Verificar Hash
        stored_hash = user_found.get('PASSWORD_HASH')
        try:
            if check_password_hash(stored_hash, password):
                if user_found.get('ESTADO') != 'ACTIVO':
                     return jsonify({"success": False, "message": "Cuenta inactiva."}), 403
                     
                return jsonify({
                    "success": True,
                    "user": {
                        "nombre": user_found.get('NOMBRE_EMPRESA'), # Para mostrar en UI
                        "nombre_contacto": user_found.get('NOMBRE_CONTACTO'),
                        "email": email,
                        "nit": user_found.get('NIT_EMPRESA'),
                        "rol": "Cliente",
                        "tipo": "CLIENTE"
                    }
                })
            else:
                return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401
        except Exception:
             # Fallback por si la pass no era hash (migracion o error manual)
             if stored_hash == password:
                  return jsonify({
                    "success": True,
                    "user": {
                        "nombre": user_found.get('NOMBRE_EMPRESA'),
                        "nombre_contacto": user_found.get('NOMBRE_CONTACTO'),
                        "email": email,
                        "nit": user_found.get('NIT_EMPRESA'),
                        "rol": "Cliente",
                        "tipo": "CLIENTE"
                    }
                })
             return jsonify({"success": False, "message": "Error de autenticación."}), 401

    except Exception as e:
        logger.error(f"Error in client login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
