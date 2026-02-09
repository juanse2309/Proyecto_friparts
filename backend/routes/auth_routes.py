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
        return s_val[:-2]
        
    return s_val

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
        # Normalizamos TODAS las entradas para evitar fallos por formatos numericos
        pwd_input_norm = normalize_credential(password)
        
        # 1. Obtener "contraseña almacenada"
        stored_password_raw = user_found.get("CONTRASEÑA", "")
        # 2. Si esta vacía, el fallback es el DOCUMENTO
        if not str(stored_password_raw).strip():
            stored_password_raw = user_found.get("DOCUMENTO", "")
            
        stored_password_norm = normalize_credential(stored_password_raw)
        
        auth_success = False
        
        # A. Intentar verificar como Hash (solo si tiene formato hash)
        if stored_password_norm.startswith('scrypt:') or stored_password_norm.startswith('pbkdf2:'):
            # Para check_password_hash, usamos el input tal cual (string), 
            # ya que el hash se genero sobre un string especifico.
            # Sin embargo, si el hash se genero sobre "12345" y pasamos "12345", funca.
            if check_password_hash(stored_password_norm, pwd_input_norm):
                auth_success = True
        # B. Comparacion Directa (Texto plano / Documento normalizado)
        elif stored_password_norm == pwd_input_norm:
            auth_success = True
            
        if auth_success:
             rol = user_found.get("DEPARTAMENTO", "Invitado")
             print(f"🔐 Login Staff Index OK: {usuario_nombre} - Rol: {rol}")
             return jsonify({
                 "success": True, 
                 "user": {
                     "nombre": usuario_nombre,
                     "rol": rol,
                     "tipo": "STAFF"
                 }
             })
        else:
             print(f"🔐 Fallo login Staff: {usuario_nombre} | Input: '{pwd_input_norm}' vs Stored: '{stored_password_norm}'")
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
        
        # Necesitamos el indice para actualizar después si fuera necesario (aunque gspread usa base 1)
        # Lo buscaremos de nuevo en change-password si es necesario
        for row in records:
            if str(row.get('EMAIL')).lower() == email:
                user_found = row
                break
                
        if not user_found:
             return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401
             
        # Verificar Hash
        stored_hash = user_found.get('PASSWORD_HASH')
        password_ok = False
        
        try:
            if check_password_hash(stored_hash, password):
                password_ok = True
        except Exception:
             # Fallback texto plano
             if stored_hash == password:
                  password_ok = True

        if not password_ok:
            return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"}), 401

        if user_found.get('ESTADO') != 'ACTIVO':
                return jsonify({"success": False, "message": "Cuenta inactiva."}), 403

        # Chequear flag de cambio de clave
        # Puede ser TRUE, "TRUE", "SI", "1", etc.
        cambiar_clave_val = str(user_found.get('CAMBIAR_CLAVE', '')).upper()
        requires_change = cambiar_clave_val in ['TRUE', 'SI', '1', 'VERDADERO']

        return jsonify({
            "success": True,
            "requires_password_change": requires_change,
            "user": {
                "nombre": user_found.get('NOMBRE_EMPRESA'), 
                "nombre_contacto": user_found.get('NOMBRE_CONTACTO'),
                "email": email,
                "nit": user_found.get('NIT_EMPRESA'),
                "rol": "Cliente",
                "tipo": "CLIENTE"
            }
        })

    except Exception as e:
        logger.error(f"Error in client login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/auth/client/change-password', methods=['POST'])
def change_password_client():
    try:
        data = request.json
        email = str(data.get('email', '')).strip().lower()
        old_password = str(data.get('old_password', '')).strip()
        new_password = str(data.get('new_password', '')).strip()

        if not new_password:
             return jsonify({"success": False, "message": "La nueva contraseña es obligatoria"}), 400

        ws_users = sheets_client.get_worksheet("USUARIOS_CLIENTES")
        if not ws_users:
             return jsonify({"success": False, "message": "Sistema de clientes no disponible"}), 500
             
        records = ws_users.get_all_records()
        user_row_index = -1
        user_found = None
        
        for i, row in enumerate(records):
            if str(row.get('EMAIL')).lower() == email:
                user_found = row
                # gspread update usa index 1-based, y records tiene headers
                # row index 0 en 'records' es la fila 2 en el sheet
                user_row_index = i + 2 
                break
        
        if not user_found:
             return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

        # Verificar old password nuevamente por seguridad
        stored_hash = user_found.get('PASSWORD_HASH')
        password_ok = False
        try:
            if check_password_hash(stored_hash, old_password):
                password_ok = True
        except Exception:
             if stored_hash == old_password:
                  password_ok = True
        
        if not password_ok:
             return jsonify({"success": False, "message": "La contraseña actual es incorrecta"}), 401

        # Actualizar contraseña
        new_hashed = generate_password_hash(new_password)
        
        # Buscar columnas. Asumimos que existen. Si no, las agregamos al final?
        # Mejor buscar el indice de la columna por nombre
        headers = ws_users.row_values(1)
        
        try:
            col_pass_idx = headers.index('PASSWORD_HASH') + 1
        except ValueError:
            return jsonify({"success": False, "message": "Error schema: No existe col PASSWORD_HASH"}), 500
            
        try:
            col_cambiar_idx = headers.index('CAMBIAR_CLAVE') + 1
        except ValueError:
            # Si no existe la columna CAMBIAR_CLAVE, no podemos actualizarla, pero si la pass
             col_cambiar_idx = None

        # Actualizar Pass
        ws_users.update_cell(user_row_index, col_pass_idx, new_hashed)
        
        # Actualizar Flag a FALSE
        if col_cambiar_idx:
            ws_users.update_cell(user_row_index, col_cambiar_idx, "FALSE")

        return jsonify({"success": True, "message": "Contraseña actualizada correctamente."})

    except Exception as e:
        logger.error(f"Error updating password: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
