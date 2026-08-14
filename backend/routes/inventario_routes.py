"""
Rutas de inventario.
Endpoints REST para operaciones de inventario.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventario_service import inventario_service, InventarioService
from backend.core.base_repository import base_repository
from backend.core.exceptions import AppException
from backend.utils.auth_middleware import require_role, require_login, ROL_ADMINS, ROL_JEFES, ROL_COMERCIALES
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Crear blueprint
inventario_bp = Blueprint('inventario', __name__)

# Roles con acceso a la página "inventario" en el frontend (ver frontend/static/js/modules/auth.js)
ROLES_INVENTARIO = ROL_ADMINS + ROL_JEFES + ['AUXILIAR INVENTARIO', 'METALS_ADMIN']
# crear_producto_dual también se dispara desde el formulario "crear producto
# rápido" de pedidos.js, en la página "pedidos" -- accesible a roles
# comerciales (COMERCIAL/COMERCIAL FRIMETALS/STAFF FRIMETALS) que no viven en
# ROLES_INVENTARIO. Sin este set aparte, un comercial legítimo creando un
# pedido con un producto nuevo recibiría 403.
ROLES_CREACION_PRODUCTO = ROLES_INVENTARIO + ROL_COMERCIALES


@inventario_bp.route('/api/entrada', methods=['POST'])
@require_role(ROLES_INVENTARIO)
def registrar_entrada():
    """Registra una entrada de inventario."""
    try:
        datos = request.get_json()
        
        if not datos:
            return jsonify({
                "status": "error",
                "message": "No se recibieron datos"
            }), 400
        
        resultado = inventario_service.registrar_entrada(datos)
        
        status_code = 200 if resultado["status"] == "success" else 400
        return jsonify(resultado), status_code
        
    except Exception as e:
        logger.error(f"Error en entrada: {e}")
        return jsonify({
            "status": "error",
            "message": "Error interno del servidor"
        }), 500


@inventario_bp.route('/api/salida', methods=['POST'])
@require_role(ROLES_INVENTARIO)
def registrar_salida():
    """Registra una salida de inventario."""
    try:
        datos = request.get_json()
        
        if not datos:
            return jsonify({
                "status": "error",
                "message": "No se recibieron datos"
            }), 400
        
        resultado = inventario_service.registrar_salida(datos)
        
        status_code = 200 if resultado["status"] == "success" else 400
        return jsonify(resultado), status_code
        
    except Exception as e:
        logger.error(f"Error en salida: {e}")
        return jsonify({
            "status": "error",
            "message": "Error interno del servidor"
        }), 500


@inventario_bp.route('/api/conteo', methods=['POST'])
@require_role(ROLES_INVENTARIO)
def registrar_conteo():
    """Registra un conteo de inventario con validación doble."""
    try:
        datos = request.json
        # datos: {codigo, cantidad, responsable, tipo_stock, observaciones}
        
        codigo = str(datos.get("codigo")).strip().upper()
        cantidad = int(datos.get("cantidad"))
        responsable = datos.get("responsable")
        tipo_stock = datos.get("tipo_stock", "principal")
        observaciones_user = datos.get("observaciones", "")
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        
        # Buscar si ya hay un proceso abierto hoy para este producto en SQL
        # IMPORTANTE: to_legacy=False para usar llaves SQL reales (fecha, id_codigo, etc)
        registros = base_repository.get_all('conteos', to_legacy=False)
        
        fila_proceso_sql = None
        conteo_existente = None
        for r in registros:
            # Comparación con nombres de columnas normalizados (lowercase)
            if str(r.get("fecha")) == fecha_hoy and \
               str(r.get("id_codigo")).strip().upper() == codigo and \
               str(r.get("tipo_stock", "principal")) == tipo_stock and \
               r.get("estado") != "FINALIZADO":
                conteo_existente = r
                fila_proceso_sql = True # Flag para indicar que existe
                break
        
        if not fila_proceso_sql:
            # PRIMER CONTEO
            nueva_fila = {
                "fecha": fecha_hoy,
                "responsable": responsable,
                "id_codigo": codigo,
                "conteo_1": cantidad,
                "conteo_2": "",
                "conteo_3": "",
                "estado": "CONTEO_1_PENDIENTE",
                "observaciones": observaciones_user,
                "tipo_stock": tipo_stock
            }
            if not base_repository.insert_one('conteos', nueva_fila):
                return jsonify({"success": False, "error": "Error al insertar el primer conteo en la base de datos."}), 500
                
            return jsonify({
                "success": True, 
                "status": "first_count",
                "message": f"Primer conteo ({cantidad}) registrado. Se requiere un segundo conteo de validación.",
                "step": 1
            })
        
        # SEGUNDO O TERCER CONTEO
        c1 = conteo_existente.get("conteo_1")
        c2 = conteo_existente.get("conteo_2")
        obs_previa = conteo_existente.get("observaciones", "")
        nueva_obs = f"{obs_previa} | {observaciones_user}".strip(" |") if observaciones_user else obs_previa
        
        # Filtros para actualizar la fila correcta en SQL
        filtros_update = {
            "fecha": fecha_hoy,
            "id_codigo": codigo,
            "tipo_stock": tipo_stock,
            "estado": conteo_existente.get("estado")
        }

        if c1 != "" and c2 == "":
            # ES EL SEGUNDO CONTEO
            c1_val = int(c1)
            if c1_val == cantidad:
                # COINCIDEN -> FINALIZAR
                if not base_repository.update_one('conteos', filtros_update, {
                    "conteo_2": cantidad,
                    "estado": "FINALIZADO",
                    "observaciones": f"Coincidencia en 2do conteo. {nueva_obs}".strip()
                }):
                    return jsonify({"success": False, "error": "Error al finalizar el segundo conteo."}), 500
                
                # ACTUALIZAR STOCK FISICO REAL EN TABLA db_productos
                try:
                    # Mapeo Inteligente
                    col_target = "por_pulir" if tipo_stock == "por_pulir" else \
                                ("p_terminado" if codigo.startswith(('FR-', 'MT-')) else "stock_bodega")
                    
                    # CORRECCIÓN: Usar db_productos según modelo SQLAlchemy
                    base_repository.update_one('db_productos', {"codigo_sistema": codigo}, {col_target: cantidad})
                    logger.info(f"Stock físico de {codigo} actualizado en {col_target} a {cantidad} (SQL).")
                except Exception as e_stock:
                    logger.error(f"Error actualizando stock SQL: {e_stock}")

                return jsonify({
                    "success": True, 
                    "status": "match",
                    "message": "¡Conteo exitoso! Los valores coinciden. El stock ha sido actualizado.",
                    "step": 2,
                    "finalizado": True
                })
            else:
                # NO COINCIDEN -> PEDIR TERCERO
                if not base_repository.update_one('conteos', filtros_update, {
                    "conteo_2": cantidad,
                    "estado": "DISCREPANCIA",
                    "observaciones": f"Dif: {c1_val} vs {cantidad}. {nueva_obs}".strip()
                }):
                    return jsonify({"success": False, "error": "Error al registrar discrepancia en el segundo conteo."}), 500
                    
                return jsonify({
                    "success": True, 
                    "status": "discrepancy",
                    "mensaje": "¡ALERTA DE DISCREPANCIA! Las cuentas no coinciden. Por favor, llame a un administrador o supervisor para realizar el 3er conteo de desempate.",
                    "message": "¡ALERTA DE DISCREPANCIA! Las cuentas no coinciden.",
                    "step": 2,
                    "discrepancia": True
                })
        
        # ES EL TERCER CONTEO (DEFINITIVO)
        if not base_repository.update_one('conteos', filtros_update, {
            "conteo_3": cantidad,
            "estado": "FINALIZADO",
            "observaciones": f"Finalizado con 3er conteo por {responsable}. {nueva_obs}".strip()
        }):
            return jsonify({"success": False, "error": "Error al registrar el tercer conteo definitivo."}), 500
        
        # ACTUALIZAR STOCK FISICO REAL (DEFINITIVO) en db_productos
        try:
            col_target = "por_pulir" if tipo_stock == "por_pulir" else \
                        ("p_terminado" if codigo.startswith(('FR-', 'MT-')) else "stock_bodega")
            base_repository.update_one('db_productos', {"codigo_sistema": codigo}, {col_target: cantidad})
            logger.info(f"Stock físico de {codigo} actualizado tras 3er conteo (SQL).")
        except Exception as e_stock:
            logger.error(f"Error actualizando stock SQL (3er conteo): {e_stock}")

        return jsonify({
            "success": True, 
            "message": f"Conteo finalizado con el tercer valor definitivo: {cantidad}. Inventario actualizado.",
            "step": 3,
            "finalizado": True
        })

    except Exception as e:
        logger.error(f"Error en conteo: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ====================================================================
# CATÁLOGO DE PRODUCTOS / FICHAS / MOLDES / CACHE
# (migrado desde backend/app.py)
# ====================================================================

@inventario_bp.route('/api/producto/<codigo>', methods=['GET'])
@require_login
def obtener_producto(codigo):
    """Obtiene información resumida del producto (código sistema + código ensamble)."""
    try:
        return jsonify(InventarioService.obtener_producto_resumen(codigo)), 200
    except AppException as e:
        return jsonify({'error': e.mensaje}), e.codigo
    except Exception as e:
        logger.error(f"Error en obtener_producto: {str(e)}")
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500


@inventario_bp.route('/api/obtener_ficha/<id_codigo>', methods=['GET'])
@require_login
def obtener_ficha(id_codigo):
    """Obtiene la ficha técnica (buje de origen y cantidad unitaria) de un producto."""
    return jsonify(InventarioService.obtener_ficha_tecnica(id_codigo)), 200


@inventario_bp.route('/api/moldes', methods=['GET'])
@require_login
def obtener_moldes():
    """Obtiene la lista de moldes activos."""
    try:
        return jsonify(InventarioService.obtener_moldes_activos()), 200
    except Exception as e:
        logger.error(f"Error en obtener_moldes: {e}")
        return jsonify([]), 200


@inventario_bp.route('/api/moldes/validar', methods=['POST'])
@require_login
def validar_molde():
    """Valida si las cavidades solicitadas no superan el máximo del molde."""
    data = request.json or {}
    try:
        InventarioService.validar_molde(data.get('molde'), int(data.get('cavidades', 0)))
        return jsonify({'success': True, 'message': 'Validación exitosa'}), 200
    except AppException as e:
        return jsonify({'success': False, 'error': e.mensaje}), e.codigo
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@inventario_bp.route('/api/obtener_fichas', methods=['GET'])
@require_login
def obtener_fichas():
    """Obtiene todas las fichas técnicas (nueva_ficha_maestra)."""
    try:
        return jsonify(InventarioService.obtener_fichas_tecnicas()), 200
    except Exception as e:
        logger.error(f"Error obteniendo fichas SQL: {e}")
        return jsonify([]), 500


@inventario_bp.route('/api/productos/listar_v2', methods=['GET'])
@require_login
def listar_productos_v2():
    """Endpoint optimizado para la tabla de inventario con semáforos."""
    try:
        return jsonify(InventarioService.listar_productos_v2()), 200
    except Exception as e:
        logger.error(f"❌ Error en listar_productos_v2 SQL: {e}")
        return jsonify({"success": False, "error": str(e), "detail": "Error en el servidor al listar productos (V2)"}), 500


@inventario_bp.route('/api/productos/crear_dual', methods=['POST'])
@inventario_bp.route('/api/productos/dual', methods=['POST'])
@require_role(ROLES_CREACION_PRODUCTO)
def crear_producto_dual():
    """Registra un nuevo producto en db_productos."""
    data = request.json or {}
    try:
        InventarioService.crear_producto(
            id_codigo=data.get('id_codigo', ''),
            codigo_sistema_raw=str(data.get('codigo_sistema', '')).strip(),
            descripcion=data.get('descripcion', ''),
            precio=data.get('precio', 0),
            stock_inicial=data.get('stock_inicial', 0),
        )
        return jsonify({"success": True, "message": "Producto creado en PostgreSQL"}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventario_bp.route('/api/cache/invalidar', methods=['POST'])
@require_role(ROLES_INVENTARIO)
def invalidar_cache_endpoint():
    """Endpoint para forzar la invalidación del cache de productos."""
    try:
        InventarioService.invalidar_cache_productos()
        return jsonify({'status': 'success', 'message': 'Cache de productos invalidado'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@inventario_bp.route('/api/cache/estado', methods=['GET'])
def estado_cache():
    """Obtiene el estado actual del cache de productos."""
    return jsonify({'status': 'success', 'cache': InventarioService.obtener_estado_cache()}), 200


@inventario_bp.route('/api/productos/limpiar_cache', methods=['POST'])
@require_role(ROLES_INVENTARIO)
def limpiar_cache_manual():
    """Fuerza la limpieza manual del cache de productos."""
    try:
        InventarioService.limpiar_cache_productos()
        return jsonify({"status": "success", "message": "Inventario actualizado"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@inventario_bp.route('/api/producto/historial/<codigo>', methods=['GET'])
@require_login
def obtener_historial_producto(codigo):
    """Obtiene el historial de movimientos (Inyección + Pulido + Ventas) de un producto."""
    try:
        resultado = InventarioService.obtener_historial_producto(codigo)
        return jsonify({'status': 'success', **resultado}), 200
    except Exception as e:
        logger.error(f"❌ Error en obtener_historial_producto SQL: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@inventario_bp.route('/api/productos/buscar_alternativas/<interno>', methods=['GET'])
@require_login
def buscar_alternativas(interno):
    """Busca productos que comparten el mismo ID CODIGO (INTERNO)."""
    try:
        return jsonify(InventarioService.buscar_alternativas(interno)), 200
    except Exception as e:
        logger.error(f"Error en buscar_alternativas SQL: {e}")
        return jsonify([]), 500