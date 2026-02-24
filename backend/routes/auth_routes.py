from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import uuid
import datetime

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# ====================================================================
# FRIMETALS AUTH
# ====================================================================

@auth_bp.route('/api/auth/metals/responsables', methods=['GET'])
def get_metals_responsables():
    try:
        ws = sheets_client.get_worksheet("METALS_PERSONAL")
        if not ws:
            return jsonify({"error": "Hoja METALS_PERSONAL no encontrada"}), 500
        records = ws.get_all_records()
        usuarios = []
        for row in records:
            if row.get("ACTIVO") == "SI":
                usuarios.append({
                    "nombre": row.get("RESPONSABLE", ""),
                    "departamento": row.get("DEPARTAMENTO", ""),
                    "documento": str(row.get("DOCUMENTO", ""))
                })
        return jsonify(usuarios)
    except Exception as e:
        logger.error(f"Error fetching metals responsables: {e}")
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/api/auth/metals/login', methods=['POST'])
def metals_login():
    try:
        data = request.json
        usuario_nombre = data.get('responsable')
        password = data.get('password')
        if not usuario_nombre or not password:
            return jsonify({"success": False, "message": "Faltan datos"}), 400
        ws = sheets_client.get_worksheet("METALS_PERSONAL")
        if not ws:
            return jsonify({"success": False, "message": "Error interno"}), 500
        records = ws.get_all_records()
        user_found = next((r for r in records if r.get("RESPONSABLE") == usuario_nombre), None)
        if not user_found:
             return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        
        # Validar password (documento)
        stored_doc = normalize_credential(user_found.get("DOCUMENTO"))
        provided_pass = normalize_credential(password)
        
        if provided_pass == stored_doc:
            return jsonify({
                "success": True,
                "user": {
                    "nombre": user_found.get("RESPONSABLE"),
                    "rol": user_found.get("DEPARTAMENTO"),
                    "tipo": "METALS_STAFF"
                }
            })
        else:
            return jsonify({"success": False, "message": "Contraseña incorrecta"}), 401
    except Exception as e:
        logger.error(f"Error in metals login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


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
        s_val = s_val[:-2]

    # Quitar puntos y comas para comparacion agnostica de formato (1.234.567 == 1234567)
    s_val = s_val.replace(".", "").replace(",", "")
        
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

@auth_bp.route('/api/admin/clientes/crear', methods=['POST'])
def crear_cuenta_cliente():
    """
    SOLO ADMIN/VENTAS: Crea cuenta de cliente con contraseña temporal.
    El cliente deberá cambiarla en el primer login.
    """
    try:
        data = request.json
        
        # Extraer datos
        nit = str(data.get('nit', '')).strip()
        nombre_empresa = str(data.get('nombre_empresa', '')).strip()
        email = str(data.get('email', '')).strip().lower()
        nombre_contacto = str(data.get('nombre_contacto', '')).strip()
        telefono = str(data.get('telefono', '')).strip()
        direccion = str(data.get('direccion', '')).strip()
        ciudad = str(data.get('ciudad', '')).strip()
        
        # Validaciones
        if not nit or not email or not nombre_empresa:
            return jsonify({"success": False, "message": "NIT, Email y Nombre de Empresa son obligatorios"}), 400
        
        # Verificar que el NIT exista en la lista maestra de CLIENTES
        ws_clientes_master = sheets_client.get_worksheet("CLIENTES")
        if ws_clientes_master:
            clientes_master = ws_clientes_master.get_all_records()
            nit_valido = any(str(c.get('NIT', '')).strip() == nit for c in clientes_master)
            
            if not nit_valido:
                return jsonify({
                    "success": False, 
                    "message": f"El NIT {nit} no está en la lista de clientes autorizados."
                }), 403
            
            # Auto-completar datos desde la lista maestra si no se proporcionaron
            cliente_data = next((c for c in clientes_master if str(c.get('NIT', '')).strip() == nit), None)
            if cliente_data and not nombre_empresa:
                nombre_empresa = cliente_data.get('CLIENTE', nombre_empresa)
        
        # Verificar si ya existe una cuenta con este email o NIT
        ws_users = sheets_client.get_worksheet("USUARIOS_CLIENTES")
        if not ws_users:
            return jsonify({"success": False, "message": "Error interno: Hoja de usuarios no configurada."}), 500
        
        users_records = ws_users.get_all_records()
        for u in users_records:
            if str(u.get('EMAIL', '')).lower() == email:
                return jsonify({"success": False, "message": "Ya existe una cuenta con este correo."}), 400
            if str(u.get('NIT_EMPRESA', '')).strip() == nit:
                return jsonify({"success": False, "message": "Ya existe una cuenta para este NIT."}), 400
        
        # Generar contraseña temporal: NIT + año actual
        import datetime
        password_temporal = f"{nit}-{datetime.datetime.now().year}"
        hashed_pw = generate_password_hash(password_temporal)
        
        # Crear usuario
        new_id = str(uuid.uuid4())
        fecha_registro = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Columnas: ID, NIT_EMPRESA, NOMBRE_EMPRESA, EMAIL, PASSWORD_HASH, ESTADO, 
        #           FECHA_REGISTRO, NOMBRE_CONTACTO, CAMBIAR_CLAVE, TELEFONO, DIRECCION, CIUDAD
        new_user_row = [
            new_id,
            nit,
            nombre_empresa,
            email,
            hashed_pw,
            "ACTIVO",
            fecha_registro,
            nombre_contacto,
            "TRUE",  # CAMBIAR_CLAVE - Forzar cambio en primer login
            telefono,
            direccion,
            ciudad
        ]
        
        ws_users.append_row(new_user_row)
        
        logger.info(f"✅ Cuenta creada para {nombre_empresa} (NIT: {nit})")
        
        return jsonify({
            "success": True,
            "message": "Cuenta creada exitosamente",
            "credenciales": {
                "nit": nit,
                "email": email,
                "password_temporal": password_temporal,
                "nombre_empresa": nombre_empresa
            }
        })
        
    except Exception as e:
        logger.error(f"Error creando cuenta de cliente: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/admin/clientes/listar', methods=['GET'])
def listar_clientes():
    """
    ADMIN: Lista todos los clientes registrados en USUARIOS_CLIENTES
    """
    try:
        ws_users = sheets_client.get_worksheet("USUARIOS_CLIENTES")
        if not ws_users:
            return jsonify({"success": False, "message": "Hoja no encontrada"}), 500
        
        registros = ws_users.get_all_records()
        
        clientes = []
        for r in registros:
            clientes.append({
                "nit": r.get("NIT_EMPRESA", ""),
                "nombre_empresa": r.get("NOMBRE_EMPRESA", ""),
                "email": r.get("EMAIL", ""),
                "nombre_contacto": r.get("NOMBRE_CONTACTO", ""),
                "telefono": r.get("TELEFONO", ""),
                "direccion": r.get("DIRECCION", ""),
                "ciudad": r.get("CIUDAD", ""),
                "estado": r.get("ESTADO", "ACTIVO"),
                "fecha_registro": r.get("FECHA_REGISTRO", ""),
                "cambiar_clave": r.get("CAMBIAR_CLAVE", "FALSE")
            })
        
        return jsonify({"success": True, "clientes": clientes})
        
    except Exception as e:
        logger.error(f"Error listando clientes: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/admin/clientes/reset-password', methods=['POST'])
def reset_password_admin():
    """
    ADMIN: Resetea la contraseña de un cliente a una temporal
    """
    try:
        data = request.json
        email = str(data.get('email', '')).strip().lower()
        
        if not email:
            return jsonify({"success": False, "message": "Email requerido"}), 400
        
        ws_users = sheets_client.get_worksheet("USUARIOS_CLIENTES")
        if not ws_users:
            return jsonify({"success": False, "message": "Hoja no encontrada"}), 500
        
        registros = ws_users.get_all_records()
        user_row_index = None
        user_nit = None
        
        for i, r in enumerate(registros):
            if str(r.get('EMAIL', '')).lower() == email:
                user_row_index = i + 2  # +2 porque row 1 es header y enumerate empieza en 0
                user_nit = str(r.get('NIT_EMPRESA', '')).strip()
                break
        
        if not user_row_index:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        
        # Generar nueva contraseña temporal
        import datetime
        password_temporal = f"{user_nit}-{datetime.datetime.now().year}"
        hashed_pw = generate_password_hash(password_temporal)
        
        # Obtener índices de columnas
        headers = ws_users.row_values(1)
        try:
            col_pass_idx = headers.index('PASSWORD_HASH') + 1
            col_cambiar_idx = headers.index('CAMBIAR_CLAVE') + 1
        except ValueError:
            return jsonify({"success": False, "message": "Error en estructura de hoja"}), 500
        
        # Actualizar
        ws_users.update_cell(user_row_index, col_pass_idx, hashed_pw)
        ws_users.update_cell(user_row_index, col_cambiar_idx, "TRUE")
        
        logger.info(f"✅ Contraseña reseteada para {email}")
        
        return jsonify({
            "success": True,
            "message": "Contraseña reseteada",
            "password_temporal": password_temporal,
            "nit": user_nit
        })
        
    except Exception as e:
        logger.error(f"Error reseteando contraseña: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route('/api/admin/clientes/toggle-estado', methods=['POST'])
def toggle_estado_cliente():
    """
    ADMIN: Activa/Desactiva una cuenta de cliente
    """
    try:
        data = request.json
        email = str(data.get('email', '')).strip().lower()
        nuevo_estado = str(data.get('estado', 'ACTIVO')).strip().upper()
        
        if not email or nuevo_estado not in ['ACTIVO', 'INACTIVO']:
            return jsonify({"success": False, "message": "Datos inválidos"}), 400
        
        ws_users = sheets_client.get_worksheet("USUARIOS_CLIENTES")
        if not ws_users:
            return jsonify({"success": False, "message": "Hoja no encontrada"}), 500
        
        registros = ws_users.get_all_records()
        user_row_index = None
        
        for i, r in enumerate(registros):
            if str(r.get('EMAIL', '')).lower() == email:
                user_row_index = i + 2
                break
        
        if not user_row_index:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        
        # Obtener índice de columna ESTADO
        headers = ws_users.row_values(1)
        try:
            col_estado_idx = headers.index('ESTADO') + 1
        except ValueError:
            return jsonify({"success": False, "message": "Error en estructura de hoja"}), 500
        
        # Actualizar
        ws_users.update_cell(user_row_index, col_estado_idx, nuevo_estado)
        
        logger.info(f"✅ Estado actualizado para {email}: {nuevo_estado}")
        
        return jsonify({"success": True, "message": f"Cuenta {nuevo_estado.lower()}da"})
        
    except Exception as e:
        logger.error(f"Error actualizando estado: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ====================================================================
# HELPER: Data Enrichment
# ====================================================================
def enrich_client_data(user_data):
    """
    Intenta completar dirección y ciudad desde DB_Clientes si faltan.
    """
    nit = user_data.get('nit', '')
    if not nit:
        return user_data

    # Limpiar NIT para búsqueda (quitar 'NIT ' o similares)
    nit_clean = str(nit).upper().replace('NIT', '').strip()
    
    if not user_data.get('direccion') or not user_data.get('ciudad'):
        try:
            ws_db = sheets_client.get_worksheet("DB_Clientes")
            if ws_db:
                records = ws_db.get_all_records()
                # Buscar por coincidencia parcial en IDENTIFICACION
                match = next((r for r in records if nit_clean in str(r.get('IDENTIFICACION', '')).upper()), None)
                
                if match:
                    if not user_data.get('direccion'):
                        user_data['direccion'] = match.get('DIRECCION', '')
                    if not user_data.get('ciudad'):
                        user_data['ciudad'] = match.get('CIUDAD', '')
                    logger.info(f"✅ Datos enriquecidos para {nit} desde DB_Clientes")
        except Exception as e:
            logger.error(f"⚠️ Error enriqueciendo datos desde DB_Clientes: {e}")
            
    return user_data

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

        # Helper para buscar campos con posibles variaciones de acentos/mayúsculas
        def get_field(record, keys):
            for k in keys:
                if k in record and record[k]:
                    return record[k]
            return ""

        response_data = {
            "success": True,
            "requires_password_change": requires_change,
            "user": {
                "nombre": get_field(user_found, ['NOMBRE_EMPRESA', 'Nombre Empresa', 'Cliente', 'CLIENTE']), 
                "nombre_contacto": get_field(user_found, ['NOMBRE_CONTACTO', 'Contacto', 'Nombre Contacto']),
                "email": email,
                "nit": get_field(user_found, ['NIT_EMPRESA', 'NIT', 'Nit']),
                "direccion": get_field(user_found, ['DIRECCION', 'DIRECCIÓN', 'Direccion', 'Dirección', 'direccion']),
                "ciudad": get_field(user_found, ['CIUDAD', 'Ciudad', 'ciudad']),
                "rol": "Cliente",
                "tipo": "CLIENTE"
            }
        }
        
        # Enriquecer datos antes de enviar
        response_data['user'] = enrich_client_data(response_data['user'])

        return jsonify(response_data)

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

        # Helper para buscar campos con posibles variaciones
        def get_field(record, keys):
            for k in keys:
                if k in record and record[k]:
                    return record[k]
            return ""

        # Return user info for auto-login
        response_data = {
            "success": True, 
            "message": "Contraseña actualizada correctamente.",
            "user": {
                "nombre": get_field(user_found, ['NOMBRE_EMPRESA', 'Nombre Empresa', 'Cliente', 'CLIENTE']),
                "nombre_contacto": get_field(user_found, ['NOMBRE_CONTACTO', 'Contacto', 'Nombre Contacto']),
                "email": email,
                "nit": get_field(user_found, ['NIT_EMPRESA', 'NIT', 'Nit']),
                "direccion": get_field(user_found, ['DIRECCION', 'DIRECCIÓN', 'Direccion', 'Dirección', 'direccion']),
                "ciudad": get_field(user_found, ['CIUDAD', 'Ciudad', 'ciudad']),
                "rol": "Cliente",
                "tipo": "CLIENTE"
            }
        }

        # Enriquecer datos antes de enviar
        response_data['user'] = enrich_client_data(response_data['user'])

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error updating password: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
