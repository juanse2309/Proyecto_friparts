"""
Rutas de productos.
Endpoints REST para operaciones con productos.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventario_service import inventario_service
from backend.repositories.producto_repository import producto_repo, ProductoRepository
from backend.core.tenant import get_tenant_from_request
from backend.core.database import sheets_client
import logging
import time # Juan Sebastian: Para manejo de caché
import os

logger = logging.getLogger(__name__)

productos_bp = Blueprint('productos', __name__)


@productos_bp.route('/detalle/<codigo_sistema>', methods=['GET'])
def detalle_producto(codigo_sistema):
    """Obtiene el detalle completo de un producto con imagen validada."""
    try:
        from backend.utils.formatters import normalizar_codigo
        print(f"\n{'='*40}")
        print(f"🚀 --- PETICIÓN RECIBIDA PARA: {codigo_sistema} ---")
        
        # 1. Normalización de entrada (Regex)
        codigo_norm = normalizar_codigo(codigo_sistema)
        print(f"🔍 --- CÓDIGO NORMALIZADO: {codigo_norm} ---")
        
        # 2. Búsqueda en el servicio
        resultado = inventario_service.obtener_detalle_producto(codigo_norm)
        
        # Auditoría Defensiva
        enc_bodega = "Si" if resultado.get("status") == "success" and resultado["producto"].get("stock_total", 0) > 0 else "No"
        enc_cat = "Si" if resultado.get("status") == "success" else "No"
        print(f"📊 Buscando detalle para: [{codigo_norm}] | ¿Encontrado en Bodega?: [{enc_bodega}] | ¿Encontrado en Catálogo?: [{enc_cat}]")
        print(f"{'='*40}\n")

        if resultado["status"] == "success":
            p = resultado["producto"]
            # 3. Normalización Simétrica para Imágenes (Súper Radar v3.0)
            codigo_limpio = normalizar_codigo(str(p.get('codigo_sistema', codigo_norm)))
            
            # ... (Resto de la lógica de imágenes se mantiene igual)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            image_dir = os.path.join(base_dir, 'frontend', 'static', 'img', 'productos')
            default_image = '/static/img/no-image.svg'
            
            img_raw = str(p.get('imagen', '')).strip()
            if img_raw and ('drive.google.com' in img_raw or len(img_raw) > 20):
                p['imagen_valida'] = img_raw
            else:
                p['imagen_valida'] = f"/static/img/productos/{codigo_limpio}.jpg" if os.path.exists(os.path.join(image_dir, f"{codigo_limpio}.jpg")) else default_image

            return jsonify(resultado), 200
        else:
            # Fallback Defensivo solicitado por el usuario para evitar roturas en frontend
            return jsonify({
                "status": "error",
                "error": "No encontrado",
                "message": resultado.get("message", "Producto no encontrado en las bases de datos"),
                "debug_info": {
                    "codigo_original": codigo_sistema,
                    "codigo_buscado": codigo_norm,
                    "catalogo": enc_cat,
                    "bodega": enc_bodega
                }
            }), 200 # Devolvemos 200 con status:error como fallback suave
            
    except Exception as e:
        logger.error(f"Error en endpoint detalle: {e}")
        return jsonify({
            "status": "error",
            "message": "Error interno del servidor",
            "debug_info": str(e)
        }), 500



@productos_bp.route('/buscar/<query>', methods=['GET'])
def buscar_productos(query):
    """Busca productos por código, descripción o OEM."""
    try:
        limite = request.args.get('limite', 20, type=int)
        resultados = producto_repo.buscar_por_termino(query, limite)
        
        productos_formateados = []
        for producto in resultados:
            stock_fisico = int(producto.get('P. TERMINADO', 0) or 0)
            stock_comprometido = int(producto.get('COMPROMETIDO', 0) or 0)
            stock_disponible = stock_fisico - stock_comprometido
            
            productos_formateados.append({
                'codigo_sistema': producto.get('CODIGO SISTEMA', ''),
                'id_codigo': producto.get('ID CODIGO', ''),
                'descripcion': producto.get('DESCRIPCION', ''),
                'stock_fisico': stock_fisico,
                'stock_comprometido': stock_comprometido,
                'stock_disponible': stock_disponible,
                'stock_por_pulir': int(producto.get('POR PULIR', 0) or 0),
                'stock_terminado': int(producto.get('P. TERMINADO', 0) or 0),
                'stock_minimo': int(producto.get('STOCK MINIMO', 10) or 10),
                'imagen': producto.get('IMAGEN', ''),
                'unidad': producto.get('UNIDAD', 'PZ')
            })
        
        return jsonify({
            'status': 'success',
            'resultados': productos_formateados
        }), 200
        
    except Exception as e:
        logger.error(f"Error en búsqueda: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@productos_bp.route('/listar', methods=['GET'])
def listar_productos():
    """Lista todos los productos con información completa. Tenant-aware."""
    try:
        from backend.app import PRODUCTOS_LISTAR_CACHE, PRODUCTOS_CACHE_TTL
        ahora = time.time()

        # Resolver tenant desde el rol del usuario en sesión
        tenant = get_tenant_from_request()

        # Forzar limpieza de caché si se solicita
        force_refresh = request.args.get('refresh', 'false').lower() == 'true' or \
                        request.args.get('force_refresh', 'false').lower() == 'true'

        if force_refresh and tenant == "friparts":
            logger.info("🔄 [Caché] Forzando actualización de productos por solicitud del usuario")
            PRODUCTOS_LISTAR_CACHE["data"] = None
            PRODUCTOS_LISTAR_CACHE["timestamp"] = 0

        # 1. Verificar Caché (solo para Friparts, que usa la caché global)
        if tenant == "friparts" and PRODUCTOS_LISTAR_CACHE["data"] and \
                (ahora - PRODUCTOS_LISTAR_CACHE["timestamp"] < PRODUCTOS_CACHE_TTL):
            logger.info("⚡ [Cache] Retornando listado de productos desde caché (friparts)")
            return jsonify(PRODUCTOS_LISTAR_CACHE["data"])

        # 2. Consultar repositorio con el tenant correcto
        logger.info(f"🌐 [API] Consultando repositorio de productos (tenant={tenant!r})")
        repo = ProductoRepository(tenant=tenant)
        productos = repo.listar_todos()

        # 3. Obtener estados de auditoría activos (Solo para Friparts por ahora)
        audit_states = {}
        if tenant == "friparts":
            try:
                from backend.app import get_worksheet
                ws_conteos = get_worksheet("AUDITORIA_CONTEOS")
                if ws_conteos:
                    conteos_raw = sheets_client.get_all_records_seguro(ws_conteos)
                    for c in conteos_raw:
                        code = str(c.get("ID CODIGO") or "").strip().upper()
                        state = str(c.get("ESTADO") or "").strip().upper()
                        if code and state == "DISCREPANCIA":
                            audit_states[code] = "DISCREPANCIA"
            except Exception as e_audit:
                logger.warning(f"No se pudieron cargar estados de auditoría: {e_audit}")
        
        def clean_numeric(val):
            if val is None: return 0
            if isinstance(val, (int, float)): return val
            # Remove $, whitespace, and thousands separators (dots)
            # Assuming '.' is thousands and ',' is decimal for Colombian context
            s = str(val).replace('$', '').replace(' ', '').replace('.', '')
            s = s.replace(',', '.') # Normalize decimal if any
            try:
                return float(s) if s else 0
            except:
                return 0

        productos_formateados = []
        for p in productos:
            # Mapeo flexible para Frimetals (CODIGO vs CÓDIGO vs CODIGO SISTEMA, etc)
            codigo = p.get('CODIGO') or p.get('CÓDIGO') or p.get('CODIGO SISTEMA') or p.get('ID CODIGO', '')
            desc = p.get('DESCRIPCION') or p.get('DESCRIPCIÓN') or p.get('NOMBRE') or 'Sin descripción'
            precio = clean_numeric(p.get('PRECIO') or p.get('VALOR'))
            
            # Stocks (intentar varios nombres comunes)
            p_term = p.get('P. TERMINADO') or p.get('STOCK') or p.get('EXISTENCIAS') or 0
            comp = p.get('COMPROMETIDO') or 0
            p_pulir = p.get('POR PULIR') or 0
            
            stock_fisico = int(clean_numeric(p_term))
            stock_comprometido = int(clean_numeric(comp))
            stock_disponible = stock_fisico - stock_comprometido
            
            stock_bodega = int(clean_numeric(p.get('STOCK_BODEGA') or 0))
            minimo = int(clean_numeric(p.get('MINIMO') or p.get('STOCK MINIMO') or p.get('EXISTENCIAS MÍNIMAS') or 10))
            en_zincado = int(clean_numeric(p.get('EN_ZINCADO') or 0))
            en_granallado = int(clean_numeric(p.get('EN_GRANALLADO') or 0))
            clase_rotacion = str(p.get('CLASE_ROTACION') or 'C').strip()
            
            productos_formateados.append({
                'codigo_sistema': codigo,
                'id_codigo': p.get('ID CODIGO') or codigo,
                'descripcion': desc,
                'stock_fisico': stock_fisico,
                'stock_comprometido': stock_comprometido,
                'stock_disponible': stock_disponible,
                'stock_por_pulir': int(p_pulir or 0),
                'stock_terminado': stock_fisico,
                'stock_ensamblado': int(p.get('PRODUCTO ENSAMBLADO', 0) or 0),
                'stock_bodega': stock_bodega,
                'stock_minimo': minimo,
                'clase_rotacion': clase_rotacion,
                'en_zincado': en_zincado,
                'en_granallado': en_granallado,
                'imagen': p.get('IMAGEN', ''),
                'categoria': p.get('CATEGORIA', ''),
                'marca': p.get('MARCA', ''),
                'unidad': p.get('UNIDAD', 'PZ'),
                'precio': precio,
                'tenant': tenant,
                'estado_auditoria': audit_states.get(str(p.get('ID CODIGO') or codigo).strip().upper(), 'NORMAL')
            })
        
        # Retornar lista plana para compatibilidad total con pedidos.js y autocomplete
        # Asegurar que existan los campos 'codigo', 'nombre' y 'label'
        for p in productos_formateados:
            p['codigo'] = p['codigo_sistema']
            p['nombre'] = p['descripcion']
            p['label'] = f"{p['codigo']} - {p['nombre']}"

        # 3. Guardar en Caché solo para Friparts (opcionalmente formateado o crudo)
        if tenant == "friparts":
            PRODUCTOS_LISTAR_CACHE["data"] = productos_formateados
            PRODUCTOS_LISTAR_CACHE["timestamp"] = ahora

        # --- VALIDACIÓN PRE-VUELO DE IMÁGENES (Juan Sebastian) ---
        # Evita errores 404 en consola enviando solo rutas que existen físicamente
        # o delegando a Drive si es el caso.
        base_dir = os.getcwd()
        image_dir = os.path.join(base_dir, 'frontend', 'static', 'img', 'productos')
        default_image = '/static/img/no-image.svg'

        for p in productos_formateados:
            codigo_limpio = str(p['codigo']).strip().lower()
            # Juan Sebastian: Forzar placeholder para FR-5009 (archivo corrupto reportado por usuario)
            if codigo_limpio in ['fr-5009', '5009']:
                p['imagen_valida'] = default_image
                continue

            # Clean possible prefix (DE-1000 -> 1000)
            num_only = codigo_limpio.split('-')[1] if '-' in codigo_limpio else codigo_limpio
            
            # 1. Si ya tiene IMAGEN en Sheets, verificar si es Drive o URL
            # (Si es Drive, el frontend tiene su proxy, lo dejamos pasar)
            img_raw = str(p.get('imagen', '')).strip()
            if img_raw and ('drive.google.com' in img_raw or len(img_raw) > 20):
                p['imagen_valida'] = img_raw
                continue

            # 2. Buscar en servidor local (static/img/productos/)
            found_path = None
            for name in [codigo_limpio, num_only]:
                for ext in ['.jpg', '.png', '.jpeg']:
                    full_name = f"{name}{ext}"
                    if os.path.exists(os.path.join(image_dir, full_name)):
                        found_path = f"/static/img/productos/{full_name}"
                        break
                if found_path: break
            
            p['imagen_valida'] = found_path if found_path else default_image

        logger.info(f"📊 [DEBUG-PRODUCTOS] FinalCount={len(productos_formateados)} | Tenant={tenant}")
        return jsonify(productos_formateados), 200
        
    except Exception as e:
        logger.error(f"Error listando productos: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@productos_bp.route('/historial/<codigo>', methods=['GET'])
def historial_producto(codigo):
    """
    Obtiene la trazabilidad 360 de un producto.
    """
    try:
        from flask import request
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        print(f"DEBUG: Paginación - Página {page}, Límite {limit}")
        
        tenant = get_tenant_from_request()
        from datetime import datetime
        from backend.utils.formatters import normalizar_codigo
        
        def parsear_fecha_flex(fecha_str):
            if not fecha_str or str(fecha_str).strip() in ['', 'None']:
                return None
            fecha_str = str(fecha_str).strip()
            if ' ' in fecha_str: fecha_str = fecha_str.split(' ')[0]
            if 'T' in fecha_str: fecha_str = fecha_str.split('T')[0]
            for fmt in ['%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y']:
                try: return datetime.strptime(fecha_str, fmt)
                except: pass
            if '/' in fecha_str:
                try:
                    p = fecha_str.split('/')
                    if len(p) == 3: return datetime(int(p[2]), int(p[1]), int(p[0]))
                except: pass
            return None

        def s_get(d, keys, default=''):
            for k in keys:
                if k in d: return d[k]
                for dk, dv in d.items():
                    if str(dk).strip().upper() == str(k).strip().upper():
                        return dv
            return default

        codigo_norm = normalizar_codigo(codigo)
        movimientos = []
        
        # Using Pandas DF to vectorize string contains
        def buscar_movimientos_pandas(hoja, codigo_search, map_tipo, map_fecha, map_resp, map_cant, map_det, filter_col):
            movs = []
            print(f"DEBUG: Iniciando búsqueda en {hoja} para [{codigo_search}] en columna [{filter_col}]")
            try:
                from backend.core.database import sheets_client
                df = sheets_client.get_dataframe(hoja)
                if df.empty:
                    print(f"DEBUG: Hoja {hoja} está VACÍA en el caché.")
                    return movs
                
                # Check target filter column, if it doesn't exist try to fallback 
                if filter_col not in df.columns:
                    print(f"DEBUG: Columna {filter_col} NO encontrada en {hoja}. Intentando fallback...")
                    # Fallback to similar columns
                    for c in df.columns:
                        if 'CODIGO' in c.upper() or 'PRODUCTO' in c.upper():
                            filter_col = c
                            print(f"DEBUG: Fallback exitoso a columna: {filter_col}")
                            break
                            
                if filter_col not in df.columns:
                    print(f"DEBUG: ERROR CRÍTICO: No se encontró columna de filtrado en {hoja}. Columnas: {list(df.columns)}")
                    return movs
                
                # Normalización simétrica garantizada (Regex-based)
                df[filter_col] = df[filter_col].apply(normalizar_codigo)
                
                # Match Inteligente: Captura el código en cualquier parte de la cadena (Flexible)
                import re
                regex_search = fr'{re.escape(str(codigo_search))}'
                mask = df[filter_col].astype(str).str.contains(regex_search, regex=True, na=False)
                df_match = df[mask]
                
                # LOG OBLIGATORIO SOLICITADO
                print(f"DEBUG: Registros encontrados en {hoja} para [{codigo_search}]: {len(df_match)} filas")
                
                for _, r in df_match.iterrows():
                    f_str = s_get(r, map_fecha)
                    f = parsear_fecha_flex(f_str)
                    
                    t_str = str(s_get(r, map_tipo)).strip().upper() if map_tipo else hoja.upper()
                    if hoja == 'RAW_VENTAS':
                        tipo_mov = 'PEDIDO' if 'PEDIDO' in t_str else 'VENTA'
                    else:
                        tipo_mov = hoja.upper() if getattr(hoja, 'upper', None) else hoja
                        if tipo_mov == 'ENSAMBLES': tipo_mov = 'ENSAMBLE'
                        
                    doc_val = str(s_get(r, map_resp))
                    cant_str = s_get(r, map_cant)
                    try: cantidad = int(float(str(cant_str))) if cant_str else 0
                    except: cantidad = 0
                    
                    if hoja == 'INYECCION':
                        det = f"OP: {s_get(r, ['ORDEN PRODUCCION'])} | Maq: {s_get(r, ['MAQUINA'])}"
                    elif hoja == 'PULIDO':
                        det = f"Bs: {s_get(r, ['BUJES BUENOS'])} | PNC: {s_get(r, ['PNC'])}"
                    elif hoja == 'ENSAMBLES':
                        det = f"OP: {s_get(r, ['OP NUMERO'])}"
                    else:
                        det = f"Clasificación: {t_str}"
                        doc_val = f"Doc: {doc_val}" if doc_val else "-"

                    mov_item = {
                        'tipo': tipo_mov,
                        'fecha_obj': f or datetime.min,
                        'fecha': f.strftime('%d/%m/%Y') if f else '-',
                        'responsable': doc_val,
                        'cantidad': cantidad,
                        'detalle': det
                    }

                    # Agregar horarios para PULIDO (Búsqueda robusta)
                    if hoja == 'PULIDO':
                        mov_item['hora_inicio'] = str(s_get(r, ['HORA INICIO', 'HORA_INICIO', 'INICIO', 'HORA_INI', 'HORA INICIAL']))
                        mov_item['hora_fin'] = str(s_get(r, ['HORA FIN', 'HORA_FIN', 'FIN', 'HORA_TER', 'HORA FINAL', 'HORA TERMINA']))

                    movs.append(mov_item)
            except Exception as e:
                logger.error(f"Error {hoja} pandas historial prod: {e}")
            return movs

        # Execute accelerated queries
        mov_iny = buscar_movimientos_pandas('INYECCION', codigo_norm, [], ['FECHA INICIA', 'FECHA'], ['RESPONSABLE'], ['CANTIDAD REAL', 'CANTIDAD'], [], 'ID CODIGO')
        mov_pul = buscar_movimientos_pandas('PULIDO', codigo_norm, [], ['FECHA'], ['RESPONSABLE', 'OPERARIO', 'USUARIO'], ['CANTIDAD RECIBIDA', 'BUJES BUENOS', 'CANTIDAD REAL'], [], 'ID CODIGO')
        mov_ens = buscar_movimientos_pandas('ENSAMBLES', codigo_norm, [], ['FECHA', 'FECHA INICIA'], ['RESPONSABLE'], ['CANTIDAD'], [], 'ID CODIGO')
        from backend.app import Hojas
        mov_com = buscar_movimientos_pandas(Hojas.RAW_VENTAS, codigo_norm, ['CLASIFICACION', 'CLASIFICACIÓN', 'TIPO'], ['FECHA', 'FEC', 'Fecha'], ['DOCUMENTO', 'DOC', 'ORDEN', 'Documento'], ['CANTIDAD', 'CANT', 'Cantidad'], [], 'PRODUCTOS')
        
        movimientos = mov_iny + mov_pul + mov_ens + mov_com
        
        # Resumen de depuración solicitado
        print(f"--- DEBUG: RESULTADOS HISTORIAL PARA {codigo} ---")
        print(f"¿Inyección?: {len(mov_iny)} filas")
        print(f"¿Pulido?:    {len(mov_pul)} filas")
        print(f"¿Ensambles?: {len(mov_ens)} filas")
        print(f"¿Comercial?: {len(mov_com)} filas")
        print(f"Total:      {len(movimientos)} registros")

        # Ordenar cronológicamente descendente (más nuevo a más antiguo)
        movimientos.sort(key=lambda x: x['fecha_obj'], reverse=True)
        
        # Calcular KPIs absolutos antes de paginar
        kpis = { 'INYECCION': 0, 'PULIDO': 0, 'ENSAMBLE': 0, 'COMERCIAL': 0 }
        for m in movimientos:
            try: cant = int(m.get('cantidad', 0))
            except: cant = 0
            
            tipo = m.get('tipo', '')
            if tipo == 'INYECCION': kpis['INYECCION'] += cant
            elif tipo == 'PULIDO': kpis['PULIDO'] += cant
            elif tipo == 'ENSAMBLE': kpis['ENSAMBLE'] += cant
            else: kpis['COMERCIAL'] += cant
            
            if 'fecha_obj' in m: del m['fecha_obj']

        total_records = len(movimientos)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated = movimientos[start_idx:end_idx]
        has_more = end_idx < total_records

        return jsonify({
            'status': 'success',
            'resultados': paginated,
            'kpis': kpis,
            'has_more': has_more,
            'total': total_records,
            'ENSAMBLE': mov_ens # Llave en singular y mayúsculas según lo solicitado
        }), 200

    except Exception as e:
        logger.error(f"Error historial_producto: {e}")
        code = 429 if "saturado" in str(e) else 500
        return jsonify({'status': 'error', 'message': str(e)}), code