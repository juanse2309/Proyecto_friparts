import time
from flask import Blueprint, jsonify, request, session
from backend.core.database import sheets_client as gc
from backend.config.settings import Hojas
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
    """
    Obtiene el catálogo maestro de carcasas, internos, tornillería y otros.
    """
    try:
        ahora = time.time()
        # Verificar cache
        if PARAMETROS_CACHE["data"] and (ahora - PARAMETROS_CACHE["timestamp"] < PARAMETROS_CACHE["ttl"]):
            return jsonify({"status": "success", "data": PARAMETROS_CACHE["data"]}), 200

        ws = gc.get_worksheet(Hojas.PRODUCTOS)
        if not ws:
            return jsonify({"status": "error", "message": f"Hoja {Hojas.PRODUCTOS} no encontrada"}), 500

        registros = gc.get_all_records_seguro(ws)
        if not registros:
            return jsonify({"status": "error", "message": "La hoja está vacía"}), 404

        productos = []
        for r in registros:
            codigo = str(r.get("ID CODIGO", "") or r.get("CODIGO SISTEMA", "")).strip()
            if not codigo: continue

            # Normalizar para búsqueda interna (quitando espacios y guiones)
            codigo_normalizado = codigo.replace(" ", "").replace("-", "").upper()

            productos.append({
                "codigo": codigo,
                "codigo_normalizado": codigo_normalizado,
                "descripcion": str(r.get("DESCRIPCION", "")).strip(),
                "existencia_minima": safe_int(r.get("MINIMO", 0)),
                "existencia_ideal": 0
            })

        # Almacenar en caché
        PARAMETROS_CACHE["data"] = productos
        PARAMETROS_CACHE["timestamp"] = ahora

        return jsonify({"status": "success", "data": productos}), 200

    except Exception as e:
        logger.error(f"Error listando parámetros de procura: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@procura_bp.route('/listar_proveedores', methods=['GET'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
def listar_proveedores():
    """
    Lista los proveedores con detalles completos desde la hoja DB_PROVEEDORES.
    """
    try:
        ahora = time.time()
        # Cache de corta duración para permitir actualizaciones
        if PROVEEDORES_CACHE["data"] and (ahora - PROVEEDORES_CACHE["timestamp"] < PROVEEDORES_CACHE["ttl"]):
            return jsonify({"status": "success", "data": PROVEEDORES_CACHE["data"]}), 200

        ws = gc.get_worksheet(Hojas.DB_PROVEEDORES)
        if not ws:
            return jsonify({"status": "error", "message": f"Hoja {Hojas.DB_PROVEEDORES} no encontrada"}), 500

        registros = gc.get_all_records_seguro(ws)
        proveedores = []
        
        for r in registros:
            # Extraer y limpiar campos según los encabezados solicitados
            nombre = str(r.get("PROVEEDORES", "") or r.get("NOMBRE", "") or "").strip()
            if not nombre: continue

            proveedores.append({
                "nombre": nombre,
                "nit": str(r.get("NIT", "")).strip(),
                "direccion": str(r.get("DIRECCIÓN", "") or r.get("DIRECCION", "")).strip(),
                "contacto": str(r.get("PERSONA DE CONTACTO", "") or r.get("CONTACTO", "")).strip(),
                "telefono": str(r.get("TELEFONO", "") or r.get("TELÉFONO", "")).strip(),
                "correo": str(r.get("CORREO", "") or r.get("EMAIL", "")).strip(),
                "proceso": str(r.get("PROCESO", "")).strip(),
                "forma_pago": str(r.get("FORMA DE PAGO", "")).strip(),
                "evaluacion": str(r.get("ULTIMA EVALUACIÓN", "") or r.get("EVALUACION", "")).strip()
            })

        # Ordenar por nombre
        proveedores.sort(key=lambda x: x["nombre"])

        PROVEEDORES_CACHE["data"] = proveedores
        PROVEEDORES_CACHE["timestamp"] = ahora

        return jsonify({"status": "success", "data": proveedores}), 200
    except Exception as e:
        logger.error(f"Error listando proveedores detallados: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@procura_bp.route('/registrar_oc', methods=['POST'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
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
        cantidad_solicitada = safe_int(item.get("cantidad", 0))
        
        # Recepción (pueden venir vacíos si es solicitud inicial)
        fecha_factura = item.get("fecha_factura", "")
        n_factura = item.get("n_factura", "")
        cantidad_fact = safe_int(item.get("cantidad_fact", 0))
        fecha_llegada = item.get("fecha_llegada", "")
        cantidad_recibida = safe_int(item.get("cantidad_recibida", 0))
        diferencia = cantidad_solicitada - cantidad_recibida

        # Fila completa según base (14 columnas)
        observaciones = str(item.get('observaciones', '')).strip()
        cantidad_enviada = safe_int(item.get("cantidad_enviada", 0))
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
            cantidad_enviada,
            estado_proceso
        ]
        rows_to_insert.append(row)

    try:
        ws_oc = gc.get_worksheet(Hojas.ORDENES_DE_COMPRA)
        if not ws_oc:
            return jsonify({"success": False, "error": f"Hoja {Hojas.ORDENES_DE_COMPRA} no encontrada"}), 500

        # 1. Calcular DELTA de stock antes de actualizar la OC
        n_oc_ref = items[0].get("n_oc", "")
        old_records = gc.get_all_records_seguro(ws_oc)
        old_qty_map = collections.defaultdict(int)
        for r in old_records:
            if str(r.get("N° OC", "")).strip() == str(n_oc_ref).strip():
                prod_key = str(r.get("PRODUCTO", "")).strip().upper()
                old_qty_map[prod_key] += safe_int(r.get("CANTIDAD RECIBIDA", 0))

        new_qty_map = collections.defaultdict(int)
        for it in items:
            prod_key = str(it.get("producto", "")).strip().upper()
            new_qty_map[prod_key] += safe_int(it.get("cantidad_recibida", 0))

        # 2. Eliminar filas antiguas
        registros_values = ws_oc.get_all_values()
        filas_a_borrar = [i + 1 for i, r in enumerate(registros_values) if len(r) > 1 and str(r[1]).strip() == str(n_oc_ref).strip()]
        for row_index in reversed(filas_a_borrar):
            ws_oc.delete_rows(row_index)

        # 3. Insertar nuevas filas
        ws_oc.append_rows(rows_to_insert, value_input_option='USER_ENTERED')

        # 4. Actualizar STOCK_BODEGA en PRODUCTOS basado en el DELTA
        ws_param = gc.get_worksheet(Hojas.PRODUCTOS)
        if ws_param:
            param_records = gc.get_all_records_seguro(ws_param)
            headers = ws_param.row_values(1)
            col_stock = headers.index('STOCK_BODEGA') + 1 if 'STOCK_BODEGA' in headers else -1
            col_contador = headers.index('CONTADOR_OC') + 1 if 'CONTADOR_OC' in headers else -1

            for i, r in enumerate(param_records):
                cod = str(r.get("ID CODIGO", "") or r.get("CODIGO SISTEMA", "")).strip().upper()
                row_idx = i + 2
                
                # Actualizar Stock
                if cod in new_qty_map or cod in old_qty_map:
                    delta = new_qty_map.get(cod, 0) - old_qty_map.get(cod, 0)
                    if delta != 0 and col_stock > 0:
                        current_s = safe_int(r.get("STOCK_BODEGA", 0))
                        ws_param.update_cell(row_idx, col_stock, current_s + delta)
                
                # Incrementar contador si es producto nuevo en esta OC
                if cod in new_qty_map and cod not in old_qty_map and col_contador > 0:
                    val_c = safe_int(r.get("CONTADOR_OC", 0))
                    ws_param.update_cell(row_idx, col_contador, val_c + 1)

        return jsonify({"success": True, "message": f"Orden {n_oc_ref} guardada y stock actualizado."}), 200

    except Exception as e:
        logger.error(f"Error guardando órdenes de compra y actualizando stock: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procura_bp.route('/siguiente_oc', methods=['GET'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
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
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE'])
def buscar_oc(n_oc):
    """
    Busca todas las líneas correspondientes a una N° OC y las retorna para edición.
    """
    try:
        ws = gc.get_worksheet(Hojas.ORDENES_DE_COMPRA)
        if not ws:
            return jsonify({"success": False, "error": f"Hoja {Hojas.ORDENES_DE_COMPRA} no encontrada"}), 500

        records = gc.get_all_records_seguro(ws)
        items_encontrados = []

        for row in records:
            if str(row.get("N° OC", "")).strip() == str(n_oc).strip():
                    items_encontrados.append({
                        "fecha_solicitud": str(row.get("FECHA DE SOLICITUD", "") or row.get("FECHA SOLICITUD", "") or row.get("FECHA", "")),
                        "n_oc": str(row.get("N° OC", "") or row.get("N OC", "") or row.get("OC", "")),
                        "proveedor": str(row.get("PROVEEDOR", "") or ""),
                        "producto": str(row.get("PRODUCTO", "") or row.get("CÓDIGO", "")).strip(),
                        "cantidad": safe_int(row.get("CANTIDAD", 0) or row.get("CANTIDAD SOLICITADA", 0)),
                        "fecha_factura": str(row.get("FECHA FACTURA", "") or ""),
                        "n_factura": str(row.get("N° FACTURA", "") or row.get("N FACTURA", "") or ""),
                        "cantidad_fact": safe_int(row.get("CANTIDAD FACT", 0) or row.get("CANTIDAD FACTURADA", 0)),
                        "fecha_llegada": str(row.get("FECHA LLEGADA", "") or ""),
                        "cantidad_recibida": safe_int(row.get("CANTIDAD RECIBIDA", 0)),
                        "observaciones": str(row.get("OBSERVACIONES", "") or ""),
                        "cantidad_enviada": safe_int(row.get("CANTIDAD TOTAL ENVIADA", 0)),
                        "estado_proceso": str(row.get("ESTADO PROCESO", "") or row.get("ESTADO", "") or "Normal")
                    })

        if not items_encontrados:
            return jsonify({"success": False, "error": f"No se encontró la Orden de Compra {n_oc}"}), 404

        # Adornar con descripción desde el maestro
        ws_param = gc.get_worksheet(Hojas.PRODUCTOS)
        cat_records = gc.get_all_records_seguro(ws_param) if ws_param else []
        
        def normalizar_para_busqueda(codigo):
            return str(codigo).strip().upper().replace(" ", "").replace("-", "")

        catalogo = {normalizar_para_busqueda(r.get("ID CODIGO", "") or r.get("CODIGO SISTEMA", "")): str(r.get("DESCRIPCION", "")) for r in cat_records if r.get("ID CODIGO") or r.get("CODIGO SISTEMA")}

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
        ws_param = gc.get_worksheet(Hojas.PRODUCTOS)
        cat_records = gc.get_all_records_seguro(ws_param) if ws_param else []
        
        catalogo = {}
        for r in cat_records:
            codigo = str(r.get("ID CODIGO", "") or r.get("CODIGO SISTEMA", "")).strip().upper()
            if codigo:
                catalogo[codigo] = {
                    "descripcion": str(r.get("DESCRIPCION", "")),
                    "min": safe_int(r.get("MINIMO", 0)),
                    "stock_actual": safe_int(r.get("STOCK_BODEGA", 0))
                }

        # 2. Generar Alertas basadas en STOCK_ACTUAL
        alertas = []
        for codigo, data in catalogo.items():
            stock_actual = data["stock_actual"]
            if stock_actual < data["min"]:
                alertas.append({
                    "producto": codigo,
                    "descripcion": data["descripcion"],
                    "stock_proyectado": stock_actual,
                    "minimo_requerido": data["min"],
                    "diferencia": data["min"] - stock_actual,
                    "semaforo": "ROJO" if stock_actual == 0 else "AMARILLO"
                })

        # 2. Sumar total CANTIDAD RECIBIDA por producto (Opcional: Podemos dejar la suma histórica si se quiere mostrar como dato informativo, pero el semáforo manda el real)

        alertas.sort(key=lambda x: x["diferencia"], reverse=True)

        return jsonify({
            "status": "success",
            "total_alertas": len(alertas),
            "data": alertas
        }), 200

    except Exception as e:
        logger.error(f"Error generando alertas de abastecimiento: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@procura_bp.route('/rotacion/prioridades', methods=['GET'])
def rotacion_prioridades():
    """
    Combina PARAMETROS_INVENTARIO y ORDENES_DE_COMPRA para priorización inteligente.
    Asigna Clase A, B o C dinámicamente según el contador de compras y los mínimos.
    Ordena por CLASE_ROTACION (A > B > C) y luego por déficit crítico.
    """
    try:
        # 1. Traer Parámetros con sus históricos
        ws_param = gc.get_worksheet(Hojas.PRODUCTOS)
        cat_records = gc.get_all_records_seguro(ws_param) if ws_param else []
        
        catalogo = {}
        for r in cat_records:
            codigo = str(r.get("ID CODIGO", "") or r.get("CODIGO SISTEMA", "")).strip().upper()
            if codigo:
                minimo = safe_int(r.get("MINIMO", 0))
                contador_oc = safe_int(r.get("CONTADOR_OC", 0))
                
                # REGLAS DEL BOT DE PROCURA PARA CLASIFICACION ABC ESTATICA-DINAMICA
                clase_calculada = str(r.get("CLASE_ROTACION", "C")).strip().upper() or "C"
                
                catalogo[codigo] = {
                    "descripcion": str(r.get("DESCRIPCION", "")),
                    "min": minimo,
                    "clase": clase_calculada,
                    "contador_oc": contador_oc,
                    "stock_actual": safe_int(r.get("STOCK_BODEGA", 0))
                }

        # 2. Consultar Stock Externo en Tránsito (Zincado/Granallado)
        ws_oc = gc.get_worksheet(Hojas.ORDENES_DE_COMPRA)
        oc_records = gc.get_all_records_seguro(ws_oc) if ws_oc else []
        
        stock_externo_map = collections.defaultdict(int)
        desglose_externo_map = collections.defaultdict(lambda: {"Zincado": 0, "Granallado": 0})
        
        for r in oc_records:
            procesos = str(r.get("ESTADO PROCESO", "")).upper()
            codigo_oc = str(r.get("PRODUCTO", "")).strip().upper()
            
            # Solo si tiene algún proceso externo marcado
            if "ZINCADO" in procesos or "GRANALLADO" in procesos:
                # Stock EXTERNO = Enviado - Recibido (lo que aún no vuelve)
                enviado = safe_int(r.get("CANTIDAD TOTAL ENVIADA", 0))
                recibido = safe_int(r.get("CANTIDAD RECIBIDA", 0))
                saldo_en_transito = max(0, enviado - recibido)
                
                if saldo_en_transito > 0:
                    stock_externo_map[codigo_oc] += saldo_en_transito
                    if "ZINCADO" in procesos: desglose_externo_map[codigo_oc]["Zincado"] += saldo_en_transito
                    if "GRANALLADO" in procesos: desglose_externo_map[codigo_oc]["Granallado"] += saldo_en_transito

        # 3. Consolidar Datos
        resultado = []
        for codigo, data in catalogo.items():
            stock_fisico = data["stock_actual"]
            stock_externo = stock_externo_map.get(codigo, 0)
            stock_total_disponible = stock_fisico + stock_externo
            
            diferencia_critica = data["min"] - stock_total_disponible
            
            # Cálculo de semáforo UX considerando Stock Total (Físico + Externo)
            semaforo = "VERDE"
            porcentaje_del_minimo = (stock_total_disponible / data["min"] * 100) if data["min"] > 0 else 100
            
            if stock_total_disponible < data["min"]:
                if porcentaje_del_minimo < 20:
                    semaforo = "ROJO"
                elif porcentaje_del_minimo <= 50:
                    semaforo = "AMARILLO"
                else:
                    semaforo = "VERDE"

            resultado.append({
                "codigo": codigo,
                "descripcion": data["descripcion"],
                "clase": data["clase"],
                "stock_actual": stock_fisico,
                "stock_externo": stock_externo,
                "desglose_externo": desglose_externo_map.get(codigo, {"Zincado": 0, "Granallado": 0}),
                "minimo": data["min"],
                "diferencia": diferencia_critica,
                "porcentaje": round(porcentaje_del_minimo),
                "semaforo": semaforo,
                "contador_oc": data["contador_oc"]
            })

        # 4. Ordenamiento inteligente
        # Primero por Clase (A=0, B=1, C=2 para sorting ascendente)
        # Luego por Déficit (diferencia más alta primero)
        clase_map = {"A": 0, "B": 1, "C": 2}
        resultado.sort(key=lambda x: (clase_map.get(x["clase"], 3), -x["diferencia"]))

        return jsonify({
            "status": "success",
            "data": resultado
        }), 200

    except Exception as e:
        logger.error(f"Error en rotacion_prioridades: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
