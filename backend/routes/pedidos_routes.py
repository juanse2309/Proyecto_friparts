

from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import uuid
import datetime
import logging
import json


pedidos_bp = Blueprint('pedidos', __name__)
logger = logging.getLogger(__name__)

@pedidos_bp.route('/api/pedidos/registrar', methods=['POST'])
def registrar_pedido():
    """
    Registra un pedido con múltiples productos.
    Estructura esperada:
    {
        "fecha": "2026-02-02",
        "vendedor": "Juan Pérez",
        "cliente": "Cliente X",
        "nit": "123456",
        "forma_pago": "Contado",
        "descuento_global": 10,
        "productos": [
            {"codigo": "9304", "descripcion": "Buje A", "cantidad": 10, "precio_unitario": 5000},
            {"codigo": "9309", "descripcion": "Buje B", "cantidad": 20, "precio_unitario": 6000}
        ]
    }
    """
    try:
        logger.info("🛒 ===== INICIO REGISTRO DE PEDIDO =====")
        
        data = request.json
        logger.info(f"📦 Datos recibidos del frontend:")
        logger.info(f"   JSON completo: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if not data:
            logger.error("❌ No se recibieron datos en el request")
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Extract common fields
        fecha = data.get('fecha')
        vendedor = data.get('vendedor')
        cliente = data.get('cliente')
        nit = data.get('nit', '')
        forma_pago = data.get('forma_pago', 'Contado')
        descuento_global = data.get('descuento_global', 0)
        productos = data.get('productos', [])
        
        logger.info(f"📋 Campos extraídos:")
        logger.info(f"   Fecha: {fecha}")
        logger.info(f"   Vendedor: {vendedor}")
        logger.info(f"   Cliente: {cliente}")
        logger.info(f"   NIT: {nit}")
        logger.info(f"   Forma de pago: {forma_pago}")
        logger.info(f"   Descuento global: {descuento_global}%")
        logger.info(f"   Total productos: {len(productos)}")
        
        # Validation
        if not all([fecha, vendedor, cliente]):
            logger.error(f"❌ Faltan campos obligatorios: fecha={fecha}, vendedor={vendedor}, cliente={cliente}")
            return jsonify({"success": False, "error": "Faltan campos obligatorios (fecha, vendedor, cliente)"}), 400
        
        if not productos or not isinstance(productos, list):
            logger.error(f"❌ Array de productos inválido: {productos}")
            return jsonify({"success": False, "error": "Debe incluir al menos un producto en 'productos'"}), 400

        # Generate unique ID for this order (shared by all items)
        id_pedido = f"PED-{str(uuid.uuid4())[:8].upper()}"
        estado = "PENDIENTE"
        
        logger.info(f"🆔 ID de pedido generado: {id_pedido}")
        logger.info(f"📊 Estado inicial: {estado}")
        
        # Get or create worksheet
        ws = sheets_client.get_or_create_worksheet(
            Hojas.PEDIDOS, 
            rows=1000, 
            cols=13
        )
        
        logger.info(f"📄 Worksheet 'PEDIDOS' obtenida correctamente")
        
        # Check headers
        existing_headers = ws.row_values(1)
        expected_headers = [
            "ID PEDIDO", "FECHA", "ID CODIGO", "DESCRIPCION", "VENDEDOR", 
            "CLIENTE", "NIT", "FORMA DE PAGO", "DESCUENTO %", "TOTAL", 
            "ESTADO", "CANTIDAD", "PRECIO UNITARIO"
        ]
        
        if not existing_headers:
            logger.info("📝 Creando encabezados en hoja PEDIDOS")
            ws.append_row(expected_headers)
        
        # Process each product
        subtotal_general = 0
        rows_to_append = []
        
        logger.info(f"🔄 Procesando {len(productos)} productos...")
        
        for idx, producto in enumerate(productos):
            logger.info(f"\n   --- Producto {idx+1}/{len(productos)} ---")
            logger.info(f"   Datos del producto: {producto}")
            
            codigo = producto.get('codigo')
            descripcion = producto.get('descripcion', '')
            cantidad = producto.get('cantidad', 0)
            precio_unitario = producto.get('precio_unitario', 0)
            
            logger.info(f"   Código: '{codigo}' (tipo: {type(codigo).__name__})")
            logger.info(f"   Descripción: '{descripcion}'")
            logger.info(f"   Cantidad: {cantidad}")
            logger.info(f"   Precio unitario: {precio_unitario}")
            
            # Validate product
            if not all([codigo, cantidad, precio_unitario]):
                logger.warning(f"⚠️ Producto incompleto ignorado: {producto}")
                logger.warning(f"   codigo={codigo}, cantidad={cantidad}, precio_unitario={precio_unitario}")
                continue
            
            # Calculations (sin descuento individual)
            try:
                cant_float = float(cantidad)
                precio_float = float(precio_unitario)
                
                subtotal = cant_float * precio_float
                subtotal_general += subtotal
                
                logger.info(f"   ✅ Cálculos: {cant_float} × ${precio_float} = ${subtotal}")
            except ValueError as ve:
                logger.error(f"❌ Error en valores numéricos del producto: {producto}")
                logger.error(f"   Error: {str(ve)}")
                continue
            
            # Prepare row for this product (total se calcula después)
            row = [
                id_pedido,
                fecha,
                codigo,
                descripcion,
                vendedor,
                cliente,
                nit,
                forma_pago,
                f"{descuento_global}%",  # Descuento global para todos
                0,  # Total se calculará después
                estado,
                cantidad,
                precio_unitario
            ]
            
            rows_to_append.append(row)
            logger.info(f"   ✅ Fila preparada para Google Sheets")
        
        # Calcular total general con descuento global
        try:
            desc_float = float(descuento_global) / 100
            total_general = subtotal_general * (1 - desc_float)
            total_general = round(total_general, 2)
            
            logger.info(f"\n💰 Cálculo de totales:")
            logger.info(f"   Subtotal general: ${subtotal_general}")
            logger.info(f"   Descuento: {descuento_global}% (${subtotal_general * desc_float})")
            logger.info(f"   Total general: ${total_general}")
        except ValueError:
            total_general = subtotal_general
            logger.warning(f"⚠️ Error calculando descuento, usando subtotal: ${total_general}")
        
        # Calcular total proporcional por cada item
        if subtotal_general > 0:
            logger.info(f"\n🔢 Calculando totales proporcionales por item...")
            for i, row in enumerate(rows_to_append):
                cantidad = float(row[11])  # CANTIDAD
                precio_unitario = float(row[12])  # PRECIO UNITARIO
                subtotal_item = cantidad * precio_unitario
                
                # Total proporcional con descuento global
                total_item = subtotal_item * (1 - desc_float)
                total_item = round(total_item, 2)
                
                row[9] = total_item  # Actualizar TOTAL
                logger.info(f"   Item {i+1}: ${subtotal_item} → ${total_item} (con {descuento_global}% desc)")
        
        # Append all rows
        if rows_to_append:
            logger.info(f"\n💾 Guardando {len(rows_to_append)} filas en Google Sheets...")
            for i, row in enumerate(rows_to_append):
                logger.info(f"   Guardando fila {i+1}: {row[:5]}...")  # Solo primeros 5 campos para no saturar
                ws.append_row(row)
            
            # ==========================================
            # 📉 ACTUALIZACIÓN DE INVENTARIO (STOCK)
            # ==========================================
            try:
                logger.info("📉 Iniciando descuento de inventario (P. TERMINADO)...")
                ws_productos = sheets_client.get_worksheet(Hojas.PRODUCTOS)
                registros_productos = ws_productos.get_all_records()
                headers_productos = ws_productos.row_values(1)
                
                try:
                    col_idx = headers_productos.index("P. TERMINADO") + 1
                except ValueError:
                    logger.error("❌ Columna 'P. TERMINADO' no encontrada en PRODUCTOS. No se pudo descontar inventario.")
                    col_idx = None

                if col_idx:
                    # Crear mapa de código -> fila para búsqueda rápida
                    # Normalizamos claves para mejorar coincidencia (strip + upper)
                    mapa_productos = {}
                    for idx, r in enumerate(registros_productos):
                        # Mapeamos tanto CODIGO SISTEMA como ID CODIGO para ser flexibles
                        c_sis = str(r.get("CODIGO SISTEMA", "")).strip().upper()
                        id_cod = str(r.get("ID CODIGO", "")).strip().upper()
                        fila_real = idx + 2 # +1 header +1 0-index
                        
                        if c_sis: mapa_productos[c_sis] = fila_real
                        if id_cod: mapa_productos[id_cod] = fila_real

                    updates_pendientes = []

                    for producto in productos:
                        codigo = str(producto.get('codigo', '')).strip().upper()
                        if " - " in codigo: # Limpiar si viene "COD - DESC"
                             codigo = codigo.split(" - ")[0].strip()
                        
                        cantidad_venta = float(producto.get('cantidad', 0))
                        
                        if codigo in mapa_productos:
                            fila = mapa_productos[codigo]
                            # Obtener stock actual leyendo la celda directamente para ser atómico (o confiando en records)
                            # Usamos records para evitar N lecturas, pero idealmente deberíamos re-leer. 
                            # Por simplicidad usamos el dato cargado.
                            item_data = registros_productos[fila - 2]
                            stock_actual = item_data.get("P. TERMINADO", 0)
                            
                            try:
                                stock_val = float(stock_actual) if stock_actual != '' else 0
                            except:
                                stock_val = 0
                                
                            nuevo_stock = max(0, stock_val - cantidad_venta)
                            
                            # Agendar update
                            # ws_productos.update_cell(fila, col_idx, nuevo_stock) # Opción lenta
                            updates_pendientes.append({
                                'range': f"{gspread.utils.rowcol_to_a1(fila, col_idx)}",
                                'values': [[nuevo_stock]]
                            })
                            logger.info(f"   ✅ Descontado {codigo}: {stock_val} - {cantidad_venta} = {nuevo_stock}")
                        else:
                            logger.warning(f"   ⚠️ Producto {codigo} no encontrado en inventario para descontar.")

                    # Batch update si es posible, o uno por uno
                    if updates_pendientes:
                        try:
                            ws_productos.batch_update(updates_pendientes)
                            logger.info(f"   📉 Stock actualizado correctamente para {len(updates_pendientes)} productos")
                        except Exception as e:
                            logger.error(f"   ❌ Error en batch update de stock: {e}")
                            # Fallback uno a uno
                            for up in updates_pendientes:
                                ws_productos.update(up['range'], up['values'])

            except Exception as e_inv:
                logger.error(f"❌ Error crítico actualizando inventario: {str(e_inv)}")
                # No fallamos el pedido si falla el stock, pero avisamos en log
            
            # ==========================================
            # FIN ACTUALIZACIÓN INVENTARIO
            # ==========================================

            logger.info(f"✅ PEDIDO REGISTRADO EXITOSAMENTE")
            logger.info(f"   ID: {id_pedido}")
            logger.info(f"   Cliente: {cliente}")
            logger.info(f"   Productos: {len(rows_to_append)}")
            logger.info(f"   Total: ${total_general}")
            
            return jsonify({
                "success": True, 
                "message": "Pedido registrado exitosamente",
                "id_pedido": id_pedido,
                "total_productos": len(rows_to_append),
                "total_general": total_general
            })
        else:
            logger.error("❌ No se pudo procesar ningún producto válido")
            return jsonify({"success": False, "error": "No se pudo procesar ningún producto válido"}), 400

    except Exception as e:
        logger.error(f"❌ ERROR CRÍTICO registrando pedido: {str(e)}")
        logger.error(f"   Tipo de error: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
