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

def _obtener_jwt_secrets():
    """
    Retorna la lista ordenada de posibles claves secretas para decodificar JWT,
    desduplicando y omitiendo valores nulos o vacíos.
    """
    candidatas = []
    
    # 1. Variable de entorno explícita
    env_secret = os.environ.get('JWT_PWA_SECRET')
    if env_secret:
        candidatas.append(env_secret)

    # 2. Claves en la aplicación Flask
    try:
        cfg_pwa = current_app.config.get('JWT_PWA_SECRET')
        if cfg_pwa:
            candidatas.append(cfg_pwa)
        cfg_secret = current_app.config.get('SECRET_KEY')
        if cfg_secret:
            candidatas.append(cfg_secret)
        if getattr(current_app, 'secret_key', None):
            candidatas.append(current_app.secret_key)
    except Exception:
        pass

    # 3. Clave por defecto utilizada en auth_routes.py
    candidatas.append('super_secret_pwa_key_2026')

    # Desduplicar preservando orden de prioridad
    unicas = []
    for s in candidatas:
        if s and s not in unicas:
            unicas.append(s)

    return unicas

def decode_pwa_token(request):
    """
    Extrae y decodifica el token JWT del header Authorization o del parámetro query ('token'/'pwa_token')
    probando secuencialmente contra las claves secretas configuradas.
    """
    token = None
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
    elif request.args.get('token'):
        token = request.args.get('token')
    elif request.args.get('pwa_token'):
        token = request.args.get('pwa_token')
    elif request.args.get('jwt'):
        token = request.args.get('jwt')

    if not token:
        return None

    secrets = _obtener_jwt_secrets()
    for secret in secrets:
        try:
            return jwt.decode(token, secret, algorithms=['HS256'])
        except jwt.InvalidSignatureError:
            continue
        except Exception as e:
            logger.warning(f"[AUTH] Error decodificando JWT en {request.path}: {e}")
            return None

    logger.warning(f"[AUTH] Firma de JWT no válida con ninguna clave configurada en {request.path}")
    return None

def _obtener_usuario_activo():
    """
    Extrae la identidad del usuario activo desde el token JWT o la sesión Flask.
    """
    user, _ = obtener_identidad_segura(request)
    return user

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
            user = payload.get('username') or payload.get('user') or payload.get('nombre')
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
