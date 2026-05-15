# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from flask_cors import CORS
from datetime import datetime, time, timedelta, date, timezone
import pytz
import uuid
import traceback
import time as time_module # Usar alias para no chocar con datetime.time
import os
import json
import math
import pandas as pd
import logging
import psycopg2.extensions
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE) # Blindaje OID 25
from concurrent.futures import ThreadPoolExecutor
from backend.utils.report_service import PDFGenerator
from backend.services.bom_service import calcular_descuentos_ensamble, traducir_codigo_componente
from backend.utils.formatters import normalizar_codigo, to_int, limpiar_cadena

# Global executor for background tasks (PDF, Drive, etc)
bg_executor = ThreadPoolExecutor(max_workers=3)

from backend.core.sql_database import db


# Configurar logging detallado
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configurar Flask
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, '../frontend/templates'), 
            static_folder=os.path.join(BASE_DIR, '../frontend/static'))
CORS(app)

# Required for Flask Sessions
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_friparts_key_2026")

# --- GLOBAL TIMEZONE CONFIG (Colombia UTC-5) ---
COLOMBIA_TZ = pytz.timezone('America/Bogota')

def get_now_colombia():
    return datetime.now(COLOMBIA_TZ)

# --- CONFIGURACIÃ“N SQL (SQL-First) ---
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://admin_juan:5uM2TSjhKB2nIRPR41xJlmgJ5tKgaonX@dpg-d7f5mrpf9bms73a0a1g0-a.virginia-postgres.render.com/fritech_db'
)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
logger.info("ðŸ“¡ [DB] SQLAlchemy inicializado con Ã©xito")
# -----------------------------------

# Login Blueprints
from backend.routes.auth_routes import auth_bp
from backend.routes.pedidos_routes import pedidos_bp
from backend.routes.imagenes_routes import imagenes_bp

from backend.routes.facturacion_routes import facturacion_bp
from backend.routes.inventario_routes import inventario_bp
from backend.routes.metals_routes import metals_bp
from backend.routes.procura_routes import procura_bp
from backend.routes.dashboard_routes import dashboard_bp
from backend.routes.admin_routes import admin_bp
from backend.routes.inyeccion_routes import inyeccion_bp
from backend.routes.pulido_routes import pulido_bp
from backend.routes.asistencia_routes import asistencia_bp
from backend.routes.productos_routes import productos_bp
from backend.routes.historial_routes import historial_bp
from backend.routes.ensamble_routes import ensamble_bp
from backend.routes.ia_routes import ia_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(imagenes_bp, url_prefix='/imagenes')
app.register_blueprint(facturacion_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(metals_bp)
app.register_blueprint(procura_bp)
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(productos_bp, url_prefix='/api/productos')
app.register_blueprint(historial_bp)

app.register_blueprint(admin_bp)
app.register_blueprint(inyeccion_bp)
app.register_blueprint(pulido_bp)
app.register_blueprint(asistencia_bp, url_prefix='/api/asistencia')
app.register_blueprint(ensamble_bp)
app.register_blueprint(ia_bp)


# --- RUTA DE DEBUG INICIAL ---
@app.route('/')
def index():
    """Pagina principal con la interfaz web."""
    try:
        from backend.models.sql_models import Usuario
        # FILTRO ESTRICTO: Solo staff frimetals o administracion
        lista_usuarios = Usuario.query.filter(
            Usuario.activo == True,
            (Usuario.rol.ilike('staff frimetals')) | (Usuario.rol.ilike('administracion'))
        ).order_by(Usuario.nombre_completo).all()

        logger.info(f"[{get_now_colombia()}] >>> PETICIÓN RECIBIDA: index.html")
        return render_template('index.html', usuarios=lista_usuarios)
    except Exception as e:
        logger.error(f"âŒ ERROR RENDERIZANDO index.html: {e}")
        return f"Error en el servidor: {str(e)}", 500
# -----------------------------

# --- ENDPOINTS CATÁLOGO: MÁQUINAS, RESPONSABLES, CLIENTES ---
@app.route('/api/obtener_maquinas', methods=['GET'])
@app.route('/api/maquinas', methods=['GET'])
def obtener_maquinas():
    """Retorna lista de máquinas activas desde db_maquinas (SQL-Native)."""
    try:
        from backend.models.sql_models import Maquina
        maquinas = Maquina.query.filter_by(activa=True).order_by(Maquina.nombre).all()
        nombres = [m.nombre for m in maquinas]
        if not nombres:
            # Fallback: query directa sin filtro de activa
            from backend.core.sql_database import db
            from sqlalchemy import text
            rows = db.session.execute(text("SELECT nombre FROM db_maquinas ORDER BY nombre")).fetchall()
            nombres = [r[0] for r in rows if r[0]]
        return jsonify(nombres), 200
    except Exception as e:
        logger.error(f"❌ Error obteniendo máquinas SQL: {e}")
        return jsonify([]), 200

@app.route('/api/obtener_responsables', methods=['GET'])
def obtener_responsables():
    """Retorna lista de responsables activos (SQL-Native). Prioriza db_usuarios, fallback db_asistencia."""
    try:
        from backend.models.sql_models import Usuario
        usuarios = Usuario.query.filter_by(activo=True).order_by(Usuario.nombre_completo).all()
        # Retornamos objeto completo para que el frontend pueda filtrar por departamento
        # Usamos nombre_completo si existe, sino el username
        datos = []
        for u in usuarios:
            nombre_final = u.nombre_completo if u.nombre_completo else u.username
            datos.append({
                "nombre": nombre_final,
                "departamento": u.departamento or "",
                "username": u.username
            })
        
        if not datos:
            from backend.core.sql_database import db
            from sqlalchemy import text
            rows = db.session.execute(text(
                "SELECT DISTINCT colaborador FROM db_asistencia WHERE colaborador IS NOT NULL ORDER BY colaborador"
            )).fetchall()
            datos = [{"nombre": r[0], "departamento": "", "username": r[0]} for r in rows if r[0]]
            
        return jsonify(datos), 200
    except Exception as e:
        logger.error(f"❌ Error obteniendo responsables SQL: {e}")
        return jsonify([]), 200

@app.route('/api/obtener_clientes', methods=['GET'])
def obtener_clientes():
    """Retorna lista de clientes desde db_clientes (SQL-Native)."""
    try:
        from backend.core.repository_service import repository_service
        clientes = repository_service.get_clientes_all()
        return jsonify(clientes), 200
    except Exception as e:
        logger.error(f"❌ Error obteniendo clientes SQL: {e}")
        return jsonify([]), 200
# -------------------------------------------------------

# --- CONFIGURACIÃ“N DE CACHÃ‰ GLOBAL ---
CACHE_TTL_STRICT = 60    # 1 minuto para datos muy volÃ¡tiles
CACHE_TTL_MEDIUM = 300   # 5 minutos para catÃ¡logos y personal
CACHE_TTL_LONG = 3600    # 1 hora para configuraciones

PRODUCTOS_CACHE_TTL = CACHE_TTL_MEDIUM

PRODUCTOS_LISTAR_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": CACHE_TTL_MEDIUM
}

PRODUCTOS_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": PRODUCTOS_CACHE_TTL
}

PRODUCTOS_V2_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": PRODUCTOS_CACHE_TTL
}

RESPONSABLES_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": CACHE_TTL_LONG
}

CLIENTES_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": CACHE_TTL_LONG
}

PEDIDOS_PENDIENTES_CACHE = {
    "friparts": {"data": None, "timestamp": 0, "ttl": CACHE_TTL_STRICT},
    "frimetals": {"data": None, "timestamp": 0, "ttl": CACHE_TTL_STRICT}
}

# METALS_PRODUCTOS_CACHE eliminado â€” ahora se usa ProductoRepository(tenant='frimetals')
# que centraliza el acceso a la hoja siguiendo el patrÃ³n multi-tenant (DRY).

METALS_PERSONAL_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": CACHE_TTL_MEDIUM
}

def invalidar_cache_pedidos():
    """Llamar tras registrar o actualizar alistamiento."""
    global PEDIDOS_PENDIENTES_CACHE
    PEDIDOS_PENDIENTES_CACHE["friparts"]["timestamp"] = 0
    PEDIDOS_PENDIENTES_CACHE["frimetals"]["timestamp"] = 0
    logger.info("ðŸ—‘ï¸ CachÃ© de PEDIDOS invalidado (ambos tenants)")

def invalidar_cache_productos():
    global PRODUCTOS_LISTAR_CACHE
    PRODUCTOS_LISTAR_CACHE["timestamp"] = 0
    logger.info("ðŸ—‘ï¸ CachÃ© de PRODUCTOS invalidado")

# (Hojas legacy eliminadas)

# ====================================================================
# FUNCIONES DE CACH
# ====================================================================

def invalidar_cache_productos():
    """Invalida todos los caches relacionados con productos."""
    PRODUCTOS_CACHE["data"] = None
    PRODUCTOS_CACHE["timestamp"] = 0
    
    PRODUCTOS_LISTAR_CACHE["data"] = None
    PRODUCTOS_LISTAR_CACHE["timestamp"] = 0
    
    PRODUCTOS_V2_CACHE["data"] = None
    PRODUCTOS_V2_CACHE["timestamp"] = 0
    
    print(" ðŸ§¹ Todos los caches de PRODUCTOS han sido invalidados")

# ====================================================================
# HELPERS
# ====================================================================

def obtener_precio_db(codigo):
    """
    Obtiene el precio de un producto desde PostgreSQL.
    Retorna 0 si no se encuentra.
    """
    try:
        from backend.models.sql_models import Producto
        codigo_buscar = str(codigo).strip().upper()
        
        producto = db.session.query(Producto).filter(
            (Producto.codigo_sistema == codigo_buscar) | 
            (Producto.id_codigo == codigo_buscar)
        ).first()
        
        if producto and producto.precio:
            try:
                return float(producto.precio)
            except:
                return 0
        return 0
    except Exception as e:
        logger.warning(f"No se pudo obtener precio SQL para {codigo}: {e}")
        return 0

def buscar_producto_en_inventario(codigo_sistema):
    """
    Busca un producto en la tabla db_productos (SQL-Native).
    Elimina dependencia total de Google Sheets.
    """
    from backend.models.sql_models import Producto
    from backend.utils.formatters import normalizar_codigo
    try:
        codigo_norm = normalizar_codigo(codigo_sistema)
        # Búsqueda directa y robusta (Match exacto con primera palabra)
        producto = Producto.query.filter(
            (Producto.codigo_sistema == codigo_norm) | 
            (Producto.id_codigo == codigo_norm)
        ).first()
        
        if not producto:
            return {'encontrado': False, 'error': f'Producto "{codigo_norm}" no encontrado en SQL'}
            
        return {
            'encontrado': True,
            'datos': {
                'CODIGO SISTEMA': producto.codigo_sistema,
                'ID CODIGO': producto.id_codigo,
                'DESCRIPCION': producto.descripcion,
                'POR PULIR': float(producto.por_pulir or 0),
                'P. TERMINADO': float(producto.p_terminado or 0),
                'PRODUCTO ENSAMBLADO': float(producto.producto_ensamblado or 0),
                'STOCK_BODEGA': float(producto.stock_bodega or 0),
                'COMPROMETIDO': float(producto.comprometido or 0)
            }
        }
    except Exception as e:
        logger.error(f"❌ ERROR SQL en buscar_producto_en_inventario: {str(e)}")
        return {'encontrado': False, 'error': str(e)}


def obtener_datos_producto(codigo_entrada):
    """
    HELPER CENTRALIZADO: Este es el unico lugar que deberia realizar bÃºsquedas directas
    en la hoja de PRODUCTOS para evitar disparar el error 429 (Too Many Requests).
    
    Flujo: 
    1. Normaliza el cÃ³digo (quita prefijos 'FR-').
    2. Busca en la hoja PRODUCTOS.
    3. Devuelve los 3 pilares de los datos: CÃ³digo Sistema, ID Ficha y el diccionario completo.
    """
    try:
        codigo_sis = obtener_codigo_sistema_real(codigo_entrada)
        if not codigo_sis:
            return None, None, None
            
        resultado = buscar_producto_en_inventario(codigo_sis)
        if resultado['encontrado']:
            datos = resultado['datos']
            id_codigo = str(datos.get('ID CODIGO', '')).strip()
            codigo_completo = str(datos.get('CODIGO SISTEMA', '')).strip()
            return codigo_completo, id_codigo, datos
            
        return codigo_sis, None, None
    except:
        return None, None, None

def obtener_stock(codigo_sistema, almacen):
    """Obtiene el stock actual de un producto en un almacen especifico."""
    try:
        resultado = buscar_producto_en_inventario(codigo_sistema)
        if not resultado['encontrado']:
            return 0
        
        datos = resultado['datos']
        
        mapeo_almacenes = {
            'POR PULIR': 'POR PULIR',
            'P. TERMINADO': 'P. TERMINADO',
            'PRODUCTO ENSAMBLADO': 'PRODUCTO ENSAMBLADO',
            'STOCK_BODEGA': 'STOCK_BODEGA',
            'CLIENTE': 'CLIENTE',
            'PNC': 'PNC'
        }
        
        columna = mapeo_almacenes.get(almacen)
        if not columna or columna not in datos:
            return 0
        
        stock = datos.get(columna, 0)
        # Usar helper to_int o casting robusto
        try:
            if isinstance(stock, (int, float)):
                return int(stock)
            val_str = str(stock).strip().replace(',', '')
            if not val_str: return 0
            return int(float(val_str))
        except Exception:
            return 0
            
    except Exception as e:
        print(f"Error obteniendo stock: {e}")
        return 0

def actualizar_stock(codigo_sistema, cantidad, almacen, operacion='sumar'):
    """
    Actualiza el stock en PostgreSQL (SQL-Native).
    Elimina dependencia total de Google Sheets y Caché.
    """
    from backend.models.sql_models import Producto
    from backend.utils.formatters import normalizar_codigo
    try:
        codigo_norm = normalizar_codigo(codigo_sistema)
        producto = Producto.query.filter(
            (Producto.codigo_sistema == codigo_norm) | 
            (Producto.id_codigo == codigo_norm)
        ).first()

        if not producto:
            return False, f"Producto {codigo_norm} no encontrado en SQL"

        mapeo_sql = {
            'POR PULIR': 'por_pulir',
            'P. TERMINADO': 'p_terminado',
            'PRODUCTO ENSAMBLADO': 'producto_ensamblado',
            'STOCK_BODEGA': 'stock_bodega',
            'CLIENTE': 'comprometido',
            'PNC': 'comprometido'
        }

        columna = mapeo_sql.get(almacen)
        if not columna:
            return False, f"Almacén {almacen} no mapeado a SQL"

        stock_actual = float(getattr(producto, columna) or 0)
        
        if operacion == 'sumar':
            nuevo_valor = stock_actual + cantidad
        else:
            nuevo_valor = stock_actual - cantidad
            if nuevo_valor < 0:
                logger.warning(f"⚠️ Stock negativo detectado en {codigo_norm} ({almacen}): {nuevo_valor}")
                # En modo normal, podríamos retornar error, pero registrar_salida_resiliente lo ignorará

        setattr(producto, columna, nuevo_valor)
        db.session.flush()
        logger.info(f" ✅ [SQL-STOCK] {codigo_norm} en {almacen}: {stock_actual} -> {nuevo_valor}")
        return True, "OK"
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error actualizando stock SQL: {e}")
        return False, str(e)

def calcular_metricas_semaforo(stock_total, p_min, p_reorden, p_max):
    """
    LOGICA DE NEGOCIO UNIFICADA: Centraliza las reglas de colores del inventario.
    Usa colores: green, yellow, red, dark (NO success/danger/warning)
    Estados: STOCK OK, POR PEDIR, CRÃ TICO, AGOTADO
    """
    tiene_config = (p_max is not None and p_max > 0 and p_max != 999999)
    
    if stock_total <= 0:
        estado = "AGOTADO"
        color = "dark"
        mensaje = "Sin Stock"
    elif stock_total <= (p_reorden or 0):
        estado = "CRÃ TICO"
        color = "red"
        mensaje = f"Bajo Punto Reorden ({p_reorden})"
    elif stock_total < (p_min or 0):
        estado = "POR PEDIR"
        color = "yellow"
        mensaje = f"Bajo MÃ­nimo ({p_min})"
    else:
        estado = "STOCK OK"
        color = "green"
        mensaje = "Stock Saludable"

    if not tiene_config and stock_total > 0:
        mensaje = ""
        
    return {
        "estado": estado,
        "color": color,
        "mensaje": mensaje,
        "configurado": tiene_config
    }

