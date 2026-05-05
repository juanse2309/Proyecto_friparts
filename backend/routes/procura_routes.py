import time
from flask import Blueprint, jsonify, request, session
from backend.models.sql_models import db, Producto, DbProveedor, OrdenCompra

import logging
import uuid
import collections
from datetime import datetime
from backend.utils.auth_middleware import require_role, ROL_ADMINS

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
        rows = DbProveedor.query.order_by(DbProveedor.nombre).all()
        proveedores = []
        for r in rows:
            proveedores.append({
                "nombre": r.nombre,
                "nit": r.nit,
                "direccion": r.direccion,
                "contacto": r.contacto,
                "telefono": r.telefono,
                "correo": r.correo,
                "proceso": r.proceso,
                "forma_pago": r.forma_pago,
                "evaluacion": r.evaluacion
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
                cantidad_enviada=float(item.get("cantidad_enviada", 0)),
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
                "cantidad_enviada": float(r.cantidad_enviada),
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
        transit_rows = db.session.query(OrdenCompra.producto, db.func.sum(OrdenCompra.cantidad_enviada - OrdenCompra.cantidad_recibida)).filter(OrdenCompra.estado_proceso.ilike('%ZINCADO%') | OrdenCompra.estado_proceso.ilike('%GRANALLADO%')).group_by(OrdenCompra.producto).all()
        transit_map = {r[0]: float(r[1]) for r in transit_rows if r[1] > 0}

        resultado = []
        for p in productos:
            cod = p.id_codigo or p.codigo_sistema
            stock_fisico = float(p.stock_bodega or 0)
            stock_transito = transit_map.get(cod, 0)
            stock_total = stock_fisico + stock_transito
            minimo = float(p.stock_minimo or 0)
            
            diferencia = minimo - stock_total
            porcentaje = (stock_total / minimo * 100) if minimo > 0 else 100
            
            semaforo = "VERDE"
            if stock_total < minimo:
                semaforo = "ROJO" if porcentaje < 20 else "AMARILLO"

            resultado.append({
                "codigo": cod,
                "descripcion": p.descripcion,
                "clase": "A", # Simplificado
                "stock_actual": stock_fisico,
                "stock_externo": stock_transito,
                "minimo": minimo,
                "diferencia": diferencia,
                "porcentaje": round(porcentaje),
                "semaforo": semaforo
            })
        
        resultado.sort(key=lambda x: x["diferencia"], reverse=True)
        return jsonify({"status": "success", "data": resultado}), 200
    except Exception as e:
        logger.error(f"Error rotacion SQL: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
