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

@wo_bp.route('/api/wo/unificar', methods=['POST'])
def unificar_inventario_wo():
    """
    Sincroniza y unifica el stock de la tabla espejo inventario_wo
    en la tabla db_productos mediante similitud de descripción (mínimo 85%).
    """
    try:
        from backend.core.sql_database import db
        from backend.models.sql_models import InventarioWO, Producto
        from difflib import SequenceMatcher

        # Traer todos los productos de db_productos
        productos = db.session.query(Producto).all()
        
        # Pre-normalizar descripciones locales para optimizar rendimiento
        productos_info = []
        for p in productos:
            desc_local_original = p.descripcion or ""
            desc_local_norm = str(desc_local_original).strip().lower()
            productos_info.append({
                "producto": p,
                "original": desc_local_original,
                "normalizada": desc_local_norm
            })

        # Traer todos los registros de inventario_wo
        items_wo = db.session.query(InventarioWO).all()
        
        actualizados = 0
        no_encontrados = 0
        
        for item in items_wo:
            desc_wo_original = item.descripcion or ""
            if not desc_wo_original.strip():
                continue
                
            desc_wo_norm = str(desc_wo_original).strip().lower()
            
            mejor_similitud = 0.0
            mejor_p_info = None
            
            for p_info in productos_info:
                # SequenceMatcher de la librería estándar
                ratio = SequenceMatcher(None, desc_wo_norm, p_info["normalizada"]).ratio() * 100
                if ratio > mejor_similitud:
                    mejor_similitud = ratio
                    mejor_p_info = p_info
            
            # Log requerido: [DEBUG] Comparando Descripción WO: "[valor_wo]" con Descripción Local: "[valor_local]". Similitud: X%.
            valor_local = mejor_p_info["original"] if mejor_p_info else "Ninguno"
            logger.info(f'[DEBUG] Comparando Descripción WO: "{desc_wo_original}" con Descripción Local: "{valor_local}". Similitud: {mejor_similitud:.2f}%.')
            
            if mejor_similitud >= 85.0 and mejor_p_info:
                p_db = mejor_p_info["producto"]
                p_db.p_terminado = float(item.stock_wo or 0)
                p_db.precio = float(item.precio_wo or 0)
                actualizados += 1
            else:
                no_encontrados += 1
                
        # Confirmar los cambios al final del proceso
        db.session.commit()
        
        logger.info(f"📊 [Unificar WO por Descripción] Proceso finalizado. Actualizados: {actualizados}, No encontrados: {no_encontrados}")
        
        return jsonify({
            "success": True,
            "message": f"Sincronización de stock completada. {actualizados} productos actualizados, {no_encontrados} no emparejados.",
            "actualizados": actualizados,
            "no_emparejados": no_encontrados
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en unificar de WO por descripción: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
