import time
from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client as gc
from backend.config.settings import Hojas
import logging
import uuid
import collections
from datetime import datetime

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
def listar_parametros():
    """
    Obtiene el catálogo maestro de carcasas, internos, tornillería y otros.
    """
    try:
        ahora = time.time()
        # Verificar cache
        if PARAMETROS_CACHE["data"] and (ahora - PARAMETROS_CACHE["timestamp"] < PARAMETROS_CACHE["ttl"]):
            return jsonify({"status": "success", "data": PARAMETROS_CACHE["data"]}), 200

        ws = gc.get_worksheet(Hojas.PARAMETROS_INVENTARIO)
        if not ws:
            return jsonify({"status": "error", "message": f"Hoja {Hojas.PARAMETROS_INVENTARIO} no encontrada"}), 500

        registros = ws.get_all_records()
        if not registros:
            return jsonify({"status": "error", "message": "La hoja está vacía"}), 404

        productos = []
        for r in registros:
            codigo = str(r.get("CÓDIGO", "") or r.get("CODIGO", "") or r.get("REFERENCIA", "") or r.get("REF", "")).strip()
            if not codigo: continue

            # Normalizar para búsqueda interna (quitando espacios y guiones)
            codigo_normalizado = codigo.replace(" ", "").replace("-", "").upper()

            productos.append({
                "codigo": codigo,
                "codigo_normalizado": codigo_normalizado,
                "descripcion": str(r.get("DESCRIPCIÓN", "") or r.get("DESCRIPCION", "")).strip(),
                "existencia_minima": int(r.get("EXISTENCIAS MÍNIMAS", 0) or r.get("EXISTENCIAS MINIMAS", 0)  or 0),
                "existencia_ideal": int(r.get("EXISTENCIAS IDEALES", 0) or 0)
            })

        # Almacenar en caché
        PARAMETROS_CACHE["data"] = productos
        PARAMETROS_CACHE["timestamp"] = ahora

        return jsonify({"status": "success", "data": productos}), 200

    except Exception as e:
        logger.error(f"Error listando parámetros de procura: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@procura_bp.route('/listar_proveedores', methods=['GET'])
def listar_proveedores():
    """
    Lista los proveedores desde la hoja DB_PROVEEDORES.
    """
    try:
        ahora = time.time()
        if PROVEEDORES_CACHE["data"] and (ahora - PROVEEDORES_CACHE["timestamp"] < PROVEEDORES_CACHE["ttl"]):
            return jsonify({"status": "success", "data": PROVEEDORES_CACHE["data"]}), 200

        ws = gc.get_worksheet(Hojas.DB_PROVEEDORES)
        if not ws:
            return jsonify({"status": "error", "message": f"Hoja {Hojas.DB_PROVEEDORES} no encontrada"}), 500

        registros = ws.get_all_records()
        proveedores = []
        for r in registros:
            # Asumimos que la hoja tiene una columna NOMBRE, PROVEEDOR o PROVEEDORES
            nombre = str(r.get("PROVEEDORES", "") or r.get("NOMBRE", "") or r.get("PROVEEDOR", "")).strip()
            if nombre:
                proveedores.append(nombre)

        # Hacerlos únicos y ordenados
        proveedores = sorted(list(set(proveedores)))

        PROVEEDORES_CACHE["data"] = proveedores
        PROVEEDORES_CACHE["timestamp"] = ahora

        return jsonify({"status": "success", "data": proveedores}), 200
    except Exception as e:
        logger.error(f"Error listando proveedores: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@procura_bp.route('/registrar_oc', methods=['POST'])
def registrar_oc():
    """
    Registra nuevas Órdenes de Compra en lote o actualiza recepción (registra nuevo movimiento iterativo).
    Formato esperado: A-E inicial o A-K recepción total.
    """
    data = request.json
    if not data or 'items' not in data:
        return jsonify({"success": False, "error": "Datos inválidos, faltan items"}), 400

    items = data['items']
    if not items:
        return jsonify({"success": False, "error": "No hay ítems para procesar"}), 400

    rows_to_insert = []
    
    for item in items:
        fecha_solicitud = item.get("fecha_solicitud", "")
        n_oc = item.get("n_oc", "")
        proveedor = item.get("proveedor", "")
        producto = item.get("producto", "") # Código real
        cantidad_solicitada = int(item.get("cantidad", 0) or 0)
        
        # Recepción (pueden venir vacíos si es solicitud inicial)
        fecha_factura = item.get("fecha_factura", "")
        n_factura = item.get("n_factura", "")
        cantidad_fact = int(item.get("cantidad_fact", 0) or 0)
        fecha_llegada = item.get("fecha_llegada", "")
        cantidad_recibida = int(item.get("cantidad_recibida", 0) or 0)
        diferencia = cantidad_solicitada - cantidad_recibida

        # Fila completa según base (11 columnas)
        observaciones = str(item.get('observaciones', '')).strip()
        estado_proceso = str(item.get('estado_proceso', 'Normal')).strip()

        row = [
            fecha_solicitud,
            n_oc,
            proveedor,
            producto,
            cantidad_solicitada,
            fecha_factura,
            n_factura,
            cantidad_fact,
            fecha_llegada,
            cantidad_recibida,
            diferencia,
            observaciones,
            estado_proceso
        ]
        rows_to_insert.append(row)

    try:
        ws = gc.get_worksheet(Hojas.ORDENES_DE_COMPRA)
        if not ws:
            return jsonify({"success": False, "error": f"Hoja {Hojas.ORDENES_DE_COMPRA} no encontrada"}), 500

        # Primero, si es una OC existente, eliminamos los items anteriores para poder insertar los actualizados
        # Como es complicado eliminar múltiples filas sueltas sin romper, vamos a buscar si "n_oc" ya existe
        # Buscamos todas las filas donde la columna B (n_oc) coincida para borrarlas de abajo hacia arriba.
        n_oc_ref = items[0].get("n_oc", "")
        
        registros = ws.get_all_values()
        
        # Encuentra los indices (1-indexed) de las filas que corresponden a esta OC
        filas_a_borrar = []
        for i, r in enumerate(registros):
            if len(r) > 1 and str(r[1]).strip() == str(n_oc_ref).strip():
                filas_a_borrar.append(i + 1)
        
        # Eliminar las filas si existen (de abajo hacia arriba para no dañar índices)
        for row_index in reversed(filas_a_borrar):
            ws.delete_rows(row_index)

        # Función de batch insert manual 
        from flask import current_app
        # append_rows_seguro(ws, rows_to_insert) -> Reemplazo por WS normal. Para seguro se puede usar direct ws.append_rows()
        ws.append_rows(rows_to_insert, value_input_option='USER_ENTERED')
        return jsonify({"success": True, "message": f"Orden {n_oc_ref} guardada excitoxamente."}), 200

    except Exception as e:
        logger.error(f"Error guardando órdenes de compra: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procura_bp.route('/siguiente_oc', methods=['GET'])
def siguiente_oc():
    """
    Lee la hoja ORDENES_DE_COMPRA para encontrar el número de OC más alto (Ej: OC-105)
    y retorna el consecutivo siguiente (Ej: OC-106).
    """
    try:
        ws = gc.get_worksheet(Hojas.ORDENES_DE_COMPRA)
        if not ws:
            return jsonify({"success": False, "error": f"Hoja {Hojas.ORDENES_DE_COMPRA} no encontrada"}), 500

        col_b_values = ws.col_values(2) # Columna B (N° OC)
        # Ignorar la primera fila (encabezado)
        if len(col_b_values) > 1:
            valores_oc = col_b_values[1:]
        else:
            return jsonify({"success": True, "siguiente_oc": "200"}), 200 # Valor inicial por defecto si está vacío
        
        # Buscar el número más alto
        max_num = 0
        import re
        for val in valores_oc:
            val_limpio = str(val).strip()
            # Extraer números, ignorando prefijos como 'OC-'
            numeros = re.findall(r'\d+', val_limpio)
            if numeros:
                num = int(numeros[-1]) # Tomar el último grupo de números en caso de algo como "OC-2023-10"
                if num > max_num:
                    max_num = num
        
        siguiente = max_num + 1 if max_num > 0 else 200
        return jsonify({"success": True, "siguiente_oc": str(siguiente)}), 200

    except Exception as e:
        logger.error(f"Error obteniendo siguiente OC: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procura_bp.route('/buscar_oc/<n_oc>', methods=['GET'])
def buscar_oc(n_oc):
    """
    Busca todas las líneas correspondientes a una N° OC y las retorna para edición.
    """
    try:
        ws = gc.get_worksheet(Hojas.ORDENES_DE_COMPRA)
        if not ws:
            return jsonify({"success": False, "error": f"Hoja {Hojas.ORDENES_DE_COMPRA} no encontrada"}), 500

        records = ws.get_all_records()
        items_encontrados = []

        for row in records:
            if str(row.get("N° OC", "")).strip() == str(n_oc).strip():
                    items_encontrados.append({
                        "fecha_solicitud": str(row.get("FECHA DE SOLICITUD", "") or row.get("FECHA SOLICITUD", "") or row.get("FECHA", "")),
                        "n_oc": str(row.get("N° OC", "") or row.get("N OC", "") or row.get("OC", "")),
                        "proveedor": str(row.get("PROVEEDOR", "") or ""),
                        "producto": str(row.get("PRODUCTO", "") or row.get("CÓDIGO", "")).strip(),
                        "cantidad": int(row.get("CANTIDAD", 0) or row.get("CANTIDAD SOLICITADA", 0) or 0),
                        "fecha_factura": str(row.get("FECHA FACTURA", "") or ""),
                        "n_factura": str(row.get("N° FACTURA", "") or row.get("N FACTURA", "") or ""),
                        "cantidad_fact": int(row.get("CANTIDAD FACT", 0) or row.get("CANTIDAD FACTURADA", 0) or 0),
                        "fecha_llegada": str(row.get("FECHA LLEGADA", "") or ""),
                        "cantidad_recibida": int(row.get("CANTIDAD RECIBIDA", 0) or 0),
                        "observaciones": str(row.get("OBSERVACIONES", "") or ""),
                        "estado_proceso": str(row.get("ESTADO PROCESO", "") or row.get("ESTADO", "") or "Normal")
                    })

        if not items_encontrados:
            return jsonify({"success": False, "error": f"No se encontró la Orden de Compra {n_oc}"}), 404

        # Adornar con descripción desde el maestro
        ws_param = gc.get_worksheet(Hojas.PARAMETROS_INVENTARIO)
        cat_records = ws_param.get_all_records() if ws_param else []
        
        def normalizar_para_busqueda(codigo):
            return str(codigo).strip().upper().replace(" ", "").replace("-", "")

        catalogo = {normalizar_para_busqueda(r.get("CÓDIGO", "") or r.get("CODIGO", "") or r.get("REFERENCIA", "") or r.get("REF", "")): str(r.get("DESCRIPCIÓN", "") or r.get("DESCRIPCION", "")) for r in cat_records if r.get("CÓDIGO") or r.get("CODIGO") or r.get("REFERENCIA") or r.get("REF")}

        for item in items_encontrados:
            codigo_limpio = normalizar_para_busqueda(item["producto"])
            item["descripcion"] = catalogo.get(codigo_limpio, "Sin descripción")

        return jsonify({"success": True, "data": {"n_oc": n_oc, "items": items_encontrados}}), 200

    except Exception as e:
        logger.error(f"Error buscando orden de compra {n_oc}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procura_bp.route('/alertas_abastecimiento', methods=['GET'])
def alertas_abastecimiento():
    """
    Compara CANTIDAD RECIBIDA histórica de hojas OC contra PARAMETROS_INVENTARIO min.
    """
    try:
        # 1. Traer Catálogo Maestro
        ws_param = gc.get_worksheet(Hojas.PARAMETROS_INVENTARIO)
        cat_records = ws_param.get_all_records() if ws_param else []
        
        catalogo = {}
        for r in cat_records:
            codigo = str(r.get("CÓDIGO", "") or r.get("CODIGO", "") or r.get("REFERENCIA", "") or r.get("REF", "")).strip().upper()
            if codigo:
                catalogo[codigo] = {
                    "descripcion": str(r.get("DESCRIPCIÓN", "") or r.get("DESCRIPCION", "")),
                    "min": int(r.get("EXISTENCIAS MÍNIMAS", 0) or r.get("EXISTENCIAS MINIMAS", 0) or 0)
                }

        # 2. Sumar total CANTIDAD RECIBIDA por producto
        ws_oc = gc.get_worksheet(Hojas.ORDENES_DE_COMPRA)
        oc_records = ws_oc.get_all_records() if ws_oc else []

        stock_recibido = collections.defaultdict(int)
        for oc in oc_records:
            prod_codigo = str(oc.get("PRODUCTO", "")).strip().upper()
            cant_rec = int(oc.get("CANTIDAD RECIBIDA", 0) or 0)
            if prod_codigo and cant_rec > 0:
                stock_recibido[prod_codigo] += cant_rec

        # 3. Generar Alertas
        alertas = []
        for codigo, data in catalogo.items():
            stock_actual = stock_recibido.get(codigo, 0)
            if stock_actual < data["min"]:
                alertas.append({
                    "producto": codigo,
                    "descripcion": data["descripcion"],
                    "stock_proyectado": stock_actual,
                    "minimo_requerido": data["min"],
                    "diferencia": data["min"] - stock_actual,
                    "semaforo": "ROJO" if stock_actual == 0 else "AMARILLO"
                })

        alertas.sort(key=lambda x: x["diferencia"], reverse=True)

        return jsonify({
            "status": "success",
            "total_alertas": len(alertas),
            "data": alertas
        }), 200

    except Exception as e:
        logger.error(f"Error generando alertas de abastecimiento: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
