"""
Rutas de inventario.
Endpoints REST para operaciones de inventario.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventario_service import inventario_service
from backend.core.repository_service import repository_service
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Crear blueprint
inventario_bp = Blueprint('inventario', __name__)


@inventario_bp.route('/api/entrada', methods=['POST'])
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
        registros = repository_service.get_all('conteos', to_legacy=False)
        
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
            if not repository_service.insert_one('conteos', nueva_fila):
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
                if not repository_service.update_one('conteos', filtros_update, {
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
                    repository_service.update_one('db_productos', {"codigo_sistema": codigo}, {col_target: cantidad})
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
                if not repository_service.update_one('conteos', filtros_update, {
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
        if not repository_service.update_one('conteos', filtros_update, {
            "conteo_3": cantidad,
            "estado": "FINALIZADO",
            "observaciones": f"Finalizado con 3er conteo por {responsable}. {nueva_obs}".strip()
        }):
            return jsonify({"success": False, "error": "Error al registrar el tercer conteo definitivo."}), 500
        
        # ACTUALIZAR STOCK FISICO REAL (DEFINITIVO) en db_productos
        try:
            col_target = "por_pulir" if tipo_stock == "por_pulir" else \
                        ("p_terminado" if codigo.startswith(('FR-', 'MT-')) else "stock_bodega")
            repository_service.update_one('db_productos', {"codigo_sistema": codigo}, {col_target: cantidad})
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