"""
Rutas de inventario.
Endpoints REST para operaciones de inventario.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventario_service import inventario_service
from backend.core.database import sheets_client
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
        # datos: {codigo, cantidad, responsable}
        
        codigo = str(datos.get("codigo")).strip().upper()
        cantidad = int(datos.get("cantidad"))
        responsable = datos.get("responsable")
        tipo_stock = datos.get("tipo_stock", "principal")
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        
        try:
            ws_conteos = sheets_client.get_worksheet("CONTEOS")
        except:
             return jsonify({"success": False, "error": "Hoja CONTEOS no encontrada"}), 500
             
        registros = sheets_client.get_all_records_seguro(ws_conteos)
        
        # Buscar si ya hay un proceso abierto hoy para este producto
        fila_proceso = None
        conteo_existente = None
        for i, r in enumerate(registros):
            if str(r.get("FECHA")) == fecha_hoy and \
               str(r.get("ID CODIGO")).strip().upper() == codigo and \
               str(r.get("TIPO STOCK", "principal")) == tipo_stock and \
               r.get("ESTADO") != "FINALIZADO":
                fila_proceso = i + 2
                conteo_existente = r
                break
        
        if not fila_proceso:
            # PRIMER CONTEO (Añadimos tipo_stock como 9na columna)
            ws_conteos.append_row([
                fecha_hoy, responsable, codigo, cantidad, "", "", "CONTEO_1_PENDIENTE", "", tipo_stock
            ])
            return jsonify({
                "success": True, 
                "status": "first_count",
                "message": f"Primer conteo ({cantidad}) registrado. Se requiere un segundo conteo de validación.",
                "step": 1
            })
        
        # SEGUNDO O TERCER CONTEO
        c1 = conteo_existente.get("CONTEO_1")
        c2 = conteo_existente.get("CONTEO_2")
        
        if c1 != "" and c2 == "":
            # ES EL SEGUNDO CONTEO
            c1_val = int(c1)
            if c1_val == cantidad:
                # COINCIDEN -> FINALIZAR
                ws_conteos.update_cell(fila_proceso, 5, cantidad) # CONTEO_2 (Columna E)
                ws_conteos.update_cell(fila_proceso, 7, "FINALIZADO") # ESTADO (Columna G)
                ws_conteos.update_cell(fila_proceso, 8, "Coincidencia en 2do conteo") # OBS (Columna H)
                
                # ACTUALIZAR STOCK FISICO REAL
                try:
                    ws_productos = sheets_client.get_worksheet("PRODUCTOS")
                    registros_prod = sheets_client.get_all_records_seguro(ws_productos)
                    headers_prod = ws_productos.row_values(1)
                    
                    # Lógica de Mapeo Inteligente: 
                    # 1. Si es "Por Pulir", va a esa columna sin importar prefijos.
                    # 2. Si es "Principal", FR/MT -> P. TERMINADO, Resto -> STOCK_BODEGA.
                    if tipo_stock == "por_pulir":
                        col_target_name = "POR PULIR"
                    else:
                        col_target_name = "P. TERMINADO" if codigo.startswith(('FR-', 'MT-')) else "STOCK_BODEGA"
                    col_idx = headers_prod.index(col_target_name) + 1 if col_target_name in headers_prod else None
                    
                    if col_idx:
                        fila_prod = None
                        for idx, rp in enumerate(registros_prod):
                             if str(rp.get("ID CODIGO")).strip().upper() == codigo:
                                 fila_prod = idx + 2
                                 break
                        
                        if fila_prod:
                             ws_productos.update_cell(fila_prod, col_idx, cantidad)
                             logger.info(f"Stock físico de {codigo} actualizado en {col_target_name} a {cantidad} tras validación.")
                except Exception as e_stock:
                    logger.error(f"Error actualizando stock tras conteo coincidente: {e_stock}")

                return jsonify({
                    "success": True, 
                    "status": "match",
                    "message": "¡Conteo exitoso! Los valores coinciden. El stock ha sido actualizado.",
                    "step": 2,
                    "finalizado": True
                })
            else:
                # NO COINCIDEN -> PEDIR TERCERO
                ws_conteos.update_cell(fila_proceso, 5, cantidad) # CONTEO_2
                ws_conteos.update_cell(fila_proceso, 7, "DISCREPANCIA")
                ws_conteos.update_cell(fila_proceso, 8, f"Dif: {c1_val} vs {cantidad}")
                return jsonify({
                    "success": True, 
                    "status": "discrepancy",
                    "mensaje": "¡ALERTA DE DISCREPANCIA! Las cuentas no coinciden. Por favor, llame a un administrador o supervisor para realizar el 3er conteo de desempate.",
                    "message": "¡ALERTA DE DISCREPANCIA! Las cuentas no coinciden.", # Fallback
                    "step": 2,
                    "discrepancia": True
                })
        
        # ES EL TERCER CONTEO (DEFINITIVO)
        # El frontend ya debería filtrar por rol, pero aquí registramos que fue un 3er conteo
        ws_conteos.update_cell(fila_proceso, 6, cantidad) # CONTEO_3 (Columna F)
        ws_conteos.update_cell(fila_proceso, 7, "FINALIZADO")
        ws_conteos.update_cell(fila_proceso, 8, f"Finalizado con 3er conteo por {responsable}")
        
        # ACTUALIZAR STOCK FISICO REAL (DEFINITIVO)
        try:
            ws_productos = sheets_client.get_worksheet("PRODUCTOS")
            registros_prod = sheets_client.get_all_records_seguro(ws_productos)
            headers_prod = ws_productos.row_values(1)
            
            # Mapeo Inteligente para el 3er conteo
            if tipo_stock == "por_pulir":
                col_target_name = "POR PULIR"
            else:
                col_target_name = "P. TERMINADO" if codigo.startswith(('FR-', 'MT-')) else "STOCK_BODEGA"
            col_idx = headers_prod.index(col_target_name) + 1 if col_target_name in headers_prod else None

            if col_idx:
                fila_prod = None
                for idx, rp in enumerate(registros_prod):
                        if str(rp.get("ID CODIGO")).strip().upper() == codigo:
                            fila_prod = idx + 2
                            break
                
                if fila_prod:
                        ws_productos.update_cell(fila_prod, col_idx, cantidad)
                        logger.info(f"Stock físico de {codigo} actualizado en {col_target_name} a {cantidad} tras tercer conteo definitivo.")
        except Exception as e_stock:
            logger.error(f"Error actualizando stock tras tercer conteo: {e_stock}")

        return jsonify({
            "success": True, 
            "message": f"Conteo finalizado con el tercer valor definitivo: {cantidad}. Inventario actualizado.",
            "step": 3,
            "finalizado": True
        })

    except Exception as e:
        logger.error(f"Error en conteo: {e}")
        return jsonify({"success": False, "error": str(e)}), 500