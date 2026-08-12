# -*- coding: utf-8 -*-
from flask import Flask, jsonify, render_template, send_from_directory, request
from flask_cors import CORS
from flask_compress import Compress
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv
load_dotenv()
import logging
import psycopg2.extensions
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE) # Blindaje OID 25
from sqlalchemy import text

from backend.core.sql_database import db

# Configurar logging detallado
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar Flask
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, '../frontend/templates'), 
            static_folder=os.path.join(BASE_DIR, '../frontend/static'))
CORS(app)

# Compresion de respuestas (gzip/brotli) para reducir ancho de banda en Render
app.config['COMPRESS_MIMETYPES'] = ['application/json', 'text/html']
Compress(app)

# Cache-Control de 30 dias exclusivamente para /static/ (sin CDN propio, reduce egress en Render)
@app.after_request
def set_static_cache_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=2592000'
    return response

# Required for Flask Sessions
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
if not FLASK_SECRET_KEY:
    raise RuntimeError(
        "FLASK_SECRET_KEY no está configurada. Defínela como variable de entorno "
        "(archivo .env en local, panel de Environment en Render en producción)."
    )
app.secret_key = FLASK_SECRET_KEY
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

# --- GLOBAL TIMEZONE CONFIG (Colombia UTC-5) ---
COLOMBIA_TZ = pytz.timezone('America/Bogota')

def get_now_colombia():
    return datetime.now(COLOMBIA_TZ)

# --- CONFIGURACIÃ“N SQL (SQL-First) ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL no está configurada. Defínela como variable de entorno "
        "(archivo .env en local, panel de Environment en Render en producción)."
    )
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
logger.debug("📡 [DB] SQLAlchemy inicializado con éxito")

