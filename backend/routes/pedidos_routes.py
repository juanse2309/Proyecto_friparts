from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_COMERCIALES, ROL_JEFES
from flask import Blueprint, jsonify, request, session
from backend.core.database import sheets_client
from backend.config.settings import Hojas, TenantConfig
from backend.core.tenant import get_tenant_from_request
import gspread
from datetime import datetime
import logging
import json
import pytz


pedidos_bp = Blueprint('pedidos', __name__)
logger = logging.getLogger(__name__)


def _resolve_tenant():
    """Resuelve el tenant desde la sesión y retorna (tenant, hoja_pedidos, hoja_productos)."""
    tenant = get_tenant_from_request()
    hoja_pedidos = TenantConfig.get(tenant, 'PEDIDOS')
    hoja_productos = TenantConfig.get(tenant, 'PRODUCTOS')
    logger.info(f"🏢 [Tenant] Resuelto: {tenant} → PEDIDOS={hoja_pedidos}, PRODUCTOS={hoja_productos}")
    return tenant, hoja_pedidos, hoja_productos

def _buscar_producto_inteligente(codigo_buscado, registros):
    """
    Búsqueda inteligente en registros de PRODUCTOS.
    Jerarquía: Exacto > Prefijo (solo para CAR, INT, ENS, CB).
    Retorna (fila_real, datos_dict) o (None, None).
    """
    target = str(codigo_buscado).strip().upper()
    if not target:
        return None, None

    PREFIJOS_FLEX = ("CAR", "INT", "ENS", "CB")
    es_comp = target.startswith(PREFIJOS_FLEX)

    for idx, r in enumerate(registros):
        v_sis = str(r.get("CODIGO SISTEMA", "")).strip().upper()
        v_id = str(r.get("ID CODIGO", "")).strip().upper()

        # 1. Coincidencia Exacta
        if target == v_sis or target == v_id:
            return idx + 2, r

        # 2. Coincidencia por Prefijo (Solo componentes)
        if es_comp:
            if v_sis.startswith(target) or v_id.startswith(target):
                logger.info(f"   🔍 [Prefix Match] '{target}' hallado en '{v_sis or v_id}'")
                return idx + 2, r

    return None, None

def obtener_siguiente_id_pedido(hoja_pedidos=None):
    """Genera el siguiente ID secuencial con formato PED9643 (o MPED para Frimetals)."""
    try:
        nombre_hoja = hoja_pedidos or Hojas.PEDIDOS
        ws = sheets_client.get_worksheet(nombre_hoja)
        if not ws:
            raise ValueError(f"Hoja {nombre_hoja} no encontrada")
        col_values = ws.col_values(1)  # columna A = ID PEDIDO
        
        import re
        max_num = 0
        base_inicial = 9644
        
        for val in col_values[1:]:
            val_str = str(val).strip().upper()
            # Buscamos estrictamente formato PED seguido de SOLAMENTE DIGITOS (no PED-UUID)
            match = re.match(r'^PED(\d+)$', val_str)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
        
        # Si no encontramos ningún PEDxxxx, iniciamos en la base solicitada
        if max_num == 0:
            return f"PED{base_inicial}"
            
        return f"PED{max_num + 1}"
    except Exception as e:
        logger.error(f"Error generando siguiente ID pedido: {e}")
        return f"PED{datetime.now().strftime('%M%S')}" # Fallback seguro

def _generar_siguiente_id_pedido_sql():
    """Genera el siguiente consecutivo PED-XXXX consultando la base de datos SQL."""
    from backend.models.sql_models import Pedido
    from backend.core.sql_database import db
    from sqlalchemy import text
    try:
        # Buscar el último registro que tenga el formato PED- usando SQL crudo para mayor precisión en el ordenamiento
        sql = "SELECT id_pedido FROM db_pedidos WHERE id_pedido LIKE 'PED-%' ORDER BY id DESC LIMIT 1"
        result = db.session.execute(text(sql)).fetchone()
        
        if not result or not result[0]:
            return "PED-1001" # Base inicial
            
        import re
        match = re.search(r'PED-(\d+)', result[0])
        if match:
            ultimo_num = int(match.group(1))
            return f"PED-{ultimo_num + 1}"
        
        return f"PED-{datetime.now().strftime('%M%S')}" # Fallback
    except Exception as e:
        logger.error(f"❌ Error generando ID Pedido SQL: {e}")
        return f"PED-{datetime.now().strftime('%M%S')}"

