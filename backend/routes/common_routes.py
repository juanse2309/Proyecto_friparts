"""
Rutas comunes (responsables, clientes, etc).
"""
from flask import Blueprint, jsonify
from backend.core.database import sheets_client
from backend.config.settings import Hojas, TenantConfig
from backend.core.tenant import get_tenant_from_request
import logging

logger = logging.getLogger(__name__)

common_bp = Blueprint('common', __name__)


@common_bp.route('/responsables', methods=['GET'])
def obtener_responsables():
    """Obtiene lista de responsables."""
    try:
        from backend.app import RESPONSABLES_CACHE, CACHE_TTL_LONG
        import time
        ahora = time.time()

        # 1. Verificar Caché
        if RESPONSABLES_CACHE["data"] and (ahora - RESPONSABLES_CACHE["timestamp"] < RESPONSABLES_CACHE["ttl"]):
            return jsonify(RESPONSABLES_CACHE["data"]), 200

        ws = sheets_client.get_worksheet(Hojas.RESPONSABLES)
        if not ws:
            return jsonify({
                'status': 'success',
                'responsables': ['Juan Pérez', 'María García', 'Carlos López']
            }), 200
        
        registros = ws.get_all_records()
        responsables = [r.get('NOMBRE', '') for r in registros if r.get('NOMBRE')]
        
        resultado = {
            'status': 'success',
            'responsables': responsables
        }

        # 2. Guardar en Caché
        RESPONSABLES_CACHE["data"] = resultado
        RESPONSABLES_CACHE["timestamp"] = ahora

        return jsonify(resultado), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo responsables: {e}")
        return jsonify({
            'status': 'success',
            'responsables': ['Juan Pérez', 'María García']
        }), 200


@common_bp.route('/obtener_clientes', methods=['GET'])
def obtener_clientes():
    """Obtiene lista de clientes (tenant-aware)."""
    try:
        from backend.app import CLIENTES_CACHE
        import time
        ahora = time.time()

        # Resolver tenant para saber qué hoja leer
        tenant = get_tenant_from_request()
        hoja_clientes = TenantConfig.get(tenant, 'CLIENTES')
        logger.info(f"🏢 [DEBUG-CLIENTES] Tenant={tenant} | Hoja={hoja_clientes}")

        ws = sheets_client.get_worksheet(hoja_clientes)
        if not ws:
            return jsonify({
                'status': 'success',
                'clientes': ['Cliente General', 'Cliente Mayorista']
            }), 200
        raw_rows = ws.get_all_values()
        if not raw_rows or len(raw_rows) < 2:
            logger.warning(f"⚠️ Hoja {hoja_clientes} vacía o sin datos")
            return jsonify([]), 200

        headers = [str(h).strip().upper() for h in raw_rows[0]]
        
        # Buscar índices de forma flexible (compatible con Friparts y Frimetals)
        def find_idx(names):
            for name in names:
                if name in headers: return headers.index(name)
            return -1

        idx_nombre = find_idx(["NOMBRE", "CLIENTE", "RAZON SOCIAL", "CLIENTE NOMBRE", "NOMBRE CLIENTE"])
        idx_nit = find_idx(["NIT", "IDENTIFICACION", "IDENTIFICACIÓN", "RUT", "ID", "CEDULA", "NIT/CEDULA"])
        idx_dir = find_idx(["DIRECCION", "DIRECCIÓN", "DOMICILIO"])
        idx_tel = find_idx(["TELEFONOS", "TELÉFONOS", "TELEFONO", "TELÉFONO", "CELULAR", "MOVIL"])
        idx_ciu = find_idx(["CIUDAD", "MUNICIPIO"])

        logger.info(f"📊 [DEBUG-CLIENTES] Hoja={hoja_clientes} → MappedIdxs: Nombre={idx_nombre}, NIT={idx_nit}")

        clientes_formateados = []
        for row in raw_rows[1:]:
            if idx_nombre >= 0 and len(row) > idx_nombre:
                nombre = str(row[idx_nombre]).strip()
                if nombre:
                    clientes_formateados.append({
                        "nombre": nombre,
                        "nit": str(row[idx_nit]).strip() if idx_nit >= 0 and len(row) > idx_nit else "",
                        "direccion": str(row[idx_dir]).strip() if idx_dir >= 0 and len(row) > idx_dir else "",
                        "telefonos": str(row[idx_tel]).strip() if idx_tel >= 0 and len(row) > idx_tel else "",
                        "ciudad": str(row[idx_ciu]).strip() if idx_ciu >= 0 and len(row) > idx_ciu else ""
                    })

        logger.info(f"📊 [DEBUG-CLIENTES] RawRows={len(raw_rows)} | FinalCount={len(clientes_formateados)}")
        if clientes_formateados:
            logger.info(f"🔍 [DEBUG-CLIENTES] Sample: {clientes_formateados[0]}")

        # Solo cachear friparts (lista plana)
        if tenant == 'friparts':
            CLIENTES_CACHE["data"] = clientes_formateados
            CLIENTES_CACHE["timestamp"] = ahora

        return jsonify(clientes_formateados), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo clientes: {e}")
        return jsonify({
            'status': 'success',
            'clientes': ['Cliente General']
        }), 200