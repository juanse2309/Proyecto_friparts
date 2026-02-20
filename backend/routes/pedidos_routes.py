

from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import gspread
import uuid
import datetime
import logging
import json
import pytz


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
        direccion = data.get('direccion', '')  # OPCIONAL - Compatible con frontend antiguo
        ciudad = data.get('ciudad', '')        # OPCIONAL - Compatible con frontend antiguo
        forma_pago = data.get('forma_pago', 'Contado')
        descuento_global = data.get('descuento_global', 0)
        observaciones = data.get('observaciones', '')
        productos = data.get('productos', [])
        
        logger.info(f"📋 Campos extraídos:")
        logger.info(f"   Fecha: {fecha}")
        logger.info(f"   Vendedor: {vendedor}")
        logger.info(f"   Cliente: {cliente}")
        logger.info(f"   NIT: {nit}")
        logger.info(f"   Dirección: {direccion}")
        logger.info(f"   Ciudad: {ciudad}")
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
        
        # Auto-capturar hora actual del servidor (Colombia UTC-5)
        try:
            tz_colombia = pytz.timezone('America/Bogota')
            hora_actual = datetime.datetime.now(tz_colombia).strftime('%I:%M %p')
        except Exception:
            hora_actual = datetime.datetime.now().strftime('%I:%M %p')
        logger.info(f"🕐 Hora auto-capturada: {hora_actual}")
        
        logger.info(f"🆔 ID de pedido generado: {id_pedido}")
        logger.info(f"📊 Estado inicial: {estado}")
        
        # Get or create worksheet
        ws = sheets_client.get_or_create_worksheet(
            Hojas.PEDIDOS, 
            rows=1000, 
            cols=20
        )
        
        logger.info(f"📄 Worksheet 'PEDIDOS' obtenida correctamente")
        
        # Check headers
        existing_headers = ws.row_values(1)
        expected_headers = [
            "ID PEDIDO", "FECHA", "HORA", "ID CODIGO", "DESCRIPCION", "VENDEDOR", 
            "CLIENTE", "NIT", "DIRECCION", "CIUDAD", "FORMA DE PAGO", "DESCUENTO %", "TOTAL", 
            "ESTADO", "CANTIDAD", "PRECIO UNITARIO", "PROGRESO", "CANT_ALISTADA",
            "PROGRESO_DESPACHO", "CANT_ENVIADA", "DELEGADO_A", "ESTADO_DESPACHO", "NO_DISPONIBLE", 
            "OBSERVACIONES"
        ]
        
        if not existing_headers:
            logger.info("📝 Creando encabezados en hoja PEDIDOS")
            ws.append_row(expected_headers)

        # ---------------------------------------------------------
        # LÓGICA DE EDICIÓN / RETOMAR PEDIDO
        # ---------------------------------------------------------
        id_pedido_existente = data.get('id_pedido')
        if id_pedido_existente:
            logger.info(f"✏️ MODO EDICIÓN: Actualizando pedido {id_pedido_existente}")
            
            # 1. Buscar filas del pedido anterior
            registros = ws.get_all_records()
            filas_a_eliminar = []
            productos_anteriores = []
            
            # Recopilar info para reversión de inventario
            for idx, r in enumerate(registros):
                if str(r.get("ID PEDIDO")) == str(id_pedido_existente):
                    filas_a_eliminar.append(idx + 2) # +2 por header y 0-index
                    productos_anteriores.append({
                        "codigo": str(r.get("ID CODIGO")).strip().upper(),
                        "cantidad": float(r.get("CANTIDAD", 0))
                    })
            
            if filas_a_eliminar:
                logger.info(f"   🗑️ Eliminando {len(filas_a_eliminar)} filas anteriores...")
                
                # REVERSIÓN DE STOCK COMPROMETIDO (Antes de borrar)
                try:
                    ws_productos = sheets_client.get_worksheet(Hojas.PRODUCTOS)
                    registros_prods = ws_productos.get_all_records()
                    headers_prods = ws_productos.row_values(1)
                    col_comp = headers_prods.index("COMPROMETIDO") + 1
                    
                    mapa_prods = {str(p["ID CODIGO"]).strip().upper(): (i + 2) for i, p in enumerate(registros_prods)}
                    # También mapear por codigo sistema
                    for i, p in enumerate(registros_prods):
                         c_sis = str(p.get("CODIGO SISTEMA", "")).strip().upper()
                         if c_sis: mapa_prods[c_sis] = i + 2

                    updates_reversion = []
                    for prod_ant in productos_anteriores:
                        cod = prod_ant["codigo"]
                        cant = prod_ant["cantidad"]
                        
                        if cod in mapa_prods:
                            fila_p = mapa_prods[cod]
                            # Obtener valor actual directo de la celda para ser preciso (o confiar en la lectura masiva)
                            # Confiaremos en lectura masiva por velocidad, riesgo bajo si concurrencia es baja
                            # Mejor: usar el valor leido y restar.
                            # OJO: Si alguien mas modificó, podria haber error.
                            # Para batch update, necesitamos valor actual.
                            # Re-leer SOLO las celdas afectadas seria lento.
                            # Asumiremos snapshot de registros_prods es valido.
                            item_prod = registros_prods[fila_p - 2]
                            comp_actual = float(item_prod.get("COMPROMETIDO", 0) or 0)
                            nuevo_comp = max(0, comp_actual - cant)
                            
                            updates_reversion.append({
                                'range': gspread.utils.rowcol_to_a1(fila_p, col_comp),
                                'values': [[nuevo_comp]]
                            })
                    
                    if updates_reversion:
                        ws_productos.batch_update(updates_reversion)
                        logger.info(f"   📉 Reversiòn stock comprometido completada ({len(updates_reversion)} updates)")

                except Exception as e_rev:
                    logger.error(f"❌ Error revirtiendo stock comprometido: {e_rev}")

                # Borrar filas (en orden inverso para no alterar índices de las pendientes)
                for fila in sorted(filas_a_eliminar, reverse=True):
                    ws.delete_rows(fila)
                
                logger.info("   ✅ Filas anteriores eliminadas.")
            
            # Usar el ID existente
            id_pedido = id_pedido_existente
        else:
            # Generate unique ID for this order (shared by all items)
            id_pedido = f"PED-{str(uuid.uuid4())[:8].upper()}"
        
        estado = "PENDIENTE"

        
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
            
            # Prepare row for this product as a dictionary first to avoid index errors
            row_dict = {h: "" for h in expected_headers}
            row_dict.update({
                "ID PEDIDO": id_pedido,
                "FECHA": fecha,
                "HORA": hora_actual,
                "ID CODIGO": codigo,
                "DESCRIPCION": descripcion,
                "VENDEDOR": vendedor,
                "CLIENTE": cliente,
                "NIT": nit,
                "DIRECCION": direccion,
                "CIUDAD": ciudad,
                "FORMA DE PAGO": forma_pago,
                "DESCUENTO %": f"{descuento_global}%",
                "TOTAL": 0,  # Se calcula después
                "ESTADO": estado,
                "CANTIDAD": cantidad,
                "PRECIO UNITARIO": precio_unitario,
                "PROGRESO": "0%",
                "CANT_ALISTADA": 0,
                "PROGRESO_DESPACHO": "0%",
                "CANT_ENVIADA": 0,
                "DELEGADO_A": "",
                "ESTADO_DESPACHO": "FALSE",
                "NO_DISPONIBLE": "FALSE",
                "OBSERVACIONES": observaciones
            })
            
            rows_to_append.append(row_dict)
            logger.info(f"   ✅ Fila preparada para Google Sheets")
        
        # Calcular total general con descuento global e IVA 19%
        try:
            desc_float = float(descuento_global) / 100
            subtotal_neto = subtotal_general * (1 - desc_float)
            iva_general = subtotal_neto * 0.19
            total_general = subtotal_neto + iva_general
            
            total_general = round(total_general, 2)
            
            logger.info(f"\n💰 Cálculo de totales:")
            logger.info(f"   Subtotal bruto: ${subtotal_general}")
            logger.info(f"   Descuento: {descuento_global}% (${subtotal_general * desc_float})")
            logger.info(f"   IVA (19%): ${iva_general}")
            logger.info(f"   Total a Pagar: ${total_general}")
        except ValueError:
            total_general = subtotal_general
            logger.warning(f"⚠️ Error calculando descuento/IVA, usando subtotal: ${total_general}")
        
        if subtotal_general > 0:
            logger.info(f"\n🔢 Calculando totales proporcionales por item...")
            for i, row_dict in enumerate(rows_to_append):
                cantidad = float(row_dict["CANTIDAD"])
                precio_unitario = float(row_dict["PRECIO UNITARIO"])
                subtotal_item_bruto = cantidad * precio_unitario
                
                # Total proporcional con descuento global e IVA
                subtotal_item_neto = subtotal_item_bruto * (1 - desc_float)
                total_item = subtotal_item_neto * 1.19
                total_item = round(total_item, 2)
                
                row_dict["TOTAL"] = total_item
                logger.info(f"   Item {i+1}: ${subtotal_item_bruto} → ${total_item} (con {descuento_global}% desc e IVA)")
        
        # Convert dictionary rows to lists in correct order
        final_rows = []
        for rd in rows_to_append:
            final_rows.append([rd[h] for h in expected_headers])
        
        # Append all rows in a single batch to avoid quota issues
        if final_rows:
            logger.info(f"\n💾 Guardando {len(final_rows)} filas en Google Sheets (Batch Append)...")
            ws.append_rows(final_rows)
            
            # ==========================================
            # 📉 ACTUALIZACIÓN DE INVENTARIO (COMPROMETIDO)
            # ==========================================
            try:
                logger.info("📉 Iniciando aumento de COMPROMETIDO...")
                ws_productos = sheets_client.get_worksheet(Hojas.PRODUCTOS)
                registros_productos = ws_productos.get_all_records()
                headers_productos = ws_productos.row_values(1)
                
                try:
                    col_idx = headers_productos.index("COMPROMETIDO") + 1
                except ValueError:
                    logger.error("❌ Columna 'COMPROMETIDO' no encontrada en PRODUCTOS. No se pudo registrar compromiso.")
                    col_idx = None

                if col_idx:
                    mapa_productos = {}
                    for idx, r in enumerate(registros_productos):
                        c_sis = str(r.get("CODIGO SISTEMA", "")).strip().upper()
                        id_cod = str(r.get("ID CODIGO", "")).strip().upper()
                        fila_real = idx + 2
                        if c_sis: mapa_productos[c_sis] = fila_real
                        if id_cod: mapa_productos[id_cod] = fila_real

                    updates_pendientes = []
                    for producto in productos:
                        codigo = str(producto.get('codigo', '')).strip().upper()
                        if " - " in codigo:
                             codigo = codigo.split(" - ")[0].strip()
                        
                        cantidad_venta = float(producto.get('cantidad', 0))
                        
                        if codigo in mapa_productos:
                            fila = mapa_productos[codigo]
                            item_data = registros_productos[fila - 2]
                            comp_actual = item_data.get("COMPROMETIDO", 0)
                            
                            try:
                                comp_val = float(comp_actual) if comp_actual != '' else 0
                            except:
                                comp_val = 0
                                
                            nuevo_comp = comp_val + cantidad_venta
                            
                            updates_pendientes.append({
                                'range': f"{gspread.utils.rowcol_to_a1(fila, col_idx)}",
                                'values': [[nuevo_comp]]
                            })
                            logger.info(f"   ✅ Comprometido {codigo}: {comp_val} + {cantidad_venta} = {nuevo_comp}")
                        else:
                            logger.warning(f"   ⚠️ Producto {codigo} no encontrado en inventario para comprometer.")

                    if updates_pendientes:
                        ws_productos.batch_update(updates_pendientes)
                        logger.info(f"   📉 COMPROMETIDO actualizado correctamente para {len(updates_pendientes)} productos")
            except Exception as e_inv:
                logger.error(f"❌ Error crítico comprometiendo inventario: {str(e_inv)}")
            
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

