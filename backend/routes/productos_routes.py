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
    """Obtiene el detalle completo de un producto."""
    try:
        resultado = inventario_service.obtener_detalle_producto(codigo_sistema)
        
        if resultado["status"] == "success":
            return jsonify(resultado), 200
        else:
            return jsonify(resultado), 404
            
    except Exception as e:
        logger.error(f"Error en endpoint detalle: {e}")
        return jsonify({
            "status": "error",
            "message": "Error interno del servidor"
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