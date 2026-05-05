"""
Rutas de productos.
Endpoints REST para operaciones con productos.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventario_service import inventario_service
from backend.repositories.producto_repository import producto_repo, ProductoRepository
from backend.core.tenant import get_tenant_from_request
import logging
import time # Juan Sebastian: Para manejo de caché
import os

logger = logging.getLogger(__name__)

productos_bp = Blueprint('productos', __name__)


@productos_bp.route('/detalle/<codigo_sistema>', methods=['GET'])
def detalle_producto(codigo_sistema):
    """Obtiene el detalle completo de un producto con auditoría de stock detallada."""
    try:
        from backend.utils.formatters import normalizar_codigo
        from backend.models.sql_models import Producto
        
        codigo_norm = normalizar_codigo(codigo_sistema).strip().upper()
        # Intentar búsqueda con código limpio (fallback) por si el catálogo usa el corto
        codigo_limpio = codigo_norm.replace('FR-', '').replace('CB-', '').replace('ENS-', '').strip()
        
        # Búsqueda Robusta: Primero por el normalizado, luego por el limpio
        p_sql = Producto.query.filter(
            (Producto.id_codigo == codigo_norm) | 
            (Producto.codigo_sistema == codigo_norm) |
            (Producto.id_codigo == codigo_limpio)
        ).first()
        
        if p_sql:
            # MÉTRICA MATEMÁTICA PURA
            v_por_pulir = float(p_sql.por_pulir or 0)
            v_p_terminado = float(p_sql.p_terminado or 0)
            v_bodega = float(p_sql.stock_bodega or 0)
            
            # La suma que solicita el usuario: Por Pulir + Terminado
            stock_total_calculado = v_por_pulir + v_p_terminado
            comp = float(p_sql.comprometido or 0)
            
            # Auditoría Crítica en Consola
            print(f'🔍 [CHECK-STOCK] Buscando: {codigo_sistema} | Encontrado ID: {p_sql.id_codigo} | Por Pulir: {v_por_pulir} | Terminado: {v_p_terminado} | Total: {stock_total_calculado}')

            # CONSTRUCCIÓN DE RESPUESTA SIMPLIFICADA (PEDIDO USUARIO)
            res_data = {
                "id_codigo": p_sql.id_codigo,
                "codigo_sistema": p_sql.codigo_sistema,
                "descripcion": p_sql.descripcion,
                "p_terminado": float(v_p_terminado),
                "por_pulir": float(v_por_pulir),
                "comprometido": float(comp),
                "stock_disponible": float(v_p_terminado), # Mapeado a p_terminado según pedido
                "disponible": float(v_p_terminado),
                "stock_bodega": float(v_bodega),
                "imagen": p_sql.imagen or "",
                "imagen_valida": "" 
            }
            
            # Gestión de Imágenes
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            image_dir = os.path.join(base_dir, 'frontend', 'static', 'img', 'productos')
            codigo_img = normalizar_codigo(str(res_data.get('codigo_sistema', codigo_norm)))
            
            if res_data['imagen'] and ('drive.google.com' in res_data['imagen'] or len(res_data['imagen']) > 20):
                res_data['imagen_valida'] = res_data['imagen']
            else:
                img_path = os.path.join(image_dir, f"{codigo_img}.jpg")
                res_data['imagen_valida'] = f"/static/img/productos/{codigo_img}.jpg" if os.path.exists(img_path) else '/static/img/no-image.svg'

            return jsonify({"status": "success", "producto": res_data}), 200
        else:
            print(f'⚠️ [CHECK-STOCK] No se encontró el producto: {codigo_norm}')
            return jsonify({"status": "error", "message": f"Producto [{codigo_norm}] no encontrado"}), 200
            
    except Exception as e:
        logger.error(f"Error crítico en detalle producto SQL: {e}")
        return jsonify({"status": "error", "message": str(e)}), 200



@productos_bp.route('/buscar/<query>', methods=['GET'])
def buscar_productos(query):
    """
    Busca productos uniendo con la tabla de costos (SQL-Native).
    Permite obtener Stock y Precio en una sola consulta.
    """
    try:
        from backend.core.sql_database import db
        from sqlalchemy import text
        
        limite = request.args.get('limite', 30, type=int)
        termino = f"%{query.strip().upper()}%"
        
        # JOIN optimizado con CTE para pre-normalización
        PREFIX_PATTERN = "'^(FR-|CAR-|INT-|ENS-|CB-|DE-|HR-|KIT-|AL-)'"
        # JOIN optimizado: Usamos dos joins directos (exacto y normalizado) para evitar REGEXP en la cláusula JOIN
        PREFIX_PATTERN = "'^(FR-|CAR-|INT-|ENS-|CB-|DE-|HR-|KIT-|AL-)'"
        sql = f"""
            WITH precios_norm AS (
                SELECT 
                    codigo,
                    precio,
                    REGEXP_REPLACE(codigo, {PREFIX_PATTERN}, '', 'i') as cod_norm
                FROM db_precio_venta
            ),
            productos_base AS (
                SELECT 
                    *,
                    REGEXP_REPLACE(id_codigo, {PREFIX_PATTERN}, '', 'i') as id_norm
                FROM db_productos
                WHERE 
                    id_codigo ILIKE :t OR 
                    codigo_sistema ILIKE :t OR 
                    descripcion ILIKE :t OR
                    oem ILIKE :t
            )
            SELECT 
                p.id_codigo, 
                p.descripcion as nombre_producto, 
                p.p_terminado, 
                p.comprometido, 
                p.stock_bodega, 
                p.por_pulir, 
                p.codigo_sistema, 
                p.imagen,
                p.oem,
                COALESCE(pv1.precio, pv2.precio, p.precio, 0) as precio_raw
            FROM productos_base p
            LEFT JOIN db_precio_venta pv1 ON pv1.codigo = p.id_codigo
            LEFT JOIN precios_norm pv2 ON pv2.cod_norm = p.id_norm
            ORDER BY p.codigo_sistema
            LIMIT :l
        """
        
        result_query = db.session.execute(text(sql), {"t": termino, "l": limite}).mappings().all()
        
        def limpiar_precio(p_str):
            if not p_str or str(p_str).strip() in ['', 'None']: return 0
            l = str(p_str).replace('$', '').replace('.', '').replace(',', '').strip()
            try: return float(l)
            except: return 0

        resultado = []
        for r in result_query:
            p_term = float(r['p_terminado'] or 0)
            comp = float(r['comprometido'] or 0)
            
            resultado.append({
                "id_codigo": r['id_codigo'],
                "nombre_producto": r['nombre_producto'],
                "descripcion": r['nombre_producto'], # Alias para compatibilidad
                "p_terminado": p_term,
                "comprometido": comp,
                "disponible": p_term - comp,
                "stock_disponible": p_term - comp, # Alias para compatibilidad
                "stock_bodega": float(r['stock_bodega'] or 0),
                "por_pulir": float(r['por_pulir'] or 0),
                "codigo_sistema": r['codigo_sistema'],
                "imagen": r['imagen'] or "",
                "oem": r['oem'] or "",
                "precio": limpiar_precio(r['precio_raw'])
            })
            
        return jsonify({
            'status': 'success',
            'resultados': resultado
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en búsqueda SQL-JOIN: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@productos_bp.route('/listar', methods=['GET'])
def listar_productos():
    """
    Lista todos los productos uniendo la tabla maestra con la tabla de costos.
    Cruza por id_codigo vs referencia aplicando normalización.
    """
    try:
        from backend.core.sql_database import db
        from sqlalchemy import text
        import re

        # JOIN optimizado con CTE para pre-normalización
        PREFIX_PATTERN = "'^(FR-|CAR-|INT-|ENS-|CB-|DE-|HR-|KIT-|AL-)'"
        # JOIN optimizado: Usamos dos joins directos (exacto y normalizado) para evitar REGEXP en la cláusula JOIN
        PREFIX_PATTERN = "'^(FR-|CAR-|INT-|ENS-|CB-|DE-|HR-|KIT-|AL-)'"
        sql = f"""
            WITH precios_norm AS (
                SELECT 
                    codigo,
                    precio,
                    REGEXP_REPLACE(codigo, {PREFIX_PATTERN}, '', 'i') as cod_norm
                FROM db_precio_venta
            ),
            productos_base AS (
                SELECT 
                    *,
                    REGEXP_REPLACE(id_codigo, {PREFIX_PATTERN}, '', 'i') as id_norm
                FROM db_productos
            )
            SELECT 
                p.id_codigo, 
                p.descripcion as nombre_producto, 
                p.p_terminado, 
                p.comprometido, 
                p.stock_bodega, 
                p.por_pulir, 
                p.codigo_sistema, 
                p.imagen,
                COALESCE(pv1.precio, pv2.precio, p.precio, 0) as precio_raw
            FROM productos_base p
            LEFT JOIN db_precio_venta pv1 ON pv1.codigo = p.id_codigo
            LEFT JOIN precios_norm pv2 ON pv2.cod_norm = p.id_norm
            ORDER BY p.codigo_sistema
        """
        
        result_query = db.session.execute(text(sql)).mappings().all()
        
        def limpiar_precio(val):
            if val is None or str(val).strip() in ['', 'None']: return 0
            # Si ya es un número, no lo toques (evita multiplicar por 10 si hay punto decimal)
            if isinstance(val, (int, float)): return float(val)
            from decimal import Decimal
            if isinstance(val, Decimal): return float(val)
            
            # Solo limpiar si es string
            s = str(val).replace('$', '').replace(' ', '')
            # Si tiene coma y punto, es formato 1.234,56 -> 1234.56
            if ',' in s and '.' in s:
                s = s.replace('.', '').replace(',', '.')
            # Si solo tiene punto y parece ser separador de miles (ej: 116.400)
            elif '.' in s and len(s.split('.')[-1]) == 3:
                s = s.replace('.', '')
            # Si solo tiene coma, es decimal (ej: 116400,00)
            elif ',' in s:
                s = s.replace(',', '.')
                
            try: return float(s)
            except: return 0

        resultado = []
        for r in result_query:
            p_term = float(r['p_terminado'] or 0)
            comp = float(r['comprometido'] or 0)
            
            resultado.append({
                "id_codigo": r['id_codigo'],
                "nombre_producto": r['nombre_producto'],
                "descripcion": r['nombre_producto'], # Alias para compatibilidad
                "p_terminado": p_term,
                "comprometido": comp,
                "disponible": p_term - comp,
                "stock_disponible": p_term - comp, # Alias para compatibilidad
                "stock_bodega": float(r['stock_bodega'] or 0),
                "por_pulir": float(r['por_pulir'] or 0),
                "codigo_sistema": r['codigo_sistema'],
                "imagen": r['imagen'] or "",
                "precio": limpiar_precio(r['precio_raw'])
            })
            
        logger.info(f"📊 [SQL-NATIVE] Listando {len(resultado)} productos con Precios de db_precio_venta")
        return jsonify({"items": resultado}), 200

    except Exception as e:
        logger.error(f"❌ Error en /api/productos/listar (JOIN Costos): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify([]), 200


@productos_bp.route('/historial/<codigo>', methods=['GET'])
def historial_producto(codigo):
    """
    Obtiene la trazabilidad 360 de un producto 100% SQL-Native.
    Soporta fallback para códigos sin prefijo (ej: FR-9304 -> 9304).
    """
    try:
        from sqlalchemy import text, or_
        from backend.core.sql_database import db
        from backend.models.sql_models import (
            ProduccionInyeccion, ProduccionPulido, Ensamble, 
            Pedido, Pnc
        )
        from backend.utils.formatters import normalizar_codigo
        from datetime import datetime

        codigo_norm = normalizar_codigo(codigo).strip().upper()
        # Fallback inteligente: Quitar el prefijo para buscar en tablas de producción
        codigo_limpio = codigo_norm.replace('FR-', '').replace('CB-', '').replace('ENS-', '').strip()
        
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 500))
        
        eventos = []
        radar = { 'INYECCION': 0, 'PULIDO': 0, 'ENSAMBLE': 0, 'COMERCIAL': 0, 'PNC': 0 }

        # 1. BARRIDO DE INYECCIÓN
        try:
            res_iny = ProduccionInyeccion.query.filter(
                or_(
                    ProduccionInyeccion.id_codigo.ilike(f"%{codigo_norm}%"),
                    ProduccionInyeccion.id_codigo.ilike(f"%{codigo_limpio}%")
                )
            ).all()
            radar['INYECCION'] = len(res_iny)
            for r in res_iny:
                eventos.append({
                    'tipo': 'INYECCION',
                    'fecha_dt': r.fecha_inicia if hasattr(r.fecha_inicia, 'year') else datetime.now(),
                    'fecha': r.fecha_inicia.strftime('%d/%m/%Y') if hasattr(r.fecha_inicia, 'strftime') else str(r.fecha_inicia or ''),
                    'responsable': str(r.responsable or 'SISTEMA'),
                    'cant': int(float(r.cantidad_real or 0)),
                    'detalle': f"Máquina: {r.maquina or ''} | Molde: {r.molde or ''}"
                })
        except Exception as e: logger.error(f"Falla bloque Inyección para {codigo}: {e}")

        # 2. BARRIDO DE PULIDO (ESTRUCTURA REAL)
        try:
            res_pul = ProduccionPulido.query.filter(
                or_(
                    ProduccionPulido.codigo.ilike(f"%{codigo_norm}%"),
                    ProduccionPulido.codigo.ilike(f"%{codigo_limpio}%")
                )
            ).all()
            radar['PULIDO'] = len(res_pul)
            for r in res_pul:
                evento_dict = {
                    'tipo': 'PULIDO',
                    'fecha': r.fecha.strftime('%d/%m/%Y') if hasattr(r.fecha, 'strftime') else str(r.fecha),
                    'cant': int(r.cantidad_real or 0),
                    'responsable': r.responsable,
                    'detalle': f"Hora: {r.hora_inicio} - {r.hora_fin} | OP: {r.orden_produccion or 'N/A'}",
                    'fecha_dt': r.fecha if hasattr(r.fecha, 'year') else datetime.now()
                }
                print(f'[DB-PULIDO] Usando cantidad_real: {evento_dict["cant"]}')
                eventos.append(evento_dict)
        except Exception as e: logger.error(f"Falla bloque Pulido para {codigo}: {e}")

        # 🔥 3. BARRIDO DE ENSAMBLE
        try:
            sql_ens = text("""
                SELECT id, fecha, responsable, cantidad, op_numero, buje_ensamble 
                FROM db_ensambles 
                WHERE id_codigo ILIKE :o OR id_codigo ILIKE :l
            """)
            res_ens = db.session.execute(sql_ens, {"o": f"%{codigo_norm}%", "l": f"%{codigo_limpio}%"}).mappings().all()
            radar['ENSAMBLE'] = len(res_ens)
            for r in res_ens:
                f_dt = r['fecha'] if hasattr(r['fecha'], 'year') else None
                eventos.append({
                    'tipo': 'ENSAMBLE',
                    'fecha_dt': f_dt or datetime.now(),
                    'fecha': f_dt.strftime('%d/%m/%Y') if f_dt else str(r['fecha'] or ''),
                    'responsable': str(r['responsable'] or 'SISTEMA'),
                    'cant': int(float(r['cantidad'] or 0)),
                    'detalle': f"OP: {r['op_numero'] or ''} | {r['buje_ensamble'] or ''}"
                })
        except Exception as e: logger.error(f"Falla bloque Ensamble para {codigo}: {e}")

        # 4. BARRIDO DE VENTAS / PEDIDOS
        try:
            res_ped = Pedido.query.filter(Pedido.id_codigo.ilike(f"%{codigo_norm}%")).all()
            radar['COMERCIAL'] = len(res_ped)
            for r in res_ped:
                eventos.append({
                    'tipo': 'VENTA' if r.estado == 'EXPORTADO_WO' else 'PEDIDO',
                    'fecha_dt': r.fecha if hasattr(r.fecha, 'year') else datetime.now(),
                    'fecha': r.fecha.strftime('%d/%m/%Y') if hasattr(r.fecha, 'strftime') else str(r.fecha or ''),
                    'responsable': str(r.cliente or 'CLIENTE'),
                    'cant': int(float(r.cantidad or 0)),
                    'detalle': f"Orden: {r.id_pedido} | Vendedor: {r.vendedor or ''}"
                })
        except Exception as e: logger.error(f"Falla bloque Ventas para {codigo}: {e}")

        # 5. BARRIDO DE PNC
        try:
            res_pnc = Pnc.query.filter(Pnc.id_codigo.ilike(f"%{codigo_norm}%")).all()
            radar['PNC'] = len(res_pnc)
            for r in res_pnc:
                eventos.append({
                    'tipo': 'PNC',
                    'fecha_dt': r.fecha if hasattr(r.fecha, 'year') else datetime.now(),
                    'fecha': r.fecha.strftime('%d/%m/%Y') if hasattr(r.fecha, 'strftime') else str(r.fecha or ''),
                    'responsable': 'CONTROL CALIDAD',
                    'cant': int(float(r.cantidad or 0)),
                    'detalle': f"Criterio: {r.criterio or ''} | {r.observacion or ''}"
                })
        except Exception as e: logger.error(f"Falla bloque PNC para {codigo}: {e}")

        # --- LOG DE AUDITORÍA FINAL ---
        print(f"📊 [RADAR 360] Auditando {codigo_norm} y fallback {codigo_limpio}: {radar}")

        # --- UNIFICACIÓN Y ORDENAMIENTO ---
        eventos.sort(key=lambda x: x['fecha_dt'] if x['fecha_dt'] else datetime.min, reverse=True)

        kpis = { 'INYECCION': 0, 'PULIDO': 0, 'ENSAMBLE': 0, 'COMERCIAL': 0 }
        for e in eventos:
            c = e.get('cant', 0)
            if e['tipo'] == 'INYECCION': kpis['INYECCION'] += c
            elif e['tipo'] == 'PULIDO': kpis['PULIDO'] += c
            elif e['tipo'] == 'ENSAMBLE': kpis['ENSAMBLE'] += c
            else: kpis['COMERCIAL'] += c
            if 'fecha_dt' in e: del e['fecha_dt']

        total = len(eventos)
        start = (page - 1) * limit
        end = start + limit
        paginados = eventos[start:end]

        return jsonify({
            'status': 'success',
            'resultados': paginados,
            'kpis': kpis,
            'radar': radar,
            'total': total,
            'has_more': end < total
        }), 200

    except Exception as e:
        logger.error(f"Error crítico en Timeline 360 (SQL Final): {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

    except Exception as e:
        logger.error(f"Error historial_producto: {e}")
        code = 429 if "saturado" in str(e) else 500
        return jsonify({'status': 'error', 'message': str(e)}), code