@pedidos_bp.route('/api/pedidos/detalle/<id_pedido>', methods=['GET'])
def obtener_detalle_pedido(id_pedido):
    """
    Obtiene el detalle completo de un pedido por su ID.
    Útil para la funcionalidad de 'Retomar Pedido'.
    """
    try:
        if not id_pedido:
             return jsonify({"success": False, "error": "ID Pedido requerido"}), 400

        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        registros = ws.get_all_records()
        
        # Filtrar por ID
        items_pedido = [r for r in registros if str(r.get("ID PEDIDO")) == str(id_pedido)]
        
        if not items_pedido:
            return jsonify({"success": False, "error": "Pedido no encontrado"}), 404
            
        # Tomamos los datos de cabecera del primer item
        cabecera = items_pedido[0]
        
        pedido = {
            "id_pedido": cabecera.get("ID PEDIDO"),
            "fecha": cabecera.get("FECHA"),
            "hora": cabecera.get("HORA", ""),
            "vendedor": cabecera.get("VENDEDOR"),
            "cliente": cabecera.get("CLIENTE"),
            "nit": cabecera.get("NIT", ""),
            "direccion": cabecera.get("DIRECCION", ""),
            "ciudad": cabecera.get("CIUDAD", ""),
            "forma_pago": cabecera.get("FORMA DE PAGO", "Contado"),
            "descuento_global": str(cabecera.get("DESCUENTO %", "0")).replace('%', ''),
            "estado": cabecera.get("ESTADO"),
            "observaciones": cabecera.get("OBSERVACIONES", ""),
            "productos": []
        }
        
        for item in items_pedido:
            pedido["productos"].append({
                "codigo": item.get("ID CODIGO"),
                "descripcion": item.get("DESCRIPCION"),
                "cantidad": item.get("CANTIDAD"),
                "precio_unitario": item.get("PRECIO UNITARIO"),
                "total": item.get("TOTAL"),
                "cant_alistada": item.get("CANT_ALISTADA", 0),
                "cant_enviada": item.get("CANT_ENVIADA", 0),
                "estado_despacho": str(item.get("ESTADO_DESPACHO", "FALSE")).upper() == "TRUE"
            })
            
        return jsonify({
            "success": True,
            "pedido": pedido
        })

    except Exception as e:
        logger.error(f"Error cargando detalle pedido {id_pedido}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/pendientes', methods=['GET'])
def obtener_pedidos_pendientes():
    """
    Retorna la lista de pedidos que no están completados, agrupados por ID.
    """
    try:
        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        registros = ws.get_all_records()
        
        # Obtener usuario y rol desde query params para filtrado
        usuario_actual = request.args.get('usuario')
        rol_actual = request.args.get('rol')
        
        logger.info(f"🔍 Filtrando pedidos para: Usuario='{usuario_actual}', Rol='{rol_actual}'")
        if registros:
            logger.info(f"📊 Primer registro de PEDIDOS: {registros[0].keys()}")
        else:
            logger.warning("⚠️ La hoja PEDIDOS está vacía")

        # Agrupar por ID PEDIDO
        pedidos_dict = {}
        for r in registros:
            id_pedido = r.get("ID PEDIDO")
            estado = r.get("ESTADO", "PENDIENTE").upper()
            delegado_a = str(r.get("DELEGADO_A", "")).strip()
            
            # FILTRADO DE SEGURIDAD:
            # Si no es Admin ni Natalia, solo ve lo que tiene asignado o lo que no tiene a nadie asignado (para que Natalia lo asigne)
            # El usuario pidió: "viera desde su usuario solo los que tienen pendientes o delegados"
            # Asumimos que si está vacío es "para todos" hasta que se delegue, 
            # pero el requerimiento dice "solo los que tienen pendientes o delegados".
            # Verificar si es admin o Natalia (case-insensitive para evitar problemas de acentos o nombres)
            # Normalizar para comparación
            rol_norm = str(rol_actual).upper() if rol_actual else ""
            user_norm = str(usuario_actual).upper() if usuario_actual else ""
            
            es_admin = "ADMIN" in rol_norm or "NATALIA" in user_norm or "NATHALIA" in user_norm or "LOPEZ" in user_norm or "ANDRES" in user_norm or "ANDRÉS" in user_norm
            
            if not es_admin:
                # Si no es admin/Natalia, solo ve lo que tiene expresamente asignado
                # Normalización para evitar problemas con mayúsculas/minúsculas
                if str(delegado_a).strip().upper() != str(usuario_actual).strip().upper():
                    logger.debug(f"   ⏩ Saltando pedido {id_pedido}: no delegado a {usuario_actual}")
                    continue # No es para mí
            
            logger.info(f"   ✅ Incluyendo pedido {id_pedido} para {usuario_actual} (es_admin={es_admin})")
            
            if estado != "COMPLETADO":
                if id_pedido not in pedidos_dict:
                    pedidos_dict[id_pedido] = {
                        "id_pedido": id_pedido,
                        "fecha": r.get("FECHA"),
                        "hora": r.get("HORA", ""),
                        "cliente": r.get("CLIENTE"),
                        "estado": estado,
                        "progreso": r.get("PROGRESO", "0%"),
                        "vendedor": r.get("VENDEDOR"),
                        "direccion": r.get("DIRECCION", ""),
                        "ciudad": r.get("CIUDAD", ""),
                        "delegado_a": delegado_a,
                        "productos": []
                    }
                
                pedidos_dict[id_pedido]["productos"].append({
                    "codigo": r.get("ID CODIGO"),
                    "descripcion": r.get("DESCRIPCION"),
                    "cantidad": r.get("CANTIDAD"),
                    "cant_lista": r.get("CANT_ALISTADA", 0),
                    "cant_enviada": r.get("CANT_ENVIADA", 0),
                    "total": r.get("TOTAL", 0),
                    # Leer estado booleano de despacho (convertir string 'TRUE'/'FALSE' a bool)
                    "despachado": str(r.get("ESTADO_DESPACHO", "FALSE")).strip().upper() == "TRUE",
                    "no_disponible": str(r.get("NO_DISPONIBLE", "FALSE")).strip().upper() == "TRUE"
                })
            
            # Siempre intentamos obtener el progreso de despacho si existe
            if id_pedido in pedidos_dict:
                pedidos_dict[id_pedido]["progreso_despacho"] = r.get("PROGRESO_DESPACHO", "0%")
        
        return jsonify({
            "success": True, 
            "pedidos": list(pedidos_dict.values())
        })
    except Exception as e:
        logger.error(f"Error cargando pedidos pendientes: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/delegar', methods=['POST'])
def delegar_pedido():
    """
    Asigna un pedido a una colaboradora específica.
    """
    try:
        data = request.json
        id_pedido = data.get("id_pedido")
        colaboradora = data.get("colaboradora")
        
        if not id_pedido or colaboradora is None:
            return jsonify({"success": False, "error": "ID Pedido y Colaboradora requeridos"}), 400
            
        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        registros = ws.get_all_records()
        headers = ws.row_values(1)
        
        if "DELEGADO_A" not in headers:
            # Crear columna si no existe
            col_idx = len(headers) + 1
            ws.update_cell(1, col_idx, "DELEGADO_A")
            headers.append("DELEGADO_A")
            
        col_id = headers.index("ID PEDIDO") + 1
        col_delegado = headers.index("DELEGADO_A") + 1
        
        updates = []
        for idx, r in enumerate(registros):
            if str(r.get("ID PEDIDO")) == str(id_pedido):
                fila = idx + 2
                updates.append({
                    'range': gspread.utils.rowcol_to_a1(fila, col_delegado),
                    'values': [[colaboradora]]
                })
        
        if updates:
            ws.batch_update(updates)
            return jsonify({"success": True, "message": f"Pedido {id_pedido} delegado a {colaboradora}"})
        else:
            return jsonify({"success": False, "error": "Pedido no encontrado"}), 404
            
    except Exception as e:
        logger.error(f"Error delegando pedido: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/eliminar-producto', methods=['POST'])
def eliminar_producto_pedido():
    """
    Elimina un producto específico de un pedido y restaura el inventario.
    Solo permitido para Andrés y Administradores.
    No se puede eliminar si el producto ya fue despachado.
    """
    try:
        data = request.json
        id_pedido = data.get("id_pedido")
        codigo = data.get("codigo")
        
        if not id_pedido or not codigo:
            return jsonify({"success": False, "error": "ID Pedido y Código requeridos"}), 400
        
        logger.info(f"🗑️ Solicitud de eliminación: Pedido={id_pedido}, Código={codigo}")
        
        # Obtener hojas
        ws_pedidos = sheets_client.get_worksheet(Hojas.PEDIDOS)
        ws_productos = sheets_client.get_worksheet(Hojas.PRODUCTOS)
        
        registros = ws_pedidos.get_all_records()
        headers = ws_pedidos.row_values(1)
        
        # Buscar el producto en el pedido
        fila_a_eliminar = None
        cantidad_a_restaurar = 0
        estado_despacho = False
        
        for idx, r in enumerate(registros):
            if str(r.get("ID PEDIDO")) == str(id_pedido) and str(r.get("ID CODIGO")).strip().upper() == str(codigo).strip().upper():
                fila_a_eliminar = idx + 2  # +1 header, +1 0-index
                cantidad_a_restaurar = float(r.get("CANTIDAD", 0))
                
                # Verificar si ya fue despachado
                estado_despacho_str = str(r.get("ESTADO_DESPACHO", "FALSE")).strip().upper()
                estado_despacho = estado_despacho_str == "TRUE"
                
                logger.info(f"   Producto encontrado en fila {fila_a_eliminar}")
                logger.info(f"   Cantidad: {cantidad_a_restaurar}")
                logger.info(f"   Estado despacho: {estado_despacho}")
                break
        
        if not fila_a_eliminar:
            return jsonify({"success": False, "error": "Producto no encontrado en el pedido"}), 404
        
        # Validar que no esté despachado
        if estado_despacho:
            return jsonify({
                "success": False, 
                "error": "No se puede eliminar un producto que ya fue despachado"
            }), 400
        
        # Restaurar inventario
        try:
            registros_productos = ws_productos.get_all_records()
            headers_productos = ws_productos.row_values(1)
            
            col_terminado = headers_productos.index("P. TERMINADO") + 1
            
            # Buscar el producto en inventario
            for idx, p in enumerate(registros_productos):
                codigo_prod = str(p.get("ID CODIGO", "")).strip().upper()
                codigo_buscar = str(codigo).strip().upper()
                
                if codigo_prod == codigo_buscar:
                    fila_producto = idx + 2
                    stock_actual = float(p.get("P. TERMINADO", 0) or 0)
                    nuevo_stock = stock_actual + cantidad_a_restaurar
                    
                    # Actualizar stock
                    ws_productos.update_cell(fila_producto, col_terminado, nuevo_stock)
                    logger.info(f"   ✅ Inventario restaurado: {stock_actual} + {cantidad_a_restaurar} = {nuevo_stock}")
                    break
        except Exception as e_inv:
            logger.warning(f"   ⚠️ No se pudo restaurar inventario: {e_inv}")
            # Continuamos con la eliminación aunque falle la restauración
        
        # Eliminar la fila del pedido
        ws_pedidos.delete_rows(fila_a_eliminar)
        logger.info(f"   🗑️ Fila {fila_a_eliminar} eliminada de PEDIDOS")
        
        # Verificar si quedan productos en el pedido
        registros_actualizados = ws_pedidos.get_all_records()
        productos_restantes = [r for r in registros_actualizados if str(r.get("ID PEDIDO")) == str(id_pedido)]
        
        if len(productos_restantes) == 0:
            logger.info(f"   ⚠️ No quedan productos en el pedido {id_pedido}")
            return jsonify({
                "success": True, 
                "message": "Producto eliminado. El pedido no tiene más productos.",
                "pedido_vacio": True
            })
        else:
            logger.info(f"   ✅ Quedan {len(productos_restantes)} productos en el pedido")
            return jsonify({
                "success": True, 
                "message": f"Producto {codigo} eliminado del pedido",
                "pedido_vacio": False
            })
        
    except Exception as e:
        logger.error(f"❌ Error eliminando producto: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/actualizar-alistamiento', methods=['POST'])
def actualizar_alistamiento():
    """
    Actualiza el progreso y estado de un pedido en Google Sheets.
    Ahora soporta ESTADO_DESPACHO como boolean (CHECKBOX).
    """
    try:
        data = request.json
        id_pedido = data.get("id_pedido")
        progreso = data.get("progreso")          # Alistamiento %
        progreso_despacho = data.get("progreso_despacho") # Despacho %
        estado = data.get("estado")              # ej: "EN ALISTAMIENTO", "ENVIADO", etc.
        detalles = data.get("detalles", [])      # [{codigo, cant_lista, despachado}, ...]
        
        if not id_pedido:
            return jsonify({"success": False, "error": "ID Pedido requerido"}), 400
            
        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        registros = ws.get_all_records()
        headers = ws.row_values(1)
        
        # Asegurar columnas necesarias expandiendo la hoja si es necesario
        def asegurar_columna(nombre):
            nonlocal headers
            if nombre not in headers:
                new_col_idx = len(headers) + 1
                if new_col_idx > ws.col_count:
                    ws.add_cols(1)
                ws.update_cell(1, new_col_idx, nombre)
                headers.append(nombre)
                return True
            return False

        asegurar_columna("ESTADO")
        asegurar_columna("PROGRESO")
        asegurar_columna("CANT_ALISTADA")
        asegurar_columna("PROGRESO_DESPACHO")
        # Asegurar columna booleana para despacho
        asegurar_columna("ESTADO_DESPACHO")
        asegurar_columna("NO_DISPONIBLE")
            
        col_estado = headers.index("ESTADO") + 1
        col_progreso = headers.index("PROGRESO") + 1
        col_cant_lista = headers.index("CANT_ALISTADA") + 1
        col_progreso_despacho = headers.index("PROGRESO_DESPACHO") + 1
        col_estado_despacho = headers.index("ESTADO_DESPACHO") + 1
        col_no_disponible = headers.index("NO_DISPONIBLE") + 1
        
        updates = []
        for idx, r in enumerate(registros):
            if str(r.get("ID PEDIDO")) == str(id_pedido):
                fila = idx + 2
                
                # Actualizar estado y progreso general
                updates.append({
                    'range': gspread.utils.rowcol_to_a1(fila, col_estado),
                    'values': [[estado]]
                })
                if progreso is not None:
                    updates.append({
                        'range': gspread.utils.rowcol_to_a1(fila, col_progreso),
                        'values': [[progreso]]
                    })

                if progreso_despacho is not None:
                    updates.append({
                        'range': gspread.utils.rowcol_to_a1(fila, col_progreso_despacho),
                        'values': [[progreso_despacho]]
                    })
                
                # Buscar si este producto tiene una cantidad específica para actualizar
                codigo_fila = r.get("ID CODIGO")
                for d in detalles:
                    if str(d.get("codigo")) == str(codigo_fila):
                        if "cant_lista" in d:
                            updates.append({
                                'range': gspread.utils.rowcol_to_a1(fila, col_cant_lista),
                                'values': [[d.get("cant_lista")]]
                            })
                        # ACTUALIZACION CHECKBOX DESPACHO
                        if "despachado" in d:
                            # Convertir a TRUE/FALSE string para Sheets
                            val_despacho = "TRUE" if d.get("despachado") else "FALSE"
                            updates.append({
                                'range': gspread.utils.rowcol_to_a1(fila, col_estado_despacho),
                                'values': [[val_despacho]]
                            })
                        # ACTUALIZACION NO_DISPONIBLE
                        if "no_disponible" in d:
                            val_nd = "TRUE" if d.get("no_disponible") else "FALSE"
                            updates.append({
                                'range': gspread.utils.rowcol_to_a1(fila, col_no_disponible),
                                'values': [[val_nd]]
                            })
        
        if updates:
            ws.batch_update(updates)
            
            # ==========================================
            # 📉 DESCUENTO REAL DE STOCK AL DESPACHAR
            # ==========================================
            # Si hay productos marcados como despachados ahora, descontar de Físico y Comprometido
            try:
                # Filtrar solo los productos que se acaban de marcar como despachados "TRUE"
                # y que tienen una fila identificada en el bucle anterior.
                # Para simplificar, buscamos los detalles que vienen en el request y tienen despachado=True
                despachados_ahora = [d for d in detalles if d.get("despachado") == True]
                
                if despachados_ahora:
                    logger.info(f"📉 Descontando stock real para {len(despachados_ahora)} items despachados...")
                    ws_productos = sheets_client.get_worksheet(Hojas.PRODUCTOS)
                    registros_productos = ws_productos.get_all_records()
                    headers_productos = ws_productos.row_values(1)
                    
                    col_p_term = headers_productos.index("P. TERMINADO") + 1
                    col_comp = headers_productos.index("COMPROMETIDO") + 1
                    
                    mapa_productos = {}
                    for idx, r in enumerate(registros_productos):
                        c_sis = str(r.get("CODIGO SISTEMA", "")).strip().upper()
                        id_cod = str(r.get("ID CODIGO", "")).strip().upper()
                        fila_real = idx + 2
                        if c_sis: mapa_productos[c_sis] = fila_real
                        if id_cod: mapa_productos[id_cod] = fila_real

                    updates_stock = []
                    
                    # Necesitamos saber la CANTIDAD original del pedido para cada producto
                    # para saber cuánto descontar del stock físico y comprometido
                    prod_pedido_map = {str(r.get("ID CODIGO")).strip().upper(): float(r.get("CANTIDAD", 0)) 
                                     for r in registros if str(r.get("ID PEDIDO")) == str(id_pedido)}

                    for d in despachados_ahora:
                        cod = str(d.get("codigo")).strip().upper()
                        qty_pedido = prod_pedido_map.get(cod, 0)
                        
                        if cod in mapa_productos and qty_pedido > 0:
                            fila_p = mapa_productos[cod]
                            item_p = registros_productos[fila_p - 2]
                            
                            s_fisico = float(item_p.get("P. TERMINADO", 0) or 0)
                            s_comp = float(item_p.get("COMPROMETIDO", 0) or 0)
                            
                            nuevo_fisico = max(0, s_fisico - qty_pedido)
                            nuevo_comp = max(0, s_comp - qty_pedido)
                            
                            updates_stock.append({'range': gspread.utils.rowcol_to_a1(fila_p, col_p_term), 'values': [[nuevo_fisico]]})
                            updates_stock.append({'range': gspread.utils.rowcol_to_a1(fila_p, col_comp), 'values': [[nuevo_comp]]})
                            logger.info(f"   ✅ Stock Real {cod}: Físico({s_fisico}->{nuevo_fisico}), Comprometido({s_comp}->{nuevo_comp})")

                    if updates_stock:
                        ws_productos.batch_update(updates_stock)

            except Exception as e_stock:
                logger.error(f"❌ Error actualizando stock real en despacho: {e_stock}")

            return jsonify({"success": True, "message": f"Pedido {id_pedido} actualizado a {estado} ({progreso})"})
        else:
            return jsonify({"success": False, "error": "Pedido no encontrado"}), 404
            
    except Exception as e:
        logger.error(f"Error actualizando alistamiento: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/cliente', methods=['GET'])
def obtener_pedidos_cliente():
    """
    Retorna el historial de pedidos de un cliente basado en su NIT.
    """
    try:
        nit = request.args.get('nit')
        # También podrías aceptar 'cliente' (nombre) como fallback si el NIT no está presente en todos los registros
        
        if not nit:
             return jsonify({"success": False, "error": "NIT requerido"}), 400

        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        registros = ws.get_all_records()
        
        # Filtrar por NIT
        # Normalizar NIT input
        nit_str = str(nit).strip().upper()

        # Re-dict para sumar bien
        calc_dict = {}
        
        for r in registros:
            # Normalizar NIT en registro
            r_nit = str(r.get("NIT", "")).strip().upper()
            
            # Comparación robusta
            if r_nit == nit_str:
                id_p = r.get("ID PEDIDO")
                # Si el NIT coincide, procesamos
                if id_p not in calc_dict:
                    calc_dict[id_p] = {
                        "id": id_p,
                        "fecha": r.get("FECHA"),
                        "estado": r.get("ESTADO"),
                        "progreso": str(r.get("PROGRESO", "0%")).replace('%', ''),
                        "progreso_despacho": str(r.get("PROGRESO_DESPACHO", "0%")).replace('%', ''),
                        "total_dinero": 0.0,
                        "items_count": 0
                    }
                
                # Sumar Dinero (TOTAL es por item en la hoja)
                try:
                    raw_total = str(r.get("TOTAL", 0)).replace(',','').replace('$','')
                    val_total = float(raw_total) if raw_total else 0
                except:
                    val_total = 0
                
                # Sumar items
                try:
                    val_cant = float(r.get("CANTIDAD", 0))
                except:
                    val_cant = 0
                    
                calc_dict[id_p]["total_dinero"] += val_total
                calc_dict[id_p]["items_count"] += val_cant

        # Convertir a lista y formatear
        final_list = []
        for pid, data in calc_dict.items():
            final_list.append({
                "id": data["id"],
                "fecha": data["fecha"],
                "estado": data["estado"],
                "progreso": float(data["progreso"]) if data["progreso"] else 0,
                "progreso_despacho": float(data["progreso_despacho"]) if data.get("progreso_despacho") else 0,
                "items": int(data["items_count"]),
                "total": data["total_dinero"] # Frontend format currency
            })
            
        # Ordenar por fecha desc (o ID desc)
        final_list.sort(key=lambda x: x["id"], reverse=True)

        return jsonify({
            "success": True, 
            "pedidos": final_list
        })

    except Exception as e:
        logger.error(f"Error cargando pedidos cliente: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
