# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
import os
import logging
import re
from sqlalchemy import text
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_JEFES
from backend.services.wo_sync_service import (
    WoSyncService,
    WoSyncError,
    SincronizacionVaciaError,
    CaidaAnomalaError,
    WoSyncConfigError,
)

wo_bp = Blueprint('wo', __name__)
logger = logging.getLogger(__name__)


def _mask_token(token):
    """
    Enmascara un token/API key para logging seguro: NUNCA se imprime la
    clave completa (ni la recibida ni la esperada) en logs, que en Render
    quedan en texto plano y accesibles a cualquiera con acceso al panel.
    """
    if not token:
        return "(vacío)"
    token = str(token)
    return f"{token[:4]}***" if len(token) > 4 else "***"


# ====================================================================
# UTILIDADES DE NORMALIZACIÓN
# ====================================================================

def limpiar_codigo_wo(c):
    if not c:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(c).upper().strip())


def normalizar_referencia(codigo):
    """
    Extrae la parte numérica final de cualquier código.
    Reglas:
      - ANILLO9735   -> 9735
      - FR-5002B     -> 5002
      - FR-9714      -> 9714
      - MT5007R      -> 5007
      - 513075       -> 513075  (número puro, se retorna completo)
      - CAR-9890     -> 9890
    """
    if not codigo:
        return ""
    t = str(codigo).strip()
    numeros = re.findall(r'\d+', t)
    return numeros[-1] if numeros else ""


# ====================================================================
# ENDPOINT: RECIBIR DATOS DESDE EL AGENTE LOCAL WO
# ====================================================================

