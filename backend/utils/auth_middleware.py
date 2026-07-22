import os
import jwt
import logging
from functools import wraps
from flask import session, jsonify, request, current_app

logger = logging.getLogger(__name__)

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
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        secret = os.environ.get('JWT_PWA_SECRET')
        if not secret:
            try:
                secret = current_app.config.get('JWT_PWA_SECRET') or current_app.config.get('SECRET_KEY')
            except Exception:
                secret = None

        if not secret:
            logger.error('[AUTH] JWT_PWA_SECRET no configurada en el sistema')
            return None

        return jwt.decode(token, secret, algorithms=['HS256'])
    return None

def obtener_identidad_segura(req):
    """
    Extrae la identidad (user, role) desde el header Authorization (JWT) o la sesión de Flask.
    Registra una advertencia si no se encuentra autenticación válida.
    """
    user = None
    role = None

    # 1. Intentar JWT
    try:
        payload = decode_pwa_token(req)
        if payload:
            user = payload.get('username') or payload.get('user')
            role = payload.get('rol') or payload.get('role')
    except Exception as e:
        logger.warning('[AUTH] Error decodificando JWT en %s: %s', req.path, e)

    # 2. Fallback a sesión de Flask si no hay JWT
    if not user and 'user' in session:
        user = session.get('user')
        role = session.get('role')

    # 3. Log explicativo si no hay credenciales válidas
    if not user:
        logger.warning('[AUTH] Fallo de autenticación en %s: No hay JWT válido ni sesión activa', req.path)
        logger.warning('[AUTH] Petición a %s rechazada. Authorization Header presente: %s', req.path, 'Authorization' in req.headers)
        return None, None

    return user, role

def require_role(allowed_roles_input):
    """
    Examines the current user's role obtained via obtener_identidad_segura with strict UPPERCASE normalization.
    allowed_roles_input: A list of strings or a single role string. 
    Accepts both flat lists and our predefined constants.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user, raw_role = obtener_identidad_segura(request)
            
            if not user or not raw_role:
                return jsonify({'status': 'error', 'message': 'No autorizado'}), 401
            
            import unicodedata
            
            # 2. Extract user's role and normalize (Accents removed + UPPERCASE + strip)
            raw_role_str = str(raw_role).strip().upper() # ⚡ ALWAYS UPPERCASE
            user_role = ''.join((c for c in unicodedata.normalize('NFD', raw_role_str) if unicodedata.category(c) != 'Mn'))
            
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
                'status': 'error', 
                'message': f'Acceso denegado: permisos insuficientes para el rol {user_role}.'
            }), 403
            
        return decorated_function
    return decorator
