# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
import os
import logging
import re
import unicodedata
from sqlalchemy import text

wo_bp = Blueprint('wo', __name__)
logger = logging.getLogger(__name__)


def _refrescar_mv_dashboard_ventas():
    """
    Refresca en cascada las vistas materializadas derivadas de db_ventas que
    alimentan el panel de Jefatura tras una sincronización exitosa de World Office:
      - mv_dashboard_ventas_analitica (Backorder/Top/Peores Productos)
      - mv_rendimiento_mensual (comparativo mensual Ventas vs Pedidos)
    Ver backend/sql/create_mv_dashboard_ventas_analitica.sql y
    backend/sql/create_mv_rendimiento_mensual.sql.

    REFRESH ... CONCURRENTLY no puede correr dentro de una transacción, así que se
    abre una conexión aparte en autocommit. Cada vista se refresca de forma
    independiente: si una falla, la otra igual se intenta. Un fallo aquí se loggea
    pero no debe tumbar la respuesta de sync: los datos de db_ventas ya se
    confirmaron con éxito, y el dashboard simplemente seguirá sirviendo el
    snapshot anterior de la vista que falló hasta el próximo refresh exitoso.
    """
    from backend.core.sql_database import db

    vistas = ["mv_dashboard_ventas_analitica", "mv_rendimiento_mensual"]
    try:
        conn = db.engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            for vista in vistas:
                try:
                    conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {vista}"))
                    logger.info(f"✅ {vista} refrescada tras sincronización de WO.")
                except Exception as e_vista:
                    logger.error(f"⚠️ Fallo al refrescar {vista} tras sync de WO: {e_vista}")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"⚠️ Fallo al abrir conexión para refrescar vistas materializadas tras sync de WO: {e}")


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

                # PASO 1 y 2: UPSERT Atómico (DELETE previo + INSERT en transacción)
                logger.info("[AUDITORIA] Estrategia de UPSERT Atómica iniciada. No se usará TRUNCATE.")

                BATCH_SIZE = 500
                rows_insertados = 0

                for i in range(0, len(datos_normalizados), BATCH_SIZE):
                    batch = datos_normalizados[i:i + BATCH_SIZE]
                    values_parts = []
                    params = {}
                    
                    ids_lote = []

                    for j, r in enumerate(batch):
                        codigo_producto = str(
                            r.get('codigo_producto') or r.get('codigo') or
                            r.get('codigo_alterno') or ""
                        ).strip()
                        if not codigo_producto:
                            continue
                            
                        ids_lote.append(codigo_producto)

                        descripcion    = str(r.get('descripcion') or r.get('nombre') or "").strip()[:500]
                        codigo_alterno = str(r.get('codigo_alterno') or "").strip()[:100]
                        referencia     = str(r.get('referencia') or r.get('ref') or "").strip()[:100]

                        # Mapeo Explícito y Constante de Columna
                        columna_stock_leida = 'stock_wo' if 'stock_wo' in r else 'existencia' if 'existencia' in r else 'stock'
                        stock_raw = r.get(columna_stock_leida)
                        
                        if j == 0 and i == 0:
                            logger.info(f"[AUDITORIA EXPLICITA] Leyendo valor de stock desde la clave: '{columna_stock_leida}'")

                        if j < 5 and i == 0:  
                            logger.info(f"[CARGA WO] Procesando Ref: {codigo_producto} | Valor Detectado: {stock_raw}")

                        # Validación de Datos Segura contra NULL o vacíos
                        if stock_raw is None or str(stock_raw).strip() == "":
                            stock_wo = None # Se preservará como NULL para no sobreescribir con 0
                        else:
                            try:
                                stock_wo = float(stock_raw)
                            except (ValueError, TypeError):
                                stock_wo = None

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

                    if values_parts and ids_lote:
                        # 1. DELETE atómico de los IDs que vamos a actualizar (Evita duplicados sin vaciar la tabla)
                        ids_placeholders = [f":del_{idx}" for idx in range(len(ids_lote))]
                        del_params = {f"del_{idx}": id_val for idx, id_val in enumerate(ids_lote)}
                        sql_del = text(f"DELETE FROM inventario_wo WHERE codigo_producto IN ({', '.join(ids_placeholders)})")
                        db.session.execute(sql_del, del_params)
                        

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

        # NOTA: Este UPDATE sincroniza el stock validando nulos.
        sql_update = text("""
            UPDATE db_productos AS p
            SET 
                p_terminado = COALESCE(n.stock_wo, p.p_terminado)
            FROM inventario_wo n
            WHERE 
                (p.codigo_sistema = n.codigo_producto OR p.id_codigo = n.codigo_producto)
                AND n.stock_wo IS NOT NULL AND n.stock_wo >= 0;
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


# ====================================================================
# ENDPOINT: RECIBIR DATOS COMERCIALES (VENTAS Y PEDIDOS) DESDE WO
# ====================================================================

@wo_bp.route('/api/wo/recibir_comercial', methods=['POST'])
def recibir_comercial():
    """
    Recibe la sincronización de ventas, pedidos y devoluciones (año actual) desde World Office.
    Realiza un DELETE previo del año actual en db_ventas para evitar duplicados,
    y luego realiza un bulk insert de los nuevos registros mapeados.
    Ambas operaciones corren en una sola transacción para evitar dejar la base de datos vacía en caso de falla.
    """
    # Validar Token de Seguridad
    api_key_header = request.headers.get('X-API-Key') or request.headers.get('X-Sync-Token')
    api_key_env = os.environ.get('SYNC_TOKEN') or os.environ.get('WO_SYNC_API_KEY')

    if not api_key_env or api_key_header != api_key_env:
        logger.warning(f"⚠️ Sincronización comercial WO no autorizada. Token recibido: {api_key_header}")
        return jsonify({"success": False, "error": "No autorizado. Token de sincronización inválido o ausente."}), 401

    try:
        payload = request.json or {}
        
        # Detectar si es un lote (chunk) o un payload tradicional
        is_chunk = payload.get("is_chunk", False)
        if is_chunk:
            index = payload.get("index", 0)
            total_chunks = payload.get("total_chunks", 1)
            datos = payload.get("data", [])
            logger.info(f"Recibiendo lote {index + 1}/{total_chunks} de datos comerciales de WO: {len(datos)} registros")
        else:
            index = 0
            total_chunks = 1
            if isinstance(payload, dict):
                datos = payload.get("datos", [])
            else:
                datos = payload
            if not isinstance(datos, list):
                datos = [datos] if datos else []
            logger.info(f"Datos comerciales de WO recibidos (sin chunking): {len(datos)} registros")

        from backend.models.sql_models import RawVentas
        from backend.core.sql_database import db
        from sqlalchemy import text
        from datetime import datetime

        # Helper para parseo seguro de fechas
        def parse_date(date_val):
            if not date_val:
                return None
            if isinstance(date_val, datetime):
                return date_val.date()
            try:
                # Intentar formato ISO 'YYYY-MM-DD'
                return datetime.fromisoformat(str(date_val).replace('Z', '')).date()
            except ValueError:
                try:
                    return datetime.strptime(str(date_val)[:10], '%Y-%m-%d').date()
                except ValueError:
                    return None

        # Paso 1: Si es el primer lote, inicializamos la tabla Staging en PostgreSQL
        if index == 0:
            logger.info("Lote inicial (index 0). Preparando tabla Staging 'db_ventas_staging'...")
            # Asumimos que db_ventas_staging ya existe estáticamente. Vaciamos la tabla para el nuevo volcado.
            db.session.execute(text("TRUNCATE db_ventas_staging"))
            db.session.commit()

        # Paso 2: Mapear y preparar datos del chunk actual
        mappings_chunk = []
        conteo_prefijos = {}
        cant_pd = 0
        cant_fv = 0
        cant_nc = 0

        for item in datos:
            clasif = item.get('clasificacion')
            
            # Extraer prefijo real del documento (ej: "COT-1234" -> "COT")
            doc_str = str(item.get('documento') or '')
            prefijo_real = doc_str.split('-')[0] if '-' in doc_str else 'DESC'
            conteo_prefijos[prefijo_real] = conteo_prefijos.get(prefijo_real, 0) + 1

            if clasif == 'pedido':
                cant_pd += 1
            elif clasif == 'venta':
                cant_fv += 1
            elif clasif == 'devolucion':
                cant_nc += 1
            else:
                # Fallback por si acaso el mapeo falló o viene directo del agente
                prefijo = item.get('prefijo_doc') or ''
                if prefijo == 'FV':
                    clasif = 'venta'
                    cant_fv += 1
                elif prefijo == 'PD':
                    clasif = 'pedido'
                    cant_pd += 1
                elif prefijo == 'NC':
                    clasif = 'devolucion'
                    cant_nc += 1
                else:
                    clasif = 'desconocido'

            # Conversión de tipos para evitar errores de persistencia
            try:
                cantidad = float(item.get('cantidad') or 0)
            except (ValueError, TypeError):
                cantidad = 0.0

            try:
                total_ingresos = float(item.get('total_ingresos') or 0)
            except (ValueError, TypeError):
                total_ingresos = 0.0

            try:
                precio_promedio = float(item.get('precio_promedio') or 0)
            except (ValueError, TypeError):
                precio_promedio = 0.0

            fecha_parsed = parse_date(item.get('fecha'))
            
            mappings_chunk.append({
                'fecha': fecha_parsed,
                'documento': str(item.get('documento') or '').strip()[:80],
                'nombres': str(item.get('nombres') or '').strip()[:200],
                'productos': str(item.get('productos') or '').strip()[:100],
                'cantidad': cantidad,
                'total_ingresos': total_ingresos,
                'precio_promedio': precio_promedio,
                'clasificacion': clasif,
                'vendedor': str(item.get('vendedor') or '').strip()[:150],
                'zona': str(item.get('zona') or '').strip()[:100]
            })

        # Persistir el chunk actual en la tabla Staging
        if mappings_chunk:
            sql_insert = text("""
                INSERT INTO db_ventas_staging
                (fecha, documento, nombres, productos, cantidad, total_ingresos, precio_promedio, clasificacion, vendedor, zona)
                VALUES (:fecha, :documento, :nombres, :productos, :cantidad, :total_ingresos, :precio_promedio, :clasificacion, :vendedor, :zona)
            """)
            db.session.execute(sql_insert, mappings_chunk)
            db.session.commit()

        # Paso 3: Si llegamos al último chunk, procedemos con la transacción atómica
        if index == total_chunks - 1:
            logger.info("Último lote recibido. Iniciando Volcado Atómico desde Staging a db_ventas...")
            try:
                # Transacción ultrarrápida: Swap de tablas en el motor SQL
                db.session.execute(text("TRUNCATE db_ventas"))
                db.session.execute(text("""
                    INSERT INTO db_ventas (fecha, documento, nombres, productos, cantidad, total_ingresos, precio_promedio, clasificacion, vendedor, zona)
                    SELECT fecha, documento, nombres, productos, cantidad, total_ingresos, precio_promedio, clasificacion, vendedor, zona
                    FROM db_ventas_staging
                """))
                db.session.commit()
                logger.info("✅ Sincronización comercial completada con volcado atómico desde Staging Table.")
                _refrescar_mv_dashboard_ventas()
            except Exception as db_err:
                db.session.rollback()
                logger.error(f"❌ Error en volcado de staging a producción: {db_err}")
                raise db_err

        detalles_response = {
            "total_insertados_chunk": len(mappings_chunk),
            "lote_actual": index + 1,
            "total_lotes": total_chunks,
            "estado": "En progreso (Staging)" if index < total_chunks - 1 else "Completado y Volcado a Producción"
        }

        return jsonify({
            "success": True,
            "message": f"Sincronización comercial del lote {index + 1}/{total_chunks} exitosa",
            "detalles": detalles_response
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Transacción fallida en recepción de chunk. Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


# ====================================================================
# ENDPOINT: DISPARAR SINCRONIZACIÓN AUTOMÁTICA DESDE SERVIDOR LOCAL / PLANTA
# ====================================================================

@wo_bp.route('/api/wo/sincronizar_automatica', methods=['GET', 'POST'])
def sincronizar_automatica():
    """
    Ruta segura para disparar la sincronización comercial desde World Office de forma autónoma.
    Soporta POST (header X-Sync-Token) y GET (parámetro query ?token=...).
    Utiliza el driver pyodbc local para extraer y guardar directamente en db_ventas.
    """
    # 1. Validar Token de Seguridad (desde Header o parámetro query de URL)
    token_recibido = request.args.get('token') or request.headers.get('X-Sync-Token')
    token_esperado = os.getenv('SYNC_TOKEN')

    if token_esperado is None:
        logger.error("❌ Variable de entorno SYNC_TOKEN no configurada en el servidor (es None).")
        return jsonify({"status": "error", "message": "Error de configuración de seguridad: SYNC_TOKEN es None"}), 500

    if token_recibido != token_esperado:
        logger.warning(f"⚠️ Intento de sincronización automática no autorizado. Comparación fallida: '{token_recibido}' != '{token_esperado}'")
        return jsonify({"status": "error", "message": "No autorizado. Token de sincronización inválido."}), 403

    try:
        import pyodbc
    except ImportError:
        logger.error("❌ La librería pyodbc no está instalada en este entorno del servidor.")
        return jsonify({"status": "error", "message": "pyodbc no está disponible en este servidor"}), 500

    # 2. Configurar conexión SQL Server (Mismos parámetros que agente_wo_comercial.py)
    DB_SERVER   = os.getenv("WO_SERVER",     r"SERVERWO\WORLDOFFICE17")
    DB_DATABASE = os.getenv("WO_DB",         "FRIPARTS2021")
    DB_UID      = os.getenv("WO_USER",       "wo_cliente")
    DB_PWD      = os.getenv("WO_PASSWORD")
    if not DB_PWD:
        return jsonify({"status": "error", "message": "WO_PASSWORD no está configurada en el servidor"}), 500

    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        f"UID={DB_UID};"
        f"PWD={DB_PWD};"
        "Timeout=30;"
    )

    from backend.models.sql_models import RawVentas, OperacionLog
    from backend.core.sql_database import db
    from datetime import datetime

    db_log_entry = OperacionLog(
        fecha=datetime.now(),
        modulo="SincronizacionComercial",
        operario="Sistema (Auto)",
        accion="Inicio Sincronización Automática",
        detalles="Iniciando conexión local a World Office..."
    )
    db.session.add(db_log_entry)
    db.session.commit()

    conn = None
    try:
        conn = pyodbc.connect(conn_str, timeout=15)
        cursor = conn.cursor()

        # 3. Cargar catálogo maestro en memoria
        cursor.execute("SELECT Autonumerico, Codigo_Producto FROM [FRIPARTS2021].[dbo].[Vista_Tabla_Inventarios]")
        mapping = {}
        for row in cursor.fetchall():
            mapping[str(row[0])] = row[1]

        # 4. Extraer datos comerciales
        sql = """
        SELECT
            E.Fecha AS fecha,
            (E.prefijo + '-' + CAST(E.Numero_de_Documento AS VARCHAR)) AS documento,
            E.Nombre_tercero_externo AS nombres,
            E.Nombres_tercero_interno AS vendedor,
            E.Ciudad_Encabezado AS zona,
            D.Producto AS productos,
            CAST(D.Cantidad AS FLOAT) AS cantidad,
            CAST((D.Cantidad * D.Valor_Unitario * (1 - (D.Descuento/100.0))) AS FLOAT) AS total_ingresos,
            CAST(D.Valor_Unitario AS FLOAT) AS precio_promedio,
            E.Tipo_de_Documento AS tipo_doc
        FROM [FRIPARTS2021].[dbo].[Vista_Tabla_Encabezados] E
        INNER JOIN [FRIPARTS2021].[dbo].[Vista_Tabla_Movimientos_Inventario] D
            ON E.Autonumerico = D.Pertenece_A
        WHERE YEAR(E.Fecha) >= YEAR(GETDATE()) - 1
          AND E.Tipo_de_Documento IN ('FV', 'PED', 'COT', 'NC', 'NCV', 'NCCL', 'DMC')
          AND E.Anulado = 0;
        """
        cursor.execute(sql)
        columnas = [column[0] for column in cursor.description]

        datos_mapeados = []
        cant_pd = 0
        cant_fv = 0

        for row in cursor.fetchall():
            item = dict(zip(columnas, row))

            tipo_doc = item.get('tipo_doc', '').strip()
            if tipo_doc == 'PED':
                clasif = 'pedido'
                cant_pd += 1
            elif tipo_doc in ('FV', 'COT', 'NC', 'NCV', 'NCCL', 'DMC'):
                clasif = 'venta'
                if tipo_doc == 'FV':
                    cant_fv += 1
                # Ajuste matematico para devoluciones/notas credito/devolucion de mercancia
                if tipo_doc in ('NC', 'NCV', 'NCCL', 'DMC'):
                    item['total_ingresos'] = float(item.get('total_ingresos', 0) or 0) * -1
            else:
                clasif = 'desconocido'

            prod_id = str(item.get('productos', '')).strip()
            mapped_prod = mapping.get(prod_id, prod_id)
            mapped_prod_str = str(mapped_prod or '').strip()

            datos_mapeados.append({
                'fecha': item.get('fecha'),
                'documento': str(item.get('documento') or '').strip()[:80],
                'nombres': str(item.get('nombres') or '').strip()[:200],
                'productos': mapped_prod_str[:100],
                'cantidad': float(item.get('cantidad') or 0.0),
                'total_ingresos': float(item.get('total_ingresos') or 0.0),
                'precio_promedio': float(item.get('precio_promedio') or 0.0),
                'clasificacion': clasif,
                'vendedor': str(item.get('vendedor') or '').strip()[:150],
                'zona': str(item.get('zona') or '').strip()[:100]
            })

        conn.close()

        # 5. Borrado total de db_ventas e inserción masiva en transacción atómica
        db.session.query(RawVentas).delete(synchronize_session=False)

        if datos_mapeados:
            db.session.bulk_insert_mappings(RawVentas, datos_mapeados)
        
        # Registrar éxito en bitácora
        log_exito = OperacionLog(
            fecha=datetime.now(),
            modulo="SincronizacionComercial",
            operario="Sistema (Auto)",
            accion="Fin Sincronización Automática",
            detalles=f"Exito. Procesados: {len(datos_mapeados)} (Ventas: {cant_fv}, Pedidos: {cant_pd})"
        )
        db.session.add(log_exito)
        db.session.commit()
        _refrescar_mv_dashboard_ventas()

        return jsonify({
            "status": "success",
            "message": "Sincronización completada",
            "registros": len(datos_mapeados)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except:
                pass
        db.session.rollback()

        # Registrar error en bitácora
        log_error = OperacionLog(
            fecha=datetime.now(),
            modulo="SincronizacionComercial",
            operario="Sistema (Auto)",
            accion="Error Sincronización Automática",
            detalles=f"Falla crítica: {str(e)}"
        )
        db.session.add(log_error)
        db.session.commit()

        logger.error(f"❌ Error en sincronizar_automatica: {e}")
        return jsonify({"status": "error", "message": f"Falla en sincronización: {str(e)}"}), 500


# ====================================================================
# ENDPOINT: AUDITORÍA DE DATOS COMERCIALES EN DB_VENTAS
# ====================================================================

@wo_bp.route('/api/wo/auditoria_comercial', methods=['GET'])
def auditoria_comercial():
    """
    Ruta pura de auditoría para depurar los datos de la tabla db_ventas.
    Agrupa los resultados y retorna un JSON con la cantidad de ventas y pedidos por año.
    No realiza ninguna sincronización ni proceso pesado.
    """
    try:
        from backend.core.sql_database import db
        from backend.models.sql_models import RawVentas
        from sqlalchemy import func

        resultados = db.session.query(
            func.extract('year', RawVentas.fecha).label('anio'),
            RawVentas.clasificacion,
            func.count(RawVentas.id).label('total')
        ).group_by(
            func.extract('year', RawVentas.fecha),
            RawVentas.clasificacion
        ).all()

        data = {}
        for r in resultados:
            if r.anio is None:
                continue
            
            anio = str(int(r.anio))
            clasif = str(r.clasificacion).lower().strip()
            
            if anio not in data:
                data[anio] = {"ventas": 0, "pedidos": 0}
                
            if clasif == 'venta':
                data[anio]["ventas"] += r.total
            elif clasif == 'pedido':
                data[anio]["pedidos"] += r.total
                
        return jsonify(data), 200

    except Exception as e:
        logger.error(f"❌ Error en auditoria_comercial: {e}")
        return jsonify({"error": str(e)}), 500


# ====================================================================
# ENDPOINT: AUDITORÍA MENSUAL DE DATOS COMERCIALES
# ====================================================================

@wo_bp.route('/api/wo/auditoria_mensual', methods=['GET'])
def auditoria_mensual():
    """
    Ruta pura de auditoría para diagnosticar la carga mensual de db_ventas.
    Retorna la cantidad de ventas y pedidos agrupados por año y mes.
    """
    try:
        from backend.core.sql_database import db
        from backend.models.sql_models import RawVentas
        from sqlalchemy import func

        resultados = db.session.query(
            func.extract('year', RawVentas.fecha).label('anio'),
            func.extract('month', RawVentas.fecha).label('mes'),
            RawVentas.clasificacion,
            func.count(RawVentas.id).label('total')
        ).group_by(
            func.extract('year', RawVentas.fecha),
            func.extract('month', RawVentas.fecha),
            RawVentas.clasificacion
        ).all()

        data = {}
        for r in resultados:
            if r.anio is None or r.mes is None:
                continue
            
            anio = str(int(r.anio))
            mes = f"{int(r.mes):02d}"
            clasif = str(r.clasificacion).lower().strip()
            
            if anio not in data:
                data[anio] = {}
                
            if mes not in data[anio]:
                data[anio][mes] = {"ventas": 0, "pedidos": 0}
                
            if clasif == 'venta':
                data[anio][mes]["ventas"] += r.total
            elif clasif == 'pedido':
                data[anio][mes]["pedidos"] += r.total
                
        for anio in data:
            data[anio] = dict(sorted(data[anio].items()))
            
        return jsonify(data), 200

    except Exception as e:
        logger.error(f"❌ Error en auditoria_mensual: {e}")
        return jsonify({"error": str(e)}), 500


# ====================================================================
# ENDPOINTS: FLAG DE SINCRONIZACIÓN COMERCIAL DESDE DASHBOARD
# ====================================================================

@wo_bp.route('/api/wo/solicitar_sync', methods=['POST'])
def solicitar_sync():
    """
    Endpoint para activar o desactivar el flag de sincronización comercial.
    """
    try:
        import json
        
        payload = request.get_json() if request.is_json else {}
        # Por defecto, si no se especifica, se asume que se solicita la sync
        estado = payload.get("sync_pendiente", True)
        
        # Guardar el flag en un archivo temporal o en el directorio base
        data_dir = os.path.join(os.getcwd(), 'data')
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, 'sync_comercial_flag.json')
        
        with open(file_path, 'w') as f:
            json.dump({"sync_pendiente": estado}, f)
            
        logger.info(f"Flag de sincronización actualizado: sync_pendiente={estado}")
        return jsonify({"success": True, "message": f"Sincronización {'solicitada' if estado else 'limpiada'} exitosamente"}), 200
        
    except Exception as e:
        logger.error(f"❌ Error al solicitar sincronización: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@wo_bp.route('/api/wo/verificar_sync', methods=['GET'])
def verificar_sync():
    """
    Ruta que el Agente Local consultará para saber si debe extraer los datos.
    """
    try:
        import json
        file_path = os.path.join(os.getcwd(), 'data', 'sync_comercial_flag.json')
        
        if not os.path.exists(file_path):
            return jsonify({"sync_pendiente": False}), 200
            
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"❌ Error al verificar flag de sincronización: {e}")
        return jsonify({"sync_pendiente": False, "error": str(e)}), 500

# ====================================================================
# ENDPOINT: SINCRONIZAR CARTERA DESDE WO
# ====================================================================

@wo_bp.route('/api/wo/sincronizar_cartera', methods=['POST'])
def sincronizar_cartera():
    """Recibe y procesa el estado de cartera desde el Agente WO con chunking."""
    api_key_header = request.headers.get('X-API-Key') or request.headers.get('X-Sync-Token')
    api_key_env = os.environ.get('SYNC_TOKEN') or os.environ.get('WO_SYNC_API_KEY')
    
    if not api_key_env or api_key_header != api_key_env:
        return jsonify({"success": False, "error": "No autorizado."}), 401
        
    try:
        from decimal import Decimal, InvalidOperation
        
        payload = request.json or {}
        datos = payload.get("datos", payload) if isinstance(payload, dict) else payload
        
        if not isinstance(datos, list):
            datos = [datos] if datos else []
            
        from backend.repositories.ventas_repository import VentasRepository

        # Validar y limpiar datos
        datos_limpios = []
        for item in datos:
            if not item.get('documento'):
                continue
            
            try:
                saldo_documento = Decimal(str(item.get('saldo_documento', '0')))
            except InvalidOperation:
                saldo_documento = Decimal('0')
                
            datos_limpios.append({
                'documento': str(item.get('documento')).strip(),
                'identificacion': str(item.get('identificacion')).strip(),
                'nombre': str(item.get('nombre') or 'Desconocido').strip(),
                'vendedor': str(item.get('vendedor') or '').strip(),
                'moneda': str(item.get('moneda') or '').strip(),
                'empresa': str(item.get('empresa') or '').strip(),
                'fecha_emision': item.get('fecha_emision') or None,
                'fecha_vencimiento': item.get('fecha_vencimiento') or None,
                'saldo_documento': saldo_documento
            })
            
        # Procesamiento por lotes (chunking) de 500 en 500
        BATCH_SIZE = 500
        procesados_totales = 0
        
        for i in range(0, len(datos_limpios), BATCH_SIZE):
            chunk = datos_limpios[i:i+BATCH_SIZE]
            procesados = VentasRepository.upsert_cartera_wo(chunk)
            procesados_totales += procesados
            logger.info(f"Procesado chunk {i//BATCH_SIZE + 1} de Cartera: {procesados} registros")
        
        return jsonify({
            "success": True,
            "message": "Cartera sincronizada correctamente",
            "procesados": procesados_totales
        }), 200
        
    except Exception as e:
        logger.error(f"Error en sincronizar_cartera: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ====================================================================
# ENDPOINT: SINCRONIZAR CLIENTES (TERCEROS) DESDE WO
# ====================================================================

# Umbral del circuit breaker: si el catalogo recibido cae por debajo de este
# porcentaje del catalogo actual en db_clientes, se aborta para no perder
# clientes existentes ante una extraccion parcial/rota en el agente local.
UMBRAL_CAIDA_ANOMALA_CLIENTES = 0.5


@wo_bp.route('/api/wo/sincronizar_clientes', methods=['POST'])
def sincronizar_clientes():
    """Recibe y procesa el catalogo de clientes/terceros desde el Agente WO.
    Persiste vía ClienteRepository.upsert_clientes_wo (UPSERT por identificacion/NIT).
    """
    api_key_header = request.headers.get('X-API-Key') or request.headers.get('X-Sync-Token')
    api_key_env = os.environ.get('SYNC_TOKEN') or os.environ.get('WO_SYNC_API_KEY')

    if not api_key_env or api_key_header != api_key_env:
        logger.warning(f"⚠️ Sincronización de clientes WO no autorizada. Token recibido: {api_key_header}")
        return jsonify({"success": False, "error": "No autorizado. Token de sincronización inválido o ausente."}), 401

    try:
        payload = request.json or {}
        datos = payload.get("datos", payload) if isinstance(payload, dict) else payload

        if not isinstance(datos, list):
            datos = [datos] if datos else []

        logger.info(f"Datos de clientes WO recibidos: {len(datos)} registros")

        # --- Circuit Breaker: catálogo vacío o caída anómala frente al actual ---
        from backend.core.sql_database import db
        from backend.repositories.cliente_repository import ClienteRepository

        if len(datos) == 0:
            logger.critical("❌ [CRÍTICO] El catálogo de clientes recibido de WO viene vacío. Se aborta la sincronización.")
            return jsonify({
                "success": False,
                "error": "El catálogo de clientes recibido está vacío."
            }), 422

        count_actual = db.session.execute(text("SELECT COUNT(*) FROM db_clientes")).scalar() or 0
        if count_actual > 0 and len(datos) < count_actual * UMBRAL_CAIDA_ANOMALA_CLIENTES:
            logger.critical(
                f"❌ [CRÍTICO] Caída anómala en la sincronización de clientes: "
                f"recibidos={len(datos)} vs actuales={count_actual} (umbral {UMBRAL_CAIDA_ANOMALA_CLIENTES:.0%}). "
                "Se aborta para no perder clientes existentes."
            )
            return jsonify({
                "success": False,
                "error": f"Caída anómala: se recibieron {len(datos)} clientes frente a {count_actual} existentes. "
                         "Verifique la extracción en el agente local."
            }), 422

        # --- Normalización y limpieza ---
        # Cada fila es una direccion/sucursal de un tercero (IdTerceroDireccion
        # de WO), no un cliente unico: un mismo NIT puede repetirse en varias
        # filas con id_direccion_wo distinto (ver Vista_Tabla_Direcciones).
        datos_limpios = []
        for item in datos:
            identificacion = str(item.get('identificacion') or item.get('nit') or '').strip()
            id_direccion_wo_raw = item.get('id_direccion_wo') or item.get('IdTerceroDireccion')
            if not identificacion or id_direccion_wo_raw in (None, ''):
                continue
            try:
                id_direccion_wo = int(id_direccion_wo_raw)
            except (ValueError, TypeError):
                continue

            datos_limpios.append({
                'id_direccion_wo': id_direccion_wo,
                'identificacion':  identificacion[:50],
                'nombre':          str(item.get('nombre') or item.get('razon_social') or '').strip()[:200],
                'direccion':       str(item.get('direccion') or '').strip()[:300],
                'telefonos':       str(item.get('telefonos') or item.get('telefono') or '').strip()[:100],
                'ciudad':          str(item.get('ciudad') or '').strip()[:100],
            })

        procesados = ClienteRepository.upsert_clientes_wo(datos_limpios)

        return jsonify({
            "success": True,
            "message": "Clientes sincronizados correctamente",
            "procesados": procesados
        }), 200

    except Exception as e:
        logger.error(f"Error en sincronizar_clientes: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
