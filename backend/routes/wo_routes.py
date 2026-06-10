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

            upsert_count = 0
            productos_actualizados = 0
            logs_fallidos_counter = [0] # Mutable list para contar en el helper

            def buscar_producto_flexible(r_wo):
                # Extraer códigos de World Office
                c_principal = (
                    r_wo.get('código_producto') or 
                    r_wo.get('codigo_producto') or 
                    r_wo.get('codigo') or 
                    r_wo.get('código')
                )
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

            for r in datos:
                # Extraer codigo_producto de forma flexible
                codigo_producto = (
                    r.get('código_producto') or 
                    r.get('codigo_producto') or 
                    r.get('codigo') or 
                    r.get('código')
                )
                if not codigo_producto:
                    continue
                codigo_producto = str(codigo_producto).strip()
                
                descripcion = (
                    r.get('descripción') or 
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
            logger.info(f"✅ Upsert exitoso en inventario_wo: {upsert_count} registros procesados.")
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
    Lee todos los registros de 'inventario_wo' y sobrescribe directamente 
    la columna 'p_terminado' y 'precio' de cada producto correspondiente en 'db_productos'.
    """
    try:
        from backend.core.sql_database import db
        from backend.models.sql_models import InventarioWO, Producto
        
        # Asegurar columnas alternas en caliente
        try:
            db.session.execute(text("ALTER TABLE inventario_wo ADD COLUMN IF NOT EXISTS codigo_alterno VARCHAR(100)"))
            db.session.execute(text("ALTER TABLE inventario_wo ADD COLUMN IF NOT EXISTS referencia VARCHAR(100)"))
            db.session.commit()
        except Exception as e_ddl:
            db.session.rollback()
            logger.warning(f"No se pudieron asegurar las columnas DDL de inventario_wo: {e_ddl}")
            
        registros_wo = db.session.query(InventarioWO).all()
        productos_db = db.session.query(Producto).all()
        
        # Mapa en memoria para emparejamiento flexible
        prods_map = []
        for p in productos_db:
            prods_map.append({
                "obj": p,
                "codigo_sistema": p.codigo_sistema,
                "id_codigo": p.id_codigo,
                "cod_sis_limpio": limpiar_codigo_wo(p.codigo_sistema),
                "id_cod_limpio": limpiar_codigo_wo(p.id_codigo)
            })
            
        actualizados = 0
        logs_fallidos_counter = [0] # Mutable list para contar en el helper

        def buscar_producto_flexible(item_wo):
            c_principal = item_wo.codigo_producto
            c_alterno = item_wo.codigo_alterno
            ref = item_wo.referencia
            
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
                    f"⚠️ [Unificación] Cruce fallido ({logs_fallidos_counter[0] + 1}/3): Intentando cruzar candidatos WO {candidatos} "
                    f"con FriTech (Muestra: '{sample_fritech}'). No se encontró coincidencia flexible."
                )
                logs_fallidos_counter[0] += 1
            
            return None
        
        for item in registros_wo:
            stock_wo = item.stock_wo or 0.0
            precio_wo = item.precio_wo or 0.0
            
            p_db = buscar_producto_flexible(item)
            if p_db:
                p_db.p_terminado = stock_wo
                p_db.precio = precio_wo
                actualizados += 1
                
        db.session.commit()
        logger.info(f"✅ Unificación manual completada: {actualizados} productos actualizados en db_productos.")
        
        return jsonify({
            "success": True,
            "message": "Unificación completada con éxito",
            "actualizados": actualizados
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en endpoint unificar de WO: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