@pedidos_bp.route('/api/pedidos/registrar', methods=['POST'])
@require_role(ROL_ADMINS + ROL_COMERCIALES + ['JEFE ALMACEN'])
def registrar_pedido():
    """
    Registra un pedido en PostgreSQL (SQL-Native).
    Elimina dependencia total de Google Sheets para el guardado.
    """
    from backend.models.sql_models import Pedido
    from backend.core.sql_database import db
    
    try:
        # Asegurar transacción limpia (Evitar InFailedSqlTransaction persistente)
        db.session.rollback()
        
        logger.info("🛒 ===== INICIO REGISTRO DE PEDIDO (SQL-NATIVE) =====")
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # 1. Extracción y Validación
        fecha_str = data.get('fecha')
        vendedor = data.get('vendedor')
        cliente = data.get('cliente')
        nit = data.get('nit', '')
        direccion = data.get('direccion', '')
        ciudad = data.get('ciudad', '')
        forma_pago = data.get('forma_pago', 'Contado')
        descuento_global = str(data.get('descuento_global', '0'))
        observaciones = data.get('observaciones', '')
        productos = data.get('productos', [])
        
        print(f"DEBUG: [REGISTRO] Cliente: {cliente} | Dir: {direccion} | Ciudad: {ciudad} | Pago: {forma_pago} | Desc: {descuento_global}%")
        print(f"DEBUG: [REGISTRO] Productos recibidos: {len(productos)}")
        
        if not all([fecha_str, vendedor, cliente]):
            return jsonify({"success": False, "error": "Faltan campos obligatorios: fecha, vendedor, cliente"}), 400
            
        # 2. Generar ID Único Secuencial (PED-XXXX)
        id_pedido = _generar_siguiente_id_pedido_sql()
        logger.info(f"🆔 ID Generado para SQL: {id_pedido}")

        # Convertir fecha
        try:
            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except:
            fecha_dt = datetime.now().date()

        # Capturar hora actual
        try:
            import pytz
            tz_colombia = pytz.timezone('America/Bogota')
            hora_actual = datetime.now(tz_colombia).strftime('%I:%M %p')
        except:
            hora_actual = datetime.now().strftime('%I:%M %p')

        # 3. Guardar cada ítem del pedido en la tabla db_pedidos
        if not productos:
             return jsonify({"success": False, "error": "Debe incluir al menos un producto"}), 400

        items_agregados = 0
        for prod in productos:
            codigo = str(prod.get('codigo', '')).strip().upper()
            cantidad = float(prod.get('cantidad', 0))
            precio = float(prod.get('precio_unitario', 0))
            descripcion = prod.get('descripcion', '')
            total_item = cantidad * precio
            
            if not codigo or cantidad <= 0:
                continue

            nuevo_registro = Pedido(
                id_pedido=id_pedido,
                fecha=fecha_dt,
                hora=hora_actual,
                cliente=cliente,
                nit=nit,
                direccion=direccion,
                ciudad=ciudad,
                vendedor=vendedor,
                id_codigo=codigo,
                descripcion=descripcion,
                cantidad=cantidad,
                precio_unitario=precio,
                total=total_item,
                estado='PENDIENTE',
                observaciones=observaciones,
                forma_de_pago=forma_pago,
                descuento=descuento_global
            )
            db.session.add(nuevo_registro)
            items_agregados += 1
            
        # 4. Transacción Atómica
        db.session.commit()
        logger.info(f"✅ Pedido {id_pedido} guardado físicamente en PostgreSQL. Items: {items_agregados}")

        # Invalidad caché de pedidos
        try:
            from backend.app import invalidar_cache_pedidos
            invalidar_cache_pedidos()
        except:
            pass

        return jsonify({
            "success": True, 
            "status": "success",
            "message": f"Pedido {id_pedido} registrado exitosamente",
            "id_pedido": id_pedido,
            "total_productos": len(productos),
            "productos_guardados": items_agregados
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ ERROR registrando pedido SQL: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/detalle/<id_pedido>', methods=['GET'])
def obtener_detalle_pedido(id_pedido):
    """
    Obtiene el detalle completo de un pedido desde PostgreSQL (SQL-Native).
    Útil para la funcionalidad de 'Retomar Pedido' y edición.
    """
    from backend.models.sql_models import Pedido
    try:
        if not id_pedido:
             return jsonify({"success": False, "error": "ID Pedido requerido"}), 400

        id_pedido_buscado = str(id_pedido).strip().upper()
        logger.info(f"🔍 [SQL-DETALLE] Consultando pedido: {id_pedido_buscado}")
        
        # 1. Buscar todos los items en SQL
        items_sql = Pedido.query.filter_by(id_pedido=id_pedido_buscado).all()
        
        if not items_sql:
            return jsonify({
                "success": False, 
                "error": f"Pedido {id_pedido} no encontrado en SQL"
            }), 404
            
        # 2. Construir cabecera (usando el primer item)
        cab = items_sql[0]
        
        # Formatear fecha para el input date del frontend (YYYY-MM-DD)
        fecha_str = cab.fecha.strftime('%Y-%m-%d') if cab.fecha else ""

        pedido = {
            "id_pedido": cab.id_pedido,
            "fecha": fecha_str,
            "hora": cab.hora or "",
            "vendedor": cab.vendedor,
            "cliente": cab.cliente,
            "nit": cab.nit or "",
            "direccion": getattr(cab, 'direccion', '') or "",
            "ciudad": getattr(cab, 'ciudad', '') or "",
            "forma_pago": getattr(cab, 'forma_de_pago', 'Contado') or "Contado",
            "descuento_global": getattr(cab, 'descuento', '0') or "0",
            "estado": cab.estado,
            "observaciones": cab.observaciones or "",
            "productos": []
        }
        
        def _clean_numeric(val):
            if not val or str(val).strip() in ['', 'None']: return 0
            # Limpieza matemática: remover símbolos pero NO el punto decimal
            s = str(val).replace('$', '').replace(',', '').strip()
            try:
                # Primero convertimos a float (entiende el punto) y luego a int si necesario
                return int(float(s))
            except: return 0

        # 3. Mapear productos con limpieza de tipos (PG OID 25 Fix)
        for item in items_sql:
            # Asegurar que cantidad alistada sea un número limpio para el modal
            cantidad_lista = _clean_numeric(item.cant_alistada)
            
            pedido["productos"].append({
                "codigo": item.id_codigo,
                "descripcion": item.descripcion or "Sin descripción",
                "cantidad": _clean_numeric(item.cantidad),
                "precio_unitario": _clean_numeric(item.precio_unitario),
                "total": _clean_numeric(item.total),
                "cant_alistada": cantidad_lista,
                "cant_lista": cantidad_lista, # Mapeo para el modal del almacén
                "progreso": item.progreso or "0%"
            })
        
        return jsonify({
            "success": True,
            "pedido": pedido
        })

    except Exception as e:
        logger.error(f"❌ ERROR obteniendo detalle pedido SQL: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/pendientes', methods=['GET'])
def obtener_pedidos_pendientes():
    """
    Retorna la lista de pedidos que no están completados.
    Ahora utiliza SQL-First con JOIN de clientes para evitar valores null.
    """
    try:
        from backend.core.repository_service import repository_service

        # 1. Obtener datos desde SQL (JOIN incluido)
        pedidos = repository_service.get_pedidos_pendientes_sql()
        
        # 2. Determinar tenant para filtrado
        tenant = get_tenant_from_request()

        # 3. Filtrar por usuario y rol (Lógica RBAC Estricta)
        # Compatibilidad: Chequear 'rol' (legacy) y 'role' (estándar)
        user_session = str(session.get('user', '')).strip().upper()
        rol_session = str(session.get('rol') or session.get('role', '')).lower()
        
        # Roles con visibilidad global
        es_admin = any(x in rol_session for x in ["admin", "administracion", "administrador", "gerencia", "jefe almacen", "comercial", "metals_staff", "metals_admin"])

        filtrados = []
        for p in pedidos:
            if es_admin or tenant == "frimetals":
                filtrados.append(p)
            else:
                # Si no es admin y es Friparts, solo ve lo que tiene asignado
                if str(p.get("Delegado_a", "")).strip().upper() == user_session:
                    filtrados.append(p)

        # 4. DEBUG EN TERMINAL (Solicitado por el usuario)
        print(f"DEBUG ALMACEN: Rol detectado: {rol_session}, Pedidos totales SQL: {len(pedidos)}, Pedidos filtrados: {len(filtrados)}")

        return jsonify({
            "success": True, 
            "pedidos": filtrados
        })
    except Exception as e:
        logger.error(f"Error cargando pedidos pendientes (SQL): {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@pedidos_bp.route('/api/pedidos/delegar', methods=['POST'])
@require_role(ROL_ADMINS + ROL_COMERCIALES + ['JEFE ALMACEN'])
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
            
        _, hoja_pedidos, _ = _resolve_tenant()
        ws = sheets_client.get_worksheet(hoja_pedidos)
        registros = sheets_client.get_all_records_seguro(ws)
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
            from backend.app import invalidar_cache_pedidos
            invalidar_cache_pedidos()
            return jsonify({"success": True, "message": f"Pedido {id_pedido} delegado a {colaboradora}"})
        else:
            return jsonify({"success": False, "error": "Pedido no encontrado"}), 404
            
    except Exception as e:
        logger.error(f"Error delegando pedido: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/eliminar-producto', methods=['POST'])
@require_role(ROL_ADMINS + ['JEFE ALMACEN'])
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
        _, hoja_pedidos, hoja_productos = _resolve_tenant()
        ws_pedidos = sheets_client.get_worksheet(hoja_pedidos)
        ws_productos = sheets_client.get_worksheet(hoja_productos)
        
        registros = sheets_client.get_all_records_seguro(ws_pedidos)
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
            registros_productos = sheets_client.get_all_records_seguro(ws_productos)
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
        registros_actualizados = sheets_client.get_all_records_seguro(ws_pedidos)
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
    Actualiza el progreso y estado de un pedido en PostgreSQL (SQL-Native).
    Elimina dependencia de Google Sheets.
    """
    from backend.models.sql_models import Pedido
    from backend.core.sql_database import db
    
    try:
        data = request.json
        id_pedido = data.get("id_pedido")
        estado_general = data.get("estado") # ej: "EN ALISTAMIENTO"
        detalles = data.get("detalles", []) # [{codigo, cant_lista}, ...]
        
        if not id_pedido:
            return jsonify({"success": False, "error": "ID Pedido requerido"}), 400
            
        logger.info(f"📦 [SQL-ALISTAMIENTO] Actualizando pedido: {id_pedido}")

        # 1. Buscar todos los items del pedido en SQL
        items_sql = Pedido.query.filter_by(id_pedido=id_pedido).all()
        
        if not items_sql:
            return jsonify({"success": False, "error": f"Pedido {id_pedido} no encontrado en SQL"}), 404

        items_actualizados = 0
        def _clean_num(val):
            if not val or str(val).strip() in ['', 'None']: return 0
            s = str(val).replace('$', '').replace('.', '').replace(',', '').strip()
            try: return float(s)
            except: return 0

        for d in detalles:
            codigo_front = str(d.get("codigo", "")).strip().upper()
            cant_lista_front = _clean_num(d.get("cant_lista", 0))
            
            # Buscar el match en SQL para este código dentro del pedido
            item = next((i for i in items_sql if str(i.id_codigo).strip().upper() == codigo_front), None)
            
            if item:
                # 1. Obtener tope máximo y aplicar filtro min() de seguridad
                cantidad_total = _clean_num(item.cantidad)
                cant_segura = min(cant_lista_front, cantidad_total)
                
                # 2. Persistir cantidad segura (como entero para evitar bug de .0 -> 000)
                item.cant_alistada = str(int(cant_segura))
                
                # Lógica de progreso y estado por item
                cantidad_total = _clean_num(item.cantidad)
                if cantidad_total > 0:
                    porcentaje = (cant_lista_front / cantidad_total) * 100
                    item.progreso = f"{int(porcentaje)}%"
                    
                    if cant_lista_front >= cantidad_total:
                        item.estado = 'ALISTADO'
                        item.progreso = '100%'
                    else:
                        item.estado = estado_general or 'EN ALISTAMIENTO'
                
                items_actualizados += 1

        db.session.commit()
        logger.info(f"✅ [SQL-ALISTAMIENTO] {items_actualizados} items actualizados para {id_pedido}")

        # Opcional: Invalidar caché
        try:
            from backend.app import invalidar_cache_pedidos
            invalidar_cache_pedidos()
        except: pass

        return jsonify({
            "success": True, 
            "message": f"Progreso actualizado en SQL para {items_actualizados} productos"
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error alistamiento SQL: {e}")
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

        _, hoja_pedidos, _ = _resolve_tenant()
        ws = sheets_client.get_worksheet(hoja_pedidos)
        registros = sheets_client.get_all_records_seguro(ws)
        
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
