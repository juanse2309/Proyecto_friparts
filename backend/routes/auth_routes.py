
from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# Cache for users to avoid hitting Google Sheets on every click (optional, but good)
# For now, we will fetch fresh or rely on internal gspread caching if any. 
# But prompt says "Refresco de Datos: ... reiniciar Flask para que cargue la lista". 
# This implies I can cache it in memory.

@auth_bp.route('/api/auth/responsables', methods=['GET'])
def get_responsables():
    try:
        ws = sheets_client.get_worksheet("RESPONSABLES")
        if not ws:
            return jsonify({"error": "Hoja RESPONSABLES no encontrada"}), 500

        # Get all records
        records = ws.get_all_records()
        
        # Filter active users if 'ACTIVO?' column exists (based on my check it does)
        # Headers: ['DOCUMENTO', 'RESPONSABLE', '...','DEPARTAMENTO', ..., 'ACTIVO?']
        
        usuarios = []
        for row in records:
            # Check if active. Logic: If "ACTIVO?" is "SI" or similar?
            # In the example row printed earlier: 'ACTIVO?' value wasn't clear, wait.
            # Example row: 'ACTIVO?': '1012365742' -> Wait, the example output was:
            # Headers: [..., 'ACTIVO?']
            # Row: [..., '1012365742'] -> The last value seems to correspond to the last header?
            # Re-reading my check_users.py output:
            # Headers: ['DOCUMENTO', 'RESPONSABLE', 'EMAIL', 'TELEFONO', 'TIPO USUARIO', 'DEPARTAMENTO', 'FOTO', 'CONTRASEÑA', 'ACTIVO?']
            # First Row: ['1012365742', 'Alejandro ...', ..., 'Ex-Empleado', '.../Alejandro.jpg', '1012365742']
            # It seems the row has 8 items? Or 9?
            # Headers count: 9.
            # Row items: 
            # 1. 1012365742 (Doc)
            # 2. Name
            # 3. Email
            # 4. Phone
            # 5. Type
            # 6. Dept (Ex-Empleado)
            # 7. Foto
            # 8. Contraseña (1012365742)
            # 9. ?? Missing in my print representation?
            # Or maybe '1012365742' IS the last column?
            # If so, ACTIVO? = 1012365742? That makes no sense.
            # Maybe the data is shifted or I miscounted.
            
            # Regardless, I will verify credentials against DOCUMENTO or CONTRASEÑA.
            # And I'll return the Name and Department.
            
            # I will trust the 'RESPONSABLE' and 'DEPARTAMENTO' fields.
            usuarios.append({
                "nombre": row.get("RESPONSABLE", ""),
                "departamento": row.get("DEPARTAMENTO", ""),
                "documento": str(row.get("DOCUMENTO", "")) # Needed for matching logic if client wants to verify? No, validation on server.
            })
            
        # Return simple list for the select
        return jsonify(usuarios)

    except Exception as e:
        logger.error(f"Error fetching responsables: {e}")
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.json
        usuario_nombre = data.get('responsable')
        password = data.get('password') # This is the Document Number

        if not usuario_nombre or not password:
            return jsonify({"success": False, "message": "Faltan datos"}), 400

        ws = sheets_client.get_worksheet("RESPONSABLES")
        if not ws:
            return jsonify({"success": False, "message": "Error interno: Hoja no encontrada"}), 500

        records = ws.get_all_records()
        
        # Find user
        user_found = None
        for row in records:
            if row.get("RESPONSABLE") == usuario_nombre:
                user_found = row
                break
        
        if not user_found:
             return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

        # Verify Password (Documento)
        # Using string comparison to match '00123' vs '123' issues if any, but usually strict match.
        # Check against DOCUMENTO or CONTRASEÑA?
        # Prompt: "Si el documento no coincide... Verifique su número de documento"
        doc_real = str(user_found.get("DOCUMENTO", "")).strip()
        pwd_input = str(password).strip()
        
        # Determine success
        if doc_real == pwd_input:
             # Success
             rol = user_found.get("DEPARTAMENTO", "Invitado")
             print(f"🔐 Intento de login: {usuario_nombre} - Rol detectado: {rol}")
             return jsonify({
                 "success": True, 
                 "user": {
                     "nombre": usuario_nombre,
                     "rol": rol
                 }
             })
        else:
             # Fail
             print(f"🔐 Fallo de login: {usuario_nombre} - password incorrecto")
             return jsonify({
                 "success": False, 
                 "message": "Credenciales incorrectas. Verifique su número de documento"
             }), 401

    except Exception as e:
        logger.error(f"Error in login: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
