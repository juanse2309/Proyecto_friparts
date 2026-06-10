# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
import os
import logging
from sqlalchemy import text

wo_bp = Blueprint('wo', __name__)
logger = logging.getLogger(__name__)

def limpiar_codigo_wo(c):
    if not c:
        return ""
    import re
    # Convertir a mayúsculas, quitar espacios y caracteres no alfanuméricos
    return re.sub(r'[^A-Z0-9]', '', str(c).upper().strip())

@wo_bp.route('/api/wo/recibir_datos', methods=['POST'])
def recibir_datos():
    """
    Endpoint para recibir datos sincronizados desde el agente local de World Office.
    Verifica el header X-API-Key contra la variable de entorno WO_SYNC_API_KEY.
    """
    # Validar API Key de seguridad
    api_key_header = request.headers.get('X-API-Key')
    api_key_env = os.environ.get('WO_SYNC_API_KEY')
    
    if not api_key_env:
        logger.error("❌ Variable de entorno WO_SYNC_API_KEY no configurada en el servidor.")
        return jsonify({
            "success": False, 
            "error": "Configuración de seguridad incompleta en el servidor"
        }), 500
        
    if api_key_header != api_key_env:
        logger.warning(f"⚠️ Intento de sincronización WO no autorizado. Header X-API-Key: {api_key_header}")
        return jsonify({
            "success": False, 
            "error": "No autorizado. API Key inválida o ausente."
        }), 401

    try:
        payload = request.json
        if payload is None:
            payload = {}

        # Soportar formato envuelto {nombre_vista, datos} y fallback de lista directa
        if isinstance(payload, dict):
            nombre_vista = payload.get("nombre_vista", "Desconocida")
            datos = payload.get("datos", [])
        else:
            nombre_vista = "Desconocida (Lista directa)"
            datos = payload

        if not isinstance(datos, list):
            datos = [datos] if datos else []
            
        logger.info(f"Datos de WO recibidos ({nombre_vista}): {len(datos)} registros")

        # Upsert para Vista_Tabla_Inventarios y unificación directa en db_productos
        # Upsert para Vista_Tabla_Inventarios y unificación directa en db_productos
        if nombre_vista == "Vista_Tabla_Inventarios":
            from backend.core.sql_database import db
            from backend.models.sql_models import InventarioWO, Producto
            
            # Asegurar columnas alternas en caliente en Render
            try:
                db.session.execute(text("ALTER TABLE inventario_wo ADD COLUMN IF NOT EXISTS codigo_alterno VARCHAR(100)"))
                db.session.execute(text("ALTER TABLE inventario_wo ADD COLUMN IF NOT EXISTS referencia VARCHAR(100)"))
                db.session.commit()
            except Exception as e_ddl:
                db.session.rollback()
                logger.warning(f"No se pudieron asegurar las columnas DDL de inventario_wo: {e_ddl}")
            
            # Cargar productos de base de datos a memoria para cruce flexible ultra-rápido
            productos_db = db.session.query(Producto).all()
            prods_map = []
            for p in productos_db:
                prods_map.append({
                    "obj": p,
                    "codigo_sistema": p.codigo_sistema,
                    "id_codigo": p.id_codigo,
                    "cod_sis_limpio": limpiar_codigo_wo(p.codigo_sistema),
                    "id_cod_limpio": limpiar_codigo_wo(p.id_codigo)
                })

            # Normalizar las llaves de todos los registros recibidos de forma robusta
            def normalizar_llaves(d):
                if not isinstance(d, dict):
                    return d
                import unicodedata
                def limpiar_texto(s):
                    s = s.lower().strip()
                    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
                    s = s.replace(' ', '_')
                    return s
                return {limpiar_texto(k): v for k, v in d.items()}

            datos_normalizados = []
            for item in datos:
                datos_normalizados.append(normalizar_llaves(item))

            logger.info(f"[DEBUG] Recibidos {len(datos_normalizados)} registros para insertar.")
            if datos_normalizados:
                logger.info(f"[DEBUG] Llaves del primer registro normalizado: {list(datos_normalizados[0].keys())}")
                logger.info(f"[DEBUG] Primer registro normalizado crudo: {datos_normalizados[0]}")

            upsert_count = 0
            productos_actualizados = 0
            logs_fallidos_counter = [0] # Mutable list para contar en el helper

            def buscar_producto_flexible(r_wo):
                # Extraer códigos de World Office
                c_principal = r_wo.get('codigo_producto') or r_wo.get('codigo')
                c_alterno = r_wo.get('codigo_alterno') or r_wo.get('codigo_alterno_wo')
                ref = r_wo.get('referencia') or r_wo.get('ref') or r_wo.get('referencia_comercial')
                
                candidatos = [c for c in [c_principal, c_alterno, ref] if c]
                if not candidatos:
                    return None
                
                # 1. Coincidencia exacta limpia
                for c in candidatos:
                    c_limpio = limpiar_codigo_wo(c)
                    if not c_limpio:
                        continue
                    for p_info in prods_map:
                        if c_limpio == p_info["cod_sis_limpio"] or c_limpio == p_info["id_cod_limpio"]:
                            return p_info["obj"]
                
                # 2. Coincidencia exacta original (case-insensitive, strip)
                for c in candidatos:
                    c_str = str(c).upper().strip()
                    for p_info in prods_map:
                        sis_upper = (p_info["codigo_sistema"] or "").upper().strip()
                        id_upper = (p_info["id_codigo"] or "").upper().strip()
                        if c_str == sis_upper or c_str == id_upper:
                            return p_info["obj"]
                            
                # 3. Coincidencia de Substring parcial (min 3 caracteres)
                for c in candidatos:
                    c_limpio = limpiar_codigo_wo(c)
                    if len(c_limpio) < 3:
                        continue
                    for p_info in prods_map:
                        if c_limpio in p_info["cod_sis_limpio"] or c_limpio in p_info["id_cod_limpio"]:
                            return p_info["obj"]
                        if p_info["cod_sis_limpio"] and p_info["cod_sis_limpio"] in c_limpio:
                            return p_info["obj"]
                        if p_info["id_cod_limpio"] and p_info["id_cod_limpio"] in c_limpio:
                            return p_info["obj"]
                
                # Reporte de logs de control si falla el emparejamiento
                if logs_fallidos_counter[0] < 3:
                    sample_fritech = prods_map[0]["codigo_sistema"] if prods_map else "Sin productos"
                    logger.info(
                        f"⚠️ [Sincronización] Cruce fallido ({logs_fallidos_counter[0] + 1}/3): Intentando cruzar candidatos WO {candidatos} "
                        f"con FriTech (Muestra: '{sample_fritech}'). No se encontró coincidencia flexible."
                    )
                    logs_fallidos_counter[0] += 1
                
                return None

            for r in datos_normalizados:
                # Extraer codigo_producto de forma flexible
                codigo_producto = (
                    r.get('codigo_producto') or 
                    r.get('codigo') or
                    r.get('codigo_alterno') or
                    r.get('referencia')
                )
                if not codigo_producto:
                    continue
                codigo_producto = str(codigo_producto).strip()
                
                descripcion = (
                    r.get('descripcion') or 
                    r.get('nombre') or 
                    r.get('detalle') or 
                    ""
                )
                descripcion = str(descripcion).strip()
                
                # Extraer campos opcionales / alternos
                codigo_alterno = r.get('codigo_alterno') or r.get('codigo_alterno_wo') or ""
                codigo_alterno = str(codigo_alterno).strip()
                referencia = r.get('referencia') or r.get('ref') or r.get('referencia_comercial') or ""
                referencia = str(referencia).strip()
                
                # Convertir stock de forma segura
                stock_raw = r.get('stock_wo') or r.get('stock') or r.get('cantidad') or 0
                try:
                    stock_wo = float(stock_raw)
                except (ValueError, TypeError):
                    stock_wo = 0.0
                    
                # Convertir precio de forma segura
                precio_raw = r.get('precio_wo') or r.get('precio') or r.get('precio_venta') or 0
                try:
                    precio_wo = float(precio_raw)
                except (ValueError, TypeError):
                    precio_wo = 0.0
                
                # 1. Realizar Upsert en la tabla espejo inventario_wo
                registro_existente = db.session.query(InventarioWO).filter_by(codigo_producto=codigo_producto).first()
                if registro_existente:
                    registro_existente.descripcion = descripcion
                    registro_existente.stock_wo = stock_wo
                    registro_existente.precio_wo = precio_wo
                    registro_existente.codigo_alterno = codigo_alterno
                    registro_existente.referencia = referencia
                else:
                    nuevo_registro = InventarioWO(
                        codigo_producto=codigo_producto,
                        descripcion=descripcion,
                        stock_wo=stock_wo,
                        precio_wo=precio_wo,
                        codigo_alterno=codigo_alterno,
                        referencia=referencia
                    )
                    db.session.add(nuevo_registro)
                
                # 2. Modificación Directa: Sobrescribir p_terminado y precio en db_productos mediante cruce flexible
                p_db = buscar_producto_flexible(r)
                if p_db:
                    p_db.p_terminado = stock_wo
                    p_db.precio = precio_wo
                    productos_actualizados += 1
                
                upsert_count += 1
            
            db.session.commit()
            
            # Forzar volcado y verificar cantidad en BD
            guardados_bd = db.session.query(InventarioWO).count()
            logger.info(f"[DEBUG] Registros guardados en inventario_wo: {guardados_bd}")
            logger.info(f"✅ Upsert exitoso en inventario_wo: {upsert_count} registros procesados en esta tanda.")
            logger.info(f"✅ Unificación directa completada: {productos_actualizados} productos actualizados en db_productos.")
        
        return jsonify({
            "success": True,
            "message": f"Datos de la vista '{nombre_vista}' recibidos con éxito",
            "recibidos": len(datos),
            "nombre_vista": nombre_vista
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en endpoint recibir_datos de WO: {e}")
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500

def normalizar_referencia(codigo):
    """Normalización agresiva: mayúsculas, elimina todo lo no alfanumérico
    y cualquier prefijo de letras que preceda a dígitos (FR-, MT-, CAR-, FR9714, etc.)"""
    if not codigo:
        return ""
    import re
    t = str(codigo).upper()
    # Quitar TODO lo que no sea letra o dígito
    t = re.sub(r'[^A-Z0-9]', '', t)
    # Eliminar cualquier bloque de letras al inicio si va seguido de dígitos
    # Ej: FR9714 -> 9714, MT5002 -> 5002, CAR9890 -> 9890
    t = re.sub(r'^[A-Z]+(?=\d)', '', t)
    return t

@wo_bp.route('/api/wo/unificar', methods=['POST'])
def unificar_inventario_wo():
    """
    MODO DIAGNÓSTICO: Solo lee y compara, NO actualiza nada.
    Imprime los valores RAW de WO y los 3 códigos locales más cercanos
    para identificar el gap de normalización.
    """
    try:
        from backend.core.sql_database import db
        from backend.models.sql_models import InventarioWO, Producto
        from difflib import SequenceMatcher, get_close_matches

        # Traer todos los productos de db_productos
        productos = db.session.query(Producto).all()
        
        # Guardar valores RAW locales para diagnóstico
        # Clave: normalizada -> (codigo_sistema_raw, id_codigo_raw)
        productos_mapa_raw = {}
        for p in productos:
            ref_local = normalizar_referencia(p.codigo_sistema) or normalizar_referencia(p.id_codigo)
            if ref_local:
                productos_mapa_raw[ref_local] = {
                    "codigo_sistema": p.codigo_sistema,
                    "id_codigo": p.id_codigo,
                    "ref_norm": ref_local
                }

        claves_locales_norm = list(productos_mapa_raw.keys())

        # Traer los primeros 20 items de inventario_wo para diagnóstico (evitar flood de logs)
        items_wo = db.session.query(InventarioWO).limit(20).all()
        
        encontrados = 0
        no_encontrados = 0

        for item in items_wo:
            # Valores RAW tal cual están en la tabla
            ref_raw = item.referencia
            alt_raw = item.codigo_alterno
            cod_raw = item.codigo_producto

            # Normalizar para intentar lookup
            ref_wo_norm = normalizar_referencia(ref_raw)
            alt_wo_norm = normalizar_referencia(alt_raw)

            hit = productos_mapa_raw.get(ref_wo_norm) or productos_mapa_raw.get(alt_wo_norm)

            if hit:
                logger.info(
                    f'[DEBUG-OK] WO: referencia="{ref_raw}" | alt="{alt_raw}" | cod="{cod_raw}" '
                    f'-> MATCH con local: codigo_sistema="{hit["codigo_sistema"]}" | id_codigo="{hit["id_codigo"]}" | ref_norm="{hit["ref_norm"]}"'
                )
                encontrados += 1
            else:
                # Buscar los 3 más cercanos por similitud en las claves normalizadas
                clave_busqueda = ref_wo_norm or alt_wo_norm
                cercanos_norm = get_close_matches(clave_busqueda, claves_locales_norm, n=3, cutoff=0.0) if clave_busqueda else []
                cercanos_raw = [
                    f"{productos_mapa_raw[c]['codigo_sistema']} (norm={c})"
                    for c in cercanos_norm
                ]
                logger.info(
                    f'[DEBUG-FAIL] WO: referencia="{ref_raw}" | alt="{alt_raw}" | cod="{cod_raw}" '
                    f'| ref_norm="{ref_wo_norm}" | alt_norm="{alt_wo_norm}" '
                    f'-> NO ENCONTRADO. Más cercanos locales: {cercanos_raw}'
                )
                no_encontrados += 1

        logger.info(f"📊 [DIAGNÓSTICO] Encontrados: {encontrados} | No encontrados: {no_encontrados} (de {len(items_wo)} muestras)")
        
        return jsonify({
            "success": True,
            "message": f"MODO DIAGNÓSTICO completado. Encontrados: {encontrados}, No encontrados: {no_encontrados}. Revisa los logs del servidor.",
            "encontrados": encontrados,
            "no_encontrados": no_encontrados,
            "nota": "Este modo NO actualiza datos. Revisa los logs [DEBUG-OK] y [DEBUG-FAIL] en el servidor."
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en diagnóstico WO: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
