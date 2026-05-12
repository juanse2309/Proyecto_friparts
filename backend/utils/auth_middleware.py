from functools import wraps
from flask import session, jsonify

# Define allowed roles constants (UPPERCASE for strict matching)
ROL_ADMINS = ['ADMIN', 'ADMINISTRACION', 'ADMINISTRADOR', 'GERENCIA']
ROL_JEFES = ['JEFE ALMACEN', 'JEFE INYECCION', 'JEFE PULIDO', 'JEFE DE PLANTA']
ROL_COMERCIALES = ['COMERCIAL', 'COMERCIAL FRIMETALS', 'STAFF FRIMETALS']
ROL_OPERARIOS = ['INYECCION', 'PULIDO', 'ALISTAMIENTO', 'ENSAMBLE', 'AUXILIAR INVENTARIO']

def require_role(allowed_roles_input):
    """
    Examines the current user's session role with strict UPPERCASE normalization.
    allowed_roles_input: A list of strings or a single role string. 
    Accepts both flat lists and our predefined constants.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Check if user is logged in
            if 'role' not in session:
                return jsonify({
                    'success': False, 
                    'error': 'No auth token/session found', 
                    'needs_login': True
                }), 401
            
            import unicodedata
            
            # 2. Extract user's role and normalize (Accents removed + UPPERCASE)
            raw_role = str(session.get('role', '')).upper() # ⚡ ALWAYS UPPERCASE
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
            
            # 5. Check specific access
            if user_role in allowed_roles:
                return f(*args, **kwargs)
            
            return jsonify({
                'success': False, 
                'error': f'Insufficient permissions. Role {user_role} is not authorized for this action.',
                'needs_login': False
            }), 403
            
        return decorated_function
    return decorator
