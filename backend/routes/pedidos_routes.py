from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_COMERCIALES, ROL_JEFES
from flask import Blueprint, jsonify, request, session
from backend.models.sql_models import db, Pedido, MetalsPedido
from sqlalchemy import text
from backend.core.tenant import get_tenant_from_request
from datetime import datetime
import logging
import json
import pytz


pedidos_bp = Blueprint('pedidos', __name__)
logger = logging.getLogger(__name__)


def _resolve_tenant():
    """Resuelve el tenant desde la sesión."""
    tenant = get_tenant_from_request()
    logger.info(f"🏢 [Tenant] Resuelto: {tenant}")
    return tenant

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
    """DEPRECATED: Usar _generar_siguiente_id_pedido_sql."""
    return _generar_siguiente_id_pedido_sql()

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
    Registra o actualiza un pedido en PostgreSQL (SQL-Native).
    Implementa lógica de UPSERT basada en id_sql e id_pedido.
    """
    from backend.models.sql_models import Pedido
    from backend.core.sql_database import db
    
    try:
        # Asegurar transacción limpia
        db.session.rollback()
        
        logger.info("🛒 ===== INICIO REGISTRO DE PEDIDO (UPSERT-MODE) =====")
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
        
        if not all([fecha_str, vendedor, cliente]):
            return jsonify({"success": False, "error": "Faltan campos obligatorios: fecha, vendedor, cliente"}), 400
            
        # 2. Determinar ID de Pedido (Nuevo o Existente)
        id_pedido_final = data.get('id_pedido')
        es_edicion = False
        if not id_pedido_final:
            id_pedido_final = _generar_siguiente_id_pedido_sql()
            logger.info(f"🆔 Nuevo ID Pedido Generado: {id_pedido_final}")
        else:
            id_pedido_final = str(id_pedido_final).strip().upper()
            es_edicion = True
            logger.info(f"🔄 Actualizando Pedido Existente: {id_pedido_final}")

        # Convertir fecha
        try:
            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except:
            fecha_dt = datetime.now().date()

        # Capturar hora actual
        try:
            tz_colombia = pytz.timezone('America/Bogota')
            hora_actual = datetime.now(tz_colombia).strftime('%I:%M %p')
        except:
            hora_actual = datetime.now().strftime('%I:%M %p')

        # 3. Guardar cada ítem con Lógica UPSERT
        if not productos:
             return jsonify({"success": False, "error": "Debe incluir al menos un producto"}), 400

        # Sincronización de eliminaciones: Si es edición, borrar lo que ya no viene en el payload
        if es_edicion:
            ids_enviados = [p.get('id_sql') for p in productos if p.get('id_sql')]
            if ids_enviados:
                try:
                    db.session.execute(
                        text("DELETE FROM db_pedidos WHERE id_pedido = :id_p AND id NOT IN :ids"),
                        {"id_p": id_pedido_final, "ids": tuple(ids_enviados)}
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Error limpiando items eliminados: {e}")

        items_procesados = 0
        for prod in productos:
            id_sql = prod.get('id_sql')
            codigo = str(prod.get('codigo', '')).strip().upper()
            cantidad = float(prod.get('cantidad', 0))
            precio = float(prod.get('precio_unitario', 0))
            descripcion = prod.get('descripcion', '')
            total_item = cantidad * precio
            
            if not codigo or cantidad <= 0:
                continue

            # Buscar registro existente para UPSERT
            registro_existente = None
            if id_sql:
                registro_existente = Pedido.query.get(id_sql)
            else:
                # Fallback: Buscar por id_pedido + id_codigo
                registro_existente = Pedido.query.filter_by(id_pedido=id_pedido_final, id_codigo=codigo).first()

            if registro_existente:
                # SOBREESCRITURA TOTAL (No sumatoria)
                registro_existente.fecha = fecha_dt
                registro_existente.cliente = cliente
                registro_existente.nit = nit
                registro_existente.direccion = direccion
                registro_existente.ciudad = ciudad
                registro_existente.id_codigo = codigo
                registro_existente.descripcion = descripcion
                registro_existente.cantidad = cantidad 
                registro_existente.precio_unitario = precio 
                registro_existente.total = total_item
                registro_existente.observaciones = observaciones
                registro_existente.forma_de_pago = forma_pago
                registro_existente.descuento = descuento_global
            else:
                # INSERT
                nuevo_registro = Pedido(
                    id_pedido=id_pedido_final,
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
            
            items_procesados += 1
            
        # 4. Transacción Final con Commit y Error Handling
        try:
            db.session.commit()
            logger.info(f"✅ Pedido {id_pedido_final} procesado exitosamente. Items: {items_procesados}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en commit de Pedidos: {e}")
            return jsonify({"success": False, "error": f"Error de persistencia: {str(e)}"}), 500

        # Invalidad caché
        try:
            from backend.app import invalidar_cache_pedidos
            invalidar_cache_pedidos()
        except: pass
        
        return jsonify({
            "success": True, 
            "message": f"Pedido {id_pedido_final} procesado correctamente",
            "id_pedido": id_pedido_final
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"💥 Error crítico en registrar_pedido: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Error interno: {str(e)}"}), 500

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

        # 3. Mapear productos (Ya curados por el script)
        for item in items_sql:
            cant_item = _clean_numeric(item.cantidad)
            ali_item = _clean_numeric(item.cant_alistada)
            precio_item = _clean_numeric(item.precio_unitario)
            
            pedido["productos"].append({
                "id_sql": item.id_sql, # CRÍTICO PARA UPSERT
                "codigo": str(item.id_codigo or '').strip().upper(),
                "descripcion": item.descripcion or "Sin descripción",
                "cantidad": cant_item,
                "precio_unitario": precio_item,
                "cant_alistada": ali_item,
                "cant_lista": ali_item,
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
                if str(p.get("delegado_a", "")).strip().upper() == user_session:
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
    """Asigna un pedido a una colaboradora en SQL."""
    try:
        data = request.json
        id_p = data.get("id_pedido")
        colab = data.get("colaboradora")
        
        if not id_p: return jsonify({"error": "ID requerido"}), 400
        
        Pedido.query.filter_by(id_pedido=id_p).update({"delegado_a": colab})
        db.session.commit()
        return jsonify({"success": True, "message": f"Pedido {id_p} delegado a {colab}"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/eliminar-producto', methods=['POST'])
@require_role(ROL_ADMINS + ['JEFE ALMACEN'])
def eliminar_producto_pedido():
    """Elimina un producto de un pedido en SQL y restaura stock."""
    try:
        data = request.json
        id_p = data.get("id_pedido")
        cod = data.get("codigo")
        
        item = Pedido.query.filter_by(id_pedido=id_p, id_codigo=cod).first()
        if not item: return jsonify({"error": "No hallado"}), 404
        
        # Restaurar stock
        from backend.app import actualizar_stock
        actualizar_stock(cod, float(item.cantidad or 0), "STOCK_BODEGA", "ENTRADA", f"ELIMINACION {id_p}")
        
        db.session.delete(item)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/actualizar-alistamiento', methods=['POST'])
def actualizar_alistamiento():
    """
    Actualiza el progreso y estado de un pedido en PostgreSQL (SQL-Native).
    Elimina dependencia de Google Sheets.
    """
    from backend.models.sql_models import Pedido
    from backend.core.sql_database import db
    
    try:
        data = request.json or {}
        id_pedido = data.get("id_pedido")
        estado_general = data.get("estado")  # ej: "EN ALISTAMIENTO"
        progreso_pedido = data.get("progreso")  # ej: "40%"
        progreso_despacho_pedido = data.get("progreso_despacho")  # ej: "10%"
        detalles = data.get("detalles", [])  # [{codigo, cant_lista, despachado, no_disponible}, ...]
        
        if not id_pedido:
            return jsonify({"success": False, "error": "ID Pedido requerido"}), 400
            
        logger.info(f"📦 [SQL-ALISTAMIENTO] Actualizando pedido: {id_pedido}")

        # 1. Buscar todos los items del pedido en SQL
        items_sql = Pedido.query.filter_by(id_pedido=id_pedido).all()
        
        if not items_sql:
            return jsonify({"success": False, "error": f"Pedido {id_pedido} no encontrado en SQL"}), 404

        items_actualizados = 0

        def _clean_num(val):
            """
            Convierte entradas como '10', '10.0', '10%', '$1,200' a float.
            Mantiene el punto decimal; remueve símbolos y separadores de miles.
            """
            if val is None:
                return 0.0
            s = str(val).strip()
            if s in ['', 'None', 'null', 'undefined']:
                return 0.0
            s = s.replace('%', '').replace('$', '').replace(' ', '')
            # Quitar separadores de miles (coma) sin tocar el punto decimal
            s = s.replace(',', '')
            try:
                return float(s)
            except Exception:
                return 0.0

        def _clean_pct_str(val, default="0%"):
            if val is None:
                return default
            s = str(val).strip()
            if not s:
                return default
            # normalizar "40" -> "40%"
            if not s.endswith('%'):
                s = f"{s}%"
            return s

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
                    porcentaje = (cant_segura / cantidad_total) * 100
                    item.progreso = f"{int(porcentaje)}%"
                    
                    if cant_segura >= cantidad_total:
                        item.estado = 'ALISTADO'
                        item.progreso = '100%'
                    else:
                        item.estado = estado_general or 'EN ALISTAMIENTO'
                
                items_actualizados += 1

        # Persistir estado/progresos a nivel pedido (en TODAS las filas),
        # porque el listado agrupa tomando el primer item del pedido.
        if estado_general or progreso_pedido or progreso_despacho_pedido:
            update_data = {}
            if estado_general:
                update_data["estado"] = estado_general
            if progreso_pedido is not None:
                update_data["progreso"] = _clean_pct_str(progreso_pedido)
            if progreso_despacho_pedido is not None:
                update_data["progreso_despacho"] = _clean_pct_str(progreso_despacho_pedido)
            if update_data:
                Pedido.query.filter_by(id_pedido=id_pedido).update(update_data)

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
    """Historial de pedidos por NIT desde SQL (db_pedidos)."""
    try:
        nit = request.args.get('nit')
        if not nit: return jsonify({"error": "NIT requerido"}), 400
        
        items = Pedido.query.filter_by(nit=str(nit)).all()
        # Agrupar por id_pedido
        ped_map = {}
        for r in items:
            id_p = r.id_pedido
            if id_p not in ped_map:
                ped_map[id_p] = {
                    "id": id_p,
                    "fecha": r.fecha.strftime('%Y-%m-%d') if r.fecha else "",
                    "hora": str(r.hora or "").strip(),
                    "estado": r.estado,
                    "items": 0,
                    "total": 0.0
                }
            else:
                if not ped_map[id_p]["hora"] and r.hora:
                    ped_map[id_p]["hora"] = str(r.hora).strip()
            
            ped_map[id_p]["items"] += float(r.cantidad or 0)
            ped_map[id_p]["total"] += float(r.total or 0)
            
        final = sorted(list(ped_map.values()), key=lambda x: x['id'], reverse=True)
        return jsonify({"success": True, "pedidos": final})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@pedidos_bp.route('/api/pedidos/listar', methods=['GET'])
def listar_pedidos():
    """Listado general de pedidos con soporte estricto para FriMetals."""
    try:
        division = request.args.get('division', 'friparts').lower()
        search = request.args.get('search', '').strip().upper()
        
        logger.info(f"🔍 [API] Listando pedidos - División: {division}, Búsqueda: {search}")

        if division == 'frimetals':
            # Consulta a la tabla metals_pedidos (mapeada en sql_models.py)
            query = MetalsPedido.query
            if search:
                query = query.filter(
                    (MetalsPedido.id_pedido.ilike(f'%{search}%')) |
                    (MetalsPedido.cliente.ilike(f'%{search}%'))
                )
            
            # Orden descendente por fecha e id_pedido
            rows = query.order_by(MetalsPedido.fecha.desc(), MetalsPedido.id_pedido.desc()).limit(200).all()
            
            # Agrupación por id_pedido para soportar múltiples ítems por orden
            ped_map = {}
            for r in rows:
                id_p = r.id_pedido
                if id_p not in ped_map:
                    ped_map[id_p] = {
                        "id_pedido": id_p,
                        "fecha": str(r.fecha) if r.fecha else "",
                        "cliente": r.cliente,
                        "vendedor": r.vendedor,
                        "estado": r.estado or "REGISTRADO",
                        "progreso": r.progreso or 0,
                        "items_count": 0,
                        "total": 0,
                        "productos": []
                    }
                
                ped_map[id_p]["items_count"] += 1
                ped_map[id_p]["total"] += (r.total or 0)
                ped_map[id_p]["productos"].append({
                    "id_codigo": r.id_codigo,
                    "descripcion": r.descripcion,
                    "cantidad": r.cantidad or 0,
                    "precio": r.precio_unitario or 0,
                    "total": r.total or 0
                })
            
            # Devolver lista de pedidos agrupados
            return jsonify({
                "success": True, 
                "pedidos": sorted(list(ped_map.values()), key=lambda x: x['id_pedido'], reverse=True)
            }), 200
            
        else:
            # Lógica estándar FriParts (db_pedidos)
            query = Pedido.query
            if search:
                query = query.filter(
                    (Pedido.id_pedido.ilike(f'%{search}%')) |
                    (Pedido.cliente.ilike(f'%{search}%'))
                )
            
            # Agrupar por id_pedido
            rows = query.order_by(Pedido.id.desc()).limit(300).all()
            ped_map = {}
            for r in rows:
                id_p = r.id_pedido
                if id_p not in ped_map:
                    ped_map[id_p] = {
                        "id_pedido": id_p,
                        "fecha": r.fecha.strftime('%Y-%m-%d') if r.fecha else "",
                        "cliente": r.cliente,
                        "vendedor": r.vendedor,
                        "estado": r.estado,
                        "total": 0,
                        "items_count": 0,
                        "productos": []
                    }
                ped_map[id_p]["items_count"] += 1
                ped_map[id_p]["total"] += float(r.total or 0)
            
            return jsonify({
                "success": True, 
                "pedidos": sorted(list(ped_map.values()), key=lambda x: x['id_pedido'], reverse=True)
            }), 200

    except Exception as e:
        logger.error(f"❌ Error crítico en listar_pedidos: {e}")
        return jsonify({
            "success": False, 
            "error": "Error interno del servidor", 
            "detail": str(e)
        }), 500

@pedidos_bp.route('/api/pedidos/actualizar-progreso', methods=['POST'])
def actualizar_progreso_pedido():
    """Actualiza el porcentaje de progreso de un pedido de Metales."""
    try:
        data = request.json
        id_pedido = data.get('id_pedido')
        nuevo_progreso = data.get('progreso')
        nuevo_estado = data.get('estado')

        if not id_pedido:
            return jsonify({"success": False, "error": "ID de pedido faltante"}), 400

        # Actualizar todas las filas que compartan el mismo id_pedido
        pedidos = MetalsPedido.query.filter_by(id_pedido=id_pedido).all()
        for p in pedidos:
            if nuevo_progreso is not None:
                p.progreso = int(nuevo_progreso)
            if nuevo_estado:
                p.estado = nuevo_estado
        
        db.session.commit()
        return jsonify({"success": True, "message": f"Pedido {id_pedido} actualizado correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error actualizando progreso: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
