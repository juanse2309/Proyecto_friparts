import time
from flask import Blueprint, jsonify, request, session
from backend.models.sql_models import db, Producto, DbProveedor, OrdenCompra, RawVentas, FichaMaestra
from sqlalchemy import cast, Integer

import logging
import uuid
import collections
from datetime import datetime
from backend.utils.auth_middleware import require_role, ROL_ADMINS

# TODO - Siguientes pasos estratégicos:
# 1. [PENDIENTE] Transformar la pestaña "Órdenes de Compra" en módulo de Tránsito, Ubicación y Recepción de Insumos.
# 2. [PENDIENTE] Inyectar sumatoria automática al stock de insumos: insertos de carburo, tornillos, alargadores, etc.


def safe_int(value, default=0):
    try:
        if value is None or str(value).strip() == "":
            return default
        s = str(value).replace('$', '').replace(' ', '').replace(',', '')
        if '.' in s:
            return int(float(s))
        return int(s)
    except (ValueError, TypeError):
        return default

logger = logging.getLogger(__name__)

procura_bp = Blueprint('procura', __name__, url_prefix='/api/procura')

# Cache simple en memoria para los parámetros de inventario
PARAMETROS_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": 300  # 5 minutos de cache
}
PROVEEDORES_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": 86400 # 1 día de cache
}

