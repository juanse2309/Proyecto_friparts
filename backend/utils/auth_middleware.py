from functools import wraps
from flask import session, jsonify

# Define allowed roles constants (UPPERCASE for strict matching)
ROL_ADMINS = ['ADMIN', 'ADMINISTRACION', 'ADMINISTRADOR', 'GERENCIA']
ROL_JEFES = ['JEFE ALMACEN', 'JEFE INYECCION', 'JEFE PULIDO', 'JEFE DE PLANTA', 'JEFE ALISTAMIENTO']
ROL_COMERCIALES = ['COMERCIAL', 'COMERCIAL FRIMETALS', 'STAFF FRIMETALS']
ROL_OPERARIOS = ['INYECCION', 'PULIDO', 'ALISTAMIENTO', 'ENSAMBLE', 'AUXILIAR INVENTARIO']

def decode_pwa_token(request):
    """
    Extrae y decodifica el token JWT del header Authorization si existe.
    Retorna el payload decodificado o None. Lanza excepciones jwt en caso de error.
    """
    import os, jwt
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        secret = os.environ.get('JWT_PWA_SECRET', 'super_secret_pwa_key_2026')
        return jwt.decode(token, secret, algorithms=['HS256'])
    return None

def require_role(allowed_roles_input):
    """
    Examines the current user's session role with strict UPPERCASE normalization.
    allowed_roles_input: A list of strings or a single role string. 
    Accepts both flat lists and our predefined constants.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            import jwt
            
            raw_role = None
            
            # A. Revisar JWT en Header Authorization
            try:
                payload = decode_pwa_token(request)
                if payload:
                    raw_role = payload.get('rol') or payload.get('role')
            except jwt.ExpiredSignatureError:
                return jsonify({'success': False, 'error': 'Token expirado', 'needs_login': True}), 401
            except jwt.InvalidTokenError:
                return jsonify({'success': False, 'error': 'Token inválido', 'needs_login': True}), 401

            # B. Fallback a Sesión de Flask
            if not raw_role and 'role' in session:
                raw_role = session.get('role')
            
            # Si no hay rol por ninguno de los dos métodos, rechazar
            if not raw_role:
                return jsonify({
                    'success': False, 
                    'error': 'No auth token/session found', 
                    'needs_login': True
                }), 401
            
            import unicodedata
            
            # 2. Extract user's role and normalize (Accents removed + UPPERCASE + strip)
            raw_role = str(raw_role).strip().upper() # ⚡ ALWAYS UPPERCASE
            user_role = ''.join((c for c in unicodedata.normalize('NFD', raw_role) if unicodedata.category(c) != 'Mn'))
            
            # 3. Handle input: Convert nested lists (from constants) to a flat list of upper cases
            allowed_roles = []
            if isinstance(allowed_roles_input, list):
                for r in allowed_roles_input:
                    if isinstance(r, list): # handle ROL_ADMINS + ['JEFE']
                        allowed_roles.extend([x.upper() for x in r])
                    else:
                        allowed_roles.append(r.upper())
            else:
                allowed_roles = [str(allowed_roles_input).upper()]

            # 4. Global God Mode: Admins variation always matches
            if user_role in ROL_ADMINS:
                return f(*args, **kwargs)
            
            # 5. Check specific access (flexible/inclusive matching)
            for allowed in allowed_roles:
                if allowed in user_role:
                    return f(*args, **kwargs)
            
            return jsonify({
                'success': False, 
                'error': f'Insufficient permissions. Role {user_role} is not authorized for this action.',
                'needs_login': False
            }), 403
            
        return decorated_function
    return decorator
