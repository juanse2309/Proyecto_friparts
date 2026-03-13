from functools import wraps
from flask import session, jsonify

# Define allowed roles constants
class Roles:
    ADMIN = 'admin'
    ADMINISTRACION = 'administracion'
    ADMINISTRADOR = 'administrador'
    INYECCION = 'inyeccion'
    PULIDO = 'pulido'
    ENSAMBLE = 'ensamble'

def require_role(allowed_roles):
    """
    Examines the current user's session role.
    If the user does not have a session or has an insufficient role, 
    returns a 401/403 Error before hitting the API endpoint.
    allowed_roles: A list of strings with acceptable roles for the endpoint.
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
            
            # 2. Extract user's role and clean accents
            raw_role = str(session.get('role', '')).lower()
            user_role = ''.join((c for c in unicodedata.normalize('NFD', raw_role) if unicodedata.category(c) != 'Mn'))
            
            # 3. Admins intuitively have access to almost everything, 
            #    but we enforce explicit roles here. If ADMIN in allowed_roles, handle it.
            #    For maximum flexibility, we just check if the user's role is in the list.
            admin_roles = [Roles.ADMIN, Roles.ADMINISTRADOR, Roles.ADMINISTRACION]
            
            if Roles.ADMIN in allowed_roles and user_role in admin_roles:
                pass # Admin trying to access admin route
            elif Roles.ADMINISTRADOR in allowed_roles and user_role in admin_roles:
                pass
            elif user_role not in allowed_roles:
                return jsonify({
                    'success': False, 
                    'error': f'Insufficient permissions. Role {user_role} cannot access this resource.',
                    'needs_login': False
                }), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
