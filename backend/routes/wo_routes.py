# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
import os
import logging
import re
import unicodedata
from sqlalchemy import text

wo_bp = Blueprint('wo', __name__)
logger = logging.getLogger(__name__)


# ====================================================================
# UTILIDADES DE NORMALIZACIÓN
# ====================================================================

def limpiar_codigo_wo(c):
    if not c:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(c).upper().strip())


def normalizar_referencia(codigo):
    """
    Extrae la parte numérica final de cualquier código.
    Reglas:
      - ANILLO9735   -> 9735
      - FR-5002B     -> 5002
      - FR-9714      -> 9714
      - MT5007R      -> 5007
      - 513075       -> 513075  (número puro, se retorna completo)
      - CAR-9890     -> 9890
    """
    if not codigo:
        return ""
    t = str(codigo).strip()
    numeros = re.findall(r'\d+', t)
    return numeros[-1] if numeros else ""


def normalizar_llaves(d):
    """Normaliza las llaves de un dict: minúsculas, sin acentos, espacios -> _"""
    if not isinstance(d, dict):
        return d

    def limpiar_texto(s):
        s = s.lower().strip()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = s.replace(' ', '_')
        return s

    return {limpiar_texto(k): v for k, v in d.items()}


# ====================================================================
# ENDPOINT: RECIBIR DATOS DESDE EL AGENTE LOCAL WO
# ====================================================================