def registrar_entrada(codigo_sistema, cantidad, almacen):
    """Registra una entrada de inventario."""
    return actualizar_stock(codigo_sistema, cantidad, almacen, 'sumar')

def registrar_salida(codigo_sistema, cantidad, almacen):
    """Registra una salida de inventario."""
    return actualizar_stock(codigo_sistema, cantidad, almacen, 'restar')

def mover_inventario_entre_etapas(codigo_sistema, cantidad, origen, destino):
    """Mueve inventario de un almacen a otro."""
    exito_resta, mensaje_resta = registrar_salida(codigo_sistema, cantidad, origen)
    if not exito_resta:
        return False, mensaje_resta
    
    exito_suma, mensaje_suma = registrar_entrada(codigo_sistema, cantidad, destino)
    if not exito_suma:
        registrar_entrada(codigo_sistema, cantidad, origen)
        return False, mensaje_suma
    
    return True, f'Movimiento exitoso: {cantidad} de {origen} a {destino}'

def error_response(mensaje, status_code=400):
    """Retorna una respuesta de error estandarizada."""
    logger.warning(f" Respuesta de error ({status_code}): {mensaje}")
    return jsonify({
        "success": False,
        "error": mensaje
    }), status_code

def validate_required_fields(data, required_fields):
    """Valida campos obligatorios en un diccionario. Retorna lista de errores."""
    errors = []
    for field in required_fields:
        val = data.get(field)
        if val is None or (isinstance(val, str) and str(val).strip() == ''):
            errors.append(f"Campo '{field}' es obligatorio")
    return errors

def to_int(valor, default=0):
    """Convierte un valor a entero de forma segura."""
    try:
        if valor is None or str(valor).strip() == '':
            return default
        if isinstance(valor, (int, float)):
            return int(valor)
        # Limpiar comas y otros caracteres si es string
        clean_val = str(valor).strip().replace(',', '')
        return int(float(clean_val))
    except:
        return default

# ====================================================================
# HELPERS DE NEGOCIO
# ====================================================================

# (La funciÃ³n normalizar_codigo se ha movido a backend.utils.formatters para centralizaciÃ³n Regex)