@wo_bp.route('/api/wo/recibir_datos', methods=['POST'])
def recibir_datos():
    """
    Recibe datos sincronizados desde el agente local de World Office.
    Thin controller: valida la API key, delega en WoSyncService.recibir_datos
    y traduce el resultado/excepción a jsonify + status code.
    """
    api_key_header = request.headers.get('X-API-Key')
    api_key_env = os.environ.get('WO_SYNC_API_KEY')

    if not api_key_env:
        logger.error("❌ Variable de entorno WO_SYNC_API_KEY no configurada en el servidor.")
        return jsonify({"success": False, "error": "Configuración de seguridad incompleta"}), 500

    if api_key_header != api_key_env:
        logger.warning(f"⚠️ Sincronización WO no autorizada. X-API-Key recibida: {_mask_token(api_key_header)}")
        return jsonify({"success": False, "error": "No autorizado. API Key inválida o ausente."}), 401

    try:
        payload = request.json or {}
        resultado = WoSyncService.recibir_datos(payload)
        return jsonify(resultado), 200

    except SincronizacionVaciaError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except WoSyncError as e:
        logger.error(f"❌ Error de negocio en recibir_datos de WO: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        logger.error(f"❌ Error en endpoint recibir_datos de WO: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ====================================================================
# ENDPOINT: UNIFICAR INVENTARIO WO -> DB_PRODUCTOS
# ====================================================================

@wo_bp.route('/api/wo/unificar', methods=['POST'])
@require_role(ROL_ADMINS + ROL_JEFES + ['AUXILIAR INVENTARIO', 'METALS_ADMIN'])
def unificar_inventario_wo():
    """
    Dispara el UPSERT masivo de inventario_wo -> db_productos. Toda la lógica
    de negocio/SQL vive en la capa de servicio/repositorio (regla FRITECH V4.5:
    cero SQL/lógica en rutas) -- ver InventarioService.unificar_inventario_wo
    y ProductoRepository.upsert_productos_wo.
    """
    try:
        from backend.core.sql_database import db
        from backend.services.inventario_service import InventarioService

        resultado = InventarioService.unificar_inventario_wo()
        status_code = 200 if resultado.get("success") else 400
        return jsonify(resultado), status_code

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en unificar WO: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ====================================================================
# ENDPOINT: RECIBIR DATOS COMERCIALES (VENTAS Y PEDIDOS) DESDE WO
# ====================================================================

@wo_bp.route('/api/wo/recibir_comercial', methods=['POST'])
def recibir_comercial():
    """
    Recibe la sincronización de ventas, pedidos y devoluciones (año actual) desde
    World Office. Thin controller: valida el token, delega en
    WoSyncService.recibir_comercial (parseo de chunks + staging + circuit
    breaker + volcado atómico a producción) y traduce el resultado/excepción.
    """
    api_key_header = request.headers.get('X-API-Key') or request.headers.get('X-Sync-Token')
    api_key_env = os.environ.get('SYNC_TOKEN') or os.environ.get('WO_SYNC_API_KEY')

    if not api_key_env or api_key_header != api_key_env:
        logger.warning(f"⚠️ Sincronización comercial WO no autorizada. Token recibido: {_mask_token(api_key_header)}")
        return jsonify({"success": False, "error": "No autorizado. Token de sincronización inválido o ausente."}), 401

    try:
        payload = request.json or {}
        detalles = WoSyncService.recibir_comercial(payload)
        return jsonify({
            "success": True,
            "message": f"Sincronización comercial del lote {detalles['lote_actual']}/{detalles['total_lotes']} exitosa",
            "detalles": detalles
        }), 200

    except (SincronizacionVaciaError, CaidaAnomalaError) as e:
        logger.error(f"❌ Circuit breaker activado en recibir_comercial: {e}")
        return jsonify({"success": False, "error": str(e)}), 422
    except WoSyncError as e:
        logger.error(f"❌ Error de negocio en recibir_comercial de WO: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        logger.error(f"❌ Transacción fallida en recepción de chunk comercial. Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ====================================================================
# ENDPOINT: DISPARAR SINCRONIZACIÓN AUTOMÁTICA DESDE SERVIDOR LOCAL / PLANTA
# ====================================================================

@wo_bp.route('/api/wo/sincronizar_automatica', methods=['GET', 'POST'])
def sincronizar_automatica():
    """
    Ruta segura para disparar la sincronización comercial desde World Office de
    forma autónoma. Soporta POST (header X-Sync-Token) y GET (parámetro query
    ?token=...). Thin controller: valida el token, delega en
    WoSyncService.sincronizar_automatica (extracción pyodbc + persistencia) y
    traduce el resultado/excepción.
    """
    token_recibido = request.args.get('token') or request.headers.get('X-Sync-Token')
    token_esperado = os.getenv('SYNC_TOKEN')

    if token_esperado is None:
        logger.error("❌ Variable de entorno SYNC_TOKEN no configurada en el servidor (es None).")
        return jsonify({"status": "error", "message": "Error de configuración de seguridad: SYNC_TOKEN es None"}), 500

    if token_recibido != token_esperado:
        logger.warning(f"⚠️ Intento de sincronización automática no autorizado. Token recibido: {_mask_token(token_recibido)}")
        return jsonify({"status": "error", "message": "No autorizado. Token de sincronización inválido."}), 403

    try:
        resultado = WoSyncService.sincronizar_automatica()
        return jsonify({
            "status": "success",
            "message": "Sincronización completada",
            "registros": resultado["registros"]
        }), 200

    except WoSyncConfigError as e:
        logger.error(f"❌ Error de configuración en sincronizar_automatica: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    except WoSyncError as e:
        logger.error(f"❌ Error en sincronizar_automatica: {e}")
        return jsonify({"status": "error", "message": f"Falla en sincronización: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"❌ Error en sincronizar_automatica: {e}")
        return jsonify({"status": "error", "message": f"Falla en sincronización: {str(e)}"}), 500


# ====================================================================
# ENDPOINT: AUDITORÍA DE DATOS COMERCIALES EN DB_VENTAS
# ====================================================================

@wo_bp.route('/api/wo/auditoria_comercial', methods=['GET'])
@require_role(ROL_ADMINS)
def auditoria_comercial():
    """
    Ruta pura de auditoría para depurar los datos de la tabla db_ventas.
    Agrupa los resultados y retorna un JSON con la cantidad de ventas y pedidos por año.
    No realiza ninguna sincronización ni proceso pesado.
    """
    try:
        from backend.core.sql_database import db
        from backend.models.sql_models import RawVentas
        from sqlalchemy import func

        resultados = db.session.query(
            func.extract('year', RawVentas.fecha).label('anio'),
            RawVentas.clasificacion,
            func.count(RawVentas.id).label('total')
        ).group_by(
            func.extract('year', RawVentas.fecha),
            RawVentas.clasificacion
        ).all()

        data = {}
        for r in resultados:
            if r.anio is None:
                continue

            anio = str(int(r.anio))
            clasif = str(r.clasificacion).lower().strip()

            if anio not in data:
                data[anio] = {"ventas": 0, "pedidos": 0}

            if clasif == 'venta':
                data[anio]["ventas"] += r.total
            elif clasif == 'pedido':
                data[anio]["pedidos"] += r.total

        return jsonify(data), 200

    except Exception as e:
        logger.error(f"❌ Error en auditoria_comercial: {e}")
        return jsonify({"error": str(e)}), 500


# ====================================================================
# ENDPOINT: AUDITORÍA MENSUAL DE DATOS COMERCIALES
# ====================================================================

@wo_bp.route('/api/wo/auditoria_mensual', methods=['GET'])
@require_role(ROL_ADMINS)
def auditoria_mensual():
    """
    Ruta pura de auditoría para diagnosticar la carga mensual de db_ventas.
    Retorna la cantidad de ventas y pedidos agrupados por año y mes.
    """
    try:
        from backend.core.sql_database import db
        from backend.models.sql_models import RawVentas
        from sqlalchemy import func

        resultados = db.session.query(
            func.extract('year', RawVentas.fecha).label('anio'),
            func.extract('month', RawVentas.fecha).label('mes'),
            RawVentas.clasificacion,
            func.count(RawVentas.id).label('total')
        ).group_by(
            func.extract('year', RawVentas.fecha),
            func.extract('month', RawVentas.fecha),
            RawVentas.clasificacion
        ).all()

        data = {}
        for r in resultados:
            if r.anio is None or r.mes is None:
                continue

            anio = str(int(r.anio))
            mes = f"{int(r.mes):02d}"
            clasif = str(r.clasificacion).lower().strip()

            if anio not in data:
                data[anio] = {}

            if mes not in data[anio]:
                data[anio][mes] = {"ventas": 0, "pedidos": 0}

            if clasif == 'venta':
                data[anio][mes]["ventas"] += r.total
            elif clasif == 'pedido':
                data[anio][mes]["pedidos"] += r.total

        for anio in data:
            data[anio] = dict(sorted(data[anio].items()))

        return jsonify(data), 200

    except Exception as e:
        logger.error(f"❌ Error en auditoria_mensual: {e}")
        return jsonify({"error": str(e)}), 500


# ====================================================================
# ENDPOINTS: FLAG DE SINCRONIZACIÓN COMERCIAL DESDE DASHBOARD
# ====================================================================

@wo_bp.route('/api/wo/solicitar_sync', methods=['POST'])
def solicitar_sync():
    """
    Endpoint para activar o desactivar el flag de sincronización comercial.
    """
    try:
        import json

        payload = request.get_json() if request.is_json else {}
        # Por defecto, si no se especifica, se asume que se solicita la sync
        estado = payload.get("sync_pendiente", True)

        # Guardar el flag en un archivo temporal o en el directorio base
        data_dir = os.path.join(os.getcwd(), 'data')
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, 'sync_comercial_flag.json')

        with open(file_path, 'w') as f:
            json.dump({"sync_pendiente": estado}, f)

        logger.info(f"Flag de sincronización actualizado: sync_pendiente={estado}")
        return jsonify({"success": True, "message": f"Sincronización {'solicitada' if estado else 'limpiada'} exitosamente"}), 200

    except Exception as e:
        logger.error(f"❌ Error al solicitar sincronización: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@wo_bp.route('/api/wo/verificar_sync', methods=['GET'])
def verificar_sync():
    """
    Ruta que el Agente Local consultará para saber si debe extraer los datos.
    """
    try:
        import json
        file_path = os.path.join(os.getcwd(), 'data', 'sync_comercial_flag.json')

        if not os.path.exists(file_path):
            return jsonify({"sync_pendiente": False}), 200

        with open(file_path, 'r') as f:
            data = json.load(f)

        return jsonify(data), 200
    except Exception as e:
        logger.error(f"❌ Error al verificar flag de sincronización: {e}")
        return jsonify({"sync_pendiente": False, "error": str(e)}), 500

# ====================================================================
# ENDPOINT: SINCRONIZAR CARTERA DESDE WO
# ====================================================================

# Umbral del circuit breaker: si la cartera recibida cae por debajo de este
# porcentaje de la cartera actual en cartera_wo, se aborta el DELETE de
# obsoletos (aunque se procese el upsert) para no borrar facturas vigentes
# ante una extraccion parcial/rota en el agente local.
UMBRAL_CAIDA_ANOMALA_CARTERA = 0.5


@wo_bp.route('/api/wo/sincronizar_cartera', methods=['POST'])
def sincronizar_cartera():
    """Recibe y procesa el estado de cartera desde el Agente WO con chunking."""
    api_key_header = request.headers.get('X-API-Key') or request.headers.get('X-Sync-Token')
    api_key_env = os.environ.get('SYNC_TOKEN') or os.environ.get('WO_SYNC_API_KEY')

    if not api_key_env or api_key_header != api_key_env:
        return jsonify({"success": False, "error": "No autorizado."}), 401

    try:
        from decimal import Decimal, InvalidOperation

        payload = request.json or {}
        datos = payload.get("datos", payload) if isinstance(payload, dict) else payload

        if not isinstance(datos, list):
            datos = [datos] if datos else []

        from backend.core.sql_database import db
        from backend.repositories.ventas_repository import VentasRepository

        # Validar y limpiar datos
        datos_limpios = []
        for item in datos:
            if not item.get('documento'):
                continue

            try:
                saldo_documento = Decimal(str(item.get('saldo_documento', '0')))
            except InvalidOperation:
                saldo_documento = Decimal('0')

            datos_limpios.append({
                'documento': str(item.get('documento')).strip(),
                'identificacion': str(item.get('identificacion')).strip(),
                'nombre': str(item.get('nombre') or 'Desconocido').strip(),
                'vendedor': str(item.get('vendedor') or '').strip(),
                'moneda': str(item.get('moneda') or '').strip(),
                'empresa': str(item.get('empresa') or '').strip(),
                'fecha_emision': item.get('fecha_emision') or None,
                'fecha_vencimiento': item.get('fecha_vencimiento') or None,
                'saldo_documento': saldo_documento
            })

        # Procesamiento por lotes (chunking) de 500 en 500
        BATCH_SIZE = 500
        procesados_totales = 0

        for i in range(0, len(datos_limpios), BATCH_SIZE):
            chunk = datos_limpios[i:i+BATCH_SIZE]
            procesados = VentasRepository.upsert_cartera_wo(chunk)
            procesados_totales += procesados
            logger.info(f"Procesado chunk {i//BATCH_SIZE + 1} de Cartera: {procesados} registros")

        # --- Limpieza de obsoletos ---
        # WO solo extrae documentos con Saldo > 0: una factura que se paga/cruza
        # deja de venir en el payload y el upsert nunca la toca, quedando huerfana
        # con su saldo viejo. Aqui se borra todo lo que no vino en esta extraccion,
        # protegido por un circuit breaker por si la extraccion vino incompleta.
        documentos_vigentes = [d['documento'] for d in datos_limpios]
        count_actual = db.session.execute(text("SELECT COUNT(*) FROM cartera_wo")).scalar() or 0
        eliminados = 0
        if count_actual > 0 and len(documentos_vigentes) < count_actual * UMBRAL_CAIDA_ANOMALA_CARTERA:
            logger.critical(
                f"❌ [CRÍTICO] Caída anómala en la sincronización de cartera: "
                f"recibidos={len(documentos_vigentes)} vs actuales={count_actual} "
                f"(umbral {UMBRAL_CAIDA_ANOMALA_CARTERA:.0%}). Se omite el borrado de obsoletos."
            )
        else:
            eliminados = VentasRepository.eliminar_cartera_wo_obsoleta(documentos_vigentes)
            if eliminados:
                logger.info(f"Cartera: {eliminados} facturas obsoletas (pagadas/cruzadas) eliminadas de cartera_wo")

        return jsonify({
            "success": True,
            "message": "Cartera sincronizada correctamente",
            "procesados": procesados_totales,
            "eliminados_obsoletos": eliminados
        }), 200

    except Exception as e:
        logger.error(f"Error en sincronizar_cartera: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ====================================================================
# ENDPOINT: SINCRONIZAR CLIENTES (TERCEROS) DESDE WO
# ====================================================================

# Umbral del circuit breaker: si el catalogo recibido cae por debajo de este
# porcentaje del catalogo actual en db_clientes, se aborta para no perder
# clientes existentes ante una extraccion parcial/rota en el agente local.
UMBRAL_CAIDA_ANOMALA_CLIENTES = 0.5


@wo_bp.route('/api/wo/sincronizar_clientes', methods=['POST'])
def sincronizar_clientes():
    """Recibe y procesa el catalogo de clientes/terceros desde el Agente WO.
    Persiste vía ClienteRepository.upsert_clientes_wo (UPSERT por identificacion/NIT).
    """
    api_key_header = request.headers.get('X-API-Key') or request.headers.get('X-Sync-Token')
    api_key_env = os.environ.get('SYNC_TOKEN') or os.environ.get('WO_SYNC_API_KEY')

    if not api_key_env or api_key_header != api_key_env:
        logger.warning(f"⚠️ Sincronización de clientes WO no autorizada. Token recibido: {_mask_token(api_key_header)}")
        return jsonify({"success": False, "error": "No autorizado. Token de sincronización inválido o ausente."}), 401

    try:
        payload = request.json or {}
        datos = payload.get("datos", payload) if isinstance(payload, dict) else payload

        if not isinstance(datos, list):
            datos = [datos] if datos else []

        logger.info(f"Datos de clientes WO recibidos: {len(datos)} registros")

        # --- Circuit Breaker: catálogo vacío o caída anómala frente al actual ---
        from backend.core.sql_database import db
        from backend.repositories.cliente_repository import ClienteRepository

        if len(datos) == 0:
            logger.critical("❌ [CRÍTICO] El catálogo de clientes recibido de WO viene vacío. Se aborta la sincronización.")
            return jsonify({
                "success": False,
                "error": "El catálogo de clientes recibido está vacío."
            }), 422

        count_actual = db.session.execute(text("SELECT COUNT(*) FROM db_clientes")).scalar() or 0
        if count_actual > 0 and len(datos) < count_actual * UMBRAL_CAIDA_ANOMALA_CLIENTES:
            logger.critical(
                f"❌ [CRÍTICO] Caída anómala en la sincronización de clientes: "
                f"recibidos={len(datos)} vs actuales={count_actual} (umbral {UMBRAL_CAIDA_ANOMALA_CLIENTES:.0%}). "
                "Se aborta para no perder clientes existentes."
            )
            return jsonify({
                "success": False,
                "error": f"Caída anómala: se recibieron {len(datos)} clientes frente a {count_actual} existentes. "
                         "Verifique la extracción en el agente local."
            }), 422

        # --- Normalización y limpieza ---
        # Cada fila es una direccion/sucursal de un tercero (IdTerceroDireccion
        # de WO), no un cliente unico: un mismo NIT puede repetirse en varias
        # filas con id_direccion_wo distinto (ver Vista_Tabla_Direcciones).
        datos_limpios = []
        for item in datos:
            identificacion = str(item.get('identificacion') or item.get('nit') or '').strip()
            id_direccion_wo_raw = item.get('id_direccion_wo') or item.get('IdTerceroDireccion')
            if not identificacion or id_direccion_wo_raw in (None, ''):
                continue
            try:
                id_direccion_wo = int(id_direccion_wo_raw)
            except (ValueError, TypeError):
                continue

            datos_limpios.append({
                'id_direccion_wo': id_direccion_wo,
                'identificacion':  identificacion[:50],
                'nombre':          str(item.get('nombre') or item.get('razon_social') or '').strip()[:200],
                'direccion':       str(item.get('direccion') or '').strip()[:300],
                'telefonos':       str(item.get('telefonos') or item.get('telefono') or '').strip()[:100],
                'ciudad':          str(item.get('ciudad') or '').strip()[:100],
            })

        procesados = ClienteRepository.upsert_clientes_wo(datos_limpios)

        return jsonify({
            "success": True,
            "message": "Clientes sincronizados correctamente",
            "procesados": procesados
        }), 200

    except Exception as e:
        logger.error(f"Error en sincronizar_clientes: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