@procura_bp.route('/listar_parametros', methods=['GET'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
def listar_parametros():
    """Obtiene el catálogo maestro desde SQL (db_productos)."""
    try:
        rows = Producto.query.all()
        productos = []
        for r in rows:
            productos.append({
                "codigo": r.id_codigo or r.codigo_sistema,
                "codigo_normalizado": str(r.id_codigo or r.codigo_sistema).replace(" ", "").replace("-", "").upper(),
                "descripcion": r.descripcion or '',
                "existencia_minima": float(r.stock_minimo or 0),
                "existencia_ideal": float(r.stock_maximo or 0)
            })
        return jsonify({"status": "success", "data": productos}), 200
    except Exception as e:
        logger.error(f"Error listando parámetros SQL: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@procura_bp.route('/listar_proveedores', methods=['GET'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
def listar_proveedores():
    """Lista los proveedores desde SQL (db_proveedores)."""
    try:
        rows = DbProveedor.query.order_by(DbProveedor.proveedores).all()
        proveedores = []
        for r in rows:
            proveedores.append({
                "nombre": r.proveedores,
                "nit": r.nit,
                "direccion": r.direccion,
                "contacto": r.persona_de_contacto,
                "telefono": r.telefono,
                "correo": r.correo,
                "proceso": r.proceso,
                "forma_pago": r.forma_de_pago,
                "evaluacion": r.ultima_evaluacion
            })
        return jsonify({"status": "success", "data": proveedores}), 200
    except Exception as e:
        logger.error(f"Error listando proveedores SQL: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@procura_bp.route('/registrar_oc', methods=['POST'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
def registrar_oc():
    """Registra OC en SQL y actualiza stock."""
    data = request.json
    items = data.get('items', [])
    if not items:
        return jsonify({"success": False, "error": "No hay ítems"}), 400

    try:
        n_oc_ref = items[0].get("n_oc", "")
        # 1. Borrar antiguas si existen
        OrdenCompra.query.filter_by(n_oc=n_oc_ref).delete()

        for item in items:
            nueva_oc = OrdenCompra(
                fecha_solicitud=item.get("fecha_solicitud"),
                n_oc=n_oc_ref,
                proveedor=item.get("proveedor"),
                producto=item.get("producto"),
                cantidad=float(item.get("cantidad", 0)),
                fecha_factura=item.get("fecha_factura"),
                n_factura=item.get("n_factura"),
                cantidad_fact=float(item.get("cantidad_fact", 0)),
                fecha_llegada=item.get("fecha_llegada"),
                cantidad_recibida=float(item.get("cantidad_recibida", 0)),
                diferencia=float(item.get("cantidad", 0)) - float(item.get("cantidad_recibida", 0)),
                observaciones=item.get("observaciones"),
                estado_proceso=item.get("estado_proceso", "Normal")
            )
            db.session.add(nueva_oc)
            
            # 2. Actualizar Stock en SQL
            cant_rec = float(item.get("cantidad_recibida", 0))
            if cant_rec > 0:
                from backend.app import actualizar_stock
                actualizar_stock(item.get("producto"), cant_rec, "STOCK_BODEGA", "ENTRADA", f"OC {n_oc_ref}")

        db.session.commit()
        return jsonify({"success": True, "message": f"Orden {n_oc_ref} guardada en SQL"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error registrar OC SQL: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procura_bp.route('/siguiente_oc', methods=['GET'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
def siguiente_oc():
    """Retorna el siguiente consecutivo de OC desde SQL."""
    try:
        last_oc = db.session.query(OrdenCompra.n_oc).order_by(db.cast(OrdenCompra.n_oc, db.Integer).desc()).first()
        siguiente = int(last_oc[0]) + 1 if last_oc else 200
        return jsonify({"success": True, "siguiente_oc": str(siguiente)}), 200
    except Exception as e:
        logger.error(f"Error siguiente OC SQL: {e}")
        return jsonify({"success": True, "siguiente_oc": "200"}), 200


@procura_bp.route('/buscar_oc/<n_oc>', methods=['GET'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
def buscar_oc(n_oc):
    """Busca OC en SQL para edición."""
    try:
        rows = OrdenCompra.query.filter_by(n_oc=str(n_oc)).all()
        if not rows:
            return jsonify({"success": False, "error": f"OC {n_oc} no encontrada"}), 404
            
        items = []
        for r in rows:
            items.append({
                "fecha_solicitud": r.fecha_solicitud,
                "n_oc": r.n_oc,
                "proveedor": r.proveedor,
                "producto": r.producto,
                "cantidad": float(r.cantidad),
                "fecha_factura": r.fecha_factura,
                "n_factura": r.n_factura,
                "cantidad_fact": float(r.cantidad_fact),
                "fecha_llegada": r.fecha_llegada,
                "cantidad_recibida": float(r.cantidad_recibida),
                "observaciones": r.observaciones,
                "estado_proceso": r.estado_proceso
            })
        return jsonify({"success": True, "data": {"n_oc": n_oc, "items": items}}), 200
    except Exception as e:
        logger.error(f"Error buscar OC SQL: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procura_bp.route('/alertas_abastecimiento', methods=['GET'])
def alertas_abastecimiento():
    """Genera alertas de abastecimiento basadas en SQL (db_productos)."""
    try:
        productos = Producto.query.all()
        alertas = []
        for p in productos:
            stock = float(p.stock_bodega or 0)
            minimo = float(p.stock_minimo or 0)
            if stock < minimo:
                alertas.append({
                    "producto": p.id_codigo or p.codigo_sistema,
                    "descripcion": p.descripcion,
                    "stock_proyectado": stock,
                    "minimo_requerido": minimo,
                    "diferencia": minimo - stock,
                    "semaforo": "ROJO" if stock == 0 else "AMARILLO"
                })
        alertas.sort(key=lambda x: x["diferencia"], reverse=True)
        return jsonify({"status": "success", "total_alertas": len(alertas), "data": alertas}), 200
    except Exception as e:
        logger.error(f"Error alertas SQL: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@procura_bp.route('/rotacion/prioridades', methods=['GET'])
def rotacion_prioridades():
    """Combina stocks físicos y en tránsito (OC) desde SQL."""
    try:
        productos = Producto.query.all()
        # Stock en tránsito: Suma de OC con estado Proceso externo y saldo pendiente
        try:
            transit_rows = db.session.query(
                OrdenCompra.producto, 
                db.func.sum(cast(OrdenCompra.cantidad, Integer) - cast(OrdenCompra.cantidad_recibida, Integer))
            ).filter(OrdenCompra.estado_proceso.ilike('%ZINCADO%') | OrdenCompra.estado_proceso.ilike('%GRANALLADO%')).group_by(OrdenCompra.producto).all()
            transit_map = {r[0]: float(r[1]) for r in transit_rows if r[1] > 0}
        except Exception as e:
            logger.error(f"Error calculando stock en tránsito: {e}")
            db.session.rollback()
            transit_map = {}

        # 1. OBTENER CONSUMO HISTÓRICO PARA PARETO
        ventas_rows = db.session.query(RawVentas.productos, db.func.sum(RawVentas.cantidad)).group_by(RawVentas.productos).all()
        consumo_map = {r[0]: float(r[1] or 0) for r in ventas_rows if r[0]}

        from sqlalchemy import or_
        from backend.models.sql_models import FichaMaestra
        fichas_raw = db.session.query(FichaMaestra.producto, FichaMaestra.subproducto).filter(
            or_(
                FichaMaestra.subproducto.ilike('%INT%'),
                FichaMaestra.subproducto.ilike('%CAR%'),
                FichaMaestra.subproducto.ilike('%CB%'),
                FichaMaestra.subproducto.ilike('%TUBO%'),
                FichaMaestra.subproducto.ilike('%CARCAZA%'),
                FichaMaestra.subproducto.ilike('%EXTERIOR%'),
                FichaMaestra.subproducto.ilike('%INTERNO%'),
                FichaMaestra.subproducto.ilike('%KIT%')
            )
        ).all()
        
        # Guardamos las cadenas largas de texto en una lista en memoria RAM
        textos_padres_armados = [str(f[0]).strip().upper() for f in fichas_raw if f[0]]

        # 3. ALGORITMO MATEMÁTICO DE PARETO (ABC) - PRECALCULADO
        productos_ordenados = sorted(productos, key=lambda p: float(consumo_map.get(str(p.id_codigo or p.codigo_sistema).strip().upper(), 0)), reverse=True)
        
        gran_total = sum(float(consumo_map.get(str(p.id_codigo or p.codigo_sistema).strip().upper(), 0)) for p in productos_ordenados)
        
        if gran_total == 0:
            # Fallback si no hay histórico de ventas: ordenar por stock mínimo requerido
            productos_ordenados = sorted(productos, key=lambda p: float(p.stock_minimo or 0), reverse=True)
            gran_total = sum(float(p.stock_minimo or 0) for p in productos_ordenados)

        suma_acumulada = 0.0
        pareto_map = {}

        for p in productos_ordenados:
            cod_key = str(p.id_codigo or p.codigo_sistema).strip().upper()
            # Obtener el peso de este ítem (unidades vendidas o stock mínimo en su defecto)
            valor_item = float(consumo_map.get(cod_key, 0)) if gran_total != sum(float(x.stock_minimo or 0) for x in productos_ordenados) else float(p.stock_minimo or 0)
            
            suma_acumulada += valor_item
            porcentaje_acumulado = (suma_acumulada / gran_total * 100) if gran_total > 0 else 100

            if porcentaje_acumulado <= 80.0:
                clase = "A"
            elif porcentaje_acumulado <= 95.0:
                clase = "B"
            else:
                clase = "C"
                
            pareto_map[cod_key] = clase

        resultado = []
        for p in productos:
            cod = p.id_codigo or p.codigo_sistema
            # Extraer valores sanitizados de las columnas del modelo Producto (ajusta los nombres exactos si varían en tu modelo)
            stock_general = float(getattr(p, 'stock_bodega', getattr(p, 'stock', 0)) or 0)
            prod_terminado = float(getattr(p, 'p_terminado', getattr(p, 'producto_terminado', 0)) or 0)
            
            # Unificación inteligente: Si es un buje estándar con producto terminado, priorizamos esa columna.
            # Si está en 0 o es un componente/insumo de metalmecánica, tomamos el stock general.
            if prod_terminado > 0:
                stock_fisico = prod_terminado
            else:
                stock_fisico = stock_general if stock_general != 0 else prod_terminado
                
            stock_transito = transit_map.get(cod, 0)
            stock_total = stock_fisico + stock_transito
            minimo = float(p.stock_minimo or 0)
            
            diferencia = minimo - stock_total
            porcentaje = (stock_total / minimo * 100) if minimo > 0 else 100
            
            semaforo = "VERDE"
            if stock_total < minimo:
                semaforo = "ROJO" if porcentaje < 20 else "AMARILLO"

            unidades_vendidas = consumo_map.get(cod, 0)
            # CLASIFICACIÓN INVERSA POR CONTENIDO DE TEXTO
            cod_buscar = str(p.id_codigo or p.codigo_sistema or "").strip().upper()
            desc_buscar = str(p.descripcion or "").strip().upper()
            
            # Regla Inversa: Si el código limpio de este producto está metido DENTRO de alguna de las cadenas largas de padres armados de la BD
            es_armado_por_ficha = any(cod_buscar in texto_largo for texto_largo in textos_padres_armados) if cod_buscar else False
            
            # Respaldos de seguridad por texto de descripción
            es_armado_por_desc = any(k in desc_buscar for k in ['TUBO INTERNO', 'CARCAZA', 'CON CARCAZA', 'CON TUBO', 'KIT'])
            
            tipo_buen = "ARMADO" if (es_armado_por_ficha or es_armado_por_desc) else "LIMPIO"

            resultado.append({
                "codigo": cod,
                "descripcion": p.descripcion,
                "clase": pareto_map.get(str(p.id_codigo or p.codigo_sistema).strip().upper(), "C"),
                "tipo_buen": tipo_buen,
                "unidades_vendidas": unidades_vendidas,
                "stock_actual": stock_fisico,
                "stock_externo": stock_transito,
                "minimo": minimo,
                "diferencia": diferencia,
                "porcentaje": round(porcentaje),
                "semaforo": semaforo
            })
        
        # Ordenamiento por defecto para el cliente (Prioridad de compra)
        resultado.sort(key=lambda x: x["diferencia"], reverse=True)

        total_limpios = sum(1 for x in resultado if x["tipo_buen"] == "LIMPIO")
        total_armados = sum(1 for x in resultado if x["tipo_buen"] == "ARMADO")
        
        print(f"\n=========================================")
        print(f"[CONTEO DE MOTOR ABC] Universo procesado: {len(resultado)} productos.")
        print(f" -> Bujes Clasificados como LIMPIOS: {total_limpios}")
        print(f" -> Bujes Clasificados como ARMADOS: {total_armados}")
        print(f"=========================================\n")

        return jsonify({"status": "success", "data": resultado}), 200
    except Exception as e:
        logger.error(f"Error rotacion SQL: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@procura_bp.route('/recibir_ingreso', methods=['POST'])
def recibir_ingreso():
    try:
        data = request.json
        if not data or not isinstance(data, list):
            return jsonify({"status": "error", "message": "Payload inválido, se esperaba una lista de componentes."}), 400
            
        for item in data:
            id_orden = item.get('id_orden')
            cod = item.get('codigo_producto')
            cant_hoy = float(item.get('cantidad_recibida_hoy', 0))
            
            if cant_hoy <= 0:
                continue

            # 1. Actualizar el producto en el inventario real (Sumar a bodega)
            prod_db = db.session.query(Producto).filter(Producto.id_codigo == cod).first()
            if prod_db:
                prod_db.stock_bodega = float(prod_db.stock_bodega or 0) + cant_hoy
                
            # 2. Descontar o actualizar el saldo en la tabla de órdenes de compra (Bajar el tránsito)
            orden_item = db.session.query(OrdenCompra).filter(
                OrdenCompra.id_orden == id_orden, 
                OrdenCompra.producto == cod
            ).first()
            
            if orden_item:
                # Sumar lo que acaba de llegar al histórico de lo ya recibido
                cant_ya_recibida = float(orden_item.cantidad_recibida or 0)
                orden_item.cantidad_recibida = cant_ya_recibida + cant_hoy
                
                # Si ya se completó el pedido, cambiar el estado del proceso a 'RECIBIDO TOTAL'
                if float(orden_item.cantidad_recibida or 0) >= float(orden_item.cantidad or 0):
                    orden_item.estado_proceso = 'RECIBIDO'
                else:
                    orden_item.estado_proceso = 'PARCIAL'
                    
        db.session.commit()
        return jsonify({"status": "success", "message": "Ingreso registrado correctamente y stock actualizado."}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en recibir_ingreso: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