@wo_bp.route('/api/wo/recibir_datos', methods=['POST'])
def recibir_datos():
    """
    Recibe datos sincronizados desde el agente local de World Office.
    Persiste usando TRUNCATE + INSERT masivo en lotes de SQL puro.
    """
    # Validar API Key
    api_key_header = request.headers.get('X-API-Key')
    api_key_env = os.environ.get('WO_SYNC_API_KEY')

    if not api_key_env:
        logger.error("❌ Variable de entorno WO_SYNC_API_KEY no configurada en el servidor.")
        return jsonify({"success": False, "error": "Configuración de seguridad incompleta"}), 500

    if api_key_header != api_key_env:
        logger.warning(f"⚠️ Sincronización WO no autorizada. Header X-API-Key: {api_key_header}")
        return jsonify({"success": False, "error": "No autorizado. API Key inválida o ausente."}), 401

    try:
        payload = request.json or {}

        if isinstance(payload, dict):
            nombre_vista = payload.get("nombre_vista", "Desconocida")
            datos = payload.get("datos", [])
        else:
            nombre_vista = "Desconocida (Lista directa)"
            datos = payload

        if not isinstance(datos, list):
            datos = [datos] if datos else []

        logger.info(f"Datos de WO recibidos ({nombre_vista}): {len(datos)} registros")

        if nombre_vista == "Vista_Tabla_Inventarios":
            from backend.core.sql_database import db

            # Normalizar llaves de todos los registros
            datos_normalizados = [normalizar_llaves(item) for item in datos]

            logger.info(f"[DEBUG] Recibidos {len(datos_normalizados)} registros para insertar.")
            if datos_normalizados:
                logger.info(f"[DEBUG] Llaves del primer registro: {list(datos_normalizados[0].keys())}")
                logger.info(f"[DEBUG] Primer registro crudo: {datos_normalizados[0]}")

            try:
                # PASO 1: TRUNCATE — limpiar tabla sin bloqueos residuales
                db.session.execute(text("TRUNCATE TABLE inventario_wo"))
                db.session.flush()
                logger.info("[DEBUG] TRUNCATE de inventario_wo ejecutado.")

                # PASO 2: INSERT masivo por lotes de 500 (SQL puro, sin ORM)
                BATCH_SIZE = 500
                rows_insertados = 0

                for i in range(0, len(datos_normalizados), BATCH_SIZE):
                    batch = datos_normalizados[i:i + BATCH_SIZE]
                    values_parts = []
                    params = {}

                    for j, r in enumerate(batch):
                        codigo_producto = str(
                            r.get('codigo_producto') or r.get('codigo') or
                            r.get('codigo_alterno') or ""
                        ).strip()
                        if not codigo_producto:
                            continue

                        descripcion    = str(r.get('descripcion') or r.get('nombre') or "").strip()[:500]
                        codigo_alterno = str(r.get('codigo_alterno') or "").strip()[:100]
                        referencia     = str(r.get('referencia') or r.get('ref') or "").strip()[:100]

                        try:
                            stock_wo = float(r.get('stock_wo') or r.get('stock') or r.get('cantidad') or 0)
                        except (ValueError, TypeError):
                            stock_wo = 0.0

                        try:
                            precio_wo = float(r.get('precio_wo') or r.get('precio') or r.get('precio_venta') or 0)
                        except (ValueError, TypeError):
                            precio_wo = 0.0

                        k = f"r{i}_{j}"
                        params[f"cod_{k}"]    = codigo_producto
                        params[f"desc_{k}"]   = descripcion
                        params[f"stock_{k}"]  = stock_wo
                        params[f"precio_{k}"] = precio_wo
                        params[f"alt_{k}"]    = codigo_alterno
                        params[f"ref_{k}"]    = referencia
                        values_parts.append(
                            f"(:cod_{k}, :desc_{k}, :stock_{k}, :precio_{k}, :alt_{k}, :ref_{k})"
                        )

                    if values_parts:
                        sql = text(
                            "INSERT INTO inventario_wo "
                            "(codigo_producto, descripcion, stock_wo, precio_wo, codigo_alterno, referencia) "
                            f"VALUES {', '.join(values_parts)}"
                        )
                        db.session.execute(sql, params)
                        rows_insertados += len(values_parts)

                db.session.commit()

                # Verificar persistencia real en DB
                count_res = db.session.execute(text("SELECT COUNT(*) FROM inventario_wo")).scalar()
                logger.info(f"[DEBUG] Registros guardados en inventario_wo tras INSERT: {count_res}")
                logger.info(f"✅ INSERT masivo completado: {rows_insertados} filas insertadas en inventario_wo.")

            except Exception as e_sql:
                db.session.rollback()
                logger.error(f"❌ Error en INSERT masivo de inventario_wo: {e_sql}")
                raise

        return jsonify({
            "success": True,
            "message": f"Datos de la vista '{nombre_vista}' recibidos con éxito",
            "recibidos": len(datos),
            "nombre_vista": nombre_vista
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en endpoint recibir_datos de WO: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ====================================================================
# ENDPOINT: UNIFICAR INVENTARIO WO -> DB_PRODUCTOS
# ====================================================================

@wo_bp.route('/api/wo/unificar', methods=['POST'])
def unificar_inventario_wo():
    """
    Cruza inventario_wo con db_productos por la parte numérica final
    del codigo_producto y actualiza p_terminado y precio.
    """
    try:
        from backend.core.sql_database import db
        from backend.models.sql_models import InventarioWO, Producto

        # Log de cuántos registros hay en inventario_wo ANTES del cruce
        count_wo = db.session.execute(text("SELECT COUNT(*) FROM inventario_wo")).scalar()
        logger.info(f"[DEBUG] Registros en inventario_wo antes del cruce: {count_wo}")

        if count_wo == 0:
            logger.warning("[DEBUG] inventario_wo está vacía. Ejecuta primero la sincronización del agente.")
            return jsonify({
                "success": False,
                "message": "inventario_wo está vacía. Sincroniza primero con el agente WO.",
                "actualizados": 0
            }), 400

        # Indexar productos de FriTech por su referencia numérica
        productos = db.session.query(Producto).all()
        productos_mapa = {}
        for p in productos:
            ref_local = normalizar_referencia(p.codigo_sistema) or normalizar_referencia(p.id_codigo)
            if ref_local:
                if ref_local not in productos_mapa:
                    productos_mapa[ref_local] = []
                productos_mapa[ref_local].append(p)

        logger.info(f"[DEBUG] Productos indexados en productos_mapa: {len(productos_mapa)} claves únicas.")

        # Traer todos los registros de inventario_wo
        items_wo = db.session.query(InventarioWO).all()

        actualizados  = 0
        no_encontrados = 0
        colisiones    = 0

        for item in items_wo:
            cod_wo_raw = item.codigo_producto
            if not cod_wo_raw:
                continue

            ref_wo = normalizar_referencia(cod_wo_raw)
            if not ref_wo:
                continue

            hits = productos_mapa.get(ref_wo)
            if hits:
                if len(hits) == 1:
                    hits[0].p_terminado = float(item.stock_wo or 0)
                    hits[0].precio      = float(item.precio_wo or 0)
                    actualizados += 1
                else:
                    for p_col in hits:
                        p_col.p_terminado = float(item.stock_wo or 0)
                        p_col.precio      = float(item.precio_wo or 0)
                    colisiones    += 1
                    actualizados  += len(hits)
            else:
                logger.info(f"[DEBUG] Referencia WO no encontrada en catálogo: {cod_wo_raw} (norm={ref_wo})")
                no_encontrados += 1

        db.session.commit()

        logger.info(
            f"📊 [Unificar WO] Actualizados: {actualizados}, "
            f"Colisiones: {colisiones}, No encontrados: {no_encontrados}"
        )

        return jsonify({
            "success": True,
            "message": f"Sincronización completada. {actualizados} productos actualizados, {no_encontrados} no emparejados.",
            "actualizados": actualizados,
            "colisiones": colisiones,
            "no_emparejados": no_encontrados
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en unificar WO: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
