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

        if nombre_vista in ("Vista_Tabla_Inventarios", "Vista_Existencias"):
            from backend.core.sql_database import db

            # Normalizar llaves de todos los registros
            datos_normalizados = [normalizar_llaves(item) for item in datos]

            logger.info(f"[DEBUG] Recibidos {len(datos_normalizados)} registros para insertar.")
            if datos_normalizados:
                logger.info(f"[DEBUG] Llaves del primer registro: {list(datos_normalizados[0].keys())}")
                logger.info(f"[DEBUG NUBE] Muestra primeros 5 registros recibidos:")
                for i, r in enumerate(datos_normalizados[:5]):
                    cod = r.get('codigo_producto') or r.get('codigo') or '(sin_cod)'
                    stk = r.get('stock_wo') or r.get('existencia') or r.get('stock') or 0
                    logger.info(f"  [{i}] Ref: {cod} | Stock: {stk}")

            try:
                # PRE-AUDITORÍA DE STOCK: Verificar si TODOS los registros vienen con stock 0
                all_zeros = True
                for r in datos_normalizados:
                    stock_raw = (r.get('stock_wo') or r.get('stock') or r.get('cantidad') or 
                                 r.get('saldo') or r.get('saldos') or r.get('existencia') or 0)
                    try:
                        if float(stock_raw) > 0:
                            all_zeros = False
                            break
                    except (ValueError, TypeError):
                        pass
                
                if all_zeros and len(datos_normalizados) > 0:
                    logger.critical("❌ [CRÍTICO] El archivo/reporte de WO reporta stock 0.00 para TODOS los items. "
                                    "Se aborta la sincronización para evitar borrar el inventario real.")
                    return jsonify({
                        "success": False, 
                        "error": "El reporte de World Office viene vacío o todos los saldos son 0. Verifique las columnas del reporte exportado."
                    }), 400

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

                        # Obtención de stock ampliada a posibles columnas de WO
                        stock_raw = (r.get('stock_wo') or r.get('stock') or r.get('cantidad') or 
                                     r.get('saldo') or r.get('saldos') or r.get('existencia') or 0)
                        
                        if j < 5 and i == 0:  # Imprimir log preventivo para los primeros 5 registros de muestra
                            logger.info(f"[CARGA WO] Procesando Ref: {codigo_producto} | Valor Stock Detectado: {stock_raw}")

                        try:
                            stock_wo = float(stock_raw)
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
    Cruza inventario_wo con db_productos usando SQL masivo para 
    asegurar actualización real en la base de datos de p_terminado y precio.
    """
    try:
        from backend.core.sql_database import db
        from sqlalchemy import text

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

        # Ejecutamos un UPDATE masivo nativo en PostgreSQL
        # Usamos REGEXP_REPLACE o LIKE para hacer el match de la parte numérica.
        # Aquí cruzamos usando la parte numérica normalizada
        
        sql_update = text("""
            WITH normalizados AS (
                SELECT 
                    codigo_producto, 
                    stock_wo, 
                    precio_wo,
                    -- Extraemos el último bloque de números de la referencia de WO
                    SUBSTRING(codigo_producto FROM '([0-9]+)$') as ref_num_wo
                FROM inventario_wo
                WHERE SUBSTRING(codigo_producto FROM '([0-9]+)$') IS NOT NULL
            )
            UPDATE db_productos AS p
            SET 
                p_terminado = COALESCE(n.stock_wo, 0),
                precio = COALESCE(n.precio_wo, 0)
            FROM normalizados n
            WHERE 
                -- Hacemos match con el mismo bloque numérico extraído de codigo_sistema o id_codigo
                SUBSTRING(p.codigo_sistema FROM '([0-9]+)$') = n.ref_num_wo
                OR SUBSTRING(p.id_codigo FROM '([0-9]+)$') = n.ref_num_wo;
        """)
        
        result = db.session.execute(sql_update)
        actualizados = result.rowcount
        db.session.commit()

        logger.info(f"📊 [Unificar WO] Actualización masiva completada. Filas afectadas: {actualizados}")

        return jsonify({
            "success": True,
            "message": f"Sincronización masiva completada exitosamente. {actualizados} productos actualizados.",
            "actualizados": actualizados
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en unificar WO (SQL Masivo): {e}")
        return jsonify({"success": False, "error": str(e)}), 500
