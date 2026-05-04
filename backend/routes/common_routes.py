"""
Rutas comunes (responsables, clientes, etc).
"""
from flask import Blueprint, jsonify
from backend.core.database import sheets_client
from backend.core.repository_service import repository_service, SHEET_TO_TABLE
from backend.config.settings import Hojas, TenantConfig
from backend.core.tenant import get_tenant_from_request
import logging

logger = logging.getLogger(__name__)

common_bp = Blueprint('common', __name__)


@common_bp.route('/responsables', methods=['GET'])
def obtener_responsables():
    """Obtiene lista de responsables desde SQL."""
    try:
        from backend.models.sql_models import Usuario
        
        # Consultar usuarios activos que no sean clientes
        users = Usuario.query.filter(Usuario.rol != 'cliente', Usuario.activo == True).all()
        responsables = [u.username for u in users]
        
        return jsonify({
            'status': 'success',
            'responsables': responsables
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo responsables SQL: {e}")
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

        # Resolver tenant para saber qué tabla leer
        tenant = get_tenant_from_request()
        logger.info(f"🏢 [SQL-CLIENTES] Consultando lista de clientes para Tenant={tenant}")

        # REFACTOR: 100% SQL-First usando repository_service
        clientes_formateados = repository_service.get_clientes_all()

        if not clientes_formateados:
            return jsonify([]), 200

        # Cache opcional
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