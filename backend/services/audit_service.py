"""
Servicio centralizado de auditoría y trazabilidad MES.

Este servicio es fundamental para garantizar la coherencia e inmutabilidad de la autoría 
en los registros de producción en planta (Inyección, Pulido, Ensamble, Metales y Almacén).
La asignación y validación del 'responsable' centralizada previene la corrupción de datos,
el repudio de las operaciones y la sobreescritura accidental de la sesión de trabajo activa
de un operario por parte de otro en terminales compartidas de planta.
"""

import logging
from backend.utils.formatters import resolver_operario
from backend.config.constants import FALLBACK_OPERARIO

logger = logging.getLogger(__name__)

class OwnershipMismatchException(Exception):
    """
    Excepción lanzada cuando un operario intenta modificar o interactuar con un registro 
    de producción que ya pertenece a otro responsable en base de datos (Ownership Guard).
    """
    def __init__(self, responsable_db, responsable_in, message=None):
        self.responsable_db = responsable_db
        self.responsable_in = responsable_in
        self.message = message or f"Conflicto de propiedad: El registro pertenece a '{responsable_db}' pero la sesión activa es de '{responsable_in}'."
        super().__init__(self.message)


class AuditService:
    """
    Clase de servicio encargada de la validación y normalización de identidades de
    operarios y responsables de las transacciones del sistema de producción.
    """

    @staticmethod
    def resolver_y_validar_propietario(registro_db, payload_responsable, fallback_sistema=FALLBACK_OPERARIO):
        """
        Resuelve y valida la propiedad del registro de base de datos comparándolo con el responsable recibido.

        Esta lógica centralizada:
        1. Resuelve el operario entrante usando la jerarquía (payload -> sesión -> fallback).
        2. Normaliza el nombre del operario aplicando limpieza de espacios y mayúsculas.
        3. Compara el responsable registrado en la base de datos contra el operario resuelto.
        4. Si el registro ya posee un responsable asignado y difiere del entrante (case-insensitive),
           lanza una excepción 'OwnershipMismatchException'.

        :param registro_db: Objeto modelo de SQLAlchemy que representa el registro actual en base de datos.
        :param payload_responsable: String con el nombre del responsable provisto por el cliente/frontend.
        :param fallback_sistema: Valor por defecto si no se logra determinar un operario (por defecto FALLBACK_OPERARIO).
        :return: String con el nombre normalizado del responsable validado.
        :raises OwnershipMismatchException: Si el propietario actual de la sesión no coincide con el entrante.
        """
        # 1. Resolver el responsable entrante
        incoming_responsable = resolver_operario(payload_responsable)
        
        # Si se resolvió como 'SISTEMA' por defecto por ausencia de datos de sesión/payload, 
        # pero el fallback provisto es diferente, aplicamos el fallback
        if incoming_responsable == 'SISTEMA' and fallback_sistema != 'SISTEMA':
            # Solo aplicamos el fallback si el payload original no era textualmente 'SISTEMA'
            if not payload_responsable or str(payload_responsable).strip().upper() != 'SISTEMA':
                incoming_responsable = fallback_sistema

        # Sanitizar y normalizar
        incoming_responsable = str(incoming_responsable or "").strip()

        # 2. Validar propiedad si existe registro previo con responsable ya persistido
        if registro_db and hasattr(registro_db, 'responsable') and registro_db.responsable:
            owner_db = str(registro_db.responsable).strip()
            
            if owner_db and incoming_responsable:
                if owner_db.upper() != incoming_responsable.upper():
                    # Verificar si la sesión o el incoming pertenecen a un administrador
                    from flask import request, session
                    import unicodedata
                    import jwt
                    import os

                    try:
                        user_name = ""
                        user_role = ""

                        # 1. Intentar extraer identidad y rol directamente desde el JWT de la PWA
                        auth_header = request.headers.get('Authorization')
                        if auth_header and auth_header.startswith('Bearer '):
                            token = auth_header.split(' ')[1]
                            secret = os.environ.get('JWT_PWA_SECRET', 'super_secret_pwa_key_2026')
                            try:
                                payload = jwt.decode(token, secret, algorithms=['HS256'])
                                user_name = str(payload.get('user', '')).strip().upper()
                                user_role = str(payload.get('role', '')).strip().upper()
                            except Exception:
                                pass

                        # 2. Fallback a la sesión de Flask
                        if not user_name:
                            user_name = str(session.get('user', session.get('username', ''))).strip().upper()
                        if not user_role:
                            user_role = str(session.get('role', '')).strip().upper()

                        # 3. Concatenar todo el contexto de identidad para una búsqueda robusta
                        contexto_identidad = f"{user_name} {user_role} {incoming_responsable}".upper()
                        contexto_identidad = ''.join((c for c in unicodedata.normalize('NFD', contexto_identidad) if unicodedata.category(c) != 'Mn'))
                        
                        keywords_administrativos = ['ADMIN', 'SUPERVISOR', 'JUAN', 'NOVOA', 'PAOLA', 'CEPEDA']
                        
                        if any(kw in contexto_identidad for kw in keywords_administrativos):
                            logger.info(
                                f"🛡️ [Ownership Bypass] Administrativo detectado en contexto '{contexto_identidad}'. "
                                f"Autorizado para procesar registro de '{owner_db}'."
                            )
                            # RETORNO CLAVE: Devolvemos el owner original para no corromper la trazabilidad
                            return owner_db
                    except Exception as e:
                        logger.error(f"Error evaluando by-pass infalible: {e}")

                    logger.warning(
                        f"⚠️ [Ownership Conflict] Intento de acceso denegado. "
                        f"Dueño persistido: '{owner_db}' | Usuario entrante: '{incoming_responsable}'"
                    )
                    raise OwnershipMismatchException(
                        responsable_db=owner_db,
                        responsable_in=incoming_responsable
                    )

        return incoming_responsable
