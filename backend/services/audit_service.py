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


class ValidadorRequeridoException(Exception):
    """
    Excepción lanzada cuando no se provee ni resuelve una identidad explícita para la validación de calidad.
    """
    def __init__(self, message="Se requiere una identidad explícita para la validación de calidad"):
        self.message = message
        super().__init__(self.message)


class TurnoInvalidoException(Exception):
    """
    Excepción lanzada cuando hora_inicio/hora_fin produce una duración de turno
    imposible (negativa o superior al máximo lógico del área). Síntoma clásico
    de escribir la hora en el campo de 24h sin sumar 12 (ej. 3:20 en vez de
    13:20) — ver auditoría de 2026-08-03 sobre Pulido/Inyección.
    """
    def __init__(self, horas_calculadas, horas_maximas, message=None):
        self.horas_calculadas = horas_calculadas
        self.horas_maximas = horas_maximas
        if message:
            self.message = message
        elif horas_calculadas < 0:
            self.message = (
                f"La hora de fin es anterior a la hora de inicio ({horas_calculadas:.2f}h). "
                f"Verifique si confundió la hora (ej. escribir 3:20 en vez de 13:20)."
            )
        else:
            self.message = (
                f"La duración del turno parece incorrecta ({horas_calculadas:.2f}h, excede el máximo de "
                f"{horas_maximas}h). Verifique si confundió la hora (ej. escribir 3:20 en vez de 13:20)."
            )
        super().__init__(self.message)


class AuditService:
    """
    Clase de servicio encargada de la validación y normalización de identidades de
    operarios y responsables de las transacciones del sistema de producción.
    """

    @staticmethod
    def resolver_y_validar_validador(payload_validador=None, usuario_autenticado=None):
        """
        Resuelve y valida la identidad del usuario que aprueba/valida un registro de producción.
        Firma limpia desacoplada del contexto HTTP: (payload_validador, usuario_autenticado).

        :param payload_validador: Identidad enviada en la solicitud (ej. campo del body/DTO).
        :param usuario_autenticado: Identidad del usuario autenticado extraída en la capa HTTP (routes).
        :return: String con el nombre normalizado del validador.
        :raises ValidadorRequeridoException: Si no se provee una identidad explícita.
        """
        candidato = payload_validador or usuario_autenticado
        if not candidato:
            raise ValidadorRequeridoException("Se requiere una identidad explícita para la validación de calidad")

        validador_resuelto = resolver_operario(candidato)
        if not validador_resuelto or str(validador_resuelto).strip().upper() == 'SISTEMA':
            raise ValidadorRequeridoException("Se requiere una identidad explícita para la validación de calidad")

        return str(validador_resuelto).strip()

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
            
            if owner_db and incoming_responsable and owner_db.upper() != incoming_responsable.upper():
                if AuditService._usuario_autenticado_puede_override():
                    logger.info(
                        f"🛡️ [Ownership Override] Rol autorizado detectado en la sesión activa. "
                        f"Se preserva el propietario original '{owner_db}' (solicitante: '{incoming_responsable}')."
                    )
                    # Se conserva el owner original: no se sobrescribe la autoría del creador,
                    # la trazabilidad de quién ejecutó la validación queda a cargo de validado_por/finalizado_por.
                    return owner_db

                logger.warning(
                    f"⚠️ [Ownership Conflict] Intento de acceso denegado. "
                    f"Dueño persistido: '{owner_db}' | Usuario entrante: '{incoming_responsable}'"
                )
                raise OwnershipMismatchException(
                    responsable_db=owner_db,
                    responsable_in=incoming_responsable
                )

        return incoming_responsable

    @staticmethod
    def _usuario_autenticado_puede_override():
        """
        Determina si el usuario autenticado en la petición HTTP activa (JWT o sesión Flask)
        posee un rol autorizado para omitir el Ownership Guard.

        Evalúa EXCLUSIVAMENTE el rol resuelto por la capa de autenticación centralizada
        (obtener_identidad_segura), nunca texto libre del payload — así un cliente no puede
        forjar el override enviando un 'responsable' que contenga palabras como 'ADMIN'.

        La coincidencia es unidireccional (rol_autorizado in rol_del_usuario): un rol
        autorizado debe aparecer dentro del rol real del usuario. La dirección inversa
        (rol_del_usuario in rol_autorizado) se evita a propósito porque roles de operario
        como 'INYECCION' o 'PULIDO' son substring literal de 'JEFE INYECCION' / 'JEFE PULIDO',
        lo que le daría bypass a cualquier operario común.
        """
        try:
            from flask import request
            from backend.utils.auth_middleware import obtener_identidad_segura, ROLES_VALIDACION_OVERRIDE
            import unicodedata

            _, raw_role = obtener_identidad_segura(request)
            if not raw_role:
                return False

            role_norm = str(raw_role).strip().upper()
            role_norm = ''.join(c for c in unicodedata.normalize('NFD', role_norm) if unicodedata.category(c) != 'Mn')

            return any(r.upper() in role_norm for r in ROLES_VALIDACION_OVERRIDE)
        except Exception as e:
            logger.error(f"Error evaluando permiso de override de propiedad: {e}")
            return False