with app.app_context():
    try:
        from backend.models.sql_models import TrazabilidadLote
        db.create_all()
        db.session.execute(text("ALTER TABLE db_pulido ADD COLUMN IF NOT EXISTS fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
        db.session.execute(text("ALTER TABLE cartera_wo ADD COLUMN IF NOT EXISTS fecha_emision DATE;"))
        db.session.commit()
        logger.debug("✅ [DB] Tablas y columna fecha_registro en db_pulido verificadas/creadas con éxito")
    except Exception as e_db:
        logger.error(f"❌ Error creando tablas de base de datos: {e_db}")
# ---------------------------------------------

# Login Blueprints
from backend.routes.auth_routes import auth_bp, restore_session_from_token
app.before_request(restore_session_from_token)
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
from backend.routes.gerencia_routes import gerencia_bp
from backend.routes.wo_routes import wo_bp
from backend.routes.comercial_routes import comercial_bp
from backend.routes.programacion_routes import programacion_bp
from backend.routes.materia_prima_routes import materia_prima_bp
from backend.routes.cliente_routes import cliente_bp
from backend.routes.pnc_routes import pnc_bp
from backend.routes.simulador_routes import simulador_bp
from backend.routes.asistente_routes import asistente_bp
from backend.routes.cartera_routes import cartera_bp

app.register_blueprint(auth_bp)
app.register_blueprint(simulador_bp)
app.register_blueprint(programacion_bp)
app.register_blueprint(materia_prima_bp)
app.register_blueprint(cliente_bp)
app.register_blueprint(pnc_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(imagenes_bp, url_prefix='/imagenes')
app.register_blueprint(facturacion_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(metals_bp)
app.register_blueprint(procura_bp)
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(asistente_bp, url_prefix='/api/dashboard')
app.register_blueprint(productos_bp, url_prefix='/api/productos')
app.register_blueprint(historial_bp)
app.register_blueprint(comercial_bp)

app.register_blueprint(admin_bp)
app.register_blueprint(inyeccion_bp)
app.register_blueprint(pulido_bp)
app.register_blueprint(asistencia_bp, url_prefix='/api/asistencia')
app.register_blueprint(ensamble_bp)
app.register_blueprint(ia_bp)
app.register_blueprint(gerencia_bp)
app.register_blueprint(wo_bp)
app.register_blueprint(cartera_bp)

from backend.routes.pwa_routes import pwa_bp
app.register_blueprint(pwa_bp)


# --- PWA SERVICE WORKER ---
@app.route('/service-worker.js')
def service_worker():
    """Sirve el Service Worker desde la raíz para evitar conflictos de scope (/static/)."""
    import os
    from flask import send_from_directory
    static_path = os.path.join(app.root_path, '../frontend/static')
    return send_from_directory(static_path, 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def serve_manifest():
    import os
    from flask import send_from_directory
    root_path = os.path.join(app.root_path, '..')
    return send_from_directory(root_path, 'manifest.json', mimetype='application/manifest+json')

# --- RUTA DE DEBUG INICIAL ---
@app.route('/')
def index():
    """Pagina principal con la interfaz web."""
    try:
        from backend.services.auth_service import AuthService
        lista_usuarios = AuthService.obtener_staff_frimetals_admin_activo()

        logger.debug(f"[{get_now_colombia()}] >>> PETICIÓN RECIBIDA: index.html")
        return render_template('index.html', usuarios=lista_usuarios)
    except Exception as e:
        logger.error(f"âŒ ERROR RENDERIZANDO index.html: {e}")
        return f"Error en el servidor: {str(e)}", 500
# -----------------------------

# --- ENDPOINTS CATÁLOGO ---
# (Máquinas -> backend/routes/programacion_routes.py, Clientes -> backend/routes/cliente_routes.py)
# -------------------------------------------------------

# --- CONFIGURACIÃ“N DE CACHÃ‰ GLOBAL ---
CACHE_TTL_STRICT = 60    # 1 minuto para datos muy volÃ¡tiles
CACHE_TTL_MEDIUM = 300   # 5 minutos para catÃ¡logos y personal
CACHE_TTL_LONG = 3600    # 1 hora para configuraciones


PEDIDOS_PENDIENTES_CACHE = {
    "friparts": {"data": None, "timestamp": 0, "ttl": CACHE_TTL_STRICT},
    "frimetals": {"data": None, "timestamp": 0, "ttl": CACHE_TTL_STRICT}
}

def invalidar_cache_pedidos():
    """Llamar tras registrar o actualizar alistamiento."""
    global PEDIDOS_PENDIENTES_CACHE
    PEDIDOS_PENDIENTES_CACHE["friparts"]["timestamp"] = 0
    PEDIDOS_PENDIENTES_CACHE["frimetals"]["timestamp"] = 0
    logger.debug("ðŸ—‘ï¸ CachÃ© de PEDIDOS invalidado (ambos tenants)")


# error_response, validate_required_fields y un to_int local (que
# sombreaba sin usarse al to_int real importado de backend.utils.formatters)
# eliminados por no tener ningun caller en todo el backend.


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

# /api/inyeccion (registro legacy directo) movido a
# backend/routes/inyeccion_routes.py + backend/services/inyeccion_service.py
# (InyeccionService.registrar_directa).

# ====================================================================
# MES (MANUFACTURING EXECUTION SYSTEM) - AGENDAMIENTO INYECCION
# Movido a backend/routes/programacion_routes.py + backend/services/programacion_service.py:
# catalogo de maquinas, mes_programar, mes_cancelar, mes_get_programaciones,
# mes_dashboard, mes_get_pendientes_calidad, mes_get_productos_programacion,
# mes_get_status_maquina, mes_iniciar y el cache _mes_cache/clear_mes_cache.
# ====================================================================

# ====================================================================
# FLUJO MES DE PULIDO (estado/iniciar/finalizar/pausar/reanudar,
# PAUSAS_FIJAS_FRIPARTS) y registrar_pnc_detalle movidos a
# backend/services/pulido_service.py (PulidoService) y
# backend/services/pnc_service.py (PncService.registrar_pnc_detalle) +
# backend/routes/pulido_routes.py (pulido_bp).
# ====================================================================

# /api/pulido (POST) y /api/pulido/ultimo_registro/<responsable> movidos
# a backend/routes/pulido_routes.py (pulido_bp). El handle_pulido legacy
# que vivia aqui era codigo muerto: pulido_bp ya registraba /api/pulido
# con anterioridad en el orden de carga de blueprints, y Werkzeug siempre
# enrutaba el trafico real a pulido_bp.registrar_pulido (verificado
# empiricamente con el test client). Confirmado con el usuario antes de
# borrarlo en vez de repararlo.
#
# obtener_ensamble_desde_producto, finalizar_ensamble e iniciar_ensamble
# movidos a backend/services/ensamble_service.py (EnsambleService) +
# backend/routes/ensamble_routes.py (ensamble_bp). El ALTER TABLE
# db_ensambles ADD COLUMN IF NOT EXISTS que vivia dentro de
# iniciar_ensamble fue eliminado por completo (mutacion de esquema
# en caliente prohibida), no migrado.

# /api/facturacion movido a backend/routes/facturacion_routes.py +
# backend/services/facturacion_service.py (FacturacionService). El bug de
# unpacking de StockService.registrar_salida y el NameError de
# formatear_fecha_para_sheet() (ticket task_651f2d99) fueron corregidos
# despues de esta migracion -- ver FacturacionService.registrar.

# ====================================================================
# CATALOGO DE PRODUCTOS / FICHAS / MOLDES / CACHE
# Movido a backend/routes/inventario_routes.py + backend/services/inventario_service.py:
# obtener_ficha, moldes (listar/validar), obtener_fichas, productos/listar_v2,
# productos/crear_dual+dual, cache/invalidar, cache/estado, productos/limpiar_cache.
# Se eliminaron ademas (no migradas) dos rutas duplicadas y muertas registradas
# directamente en app.py -- /api/productos/detalle/<codigo_sistema> y
# /api/productos/buscar/<query> -- que Werkzeug nunca llegaba a servir porque
# productos_bp registra la misma ruta primero (verificado empiricamente).
# ====================================================================


# ====================================================================
# DASHBOARD ANALITICO AVANZADO (indicadores, rankings, produccion por
# maquina) y /api/dashboard/real movidos a backend/routes/dashboard_routes.py
# (dashboard_bp) + backend/repositories/dashboard_repository.py
# (DashboardRepository.get_produccion_por_maquina, nuevo). to_int_seguro
# eliminado por no tener ningun caller en todo el backend.
# ====================================================================

# ====================================================================
# DOMINIO PNC (registro directo, consolidado, resolver) movido a
# backend/routes/pnc_routes.py (pnc_bp) + backend/services/pnc_service.py
# (PncService.registrar/obtener_consolidado/resolver). El bug de unpacking
# de StockService.registrar_salida en PncService.registrar (ticket
# task_651f2d99) fue corregido despues de esta migracion.
# ====================================================================

# Materia Prima (Mezcla/Molido) -> backend/routes/materia_prima_routes.py
# Los endpoints /api/historial y /api/estadisticas han sido deprecados en favor de /api/historial-global y los endpoints de dashboard especÃ­ficos.
@app.route('/static/<path:path>')
def serve_static(path):
    """Sirve archivos estáticos."""
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5005))
    logger.debug("\n" + "="*50)
    logger.debug(f"    INICIANDO SERVIDOR FLASK (PUERTO {port})")
    logger.debug("="*50)
    logger.debug(f"    URL: http://0.0.0.0:{port}")
    logger.debug("="*50 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        use_reloader=False
    )