def obtener_codigo_sistema_real(codigo_entrada):
    """
    Traduce el codigo ingresado por el usuario al codigo real del sistema.
    MEJORADO: Ahora normaliza para comparaciÃ³n flexible.
    
    Ejemplos:
    - 'FR-9304' â†’ '9304'
    - 'fr-9304' â†’ '9304'
    - ' 9304 ' â†’ '9304'
    - 'INY-1050' â†’ '1050'
    - '9304' â†’ '9304'
    
    Args:
        codigo_entrada (str): Codigo ingresado por el usuario
        
    Returns:
        str: Codigo normalizado del sistema
    """
    try:
        logger.info(f"ðŸ“¥ obtener_codigo_sistema_real ENTRADA: '{codigo_entrada}' (tipo: {type(codigo_entrada).__name__})")
        
        if codigo_entrada is None:
            logger.warning("âš ï¸   CÃ³digo de entrada es None")
            return ""
        
        # Usar la nueva funciÃ³n de normalizaciÃ³n
        resultado = normalizar_codigo(codigo_entrada)
        logger.info(f"ðŸ“¤ obtener_codigo_sistema_real SALIDA: '{resultado}'")
        return resultado
        
    except Exception as e:
        logger.error(f"â Œ Error al traducir codigo '{codigo_entrada}': {str(e)}")
        logger.error(f"   Tipo de error: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return str(codigo_entrada).strip() if codigo_entrada else ""

def obtener_producto_por_codigo(codigo_entrada: str):
    """
    Busca un producto aceptando CODIGO SISTEMA (FR-9304) o ID CODIGO (9304) en SQL.
    Devuelve un diccionario con ambos codigos o None si no lo encuentra.
    """
    if not codigo_entrada:
        return None
    
    from backend.models.sql_models import Producto
    from backend.utils.formatters import normalizar_codigo
    try:
        entrada_limpia = normalizar_codigo(codigo_entrada)
        p = Producto.query.filter(
            (Producto.codigo_sistema == entrada_limpia) |
            (Producto.id_codigo == entrada_limpia)
        ).first()

        if p:
            return {
                "id_codigo": p.id_codigo,
                "codigo_sistema": p.codigo_sistema,
                "descripcion": p.descripcion
            }
        
        return None
    except Exception as e:
        logger.error(f"❌ Error buscando producto SQL: {e}")
        return None

def actualizar_stock_producto(codigo_sistema: str, cantidad: int):
    """
    Actualiza el stock en SQL. Busca por CODIGO SISTEMA y suma a por_pulir.
    """
    try:
        from backend.models.sql_models import Producto
        from backend.utils.formatters import normalizar_codigo
        codigo_norm = normalizar_codigo(codigo_sistema)
        p = Producto.query.filter(Producto.codigo_sistema == codigo_norm).first()
        if p:
            p.por_pulir = (p.por_pulir or 0) + cantidad
            db.session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error stock SQL: {e}")
        return False

# Nota: La funciÃ³n registrar_pnc_detalle se ha movido a la secciÃ³n SQL-Native

def registrar_log_operacion(modulo, datos):
    """
    Registra auditoría de operaciones en la base de datos SQL (db_logs).
    100% SQL-Native.
    """
    try:
        from backend.models.sql_models import OperacionLog
        
        detalles_json = json.dumps(datos) if isinstance(datos, (dict, list)) else str(datos)
        operario = "Sistema"
        if isinstance(datos, dict):
            operario = datos.get('OPERARIO') or datos.get('RESPONSABLE') or "Sistema"
        
        nuevo_log = OperacionLog(
            modulo=modulo,
            operario=str(operario),
            accion=f"Registro en {modulo}",
            detalles=detalles_json
        )
        db.session.add(nuevo_log)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.warning(f" ⚠️ [SQL-LOG] Fallo al registrar log: {e}")
        return False

def obtener_buje_origen_y_qty(codigo_producto):
    """
    SQL-NATIVE: Obtiene el componente y qty desde nueva_ficha_maestra.
    """
    from backend.models.sql_models import FichaMaestra
    from backend.utils.formatters import normalizar_codigo
    try:
        codigo_norm = normalizar_codigo(codigo_producto)
        # Buscar en Ficha Maestra SQL
        ficha = FichaMaestra.query.filter(FichaMaestra.producto.ilike(f"%{codigo_norm}%")).first()
        
        if ficha:
            return str(ficha.subproducto).strip(), float(ficha.cantidad or 1), str(ficha.producto).strip()

        return codigo_producto, 1.0, "NO DEFINIDO"
    except Exception as e:
        logger.error(f"❌ Error en mapeo ensamble SQL: {e}")
        return codigo_producto, 1.0, "ERROR"


def validate_form(data, tipo_proceso="inyeccion"):
    """Valida los datos del formulario."""
    errors = []
    cleaned = {}
    
    required = ["fecha_inicio", "codigo_producto"]
    
    if tipo_proceso == "facturacion":
        required.extend(["cantidad_vendida", "cliente"])
    else:
        required.append("responsable")
        if tipo_proceso == "pulido":
            required.append("cantidad_recibida")
        else:
            required.append("cantidad_real")

    for field in required:
        if not data.get(field) or str(data.get(field)).strip() == "":
            errors.append(f"El campo '{field}' es obligatorio.")

    if errors:
        return False, errors, {}

    try:
        cleaned = {
            "fecha_inicio": data.get("fecha_inicio"),
            "fecha_fin": data.get("fecha_fin", data.get("fecha_inicio")),
            "responsable": data.get("responsable", "N/A"),
            "codigo_producto": data.get("codigo_producto"),
            "maquina": data.get("maquina", "N/A"),
            "hora_inicio": data.get("hora_inicio", "00:00"),
            "hora_fin": data.get("hora_fin", "00:00"),
            "cantidad_real": int(data.get("cantidad_real", 0)) if data.get("cantidad_real") else 0,
            "cantidad_vendida": int(data.get("cantidad_vendida", 0)) if data.get("cantidad_vendida") else 0,
            "no_cavidades": data.get("no_cavidades", "1"),
            "contador_maquina": data.get("contador_maquina", ""),
            "orden_produccion": data.get("orden_produccion", ""),
            "observaciones": data.get("observaciones", ""),
            "peso_vela_maquina": data.get("peso_vela_maquina", ""),
            "peso_bujes": data.get("peso_bujes", ""),
            "lote": data.get("lote", ""),
            "cliente": data.get("cliente", "General"),
            "total_venta": float(data.get('total_venta', 0)) if data.get('total_venta') else 0,
            "cantidad_recibida": int(data.get("cantidad_recibida", 0)) if data.get("cantidad_recibida") else 0,
            "pnc": int(data.get("pnc", 0)) if data.get("pnc") else 0,
            "criterio_pnc": data.get("criterio_pnc", "")
        }
    except ValueError as e:
        errors.append(f"Error en conversion de datos: {str(e)}")

    return len(errors) == 0, errors, cleaned

# ====================================================================
# FUNCIN ESPECFICA PARA LOG_FACTURACION (DEPRECATED - Use registrar_log_operacion)
# ====================================================================

def registrar_log_facturacion(fila):
    """Registra una facturacion en LOG_FACTURACION correctamente."""
    return registrar_log_operacion('FACTURACION', fila)

# ====================================================================
# FUNCIN OBTENER MQUINAS
# ====================================================================

# [REMOVED LEGACY MACHINES HELPER]

# ====================================================================
# ENDPOINTS PARA REGISTROS
# ====================================================================


def corregir_url_imagen(url):
    """Convierte URLs de Google Drive o IDs al formato de proxy correcto"""
    if not url:
        return ''
    
    url = str(url).strip()
    
    # 1. Si ya es una URL de proxy, retornarla
    if '/imagenes/proxy/' in url:
        return url
        
    # 2. Descartar rutas locales basura (.jpg, .png o carpetas locales)
    if (url.endswith('.jpg') or url.endswith('.png') or url.endswith('.jpeg') or 
        url.startswith('/imagenes/') or url.startswith('imagenes/')):
        return ''
            
    # 3. Extraer ID de varios formatos conocidos
    file_id = None
    
    if 'id=' in url:
        import re
        match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        if match: file_id = match.group(1)
    elif 'drive.google.com' in url:
        import re
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if match: file_id = match.group(1)
    elif len(url) > 15 and not url.startswith('http') and not url.startswith('/') and '.' not in url:
        # Los IDs de Drive suelen ser largos y sin puntos
        file_id = url
            
    if file_id:
        return f"/imagenes/proxy/{file_id}"
        
    return url


@app.route('/api/verificar-estructura-completa', methods=['GET'])
def verificar_estructura_completa():
    """Verifica la conectividad con PostgreSQL."""
    try:
        from sqlalchemy import text
        db.session.execute(text("SELECT 1"))
        return jsonify({
            'status': 'success',
            'database': 'PostgreSQL Connected',
            'message': 'Estructura SQL-Native verificada.'
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint para verificar que la app esta funcionando."""
    try:
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "bujes_produccion_sql",
            "database": "SQL-Native",
            "endpoints": {
                "obtener_responsables": "/api/obtener_responsables",
                "obtener_clientes": "/api/obtener_clientes",
                "obtener_productos": "/api/obtener_productos",
                "obtener_maquinas": "/api/obtener_maquinas"
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ========== ENDPOINT INYECCIÃ“N - SQL NATIVE ==========
@app.route('/api/inyeccion', methods=['POST'])
def registrar_inyeccion():
    """Registra una operaciÃ³n de inyecciÃ³n en SQL-Native con descuento de BOM."""
    try:
        data = request.get_json()
        from backend.models.sql_models import ProduccionInyeccion
        from backend.utils.formatters import normalizar_codigo
        from backend.services.bom_service import calcular_descuentos_ensamble
        
        # 1. Validaciones
        codigo_raw = str(data.get('codigo_producto', '')).strip()
        responsable = str(data.get('responsable', '')).strip()
        if not codigo_raw or not responsable:
            return jsonify({'success': False, 'error': 'Producto y Responsable son obligatorios'}), 400

        codigo_norm = normalizar_codigo(codigo_raw)
        
        # 2. Cantidades
        disparos = int(float(data.get('disparos', 0) or 0))
        cavidades = int(float(data.get('no_cavidades', 1) or 1))
        pnc = float(data.get('pnc', 0) or 0)
        cantidad_final = float(data.get('cantidad_real', disparos * cavidades))
        
        id_inyeccion = f"INY-{uuid.uuid4().hex[:8].upper()}"
        
        # 3. Registrar en SQL
        nuevo_registro = ProduccionInyeccion(
            id_inyeccion=id_inyeccion,
            fecha=datetime.date.today(),
            codigo_sistema=codigo_norm,
            responsable=responsable,
            maquina=data.get('maquina'),
            cavidades=cavidades,
            contador_maq=disparos,
            cantidad_real=cantidad_final,
            pnc=pnc,
            estado='PENDIENTE',
            observaciones=data.get('observaciones', '')
        )
        db.session.add(nuevo_registro)
        
        # 4. LÃ³gica de Descuento (BOM)
        bom_res = calcular_descuentos_ensamble(codigo_norm, int(cantidad_final))
        if bom_res.get('success'):
            from backend.app import registrar_salida
            for comp in bom_res.get('componentes', []):
                registrar_salida(comp['codigo_inventario'], comp['cantidad_total_descontar'], "STOCK_BODEGA")
        
        # 5. Entrada de producto por pulir
        from backend.app import registrar_entrada
        registrar_entrada(codigo_norm, cantidad_final - pnc, "POR PULIR")
        
        db.session.commit()
        clear_mes_cache()
        return jsonify({'success': True, 'id': id_inyeccion, 'message': 'InyecciÃ³n registrada en SQL con BOM'}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"âŒ Error en registrar_inyeccion SQL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====================================================================
# MES (MANUFACTURING EXECUTION SYSTEM) - CONTROL DE PRODUCCIÃ“N
# ====================================================================

@app.route('/api/mes/programar', methods=['POST'])
def mes_programar():
    """Fase 1: El Jefe de Planta 'pone en cola' uno o varios productos para una mÃ¡quina (Simplificado)."""
    try:
        from backend.models.sql_models import ProgramacionInyeccion
        from backend.core.sql_database import db


        data = request.json
        maquina = data.get('maquina')
        fecha_str = data.get('fecha')
        productos = data.get('productos', []) 
        responsable = data.get('responsable_planta', 'ADMIN')
        observaciones = data.get('observaciones', '')
        molde_capacidad = int(data.get('molde') or 0)
        
        # Parsear Fecha
        if fecha_str:
            try:
                fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except:
                fecha_obj = datetime.date.today()
        else:
            fecha_obj = datetime.date.today()

        if not productos:
            return jsonify({'success': False, 'error': 'No se enviaron productos para programar'}), 400

        # Guardar cada producto del montaje
        ids_creados = []
        for p in productos:
            nueva_prog = ProgramacionInyeccion(
                fecha=fecha_obj,
                codigo_sistema=str(p.get('codigo')).strip(),
                maquina=maquina,
                molde=molde_capacidad,
                cavidades=int(p.get('cavidades', 1)),
                responsable_planta=responsable,
                observaciones=observaciones,
                estado='PROGRAMADO'
            )
            db.session.add(nueva_prog)
            db.session.flush()
            ids_creados.append(nueva_prog.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'ids_programacion': ids_creados,
            'count': len(productos)
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en mes_programar SQL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Error en mes_programar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mes/cancelar/<int:id_target>', methods=['POST'])
def mes_cancelar(id_target):
    """Fase 1b: Liberar mÃ¡quina cancelando por ID (ProgramaciÃ³n o ProducciÃ³n activa) en SQL Native."""
    try:
        from backend.models.sql_models import ProgramacionInyeccion, ProduccionInyeccion
        from backend.core.sql_database import db

        encontrado = False
        
        # 1. Intentar borrar de ProgramaciÃ³n (Cola)
        prog = db.session.get(ProgramacionInyeccion, id_target)
        if prog:
            db.session.delete(prog)
            encontrado = True
            
        # 2. Intentar borrar de ProducciÃ³n (Activa) si no estaba en cola
        if not encontrado:
            inyeccion = db.session.get(ProduccionInyeccion, id_target)
            if inyeccion:
                db.session.delete(inyeccion)
                encontrado = True
        
        if not encontrado:
            return jsonify({'success': False, 'error': f'ID {id_target} no encontrado en Ninguna Tabla'}), 404
            
        db.session.commit()
        clear_mes_cache()
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en mes_cancelar SQL (PolimÃ³rfico): {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# --- CACHE MES (Consolidado y Protegido contra 429) ---
_mes_cache = {
    'dashboard': {'data': None, 'ts': 0},
    'prog_todas': {'data': None, 'ts': 0},
    'pendientes_calidad': {'data': None, 'ts': 0},
    'pendientes_validacion': {'data': None, 'ts': 0}
}
MES_CACHE_TTL = 60 # Aumentado a 60s para proteger cuota de API

def clear_mes_cache():
    """Limpia todos los caches de lectura del MES (Llamar en toda operaciÃ³n de escritura)."""
    global _mes_cache
    logger.info("ðŸ—‘ï¸  [CACHE] Invalidando cachÃ© MES por operaciÃ³n de escritura")
    for key in _mes_cache:
        _mes_cache[key]['ts'] = 0

@app.route('/api/mes/programaciones/<maquina>', methods=['GET'])
def mes_get_programaciones(maquina):
    """Obtiene programaciones activas desde SQL (db_programacion)."""
    try:
        from backend.models.sql_models import ProgramacionInyeccion
        maquina_upper = maquina.upper()
        
        query = db.session.query(ProgramacionInyeccion).filter(
            ProgramacionInyeccion.estado.notin_(['COMPLETADO', 'CANCELADO'])
        )
        
        if maquina_upper != 'TODAS':
            query = query.filter(ProgramacionInyeccion.maquina == maquina_upper)
            
        registros = query.all()
        
        # Formatear para el frontend (adaptado al modelo simplificado)
        data = []
        for r in registros:
            data.append({
                'id':            r.id,
                'fecha':         r.fecha.strftime('%Y-%m-%d') if r.fecha else '',
                'codigo_sistema': r.codigo_sistema,
                'maquina':       (r.maquina or '').upper(),
                'molde':         r.molde,
                'cavidades':     r.cavidades,
                'cantidad':      float(r.cantidad or 0),
                'estado':        (r.estado or 'PENDIENTE').upper()
            })

        return jsonify(data), 200
    except Exception as e:
        logger.error(f"âŒ Error en mes_get_programaciones SQL: {e}")
        return jsonify([]), 200


@app.route('/api/mes/dashboard', methods=['GET'])
def mes_dashboard():
    """Estado completo de las mÃ¡quinas (MES) consultado desde SQL."""
    try:
        from backend.models.sql_models import ProduccionInyeccion, ProgramacionInyeccion, Maquina
        
        # 1. Obtener mÃ¡quinas activas
        maquinas_sql = db.session.query(Maquina).filter(Maquina.activa == True).all()
        maquinas_set = [m.nombre for m in maquinas_sql]
        if not maquinas_set:
            maquinas_set = ['MAQUINA No.1', 'MAQUINA No.2', 'MAQUINA No.3', 'MAQUINA No.4']

        # 2. Consultar registros En Proceso y Programados
        en_proceso = db.session.query(ProduccionInyeccion).filter(ProduccionInyeccion.estado == 'EN_PROCESO').all()
        programaciones = db.session.query(ProgramacionInyeccion).filter(ProgramacionInyeccion.estado == 'PROGRAMADO').all()

        resultado = []
        for maquina_nom in maquinas_set:
            maquina_upper = maquina_nom.upper()
            activos_maq = [r for r in en_proceso if (r.maquina or '').upper() == maquina_upper]
            
            trabajo_activo = None
            estado_maquina = 'LIBRE'
            
            if activos_maq:
                primer = activos_maq[0]
                trabajo_activo = {
                    'id_inyeccion':       primer.id_inyeccion,
                    'molde':              primer.molde,
                    'hora_inicio':        primer.fecha_inicia.strftime('%H:%M') if primer.fecha_inicia else '',
                    'productos_activos': [
                        {
                            'codigo_sistema': r.id_codigo,
                            'cavidades':      r.cavidades
                        } for r in activos_maq
                    ]
                }
                estado_maquina = 'EN_PROCESO'

            # Construir cola (simplificado segÃºn ProgramacionInyeccion)
            cola = [
                {
                    'id_programacion': r.id,
                    'codigo_sistema':  r.codigo_sistema,
                    'molde':           r.molde,
                    'cavidades':       r.cavidades,
                    'cantidad':        float(r.cantidad or 0)
                }
                for r in programaciones if (r.maquina or '').upper() == maquina_upper
            ]

            if cola and estado_maquina == 'LIBRE':
                estado_maquina = 'PROGRAMADO'

            resultado.append({
                'nombre':         maquina_nom,
                'estado':         estado_maquina,
                'trabajo_activo': trabajo_activo,
                'cola':           cola
            })

        return jsonify({'maquinas': resultado}), 200

    except Exception as e:
        logger.error(f"âŒ Error en mes_dashboard SQL: {e}")
        return jsonify({'maquinas': []}), 200

@app.route('/api/mes/pendientes_calidad', methods=['GET'])
def mes_get_pendientes_calidad():
    """Obtiene registros de inyección en estado PENDIENTE_CALIDAD desde SQL."""
    try:
        from backend.models.sql_models import ProduccionInyeccion
        
        # Consulta SQL-Native filtrando por estado
        pendientes_sql = ProduccionInyeccion.query.filter(
            ProduccionInyeccion.estado.ilike('PENDIENTE_CALIDAD')
        ).all()
        
        # Mapeo a formato esperado por el frontend (Traductor Manual para MES)
        resultado = []
        for r in pendientes_sql:
            resultado.append({
                'ID INYECCION': r.id_inyeccion,
                'FECHA': r.fecha_inicia.strftime('%Y-%m-%d') if r.fecha_inicia else '',
                'RESPONSABLE': r.responsable,
                'ID CODIGO': r.id_codigo,
                'CANTIDAD REAL': float(r.cantidad_real or 0),
                'MAQUINA': r.maquina,
                'ESTADO': r.estado
            })
            
        return jsonify(resultado), 200
    except Exception as e:
        import traceback
        logger.error(f"Error en mes_get_pendientes_calidad SQL: {e}\n{traceback.format_exc()}")
        return jsonify([]), 200


@app.route('/api/mes/programacion/<id_prog>/productos', methods=['GET'])
def mes_get_productos_programacion(id_prog):
    """Obtener productos vinculados a una programación desde SQL."""
    try:
        from backend.models.sql_models import ProgramacionInyeccion
        
        # Consultar por ID primario en la tabla db_programacion
        prog = ProgramacionInyeccion.query.get(id_prog)
        
        if not prog:
            return jsonify({'success': False, 'error': 'No se encontró la programación'}), 404
            
        return jsonify({
            'success': True,
            'productos': [{
                'codigo': prog.codigo_sistema,
                'cavidades': int(prog.cavidades or 1),
                'molde': str(prog.molde or '')
            }]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching productos de programacion SQL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/mes/status/<maquina>', methods=['GET'])
def mes_get_status_maquina(maquina):
    """Obtiene el estado actual de una máquina (Activo, Programado o Libre) usando SQL."""
    try:
        from backend.models.sql_models import ProduccionInyeccion, ProgramacionInyeccion
        maquina_upper = str(maquina).strip().upper()
        
        # 1. Buscar en INYECCION si hay algo EN_PROCESO
        activo = db.session.query(ProduccionInyeccion).filter(
            ProduccionInyeccion.maquina == maquina_upper,
            ProduccionInyeccion.estado == 'EN_PROCESO'
        ).first()
        
        if activo:
            return jsonify({
                'estado': 'EN_PROCESO',
                'id_inyeccion': activo.id_inyeccion,
                'id_programacion': activo.id_inyeccion,
                'producto': activo.id_codigo,
                'molde': str(activo.molde or ''),
                'cavidades': int(activo.cavidades or 1),
                'inicio': activo.fecha_inicia.strftime('%H:%M') if activo.fecha_inicia else '',
                'teorica': 0
            }), 200
            
        # 2. Si no hay activo, buscar en PROGRAMACION_INYECCION el siguiente PROGRAMADO
        programado = db.session.query(ProgramacionInyeccion).filter(
            ProgramacionInyeccion.maquina == maquina_upper,
            ProgramacionInyeccion.estado == 'PROGRAMADO'
        ).first()
        
        if programado:
             return jsonify({
                'estado': 'PROGRAMADO',
                'id_programacion': programado.id,
                'producto': programado.codigo_sistema,
                'molde': str(programado.molde or ''),
                'cavidades': int(programado.cavidades or 1)
            }), 200
            
        return jsonify({'estado': 'LIBRE'}), 200
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Error en status_maquina: {e}\n{error_detail}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': error_detail
        }), 500

@app.route('/api/mes/iniciar', methods=['POST'])
def mes_iniciar():
    """Fase 2a: Operario inicia fÃ­sicamente la mÃ¡quina. Inicia TODO lo programado para esa mÃ¡quina (Batch)."""
    try:
        from backend.models.sql_models import ProduccionInyeccion, ProgramacionInyeccion
        data = request.json
        id_prog_trigger = data.get('id_programacion')
        operario = data.get('operario', 'OPERARIO')

        prog_trigger = db.session.get(ProgramacionInyeccion, id_prog_trigger)
        if not prog_trigger:
            return jsonify({'success': False, 'error': 'ProgramaciÃ³n base no encontrada'}), 404
            
        maquina_nom = prog_trigger.maquina
        
        # 2. Buscar TODOS los SKUs programados para esa mÃ¡quina que no estÃ©n cancelados ni terminados
        progs_en_cola = db.session.query(ProgramacionInyeccion).filter(
            ProgramacionInyeccion.maquina == maquina_nom,
            ProgramacionInyeccion.estado == 'PROGRAMADO'
        ).all()

        if not progs_en_cola:
            return jsonify({'success': False, 'error': f'No hay programaciones cargadas para {maquina_nom}'}), 400

        # 3. Crear registros de ProducciÃ³n compartiendo el mismo ID_INYECCION (Batch ID)
        id_inyeccion = f"INY-{str(uuid.uuid4())[:8].upper()}"
        colombia_tz = pytz.timezone('America/Bogota')
        ahora = datetime.now(colombia_tz)
        
        for p in progs_en_cola:
            nueva_prod = ProduccionInyeccion(
                id_inyeccion=id_inyeccion,
                fecha_inicia=ahora,
                id_codigo=p.codigo_sistema,
                responsable=operario,
                maquina=p.maquina,
                molde=p.molde,
                cavidades=p.cavidades,
                estado='EN_PROCESO'
            )
            db.session.add(nueva_prod)
            
            # Marcar programaciÃ³n como EN_PROCESO
            p.estado = 'EN_PROCESO'
        
        db.session.commit()
        clear_mes_cache()

        return jsonify({'success': True, 'id_inyeccion': id_inyeccion, 'count': len(progs_en_cola)}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"âŒ Error en mes_iniciar Batch SQL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en mes_iniciar SQL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/mes/reportar', methods=['POST'])
def mes_reportar():
    """Fase 2b: Operario finaliza el turno. Reporta TODOS los SKUs del mismo Batch (id_inyeccion)."""
    try:
        from backend.models.sql_models import ProduccionInyeccion, ProgramacionInyeccion
        from backend.core.sql_database import db

        data = request.json
        id_iny = data.get('id_inyeccion')
        cierres = int(data.get('cierres', 0))
        
        # 1. Buscar TODOS los registros bajo este ID de inyección
        prods_en_lote = db.session.query(ProduccionInyeccion).filter(ProduccionInyeccion.id_inyeccion == id_iny).all()
        if not prods_en_lote:
            return jsonify({'success': False, 'error': 'Batch de producción no encontrado'}), 404
            
        # 2. Actualizar cada registro del Batch
        for prod in prods_en_lote:
            # Sincronizar Horas Reales (si vienen del modal)
            if hi_str and prod.fecha_inicia:
                try:
                    h, m = map(int, hi_str.split(':'))
                    prod.fecha_inicia = prod.fecha_inicia.replace(hour=h, minute=m, second=0)
                except: pass
                
            if hf_str and prod.fecha_inicia:
                try:
                    h, m = map(int, hf_str.split(':'))
                    # Usamos la misma fecha base del inicio para el fin (Batch del día)
                    prod.fecha_fin = prod.fecha_inicia.replace(hour=h, minute=m, second=0)
                except: pass

            prod.cantidad_real = cierres * (prod.cavidades or 1)
            prod.estado = 'PENDIENTE'
            
            # Finalizar Programación asociada para este código en esta máquina (Uso de orden_produccion)
            db.session.query(ProgramacionInyeccion).filter(
                ProgramacionInyeccion.codigo_sistema == prod.id_codigo,
                ProgramacionInyeccion.maquina == prod.maquina,
                ProgramacionInyeccion.estado == 'EN_PROCESO'
            ).update({ 'estado': 'COMPLETADO' })
            
        db.session.commit()
        clear_mes_cache()
        return jsonify({'success': True, 'count': len(prods_en_lote)}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en mes_reportar Batch SQL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500




@app.route('/api/mes/pendientes_validacion', methods=['GET'])
def mes_pendientes_validacion():
    """Obtiene todos los lotes en estado PENDIENTE desde SQL para validación."""
    try:
        # Consulta robusta 100% SQL para evitar problemas de metadatos de SQLAlchemy
        from sqlalchemy import text
        sql = """
            SELECT 
                i.id, i.id_inyeccion, i.fecha_inicia as fecha, i.fecha_fin as fecha_fin, 
                i.id_codigo, i.responsable, i.maquina, i.molde, i.cavidades, 
                i.estado, i.cantidad_real,
                i.hora_inicio, i.hora_termina,
                i.cant_contador, i.almacen_destino, i.orden_produccion,
                i.observaciones, i.pnc_total,
                i.pnc_detalle, i.peso_lote,
                i.entrada, i.salida,
                COALESCE(pnc.total_pnc, 0) as total_pnc_sql
            FROM db_inyeccion i
            LEFT JOIN (
                SELECT id_inyeccion, id_codigo,
                       SUM(COALESCE(NULLIF(regexp_replace(cantidad::text, '[^0-9.]', '', 'g'), ''), '0')::NUMERIC) as total_pnc
                FROM db_pnc_inyeccion
                GROUP BY id_inyeccion, id_codigo
            ) pnc ON i.id_inyeccion = pnc.id_inyeccion AND i.id_codigo = pnc.id_codigo
            WHERE i.estado = 'PENDIENTE'
        """
        pendientes = db.session.execute(text(sql)).mappings().all()

        # 2. Formatear para el frontend (resistente a basura)
        data = []
        import re
        def _clean_num(val):
            if val is None: return 0
            if isinstance(val, (int, float)): return val
            clean = re.sub(r'[^0-9.]', '', str(val))
            return float(clean) if clean else 0

        for p in pendientes:
            data.append({
                'id_sql': p['id'],
                'id_inyeccion': p['id_inyeccion'],
                'fecha': p['fecha'].isoformat() if p['fecha'] else '',
                'hora_inicio': p['hora_inicio'] or (p['fecha'].strftime('%H:%M') if p['fecha'] else ''),
                'hora_fin': p['hora_termina'] or (p['fecha_fin'].strftime('%H:%M') if p.get('fecha_fin') else ''),
                'id_codigo': p['id_codigo'], 
                'responsable': p['responsable'],
                'cantidad_real': _clean_num(p['cantidad_real']),
                'pnc': _clean_num(p['pnc_total'] or p['total_pnc_sql']),
                'maquina': p['maquina'],
                'molde': p['molde'],
                'cavidades': p['cavidades'],
                'cant_contador': _clean_num(p['cant_contador']),
                'almacen_destino': p['almacen_destino'],
                'orden_produccion': p['orden_produccion'],
                'observaciones': p['observaciones'],
                'pnc_detalle': p['pnc_detalle'],
                'entrada': _clean_num(p['entrada']),
                'salida': _clean_num(p['salida']),
                'peso_lote': _clean_num(p['peso_lote'])
            })

        return jsonify({'success': True, 'data': data}), 200

    except Exception as e:
        logger.error(f"❌ Error en mes_pendientes_validacion SQL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ====================================================================
# NUEVO FLUJO PERSISTENTE: PULIDO (MES)
# ====================================================================

# ==============================================================================
# PULIDO - LOGICA DE PAUSAS Y TIEMPOS EFECTIVOS
# ==============================================================================
PAUSAS_FIJAS_FRIPARTS = [
    {"nombre": "Pausa Activa 1", "inicio": "07:00", "fin": "07:05", "minutos": 5},
    {"nombre": "Desayuno",        "inicio": "09:00", "fin": "09:15", "minutos": 15},
    {"nombre": "Pausa Activa 2", "inicio": "11:00", "fin": "11:05", "minutos": 5},
    {"nombre": "Almuerzo",        "inicio": "12:30", "fin": "13:15", "minutos": 45},
    {"nombre": "Pausa Activa 3", "inicio": "15:00", "fin": "15:05", "minutos": 5},
]

def calcular_minutos_pausas_fijas(inicio_trabajo, fin_trabajo):
    """Calcula cuántos minutos de pausas fijas de Friparts se cruzaron con el horario de trabajo."""
    try:
        if not inicio_trabajo or not fin_trabajo: return 0, []
        

        
        # Blindaje: convertir string a datetime si es necesario
        if isinstance(inicio_trabajo, str):
            try:
                if 'T' in inicio_trabajo:
                    inicio_trabajo = datetime.fromisoformat(inicio_trabajo)
                else:
                    inicio_trabajo = datetime.strptime(inicio_trabajo[:19], '%Y-%m-%d %H:%M:%S')
            except Exception as e:
                logger.error(f"Error parseando inicio_trabajo '{inicio_trabajo}': {e}")
                return 0, []
                
        if isinstance(fin_trabajo, str):
            try:
                if 'T' in fin_trabajo:
                    fin_trabajo = datetime.fromisoformat(fin_trabajo)
                else:
                    fin_trabajo = datetime.strptime(fin_trabajo[:19], '%Y-%m-%d %H:%M:%S')
            except Exception as e:
                logger.error(f"Error parseando fin_trabajo '{fin_trabajo}': {e}")
                fin_trabajo = datetime.now()

        # Extraer la fecha para reconstruir las pausas del día
        if hasattr(inicio_trabajo, 'date'):
            fecha_ref = inicio_trabajo.date()
        elif isinstance(inicio_trabajo, date):
            fecha_ref = inicio_trabajo
        else:
            fecha_ref = date.today()

        total_minutos_pausa = 0
        detalles = []
        
        for pausa in PAUSAS_FIJAS_FRIPARTS:
            try:
                # Reconstruir datetimes para la pausa en el día del trabajo
                h_ini, m_ini = map(int, pausa["inicio"].split(':'))
                h_fin, m_fin = map(int, pausa["fin"].split(':'))
                
                pausa_inicio = datetime.combine(fecha_ref, time(h_ini, m_ini))
                pausa_fin    = datetime.combine(fecha_ref, time(h_fin, m_fin))
                
                # Intersección de rangos: max(inicio) a min(fin)
                # Asegurar que ambos son datetime antes de max/min
                if not isinstance(inicio_trabajo, datetime): 
                    # Si es solo fecha, convertir a inicio del día
                    inicio_dt = datetime.combine(inicio_trabajo, time(0,0))
                else:
                    inicio_dt = inicio_trabajo
                    
                if not isinstance(fin_trabajo, datetime):
                    fin_dt = datetime.combine(fin_trabajo, time(23,59,59))
                else:
                    fin_dt = fin_trabajo

                start_inter = max(inicio_dt, pausa_inicio)
                end_inter   = min(fin_dt, pausa_fin)
                
                if start_inter < end_inter:
                    m = int((end_inter - start_inter).total_seconds() / 60)
                    if m > 0:
                        total_minutos_pausa += m
                        detalles.append({"nombre": pausa["nombre"], "minutos": m})
            except Exception as e_p:
                logger.error(f"Error procesando pausa {pausa.get('nombre')}: {e_p}")
                
        return total_minutos_pausa, detalles
    except Exception as e_global:
        logger.error(f"Error global en calcular_minutos_pausas_fijas: {e_global}")
        return 0, []

@app.route('/api/mes/pulido/estado', methods=['GET'])
def get_pulido_estado():
    """Retorna TODOS los trabajos abiertos o pausados de un operario (Multitasking)."""
    try:
        from backend.models.sql_models import ProduccionPulido
        responsable = request.args.get('responsable')
        if not responsable:
            return jsonify({'en_curso': False, 'lista': []})

        # Buscar todos los que no estÃ©n FINALIZADOS
        trabajos = db.session.query(ProduccionPulido).filter(
            ProduccionPulido.responsable == responsable,
            ProduccionPulido.estado.in_(['EN_PROCESO', 'PAUSADO'])
        ).order_by(ProduccionPulido.id.desc()).all()

        if not trabajos:
            return jsonify({'en_curso': False, 'lista': []})

        lista_final = []
        for t in trabajos:
            # Blindaje hora inicio
            hora_str = "--:--"
            if t.hora_inicio:
                try:
                    hora_str = t.hora_inicio.strftime('%H:%M') if hasattr(t.hora_inicio, 'strftime') else str(t.hora_inicio)[11:16]
                except: pass

            lista_final.append({
                'id': t.id,
                'producto': t.codigo,
                'hora_inicio': hora_str,
                'estado': t.estado
            })

        return jsonify({
            'en_curso': any(t.estado == 'EN_PROCESO' for t in trabajos),
            'lista': lista_final,
            'datos': lista_final[0] # Retrocompatibilidad UI actual
        }), 200

    except Exception as e:
        logger.error(f"Error en get_pulido_estado: {e}")
        return jsonify({'en_curso': False, 'error': str(e)}), 500

@app.route('/api/mes/pulido/iniciar', methods=['POST'])
def iniciar_pulido():
    """Inicia un nuevo registro de trabajo en Pulido."""
    try:
        from backend.models.sql_models import ProduccionPulido, PausasPulido
        from backend.utils.formatters import normalizar_codigo
        import uuid
        
        data = request.json
        responsable = data.get('responsable')
        producto_raw = data.get('producto')
        
        if not responsable or not producto_raw:
            return jsonify({'success': False, 'error': 'Falta responsable o producto'}), 400

        codigo_sistema = normalizar_codigo(producto_raw)
        
        # Generar hora actual HH:MM
        ahora = datetime.now()
        fecha_actual = ahora.date()
        
        # 1. AUTO-PAUSA: Si ya tiene un trabajo EN_PROCESO, pausarlo automÃ¡ticamente
        trabajo_activo = db.session.query(ProduccionPulido).filter_by(
            responsable=responsable, estado='EN_PROCESO'
        ).first()

        if trabajo_activo:
            trabajo_activo.estado = 'PAUSADO'
            # Registrar pausa automÃ¡tica
            pausa_auto = PausasPulido(
                id_pulido=trabajo_activo.id,
                motivo='Multitarea (NUEVO TRABAJO)',
                hora_inicio=ahora
            )
            db.session.add(pausa_auto)
            logger.info(f"â¸ï¸ AUTO-PAUSA por multitasking: {trabajo_activo.codigo}")

        # 2. Iniciar el nuevo
        hora_inicio_str = ahora.strftime('%H:%M')
        nuevo_trabajo = ProduccionPulido(
            id_pulido=f"PUL-{uuid.uuid4().hex[:8].upper()}",
            fecha=fecha_actual,
            codigo=codigo_sistema,
            responsable=responsable,
            hora_inicio=ahora,
            estado='EN_PROCESO'
        )
        
        db.session.add(nuevo_trabajo)
        db.session.commit()
        
        logger.info(f"âœ… Trabajo de pulido iniciado: {codigo_sistema} por {responsable}")
        
        return jsonify({
            'success': True,
            'mensaje': 'Trabajo iniciado correctamente',
            'id': nuevo_trabajo.id,
            'hora_inicio': hora_inicio_str
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"âŒ Error en iniciar_pulido: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mes/pulido/finalizar', methods=['POST'])
def finalizar_pulido():
    """Cierra el registro de pulido, calcula mermas y actualiza inventario SQL."""
    try:
        from backend.models.sql_models import ProduccionPulido, Producto, PausasPulido
        from backend.utils.formatters import normalizar_codigo
        
        data = request.json
        responsable = data.get('responsable')
        producto_raw = data.get('producto')
        total_canastilla = float(data.get('total_canastilla', 0))
        pnc_i = float(data.get('pnc_inyeccion', 0)) 
        
        # NUEVO: Manejo de PNC Multiple
        defectos_pulido = data.get('defectos_pulido', []) # List of {motivo, cantidad}
        if defectos_pulido:
            pnc_p = sum(float(d.get('cantidad', 0)) for d in defectos_pulido)
        else:
            pnc_p = float(data.get('pnc_pulido', 0))   # Fallback compatibilidad

        orden_produccion = data.get('orden_produccion', '')
        observaciones = data.get('observaciones', '')
        
        if not responsable or not producto_raw:
            return jsonify({'success': False, 'error': 'Falta responsable o producto'}), 400

        codigo_sistema = normalizar_codigo(producto_raw)
        
        # 1. Buscar el registro activo
        trabajo = db.session.query(ProduccionPulido).filter(
            ProduccionPulido.responsable == responsable,
            ProduccionPulido.codigo == codigo_sistema,
            ProduccionPulido.estado == 'EN_PROCESO'
        ).order_by(ProduccionPulido.id.desc()).first()

        if not trabajo:
            return jsonify({'success': False, 'error': 'No se encontrÃ³ un trabajo activo para este producto'}), 404

        # 2. Actualizar Tiempos y Estado
        ahora = datetime.now()
        trabajo.hora_fin = ahora
        trabajo.estado = 'FINALIZADO'
        trabajo.cantidad_real = total_canastilla
        
        # Procesar Defectos de InyecciÃ³n
        def_iny = data.get('defectos_inyeccion', [])
        pnc_i = sum(float(d.get('cantidad', 0)) for d in def_iny)
        trabajo.pnc_inyeccion = int(pnc_i)

        # Procesar Defectos de Pulido
        def_pul = data.get('defectos_pulido', [])
        pnc_p = sum(float(d.get('cantidad', 0)) for d in def_pul)
        trabajo.pnc_pulido = int(pnc_p)

        trabajo.orden_produccion = orden_produccion
        trabajo.observaciones = observaciones
        
        # --- CÃ¡lculo de Tiempos Avanzado ---
        try:
            # Blindaje: asegurar que hora_inicio es datetime
            inicio_t = trabajo.hora_inicio
            if isinstance(inicio_t, str):
                try:
                    if 'T' in inicio_t:
                        inicio_t = datetime.fromisoformat(inicio_t)
                    else:
                        inicio_t = datetime.strptime(inicio_t[:19], '%Y-%m-%d %H:%M:%S')
                except Exception as ex:
                    logger.error(f"Error parseando hora_inicio en finalizar: {ex}")
                    inicio_t = ahora
            
            # DuraciÃ³n Bruta (minutos)
            diff_bruta = ahora - inicio_t
            minutos_brutos = int(diff_bruta.total_seconds() / 60)
            
            # 1. Sumar Pausas Manuales
            pausas_manuales = db.session.query(PausasPulido).filter_by(id_pulido=trabajo.id).all()
            total_manuales_min = 0
            for p in pausas_manuales:
                if p.hora_inicio and p.hora_fin:
                    diff_p = p.hora_fin - p.hora_inicio
                    total_manuales_min += int(diff_p.total_seconds() / 60)
            
            # 2. Calcular Pausas Fijas AutomÃ¡ticas (Devuelve minutos, detalles)
            total_fijas_min, _ = calcular_minutos_pausas_fijas(trabajo.hora_inicio, ahora)
            
            # 3. TIEMPO EFECTIVO FINAL
            trabajo.tiempo_total_minutos = max(0, minutos_brutos - total_manuales_min - total_fijas_min)
            
            logger.info(f"â±ï¸ TIEMPOS: Bruto={minutos_brutos}m, Manuales={total_manuales_min}m, Fijas={total_fijas_min}m. Efectivo={trabajo.tiempo_total_minutos}m")
        except Exception as e_time:
            logger.error(f"Error calculando tiempos de pulido: {e_time}")
            trabajo.tiempo_total_minutos = 0
        
        # 3. ACTUALIZACIÃ“N DE INVENTARIO (SQL-Native)
        producto_inv = db.session.query(Producto).filter_by(codigo_sistema=codigo_sistema).first()
        if producto_inv:
            # Descontar de Por Pulir
            original_por_pulir = float(producto_inv.por_pulir or 0)
            producto_inv.por_pulir = max(0, original_por_pulir - total_canastilla)
            
            # Sumar a Terminado (Solo las piezas buenas)
            buenas = total_canastilla - pnc_i - pnc_p
            original_terminado = float(producto_inv.p_terminado or 0)
            producto_inv.p_terminado = original_terminado + buenas
            
            logger.info(f"ðŸ“¦ [INVENTARIO UPD] {codigo_sistema}: Pulido -> Terminado (+{buenas})")
        
        # 4. Registrar Detalles de PNC Dual
        if def_iny:
            for d in def_iny:
                registrar_pnc_detalle(
                    tipo_proceso="inyeccion", # Se marca como inyecciÃ³n aunque se detectÃ³ en pulido
                    id_operacion=trabajo.id,
                    codigo_producto=codigo_sistema,
                    cantidad_pnc=float(d.get('cantidad', 0)),
                    criterio_pnc=d.get('motivo', 'Falta Material'),
                    observaciones=f"Auditado en Pulido - {observaciones}"
                )
        
        if def_pul:
            for d in def_pul:
                registrar_pnc_detalle(
                    tipo_proceso="pulido",
                    id_operacion=trabajo.id,
                    codigo_producto=codigo_sistema,
                    cantidad_pnc=float(d.get('cantidad', 0)),
                    criterio_pnc=d.get('motivo', 'Mal Pulido'),
                    observaciones=f"Reporte Pulido - {observaciones}"
                )
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje': 'Reporte finalizado y stock actualizado',
            'buenas': trabajo.cantidad_real,
            'tiempo_efectivo': trabajo.tiempo_total_minutos
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"âŒ Error en finalizar_pulido: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mes/pulido/pausar', methods=['POST'])
def pausar_pulido():
    """Registra una pausa manual en el flujo de pulido."""
    try:
        from backend.models.sql_models import ProduccionPulido, PausasPulido

        
        data = request.json
        responsable = data.get('responsable')
        motivo = data.get('motivo', 'Otras')
        
        if not responsable:
            return jsonify({'success': False, 'error': 'Falta responsable'}), 400

        # 1. Buscar trabajo activo
        trabajo = db.session.query(ProduccionPulido).filter(
            ProduccionPulido.responsable == responsable,
            ProduccionPulido.estado == 'EN_PROCESO'
        ).order_by(ProduccionPulido.id.desc()).first()

        if not trabajo:
            return jsonify({'success': False, 'error': 'No hay un trabajo activo para pausar'}), 404

        # 2. Cambiar estado a PAUSADO
        trabajo.estado = 'PAUSADO'
        
        # 3. Registrar en tabla de pausas
        ahora = datetime.datetime.now()
        nueva_pausa = PausasPulido(
            id_pulido=trabajo.id,
            motivo=motivo,
            hora_inicio=ahora
        )
        
        db.session.add(nueva_pausa)
        db.session.commit()
        
        logger.info(f"⏸️ TRABAJO PAUSADO: {trabajo.codigo} por {responsable} (Motivo: {motivo})")
        
        return jsonify({'success': True, 'mensaje': 'Trabajo pausado correctamente'}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en pausar_pulido: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mes/pulido/reanudar', methods=['POST'])
def reanudar_pulido():
    """Finaliza una pausa y vuelve a poner el trabajo en proceso con soporte multitarea."""
    try:
        from backend.models.sql_models import ProduccionPulido, PausasPulido

        ahora = datetime.datetime.now()
        
        data = request.json
        responsable = data.get('responsable')
        if not responsable:
            return jsonify({'success': False, 'error': 'Falta responsable'}), 400

        id_fuerte = data.get('id') or data.get('id_trabajo')
        
        # 1. Pausar automáticamente cualquier otro trabajo que esté actualmente EN_PROCESO
        trabajos_activos = db.session.query(ProduccionPulido).filter(
            ProduccionPulido.responsable == responsable,
            ProduccionPulido.estado == 'EN_PROCESO',
            ProduccionPulido.id != id_fuerte
        ).all()
        
        for t_activo in trabajos_activos:
            t_activo.estado = 'PAUSADO'
            nueva_pausa = PausasPulido(
                id_pulido=t_activo.id,
                motivo='Reemplazo de Tarea (Auto)',
                hora_inicio=ahora
            )
            db.session.add(nueva_pausa)
            logger.info(f"⏸️ Auto-Pausa: {t_activo.codigo} (Operario: {responsable})")

        # 2. Buscar y activar el trabajo solicitado
        if id_fuerte:
            trabajo = db.session.query(ProduccionPulido).filter_by(id=id_fuerte, responsable=responsable).first()
        else:
            trabajo = db.session.query(ProduccionPulido).filter_by(responsable=responsable, estado='PAUSADO').order_by(ProduccionPulido.id.desc()).first()

        if not trabajo:
            return jsonify({'success': False, 'error': 'No se encontró el trabajo para reanudar'}), 404

        # 3. Volver a en curso y finalizar la pausa más reciente
        trabajo.estado = 'EN_PROCESO'
        
        pausa_activa = db.session.query(PausasPulido).filter(
            PausasPulido.id_pulido == trabajo.id,
            PausasPulido.hora_fin == None
        ).order_by(PausasPulido.id.desc()).first()

        if pausa_activa:
            pausa_activa.hora_fin = ahora
            logger.info(f"▶️ TRABAJO REANUDADO: {trabajo.codigo} (ID: {trabajo.id})")
        
        db.session.commit()
        
        hora_str = trabajo.hora_inicio.strftime('%H:%M') if hasattr(trabajo.hora_inicio, 'strftime') else str(trabajo.hora_inicio)[:16]

        return jsonify({
            'success': True, 
            'mensaje': 'Trabajo reanudado con éxito',
            'hora_inicio': hora_str,
            'id': trabajo.id
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en reanudar_pulido: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mes/pulido/resumen_pausas', methods=['GET'])
def get_resumen_pausas():
    """Retorna el detalle de las pausas para un trabajo específico."""
    try:
        from backend.models.sql_models import ProduccionPulido, PausasPulido

        
        responsable = request.args.get('responsable')
        id_trabajo = request.args.get('id')
        
        # 1. Buscar el trabajo de referencia
        trabajo = None
        if id_trabajo:
            trabajo = db.session.query(ProduccionPulido).filter_by(id=id_trabajo).first()
        else:
            trabajo = db.session.query(ProduccionPulido).filter(
                ProduccionPulido.responsable == responsable,
                ProduccionPulido.estado.in_(['EN_PROCESO', 'PAUSADO'])
            ).order_by(ProduccionPulido.id.desc()).first()

        # REGLA DE ORO: Si no hay trabajo, 404
        if not trabajo:
            return jsonify({'success': False, 'error': 'No se encontró el trabajo activo'}), 404

        # 2. Consultar Pausas Manuales
        pausas_db = db.session.query(PausasPulido).filter_by(id_pulido=trabajo.id).all()
        resumen_manuales = []
        total_manuales = 0
        for p in pausas_db:
            if p.hora_inicio and p.hora_fin:
                dur = int((p.hora_fin - p.hora_inicio).total_seconds() / 60)
                resumen_manuales.append({'motivo': p.motivo, 'duracion': dur})
                total_manuales += dur
        
        # 3. Calcular Pausas Fijas AutomÃ¡ticas
        ahora = datetime.now()
        total_fijas, detalles_fijas = calcular_minutos_pausas_fijas(trabajo.hora_inicio, ahora)
        
        return jsonify({
            'success': True,
            'pausas_manuales': resumen_manuales,
            'total_manuales_min': total_manuales,
            'total_fijas_min': total_fijas,
            'pausas_fijas_detalle': detalles_fijas,
            'orden_produccion': trabajo.orden_produccion or ''
        }), 200

    except Exception as e:
        logger.error(f"âŒ Error en get_resumen_pausas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def registrar_pnc_detalle(tipo_proceso, id_operacion, codigo_producto, cantidad_pnc, criterio_pnc, observaciones=""):
    """
    Helper para registrar PNC en las tablas específicas de producción.
    Diferencia entre pnc_inyeccion (usa id_codigo) y pnc_pulido (usa codigo).
    """
    try:
        import uuid
        tipo = str(tipo_proceso).lower()
        pk_id = uuid.uuid4().hex[:8] # Hexadecimal de 8 caracteres (DBeaver)
        
        if tipo == 'inyeccion':
            from backend.models.sql_models import PncInyeccion
            nueva_pnc = PncInyeccion(
                id_pnc_inyeccion=pk_id,
                id_inyeccion=str(id_operacion),
                id_codigo=codigo_producto,
                cantidad=cantidad_pnc,
                criterio=f"{criterio_pnc} - {observaciones}".strip(' -'),
                codigo_ensamble="AUDITORIA PULIDO"
            )
        elif tipo == 'pulido':
            from backend.models.sql_models import PncPulido
            nueva_pnc = PncPulido(
                id_pnc_pulido=pk_id,
                id_pulido=str(id_operacion),
                codigo=codigo_producto,
                cantidad=cantidad_pnc,
                criterio=f"{criterio_pnc} - {observaciones}".strip(' -'),
                codigo_ensamble="AUDITORIA PULIDO"
            )
        elif tipo == 'ensamble':
            from backend.models.sql_models import PncEnsamble
            nueva_pnc = PncEnsamble(
                id_pnc_ensamble=pk_id,
                id_ensamble=str(id_operacion),
                id_codigo=codigo_producto,
                cantidad=cantidad_pnc,
                criterio=f"{criterio_pnc} - {observaciones}".strip(' -'),
                codigo_ensamble="AUDITORIA PULIDO"
            )
        else:
            logger.warning(f"⚠️ Proceso desconocido para PNC: {tipo}")
            return False

        db.session.add(nueva_pnc)
        logger.info(f"✅ [PNC {tipo.upper()}] Preparado registro {pk_id} para {codigo_producto}")
        return True
    except Exception as e:
        logger.error(f"❌ Error en registrar_pnc_detalle ({tipo_proceso}): {e}")
        return False

@app.route('/api/producto/<codigo>', methods=['GET'])
def obtener_producto(codigo):
    """Obtiene informacion del producto incluyendo codigo ensamble"""
    try:
        logger.debug(f" Buscando producto: {codigo}")
        
        # Normalizar codigo (quitar FR- si lo tiene)
        codigo_limpio = codigo.replace('FR-', '').strip()
        
        # Usar funcion existente para buscar producto
        resultado = buscar_producto_en_inventario(codigo_limpio)
        
        if resultado.get('encontrado'):
            datos = resultado.get('datos', {})
            codigo_ensamble = str(datos.get('CODIGO ENSAMBLE', '')).strip()
            codigo_sistema = str(datos.get('CODIGO SISTEMA', '')).strip()
            
            logger.info(f" Producto encontrado: {codigo_sistema} -> Ensamble: {codigo_ensamble}")
            
            return jsonify({
                'codigoSistema': codigo_sistema,
                'codigoEnsamble': codigo_ensamble
            }), 200
        else:
            logger.warning(f" Producto no encontrado: {codigo}")
            return jsonify({'error': 'Producto no encontrado'}), 404
        
    except Exception as e:
        logger.error(f" Error en obtener_producto: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/inyeccion/ensamble_desde_producto', methods=['GET'])
def obtener_ensamble_desde_producto():
    """Dado un código de producto, retorna su BOM completo desde NUEVA_FICHA_MAESTRA."""
    try:
        codigo_entrada = request.args.get('codigo', '').strip()
        if not codigo_entrada:
            return jsonify({'success': False, 'error': 'Codigo producto requerido'}), 400
        
        from backend.services.bom_service import calcular_descuentos_ensamble
        codigo_sistema = normalizar_codigo(codigo_entrada)
        bom_res = calcular_descuentos_ensamble(codigo_sistema, 1)

        if bom_res.get('success'):
            componentes_bom = bom_res['componentes']
            opcion = {
                'codigo_ensamble': codigo_entrada,
                'buje_origen': codigo_sistema,
                'qty': componentes_bom[0].get('cantidad_por_kit', 1) if componentes_bom else 1,
                'tipo': 'producto',
                'componentes': [
                    {'buje_origen': c['codigo_inventario'], 'qty': c['cantidad_por_kit']} for c in componentes_bom
                ]
            }
            return jsonify({'success': True, 'codigo_sistema': codigo_sistema, 'opciones': [opcion]}), 200
        return jsonify({'success': True, 'codigo_sistema': codigo_sistema, 'opciones': []}), 200
    except Exception as e:
        logger.error(f" Error en obtener_ensamble_desde_producto: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ensamble/finalizar', methods=['POST'])
def finalizar_ensamble():
    """
    Finaliza un ensamble con explosión de materiales (BOM) y descarga de inventario (Fases 1-5).
    """
    try:
        from backend.models.sql_models import Ensamble, PncEnsamble
        from backend.services.bom_service import calcular_descuentos_ensamble
        import uuid

        import pytz
        colombia_tz = pytz.timezone('America/Bogota')
        ahora = datetime.datetime.now(colombia_tz)
        
        data = request.json
        id_codigo = data.get('id_codigo', '').strip()
        cantidad = int(data.get('cantidad', 0))
        responsable = data.get('responsable', '').strip()
        defectos = data.get('defectos', []) 
        
        if not id_codigo or cantidad <= 0:
            return jsonify({'success': False, 'error': 'Código y cantidad requeridos'}), 400

        # FASE 1: BOM
        bom_res = calcular_descuentos_ensamble(id_codigo, cantidad)
        if not bom_res.get('success'):
            return jsonify({'success': False, 'error': bom_res.get('error')}), 400

        # FASE 2: Descarga de Inventario (Híbrida por Prefijo)
        almacen_origen = data.get('almacen_origen', 'STOCK_BODEGA')
        for comp in bom_res['componentes']:
            codigo_comp = str(comp['codigo_inventario']).upper()
            
            # REGLA: CAR/INT -> BODEGA | Otros -> P. TERMINADO
            if codigo_comp.startswith('CAR') or codigo_comp.startswith('INT'):
                almacen_a_descontar = 'STOCK_BODEGA'
            else:
                almacen_a_descontar = 'P. TERMINADO'
                
            exito, msg = registrar_salida(codigo_comp, comp['cantidad_total_descontar'], almacen_a_descontar)
            
            if not exito:
                # Mantener By-pass: Solo advertir, no detener.
                logger.warning(f" ⚠️ [HIBRIDO-ENSAMBLE] {msg}")

        # FASE 3: Ensamble (Mapeo completo de columnas SQL)
        id_ensamble_master = data.get('id_ensamble') or uuid.uuid4().hex[:8]
        
        # Obtener datos del primer componente para buje_origen
        primer_comp = bom_res['componentes'][0]['codigo_inventario'] if bom_res.get('componentes') else ''
        consumo_total = sum(float(c['cantidad_total_descontar']) for c in bom_res['componentes']) if bom_res.get('componentes') else 0

        # Registro SQL
        from backend.utils.formatters import normalizar_codigo
        id_codigo_clean = normalizar_codigo(id_codigo)

        # CÁLCULO DE TIEMPOS REALES (Procesar horas del frontend)
        duracion_s = 0
        tiempo_m = 0.0
        s_por_u = 0.0
        dt_inicio = ahora.replace(tzinfo=None)
        dt_fin = ahora.replace(tzinfo=None)

        h_ini = data.get('hora_inicio')
        h_fin = data.get('hora_fin')
        if h_ini and h_fin:
            try:
                hi_h, hi_m = h_ini.split(':')
                hf_h, hf_m = h_fin.split(':')
                dt_inicio = ahora.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0).replace(tzinfo=None)
                dt_fin = ahora.replace(hour=int(hf_h), minute=int(hf_m), second=0, microsecond=0).replace(tzinfo=None)
                
                diff = dt_fin - dt_inicio
                duracion_s = int(diff.total_seconds())
                if duracion_s < 0: duracion_s += 86400  # Cruce de medianoche
                tiempo_m = float(round(duracion_s / 60.0, 2))
                if cantidad > 0:
                    s_por_u = float(round(duracion_s / cantidad, 2))
                logger.info(f"⏱️ [Ensamble] Tiempos: {h_ini}->{h_fin} = {duracion_s}s ({tiempo_m}min)")
            except Exception as e_time:
                logger.warning(f"Error calculando tiempos ensamble: {e_time}")

        # Upsert: Si existe registro previo (de iniciar), actualizar; si no, crear nuevo
        existente = db.session.query(Ensamble).filter_by(id_ensamble=id_ensamble_master).first()
        if existente:
            nuevo_ensamble = existente
            nuevo_ensamble.id_codigo = id_codigo_clean
            nuevo_ensamble.buje_ensamble = id_codigo_clean
            nuevo_ensamble.cantidad = float(cantidad)
            nuevo_ensamble.qty = float(data.get('qty', 1) or 1)
            nuevo_ensamble.responsable = responsable
            nuevo_ensamble.op_numero = data.get('orden_produccion', '')
            nuevo_ensamble.almacen_para_descargar = almacen_origen
            nuevo_ensamble.almacen_destino = data.get('almacen_destino', '')
            nuevo_ensamble.buje_origen = primer_comp
            nuevo_ensamble.consumo_total = float(consumo_total)
            nuevo_ensamble.hora_inicio = dt_inicio
            nuevo_ensamble.hora_fin = dt_fin
            nuevo_ensamble.estado = 'FINALIZADO'
        else:
            nuevo_ensamble = Ensamble(
                id_ensamble=id_ensamble_master,
                id_codigo=id_codigo_clean,
                buje_ensamble=id_codigo_clean, 
                cantidad=float(cantidad),
                qty=float(data.get('qty', 1) or 1),
                responsable=responsable,
                op_numero=data.get('orden_produccion', ''),
                almacen_para_descargar=almacen_origen,
                almacen_destino=data.get('almacen_destino', ''),
                buje_origen=primer_comp,
                consumo_total=float(consumo_total),
                fecha=ahora.date(),
                hora_inicio=dt_inicio,
                hora_fin=dt_fin,
                departamento='Ensamble'
            )
            db.session.add(nuevo_ensamble)

        nuevo_ensamble.duracion_segundos = duracion_s
        nuevo_ensamble.tiempo_total_minutos = tiempo_m
        nuevo_ensamble.segundos_por_unidad = s_por_u

        # FASE 4: Calidad (id_pnc_ensamble TEXT UUID)
        for d in defectos:
            cant_pnc = float(d.get('cantidad', 0))
            if cant_pnc > 0:
                db.session.add(PncEnsamble(
                    id_pnc_ensamble=uuid.uuid4().hex[:8],
                    id_ensamble=id_ensamble_master,
                    id_codigo=id_codigo,
                    cantidad=cant_pnc,
                    criterio=d.get('criterio', 'Defecto Ensamble')
                ))

        # Cargar producto terminado
        registrar_entrada(id_codigo, cantidad, "PRODUCTO TERMINADO")

        # FASE 5: Transacción
        db.session.commit()
        logger.info(f"✅ ENSAMBLE EXITOSO: {id_codigo} (ID: {id_ensamble_master})")
        return jsonify({'success': True, 'id_ensamble': id_ensamble_master}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en finalizar_ensamble: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/pulido', methods=['POST'])
def handle_pulido():
    """Endpoint para registrar operaciones de pulido en PostgreSQL."""
    try:
        from backend.models.sql_models import ProduccionPulido, db
        from backend.utils.formatters import normalizar_codigo
        import uuid
        
        data = request.get_json()
        logger.info(f" Datos recibidos en /api/pulido: {data}")
        
        # ========================================
        # VALIDAR CAMPOS REQUERIDOS
        # ========================================
        responsable = str(data.get('responsable', '')).strip()
        if not responsable:
            return jsonify({'success': False, 'error': 'El responsable es OBLIGATORIO'}), 400

        # Conversión segura a números
        try:
            cantidad_real = int(float(data.get('cantidad_real', 0) or 0)) 
            cantidad_recibida = int(float(data.get('cantidad_recibida', 0) or 0))
            pnc_iny = int(float(data.get('pnc_inyeccion', 0) or 0))
            pnc_pul = int(float(data.get('pnc_pulido', 0) or 0))
            total_pnc = pnc_iny + pnc_pul
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Error de formato en números: {str(e)}'}), 400

        # Normalizar código
        codigo_entrada = str(data.get('codigo_producto', '')).strip()
        codigo_sis = normalizar_codigo(codigo_entrada)
        
        if not codigo_sis:
            return jsonify({'success': False, 'error': 'Código de producto requerido'}), 400

        # ========================================
        # ACTUALIZAR INVENTARIO (Lógica SQL)
        # ========================================
        # 1. Salida de POR PULIR
        exito_resta, msj_resta = registrar_salida(codigo_sis, cantidad_recibida or (cantidad_real + total_pnc), "POR PULIR")
        if not exito_resta:
            return jsonify({'success': False, 'error': f"Stock insuficiente en POR PULIR: {msj_resta}"}), 400

        # 2. Entrada a P. TERMINADO
        exito_suma, msj_suma = registrar_entrada(codigo_sis, cantidad_real, "P. TERMINADO")
        if not exito_suma:
            registrar_entrada(codigo_sis, cantidad_recibida, "POR PULIR") # Revertir
            return jsonify({'success': False, 'error': msj_suma}), 400
        
        # 3. Registrar PNC si existe (Suma de ambos para inventario)
        if total_pnc > 0:
            actualizar_stock(codigo_sis, total_pnc, "PNC", "sumar")

        # ========================================
        # CREAR REGISTRO EN PostgreSQL (db_pulido)
        # ========================================
        id_pulido = data.get('id_pulido') or f"PUL-{uuid.uuid4().hex[:8].upper()}"
        fecha_str = data.get('fecha_inicio', datetime.now().strftime('%Y-%m-%d'))
        
        # Convertir a objetos datetime si es posible
        try:

            fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            h_ini = data.get('hora_inicio', '00:00')
            h_fin = data.get('hora_fin', '00:00')
            
            # Crear timestamps para hora_inicio y hora_fin combinando con la fecha
            hora_inicio_dt = datetime.strptime(f"{fecha_str} {h_ini}", '%Y-%m-%d %H:%M')
            hora_fin_dt = datetime.strptime(f"{fecha_str} {h_fin}", '%Y-%m-%d %H:%M')
        except:
            fecha_dt = datetime.now().date()
            hora_inicio_dt = datetime.now()
            hora_fin_dt = datetime.now()

        nuevo_registro = ProduccionPulido(
            id_pulido=id_pulido,
            fecha=fecha_dt,
            codigo=codigo_sis,
            responsable=responsable,
            cantidad_real=cantidad_real,
            pnc_inyeccion=pnc_iny,
            pnc_pulido=pnc_pul,
            criterio_pnc_inyeccion=data.get('criterio_pnc_inyeccion', ''),
            criterio_pnc_pulido=data.get('criterio_pnc_pulido', ''),
            hora_inicio=hora_inicio_dt,
            hora_fin=hora_fin_dt,
            orden_produccion=data.get('orden_produccion', ''),
            observaciones=data.get('observaciones', ''),
            estado='FINALIZADO'
        )
        
        db.session.add(nuevo_registro)
        db.session.commit()
        
        logger.info(f" Registro guardado en SQL: {id_pulido}")
        
        return jsonify({
            'success': True,
            'mensaje': 'Pulido registrado correctamente en PostgreSQL',
            'id_pulido': id_pulido,
            'cantidad_real': cantidad_real,
            'pnc': total_pnc
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f" Error en /api/pulido: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/pulido/ultimo_registro/<responsable>', methods=['GET'])
def get_ultimo_registro_pulido(responsable):
    """Obtiene el último registro de pulido para un responsable específico desde SQL."""
    try:
        from backend.models.sql_models import ProduccionPulido
        registro = db.session.query(ProduccionPulido).filter(
            ProduccionPulido.responsable == responsable
        ).order_by(ProduccionPulido.id.desc()).first()
        
        if not registro:
            return jsonify({'success': True, 'registro': None})
            
    except Exception as e:
        logger.error(f"Error en get_ultimo_registro_pulido: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/ensamble/iniciar', methods=['POST'])
def iniciar_ensamble():
    """
    Persistencia inmediata al iniciar ensamble.
    Crea un registro EN_PROCESO en db_ensambles para que sea visible en el PC de inmediato.
    Sigue el patrón de Pulido: persistirInicioSQL.
    """
    try:
        from backend.models.sql_models import Ensamble
        from backend.utils.formatters import normalizar_codigo
        from sqlalchemy import text
        import pytz

        # Migración segura: asegurar que la columna 'estado' exista
        try:
            db.session.execute(text("ALTER TABLE db_ensambles ADD COLUMN IF NOT EXISTS estado VARCHAR(50) DEFAULT 'FINALIZADO'"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        colombia_tz = pytz.timezone('America/Bogota')
        ahora = datetime.datetime.now(colombia_tz)

        responsable = str(data.get('responsable', '')).strip()
        id_codigo = normalizar_codigo(data.get('id_codigo', ''))

        if not responsable or not id_codigo:
            return jsonify({"success": False, "error": "Responsable y código requeridos"}), 400

        id_ensamble = data.get('id_ensamble') or f"ENS-{uuid.uuid4().hex[:8].upper()}"

        # Evitar duplicados
        existente = db.session.query(Ensamble).filter_by(id_ensamble=id_ensamble).first()
        if existente:
            return jsonify({"success": True, "message": "Ensamble ya registrado", "id_ensamble": id_ensamble}), 200

        # Parsear hora_inicio si viene del frontend
        h_inicio = data.get('hora_inicio')
        dt_inicio = None
        if h_inicio:
            try:
                hi_h, hi_m = h_inicio.split(':')
                dt_inicio = ahora.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0).replace(tzinfo=None)
            except:
                dt_inicio = ahora.replace(tzinfo=None)
        else:
            dt_inicio = ahora.replace(tzinfo=None)

        nuevo_ensamble = Ensamble(
            id_ensamble=id_ensamble,
            id_codigo=id_codigo,
            buje_ensamble=id_codigo,
            responsable=responsable,
            op_numero=data.get('orden_produccion', ''),
            fecha=ahora.date(),
            hora_inicio=dt_inicio,
            departamento='Ensamble',
            cantidad=0,  # Se actualizará al finalizar
            estado='EN_PROCESO'
        )
        db.session.add(nuevo_ensamble)
        db.session.commit()

        logger.info(f"✅ [Ensamble] Inicio persistido: {id_ensamble} ({responsable})")

        return jsonify({
            "success": True,
            "message": "Ensamble iniciado y persistido en SQL",
            "id_ensamble": id_ensamble
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en iniciar_ensamble: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/facturacion', methods=['POST'])
def handle_facturacion():
    """Endpoint para registrar operaciones de facturacion."""
    try:
        data = request.get_json()
        print(f"Datos recibidos en facturacion: {data}")
        
        errors = []
        required_fields = ["fecha_inicio", "cliente", "codigo_producto", "cantidad_vendida"]
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Campo '{field}' es obligatorio")
        
        if errors:
            return jsonify({"status": "error", "message": ", ".join(errors)}), 400
        
        try:
            cantidad_vendida = int(data['cantidad_vendida'])
            if cantidad_vendida <= 0:
                errors.append("La cantidad vendida debe ser mayor a 0")
        except:
            errors.append("La cantidad vendida debe ser un numero valido")
        
        if errors:
            return jsonify({"status": "error", "message": ", ".join(errors)}), 400
        
        codigo_sis = obtener_codigo_sistema_real(data['codigo_producto'])
        print(f"Codigo (traducido): {codigo_sis}")
        
        stock_disponible = obtener_stock(codigo_sis, "P. TERMINADO")
        
        if stock_disponible < cantidad_vendida:
            return jsonify({
                "status": "error", 
                "message": f"Stock insuficiente en P. TERMINADO. Disponible: {stock_disponible}, Solicitado: {cantidad_vendida}"
            }), 400
        
        nit_cliente = "S/N"
        try:
            from backend.models.sql_models import DbClientes
            cliente_db = DbClientes.query.filter_by(nombre=data['cliente']).first()
            if cliente_db:
                nit_cliente = cliente_db.identificacion or "S/N"
        except Exception as e:
            logger.error(f"Error obteniendo NIT del cliente SQL: {e}")
            nit_cliente = "S/N"
        
        if not nit_cliente:
            nit_cliente = "S/N"
        
        print(f"NIT obtenido para {data['cliente']}: {nit_cliente}")
        
        exito_salida, mensaje_salida = registrar_salida(codigo_sis, cantidad_vendida, "P. TERMINADO")
        
        if not exito_salida:
            return jsonify({"status": "error", "message": mensaje_salida}), 400
        
        print("Salida de P. TERMINADO exitosa")
        
        id_factura = f"FAC-{str(uuid.uuid4())[:8].upper()}"
        
        try:
            total_venta = float(data.get('total_venta', 0))
        except:
            total_venta = 0
        
        fila_factura = [
            id_factura,
            data['cliente'],
            formatear_fecha_para_sheet(data['fecha_inicio']),
            nit_cliente,
            cantidad_vendida,
            total_venta,
            codigo_sis
        ]
        
        print(f"Fila para LOG_FACTURACION: {fila_factura}")
        
        if not registrar_log_facturacion(fila_factura):
            return jsonify({
                "status": "error", 
                "message": "Error al guardar en LOG_FACTURACION"
            }), 500
        
        # El cache ya se invalido en registrar_salida
        
        mensaje = f" Facturacion registrada: {cantidad_vendida} piezas de {codigo_sis} para {data['cliente']} (NIT: {nit_cliente})"
        
        return jsonify({
            "status": "success", 
            "message": mensaje
        }), 200
        
    except Exception as e:
        print(f"ERROR en facturacion: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        
        return jsonify({
            "status": "error", 
            "message": f"Error interno: {str(e)}"
        }), 500

# ---------------------------------------------------------
# MDULO DE MEZCLA DE MATERIAL
# ---------------------------------------------------------

# 1. Agrega esto en tu configuracion de Hojas (al inicio de app.py si usas un Enum o Diccionario)
# Asegurate que coincida con el nombre de la pestana que creaste.
# Hojas.MEZCLA = "MEZCLA" 

# ---------------------------------------------------------
# MDULO DE HISTORIAL GLOBAL (VERSIN CORREGIDA)
# ---------------------------------------------------------

# @app.route('/api/historial-global', methods=['GET'])
# def obtener_historial_global():
#     """
#     Obtiene historial consolidado de todos los procesos. (SUSPENDIDO - Migrado a historial_routes.py)
#     Soporta filtros por fecha y tipo de proceso.
#     """
#     try:
#         desde = request.args.get('desde', '')
#         hasta = request.args.get('hasta', '')
#         tipo = request.args.get('tipo', '')
#         
# [BLOQUE LEGACY REMOVIDO PARA ESTABILIZACIÓN RENDER]
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'}), 200

# --- FIN BLOQUE DE RUTAS PRINCIPALES ---
@app.route('/api/auth/status')
def auth_status():
    return jsonify({"logged_in": True}), 200

# [REMOVED LEGACY HISTORY UPDATER]
# ====================================================================
# ENDPOINTS DE CONSULTA
# ====================================================================

@app.route('/api/obtener_ficha/<id_codigo>', methods=['GET'])
def obtener_ficha(id_codigo):
    """Obtiene la ficha tecnica."""
    try:
        codigo_sis = obtener_codigo_sistema_real(id_codigo)
        buje_origen, qty_unitaria = obtener_buje_origen_y_qty(codigo_sis)
        
        return jsonify({
            "buje_origen": buje_origen, 
            "qty_unitaria": qty_unitaria,
            "codigo_sistema": codigo_sis
        }), 200
        
    except Exception as e:
        print(f"Error en obtener_ficha: {str(e)}")
        return jsonify({
            "buje_origen": id_codigo,
            "qty_unitaria": 1,
            "codigo_sistema": id_codigo
        }), 200


# ENDPOINTS PARA MOLDES Y CAVIDADES
# ====================================================================
@app.route('/api/moldes', methods=['GET'])
def obtener_moldes():
    """Obtiene la lista de moldes activos."""
    try:
        from backend.models.sql_models import Molde
        moldes = db.session.query(Molde).filter(Molde.activo == True).order_by(Molde.nombre).all()
        return jsonify([{
            'id': m.id,
            'nombre': m.nombre,
            'cavidades_max': m.cavidades_max,
            'descripcion': m.descripcion
        } for m in moldes]), 200
    except Exception as e:
        logger.error(f"Error en obtener_moldes: {e}")
        return jsonify([]), 200

@app.route('/api/moldes/validar', methods=['POST'])
def validar_molde():
    """Valida si las cavidades solicitadas no superan el mÃ¡ximo del molde."""
    try:
        data = request.json
        nombre_molde = data.get('molde')
        cavidades = int(data.get('cavidades', 0))
        from backend.models.sql_models import Molde
        molde = db.session.query(Molde).filter(Molde.nombre == nombre_molde).first()

        if not molde:
            return jsonify({'success': False, 'error': 'Molde no encontrado'}), 404

        if cavidades > molde.cavidades_max:
            return jsonify({
                'success': False, 
                'error': f'Exceso de cavidades. El molde {nombre_molde} soporta mÃ¡ximo {molde.cavidades_max}.'
            }), 400

        return jsonify({'success': True, 'message': 'ValidaciÃ³n exitosa'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# [REMOVED - MOVED TO common_routes.py]
    
# Cache para Fichas
FICHAS_CACHE = {
    "data": None,
    "timestamp": 0
}
FICHAS_CACHE_TTL = 3600  # 1 hora

@app.route('/api/obtener_fichas', methods=['GET'])
def obtener_fichas():
    """
    Obtiene todas las fichas tecnicas desde SQL (nueva_ficha_maestra).
    """
    try:
        from backend.models.sql_models import FichaMaestra
        fichas_db = FichaMaestra.query.all()
        
        fichas = []
        for f in fichas_db:
            fichas.append({
                'id_codigo': f.producto,
                'buje_ensamble': f.subproducto or '',
                'qty': float(f.cantidad or 1)
            })
        
        return jsonify(fichas), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo fichas SQL: {e}")
        return jsonify([]), 500
# ELIMINADO: obtener_clientes legacy (ahora en common_routes.py)

# ELIMINADO: Endpoint duplicado con lÃ³gica incorrecta de semÃ¡foros (usaba success/danger/warning en lugar de green/red/yellow)

# ====================================================================
# ENDPOINT MAESTRO DE INVENTARIO (V2) - Logica de Semaforo
# ====================================================================
@app.route('/api/productos/listar_v2', methods=['GET'])
def listar_productos_v2():
    """Endpoint optimizado para la tabla de inventario con semaforos."""
    try:
        # 1. Verificar Cache V2
        current_time = time.time()
        if PRODUCTOS_V2_CACHE["data"] and (current_time - PRODUCTOS_V2_CACHE["timestamp"] < PRODUCTOS_CACHE_TTL):
             print(" [Cache] Sirviendo inventario V2 desde memoria")
             return jsonify(PRODUCTOS_V2_CACHE["data"])

        # 2. Obtener productos desde SQL
        productos_sql = repository_service.get_productos_all()
        
        lista_final = []
        for p in productos_sql:
            # Cálculos de stock
            terminado = float(p.get('p_terminado', 0) or 0)
            por_pulir = float(p.get('por_pulir', 0) or 0)
            comprometido = float(p.get('comprometido', 0) or 0)
            
            p_min = float(p.get('stock_minimo', 0) or 0)
            p_reorden = float(p.get('punto_reorden', 0) or 0)
            p_max = float(p.get('stock_maximo', 0) or 100)
            
            stock_global = (terminado + por_pulir) - comprometido
            semaforo = calcular_metricas_semaforo(stock_global, p_min, p_reorden, p_max)
            
            item = {
                "codigo": p.get('codigo_sistema'),
                "id_codigo": p.get('id_codigo'),
                "descripcion": p.get('descripcion', ''),
                "imagen": corregir_url_imagen(str(p.get('imagen', ''))),
                "precio": float(p.get('precio', 0) or 0),
                "stock_por_pulir": por_pulir,
                "stock_terminado": terminado,
                "stock_comprometido": comprometido,
                "stock_disponible": terminado - comprometido,
                "existencias_totales": terminado + por_pulir,
                "metricas": { "min": p_min, "max": p_max, "reorden": p_reorden },
                "semaforo": semaforo
            }
            lista_final.append(item)
            
        # 3. Guardar en cache y retornar
        PRODUCTOS_V2_CACHE["data"] = lista_final
        PRODUCTOS_V2_CACHE["timestamp"] = current_time
        return jsonify(lista_final), 200
    except Exception as e:
        logger.error(f"Error en listar_productos_v2 SQL: {e}")
        return jsonify([]), 500

# --- FIN SECCIÃ“N PRODUCTOS ---


# ELIMINADO: /api/productos legacy (ahora en productos_routes.py)

@app.route('/api/productos/crear_dual', methods=['POST'])
@app.route('/api/productos/dual', methods=['POST'])
def crear_producto_dual():
    """Registra un nuevo producto en db_productos usando SQL."""
    try:
        from backend.models.sql_models import Producto
        data = request.json
        id_codigo = str(data.get('id_codigo', '')).strip().upper()
        codigo_sistema = str(data.get('codigo_sistema', '')).strip().upper()
        descripcion = str(data.get('descripcion', '')).strip()
        precio = data.get('precio', 0)
        stock_inicial = data.get('stock_inicial', 0)

        if not id_codigo or not descripcion:
            return jsonify({"success": False, "error": "ID Código y Descripción son obligatorios"}), 400

        nuevo_prod = Producto(
            id_codigo=id_codigo,
            codigo_sistema=codigo_sistema if codigo_sistema else id_codigo,
            descripcion=descripcion,
            precio=precio,
            p_terminado=stock_inicial
        )
        db.session.add(nuevo_prod)
        db.session.commit()
        return jsonify({"success": True, "message": "Producto creado en PostgreSQL"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
        if col_sis_i >= 0: new_row_inv[col_sis_i] = codigo_sistema or id_codigo
        if col_id_i >= 0: new_row_inv[col_id_i] = id_codigo
        if col_desc_i >= 0: new_row_inv[col_desc_i] = descripcion
        if col_term_i >= 0: new_row_inv[col_term_i] = stock_inicial

        ws_inv.append_row(new_row_inv)
        logger.info("âœ… Registro exitoso en PRODUCTOS")

        # 3. Invalidar CachÃ©
        invalidar_cache_productos()
        
        return jsonify({
            "success": True,
            "message": f"Producto {id_codigo} creado exitosamente en catÃ¡logo e inventario.",
            "sku": id_codigo
        }), 201

    except Exception as e:
        logger.error(f"â Œ Error en crear_producto_dual: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

def invalidar_cache_productos():
    """Limpia el cachÃ© global de productos."""
    global PRODUCTOS_LISTAR_CACHE
    PRODUCTOS_LISTAR_CACHE["data"] = None
    PRODUCTOS_LISTAR_CACHE["timestamp"] = 0
    logger.info("â™»ï¸  Cache de productos invalidado.")


# ELIMINADO: listar_productos legacy (ahora en productos_routes.py)


@app.route('/api/productos/detalle/<codigo_sistema>', methods=['GET'])
def detalle_producto(codigo_sistema):
    """Obtiene el detalle completo de un producto desde SQL."""
    try:
        from backend.models.sql_models import Producto
        codigo_norm = obtener_codigo_sistema_real(codigo_sistema)
        
        p = db.session.query(Producto).filter(
            db.or_(
                Producto.codigo_sistema == codigo_norm,
                Producto.id_codigo == codigo_norm
            )
        ).first()
        
        if not p:
            return jsonify({'status': 'error', 'message': 'Producto no encontrado'}), 404
            
        return jsonify({
            'status': 'success',
            'producto': {
                'codigo_sistema': p.codigo_sistema,
                'id_codigo': p.id_codigo,
                'descripcion': p.descripcion,
                'stock_terminado': float(p.p_terminado or 0),
                'stock_por_pulir': float(p.por_pulir or 0),
                'precio': float(p.precio or 0),
                'imagen': corregir_url_imagen(p.imagen)
            }
        }), 200
    except Exception as e:
        logger.error(f"Error en detalle_producto SQL: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
        ws = ss.worksheet(Hojas.PRODUCTOS)
        registros = ws.get_all_records()

        producto = None
        for r in registros:
            codigo_sheet = str(r.get('CODIGO SISTEMA', '')).strip()
            
            if (codigo_sheet == codigo_sistema or 
                codigo_sheet == codigo_normalizado or
                obtener_codigo_sistema_real(codigo_sheet) == codigo_normalizado):
                
                producto = r
                break

        if not producto:
            print(f" Producto no encontrado: {codigo_sistema}")
            return jsonify({'status': 'error', 'message': f'Producto no encontrado'}), 404

        stock_por_pulir = int(producto.get('POR PULIR', 0) or 0)
        stock_terminado = int(producto.get('P. TERMINADO', 0) or 0)
        stock_comprometido = int(producto.get('COMPROMETIDO', 0) or 0)
        stock_disponible = stock_terminado - stock_comprometido
        stock_total = stock_por_pulir + stock_terminado

        return jsonify({
            'status': 'success',
            'producto': {
                'codigo_sistema': producto.get('CODIGO SISTEMA', ''),
                'descripcion': producto.get('DESCRIPCION', ''),
                'descripcion_larga': producto.get('DESCRIPCION LARGA', '') or producto.get('DESCRIPCION', ''),
                'marca': producto.get('MARCA', ''),
                'categoria': producto.get('CATEGORIA', ''),
                'moldes': producto.get('MOLDE', '') or producto.get('MOLDES', ''),
                'cavidades': producto.get('CAVIDADES', 1) or producto.get('CAV', 1),
                'stock_total': stock_total,
                'stock_por_pulir': stock_por_pulir,
                'stock_terminado': stock_terminado,
                'stock_comprometido': stock_comprometido,
                'stock_disponible': stock_disponible,
                'stock_minimo': int(producto.get('STOCK MINIMO', 10) or 10),
                'imagen': producto.get('IMAGEN', ''),
                'activo': True
            }
        }), 200

    except Exception as e:
        print(f" Error en detalle: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/productos/buscar/<query>', methods=['GET'])
def buscar_productos(query):
    """Busca productos por codigo o descripcion en SQL."""
    try:
        from backend.models.sql_models import Producto
        q = str(query).strip().lower()
        
        # Búsqueda en SQL
        productos = db.session.query(Producto).filter(
            db.or_(
                db.func.lower(Producto.codigo_sistema).contains(q),
                db.func.lower(Producto.id_codigo).contains(q),
                db.func.lower(Producto.descripcion).contains(q)
            )
        ).limit(50).all()
        
        resultados = []
        for p in productos:
            resultados.append({
                'CODIGO SISTEMA': p.codigo_sistema,
                'ID CODIGO': p.id_codigo,
                'DESCRIPCION': p.descripcion,
                'STOCK': float(p.p_terminado or 0),
                'IMAGEN': corregir_url_imagen(p.imagen)
            })
            
        return jsonify(resultados), 200
    except Exception as e:
        logger.error(f"Error en buscar_productos SQL: {e}")
        return jsonify([]), 500
# --- FIN BUSCAR PRODUCTOS ---


    
# [DELETED LEGACY GSHEETS ROUTE]
# [DELETED LEGACY GSHEETS ROUTE]
# [DELETED LEGACY GSHEETS ROUTE]
@app.route('/api/obtener_pnc/<tipo>', methods=['GET'])
def obtener_pnc_por_tipo(tipo):
    """Obtiene los registros de PNC por tipo desde SQL."""
    try:
        from backend.models.sql_models import PncInyeccion, PncPulido
        
        if tipo == "inyeccion":
            registros = PncInyeccion.query.order_by(PncInyeccion.id_row.desc()).limit(200).all()
            return jsonify([{
                'FECHA': r.id_inyeccion.split('-')[1] if '-' in r.id_inyeccion else 'S/F',
                'ID INYECCION': r.id_inyeccion,
                'ID CODIGO': r.id_codigo,
                'CANTIDAD': r.cantidad,
                'CRITERIO': r.criterio,
                'OPERARIO': 'Inyección'
            } for r in registros]), 200
            
        elif tipo == "pulido":
            registros = PncPulido.query.order_by(PncPulido.id_row.desc()).limit(200).all()
            return jsonify([{
                'FECHA': 'S/F',
                'ID PULIDO': r.id_pulido,
                'ID CODIGO': r.id_codigo,
                'CANTIDAD': r.cantidad,
                'CRITERIO': r.criterio,
                'OPERARIO': 'Pulido'
            } for r in registros]), 200
            
        return jsonify({"error": "Tipo de PNC no valido"}), 400
        
    except Exception as e:
        logger.error(f"Error obteniendo PNC SQL {tipo}: {e}")
        return jsonify([]), 200
# --- FIN OBTENER PNC ---

@app.route('/api/obtener_criterios_pnc/<tipo>', methods=['GET'])
def obtener_criterios_pnc(tipo):
    """Obtiene la lista de criterios PNC disponibles por tipo de proceso."""
    criterios = {
        "inyeccion": [
            "Rechupe",
            "Quemado",
            "Escaso",
            "Contaminado",
            "Buje de prueba",
            "Otro"
        ],
        "pulido": [
            "Rayado",
            "Mal pulido",
            "Quebrado",
            "Contaminado",
            "Fuera de especificaciÃ³n",
            "Otro"
        ],
        "ensamble": [
            "Rayado",
            "Contaminado",
            "DimensiÃ³n incorrecta",
            "Prueba",
            "Otro"
        ]
    }
    
    # Obtener criterios segÃºn el tipo
    criterios_tipo = criterios.get(tipo, ["Otro"])
    
    return jsonify({
        "success": True,
        "criterios": criterios_tipo
    }), 200

@app.route('/api/cache/invalidar', methods=['POST'])
def invalidar_cache_endpoint():
    """Endpoint para forzar la invalidacion del cache de productos."""
    try:
        invalidar_cache_productos()
        return jsonify({
            'status': 'success',
            'message': 'Cache de productos invalidado'
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/cache/estado', methods=['GET'])
def estado_cache():
    """Obtiene el estado actual del cache."""
    ahora = time.time()
    tiempo_transcurrido = ahora - PRODUCTOS_CACHE["timestamp"]
    restante = max(0, PRODUCTOS_CACHE_TTL - tiempo_transcurrido)
    
    return jsonify({
        'status': 'success',
        'cache': {
            'data_presente': PRODUCTOS_CACHE["data"] is not None,
            'timestamp': PRODUCTOS_CACHE["timestamp"],
            'tiempo_transcurrido': round(tiempo_transcurrido, 1),
            'ttl_restante': round(restante, 1),
            'ttl_total': PRODUCTOS_CACHE_TTL,
            'vencido': tiempo_transcurrido > PRODUCTOS_CACHE_TTL
        }
    }), 200

# ====================================================================
# ENDPOINT PARA FORZAR ACTUALIZACIN
# ====================================================================
@app.route('/api/productos/limpiar_cache', methods=['POST'])
def limpiar_cache_manual():
    try:
        PRODUCTOS_CACHE["data"] = None
        PRODUCTOS_CACHE["timestamp"] = 0
        print(" Cache limpiado manualmente por usuario")
        return jsonify({"status": "success", "message": "Inventario actualizado"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ====================================================================
# DASHBOARD ANALTICO AVANZADO
# ====================================================================

# [DELETED LEGACY GSHEETS ROUTE]
@app.route('/api/dashboard/avanzado/indicador_inyeccion_sql', methods=['GET'])
def indicador_inyeccion_sql():
    """Calcula indicador de eficiencia de inyección usando SQL."""
    try:
        from backend.core.repository_service import repository_service
        kpis = repository_service.get_dashboard_kpis()
        ok = kpis.get('inyeccion_ok', 0)
        pnc = kpis.get('inyeccion_pnc', 0)
        eficiencia = (ok / (ok + pnc) * 100) if (ok + pnc) > 0 else 100
        
        return jsonify({
            'status': 'success',
            'ok': ok,
            'pnc': pnc,
            'total': ok + pnc,
            'eficiencia': round(eficiencia, 2)
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/avanzado/indicador_pulido', methods=['GET'])
def indicador_pulido():
    """Calcula indicador de eficiencia de pulido usando SQL."""
    try:
        from backend.core.repository_service import repository_service
        kpis = repository_service.get_dashboard_kpis()
        ok = kpis.get('pulido_ok', 0)
        pnc = kpis.get('pulido_pnc', 0)
        eficiencia = (ok / (ok + pnc) * 100) if (ok + pnc) > 0 else 100
        
        return jsonify({
            'status': 'success',
            'ok': ok,
            'pnc': pnc,
            'total': ok + pnc,
            'eficiencia': round(eficiencia, 2)
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# [DELETED LEGACY GSHEETS ROUTE]
@app.route('/api/dashboard/avanzado/produccion_maquina_avanzado', methods=['GET'])
def produccion_maquina_avanzado():
    """
    Analiza la producción por máquina usando SQL-Native.
    Sustituye la carga lenta de Google Sheets por consultas directas a db_inyeccion.
    """
    try:
        from backend.models.sql_models import ProduccionInyeccion, Maquina
        from sqlalchemy import func
        
        # 1. Obtener lista de máquinas
        maquinas_db = {m.nombre: m for m in Maquina.query.all()}
        
        # 2. Consultar producción agregada por máquina desde SQL
        query = db.session.query(
            ProduccionInyeccion.maquina,
            func.sum(ProduccionInyeccion.cantidad_real).label('total'),
            func.count(func.distinct(func.date(ProduccionInyeccion.fecha_inicia))).label('dias')
        ).group_by(ProduccionInyeccion.maquina).all()
        
        resultado = {}
        for row in query:
            nom_maq = row.maquina or 'Sin Maquina'
            total_qty = float(row.total or 0)
            dias_op = int(row.dias or 1)
            
            resultado[nom_maq] = {
                'produccion_total': total_qty,
                'dias_trabajados': dias_op,
                'produccion_promedio': round(total_qty / dias_op if dias_op > 0 else 0),
                'estado': 'Activa' if nom_maq in maquinas_db and maquinas_db[nom_maq].activa else 'Inactiva'
            }
            
        # 3. Ordenar por producción total
        maquinas_ordenadas = sorted(
            resultado.items(),
            key=lambda x: x[1]['produccion_total'],
            reverse=True
        )
        
        return jsonify({
            'status': 'success',
            'maquinas': dict(maquinas_ordenadas),
            'total_maquinas': len(resultado)
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/avanzado/produccion_operario_ranking', methods=['GET'])
def produccion_operario_ranking():
    """Ranking consolidado de operarios (Inyección + Pulido) vía SQL."""
    try:
        from backend.core.repository_service import repository_service
        ranking_iny = repository_service.get_ranking_operarios_inyeccion()
        ranking_pul = repository_service.get_ranking_operarios_pulido()
        
        # Consolidar ambos departamentos
        consolidado = {}
        for r in ranking_iny:
            nom = r['nombre']
            consolidado[nom] = consolidado.get(nom, 0) + r['valor']
        for r in ranking_pul:
            nom = r['nombre']
            consolidado[nom] = consolidado.get(nom, 0) + r['valor']
            
        ranking_final = sorted(consolidado.items(), key=lambda x: x[1], reverse=True)
        
        return jsonify({
            'status': 'success',
            'ranking': dict(ranking_final),
            'total_operarios': len(consolidado)
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/avanzado/ranking_inyeccion', methods=['GET'])
def ranking_inyeccion():
    """Ranking específico de inyectores vía SQL."""
    try:
        from backend.core.repository_service import repository_service
        ranking = repository_service.get_ranking_operarios_inyeccion()
        
        # Mapeo a formato esperado por el frontend
        resultado = {r['nombre']: r['valor'] for r in ranking}
        
        return jsonify({
            'status': 'success',
            'ranking': resultado,
            'total': len(ranking)
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# [DELETED LEGACY GSHEETS ROUTE]
# [DELETED LEGACY GSHEETS ROUTE]
# [DELETED LEGACY GSHEETS ROUTE]
@app.route('/api/producto/historial/<codigo>', methods=['GET'])
def obtener_historial_producto(codigo):
    """
    Obtiene el historial completo de movimientos de un producto desde SQL.
    Migrado 100% a SQL-Native para velocidad y estabilidad.
    """
    try:
        from backend.models.sql_models import ProduccionInyeccion, PncInyeccion, PncPulido, ProduccionPulido, Ensamble, RawVentas
        from backend.utils.formatters import normalizar_codigo
        
        codigo_norm = normalizar_codigo(codigo)
        movimientos = []
        
        # 1. Inyección
        iny = ProduccionInyeccion.query.filter_by(id_codigo=codigo_norm).order_by(ProduccionInyeccion.fecha_inicia.desc()).limit(50).all()
        for m in iny:
            movimientos.append({
                'fecha': m.fecha_inicia.strftime('%Y-%m-%d') if m.fecha_inicia else 'S/F',
                'proceso': 'Inyección',
                'responsable': m.responsable,
                'maquina': m.maquina,
                'cantidad': float(m.cantidad_real or 0),
                'estado': m.estado
            })
            
        # 2. Pulido
        pul = ProduccionPulido.query.filter_by(id_codigo=codigo_norm).order_by(ProduccionPulido.fecha.desc()).limit(50).all()
        for m in pul:
            movimientos.append({
                'fecha': m.fecha.strftime('%Y-%m-%d') if m.fecha else 'S/F',
                'proceso': 'Pulido',
                'responsable': m.responsable,
                'maquina': 'N/A',
                'cantidad': float(m.cantidad_real or 0),
                'estado': 'Completado'
            })
            
        # 3. Ventas (SQL Quirúrgico)
        sql_ven = text("""
            SELECT id, fecha, productos, nombres, cantidad, documento, clasificacion, total_ingresos
            FROM db_ventas 
            WHERE productos ILIKE :o 
            LIMIT 50
        """)
        ven = db.session.execute(sql_ven, {"o": f"%{codigo_norm}%"}).mappings().all()
        for m in ven:
            f_dt = m['fecha']
            movimientos.append({
                'fecha': f_dt.strftime('%Y-%m-%d') if hasattr(f_dt, 'strftime') else str(f_dt or 'S/F'),
                'proceso': 'Venta',
                'responsable': m['nombres'],
                'maquina': m['documento'],
                'cantidad': float(m['cantidad'] or 0),
                'total_ingresos': float(m['total_ingresos'] or 0),
                'estado': 'Facturado'
            })
            
        # Ordenar por fecha desc
        movimientos.sort(key=lambda x: x['fecha'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'movimientos': movimientos,
            'total': len(movimientos),
            'producto': codigo_norm
        }), 200
        
    except Exception as e:
        logger.error(f" ❌ Error en obtener_historial_producto SQL: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def to_int_seguro(valor, default=0):
    """Convierte cualquier valor a entero de forma segura."""
    try:
        if valor is None:
            return default
        if isinstance(valor, (int, float)):
            return int(valor)
        s = str(valor).strip().replace(',', '')
        if s == '':
            return default
        return int(float(s))
    except:
        return default
# ====================================================================
# ENDPOINTS PARA CAVIDADES

@app.route('/api/cavidades/config', methods=['GET'])
def obtener_config_cavidades():
    """Obtiene la configuracion de cavidades disponibles."""
    try:
        # Configuracion de cavidades por maquina (puedes personalizar esto)
        config = {
            "cavidades_disponibles": [1, 2, 3, 4, 5, 6],
            "cavidades_por_defecto": 1,
            "maquinas_config": {
                "INYECTORA 1": {"cavidades": [1, 2, 3, 4, 5, 6], "default": 1},
                "INYECTORA 2": {"cavidades": [1, 2, 3, 4, 5, 6], "default": 2},
                "INYECTORA 3": {"cavidades": [2, 3, 4, 5, 6], "default": 3},
                "INYECTORA 4": {"cavidades": [4, 6, 8, 12, 16], "default": 8},
                "INYECTORA 5": {"cavidades": [8, 12, 16, 24, 32], "default": 12},
                "INYECTORA 6": {"cavidades": [16, 24, 32, 48], "default": 24}
            }
        }
        
        return jsonify({
            "status": "success",
            "config": config
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/inyeccion/calcular', methods=['POST'])
def calcular_inyeccion():
    """Calcula la produccion total basada en cantidad y cavidades."""
    try:
        data = request.get_json()
        
        if not data.get('cantidad') or not data.get('cavidades'):
            return jsonify({
                "status": "error",
                "message": "Se requieren cantidad y cavidades"
            }), 400
        
        try:
            cantidad = int(data['cantidad'])
            cavidades = int(data['cavidades'])
            
            if cantidad <= 0 or cavidades <= 0:
                return jsonify({
                    "status": "error",
                    "message": "La cantidad y cavidades deben ser mayores a 0"
                }), 400
            
            total_piezas = cantidad * cavidades
            
            # Si se envia PNC, calcular piezas OK
            pnc = int(data.get('pnc', 0))
            piezas_ok = total_piezas - pnc
            
            return jsonify({
                "status": "success",
                "calculos": {
                    "disparos": cantidad,
                    "cavidades": cavidades,
                    "total_piezas": total_piezas,
                    "pnc": pnc,
                    "piezas_ok": piezas_ok,
                    "eficiencia": round((piezas_ok / total_piezas * 100), 2) if total_piezas > 0 else 0
                }
            }), 200
            
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Cantidad y cavidades deben ser numeros validos"
            }), 400
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/dashboard/real', methods=['GET'])
def dashboard_real_redirect():
    from flask import redirect
    return redirect('/api/dashboard/stats')


@app.route('/api/pnc', methods=['POST'])
def registrar_pnc():
    """Registra un evento PNC en la tabla db_pnc de SQL y descuenta inventario."""
    try:
        from backend.models.sql_models import Pnc
        from backend.utils.formatters import normalizar_codigo

        
        data = request.json
        logger.info(f" 📥 POST /api/pnc: {data}")
        
        # 1. Normalización de Código (Primera palabra)
        codigo_entrada = str(data.get('codigo_producto', '')).strip()
        if not codigo_entrada:
            return jsonify({"success": False, "error": "Cód. de producto requerido"}), 400
            
        id_codigo = codigo_entrada.split(' ')[0].upper()
        cantidad = float(data.get("cantidad", 0))
        
        if cantidad <= 0:
            return jsonify({"success": False, "error": "Cantidad debe ser mayor a 0"}), 400

        # 2. Transacción SQL
        ahora = get_now_colombia()
        fecha_str = data.get("fecha", ahora.strftime("%Y-%m-%d"))
        fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        
        # Crear registro PNC
        nuevo_pnc = Pnc(
            id_pnc=data.get("id_pnc") or f"PNC-{ahora.strftime('%Y%m%d%H%M%S')}",
            fecha=fecha_dt,
            id_codigo=id_codigo,
            cantidad=cantidad,
            criterio=data.get("criterio", "No especificado"),
            codigo_ensamble=data.get("notas", "") # Mapeo solicitado: Notas -> codigo_ensamble
        )
        db.session.add(nuevo_pnc)
        
        # 3. Descuento de Inventario (STOCK_BODEGA)
        from backend.app import registrar_salida
        exito_salida, msg_salida = registrar_salida(id_codigo, cantidad, "STOCK_BODEGA")
        if not exito_salida:
            logger.warning(f" ⚠️ [PNC SQL] Advertencia en inventario: {msg_salida}")
            # Mantenemos la política de "By-pass" si el usuario lo prefiere, 
            # pero aquí el registro de calidad es la prioridad.
            
        db.session.commit()
        logger.info(f" ✅ PNC Guardado en SQL: {id_codigo} ({cantidad} piezas)")
        
        return jsonify({
            "success": True,
            "mensaje": f"PNC registrado en SQL y descontado de BODEGA: {cantidad} piezas de {id_codigo}",
            "id_pnc": nuevo_pnc.id_pnc
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f" ❌ ERROR /api/pnc: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ====================================================================
# ENDPOINT PNC MULTI-CRITERIO (Soporta lista de defectos)
# ====================================================================


@app.route('/api/obtener_pnc', methods=['GET'])
def obtener_pnc():
    """
    Obtiene todos los registros de PNC consolidados desde SQL.
    Migrado 100% a SQL-Native.
    """
    try:
        from backend.models.sql_models import PncInyeccion, PncPulido, PncEnsamble
        
        consolidado = []
        
        # 1. Inyección
        for p in PncInyeccion.query.order_by(PncInyeccion.id_row.desc()).limit(100).all():
            consolidado.append({
                'id': p.id_pnc_inyeccion,
                'fecha': p.id_inyeccion.split('-')[1] if '-' in p.id_inyeccion else 'S/F',
                'proceso': 'inyeccion',
                'codigo_producto': p.id_codigo,
                'responsable': 'Inyección',
                'cantidad': p.cantidad,
                'criterio_pnc': p.criterio,
                'estado': 'pendiente',
                'observaciones': p.codigo_ensamble or ''
            })
            
        # 2. Pulido
        for p in PncPulido.query.order_by(PncPulido.id_row.desc()).limit(100).all():
            consolidado.append({
                'id': p.id_pnc_pulido,
                'fecha': 'S/F',
                'proceso': 'pulido',
                'codigo_producto': p.id_codigo,
                'responsable': 'Pulido',
                'cantidad': p.cantidad,
                'criterio_pnc': p.criterio,
                'estado': 'pendiente',
                'observaciones': ''
            })
            
        return jsonify(consolidado), 200
        
    except Exception as e:
        logger.error(f" ❌ Error en obtener_pnc SQL: {e}")
        return jsonify([]), 200

@app.route('/api/resolver_pnc/<id_pnc>', methods=['POST'])
def resolver_pnc(id_pnc):
    """Marca un PNC como resuelto (simulado o via columna) Juan Sebastian."""
    # Como no hay columna estado oficial, por ahora respondemos exito Juan Sebastian
    # En el futuro, esto buscaria la fila y actualizaria una celda
    return jsonify({"success": True, "mensaje": f"PNC {id_pnc} marcado como resuelto"}), 200

# Helper local para historial Juan Sebastian se eliminÃ³ por redundancia con to_int_seguro general.

# ==========================================
# NUEVAS FUNCIONES PARA SISTEMA DE SEMFORO
# ==========================================

def calcular_estado_semaforo(stock_actual, stock_minimo, punto_reorden):
    """Calcula color y estado del stock."""
    try:
        stock_minimo = int(stock_minimo) if stock_minimo else 0
        punto_reorden = int(punto_reorden) if punto_reorden else 0
        stock_actual = int(stock_actual)
        
        if stock_minimo == 0:
            return {'color': 'secondary', 'texto': 'S/C', 'prioridad': 0} # Gris

        porcentaje = (stock_actual / stock_minimo) * 100
        
        if stock_actual <= 0:
            return {'color': 'danger', 'texto': 'AGOTADO', 'prioridad': 1} # Rojo
        if porcentaje < 50:
            return {'color': 'danger', 'texto': 'CRITICO', 'prioridad': 2} # Rojo
        if stock_actual < stock_minimo:
            return {'color': 'warning', 'texto': 'BAJO MNIMO', 'prioridad': 3} # Amarillo
        if stock_actual <= punto_reorden:
            return {'color': 'warning', 'texto': 'REORDENAR', 'prioridad': 4} # Amarillo (Cerca a reorden)
            
        return {'color': 'success', 'texto': 'OK', 'prioridad': 5} # Verde
        
    except Exception:
        return {'color': 'secondary', 'texto': 'ERR', 'prioridad': 0}



@app.route('/api/productos/buscar_alternativas/<interno>', methods=['GET'])
def buscar_alternativas(interno):
    """Busca productos que comparten el mismo ID CODIGO (INTERNO) en SQL."""
    try:
        from backend.models.sql_models import Producto
        interno_buscado = str(interno).strip().upper()
        
        # Consultar en la tabla db_productos
        productos = db.session.query(Producto).filter(
            db.func.upper(Producto.id_codigo) == interno_buscado
        ).all()
        
        resultado = []
        for p in productos:
            resultado.append({
                'CODIGO': p.codigo_sistema,
                'ID CODIGO': p.id_codigo,
                'DESCRIPCION': p.descripcion,
                'STOCK': float(p.p_terminado or 0),
                'IMAGEN': p.imagen
            })
            
        return jsonify(resultado), 200
    except Exception as e:
        logger.error(f"Error en buscar_alternativas SQL: {e}")
        return jsonify([]), 500

# ====================================================================
# RUTAS PARA SERVIR ARCHIVOS ESTÃTICOS Y TEMPLATE PRINCIPAL
# ====================================================================

# ====================================================================
# RUTAS PARA SERVIR ARCHIVOS ESTÃTICOS
# ====================================================================
# La ruta index '/' ya fue definida al inicio


# ====================================================================
# MÃ“DULOS NUEVOS: MEZCLA, HISTORIAL Y REPORTES
# ====================================================================

@app.route('/api/mezcla', methods=['POST'])
def handle_mezcla():
    """Registra una nueva mezcla de material en SQL-Native."""
    try:
        from backend.models.sql_models import Mezcla
        from backend.core.sql_database import db
        data = request.get_json()
        logger.info(f" >>> [SQL] Registrando mezcla: {data}")
        
        # Extraccion y casteo seguro de pesos
        try:
            virgen = round(float(data.get('virgen', 0) or 0), 2)
            molido = round(float(data.get('molido', 0) or 0), 2)
            pigmento = round(float(data.get('pigmento', 0) or 0), 2)
            
            # Fecha y Hora: Si viene del frontend yyyy-mm-dd, la parseamos
            f_str = data.get('fecha', '')
            ahora = get_now_colombia()
            fecha_dt = datetime.strptime(f_str, '%Y-%m-%d').date() if f_str else ahora.date()
            hora_str = ahora.strftime('%H:%M:%S')
            
            # Generar Lote Interno Automático
            lote_interno = f"M-{fecha_dt.strftime('%Y%m%d')}-{ahora.strftime('%H%M')}"
            
        except Exception as e:
            logger.error(f" Error Parseando datos de mezcla: {e}")
            return jsonify({'success': False, 'error': 'Formato de datos numéricos o fecha inválido'}), 400

        nueva_mezcla = Mezcla(
            fecha=fecha_dt,
            hora=hora_str,
            responsable=data.get('responsable', 'SISTEMA'),
            maquina=data.get('maquina', 'PROCESO GRAL'),
            virgen_kg=virgen,
            molido_kg=molido,
            pigmento_kg=pigmento,
            lote_interno=lote_interno,
            observaciones=data.get('observaciones', '')
        )
        
        db.session.add(nueva_mezcla)
        db.session.commit()
        
        logger.info(f" ✅ Mezcla Lote {lote_interno} guardada en PostgreSQL.")
        return jsonify({'success': True, 'mensaje': 'Mezcla registrada correctamente en SQL', 'lote': lote_interno}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f" Error en /api/mezcla SQL: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/molido', methods=['POST'])
def registrar_molido():
    """Registra un nuevo pesaje de molido (Recuperado/Contaminado) en SQL-First."""
    try:
        from backend.models.sql_models import Molido
        from backend.core.sql_database import db
        data = request.get_json()
        
        # Captura de datos
        peso = round(float(data.get('peso', 0) or 0), 2)
        tipo = data.get('tipo', 'Recuperado')
        # Si no hay responsable en data, intentar obtener de sesión
        responsable = data.get('responsable') or session.get('user_name', 'SISTEMA')
        obs = data.get('observaciones', '')
        
        ahora = get_now_colombia()
        
        nuevo_molido = Molido(
            fecha_registro=ahora,
            responsable=responsable,
            peso_kg=peso,
            tipo_material=tipo,
            observaciones=obs
        )
        
        db.session.add(nuevo_molido)
        db.session.commit()
        
        logger.info(f" ✅ Molido ({tipo}) registrado: {peso}kg por {responsable}")
        return jsonify({'success': True, 'mensaje': 'Molido registrado correctamente en SQL'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f" Error en /api/molido SQL: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Los endpoints /api/historial y /api/estadisticas han sido deprecados en favor de /api/historial-global y los endpoints de dashboard especÃ­ficos.
@app.route('/static/<path:path>')
def serve_static(path):
    """Sirve archivos estáticos."""
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5005))
    print("\n" + "="*50)
    print(f"    INICIANDO SERVIDOR FLASK (PUERTO {port})")
    print("="*50)
    print(f"    URL: http://0.0.0.0:{port}")
    print("="*50 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        use_reloader=False
    )


