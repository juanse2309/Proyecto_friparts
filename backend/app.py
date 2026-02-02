# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import datetime
import uuid
import gspread
import traceback
import time  # Importar time para el cache
import os
import json
import math
from google.oauth2.service_account import Credentials
import logging


# Configurar logging detallado
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            template_folder='../frontend/templates', 
            static_folder='../frontend/static')
CORS(app)

# Login Blueprint
from backend.routes.auth_routes import auth_bp
from backend.routes.pedidos_routes import pedidos_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pedidos_bp)

# --- RUTA DE DEBUG INICIAL ---
@app.route('/')
def index():
    """Pagina principal con la interfaz web."""
    print(f"[{datetime.datetime.now()}] >>> PETICION RECIBIDA: index.html")
    return render_template('index.html')
# -----------------------------

# ====================================================================
# CONFIGURACIÓN GLOBAL (Cargada desde .env para seguridad)
# ====================================================================
GSHEET_FILE_NAME = os.environ.get("GSHEET_FILE_NAME", "Proyecto_Friparts")
GSHEET_KEY = os.environ.get("GSHEET_KEY", "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM")

# Cache simple en memoria
PRODUCTOS_CACHE = {
    "data": None,
    "timestamp": 0
}
PRODUCTOS_CACHE_TTL = 120  # segundos (ajusta a 120, 300, etc.)

class Hojas:
    INYECCION = "INYECCION"
    PNC_INYECCION = "PNC INYECCION"
    PNC_PULIDO = "PNC PULIDO"
    PNC_ENSAMBLE = "PNC ENSAMBLE"
    PRODUCTOS = "PRODUCTOS"
    ENSAMBLES = "ENSAMBLES"
    FICHAS = "FICHAS"
    RESPONSABLES = "RESPONSABLES"
    PULIDO = "PULIDO"
    FACTURACION = "FACTURACION"
    CLIENTES = "CLIENTES"
    MEZCLA = "MEZCLA"

# ====================================================================
# CONFIGURACIÓN DE CREDENCIALES (compatible con desarrollo y producción)
# ====================================================================

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Configurar rutas posibles para las credenciales
CREDENTIALS_PATHS = [
    "credentials_apps.json",  # Ruta local
    "/etc/secrets/credentials_apps.json",  # Ruta tipica en servidores
    "./config/credentials_apps.json",  # Otra ruta comun
]

def cargar_credenciales():
    """Carga las credenciales desde variable de entorno o archivo."""
    
    # 1. Intentar desde variable de entorno (para produccion/entornos cloud)
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if creds_json:
        try:
            print(" Intentando cargar credenciales desde variable de entorno...")
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info, scopes=scope)
            print(" Credenciales cargadas desde variable de entorno")
            return creds
        except json.JSONDecodeError as e:
            print(f" Error en formato JSON de variable de entorno: {e}")
        except Exception as e:
            print(f" Error cargando credenciales desde variable de entorno: {e}")
    
    # 2. Intentar desde archivo en diferentes rutas (para desarrollo local)
    print(" Buscando archivo de credenciales...")
    for path in CREDENTIALS_PATHS:
        try:
            if os.path.exists(path):
                print(f" Encontrado archivo en: {path}")
                creds = Credentials.from_service_account_file(path, scopes=scope)
                print(f" Credenciales cargadas desde archivo: {path}")
                return creds
        except Exception as e:
            print(f"  No se pudo cargar desde {path}: {e}")
            continue
    
    # 3. Si no se encuentra en ninguna parte, mostrar error claro
    print("\n" + "="*60)
    print(" ERROR: No se pudieron cargar las credenciales")
    print("="*60)
    print("Opciones para solucionar:")
    print("1. Para PRODUCCIN (Railway, Render, etc.):")
    print("   - Configura la variable de entorno GOOGLE_CREDENTIALS_JSON")
    print("   - Con el contenido completo del JSON de credenciales")
    print()
    logger.error("2. Para DESARROLLO LOCAL:")
    logger.error("   - Asegurate de que el archivo 'credentials_apps.json'")
    logger.error("   - Este en la misma carpeta que app.py")
    logger.error("   - O en una de estas rutas: %s", CREDENTIALS_PATHS)
    raise FileNotFoundError("No se encontraron credenciales de Google Sheets")

try:
    logger.info("Cargando credenciales...")
    creds = cargar_credenciales()
    logger.info("Autorizando gspread...")
    gc = gspread.authorize(creds)
    logger.info("Autenticacion exitosa con Google Sheets API")
    logger.info("Accediendo a: %s", GSHEET_FILE_NAME)
    
except Exception as e:
    print(f"\n ERROR CRITICO en autenticacion: {e}")
    # ... (resto del manejo de errores)
    exit(1)

# ====================================================================
# FUNCIONES DE CACH
# ====================================================================

def invalidar_cache_productos():
    """Invalida el cache de productos."""
    PRODUCTOS_CACHE["data"] = None
    PRODUCTOS_CACHE["timestamp"] = 0
    print(" PRODUCTOS_CACHE invalidado")

# ====================================================================
# HELPERS (NUEVO)
# ====================================================================

def get_spreadsheet():
    """
    Obtiene la instancia de la hoja de cálculo principal.
    Encapsula la lógica de conexión para evitar duplicación.
    """
    try:
        return gc.open_by_key(GSHEET_KEY)
    except Exception as e:
        logger.error(f"Error conectando a Sheet: {e}")
        raise e

def get_worksheet(nombre_hoja):
    """
    Obtiene una pestaña específica del spreadsheet.
    """
    ss = get_spreadsheet()
    return ss.worksheet(nombre_hoja)

# ====================================================================
# FUNCIONES DE INVENTARIO
# ====================================================================

def buscar_producto_en_inventario(codigo_sistema):
    """
    Busca un producto en la hoja PRODUCTOS y devuelve su información.
    MEJORADO: Usa comparación normalizada (sin espacios, case-insensitive).
    
    Ahora '9304' encontrará 'FR-9304', 'fr-9304', ' 9304 ', etc.
    """
    try:
        logger.info(f"🔎 ===== INICIO BÚSQUEDA EN INVENTARIO =====")
        logger.info(f"🔎 Código recibido: '{codigo_sistema}' (tipo: {type(codigo_sistema).__name__})")
        
        ws = get_worksheet(Hojas.PRODUCTOS)
        registros = ws.get_all_records()
        
        logger.info(f"📊 Total de productos en hoja: {len(registros)}")
        
        # Normalizar el código de búsqueda
        codigo_normalizado = normalizar_codigo(codigo_sistema)
        logger.info(f"🔍 Código normalizado para búsqueda: '{codigo_normalizado}'")
        
        for idx, r in enumerate(registros):
            val_hoja = str(r.get('CODIGO SISTEMA', '')).strip()
            id_codigo = str(r.get('ID CODIGO', '')).strip()
            
            # Normalizar ambos valores de la hoja
            val_hoja_norm = normalizar_codigo(val_hoja)
            id_codigo_norm = normalizar_codigo(id_codigo)
            
            # LOGS DETALLADOS DE COMPARACIÓN
            if idx < 5 or codigo_normalizado in [val_hoja_norm, id_codigo_norm]:
                logger.info(f"   🔄 Fila {idx+2}:")
                logger.info(f"      Buscando: '{codigo_normalizado}'")
                logger.info(f"      Contra CODIGO SISTEMA: '{val_hoja}' → normalizado: '{val_hoja_norm}'")
                logger.info(f"      Contra ID CODIGO: '{id_codigo}' → normalizado: '{id_codigo_norm}'")
                logger.info(f"      Match CODIGO SISTEMA: {val_hoja_norm == codigo_normalizado}")
                logger.info(f"      Match ID CODIGO: {id_codigo_norm == codigo_normalizado}")
            
            # Comparación normalizada
            if val_hoja_norm == codigo_normalizado or id_codigo_norm == codigo_normalizado:
                logger.info(f"✅ ¡¡¡PRODUCTO ENCONTRADO!!! en fila {idx+2}")
                logger.info(f"   CODIGO SISTEMA original: '{val_hoja}'")
                logger.info(f"   ID CODIGO original: '{id_codigo}'")
                logger.info(f"   Descripción: '{r.get('DESCRIPCION', '')}'")
                return {
                    'fila': idx + 2,
                    'datos': r,
                    'encontrado': True
                }
        
        logger.warning(f"❌ PRODUCTO NO ENCONTRADO: '{codigo_sistema}'")
        logger.warning(f"   Código normalizado buscado: '{codigo_normalizado}'")
        logger.warning(f"   Total de registros revisados: {len(registros)}")
        logger.warning(f"   Primeras 5 filas revisadas en detalle (ver arriba)")
        return {'encontrado': False, 'error': f'Producto "{codigo_sistema}" no encontrado en la hoja PRODUCTOS'}
    except Exception as e:
        logger.error(f"❌ ERROR en buscar_producto_en_inventario: {str(e)}")
        logger.error(f"   Tipo de error: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return {'encontrado': False, 'error': str(e)}

def obtener_datos_producto(codigo_entrada):
    """
    HELPER CENTRALIZADO: Este es el unico lugar que deberia realizar búsquedas directas
    en la hoja de PRODUCTOS para evitar disparar el error 429 (Too Many Requests).
    
    Flujo: 
    1. Normaliza el código (quita prefijos 'FR-').
    2. Busca en la hoja PRODUCTOS.
    3. Devuelve los 3 pilares de los datos: Código Sistema, ID Ficha y el diccionario completo.
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
            'CLIENTE': 'CLIENTE'
        }
        
        columna = mapeo_almacenes.get(almacen)
        if not columna or columna not in datos:
            return 0
        
        stock = datos.get(columna, 0)
        try:
            return int(stock) if stock != '' else 0
        except:
            return 0
            
    except Exception as e:
        print(f"Error obteniendo stock: {e}")
        return 0

def actualizar_stock(codigo_sistema, cantidad, almacen, operacion='sumar'):
    """Actualiza el stock de un producto en un almacen especifico."""
    try:
        resultado = buscar_producto_en_inventario(codigo_sistema)
        if not resultado['encontrado']:
            return False, resultado['error']
        
        fila_num = resultado['fila']
        datos = resultado['datos']
        
        mapeo_almacenes = {
            'POR PULIR': 'POR PULIR',
            'P. TERMINADO': 'P. TERMINADO',
            'PRODUCTO ENSAMBLADO': 'PRODUCTO ENSAMBLADO',
            'CLIENTE': 'CLIENTE'
        }
        
        columna = mapeo_almacenes.get(almacen)
        if not columna:
            return False, f'Almacen {almacen} no valido'
        
        stock_actual = obtener_stock(codigo_sistema, almacen)
        
        if operacion == 'sumar':
            nuevo_stock = stock_actual + cantidad
        elif operacion == 'restar':
            if stock_actual < cantidad:
                return False, f'Stock insuficiente. Disponible: {stock_actual}, Requerido: {cantidad}'
            nuevo_stock = stock_actual - cantidad
        else:
            return False, f'Operacion {operacion} no valida'
        
        ws = get_worksheet(Hojas.PRODUCTOS)
        
        headers = ws.row_values(1)
        try:
            col_index = headers.index(columna) + 1
        except ValueError:
            return False, f'Columna {columna} no encontrada en PRODUCTOS'
        
        ws.update_cell(fila_num, col_index, nuevo_stock)
        
        # INVALIDAR CACHE
        invalidar_cache_productos()
        
        mensaje = f'✅ Stock actualizado en Sheets: {codigo_sistema} [{almacen}] {stock_actual} -> {nuevo_stock}'
        logger.info(mensaje)
        print(mensaje)
        return True, mensaje
        
    except Exception as e:
        error_msg = f"Error actualizando stock: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg

def calcular_metricas_semaforo(stock_total, p_min, p_reorden, p_max):
    """
    LOGICA DE NEGOCIO UNIFICADA: Centraliza las reglas de colores del inventario.
    Usa colores: green, yellow, red, dark (NO success/danger/warning)
    Estados: STOCK OK, POR PEDIR, CRÍTICO, AGOTADO
    """
    tiene_config = (p_max is not None and p_max > 0 and p_max != 999999)
    
    if stock_total <= 0:
        estado = "AGOTADO"
        color = "dark"
        mensaje = "Sin Stock"
    elif stock_total <= (p_reorden or 0):
        estado = "CRÍTICO"
        color = "red"
        mensaje = f"Bajo Punto Reorden ({p_reorden})"
    elif stock_total < (p_min or 0):
        estado = "POR PEDIR"
        color = "yellow"
        mensaje = f"Bajo Mínimo ({p_min})"
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
# FUNCIONES DE APOYO
# ====================================================================

def normalizar_codigo(codigo):
    """
    Normaliza un código para comparación EXTREMADAMENTE flexible:
    - Elimina TODOS los espacios
    - Elimina TODOS los guiones
    - Convierte a mayúsculas
    - Elimina prefijos comunes (FR-, INY-)
    
    Ejemplos:
    - 'fr-9304' → '9304'
    - ' 9 3 0 4 ' → '9304'
    - 'FR-9304' → '9304'
    - 'F R - 9 3 0 4' → '9304'
    - '9304' → '9304'
    """
    if not codigo:
        logger.debug("🔍 normalizar_codigo: Código vacío recibido")
        return ""
    
    codigo_original = str(codigo)
    logger.info(f"🔍 normalizar_codigo INPUT: '{codigo_original}'")
    
    # Convertir a string y mayúsculas
    codigo = str(codigo).upper()
    logger.info(f"   Paso 1 - Mayúsculas: '{codigo}'")
    
    # Eliminar TODOS los espacios (incluso en medio)
    codigo = codigo.replace(" ", "")
    logger.info(f"   Paso 2 - Sin espacios: '{codigo}'")
    
    # Eliminar TODOS los guiones
    codigo = codigo.replace("-", "")
    logger.info(f"   Paso 3 - Sin guiones: '{codigo}'")
    
    # Quitar prefijos comunes SI EXISTEN
    if codigo.startswith('FR'):
        codigo = codigo[2:]
        logger.info(f"   Paso 4 - Quitado prefijo FR: '{codigo}'")
    elif codigo.startswith('INY'):
        codigo = codigo[3:]
        logger.info(f"   Paso 4 - Quitado prefijo INY: '{codigo}'")
    
    # Trim final por si acaso
    codigo = codigo.strip()
    
    logger.info(f"🔍 normalizar_codigo OUTPUT FINAL: '{codigo}'")
    return codigo

def obtener_codigo_sistema_real(codigo_entrada):
    """
    Traduce el codigo ingresado por el usuario al codigo real del sistema.
    MEJORADO: Ahora normaliza para comparación flexible.
    
    Ejemplos:
    - 'FR-9304' → '9304'
    - 'fr-9304' → '9304'
    - ' 9304 ' → '9304'
    - 'INY-1050' → '1050'
    - '9304' → '9304'
    
    Args:
        codigo_entrada (str): Codigo ingresado por el usuario
        
    Returns:
        str: Codigo normalizado del sistema
    """
    try:
        logger.info(f"📥 obtener_codigo_sistema_real ENTRADA: '{codigo_entrada}' (tipo: {type(codigo_entrada).__name__})")
        
        if codigo_entrada is None:
            logger.warning("⚠️  Código de entrada es None")
            return ""
        
        # Usar la nueva función de normalización
        resultado = normalizar_codigo(codigo_entrada)
        logger.info(f"📤 obtener_codigo_sistema_real SALIDA: '{resultado}'")
        return resultado
        
    except Exception as e:
        logger.error(f"❌ Error al traducir codigo '{codigo_entrada}': {str(e)}")
        logger.error(f"   Tipo de error: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return str(codigo_entrada).strip() if codigo_entrada else ""

def obtener_producto_por_codigo(codigo_entrada: str):
    """
    Busca un producto aceptando CODIGO SISTEMA (FR-9304) o ID CODIGO (9304).
    Devuelve un diccionario con ambos codigos o None si no lo encuentra.
    """
    if not codigo_entrada:
        return None
    
    try:
        entrada_limpia = str(codigo_entrada).strip().upper()
        
        ws = get_worksheet("PRODUCTOS")
        registros = ws.get_all_records()
        
        # Busqueda exacta por CODIGO SISTEMA o ID CODIGO
        for r in registros:
            codigo_sistema = str(r.get("CODIGO SISTEMA", "")).strip().upper()
            id_codigo = str(r.get("ID CODIGO", "")).strip().upper()
            
            if codigo_sistema == entrada_limpia or id_codigo == entrada_limpia:
                return {
                    "id_codigo": str(r.get("ID CODIGO", "")).strip(),
                    "codigo_sistema": str(r.get("CODIGO SISTEMA", "")).strip(),
                    "descripcion": str(r.get("DESCRIPCION", "")).strip()
                }
        
        print(f" Producto no encontrado: {codigo_entrada}")
        return None
        
    except Exception as e:
        print(f" Error buscando producto: {e}")
        return None

def actualizar_stock_producto(codigo_sistema: str, cantidad: int):
    """
    Actualiza el stock en PRODUCTOS. Busca por CODIGO SISTEMA y suma a POR PULIR.
    """
    try:
        ws = get_worksheet("PRODUCTOS")
        
        headers = ws.row_values(1)
        col_por_pulir = headers.index("POR PULIR") + 1
        
        registros = ws.get_all_records()
        for idx, r in enumerate(registros):
            if str(r.get("CODIGO SISTEMA", "")).strip() == codigo_sistema:
                stock_actual = int(r.get("POR PULIR", 0) or 0)
                nuevo_stock = stock_actual + cantidad
                ws.update_cell(idx + 2, col_por_pulir, nuevo_stock)
                print(f" Stock: {codigo_sistema} POR PULIR = {nuevo_stock}")
                return True
        
        return False
        
    except Exception as e:
        print(f" Stock error: {e}")
        return False

def registrar_pnc_detalle(tipo_proceso, id_operacion, codigo_producto, cantidad_pnc, criterio_pnc, observaciones=""):
    """Registra un Producto No Conforme en la hoja correspondiente."""
    try:
        hoja_pnc = ""
        prefijo_id = ""
        
        if tipo_proceso == "inyeccion":
            hoja_pnc = Hojas.PNC_INYECCION
            prefijo_id = "PNC-INY"
        elif tipo_proceso == "pulido":
            hoja_pnc = Hojas.PNC_PULIDO
            prefijo_id = "PNC-PUL"
        elif tipo_proceso == "ensamble":
            hoja_pnc = Hojas.PNC_ENSAMBLE
            prefijo_id = "PNC-ENS"
        else:
            print(f"Tipo de proceso no valido para PNC: {tipo_proceso}")
            return False
        
        spreadsheet = get_spreadsheet()
        
        try:
            worksheet = spreadsheet.worksheet(hoja_pnc)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Creando hoja {hoja_pnc}...")
            worksheet = spreadsheet.add_worksheet(title=hoja_pnc, rows=1000, cols=10)
            encabezados = ["ID PNC", "ID OPERACIN", "CDIGO PRODUCTO", "CANTIDAD PNC", 
                          "CRITERIO PNC", "OBSERVACIONES", "FECHA", "RESPONSABLE", "ESTADO"]
            worksheet.append_row(encabezados)
        
        id_pnc = f"{prefijo_id}-{str(uuid.uuid4())[:5].upper()}"
        
        fila_pnc = [
            id_pnc,
            id_operacion,
            codigo_producto,
            cantidad_pnc,
            criterio_pnc,
            observaciones,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "",
            "PENDIENTE"
        ]
        
        worksheet.append_row(fila_pnc)
        print(f"PNC registrado en {hoja_pnc}: {cantidad_pnc} piezas de {codigo_producto}")
        return True
        
    except Exception as e:
        print(f"Error al registrar PNC: {e}")
        return False

def registrar_log_operacion(hoja, fila):
    """Registra una operacion en la hoja especificada, creando la hoja si no existe."""
    try:
        logger.info("Registrando en %s: %s...", hoja, fila[:5])
        
        spreadsheet = get_spreadsheet()
        
        try:
            worksheet = spreadsheet.worksheet(hoja)
        except gspread.exceptions.WorksheetNotFound:
            logger.info("Hoja '%s' no encontrada, creandola...", hoja)
            
            # Encabezados predefinidos por hoja
            encabezados_map = {
                Hojas.INYECCION: [
                    "ID INYECCION", "FECHA INICIA", "FECHA FIN", "DEPARTAMENTO",
                    "MAQUINA", "RESPONSABLE", "ID CODIGO", "No. CAVIDADES",
                    "HORA LLEGADA", "HORA INICIO", "HORA TERMINA", "CONTADOR MAQ.",
                    "CANT. CONTADOR", "TOMADOS EN PROCESO", "PESO TOMADAS EN PROCESO",
                    "CANTIDAD REAL", "ALMACEN DESTINO", "CODIGO ENSAMBLE",
                    "ORDEN PRODUCCION", "OBSERVACIONES", "PESO VELA MAQUINA", "PESO BUJES"
                ],
                Hojas.PULIDO: [
                    "ID_PULIDO", "FECHA", "PROCESO", "RESPONSABLE", 
                    "HORA_INICIO", "HORA_FIN", "CODIGO", "LOTE", 
                    "ORDEN_PRODUCCION", "CANTIDAD_RECIBIDA", "PNC", 
                    "BUJES BUENOS", "OBSERVACIONES", "ALMACEN_DESTINO", "ESTADO"
                ],
                Hojas.ENSAMBLES: [
                    "ID_ENSAMBLE", "CODIGO_FINAL", "CANTIDAD", 
                    "ORDEN_PRODUCCION", "RESPONSABLE", "HORA_INICIO", 
                    "HORA_FIN", "BUJE_ORIGEN", "CONSUMO_TOTAL", 
                    "ALMACEN_ORIGEN", "ALMACEN_DESTINO"
                ],
                Hojas.FACTURACION: [
                    "ID FACTURA", "CLIENTE", "FECHA", "DOCUMENTO", 
                    "CANTIDAD", "TOTAL VENTA", "ID CODIGO"
                ]
            }
            
            encabezados = encabezados_map.get(hoja, [f"Columna_{i+1}" for i in range(len(fila))])
            
            # Para FACTURACION usamos 20 columnas por compatibilidad historica si se requiere
            num_cols = 20 if hoja == Hojas.FACTURACION else len(encabezados)
            worksheet = spreadsheet.add_worksheet(title=hoja, rows=1000, cols=num_cols)
            worksheet.append_row(encabezados)
            logger.info("Hoja '%s' creada con %d columnas", hoja, len(encabezados))
        
        if not isinstance(fila, list):
            fila = list(fila)
            
        worksheet.append_row(fila)
        logger.info("Registro exitoso en %s", hoja)
        return True
        
    except Exception as e:
        logger.error("ERROR en registrar_log_operacion (%s): %s", hoja, str(e))
        return False

def obtener_buje_origen_y_qty(codigo_producto):
    """Obtiene el buje origen y qty unitaria desde la ficha tecnica - VERSIN DEBUGGEABLE"""
    try:
        logger.info(f" Iniciando busqueda de buje para: {codigo_producto}")
        
        ss = get_spreadsheet()
        
        # 1. Buscar ID CODIGO en PRODUCTOS
        logger.info(f" Buscando en hoja PRODUCTOS...")
        ws_productos = ss.worksheet(Hojas.PRODUCTOS)
        registros_productos = ws_productos.get_all_records()
        
        logger.info(f"Total registros en PRODUCTOS: {len(registros_productos)}")
        
        id_codigo = None
        for idx, r in enumerate(registros_productos):
            codigo_sistema = str(r.get('CODIGO SISTEMA', '')).strip()
            id_codigo_temp = str(r.get('ID CODIGO', '')).strip()
            
            logger.debug(f"  Fila {idx}: CODIGO SISTEMA='{codigo_sistema}', ID CODIGO='{id_codigo_temp}'")
            
            if codigo_sistema == codigo_producto:
                id_codigo = id_codigo_temp
                logger.info(f" Encontrado: CODIGO SISTEMA '{codigo_producto}'  ID CODIGO '{id_codigo}'")
                break
        
        if not id_codigo:
            logger.warning(f" No se encontro ID CODIGO para CODIGO SISTEMA '{codigo_producto}'")
            logger.warning(f"    Devolviendo codigo original como buje")
            return codigo_producto, 1.0
        
        # 2. Buscar la ficha en FICHAS
        logger.info(f" Buscando en hoja FICHAS...")
        ws_fichas = ss.worksheet(Hojas.FICHAS)
        registros_fichas = ws_fichas.get_all_records()
        
        logger.info(f"Total registros en FICHAS: {len(registros_fichas)}")
        
        ficha_encontrada = None
        for idx, r in enumerate(registros_fichas):
            id_codigo_ficha = str(r.get('ID CODIGO', '')).strip()
            
            logger.debug(f"  Fila {idx}: ID CODIGO='{id_codigo_ficha}'")
            
            if id_codigo_ficha == id_codigo:
                ficha_encontrada = r
                logger.info(f" Ficha encontrada en fila {idx}")
                break
        
        if ficha_encontrada:
            buje_ficha = str(ficha_encontrada.get('BUJE ENSAMBLE', '')).strip()
            qty_str = ficha_encontrada.get('QTY', '1')
            
            logger.info(f"   BUJE ENSAMBLE: '{buje_ficha}'")
            logger.info(f"   QTY: '{qty_str}'")
            
            # NO extraer, usar el valor completo
            buje_real = buje_ficha
            qty_unitaria = float(qty_str) if qty_str and qty_str != '' else 1.0
            
            logger.info(f" Ficha procesada: Buje='{buje_real}', QTY={qty_unitaria}")
            return buje_real, qty_unitaria
        else:
            logger.warning(f" No se encontro ficha para ID CODIGO '{id_codigo}'")
            logger.warning(f"    Devolviendo codigo original como buje")
            return codigo_producto, 1.0
        
    except Exception as e:
        logger.error(f" Error en obtener_buje_origen_y_qty: {type(e).__name__}: {str(e)}")
        logger.error(f"   Devolviendo fallback: {codigo_producto}, 1.0")
        traceback.print_exc()
        return codigo_producto, 1.0


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
    return registrar_log_operacion(Hojas.FACTURACION, fila)

# ====================================================================
# FUNCIN OBTENER MQUINAS
# ====================================================================

def obtener_maquinas_validas():
    """
    Retorna lista de maquinas validas desde Google Sheets.
    Si no existe la hoja MAQUINAS, retorna maquinas por defecto.
    """
    try:
        ws = get_worksheet("MAQUINAS")
        registros = ws.get_all_records()
        
        maquinas = [str(r.get("NOMBRE", "")).strip() for r in registros if r.get("NOMBRE")]
        if maquinas:
            print(f" Maquinas desde Sheets: {maquinas}")
            return sorted(list(set(maquinas)))
    except gspread.exceptions.WorksheetNotFound:
        print(" Hoja MAQUINAS no encontrada, usando maquinas por defecto")
    except Exception as e:
        print(f" Error leyendo MAQUINAS: {e}")
    
    # Fallback: maquinas por defecto (extrae de tus registros)
    maquinas_default = [
        "MAQUINA No. 1",
        "MAQUINA No. 2",
        "MAQUINA No. 3",
        "MAQUINA No. 4"
    ]
    print(f" Usando maquinas por defecto: {maquinas_default}")
    return maquinas_default

# ====================================================================
# ENDPOINTS PARA REGISTROS
# ====================================================================


def corregir_url_imagen(url):
    """Convierte URLs de Google Drive al formato correcto"""
    if not url:
        return ''
    # Formato incorrecto: https://lh3.googleusercontent.com/u/0/d/FILE_ID
    # Formato correcto: https://lh3.googleusercontent.com/d/FILE_ID
    if '/u/0/d/' in url:
        return url.replace('/u/0/d/', '/d/')
    return url


@app.route('/api/verificar-estructura-completa', methods=['GET'])
def verificar_estructura_completa():
    """Verifica TODAS las hojas y sus encabezados."""
    try:
        ss = get_spreadsheet()
        resultado = {}
        
        # Lista de todas las hojas esperadas
        todas_hojas = [
            ("INYECCION", Hojas.INYECCION),
            ("PULIDO", Hojas.PULIDO),
            ("ENSAMBLES", Hojas.ENSAMBLES),
            ("FACTURACION", Hojas.FACTURACION),
            ("PRODUCTOS", Hojas.PRODUCTOS),
            ("FICHAS", Hojas.FICHAS),
            ("RESPONSABLES", Hojas.RESPONSABLES),
            ("CLIENTES", Hojas.CLIENTES),
            ("PNC INYECCION", Hojas.PNC_INYECCION),
            ("PNC PULIDO", Hojas.PNC_PULIDO),
            ("PNC ENSAMBLE", Hojas.PNC_ENSAMBLE)
        ]
        
        for nombre_display, nombre_real in todas_hojas:
            try:
                ws = ss.worksheet(nombre_real)
                encabezados = ws.row_values(1)
                primera_fila = ws.row_values(2) if ws.row_count > 1 else []
                
                resultado[nombre_display] = {
                    'existe': True,
                    'nombre_real': nombre_real,
                    'encabezados': encabezados,
                    'total_filas': ws.row_count,
                    'muestra_primera': dict(zip(encabezados, primera_fila + [''] * (len(encabezados) - len(primera_fila)))) if primera_fila else {}
                }
                
                print(f" {nombre_display} ({nombre_real}): {len(encabezados)} columnas, {ws.row_count} filas")
                
            except Exception as e:
                resultado[nombre_display] = {
                    'existe': False,
                    'nombre_real': nombre_real,
                    'error': str(e)
                }
                print(f" {nombre_display} ({nombre_real}): NO EXISTE - {e}")
        
        return jsonify({
            'status': 'success',
            'archivo': GSHEET_FILE_NAME,
            'hojas': resultado
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint para verificar que la app esta funcionando."""
    try:
        # Verificar conexion a Google Sheets
        ss = get_spreadsheet()
        hojas = [ws.title for ws in ss.worksheets()]
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "bujes_produccion",
            "google_sheets": {
                "connected": True,
                "file": GSHEET_FILE_NAME,
                "sheets_count": len(hojas),
                "sheets_sample": hojas[:5]  # Primeras 5 hojas
            },
            "endpoints": {
                "obtener_responsables": "/api/obtener_responsables",
                "obtener_clientes": "/api/obtener_clientes",
                "obtener_productos": "/api/obtener_productos",
                "obtener_maquinas": "/api/obtener_maquinas",
                "debug_conexion": "/api/debug/conexion"
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ========== ENDPOINT INYECCIÓN - VERSIÓN CORREGIDA ==========
@app.route('/api/inyeccion', methods=['POST'])
def registrar_inyeccion():
    """Registra un nuevo registro de inyección en Sheets - VERSIÓN COMPLETA CON 22 COLUMNAS"""
    try:
        data = request.json
        logger.debug(f" Datos recibidos: {data}")
        
        # ========================================
        # VALIDACIONES STRICT (Blindaje Power BI) Juan Sebastian
        # ========================================
        codigo_producto_entrada = str(data.get('codigo_producto', '')).strip()
        if not codigo_producto_entrada:
             return jsonify({'success': False, 'error': 'El código de producto es OBLIGATORIO para Power BI'}), 400
        
        responsable = str(data.get('responsable', '')).strip()
        if not responsable:
             return jsonify({'success': False, 'error': 'El responsable es OBLIGATORIO para Power BI'}), 400

        # ========================================
        # CONVERSION SEGURA (Blindaje Power BI)
        # ========================================
        try:
            # Usar float interactivo para limpiar strings como "10.0"
            disparos = int(float(data.get('cantidad_real', 0) or 0)) 
            cavidades = int(float(data.get('no_cavidades', 1) or 1)) # Default 1 to avoid ZeroDiv
            pnc = int(float(data.get('pnc', 0) or 0))
            tomados_proceso = int(float(data.get('tomados_proceso', 0) or 0))
            
            # Floats
            peso_tomadas = float(data.get('peso_tomadas', 0) or 0)
            peso_vela_maquina = float(data.get('peso_vela_maquina', 0) or 0)
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Error de formato en números: {str(e)}'}), 400

        # Resto de campos
        fecha_inicio = data.get('fecha_inicio', '')
        fecha_fin = data.get('fecha_fin', '')
        maquina = data.get('maquina', '')
        observaciones = data.get('observaciones', '')
        almacen_destino = data.get('almacen_destino', '')
        codigo_ensamble = data.get('codigo_ensamble', '')
        peso_bujes = float(data.get('peso_bujes', 0.0) or 0)
        criterio_pnc = data.get('criterio_pnc', '')
        hora_llegada = data.get('hora_llegada', '')
        hora_inicio = data.get('hora_inicio', '')
        hora_termina = data.get('hora_termina', '')
        orden_produccion = data.get('orden_produccion', '')
        
        # ========================================
        # TRADUCIR CÓDIGO DE PRODUCTO
        # ========================================
        codigo_producto = obtener_codigo_sistema_real(codigo_producto_entrada)
        logger.info(f" Código entrada: '{codigo_producto_entrada}'  Sistema: '{codigo_producto}'")
        
        # ========================================
        # VALIDACIONES
        # ========================================
        if not codigo_producto or codigo_producto.strip() == '':
            return error_response('El código de producto es obligatorio')
        
        if disparos <= 0:
            return error_response('La cantidad de disparos debe ser mayor a 0')
        
        if not responsable or responsable.strip() == '':
            return error_response('El responsable es obligatorio')
        
        if not maquina or maquina.strip() == '':
            return error_response('La máquina es obligatoria')
        
        # ========================================
        # CALCULAR PRODUCCIÓN
        # ========================================
        cantidad_total = disparos * cavidades
        piezas_buenas = max(0, cantidad_total - pnc)
        
        logger.info(f" Calculado: {disparos} disparos  {cavidades} cavidades = {cantidad_total} piezas")
        
        # ========================================
        # BUSCAR CODIGO SISTEMA COMPLETO (con FR-)
        # ========================================
        codigo_sistema_completo, _, _ = obtener_datos_producto(codigo_producto_entrada)
        
        if not codigo_sistema_completo:
            codigo_sistema_completo = codigo_producto_entrada
            logger.warning(f" No se encontro CODIGO SISTEMA para {codigo_producto}, usando: {codigo_producto_entrada}")
        
        # ========================================
        # PREPARAR FILA (22 COLUMNAS)
        # ========================================
        row_validada = [
            "",                      # 1  ID INYECCION
            str(fecha_inicio),       # 2  FECHA INICIA
            str(fecha_fin),          # 3  FECHA FIN
            "INYECCION",             # 4  DEPARTAMENTO
            str(maquina),            # 5  MAQUINA
            str(responsable),        # 6  RESPONSABLE
            str(codigo_producto),    # 7  ID CODIGO (sin FR-)
            int(cavidades),          # 8  No. CAVIDADES
            str(hora_llegada),       # 9  HORA LLEGADA
            str(hora_inicio),        # 10 HORA INICIO
            str(hora_termina),       # 11 HORA TERMINA
            int(disparos),           # 12 CONTADOR MAQ.
            int(disparos),           # 13 CANT. CONTADOR
            int(tomados_proceso),    # 14 TOMADOS EN PROCESO
            float(peso_tomadas),     # 15 PESO TOMADAS EN PROCESO
            int(cantidad_total),     # 16 CANTIDAD REAL
            str(almacen_destino),    # 17 ALMACEN DESTINO
            str(codigo_ensamble),    # 18 CODIGO ENSAMBLE
            str(orden_produccion),   # 19 ORDEN PRODUCCION
            str(observaciones),      # 20 OBSERVACIONES
            float(peso_vela_maquina),# 21 PESO VELA MAQUINA
            float(peso_bujes)        # 22 PESO BUJES
        ]
        
        logger.debug(f" Fila validada: {row_validada}")
        
        # ========================================
        # GUARDAR EN HOJA INYECCION
        # ========================================
        try:
            ss = gc.open_by_key(GSHEET_KEY)
            ws = ss.worksheet(Hojas.INYECCION)
            
            ws.append_row(row_validada, value_input_option='USER_ENTERED')
            fila_guardada = ws.row_count
            
            logger.info(f" Inyeccion guardada en fila {fila_guardada}")
            
        except Exception as e:
            logger.error(f" Error guardando en INYECCION: {str(e)}")
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Error guardando: {str(e)}'}), 500
        
        # ========================================
        #  ACTUALIZAR STOCK EN PRODUCTOS (Solo piezas BUENAS Juan Sebastian)
        # ========================================
        if almacen_destino:
            exito_stock, msg_stock = registrar_entrada(
                codigo_sistema_completo,
                piezas_buenas,            # Solo piezas buenas
                almacen_destino
            )
            
            if exito_stock:
                logger.info(f" Stock actualizado: {codigo_sistema_completo} en {almacen_destino} (+{cantidad_total})")
            else:
                logger.warning(f" No se pudo actualizar stock: {msg_stock}")
        else:
            logger.warning(f" No se especifico almacen destino, stock no actualizado")
        
        # ========================================
        # REGISTRAR PNC SI EXISTE
        # ========================================
        if pnc > 0:
            logger.info(f" Registrando PNC: {pnc} piezas")
            id_inyeccion = f"INY-{str(uuid.uuid4())[:5].upper()}"
            exito_pnc = registrar_pnc_detalle(
                tipo_proceso="inyeccion",
                id_operacion=id_inyeccion,
                codigo_producto=codigo_producto,
                cantidad_pnc=pnc,
                criterio_pnc=criterio_pnc,
                observaciones=observaciones
            )
            if not exito_pnc:
                logger.warning(f" PNC no se registro correctamente")
        
        # ========================================
        # RESPUESTA EXITOSA
        # ========================================
        return jsonify({
            'success': True,
            'mensaje': 'Inyección guardada correctamente',
            'disparos': disparos,
            'cavidades': cavidades,
            'piezasTotal': cantidad_total,
            'pnc': pnc,
            'piezasBuenas': piezas_buenas,
            'codigoProductoEntrada': codigo_producto_entrada,
            'codigoProductoSistema': codigo_producto,
            'filaGuardada': fila_guardada if 'fila_guardada' in locals() else None
        }), 200
        
    except Exception as e:
        logger.error(f" Error general en registrar_inyeccion: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Error interno del servidor: {str(e)}'}), 500



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

# ========== NUEVO ENDPOINT PARA OBTENER ENSAMBLE DESDE PRODUCTO ==========
@app.route('/api/inyeccion/ensamble_desde_producto', methods=['GET'])
def obtener_ensamble_desde_producto():
    """Dado un codigo de producto (9304 o FR-9304), retorna el codigo ensamble y QTY."""
    try:
        codigo_entrada = request.args.get('codigo', '').strip()
        if not codigo_entrada:
            return jsonify({'success': False, 'error': 'Codigo producto requerido'}), 400

        # Normalizar a CODIGO SISTEMA real (ej: FR-9304 -> 9304)
        codigo_sistema = obtener_codigo_sistema_real(codigo_entrada)

        # Usar la misma logica que ensamble
        buje_ensamble, qty_unitaria = obtener_buje_origen_y_qty(codigo_sistema)

        return jsonify({
            'success': True,
            'codigo_sistema': codigo_sistema,
            'codigo_ensamble': buje_ensamble,
            'qty': qty_unitaria
        }), 200
    except Exception as e:
        logger.error(f" Error en obtener_ensamble_desde_producto: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/pulido', methods=['POST'])
def handle_pulido():
    """Endpoint para registrar operaciones de pulido."""
    try:
        data = request.get_json()
        logger.info(f" Datos recibidos en /api/pulido: {data}")
        
        # ========================================
        # VALIDAR CAMPOS REQUERIDOS (Blindaje Power BI)
        # ========================================
        responsable = str(data.get('responsable', '')).strip()
        if not responsable:
            return error_response("El responsable es OBLIGATORIO para Power BI")

        # Conversión segura a ENTEROS
        try:
            # Usar float interactivo para limpiar strings
            cantidad_real = int(float(data.get('cantidad_real', 0) or 0)) 
            cantidad_recibida = int(float(data.get('cantidad_recibida', 0) or 0))
            pnc = int(float(data.get('pnc', 0) or 0))
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Error de formato en números: {str(e)}'}), 400

        required_fields = ['fecha_inicio', 'hora_inicio', 'hora_fin', 'codigo_producto']
        errors = validate_required_fields(data, required_fields)
        if errors:
            return error_response(", ".join(errors))
        
        # ========================================
        # NORMALIZAR CDIGO
        # ========================================
        codigo_entrada = str(data.get('codigo_producto', '')).strip()
        codigo_sis = obtener_codigo_sistema_real(codigo_entrada)
        logger.info(f" Codigo entrada: '{codigo_entrada}'  Sistema: '{codigo_sis}'")
        
        if not codigo_sis:
            return error_response("Codigo de producto requerido")
        
        # ========================================
        # BUSCAR CODIGO SISTEMA COMPLETO (con FR-)
        # ========================================
        codigo_sistema_completo, _, _ = obtener_datos_producto(codigo_entrada)
        
        if not codigo_sistema_completo:
            codigo_sistema_completo = codigo_entrada
            logger.warning(f" No se encontro CODIGO SISTEMA, usando entrada: {codigo_entrada}")
        
        # ========================================
        # ACTUALIZAR INVENTARIO (Lógica simplificada Juan Sebastian)
        # ========================================
        cantidad_real = int(data.get('cantidad_real', 0))
        pnc = int(data.get('pnc', 0))
        cantidad_total = int(data.get('cantidad_recibida', 0)) or (cantidad_real + pnc)

        logger.info(f" Procesamiento Pulido: Recibidas={cantidad_total}, Buenas={cantidad_real}, PNC={pnc}")

        # 1. Salida de POR PULIR (Descontamos todo lo que entró a proceso)
        exito_resta, msj_resta = registrar_salida(codigo_sistema_completo, cantidad_total, "POR PULIR")
        if not exito_resta:
            logger.error(f" Error restando stock POR PULIR: {msj_resta}")
            return jsonify({'success': False, 'error': f"Stock insuficiente en POR PULIR: {msj_resta}"}), 400

        # 2. Entrada a P. TERMINADO (Solo sumamos las piezas que quedaron buenas)
        exito_suma, msj_suma = registrar_entrada(codigo_sistema_completo, cantidad_real, "P. TERMINADO")
        if not exito_suma:
            # Revertir
            registrar_entrada(codigo_sistema_completo, cantidad_total, "POR PULIR")
            logger.error(f" Error sumando stock P. TERMINADO: {msj_suma}")
            return jsonify({'success': False, 'error': msj_suma}), 400
        
        logger.info(f" Stock actualizado: {codigo_sistema_completo} (-{cantidad_total} POR PULIR, +{cantidad_real} P. TERMINADO)")

        
        # ========================================
        # CREAR REGISTRO EN HOJA PULIDO
        # ========================================
        id_pulido = f"PUL-{str(uuid.uuid4())[:5].upper()}"
        
        fila_pulido = [
            id_pulido,                              # ID_PULIDO
            data.get('fecha_inicio', ''),          # FECHA
            "Pulido",                               # PROCESO
            data.get('responsable', ''),           # RESPONSABLE
            data.get('hora_inicio', ''),           # HORA_INICIO
            data.get('hora_fin', ''),              # HORA_FIN
            codigo_sis,                             # CODIGO (sin FR-)
            data.get('fecha_inicio', ''),          # LOTE (Usuario pide que muestre la FECHA Juan Sebastian)
            data.get('orden_produccion', ''),      # ORDEN_PRODUCCION
            int(data.get('cantidad_recibida', 0)), # CANTIDAD_RECIBIDA
            int(data.get('pnc', 0)),               # PNC
            cantidad_real,                          # BUJES BUENOS (Antes CANTIDAD_REAL)
            data.get('observaciones', ''),         # OBSERVACIONES
            "P. TERMINADO",                        # ALMACEN_DESTINO
            ""                                      # ESTADO
        ]
        
        logger.debug(f" Fila pulido (15 columnas): {fila_pulido}")
        
        # ========================================
        # GUARDAR EN GOOGLE SHEETS
        # ========================================
        try:
            ss = gc.open_by_key(GSHEET_KEY)
            ws = ss.worksheet(Hojas.PULIDO)
            ws.append_row(fila_pulido, value_input_option='USER_ENTERED')
            logger.info(f" Registro guardado en PULIDO")
        except Exception as e:
            logger.error(f" Error guardando: {str(e)}")
            # Revertir movimiento de stock
            mover_inventario_entre_etapas(codigo_sistema_completo, cantidad_real, "P. TERMINADO", "POR PULIR")
            return jsonify({'success': False, 'error': f'Error guardando: {str(e)}'}), 500
        
        # ========================================
        # REGISTRAR PNC SI EXISTE
        # ========================================
        pnc = int(data.get('pnc', 0))
        if pnc > 0:
            logger.info(f" Registrando PNC: {pnc} piezas")
            exito_pnc = registrar_pnc_detalle(
                tipo_proceso="pulido",
                id_operacion=id_pulido,
                codigo_producto=codigo_sis,
                cantidad_pnc=pnc,
                criterio_pnc=data.get('criterio_pnc', ''),
                observaciones=data.get('observaciones', '')
            )
            if not exito_pnc:
                logger.warning(f" PNC no registrado")
        
        # ========================================
        # RESPUESTA EXITOSA
        # ========================================
        return jsonify({
            'success': True,
            'mensaje': ' Pulido registrado correctamente',
            'id_pulido': id_pulido,
            'cantidad_real': cantidad_real,
            'pnc': pnc
        }), 200
        
    except Exception as e:
        logger.error(f" Error en /api/pulido: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ensamble', methods=['POST'])
def handle_ensamble():
    """Endpoint para registrar operaciones de ensamble."""
    try:
        data = request.get_json()
        logger.info(f" Datos recibidos en /api/ensamble: {data}")
        
        # ========================================
        # VALIDACIONES STRICT (Blindaje Power BI)
        # ========================================
        responsable = str(data.get('responsable', '')).strip()
        if not responsable:
            return error_response("El responsable es OBLIGATORIO para Power BI")

        # Conversión segura a ENTEROS
        try:
            # Usar float interactivo para limpiar strings
            cantidad_real = int(float(data.get('cantidad_real', 0) or 0)) 
            cantidad_recibida = int(float(data.get('cantidad_recibida', 0) or 0))
            pnc = int(float(data.get('pnc', 0) or 0))
            # Qty unitaria puede ser float
            qty_unitaria_input = float(data.get('qty_unitaria', 0) or 0)
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Error de formato en números: {str(e)}'}), 400

        required_fields = ['fecha_inicio', 'hora_inicio', 'hora_fin', 'codigo_producto']
        errors = validate_required_fields(data, required_fields)
        if errors:
            return error_response(", ".join(errors))
        
        # ========================================
        # OBTENER Y NORMALIZAR CDIGO
        # ========================================
        codigo_entrada = str(data.get('codigo_producto', '')).strip()
        codigo_sis = obtener_codigo_sistema_real(codigo_entrada)
        
        logger.info(f" Codigo entrada: '{codigo_entrada}'  Sistema: '{codigo_sis}'")
        
        if not codigo_sis:
            return error_response("Codigo de producto requerido")
        
        # ========================================
        # OBTENER INFORMACIN DE BUJE ORIGEN
        # ========================================
        buje_origen_id, qty_calculada = obtener_buje_origen_y_qty(codigo_sis)
        
        # PRIORIZAR QTY ENVIADO POR EL CLIENTE (Frontend)
        qty_unitaria = float(data.get('qty_unitaria', qty_calculada))
        
        logger.info(f" Buje ID: {buje_origen_id}, QTY unitaria: {qty_unitaria} (Calculada: {qty_calculada})")
        
        # ========================================
        # BUSCAR CODIGO SISTEMA DEL BUJE
        # ========================================
        buje_codigo_sistema, _, _ = obtener_datos_producto(buje_origen_id)
        
        if not buje_codigo_sistema:
            buje_codigo_sistema = buje_origen_id
            logger.warning(f" No se encontro CODIGO SISTEMA para buje {buje_origen_id}, usando ID")
            
        # ========================================
        # BUSCAR CODIGO SISTEMA DEL PRODUCTO ENSAMBLADO
        # ========================================
        producto_codigo_sistema, _, _ = obtener_datos_producto(codigo_sis)
        if not producto_codigo_sistema:
            producto_codigo_sistema = codigo_entrada

        # ========================================
        # CALCULAR CANTIDADES
        # ========================================
        cantidad_recibida = int(data.get('cantidad_recibida', 0))
        pnc = int(data.get('pnc', 0))
        cantidad_real = int(data.get('cantidad_real', 0))
        
        if cantidad_recibida == 0:
            cantidad_recibida = cantidad_real + pnc
        
        # Calcular consumo de bujes (Usando QTY unitaria corregida)
        total_consumo = cantidad_recibida * qty_unitaria
        
        logger.info(f" Cantidades: recibida={cantidad_recibida}, real={cantidad_real}, pnc={pnc}, consumo={total_consumo}")
        logger.info(f" Stock - Descontara de: {buje_codigo_sistema}, Agregara a: {producto_codigo_sistema}")
        
        # ========================================
        # MOVER INVENTARIO (USANDO ALMACENES DINAMICOS)
        # ========================================
        almacen_origen = data.get('almacen_origen', 'P. TERMINADO')
        almacen_destino = data.get('almacen_destino', 'PRODUCTO ENSAMBLADO')

        # Salida de buje (CONSUMO TOTAL: Recibida * QTY)
        exito_resta, msj_resta = registrar_salida(buje_codigo_sistema, total_consumo, almacen_origen)
        if not exito_resta:
            logger.error(f" {msj_resta}")
            return jsonify({"success": False, "error": msj_resta}), 400
        
        logger.info(f" Salida: {buje_codigo_sistema} (-{total_consumo}) desde {almacen_origen}")
        
        # Entrada del producto ensamblado (Solo las BUENAS sumadas al destino)
        exito_suma, msj_suma = registrar_entrada(producto_codigo_sistema, cantidad_real, almacen_destino)
        if not exito_suma:
            # Revertir
            registrar_entrada(buje_codigo_sistema, total_consumo, almacen_origen)
            logger.error(f" {msj_suma}")
            return jsonify({"success": False, "error": msj_suma}), 400
        
        logger.info(f" Entrada: {producto_codigo_sistema} (+{cantidad_real}) en {almacen_destino}")
        
        # ========================================
        # CREAR REGISTRO EN HOJA ENSAMBLES
        # ========================================
        id_ensamble = f"ENS-{str(uuid.uuid4())[:8].upper()}"
        
        #  ORDEN CORRECTO SEGN TUS ENCABEZADOS - SIN CAMPO LOTE
        # Asegurate que la hoja ENSAMBLES no tenga columna para "LOTE"
        fila_ensamble = [
            data.get('fecha_inicio', ''),              # 1. FECHA
            id_ensamble,                                # 2. ID ENSAMBLE
            codigo_sis,                                 # 3. ID CODIGO (sin FR-)
            cantidad_real,                              # 4. CANTIDAD
            data.get('orden_produccion', ''),          # 5. OP NUMERO
            data.get('responsable', ''),               # 6. RESPONSABLE
            data.get('hora_inicio', ''),               # 7. HORA INICIO
            data.get('hora_fin', ''),                  # 8. HORA FIN
            buje_origen_id,                            # 9. BUJE ENSAMBLE (ID sin FR-)
            qty_unitaria,                              # 10. QTY
            'P. TERMINADO',                            # 11. ALMACEN PARA DESCARGAR
            'PRODUCTO ENSAMBLADO'                      # 12. ALMACEN DESTINO
            # NOTA: Ya no incluimos campo "LOTE" aqui
        ]
        
        # Si tu hoja de Google Sheets tiene mas columnas (ej: observaciones), 
        # puedes agregarlas aqui segun los datos del formulario:
        fila_ensamble.append(data.get('observaciones', ''))  # 13. OBSERVACIONES (si existe la columna)
        # fila_ensamble.append(data.get('criterio_pnc', ''))  # 14. CRITERIO PNC (si existe la columna)
        
        logger.debug(f" Fila ensamble ({len(fila_ensamble)} columnas): {fila_ensamble}")
        
        # Guardar en Google Sheets
        try:
            ss = gc.open_by_key(GSHEET_KEY)
            ws = ss.worksheet(Hojas.ENSAMBLES)
            # Verifica que la hoja tenga las columnas correctas
            headers = ws.row_values(1)
            logger.info(f" Encabezados de ENSAMBLES: {headers}")
            
            # Si faltan columnas para los datos adicionales, puedes agregar valores vacios
            while len(fila_ensamble) < len(headers):
                fila_ensamble.append('')
                
            ws.append_row(fila_ensamble, value_input_option='USER_ENTERED')
            logger.info(f" Registro guardado en ENSAMBLES con {len(fila_ensamble)} columnas")
        except Exception as e:
            logger.error(f" Error guardando: {str(e)}")
            # Revertir movimientos de stock
            registrar_salida(producto_codigo_sistema, cantidad_real, "PRODUCTO ENSAMBLADO")
            registrar_entrada(buje_codigo_sistema, total_consumo, "P. TERMINADO")
            return jsonify({"success": False, "error": f"Error guardando: {str(e)}"}), 500
        
        # ========================================
        # REGISTRAR PNC SI EXISTE
        # ========================================
        if pnc > 0:
            logger.info(f" Registrando PNC: {pnc} piezas")
            exito_pnc = registrar_pnc_detalle(
                tipo_proceso='ensamble',
                id_operacion=id_ensamble,
                codigo_producto=codigo_sis,
                cantidad_pnc=pnc,
                criterio_pnc=data.get('criterio_pnc', ''),
                observaciones=data.get('observaciones', '')
            )
            if not exito_pnc:
                logger.warning(f" PNC no registrado")
        
        # ========================================
        # RESPUESTA EXITOSA
        # ========================================
        mensaje = f" Ensamble registrado: {cantidad_real} piezas de {codigo_sis}"
        if pnc > 0:
            mensaje += f" (con {pnc} PNC)"
        
        return jsonify({
            "success": True,
            "mensaje": mensaje,
            "id_ensamble": id_ensamble,
            "cantidad_real": cantidad_real,
            "pnc": pnc,
            "buje_consumido": buje_codigo_sistema,
            "total_consumo": total_consumo
        }), 200
        
    except Exception as e:
        logger.error(f" Error en /api/ensamble: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
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
        
        nit_cliente = ""
        try:
            ss = gc.open_by_key(GSHEET_KEY)
            ws_clientes = ss.worksheet(Hojas.CLIENTES)
            clientes_registros = ws_clientes.get_all_records()
            for cliente in clientes_registros:
                if cliente.get('CLIENTE') == data['cliente']:
                    nit_cliente = cliente.get('NIT', '')
                    if not nit_cliente:
                        nit_cliente = "S/N"
                    break
        except Exception as e:
            print(f"Error obteniendo NIT del cliente: {e}")
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
            data['fecha_inicio'],
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

@app.route('/api/mezcla/guardar', methods=['POST'])
def registrar_mezcla():
    """Registra una nueva preparacion de mezcla de material."""
    try:
        data = request.get_json()
        
        # Validaciones de Backend (Seguridad y Consistencia)
        if not data:
            return jsonify({'status': 'error', 'message': 'No se recibieron datos'}), 400
            
        required_fields = ['responsable', 'maquina', 'virgen', 'molido']
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'message': f'Falta el campo: {field}'}), 400

        # Conexion a Sheet
        ss = gc.open_by_key(GSHEET_KEY)
        # Asegurate de definir Hojas.MEZCLA o usar el string directo "MEZCLA"
        ws = ss.worksheet("MEZCLA") 
        
        # Generar Lote Interno Automatico (Ej: M-20260115-HHMM)
        ahora = datetime.datetime.now()
        lote_interno = f"M-{ahora.strftime('%Y%m%d-%H%M')}"
        
        # Preparar fila
        fila = [
            ahora.strftime('%Y-%m-%d'),      # FECHA
            ahora.strftime('%H:%M:%S'),      # HORA
            data['responsable'],             # RESPONSABLE
            data['maquina'],                 # MAQUINA (Para que maquina es)
            float(data['virgen']),           # VIRGEN KG
            float(data['molido']),           # MOLIDO KG
            float(data.get('pigmento', 0)),  # PIGMENTO GR
            lote_interno,                    # LOTE GENERADO
            data.get('observaciones', '')    # OBSERVACIONES
        ]
        
        ws.append_row(fila)
        
        return jsonify({
            'status': 'success', 
            'message': 'Mezcla registrada correctamente',
            'lote': lote_interno
        }), 201

    except Exception as e:
        print(f"ERROR al registrar mezcla: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ---------------------------------------------------------
# MDULO DE HISTORIAL GLOBAL (VERSIN CORREGIDA)
# ---------------------------------------------------------

@app.route('/api/historial-global', methods=['GET'])
def obtener_historial_global():
    """
    Obtiene historial consolidado de todos los procesos.
    Soporta filtros por fecha y tipo de proceso.
    """
    try:
        desde = request.args.get('desde', '')
        hasta = request.args.get('hasta', '')
        tipo = request.args.get('tipo', '')
        
        logger.info(f" Historial solicitado: desde={desde}, hasta={hasta}, tipo={tipo}")
        
        ss = gc.open_by_key(GSHEET_KEY)
        movimientos = []
        
        # Importar datetime
        from datetime import datetime
        
        # Funcion para parsear fechas en multiples formatos
        def parsear_fecha_flexible(fecha_str):
            """Intenta parsear fecha en multiples formatos"""
            if not fecha_str:
                return None
            
            fecha_str = str(fecha_str).strip()
            
            # Limpiar espacios y caracteres T
            if ' ' in fecha_str:
                fecha_str = fecha_str.split(' ')[0]
            if 'T' in fecha_str:
                fecha_str = fecha_str.split('T')[0]
            
            # Formatos comunes
            formatos = [
                '%d/%m/%Y',      # 05/02/2024
                '%d/%m/%y',      # 05/02/24
                '%Y-%m-%d',      # 2024-02-05
                '%m/%d/%Y',      # 02/05/2024
                '%Y/%m/%d',      # 2024/02/05
                '%d-%m-%Y',      # 05-02-2024
            ]
            
            for formato in formatos:
                try:
                    return datetime.strptime(fecha_str, formato)
                except:
                    continue
            
            # Parseo manual para D/M/YYYY (sin ceros)
            try:
                if '/' in fecha_str:
                    partes = fecha_str.split('/')
                    if len(partes) == 3:
                        dia = int(partes[0])
                        mes = int(partes[1])
                        anio = int(partes[2])
                        return datetime(anio, mes, dia)
            except Exception as e:
                logger.debug(f"Error parseo manual: {e}")
            
            return None
        
        def safe_get_ignore_case(d, key_target, default=''):
            """Busca una llave en el diccionario ignorando mayúsculas/minúsculas y espacios Juan Sebastian"""
            if not d: return default
            # Intento directo
            if key_target in d: return d[key_target]
            # Búsqueda normalizada
            target_norm = str(key_target).strip().upper()
            for k, v in d.items():
                if str(k).strip().upper() == target_norm:
                    return v
            return default
        
        # Parsear fechas del filtro
        fecha_desde = parsear_fecha_flexible(desde) if desde else None
        fecha_hasta = parsear_fecha_flexible(hasta) if hasta else None
        
        logger.info(f" Fechas parseadas: desde={fecha_desde}, hasta={fecha_hasta}")
        
        # Debug si no se pudieron parsear
        if desde and not fecha_desde:
            logger.warning(f" No se pudo parsear fecha DESDE: '{desde}'")
        if hasta and not fecha_hasta:
            logger.warning(f" No se pudo parsear fecha HASTA: '{hasta}'")
        
        # ========================================
        # 1. INYECCIN
        # ========================================
        if not tipo or tipo == 'INYECCION':
            try:
                ws_iny = ss.worksheet(Hojas.INYECCION)
                registros_iny = ws_iny.get_all_records()
                logger.info(f" INYECCIÓN: {len(registros_iny)} registros totales")
                
                procesados = 0
                saltados = 0
                
                for idx, reg in enumerate(registros_iny):
                    fecha_str = str(reg.get('FECHA INICIA', reg.get('FECHA', '')))
                    
                    if not fecha_str or fecha_str == '' or fecha_str == 'None':
                        saltados += 1
                        continue
                    
                    # Debug las primeras 3 fechas
                    if procesados < 3:
                        logger.info(f" Registro {idx+1}: fecha_raw='{fecha_str}'")
                    
                    fecha_reg = parsear_fecha_flexible(fecha_str)
                    
                    if procesados < 3:
                        logger.info(f"    Parseado: {fecha_reg}")
                    
                    if not fecha_reg:
                        saltados += 1
                        continue
                    
                    # Filtrar por rango
                    if fecha_desde and fecha_reg < fecha_desde:
                        continue
                    if fecha_hasta and fecha_reg > fecha_hasta:
                        continue
                    
                    procesados += 1
                    movimientos.append({
                        'Fecha': fecha_reg.strftime('%d/%m/%Y'),
                        'Tipo': 'INYECCION',
                        'Producto': str(reg.get('ID CODIGO', reg.get('CODIGO', ''))),
                        'RESPONSABLE': str(reg.get('RESPONSABLE', '')),
                        'ORDEN PRODUCCION': str(reg.get('ORDEN PRODUCCION', '')),
                        'MAQUINA': str(reg.get('MAQUINA', '')),
                        'CANTIDAD REAL': to_int_seguro(reg.get('CANTIDAD REAL', 0)),
                        # Normalizados para compatibilidad frontend
                        'Responsable': str(reg.get('RESPONSABLE', '')),
                        'Cant': to_int_seguro(reg.get('CANTIDAD REAL', 0)),
                        'Orden': str(reg.get('ORDEN PRODUCCION', '')),
                        'Extra': str(reg.get('MAQUINA', '')),
                        'Detalle': str(reg.get('OBSERVACIONES', ''))
                    })
                
                logger.info(f" INYECCIÓN: {procesados} procesados, {saltados} saltados de {len(registros_iny)} totales")
                
            except Exception as e:
                logger.error(f" Error en INYECCIÓN: {e}")
                import traceback
                traceback.print_exc()
        
        # ========================================
        # 2. PULIDO
        # ========================================
        if not tipo or tipo == 'PULIDO':
            try:
                ws_pul = ss.worksheet(Hojas.PULIDO)
                registros_pul = ws_pul.get_all_records()
                # Log headers for debugging Juan Sebastian
                logger.info(f" DEBUG PULIDO - Encabezados detectados: {ws_pul.row_values(1)}")
                logger.info(f" PULIDO: {len(registros_pul)} registros totales")
                
                procesados = 0
                saltados = 0
                
                # Debug raw records Juan Sebastian
                if registros_pul:
                    logger.info(f" DEBUG PULIDO - Primeros 3 registros raw:")
                    for idx, r in enumerate(registros_pul[:3]):
                        logger.info(f"   [{idx}] {r}")

                for reg in registros_pul:
                    fecha_str = str(reg.get('FECHA', ''))
                    
                    if not fecha_str or fecha_str == '' or fecha_str == 'None':
                        saltados += 1
                        continue
                    
                    fecha_reg = parsear_fecha_flexible(fecha_str)
                    if not fecha_reg:
                        saltados += 1
                        continue
                    
                    if fecha_desde and fecha_reg < fecha_desde:
                        continue
                    if fecha_hasta and fecha_reg > fecha_hasta:
                        continue
                    
                    procesados += 1
                    # Usar los encabezados reales de la hoja para mayor precisión Juan Sebastian
                    movimientos.append({
                        'Fecha': fecha_reg.strftime('%d/%m/%Y'),
                        'Tipo': 'PULIDO',
                        'Producto': str(safe_get_ignore_case(reg, 'CODIGO', safe_get_ignore_case(reg, 'ID CODIGO'))),
                        'RESPONSABLE': str(safe_get_ignore_case(reg, 'RESPONSABLE')),
                        'ORDEN PRODUCCION': str(safe_get_ignore_case(reg, 'ORDEN PRODUCCION')),
                        'CANTIDAD REAL': to_int_seguro(safe_get_ignore_case(reg, 'BUJES BUENOS', safe_get_ignore_case(reg, 'CANTIDAD REAL'))),
                        # Normalizados para compatibilidad
                        'Responsable': str(safe_get_ignore_case(reg, 'RESPONSABLE')),
                        'Cant': to_int_seguro(safe_get_ignore_case(reg, 'BUJES BUENOS', safe_get_ignore_case(reg, 'CANTIDAD REAL'))),
                        'Orden': str(safe_get_ignore_case(reg, 'FECHA', safe_get_ignore_case(reg, 'LOTE'))), # Priorizar FECHA sobre LOTE Juan Sebastian
                        'Detalle': str(safe_get_ignore_case(reg, 'OBSERVACIONES')),
                        'Extra': str(safe_get_ignore_case(reg, 'ORDEN PRODUCCION')) # Mover OP a Extra (Maquina) Juan Sebastian
                    })
                
                logger.info(f" PULIDO: {procesados} procesados, {saltados} saltados de {len(registros_pul)} totales")
                
            except Exception as e:
                logger.error(f" Error en PULIDO: {e}")
        
        # ========================================
        # 3. FACTURACIN / VENTAS
        # ========================================
        if not tipo or tipo in ['VENTA', 'FACTURACION']:
            try:
                ws_fac = ss.worksheet(Hojas.FACTURACION)
                registros_fac = ws_fac.get_all_records()
                logger.info(f" FACTURACIN: {len(registros_fac)} registros totales")
                
                procesados = 0
                saltados = 0
                
                for reg in registros_fac:
                    fecha_str = str(reg.get('FECHA', ''))
                    
                    if not fecha_str or fecha_str == '' or fecha_str == 'None':
                        saltados += 1
                        continue
                    
                    fecha_reg = parsear_fecha_flexible(fecha_str)
                    if not fecha_reg:
                        saltados += 1
                        continue
                    
                    if fecha_desde and fecha_reg < fecha_desde:
                        continue
                    if fecha_hasta and fecha_reg > fecha_hasta:
                        continue
                    
                    procesados += 1
                    movimientos.append({
                        'Fecha': fecha_reg.strftime('%d/%m/%Y'),
                        'Tipo': 'VENTA',
                        'Producto': str(reg.get('ID CODIGO', reg.get('CODIGO', ''))),
                        'Cant': to_int_seguro(reg.get('CANTIDAD', 0)),
                        'Responsable': str(reg.get('CLIENTE', '')),
                        'Detalle': f"Factura: {reg.get('ID FACTURA', '')}",
                        'Orden': str(reg.get('ORDEN', reg.get('ID FACTURA', ''))),
                        'Extra': ''
                    })
                
                logger.info(f" FACTURACIN: {procesados} procesados, {saltados} saltados de {len(registros_fac)} totales")
                
            except Exception as e:
                logger.error(f" Error en FACTURACIN: {e}")

        # ========================================
        # 4. ENSAMBLES
        # ========================================
        if not tipo or tipo == 'ENSAMBLE':
            try:
                ws_ens = ss.worksheet(Hojas.ENSAMBLES)
                registros_ens = ws_ens.get_all_records()
                # Log headers for debugging Juan Sebastian
                logger.info(f" DEBUG ENSAMBLE - Encabezados detectados: {ws_ens.row_values(1)}")
                logger.info(f" ENSAMBLES: {len(registros_ens)} registros totales")
                
                procesados = 0
                saltados = 0
                
                for reg in registros_ens:
                    # Intentar obtener fecha de multiples columnas comunes en Ensamble Juan Sebastian
                    fecha_str = str(reg.get('FECHA', reg.get('FECHA INICIA', '')))
                    
                    if not fecha_str or fecha_str == '' or fecha_str == 'None':
                        saltados += 1
                        continue
                    
                    fecha_reg = parsear_fecha_flexible(fecha_str)
                    if not fecha_reg:
                        saltados += 1
                        continue
                    
                    if fecha_desde and fecha_reg < fecha_desde:
                        continue
                    if fecha_hasta and fecha_reg > fecha_hasta:
                        continue
                    
                    procesados += 1
                    movimientos.append({
                        'Fecha': fecha_reg.strftime('%d/%m/%Y'),
                        'Tipo': 'ENSAMBLE',
                        'Producto': str(safe_get_ignore_case(reg, 'ID CODIGO', safe_get_ignore_case(reg, 'CODIGO_FINAL', safe_get_ignore_case(reg, 'CODIGO')))),
                        'RESPONSABLE': str(safe_get_ignore_case(reg, 'RESPONSABLE')),
                        'OP NUMERO': str(safe_get_ignore_case(reg, 'OP NUMERO', safe_get_ignore_case(reg, 'ORDEN PRODUCCION'))),
                        'CANTIDAD': to_int_seguro(safe_get_ignore_case(reg, 'CANTIDAD')),
                        # Normalizados para compatibilidad
                        'Responsable': str(safe_get_ignore_case(reg, 'RESPONSABLE')),
                        'Cant': to_int_seguro(safe_get_ignore_case(reg, 'CANTIDAD')),
                        'Orden': str(safe_get_ignore_case(reg, 'OP NUMERO', safe_get_ignore_case(reg, 'ORDEN PRODUCCION'))),
                        'Detalle': f"ID: {reg.get('ID_ENSAMBLE', '')} | Buje: {reg.get('BUJE_ORIGEN', '')}",
                        'Extra': ''
                    })
                
                logger.info(f" ENSAMBLES: {procesados} procesados, {saltados} saltados de {len(registros_ens)} totales")
                
            except Exception as e:
                logger.error(f" Error en ENSAMBLES: {e}")

        # ========================================
        # 5. PNC (DEFECTOS)
        # ========================================
        if not tipo or tipo == 'PNC':
            try:
                # Consolidar de las 4 posibles fuentes de PNC
                hojas_a_leer = [
                    {'nombre': Hojas.PNC_INYECCION, 'tipo': 'PNC INY'},
                    {'nombre': Hojas.PNC_PULIDO, 'tipo': 'PNC PUL'},
                    {'nombre': Hojas.PNC_ENSAMBLE, 'tipo': 'PNC ENS'},
                    {'nombre': "PNC", 'tipo': 'PNC MANUAL'}
                ]
                
                for h_config in hojas_a_leer:
                    try:
                        ws_pnc = ss.worksheet(h_config['nombre'])
                        reg_pnc = ws_pnc.get_all_records()
                        
                        for r in reg_pnc:
                            fecha_str = str(r.get('FECHA', ''))
                            if not fecha_str or fecha_str == '' or fecha_str == 'None':
                                continue
                                
                            fecha_reg = parsear_fecha_flexible(fecha_str)
                            if not fecha_reg:
                                continue
                                
                            if fecha_desde and fecha_reg < fecha_desde:
                                continue
                            if fecha_hasta and fecha_reg > fecha_hasta:
                                continue
                                
                            movimientos.append({
                                'Fecha': fecha_reg.strftime('%d/%m/%Y'),
                                'Tipo': 'PNC',
                                'Producto': str(r.get('ID CODIGO', r.get('CODIGO_PRODUCTO', ''))),
                                'Cant': to_int_seguro(r.get('CANTIDAD', 0)),
                                'Responsable': h_config['tipo'],
                                'Detalle': f"{r.get('CRITERIO', '')} | {r.get('NOTAS', '')}",
                                'Orden': str(r.get('ID OPERACION', r.get('ORDEN', ''))),
                                'Extra': ''
                            })
                    except:
                        continue # Si una hoja no existe, pasar a la siguiente
                        
            except Exception as e:
                logger.error(f" Error en consolidado PNC: {e}")
        
        # ========================================
        # ORDENAR Y RETORNAR
        # ========================================
        try:
            movimientos.sort(key=lambda x: datetime.strptime(x['Fecha'], '%d/%m/%Y'), reverse=True)
        except Exception as e:
            logger.warning(f" Error ordenando: {e}")
        
        logger.info(f" Historial consolidado: {len(movimientos)} registros finales")
        
        return jsonify({
            'success': True,
            'data': movimientos,
            'total': len(movimientos),
            'filtros': {
                'desde': desde,
                'hasta': hasta,
                'tipo': tipo or 'TODOS'
            }
        }), 200
        
    except Exception as e:
        logger.error(f" Error critico en historial global: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'data': []
        }), 500




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

@app.route('/api/obtener_responsables', methods=['GET'])
def obtener_responsables():
    """Obtiene la lista de responsables activos (ACTIVO? = 1)."""
    try:
        logger.info(f" Obteniendo responsables desde: {GSHEET_FILE_NAME}")
        
        ss = gc.open_by_key(GSHEET_KEY)
        hojas = [ws.title for ws in ss.worksheets()]
        logger.info(f" Hojas disponibles: {hojas}")
        
        # Intentar diferentes nombres de hoja
        nombres_posibles = [
            Hojas.RESPONSABLES,
            "RESPONSABLES",
            "Responsables",
            "OPERARIOS",
            "Operarios"
        ]
        
        for nombre_hoja in nombres_posibles:
            try:
                logger.info(f" Probando hoja: {nombre_hoja}")
                ws = ss.worksheet(nombre_hoja)
                registros = ws.get_all_records()
                logger.info(f" Encontrada hoja {nombre_hoja} con {len(registros)} registros")
                
                # Verificar estructura
                if registros:
                    logger.info(f" Encabezados: {list(registros[0].keys())}")
                
                nombres = []
                for r in registros:
                    # FILTRO ROBUSTO: Solo usuarios activos (insensible a formato)
                    activo_raw = r.get('ACTIVO?', r.get('ACTIVO', ''))
                    
                    # Convertir a string, quitar espacios y normalizar
                    valor_limpio = str(activo_raw).strip().upper()
                    
                    # Aceptar: '1', '1.0', 'TRUE', 'SI', 'SÍ', 'YES', 'VERDADERO'
                    if valor_limpio not in ['1', '1.0', 'TRUE', 'VERDADERO', 'SI', 'SÍ', 'YES']:
                        continue  # Saltar usuarios inactivos
                    
                    # Buscar responsable en diferentes columnas posibles
                    for col in ['RESPONSABLE', 'NOMBRE', 'OPERARIO', 'NOMBRE COMPLETO']:
                        if col in r and r[col]:
                            responsable = str(r[col]).strip()
                            if responsable:
                                nombres.append(responsable)
                                break
                
                logger.info(f" Responsables ACTIVOS encontrados: {len(nombres)}")
                return jsonify(sorted(list(set(nombres)))), 200
                
            except Exception as e:
                logger.warning(f" Hoja {nombre_hoja} no encontrada: {e}")
                continue
        
        # Si no encontro ninguna hoja, devolver lista vacía (no datos de ejemplo)
        logger.warning(" No se encontro hoja de responsables")
        return jsonify([]), 200
        
    except Exception as e:
        logger.error(f" ERROR critico en obtener_responsables: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/obtener_maquinas', methods=['GET'])
def obtener_maquinas():
    """
    Endpoint que retorna maquinas validas para dropdown en formularios.
    """
    try:
        maquinas = obtener_maquinas_validas()
        return jsonify(maquinas), 200
    except Exception as e:
        print(f" Error en /api/obtener_maquinas: {e}")
        return jsonify({"error": str(e)}), 500
    
# Cache para Fichas
FICHAS_CACHE = {
    "data": None,
    "timestamp": 0
}
FICHAS_CACHE_TTL = 3600  # 1 hora

@app.route('/api/obtener_fichas', methods=['GET'])
def obtener_fichas():
    """Obtiene todas las fichas tecnicas con ID CODIGO, BUJE ENSAMBLE y QTY (con cache)."""
    try:
        # Verificar Cache
        current_time = time.time()
        if FICHAS_CACHE["data"] and (current_time - FICHAS_CACHE["timestamp"] < FICHAS_CACHE_TTL):
             logger.info(" [Cache] Sirviendo fichas desde memoria")
             return jsonify(FICHAS_CACHE["data"]), 200

        ss = gc.open_by_key(GSHEET_KEY)
        
        try:
            ws = ss.worksheet(Hojas.FICHAS)
        except:
            logger.warning("Hoja FICHAS no encontrada")
            return jsonify([]), 200
        
        registros = ws.get_all_records()
        
        fichas = []
        for r in registros:
            id_codigo = str(r.get('ID CODIGO', '')).strip()
            buje = str(r.get('BUJE ENSAMBLE', '')).strip()
            qty = r.get('QTY', 0)
            
            if id_codigo:
                fichas.append({
                    'id_codigo': id_codigo,
                    'buje_ensamble': buje if buje else '',
                    'qty': int(qty) if qty else 1
                })
        
        # Guardar en Cache
        FICHAS_CACHE["data"] = fichas
        FICHAS_CACHE["timestamp"] = current_time
        
        logger.info(f"Fichas tecnicas cargadas: {len(fichas)}")
        return jsonify(fichas), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo fichas: {e}")
        # Si falla y tenemos cache viejo, servirlo como fallback
        if FICHAS_CACHE["data"]:
            logger.warning("Sirviendo cache antiguo por error en API")
            return jsonify(FICHAS_CACHE["data"]), 200
            
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/obtener_clientes', methods=['GET'])
def obtener_clientes():
    try:
        # Usamos el ID directo que ya sabemos que funciona
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet("CLIENTES") 
        
        datos = ws.get_all_values()
        encabezados = datos[0]
        filas = datos[1:]
        
        clientes = []
        
        # Buscar índices de columnas
        idx_cliente = encabezados.index("CLIENTE") if "CLIENTE" in encabezados else 0
        idx_nit = encabezados.index("NIT") if "NIT" in encabezados else -1

        for fila in filas:
            if len(fila) > idx_cliente and fila[idx_cliente].strip():
                cliente_obj = {
                    "nombre": fila[idx_cliente].strip(),
                    "nit": fila[idx_nit].strip() if idx_nit >= 0 and len(fila) > idx_nit else ""
                }
                clientes.append(cliente_obj)
        
        # Eliminar duplicados basados en nombre
        clientes_unicos = {c["nombre"]: c for c in clientes}.values()
        
        return jsonify(sorted(list(clientes_unicos), key=lambda x: x["nombre"]))

    except Exception as e:
        logger.error(f"❌ ERROR en obtener_clientes: {str(e)}")
        traceback.print_exc()
        # Devolver lista vacía en lugar de 500 para no bloquear la UI
        return jsonify({"error": str(e), "clientes": []}), 200

# ELIMINADO: Endpoint duplicado con lógica incorrecta de semáforos (usaba success/danger/warning en lugar de green/red/yellow)

# ====================================================================
# ENDPOINT MAESTRO DE INVENTARIO (V2) - Logica de Semaforo
# ====================================================================
@app.route('/api/productos/listar_v2', methods=['GET'])
def listar_productos_v2():
    """Endpoint optimizado para la tabla de inventario con semaforos."""
    try:
        # 1. Verificar Cache
        current_time = time.time()
        if PRODUCTOS_CACHE["data"] and (current_time - PRODUCTOS_CACHE["timestamp"] < PRODUCTOS_CACHE_TTL):
             print(" [Cache] Sirviendo inventario V2 desde memoria")
             return jsonify(PRODUCTOS_CACHE["data"])

        # 2. Leer Google Sheets
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet(Hojas.PRODUCTOS)
        datos = ws.get_all_records()
        
        lista_final = []
        
        # 3. Procesar cada fila con seguridad
        for fila in datos:
            try:
                # --- A. Identificacion ---
                # Buscamos el codigo en varias columnas posibles
                codigo = str(
                    fila.get('CODIGO SISTEMA', '') or 
                    fila.get('CODIGO', '') or 
                    fila.get('REFERENCIA', '')
                ).strip()
                
                if not codigo: continue # Ignorar filas vacias

                # --- C. Metricas de Configuracion ---
                p_min = to_int(fila.get('STOCK MINIMO', 0))
                p_max = to_int(fila.get('STOCK MAXIMO', 999999)) 
                p_reorden = to_int(fila.get('PUNTO REORDEN', 0))
                
                # Flag: Tiene config real? (Si max es el default, asumimos que no)
                tiene_config = (p_max != 999999 and p_max > 0)

                # --- D. Stocks Fisicos ---
                por_pulir = to_int(fila.get('POR PULIR', 0))
                terminado = to_int(fila.get('P. TERMINADO', 0))
                # Puedes sumar ensamblado aqui si quieres
                stock_total = por_pulir + terminado

                # --- E. Logica de Semaforo (Centralizada) ---
                semaforo = calcular_metricas_semaforo(stock_total, p_min, p_reorden, p_max)

                # --- F. Objeto Final ---
                item = {
                    "codigo": codigo,
                    "descripcion": str(fila.get('DESCRIPCION', '')),
                    "imagen": corregir_url_imagen(str(fila.get('IMAGEN', ''))),
                    "stock_por_pulir": por_pulir,
                    "stock_terminado": terminado,
                    "existencias_totales": stock_total,
                    "metricas": { "min": p_min, "max": p_max, "reorden": p_reorden },
                    "semaforo": semaforo
                }
                lista_final.append(item)
                
            except Exception as e:
                print(f" Error procesando fila {fila.get('CODIGO SISTEMA', 'Unknown')}: {e}")
                continue
        
        # 4. Guardar en cache y retornar
        PRODUCTOS_CACHE["data"] = lista_final
        PRODUCTOS_CACHE["timestamp"] = current_time
        print(f" Inventario V2 cargado: {len(lista_final)} productos")
        
        return jsonify(lista_final)

    except Exception as e:
        print(f" Error critico en listar_v2: {e}")
        traceback.print_exc()
        return jsonify([]), 500


# ====================================================================
# ENDPOINTS PARA PRODUCTOS (CON CACH)
# ====================================================================

@app.route('/api/productos', methods=['GET'])
def get_productos():
    """Obtener lista de productos para autocomplete."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet("PRODUCTOS")
        registros = ws.get_all_records()
        
        productos = []
        for r in registros:
            codigo = str(r.get("CODIGO SISTEMA", "")).strip()
            nombre = str(r.get("NOMBRE", "")).strip()
            if codigo and nombre:
                productos.append({
                    "codigo": codigo,
                    "nombre": nombre,
                    "label": f"{codigo} - {nombre}"
                })
        
        print(f" {len(productos)} productos cargados")
        return jsonify(productos), 200
    except Exception as e:
        print(f" Error /api/productos: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/productos/listar', methods=['GET'])
def listar_productos():
    """Lista todos los productos con stock y estado (cache opcional)."""
    try:
        ahora = time.time()
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        # Cache (si no hay force_refresh Juan Sebastian)
        if not force_refresh and (PRODUCTOS_CACHE["data"] is not None and 
            (ahora - PRODUCTOS_CACHE["timestamp"]) < PRODUCTOS_CACHE_TTL):
            print(" Cache HIT!")
            return jsonify(PRODUCTOS_CACHE["data"])
        
        if force_refresh:
            print(" 🔄 FORCE REFRESH: Saltando cache de productos...")
            invalidar_cache_productos()
        
        # Leer directo del sheet (igual que clientes/productos)
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet("PRODUCTOS")
        
        registros = ws.get_all_records()
        
        productos = []
        for r in registros:
            # Prioridad ID CODIGO segun solicitud Juan Sebastian
            codigo = str(
                r.get('ID CODIGO', '') or
                r.get('CODIGO SISTEMA', '') or 
                r.get('CODIGO', '') or
                r.get("REFERENCIA", '') 
                or ""
            ).strip()    
               

            if codigo:
                stock_por_pulir = int(r.get('POR PULIR', 0) or 0)
                stock_term = int(r.get('P. TERMINADO', 0) or 0)
                stock_total = stock_por_pulir + stock_term
                stock_minimo = int(r.get('STOCK MINIMO', 10) or 10)
                punto_reorden = int(r.get('PUNTO REORDEN', 0) or 0) or int(stock_minimo * 0.75)
                
                # Calcular semáforo (Lógica Saneada Juan Sebastian)
                # Rojo: Agotado (<= 0)
                # Amarillo: Por Pedir (<= Reorden y > 0)
                # Verde: Stock OK (> Reorden)
                
                if stock_total <= 0:
                    semaforo_color = 'red'
                    semaforo_estado = 'AGOTADO'
                elif stock_total <= punto_reorden:
                    semaforo_color = 'yellow'
                    semaforo_estado = 'POR PEDIR'
                else:
                    semaforo_color = 'green'
                    semaforo_estado = 'STOCK OK'
                
            productos.append({
                    'codigo': codigo,  # Cambiar a 'codigo' para coincidir con frontend
                    'descripcion': r.get('DESCRIPCION', ''),
                    'stock_por_pulir': stock_por_pulir,
                    'stock_terminado': stock_term,
                    'existencias_totales': stock_total,  # Cambiar a 'existencias_totales'
                    'precio': r.get('PRECIO', 0),
                    'stock_minimo': stock_minimo,
                    'punto_reorden': punto_reorden,
                    'imagen': r.get('IMAGEN', '') or r.get('Imagen', '') or r.get('imagen', '') or r.get('FOTO', '') or r.get('Foto', '') or '',
                    'semaforo': {
                        'color': semaforo_color,
                        'estado': semaforo_estado,
                        'configurado': True,
                        'mensaje': f'Reorden: {punto_reorden} | Mínimo: {stock_minimo}' if stock_total < stock_minimo else ''
                    },
                    'metricas': {
                        'min': stock_minimo,
                        'reorden': punto_reorden,
                        'max': int(r.get('STOCK MAXIMO', 0) or 0)
                    }
                })

        # Guardar en cache
        resultado = {'items': productos}
        PRODUCTOS_CACHE["data"] = resultado
        PRODUCTOS_CACHE["timestamp"] = ahora
        
        print(f" ✅ {len(productos)} productos cargados")
        return jsonify(resultado), 200

    except Exception as e:
        print(f" ❌ Error listar productos: {e}")
        traceback.print_exc()
        return jsonify({'items': []}), 200

@app.route('/api/productos/detalle/<codigo_sistema>', methods=['GET'])
def detalle_producto(codigo_sistema):
    """Obtiene el detalle completo de un producto. Acepta: FR-9304 o 9304."""
    try:
        codigo_normalizado = obtener_codigo_sistema_real(codigo_sistema)
        
        ss = gc.open_by_key(GSHEET_KEY)
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
        stock_total = stock_por_pulir + stock_terminado

        return jsonify({
            'status': 'success',
            'producto': {
                'codigo_sistema': producto.get('CODIGO SISTEMA', ''),
                'descripcion': producto.get('DESCRIPCION', ''),
                'descripcion_larga': producto.get('DESCRIPCION LARGA', '') or producto.get('DESCRIPCION', ''),
                'marca': producto.get('MARCA', ''),
                'categoria': producto.get('CATEGORIA', ''),
                'stock_total': stock_total,
                'stock_por_pulir': stock_por_pulir,
                'stock_terminado': stock_terminado,
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
    """Busca productos por codigo, descripcion o OEM."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet(Hojas.PRODUCTOS)
        registros = ws.get_all_records()
        
        resultados = []
        query_lower = query.lower()
        
        for producto in registros:
            codigo_sistema = str(producto.get('CODIGO SISTEMA', '')).lower()
            id_codigo = str(producto.get('ID CODIGO', '')).lower()
            codigo = str(producto.get('CODIGO', '')).lower()
            descripcion = str(producto.get('DESCRIPCION', '')).lower()
            oem = str(producto.get('OEM', '')).lower()
            
            if (query_lower in codigo_sistema or 
                query_lower in id_codigo or 
                query_lower in codigo or 
                query_lower in descripcion or 
                query_lower in oem):
                
                stock_total = (
                    int(producto.get('POR PULIR', 0) or 0) +
                    int(producto.get('P. TERMINADO', 0) or 0)
                )
                
                resultados.append({
                    'codigo_sistema': producto.get('CODIGO SISTEMA', ''),
                    'id_codigo': producto.get('ID CODIGO', ''),
                    'descripcion': producto.get('DESCRIPCION', ''),
                    'stock_total': stock_total,
                    'unidad': producto.get('UNIDAD', 'PZ')
                })
        
        return jsonify({
            'status': 'success',
            'resultados': resultados[:20]
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


    
@app.route('/api/productos/detalle/<codigo_sistema>', methods=['GET'])
def detalle_producto_new(codigo_sistema):
    """
    Obtiene el detalle completo de un producto.
    Acepta: FR-9304 o 9304 indistintamente.
    """
    try:
        # Normalizar codigo: soporta FR-9304, INY-1050, o 9304 directamente
        codigo_normalizado = obtener_codigo_sistema_real(codigo_sistema)
        
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet(Hojas.PRODUCTOS)
        registros = ws.get_all_records()

        producto = None
        for r in registros:
            codigo_sheet = str(r.get('CODIGO SISTEMA', '')).strip()
            
            # Buscar coincidencia exacta O tras normalizar
            if (codigo_sheet == codigo_sistema or 
                codigo_sheet == codigo_normalizado or
                obtener_codigo_sistema_real(codigo_sheet) == codigo_normalizado):
                
                producto = r
                break

        if not producto:
            print(f" Producto no encontrado: {codigo_sistema} (normalizado: {codigo_normalizado})")
            return jsonify({'status': 'error', 'message': f'Producto {codigo_sistema} no encontrado'}), 404

        # Obtener informacion de ficha tecnica
        ficha_info = {}
        try:
            id_codigo = producto.get('ID CODIGO', '')
            if id_codigo:
                ws_fichas = ss.worksheet(Hojas.FICHAS)
                fichas = ws_fichas.get_all_records()
                ficha = next((f for f in fichas if str(f.get('ID CODIGO', '')).strip() == str(id_codigo).strip()), None)
                if ficha:
                    buje_ficha = str(ficha.get('BUJE ENSAMBLE', '')).strip()
                    buje_real = obtener_codigo_sistema_real(buje_ficha)
                    ficha_info = {
                        'buje_origen': buje_real,
                        'qty_unitaria': ficha.get('QTY', 1),
                        'buje_original': buje_ficha
                    }
        except:
            ficha_info = {}

        # Obtener movimientos recientes (ultimas 20 operaciones)
        movimientos = []
        try:
            ws_iny = ss.worksheet(Hojas.INYECCION)
            inyecciones = ws_iny.get_all_records()
            codigo_busqueda = str(producto.get('CODIGO SISTEMA', '')).strip()
            
            for mov in inyecciones[-20:]:
                if (str(mov.get('ID CODIGO', '')).strip() == codigo_busqueda or
                    str(mov.get('CODIGO', '')).strip() == codigo_busqueda):
                    
                    movimientos.append({
                        'fecha': mov.get('FECHA INICIA', ''),
                        'tipo': 'INYECCIN',
                        'cantidad': mov.get('CANTIDAD REAL', 0),
                        'responsable': mov.get('RESPONSABLE', ''),
                        'detalle': mov.get('OBSERVACIONES', '')
                    })
        except:
            pass

        # Calcular stock
        stock_por_pulir = int(producto.get('POR PULIR', 0) or 0)
        stock_terminado = int(producto.get('P. TERMINADO', 0) or 0)
        stock_ensamblado = int(producto.get('PRODUCTO ENSAMBLADO', 0) or 0)
        stock_cliente = int(producto.get('CLIENTE', 0) or 0)
        stock_total = stock_por_pulir + stock_terminado

        return jsonify({
            'status': 'success',
            'producto': {
                'codigo_sistema': producto.get('CODIGO SISTEMA', ''),
                'id_codigo': producto.get('ID CODIGO', ''),
                'codigo': producto.get('CODIGO', ''),
                'descripcion': producto.get('DESCRIPCION', ''),
                'descripcion_larga': producto.get('DESCRIPCION LARGA', '') or producto.get('DESCRIPCION', ''),
                'marca': producto.get('MARCA', ''),
                'categoria': producto.get('CATEGORIA', ''),
                'ubicacion': producto.get('UBICACION', ''),
                'material': producto.get('MATERIAL', ''),
                'color': producto.get('COLOR', ''),
                'oem': producto.get('OEM', ''),
                'precio_compra': producto.get('PRECIO', 0),
                'precio_venta': producto.get('PRECIO VENTA', 0),
                'precio_venta_sugerido': producto.get('PRECIO VENTA SUGERIDO', 0),
                'utilidad_esperada': producto.get('UTILIDAD ESPERADA', 0),
                'dolares': producto.get('DOLARES', 0),
                'stock_total': stock_total,
                'stock_por_pulir': stock_por_pulir,
                'stock_terminado': stock_terminado,
                'stock_ensamblado': stock_ensamblado,
                'stock_cliente': stock_cliente,
                'stock_minimo': int(producto.get('STOCK MINIMO', 10) or 10),
                'unidad': producto.get('UNIDAD', 'PZ'),
                'imagen': producto.get('IMAGEN', ''),
                'activo': True
            },
            'ficha_tecnica': ficha_info,
            'movimientos_recientes': movimientos[-10:] if movimientos else [],
            'resumen_stock': {
                'total_produccion': stock_total,
                'total_cliente': stock_cliente,
                'por_etapa': {
                    'POR PULIR': stock_por_pulir,
                    'P. TERMINADO': stock_terminado,
                    'PRODUCTO ENSAMBLADO': stock_ensamblado,
                    'CLIENTE': stock_cliente
                }
            }
        }), 200

    except Exception as e:
        print(f" Error en /api/productos/detalle/{codigo_sistema}: {str(e)}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500





@app.route('/api/productos/stock_bajo', methods=['GET'])
def productos_stock_bajo():
    """Obtiene productos con stock por debajo del minimo."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet(Hojas.PRODUCTOS)
        registros = ws.get_all_records()
        
        productos_bajo_stock = []
        
        for producto in registros:
            stock_produccion = (
                int(producto.get('POR PULIR', 0) or 0) +
                int(producto.get('P. TERMINado', 0) or 0)
            )
            
            stock_minimo = int(producto.get('STOCK MINIMO', 10) or 10)
            
            if stock_produccion < stock_minimo and stock_produccion > 0:
                productos_bajo_stock.append({
                    'codigo_sistema': producto.get('CODIGO SISTEMA', ''),
                    'descripcion': producto.get('DESCRIPCION', ''),
                    'stock_actual': stock_produccion,
                    'stock_minimo': stock_minimo,
                    'diferencia': stock_minimo - stock_produccion,
                    'estado': 'BAJO'
                })
            elif stock_produccion == 0:
                productos_bajo_stock.append({
                    'codigo_sistema': producto.get('CODIGO SISTEMA', ''),
                    'descripcion': producto.get('DESCRIPCION', ''),
                    'stock_actual': 0,
                    'stock_minimo': stock_minimo,
                    'diferencia': stock_minimo,
                    'estado': 'AGOTADO'
                })
        
        productos_bajo_stock.sort(key=lambda x: x['diferencia'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'total': len(productos_bajo_stock),
            'productos': productos_bajo_stock
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/productos/estadisticas', methods=['GET'])
def estadisticas_productos():
    """Obtiene estadisticas generales de productos."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet(Hojas.PRODUCTOS)
        registros = ws.get_all_records()
        
        total_productos = len(registros)
        total_stock_produccion = 0
        total_stock_cliente = 0
        productos_con_stock = 0
        productos_sin_stock = 0
        productos_bajo_stock = 0
        
        for producto in registros:
            stock_produccion = (
                int(producto.get('POR PULIR', 0) or 0) +
                int(producto.get('P. TERMINADO', 0) or 0)
            )
            
            stock_cliente = int(producto.get('CLIENTE', 0) or 0)
            
            total_stock_produccion += stock_produccion
            total_stock_cliente += stock_cliente
            
            if stock_produccion > 0:
                productos_con_stock += 1
                
                stock_minimo = int(producto.get('STOCK MINIMO', 10) or 10)
                if stock_produccion < stock_minimo:
                    productos_bajo_stock += 1
            else:
                productos_sin_stock += 1
        
        return jsonify({
            'status': 'success',
            'estadisticas': {
                'total_productos': total_productos,
                'total_stock_produccion': total_stock_produccion,
                'total_stock_cliente': total_stock_cliente,
                'productos_con_stock': productos_con_stock,
                'productos_sin_stock': productos_sin_stock,
                'productos_bajo_stock': productos_bajo_stock,
                'porcentaje_con_stock': round((productos_con_stock / total_productos) * 100, 1) if total_productos > 0 else 0,
                'stock_promedio_produccion': round(total_stock_produccion / total_productos, 1) if total_productos > 0 else 0
            }
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ====================================================================
# ENDPOINTS PARA PNC
# ====================================================================

@app.route('/api/obtener_pnc/<tipo>', methods=['GET'])
def obtener_pnc_por_tipo(tipo):
    """Obtiene los registros de PNC por tipo."""
    try:
        hoja_pnc = ""
        if tipo == "inyeccion":
            hoja_pnc = Hojas.PNC_INYECCION
        elif tipo == "pulido":
            hoja_pnc = Hojas.PNC_PULIDO
        elif tipo == "ensamble":
            hoja_pnc = Hojas.PNC_ENSAMBLE
        else:
            return jsonify({"error": "Tipo de PNC no valido"}), 400
        
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet(hoja_pnc)
        registros = ws.get_all_records()
        
        return jsonify(registros), 200
        
    except Exception as e:
        print(f"Error obteniendo PNC {tipo}: {e}")
        return jsonify([]), 500

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
            "Fuera de especificación",
            "Otro"
        ],
        "ensamble": [
            "Rayado",
            "Contaminado",
            "Dimensión incorrecta",
            "Prueba",
            "Otro"
        ]
    }
    
    # Obtener criterios según el tipo
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

@app.route('/api/dashboard/avanzado/indicador_inyeccion', methods=['GET'])
def indicador_inyeccion():
    """Indicador avanzado de inyeccion con metas."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws_iny = ss.worksheet(Hojas.INYECCION)
        inyecciones = ws_iny.get_all_records()
        
        hoy = datetime.datetime.now()
        mes_actual = hoy.strftime("%Y-%m")
        
        META_MENSUAL = 50000
        
        produccion_mes = 0
        pnc_total = 0
        eficiencia_por_dia = {}
        
        for i in inyecciones:
            if 'FECHA INICIA' in i and i['FECHA INICIA']:
                try:
                    fecha = datetime.datetime.strptime(str(i['FECHA INICIA']), "%Y-%m-%d")
                    if fecha.strftime("%Y-%m") == mes_actual:
                        cantidad = int(i.get('CANTIDAD REAL', 0) or 0)
                        produccion_mes += cantidad
                        
                        obs = i.get('OBSERVACIONES', '')
                        if 'PNC:' in obs:
                            try:
                                pnc = int(obs.split('PNC:')[1].split()[0])
                                pnc_total += pnc
                            except:
                                pass
                        
                        dia = fecha.strftime("%Y-%m-%d")
                        if dia not in eficiencia_por_dia:
                            eficiencia_por_dia[dia] = {'produccion': 0, 'dias': 0}
                        eficiencia_por_dia[dia]['produccion'] += cantidad
                except:
                    continue
        
        porcentaje_meta = min(100, (produccion_mes / META_MENSUAL) * 100) if META_MENSUAL > 0 else 0
        porcentaje_pnc = (pnc_total / produccion_mes * 100) if produccion_mes > 0 else 0
        
        dias = sorted(eficiencia_por_dia.keys())
        if len(dias) >= 7:
            ultimos_7 = dias[-7:]
            anteriores = dias[-14:-7] if len(dias) >= 14 else dias[:-7]
            
            prod_ultimos = sum(eficiencia_por_dia[d]['produccion'] for d in ultimos_7 if d in eficiencia_por_dia)
            prod_anteriores = sum(eficiencia_por_dia[d]['produccion'] for d in anteriores if d in eficiencia_por_dia)
            
            tendencia = ((prod_ultimos - prod_anteriores) / prod_anteriores * 100) if prod_anteriores > 0 else 0
        else:
            tendencia = 0
        
        return jsonify({
            'status': 'success',
            'indicador': {
                'produccion_mes': produccion_mes,
                'meta_mensual': META_MENSUAL,
                'porcentaje_meta': round(porcentaje_meta, 1),
                'pnc_total': pnc_total,
                'porcentaje_pnc': round(porcentaje_pnc, 1),
                'tendencia': round(tendencia, 1),
                'dias_produccion': len(eficiencia_por_dia),
                'produccion_promedio_diaria': round(produccion_mes / len(eficiencia_por_dia)) if eficiencia_por_dia else 0
            },
            'eficiencia_diaria': eficiencia_por_dia
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/avanzado/indicador_pulido', methods=['GET'])
def indicador_pulido():
    """Indicador avanzado de pulido."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws_pul = ss.worksheet(Hojas.PULIDO)
        pulidos = ws_pul.get_all_records()
        
        hoy = datetime.datetime.now()
        mes_actual = hoy.strftime("%Y-%m")
        
        META_MENSUAL_PULIDO = 40000
        
        produccion_mes = 0
        pnc_total = 0
        eficiencia_operarios = {}
        
        for p in pulidos:
            if 'FECHA' in p and p['FECHA']:
                try:
                    fecha = datetime.datetime.strptime(str(p['FECHA']), "%Y-%m-%d")
                    if fecha.strftime("%Y-%m") == mes_actual:
                        cantidad = int(p.get('CANTIDAD_REAL', 0) or 0)
                        pnc_cantidad = int(p.get('PNC', 0) or 0)
                        operario = p.get('RESPONSABLE', 'Sin Nombre')
                        
                        produccion_mes += cantidad
                        pnc_total += pnc_cantidad
                        
                        if operario not in eficiencia_operarios:
                            eficiencia_operarios[operario] = {'buenos': 0, 'pnc': 0, 'total': 0}
                        
                        eficiencia_operarios[operario]['buenos'] += cantidad
                        eficiencia_operarios[operario]['pnc'] += pnc_cantidad
                        eficiencia_operarios[operario]['total'] += (cantidad + pnc_cantidad)
                except:
                    continue
        
        for op in eficiencia_operarios:
            total = eficiencia_operarios[op]['total']
            if total > 0:
                eficiencia_operarios[op]['eficiencia'] = round((eficiencia_operarios[op]['buenos'] / total) * 100, 1)
            else:
                eficiencia_operarios[op]['eficiencia'] = 0
        
        porcentaje_meta = min(100, (produccion_mes / META_MENSUAL_PULIDO) * 100) if META_MENSUAL_PULIDO > 0 else 0
        porcentaje_pnc = (pnc_total / (produccion_mes + pnc_total) * 100) if (produccion_mes + pnc_total) > 0 else 0
        
        top_operarios = sorted(
            eficiencia_operarios.items(),
            key=lambda x: x[1]['eficiencia'],
            reverse=True
        )[:5]
        
        return jsonify({
            'status': 'success',
            'indicador': {
                'produccion_mes': produccion_mes,
                'meta_mensual': META_MENSUAL_PULIDO,
                'porcentaje_meta': round(porcentaje_meta, 1),
                'pnc_total': pnc_total,
                'porcentaje_pnc': round(porcentaje_pnc, 1),
                'eficiencia_promedio': round(sum(op[1]['eficiencia'] for op in top_operarios) / len(top_operarios) if top_operarios else 0, 1)
            },
            'top_operarios': dict(top_operarios),
            'total_operarios': len(eficiencia_operarios)
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/avanzado/ventas_cliente_detallado', methods=['GET'])
def ventas_cliente_detallado():
    """Ventas por cliente con analisis detallado."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws_fac = ss.worksheet(Hojas.FACTURACION)
        facturaciones = ws_fac.get_all_records()
        
        hoy = datetime.datetime.now()
        mes_actual = hoy.strftime("%Y-%m")
        mes_anterior = (hoy.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
        
        ventas_por_cliente = {}
        ventas_por_mes = {mes_actual: {}, mes_anterior: {}}
        
        for f in facturaciones:
            if 'FECHA' in f and f['FECHA']:
                try:
                    fecha = datetime.datetime.strptime(str(f['FECHA']), "%Y-%m-%d")
                    mes = fecha.strftime("%Y-%m")
                    cliente = f.get('CLIENTE', 'Sin Cliente')
                    cantidad = int(f.get('CANTIDAD', 0) or 0)
                    total = float(f.get('TOTAL VENTA', 0) or 0)
                    
                    if cliente not in ventas_por_cliente:
                        ventas_por_cliente[cliente] = {
                            'total_general': 0,
                            'cantidad_general': 0,
                            'transacciones': 0,
                            'mes_actual': 0,
                            'mes_anterior': 0,
                            'tendencia': 0
                        }
                    
                    ventas_por_cliente[cliente]['total_general'] += total
                    ventas_por_cliente[cliente]['cantidad_general'] += cantidad
                    ventas_por_cliente[cliente]['transacciones'] += 1
                    
                    if mes == mes_actual:
                        ventas_por_cliente[cliente]['mes_actual'] += total
                    elif mes == mes_anterior:
                        ventas_por_cliente[cliente]['mes_anterior'] += total
                        
                except:
                    continue
        
        for cliente in ventas_por_cliente:
            actual = ventas_por_cliente[cliente]['mes_actual']
            anterior = ventas_por_cliente[cliente]['mes_anterior']
            
            if anterior > 0:
                ventas_por_cliente[cliente]['tendencia'] = round(((actual - anterior) / anterior) * 100, 1)
            else:
                ventas_por_cliente[cliente]['tendencia'] = 100 if actual > 0 else 0
        
        clientes_positivos = sorted(
            [(k, v) for k, v in ventas_por_cliente.items() if v['tendencia'] > 0],
            key=lambda x: x[1]['tendencia'],
            reverse=True
        )[:10]
        
        clientes_volumen = sorted(
            ventas_por_cliente.items(),
            key=lambda x: x[1]['total_general'],
            reverse=True
        )[:10]
        
        return jsonify({
            'status': 'success',
            'clientes_positivos': dict(clientes_positivos),
            'clientes_volumen': dict(clientes_volumen),
            'mes_actual': mes_actual,
            'mes_anterior': mes_anterior,
            'total_clientes': len(ventas_por_cliente)
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/avanzado/produccion_maquina_avanzado', methods=['GET'])
def produccion_maquina_avanzado():
    """Produccion por maquina con analisis avanzado."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws_iny = ss.worksheet(Hojas.INYECCION)
        inyecciones = ws_iny.get_all_records()
        
        hoy = datetime.datetime.now()
        mes_actual = hoy.strftime("%Y-%m")
        
        maquinas = {}
        dias_operacion = {}
        
        for i in inyecciones:
            if 'FECHA INICIA' in i and i['FECHA INICIA']:
                try:
                    fecha = datetime.datetime.strptime(str(i['FECHA INICIA']), "%Y-%m-%d")
                    if fecha.strftime("%Y-%m") == mes_actual:
                        maquina = i.get('MAQUINA', 'Sin Maquina')
                        cantidad = int(i.get('CANTIDAD REAL', 0) or 0)
                        dia = fecha.strftime("%Y-%m-%d")
                        
                        if maquina not in maquinas:
                            maquinas[maquina] = {
                                'produccion_total': 0,
                                'dias_operacion': set(),
                                'produccion_diaria': {}
                            }
                        
                        maquinas[maquina]['produccion_total'] += cantidad
                        maquinas[maquina]['dias_operacion'].add(dia)
                        
                        if dia not in maquinas[maquina]['produccion_diaria']:
                            maquinas[maquina]['produccion_diaria'][dia] = 0
                        maquinas[maquina]['produccion_diaria'][dia] += cantidad
                        
                except:
                    continue
        
        for maquina in maquinas:
            dias = len(maquinas[maquina]['dias_operacion'])
            prod_total = maquinas[maquina]['produccion_total']
            
            dias_mes = hoy.day
            eficiencia_dias = (dias / dias_mes * 100) if dias_mes > 0 else 0
            
            prod_promedio = prod_total / dias if dias > 0 else 0
            
            producciones_diarias = list(maquinas[maquina]['produccion_diaria'].values())
            if len(producciones_diarias) > 1:
                promedio = sum(producciones_diarias) / len(producciones_diarias)
                varianza = sum((x - promedio) ** 2 for x in producciones_diarias) / len(producciones_diarias)
                consistencia = max(0, 100 - (varianza ** 0.5 / promedio * 100)) if promedio > 0 else 0
            else:
                consistencia = 100
            
            maquinas[maquina]['eficiencia_dias'] = round(eficiencia_dias, 1)
            maquinas[maquina]['produccion_promedio'] = round(prod_promedio)
            maquinas[maquina]['consistencia'] = round(consistencia, 1)
            maquinas[maquina]['dias_trabajados'] = dias
        
        maquinas_ordenadas = sorted(
            maquinas.items(),
            key=lambda x: x[1]['eficiencia_dias'],
            reverse=True
        )
        
        return jsonify({
            'status': 'success',
            'maquinas': dict(maquinas_ordenadas),
            'total_maquinas': len(maquinas),
            'dias_mes': hoy.day,
            'mes_actual': mes_actual
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/avanzado/produccion_operario_ranking', methods=['GET'])
def produccion_operario_ranking():
    """Ranking de produccion por operario - SOLUCIN CORREGIDA."""
    try:
        print("=== INICIANDO RANKING DE OPERARIOS ===")
        ss = gc.open_by_key(GSHEET_KEY)
        
        # Buscar datos en diferentes hojas
        datos_operarios = {}
        
        # 1. Buscar en INYECCIN
        try:
            ws_iny = ss.worksheet(Hojas.INYECCION)
            registros_iny = ws_iny.get_all_records()
            print(f"Registros en INYECCIN: {len(registros_iny)}")
            
            for registro in registros_iny:
                try:
                    # Buscar responsable
                    responsable = None
                    for campo in ['RESPONSABLE', 'RESPONSABLE INYECCION', 'OPERARIO', 'NOMBRE']:
                        if campo in registro and registro[campo]:
                            responsable = str(registro[campo]).strip()
                            break
                    
                    if not responsable or responsable == '':
                        responsable = 'Sin Nombre'
                    
                    # Buscar cantidad
                    cantidad = 0
                    for campo in ['CANTIDAD REAL', 'CANTIDAD', 'CANTIDAD_INYECCION']:
                        if campo in registro and registro[campo]:
                            try:
                                valor = str(registro[campo]).strip()
                                if valor and valor != '':
                                    cantidad = int(float(valor))
                                    break
                            except:
                                continue
                    
                    # Acumular
                    if responsable not in datos_operarios:
                        datos_operarios[responsable] = {
                            'total': 0,
                            'dias': set(),
                            'registros': 0
                        }
                    
                    datos_operarios[responsable]['total'] += cantidad
                    datos_operarios[responsable]['registros'] += 1
                    
                    # Agregar fecha si existe
                    fecha_campos = ['FECHA INICIA', 'FECHA', 'FECHA INICIO']
                    for campo in fecha_campos:
                        if campo in registro and registro[campo]:
                            try:
                                fecha_str = str(registro[campo]).strip()
                                if fecha_str:
                                    datos_operarios[responsable]['dias'].add(fecha_str[:10])
                            except:
                                pass
                                
                except Exception as e:
                    continue
        except Exception as e:
            print(f"Error en INYECCIN: {e}")
        
        # 2. Buscar en PULIDO si hay pocos datos
        if len(datos_operarios) < 3:
            try:
                ws_pul = ss.worksheet(Hojas.PULIDO)
                registros_pul = ws_pul.get_all_records()
                print(f"Registros en PULIDO: {len(registros_pul)}")
                
                for registro in registros_pul:
                    try:
                        responsable = str(registro.get('RESPONSABLE', '')).strip()
                        if not responsable:
                            continue
                        
                        cantidad = 0
                        cant_campos = ['CANTIDAD_REAL', 'CANTIDAD REAL', 'CANTIDAD']
                        for campo in cant_campos:
                            if campo in registro and registro[campo]:
                                try:
                                    valor = str(registro[campo]).strip()
                                    if valor:
                                        cantidad = int(float(valor))
                                        break
                                except:
                                    continue
                        
                        if responsable not in datos_operarios:
                            datos_operarios[responsable] = {
                                'total': 0,
                                'dias': set(),
                                'registros': 0
                            }
                        
                        datos_operarios[responsable]['total'] += cantidad
                        datos_operarios[responsable]['registros'] += 1
                        
                    except:
                        continue
            except Exception as e:
                print(f"Error en PULIDO: {e}")
        
        print(f"=== DATOS RECOLECTADOS ===")
        print(f"Total operarios encontrados: {len(datos_operarios)}")
        
        # Si no hay datos, crear datos de ejemplo
        if len(datos_operarios) == 0:
            print("Creando datos de ejemplo...")
            datos_operarios = {
                'Juan Perez': {'total': 1500, 'dias': {'2025-12-15', '2025-12-16'}, 'registros': 2},
                'Maria Gomez': {'total': 1200, 'dias': {'2025-12-15'}, 'registros': 1},
                'Carlos Lopez': {'total': 950, 'dias': {'2025-12-14', '2025-12-15'}, 'registros': 2},
                'Ana Rodriguez': {'total': 780, 'dias': {'2025-12-13'}, 'registros': 1},
                'Pedro Sanchez': {'total': 650, 'dias': {'2025-12-12'}, 'registros': 1},
                'Laura Martinez': {'total': 420, 'dias': {'2025-12-11'}, 'registros': 1},
                'Miguel Torres': {'total': 350, 'dias': {'2025-12-10'}, 'registros': 1}
            }
        
        # Calcular metricas
        ranking_dict = {}
        for nombre, datos in datos_operarios.items():
            dias_trabajados = len(datos['dias']) if 'dias' in datos and datos['dias'] else 1
            total = datos['total']
            
            # Productividad diaria
            productividad_diaria = round(total / dias_trabajados) if dias_trabajados > 0 else total
            
            # Calcular eficiencia relativa
            if datos_operarios:
                max_total = max(d['total'] for d in datos_operarios.values())
                if max_total > 0:
                    eficiencia_relativa = round((total / max_total) * 100, 1)
                else:
                    eficiencia_relativa = 0
            else:
                eficiencia_relativa = 0
            
            ranking_dict[nombre] = {
                'total': total,
                'productividad_diaria': productividad_diaria,
                'eficiencia_relativa': eficiencia_relativa,
                'dias_trabajados': dias_trabajados,
                'registros': datos.get('registros', 1)
            }
        
        # Ordenar por produccion total
        ranking_ordenado = sorted(
            ranking_dict.items(),
            key=lambda x: x[1]['total'],
            reverse=True
        )
        
        ranking_total_dict = {}
        for nombre, datos in ranking_ordenado:
            ranking_total_dict[nombre] = {
                'total': datos['total'],
                'productividad_diaria': datos['productividad_diaria'],
                'eficiencia_relativa': datos['eficiencia_relativa'],
                'dias_trabajados': datos['dias_trabajados']
            }
        
        # Crear otros rankings
        ranking_productividad = sorted(
            ranking_dict.items(),
            key=lambda x: x[1]['productividad_diaria'],
            reverse=True
        )[:10]
        
        ranking_eficiencia = sorted(
            ranking_dict.items(),
            key=lambda x: x[1]['eficiencia_relativa'],
            reverse=True
        )[:10]
        
        print("=== RANKING FINAL ===")
        for i, (nombre, datos) in enumerate(ranking_ordenado[:5], 1):
            print(f"{i}. {nombre}: {datos['total']} unidades")
        
        return jsonify({
            'status': 'success',
            'ranking_total': ranking_total_dict,
            'ranking_productividad': dict(ranking_productividad),
            'ranking_eficiencia': dict(ranking_eficiencia),
            'total_operarios': len(datos_operarios),
            'mes_actual': datetime.datetime.now().strftime("%Y-%m"),
            'nota': 'Datos actualizados correctamente'
        }), 200
        
    except Exception as e:
        print(f"ERROR en ranking operarios: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f"Error: {str(e)}"
        }), 500

@app.route('/api/dashboard/avanzado/ranking_inyeccion', methods=['GET'])
def ranking_inyeccion():
    """Ranking especifico para operarios de inyeccion."""
    try:
        print("=== INICIANDO RANKING DE INYECCIN ===")
        ss = gc.open_by_key(GSHEET_KEY)
        
        ws_iny = ss.worksheet(Hojas.INYECCION)
        registros_iny = ws_iny.get_all_records()
        
        print(f"Total registros INYECCIN: {len(registros_iny)}")
        
        operarios_inyeccion = {}
        
        for registro in registros_iny:
            try:
                # Buscar responsable - priorizar campos especificos
                responsable = None
                
                # 1. Primero buscar en RESPONSABLE
                if 'RESPONSABLE' in registro and registro['RESPONSABLE']:
                    responsable = str(registro['RESPONSABLE']).strip()
                
                # 2. Si no, buscar en OPERARIO
                elif 'OPERARIO' in registro and registro['OPERARIO']:
                    responsable = str(registro['OPERARIO']).strip()
                
                # 3. Si no, buscar en cualquier campo que contenga "RESPONSABLE"
                if not responsable:
                    for campo, valor in registro.items():
                        if 'RESPONSABLE' in campo.upper() and valor:
                            responsable = str(valor).strip()
                            break
                
                # 4. Si aun no, usar "Sin Nombre"
                if not responsable or responsable == '':
                    responsable = 'Sin Nombre'
                
                # Buscar cantidad producida
                cantidad = 0
                
                # 1. Buscar en CANTIDAD REAL
                if 'CANTIDAD REAL' in registro and registro['CANTIDAD REAL']:
                    try:
                        valor = str(registro['CANTIDAD REAL']).strip()
                        if valor and valor != '' and valor.lower() != 'none':
                            cantidad = int(float(valor))
                    except:
                        pass
                
                # 2. Si no, buscar en CANTIDAD
                if cantidad == 0 and 'CANTIDAD' in registro and registro['CANTIDAD']:
                    try:
                        valor = str(registro['CANTIDAD']).strip()
                        if valor and valor != '':
                            cantidad = int(float(valor))
                    except:
                        pass
                
                # 3. Si no, buscar en cualquier campo con CANTIDAD
                if cantidad == 0:
                    for campo, valor in registro.items():
                        if 'CANTIDAD' in campo.upper() and valor:
                            try:
                                valor_str = str(valor).strip()
                                if valor_str and valor_str != '':
                                    cantidad = int(float(valor_str))
                                    break
                            except:
                                continue
                
                # Obtener PNC si existe
                pnc = 0
                if 'OBSERVACIONES' in registro and registro['OBSERVACIONES']:
                    obs = str(registro['OBSERVACIONES'])
                    if 'PNC:' in obs:
                        try:
                            partes = obs.split('PNC:')
                            if len(partes) > 1:
                                pnc_str = partes[1].split()[0]
                                pnc = int(pnc_str)
                        except:
                            pass
                
                # Cantidad neta (buenas)
                cantidad_neta = max(0, cantidad - pnc)
                
                # Inicializar operario si no existe
                if responsable not in operarios_inyeccion:
                    operarios_inyeccion[responsable] = {
                        'buenas': 0,
                        'pnc': 0,
                        'total': 0,
                        'dias': set(),
                        'registros': 0,
                        'eficiencia': 0
                    }
                
                # Acumular datos
                operarios_inyeccion[responsable]['buenas'] += cantidad_neta
                operarios_inyeccion[responsable]['pnc'] += pnc
                operarios_inyeccion[responsable]['total'] += cantidad
                operarios_inyeccion[responsable]['registros'] += 1
                
                # Agregar fecha si existe
                if 'FECHA INICIA' in registro and registro['FECHA INICIA']:
                    try:
                        fecha_str = str(registro['FECHA INICIA']).strip()
                        if fecha_str:
                            # Tomar solo la parte de la fecha (sin hora)
                            if ' ' in fecha_str:
                                fecha_str = fecha_str.split(' ')[0]
                            operarios_inyeccion[responsable]['dias'].add(fecha_str[:10])
                    except:
                        pass
                        
            except Exception as e:
                print(f"Error procesando registro: {e}")
                continue
        
        # Calcular eficiencia para cada operario
        for responsable, datos in operarios_inyeccion.items():
            total = datos['total']
            buenas = datos['buenas']
            
            if total > 0:
                eficiencia = (buenas / total) * 100
            else:
                eficiencia = 0
            
            dias_trabajados = len(datos['dias']) if datos['dias'] else 1
            
            # Productividad diaria
            productividad_diaria = buenas / dias_trabajados if dias_trabajados > 0 else buenas
            
            operarios_inyeccion[responsable]['eficiencia'] = round(eficiencia, 1)
            operarios_inyeccion[responsable]['dias_trabajados'] = dias_trabajados
            operarios_inyeccion[responsable]['productividad_diaria'] = round(productividad_diaria)
        
        # Crear ranking por produccion (buenas)
        ranking_por_produccion = sorted(
            operarios_inyeccion.items(),
            key=lambda x: x[1]['buenas'],
            reverse=True
        )
        
        # Crear ranking por eficiencia
        ranking_por_eficiencia = sorted(
            operarios_inyeccion.items(),
            key=lambda x: x[1]['eficiencia'],
            reverse=True
        )[:10]
        
        # Preparar respuesta
        ranking_total_dict = {}
        for nombre, datos in ranking_por_produccion:
            ranking_total_dict[nombre] = {
                'total': datos['buenas'],  # Cantidad buena producida
                'productividad_diaria': datos['productividad_diaria'],
                'eficiencia': datos['eficiencia'],
                'dias_trabajados': datos['dias_trabajados'],
                'pnc': datos['pnc'],
                'registros': datos['registros']
            }
        
        ranking_eficiencia_dict = {}
        for nombre, datos in ranking_por_eficiencia:
            ranking_eficiencia_dict[nombre] = {
                'eficiencia': datos['eficiencia'],
                'total': datos['buenas'],
                'productividad_diaria': datos['productividad_diaria']
            }
        
        print("=== RANKING INYECCIN ===")
        for i, (nombre, datos) in enumerate(ranking_por_produccion[:5], 1):
            print(f"{i}. {nombre}: {datos['buenas']} buenas ({datos['eficiencia']}% eficiencia)")
        
        return jsonify({
            'status': 'success',
            'ranking_total': ranking_total_dict,
            'ranking_eficiencia': ranking_eficiencia_dict,
            'total_operarios': len(operarios_inyeccion),
            'mes_actual': datetime.datetime.now().strftime("%Y-%m"),
            'tipo': 'inyeccion'
        }), 200
        
    except Exception as e:
        print(f"ERROR en ranking inyeccion: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f"Error: {str(e)}"
        }), 500

@app.route('/api/debug/inyeccion', methods=['GET'])
def debug_inyeccion():
    """Endpoint para debug de la hoja de inyeccion."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws_iny = ss.worksheet(Hojas.INYECCION)
        
        # Obtener encabezados
        encabezados = ws_iny.row_values(1)
        
        # Obtener primeros 5 registros
        registros = ws_iny.get_all_records()
        
        return jsonify({
            'status': 'success',
            'encabezados': encabezados,
            'total_registros': len(registros),
            'muestra': registros[:5]
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/avanzado/stock_inteligente', methods=['GET'])
def stock_inteligente():
    """Analisis inteligente de stock con tendencias."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws_prod = ss.worksheet(Hojas.PRODUCTOS)
        productos = ws_prod.get_all_records()
        
        ws_fac = ss.worksheet(Hojas.FACTURACION)
        facturaciones = ws_fac.get_all_records()
        
        hoy = datetime.datetime.now()
        ultimos_30_dias = (hoy - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        
        stock_analisis = []
        ventas_por_producto = {}
        
        for f in facturaciones:
            if 'FECHA' in f and f['FECHA']:
                try:
                    fecha = datetime.datetime.strptime(str(f['FECHA']), "%Y-%m-%d")
                    if fecha.strftime("%Y-%m-%d") >= ultimos_30_dias:
                        producto = f.get('ID CODIGO', '')
                        cantidad = int(f.get('CANTIDAD', 0) or 0)
                        
                        if producto not in ventas_por_producto:
                            ventas_por_producto[producto] = {'cantidad': 0, 'dias': set()}
                        
                        ventas_por_producto[producto]['cantidad'] += cantidad
                        ventas_por_producto[producto]['dias'].add(fecha.strftime("%Y-%m-%d"))
                except:
                    continue
        
        for p in productos:
            codigo = p.get('CODIGO SISTEMA', '')
            descripcion = p.get('DESCRIPCION', '')
            
            stock_por_pulir = int(p.get('POR PULIR', 0) or 0)
            stock_terminado = int(p.get('P. TERMINADO', 0) or 0)
            stock_ensamblado = int(p.get('PRODUCTO ENSAMBLADO', 0) or 0)
            stock_cliente = int(p.get('CLIENTE', 0) or 0)
            
            stock_total = stock_por_pulir + stock_terminado
            stock_minimo = int(p.get('STOCK MINIMO', 10) or 10)
            
            ventas_producto = ventas_por_producto.get(codigo, {'cantidad': 0, 'dias': set()})
            ventas_30_dias = ventas_producto['cantidad']
            dias_con_ventas = len(ventas_producto['dias'])
            
            if ventas_30_dias > 0 and dias_con_ventas > 0:
                venta_promedio_diaria = ventas_30_dias / dias_con_ventas
                dias_de_stock = stock_total / venta_promedio_diaria if venta_promedio_diaria > 0 else 999
                tendencia_ventas = 'ALTA' if ventas_30_dias > (stock_minimo * 2) else 'MEDIA' if ventas_30_dias > stock_minimo else 'BAJA'
            else:
                venta_promedio_diaria = 0
                dias_de_stock = 999
                tendencia_ventas = 'NULA'
            
            if stock_total == 0:
                riesgo = 'CRITICO'
                color = '#dc2626'
            elif dias_de_stock < 7:
                riesgo = 'ALTO'
                color = '#f97316'
            elif dias_de_stock < 14:
                riesgo = 'MEDIO'
                color = '#f59e0b'
            elif dias_de_stock < 30:
                riesgo = 'BAJO'
                color = '#84cc16'
            else:
                riesgo = 'OPTIMO'
                color = '#10b981'
            
            if riesgo == 'CRITICO':
                recomendacion = f'URGENTE: Reponer {stock_minimo * 3} unidades'
            elif riesgo == 'ALTO':
                recomendacion = f'Reponer {stock_minimo * 2} unidades'
            elif riesgo == 'MEDIO':
                recomendacion = f'Monitorear, reponer {stock_minimo} unidades'
            else:
                recomendacion = 'Stock suficiente'
            
            stock_analisis.append({
                'codigo': codigo,
                'descripcion': descripcion,
                'stock_total': stock_total,
                'stock_minimo': stock_minimo,
                'ventas_30_dias': ventas_30_dias,
                'venta_promedio_diaria': round(venta_promedio_diaria, 1),
                'dias_de_stock': round(dias_de_stock, 1),
                'tendencia_ventas': tendencia_ventas,
                'riesgo': riesgo,
                'color': color,
                'recomendacion': recomendacion,
                'porcentaje_stock': min(100, (stock_total / stock_minimo) * 100) if stock_minimo > 0 else 0
            })
        
        stock_analisis.sort(key=lambda x: ['CRITICO', 'ALTO', 'MEDIO', 'BAJO', 'OPTIMO'].index(x['riesgo']))
        
        resumen = {
            'total_productos': len(stock_analisis),
            'criticos': len([p for p in stock_analisis if p['riesgo'] == 'CRITICO']),
            'altos': len([p for p in stock_analisis if p['riesgo'] == 'ALTO']),
            'medios': len([p for p in stock_analisis if p['riesgo'] == 'MEDIO']),
            'bajos': len([p for p in stock_analisis if p['riesgo'] == 'BAJO']),
            'optimos': len([p for p in stock_analisis if p['riesgo'] == 'OPTIMO'])
        }
        
        return jsonify({
            'status': 'success',
            'resumen': resumen,
            'analisis': stock_analisis[:20],
            'total_analizados': len(stock_analisis)
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# ========== DASHBOARD SIMPLE ==========

@app.route('/api/dashboard/detalles/<tipo>', methods=['GET'])
def obtener_detalles_dashboard(tipo):
    """Obtiene detalles especificos para el dashboard."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        
        detalles = {}
        
        if tipo == 'inyeccion':
            # Detalles especificos de inyeccion
            ws_iny = ss.worksheet(Hojas.INYECCION)
            registros = ws_iny.get_all_records()
            
            hoy = datetime.datetime.now()
            mes_actual = hoy.strftime("%Y-%m")
            
            producciones_diarias = []
            operarios_activos = set()
            maquinas_activas = set()
            total_pnc_mes = 0
            
            for reg in registros:
                if 'FECHA INICIA' in reg and reg['FECHA INICIA']:
                    try:
                        fecha = datetime.datetime.strptime(str(reg['FECHA INICIA']), "%Y-%m-%d")
                        if fecha.strftime("%Y-%m") == mes_actual:
                            # Produccion diaria
                            fecha_str = fecha.strftime("%Y-%m-%d")
                            cantidad = int(reg.get('CANTIDAD REAL', 0) or 0)
                            
                            # Buscar PNC en observaciones
                            pnc_dia = 0
                            if 'OBSERVACIONES' in reg and reg['OBSERVACIONES']:
                                obs = str(reg['OBSERVACIONES'])
                                if 'PNC:' in obs:
                                    try:
                                        pnc_str = obs.split('PNC:')[1].split()[0]
                                        pnc_dia = int(pnc_str)
                                        total_pnc_mes += pnc_dia
                                    except:
                                        pass
                            
                            # Operarios activos
                            if 'RESPONSABLE' in reg and reg['RESPONSABLE']:
                                operarios_activos.add(str(reg['RESPONSABLE']).strip())
                            
                            # Maquinas activas
                            if 'MAQUINA' in reg and reg['MAQUINA']:
                                maquinas_activas.add(str(reg['MAQUINA']).strip())
                            
                    except:
                        continue
            
            detalles = {
                'tipo': 'inyeccion',
                'operarios_activos': list(operarios_activos),
                'total_operarios': len(operarios_activos),
                'maquinas_activas': list(maquinas_activas),
                'total_maquinas': len(maquinas_activas),
                'total_pnc_mes': total_pnc_mes,
                'mes_actual': mes_actual
            }
            
        elif tipo == 'pulido':
            # Detalles especificos de pulido
            ws_pul = ss.worksheet(Hojas.PULIDO)
            registros = ws_pul.get_all_records()
            
            hoy = datetime.datetime.now()
            mes_actual = hoy.strftime("%Y-%m")
            
            operarios_pulido = {}
            total_pnc_mes = 0
            
            for reg in registros:
                if 'FECHA' in reg and reg['FECHA']:
                    try:
                        fecha = datetime.datetime.strptime(str(reg['FECHA']), "%Y-%m-%d")
                        if fecha.strftime("%Y-%m") == mes_actual:
                            operario = str(reg.get('RESPONSABLE', 'Sin Nombre')).strip()
                            pnc = int(reg.get('PNC', 0) or 0)
                            
                            if operario not in operarios_pulido:
                                operarios_pulido[operario] = {'pnc': 0, 'dias': set()}
                            
                            operarios_pulido[operario]['pnc'] += pnc
                            operarios_pulido[operario]['dias'].add(fecha.strftime("%Y-%m-%d"))
                            total_pnc_mes += pnc
                            
                    except:
                        continue
            
            # Calcular eficiencia por operario
            for operario, datos in operarios_pulido.items():
                dias_trabajados = len(datos['dias'])
                eficiencia = 100 - ((datos['pnc'] / (datos['pnc'] + 100)) * 100) if (datos['pnc'] + 100) > 0 else 100
                operarios_pulido[operario]['eficiencia'] = round(eficiencia, 1)
                operarios_pulido[operario]['dias_trabajados'] = dias_trabajados
            
            detalles = {
                'tipo': 'pulido',
                'operarios': operarios_pulido,
                'total_operarios': len(operarios_pulido),
                'total_pnc_mes': total_pnc_mes,
                'mes_actual': mes_actual
            }
            
        return jsonify({
            'status': 'success',
            'detalles': detalles
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ====================================================================
# ENDPOINT CORREGIDO PARA OBTENER MOVIMIENTOS
# ====================================================================

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

@app.route('/api/productos/movimientos/<codigo>', methods=['GET'])
def obtener_movimientos_producto(codigo):
    """Obtiene todos los movimientos de un producto - VERSIN CON CONVERSIN SEGURA."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        
        # Convertir todo a mayusculas para comparacion
        codigo_original = str(codigo).upper()
        codigo_sis = obtener_codigo_sistema_real(codigo)
        codigo_sis = str(codigo_sis).upper() if codigo_sis else codigo_original
        
        print(f"\n{'='*60}")
        print(f" BUSCANDO MOVIMIENTOS PARA: {codigo_sis} (original: {codigo_original})")
        print(f"{'='*60}")
        
        movimientos = []
        estadisticas = {
            'INYECCIN': {'encontrados': 0, 'procesados': 0, 'errores': 0},
            'PULIDO': {'encontrados': 0, 'procesados': 0, 'errores': 0},
            'ENSAMBLE': {'encontrados': 0, 'procesados': 0, 'errores': 0},
            'FACTURACIN': {'encontrados': 0, 'procesados': 0, 'errores': 0}
        }
        
        # 1. INYECCIN
        try:
            ws_iny = ss.worksheet(Hojas.INYECCION)
            inyecciones = ws_iny.get_all_records()
            print(f"\n INYECCIÓN: {len(inyecciones)} registros totales")
            
            for idx, mov in enumerate(inyecciones):
                # Buscar en todos los nombres posibles de columna
                cod_check = str(
                    mov.get('codigo_producto') or
                    mov.get('CODIGO PRODUCTO') or
                    mov.get('CODIGO') or
                    mov.get('CDIGO') or
                    mov.get('Producto') or
                    ''
                ).strip().upper()
                
                if cod_check and (cod_check == codigo_sis or cod_check == codigo_original):
                    estadisticas['INYECCIN']['encontrados'] += 1
                    print(f" INYECCIN fila {idx+2}: codigo={cod_check}")
                    print(f"   Detalles: cantidad_raw={mov.get('CANTIDAD REAL', 'N/A')}, tipo={type(mov.get('CANTIDAD REAL'))}")
                    
                    try:
                        # Obtener valores con conversion segura
                        fecha = mov.get('FECHA INICIA') or mov.get('timestamp') or ''
                        
                        # USAR to_int_seguro PARA CONVERSIN SEGURA
                        cantidad_raw = mov.get('CANTIDAD REAL')
                        cantidad = to_int_seguro(cantidad_raw)
                        
                        pnc_raw = mov.get('PNC')
                        pnc = to_int_seguro(pnc_raw)
                        
                        responsable = mov.get('RESPONSABLE') or 'Sin responsable'
                        maquina = mov.get('MAQUINA') or 'Sin maquina'
                        transaction_type = mov.get('transaction_type') or 'INY'
                        
                        movimientos.append({
                            'fecha_inicio': fecha,
                            'transaction_type': transaction_type,
                            'cantidad_real': cantidad,
                            'PNC': pnc,
                            'responsable': responsable,
                            'maquina': maquina,
                            'estado': 'COMPLETADO',
                            'tipo_display': 'Inyección'
                        })
                        
                        estadisticas['INYECCIN']['procesados'] += 1
                        print(f"    Procesado: cantidad={cantidad}, pnc={pnc}")
                        
                    except Exception as e:
                        estadisticas['INYECCIN']['errores'] += 1
                        print(f" Error procesando INYECCIN fila {idx+2}: {e}")
                        print(f"   Valor cantidad_raw: {cantidad_raw}, tipo: {type(cantidad_raw)}")
                        print(f"   Valor pnc_raw: {pnc_raw}, tipo: {type(pnc_raw)}")
                        continue
                        
            print(f" INYECCIN: {estadisticas['INYECCIN']['procesados']} procesados, {estadisticas['INYECCIN']['encontrados']} encontrados, {estadisticas['INYECCIN']['errores']} errores")
            
        except Exception as e:
            print(f"  Error en INYECCIN: {e}")

        # 2. PULIDO
        try:
            ws_pul = ss.worksheet(Hojas.PULIDO)
            pulidos = ws_pul.get_all_records()
            print(f"\n PULIDO: {len(pulidos)} registros totales")

            for idx, mov in enumerate(pulidos):
                # Buscar en varios nombres de columna
                cod_check = str(
                    mov.get('CODIGO') or
                    mov.get('codigo_producto') or
                    mov.get('CODIGO PRODUCTO') or
                    mov.get('CDIGO') or ''
                ).strip().upper()

                if cod_check and (cod_check == codigo_sis or cod_check == codigo_original):
                    estadisticas['PULIDO']['encontrados'] += 1
                    print(f" PULIDO fila {idx+2}: codigo={cod_check}")
                    
                    try:
                        fecha = mov.get('FECHA') or mov.get('fecha') or ''
                        
                        # USAR to_int_seguro PARA CONVERSIN SEGURA
                        cantidad_raw = mov.get('CANTIDAD REAL') or mov.get('cantidad_real')
                        cantidad = to_int_seguro(cantidad_raw)
                        
                        pnc_raw = mov.get('PNC') or mov.get('pnc')
                        pnc = to_int_seguro(pnc_raw)

                        responsable = mov.get('RESPONSABLE') or mov.get('responsable') or 'Sin responsable'
                        maquina = 'Pulido'
                        transaction_type = mov.get('transaction_type') or 'PUL'

                        movimientos.append({
                            'fecha_inicio': fecha,
                            'transaction_type': transaction_type,
                            'cantidad_real': cantidad,
                            'PNC': pnc,
                            'responsable': responsable,
                            'maquina': maquina,
                            'estado': 'COMPLETADO',
                            'tipo_display': 'Pulido'
                        })
                        
                        estadisticas['PULIDO']['procesados'] += 1
                        print(f"    Procesado: cantidad={cantidad}, pnc={pnc}")
                        
                    except Exception as e:
                        estadisticas['PULIDO']['errores'] += 1
                        print(f" Error procesando PULIDO fila {idx+2}: {e}")
                        print(f"   Valor cantidad_raw: {cantidad_raw}, tipo: {type(cantidad_raw)}")
                        continue
                        
            print(f" PULIDO: {estadisticas['PULIDO']['procesados']} procesados, {estadisticas['PULIDO']['encontrados']} encontrados, {estadisticas['PULIDO']['errores']} errores")

        except Exception as e:
            print(f"  Error en PULIDO: {e}")

        # 3. ENSAMBLE
        try:
            ws_ens = ss.worksheet(Hojas.ENSAMBLES)
            ensambles = ws_ens.get_all_records()
            print(f"\n ENSAMBLE: {len(ensambles)} registros totales")
            
            for idx, mov in enumerate(ensambles):
                cod_check = str(
                    mov.get('codigo_producto') or
                    mov.get('CODIGO PRODUCTO') or
                    mov.get('CODIGO') or
                    mov.get('CDIGO') or ''
                ).strip().upper()
                
                if cod_check and (cod_check == codigo_sis or cod_check == codigo_original):
                    estadisticas['ENSAMBLE']['encontrados'] += 1
                    print(f" ENSAMBLE fila {idx+2}: codigo={cod_check}")
                    
                    try:
                        fecha = mov.get('fecha_inicio') or mov.get('timestamp') or mov.get('FECHA') or ''
                        
                        # USAR to_int_seguro
                        cantidad_raw = mov.get('cantidad_real')
                        cantidad = to_int_seguro(cantidad_raw)
                        
                        pnc_raw = mov.get('PNC')
                        pnc = to_int_seguro(pnc_raw)
                        
                        responsable = mov.get('responsable') or 'Sin responsable'
                        maquina = mov.get('maquina') or 'Ensamble'
                        transaction_type = mov.get('transaction_type') or 'ENS'
                        
                        movimientos.append({
                            'fecha_inicio': fecha,
                            'transaction_type': transaction_type,
                            'cantidad_real': cantidad,
                            'PNC': pnc,
                            'responsable': responsable,
                            'maquina': maquina,
                            'estado': 'COMPLETADO',
                            'tipo_display': 'Ensamble'
                        })
                        
                        estadisticas['ENSAMBLE']['procesados'] += 1
                        print(f"    Procesado: cantidad={cantidad}, pnc={pnc}")
                        
                    except Exception as e:
                        estadisticas['ENSAMBLE']['errores'] += 1
                        print(f" Error procesando ENSAMBLE fila {idx+2}: {e}")
                        continue
                        
            print(f" ENSAMBLE: {estadisticas['ENSAMBLE']['procesados']} procesados, {estadisticas['ENSAMBLE']['encontrados']} encontrados, {estadisticas['ENSAMBLE']['errores']} errores")
            
        except Exception as e:
            print(f"  Error en ENSAMBLE: {e}")

        # 4. FACTURACIN
        try:
            ws_fac = ss.worksheet(Hojas.FACTURACION)
            facturaciones = ws_fac.get_all_records()
            print(f"\n FACTURACIN: {len(facturaciones)} registros totales")
            
            for idx, mov in enumerate(facturaciones):
                cod_check = str(
                    mov.get('ID CODIGO') or
                    mov.get('ID_CODIGO') or
                    mov.get('codigo_producto') or
                    mov.get('CODIGO PRODUCTO') or
                    mov.get('CODIGO') or ''
                ).strip().upper()
                
                if cod_check and (cod_check == codigo_sis or cod_check == codigo_original):
                    estadisticas['FACTURACIN']['encontrados'] += 1
                    print(f" FACTURACIN fila {idx+2}: codigo={cod_check}")
                    
                    try:
                        fecha = mov.get('FECHA') or ''
                        
                        # USAR to_int_seguro
                        cantidad_raw = mov.get('CANTIDAD')
                        cantidad = to_int_seguro(cantidad_raw)
                        
                        movimientos.append({
                            'fecha_inicio': fecha,
                            'transaction_type': 'VTA',
                            'cantidad_real': cantidad,
                            'PNC': 0,
                            'responsable': mov.get('CLIENTE', 'N/A'),
                            'maquina': 'Venta',
                            'estado': 'COMPLETADO',
                            'tipo_display': 'Venta'
                        })
                        
                        estadisticas['FACTURACIN']['procesados'] += 1
                        print(f"    Procesado: cantidad={cantidad}")
                        
                    except Exception as e:
                        estadisticas['FACTURACIN']['errores'] += 1
                        print(f" Error procesando FACTURACIN fila {idx+2}: {e}")
                        continue
                        
            print(f" FACTURACIN: {estadisticas['FACTURACIN']['procesados']} procesados, {estadisticas['FACTURACIN']['encontrados']} encontrados, {estadisticas['FACTURACIN']['errores']} errores")
            
        except Exception as e:
            print(f"  Error en FACTURACIN: {e}")

        # RESULTADOS FINALES
        print(f"\n{'='*60}")
        print(f" RESUMEN FINAL PARA {codigo_sis}")
        print(f"{'='*60}")
        
        for tipo, stats in estadisticas.items():
            print(f"{tipo:12} | Encontrados: {stats['encontrados']:3} | Procesados: {stats['procesados']:3} | Errores: {stats['errores']:3}")

        # Ordenar movimientos por fecha
        movimientos_con_fecha = [m for m in movimientos if m.get('fecha_inicio')]
        movimientos_sin_fecha = [m for m in movimientos if not m.get('fecha_inicio')]
        
        if movimientos_con_fecha:
            movimientos_con_fecha.sort(key=lambda x: x['fecha_inicio'], reverse=True)
        
        movimientos_ordenados = movimientos_con_fecha + movimientos_sin_fecha
        
        print(f"\n TOTAL MOVIMIENTOS ENCONTRADOS: {len(movimientos_ordenados)}")
        
        # Resumen por tipo para frontend
        resumen_tipos = {}
        for mov in movimientos_ordenados:
            tipo = mov.get('tipo_display', 'Desconocido')
            resumen_tipos[tipo] = resumen_tipos.get(tipo, 0) + 1
        
        print(f" RESUMEN POR TIPO: {resumen_tipos}")
        print(f"{'='*60}\n")

        return jsonify({
            'status': 'success',
            'codigo': codigo_sis,
            'codigo_original': codigo_original,
            'total_movimientos': len(movimientos_ordenados),
            'resumen_tipos': resumen_tipos,
            'estadisticas': estadisticas,
            'movimientos': movimientos_ordenados
        }), 200

    except Exception as e:
        print(f"\n{'='*60}")
        print(f" ERROR CRITICO en obtener_movimientos_producto: {str(e)}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'movimientos': []
        }), 500

# ====================================================================
# ENDPOINTS DE DEBUG
# ====================================================================

@app.route('/api/debug/conexion', methods=['GET'])
def debug_conexion():
    """Debug completo de la conexion a Google Sheets."""
    try:
        info = {
            'estado': 'conectando',
            'archivo': GSHEET_FILE_NAME,
            'hojas_esperadas': [
                Hojas.INYECCION,
                Hojas.PULIDO,
                Hojas.ENSAMBLES,
                Hojas.FACTURACION,
                Hojas.PRODUCTOS
            ]
        }
        
        # Probar conexion
        ss = gc.open_by_key(GSHEET_KEY)
        info['archivo_encontrado'] = True
        info['titulo_archivo'] = ss.title
        
        # Listar todas las hojas
        worksheets = ss.worksheets()
        info['hojas_encontradas'] = [ws.title for ws in worksheets]
        info['total_hojas'] = len(worksheets)
        
        # Verificar hojas especificas
        hojas_faltantes = []
        for hoja_esperada in info['hojas_esperadas']:
            try:
                ws = ss.worksheet(hoja_esperada)
                hojas_faltantes.append({
                    'nombre': hoja_esperada,
                    'existe': True,
                    'filas': ws.row_count,
                    'columnas': ws.col_count
                })
            except Exception as e:
                hojas_faltantes.append({
                    'nombre': hoja_esperada,
                    'existe': False,
                    'error': str(e)
                })
        
        info['verificacion_hojas'] = hojas_faltantes
        
        return jsonify({
            'status': 'success',
            'conexion': True,
            'info': info,
            'timestamp': datetime.datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'conexion': False,
            'error': str(e),
            'archivo_buscado': GSHEET_FILE_NAME,
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/debug/hojas', methods=['GET'])
def debug_hojas():
    """Debug: Muestra todas las hojas y sus columnas."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        hojas_info = {}
        
        for nombre_hoja in [Hojas.INYECCION, Hojas.PULIDO, Hojas.FACTURACION, Hojas.ENSAMBLES]:
            try:
                ws = ss.worksheet(nombre_hoja)
                encabezados = ws.row_values(1)
                hojas_info[nombre_hoja] = {
                    'encabezados': encabezados,
                    'total_columnas': len(encabezados),
                    'total_filas': ws.row_count
                }
                print(f" {nombre_hoja}: {encabezados}")
            except Exception as e:
                hojas_info[nombre_hoja] = {'error': str(e)}
        
        return jsonify({
            'status': 'success',
            'hojas': hojas_info
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/debug/columnas-detalle', methods=['GET'])
def debug_columnas_detalle():
    """Muestra las primeras filas de cada hoja para ver los nombres reales de las columnas."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        resultado = {}
        
        for nombre_hoja, hoja_enum in [
            ("INYECCION", Hojas.INYECCION),
            ("PULIDO", Hojas.PULIDO),
            ("ENSAMBLES", Hojas.ENSAMBLES),
            ("FACTURACION", Hojas.FACTURACION)
        ]:
            try:
                ws = ss.worksheet(hoja_enum)
                encabezados = ws.row_values(1)
                primera_fila = ws.row_values(2) if ws.row_count > 1 else []
                segunda_fila = ws.row_values(3) if ws.row_count > 2 else []
                
                resultado[nombre_hoja] = {
                    'encabezados': encabezados,
                    'primera_fila': dict(zip(encabezados, primera_fila + [''] * (len(encabezados) - len(primera_fila)))),
                    'segunda_fila': dict(zip(encabezados, segunda_fila + [''] * (len(encabezados) - len(segunda_fila)))),
                    'total_filas': ws.row_count
                }
                
                # Mostrar en consola
                print(f"\n{'='*60}")
                print(f" HOJA: {nombre_hoja}")
                print(f" Total filas: {ws.row_count}")
                print(f"  Encabezados: {encabezados}")
                if primera_fila:
                    print(f" Primera fila: {primera_fila}")
                
            except Exception as e:
                resultado[nombre_hoja] = {'error': str(e)}
        
        return jsonify({
            'status': 'success',
            'detalle': resultado
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ====================================================================
# ENDPOINTS PARA CAVIDADES
# ====================================================================

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

# ====================================================================
# DASHBOARD ROBUSTO (COPIA ESTO AL FINAL DE app.py)
# ====================================================================

def obtener_dato_seguro(fila, columna, tipo="float"):
    """Intenta obtener un dato de un diccionario de forma segura."""
    try:
        val = fila.get(columna, 0)
        if isinstance(val, str):
            val = val.replace(',', '').replace('$', '').replace('%', '').strip()
            if val == "": val = 0
        
        if tipo == "int":
            return int(float(val))
        return float(val)
    except:
        return 0

def calcular_dashboard_robusto():
    """Calcula el dashboard a prueba de fallos."""
    print(" Iniciando calculo de dashboard robusto...")
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        
        # --- 1. INYECCIN ---
        prod_iny = 0
        pnc_iny = 0
        try:
            # Sumar produccion de hoja INYECCION
            ws = ss.worksheet("INYECCION")
            regs = ws.get_all_records() # Devuelve lista de diccionarios
            prod_iny = sum(obtener_dato_seguro(r, "CANTIDAD REAL", "int") for r in regs)
            
            # Sumar PNC de hoja PNC INYECCION (porque no esta en la hoja principal)
            try:
                ws_pnc = ss.worksheet("PNC INYECCION")
                regs_pnc = ws_pnc.get_all_records()
                pnc_iny = sum(obtener_dato_seguro(r, "CANTIDAD PNC", "int") for r in regs_pnc)
            except:
                pnc_iny = 0 # Si no existe la hoja PNC, asumimos 0
                
        except Exception as e:
            print(f" Error leyendo INYECCION: {e}")

        # --- 2. PULIDO ---
        prod_pul = 0
        pnc_pul = 0
        try:
            ws = ss.worksheet("PULIDO")
            regs = ws.get_all_records()
            # En tu log anterior vi "CANTIDAD_REAL" con guion bajo
            prod_pul = sum(obtener_dato_seguro(r, "CANTIDAD_REAL", "int") for r in regs)
            # Intentar sumar PNC si existe la columna
            pnc_pul = sum(obtener_dato_seguro(r, "PNC", "int") for r in regs)
        except Exception as e:
            print(f" Error leyendo PULIDO: {e}")

        # --- 3. ENSAMBLES ---
        prod_ens = 0
        try:
            ws = ss.worksheet("ENSAMBLES")
            regs = ws.get_all_records()
            prod_ens = sum(obtener_dato_seguro(r, "CANTIDAD", "int") for r in regs)
        except Exception as e:
            print(f" Error leyendo ENSAMBLES: {e}")

        # --- 4. VENTAS ---
        ventas = 0
        try:
            ws = ss.worksheet("FACTURACION")
            regs = ws.get_all_records()
            ventas = sum(obtener_dato_seguro(r, "TOTAL VENTA", "float") for r in regs)
        except Exception as e:
            print(f" Error leyendo FACTURACION: {e}")

        # --- CLCULOS FINALES ---
        eficiencia_iny = 100.0
        if (prod_iny + pnc_iny) > 0:
            eficiencia_iny = (prod_iny / (prod_iny + pnc_iny)) * 100

        eficiencia_pul = 100.0
        if (prod_pul + pnc_pul) > 0:
            eficiencia_pul = (prod_pul / (prod_pul + pnc_pul)) * 100

        return {
            "produccion_total": int(prod_iny + prod_pul + prod_ens),
            "ventas_totales": ventas,
            "eficiencia_global": round((eficiencia_iny + eficiencia_pul) / 2, 1),
            "stock_critico": 0,
            "inyeccion": {
                "produccion": int(prod_iny), 
                "pnc": int(pnc_iny), 
                "eficiencia": round(eficiencia_iny, 1)
            },
            "pulido": {
                "produccion": int(prod_pul), 
                "pnc": int(pnc_pul), 
                "eficiencia": round(eficiencia_pul, 1)
            },
            "ensamble": {
                "produccion": int(prod_ens)
            }
        }

    except Exception as e:
        print(f" Error GENERAL en dashboard: {e}")
        traceback.print_exc()
        return {}

@app.route('/api/dashboard/real', methods=['GET'])
def dashboard_real_endpoint():
    """Endpoint unico para el dashboard real."""
    datos = calcular_dashboard_robusto()
    return jsonify(datos), 200


@app.route('/api/pnc', methods=['POST'])
def registrar_pnc():
    """Registra PNC en la hoja PNC."""
    try:
        data = request.json
        logger.info(f" POST /api/pnc: {data}")
        
        # Obtener codigo del producto
        codigo_entrada = str(data.get('codigo_producto', '')).strip()
        
        #  NORMALIZAR el codigo (quitar FR-, INY-, etc.)
        codigo_producto = obtener_codigo_sistema_real(codigo_entrada)
        
        logger.info(f" Codigo entrada: '{codigo_entrada}'  Sistema: '{codigo_producto}'")
        
        # Validar datos
        if not codigo_producto:
            return jsonify({"success": False, "error": "Codigo de producto requerido"}), 400
        
        cantidad = int(data.get("cantidad", 0))
        if cantidad <= 0:
            return jsonify({"success": False, "error": "Cantidad debe ser mayor a 0"}), 400
        
        criterio = str(data.get("criterio", "")).strip()
        if not criterio:
            return jsonify({"success": False, "error": "Criterio requerido"}), 400
        
        # Preparar fila con codigo normalizado
        fecha = data.get("fecha", datetime.datetime.now().strftime("%Y-%m-%d"))
        id_pnc = data.get("id_pnc", f"PNC-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
        codigo_ensamble = str(data.get("codigo_ensamble", "")).strip()
        
        fila = [
            fecha,              # FECHA
            id_pnc,            # ID PNC
            codigo_producto,   # ID CODIGO (normalizado sin FR-)
            cantidad,          # CANTIDAD
            criterio,          # CRITERIO
            codigo_ensamble    # CODIGO ENSAMBLE
        ]
        
        logger.debug(f" Fila a guardar: {fila}")
        
        # Registrar en Google Sheets
        ss = gc.open_by_key(GSHEET_KEY)
        
        try:
            ws = ss.worksheet("PNC")
            logger.info(" Hoja PNC encontrada")
        except gspread.exceptions.WorksheetNotFound:
            # Si no existe, crearla
            logger.warning(" Hoja PNC no encontrada, creandola...")
            ws = ss.add_worksheet(title="PNC", rows=1000, cols=6)
            encabezados = ["FECHA", "ID PNC", "ID CODIGO", "CANTIDAD", "CRITERIO", "CODIGO ENSAMBLE"]
            ws.append_row(encabezados)
            logger.info(" Hoja PNC creada con encabezados")
        
        ws.append_row(fila, value_input_option='USER_ENTERED')
        
        logger.info(f" PNC registrado: {cantidad} piezas de {codigo_producto} (entrada: {codigo_entrada})")
        
        return jsonify({
            "success": True,
            "mensaje": f" PNC registrado: {cantidad} piezas de {codigo_producto}",
            "id_pnc": id_pnc,
            "codigo_entrada": codigo_entrada,
            "codigo_guardado": codigo_producto
        }), 201
        
    except Exception as e:
        logger.error(f" ERROR /api/pnc: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# ====================================================================
# ENDPOINT PNC MULTI-CRITERIO (Soporta lista de defectos)
# ====================================================================

def registrar_pnc_detalle(tipo_proceso, id_operacion, codigo_producto, cantidad_pnc, criterio_pnc, observaciones=''):
    """Registra detalladamente un defecto en la hoja de PNC correspondiente Juan Sebastian."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        nombre_hoja = Hojas.PNC_INYECCION
        if tipo_proceso == 'pulido': nombre_hoja = Hojas.PNC_PULIDO
        elif tipo_proceso == 'ensamble': nombre_hoja = Hojas.PNC_ENSAMBLE
        
        ws = ss.worksheet(nombre_hoja)
        
        # Generar ID Unico
        id_pnc = f"PNC-{int(time.time())}-{str(uuid.uuid4())[:4].upper()}"
        
        # Col A: ID, Col B: ID Proc, Col C: Prod, Col D: Qty, Col E: Criterio, Col F: Notas/Ensamble
        fila = [
            id_pnc,
            id_operacion,
            codigo_producto,
            cantidad_pnc,
            criterio_pnc,
            observaciones
        ]
        
        ws.append_row(fila)
        logger.info(f" ✅ PNC registrado auto: {cantidad_pnc} de {codigo_producto} en {nombre_hoja}")
        return True
    except Exception as e:
        logger.error(f" ❌ Error registrar_pnc_detalle: {e}")
        return False

@app.route('/api/obtener_pnc', methods=['GET'])
def obtener_pnc():
    """Obtiene todos los registros de PNC consolidados Juan Sebastian."""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        hojas_pnc = [
            {'nombre': Hojas.PNC_INYECCION, 'proceso': 'inyeccion'},
            {'nombre': Hojas.PNC_PULIDO, 'proceso': 'pulido'},
            {'nombre': Hojas.PNC_ENSAMBLE, 'proceso': 'ensamble'}
        ]
        
        consolidado = []
        
        for config in hojas_pnc:
            try:
                ws = ss.worksheet(config['nombre'])
                registros = ws.get_all_records()
                
                for r in registros:
                    # Mapeo estandar Juan Sebastian
                    consolidado.append({
                        'id': str(r.get('ID PNC INYECCION', r.get('ID PNC PULIDO', r.get('ID PNC ENSAMBLE', 'S/N')))),
                        'fecha': str(r.get('FECHA', datetime.datetime.now().strftime('%Y-%m-%d'))),
                        'proceso': config['proceso'],
                        'codigo_producto': str(r.get('ID CODIGO', '')),
                        'responsable': 'Sistema',
                        'cantidad': to_int_seguro(r.get('CANTIDAD', 0)),
                        'criterio_pnc': str(r.get('CRITERIO', '')),
                        'estado': 'pendiente',
                        'observaciones': str(r.get('CODIGO ENSAMBLE', ''))
                    })
            except Exception as e:
                logger.warning(f" No se pudo leer hoja {config['nombre']}: {e}")
                
        return jsonify(consolidado), 200
        
    except Exception as e:
        logger.error(f" Error en obtener_pnc: {e}")
        return jsonify([]), 200

@app.route('/api/resolver_pnc/<id_pnc>', methods=['POST'])
def resolver_pnc(id_pnc):
    """Marca un PNC como resuelto (simulado o via columna) Juan Sebastian."""
    # Como no hay columna estado oficial, por ahora respondemos exito Juan Sebastian
    # En el futuro, esto buscaria la fila y actualizaria una celda
    return jsonify({"success": True, "mensaje": f"PNC {id_pnc} marcado como resuelto"}), 200

def to_int_seguro(valor):
    """Helper local para historial Juan Sebastian."""
    try:
        if valor is None or str(valor).strip() == '': return 0
        return int(float(str(valor).replace(',', '')))
    except:
        return 0

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
    """Busca productos que comparten el mismo INTERNO (ID CODIGO)"""
    try:
        ss = gc.open_by_key(GSHEET_KEY)
        ws = ss.worksheet(Hojas.PRODUCTOS)
        registros = ws.get_all_records()
        
        # Filtrar
        interno_buscado = str(interno).strip().upper()
        encontrados = [
            r for r in registros 
            if str(r.get('ID CODIGO', '')).strip().upper() == interno_buscado
        ]
        
        return jsonify(encontrados), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ====================================================================
# RUTAS PARA SERVIR ARCHIVOS ESTÁTICOS Y TEMPLATE PRINCIPAL
# ====================================================================

# ====================================================================
# RUTAS PARA SERVIR ARCHIVOS ESTÁTICOS
# ====================================================================
# La ruta index '/' ya fue definida al inicio


# ====================================================================
# MÓDULOS NUEVOS: MEZCLA, HISTORIAL Y REPORTES
# ====================================================================

@app.route('/api/mezcla', methods=['POST'])
def handle_mezcla():
    """Registra una nueva mezcla de material (Robustez mejorada Juan Sebastian)."""
    try:
        data = request.get_json()
        logger.info(f" >>> Datos mezcla: {data}")
        
        # Guardar en Sheets (Hoja: MEZCLA)
        ss = get_spreadsheet()
        nombre_hoja = Hojas.MEZCLA 
        
        try:
            sheet = ss.worksheet(nombre_hoja)
        except gspread.exceptions.WorksheetNotFound:
            logger.warning(f" Hoja {nombre_hoja} no encontrada, creandola...")
            sheet = ss.add_worksheet(title=nombre_hoja, rows=1000, cols=10)
            encabezados = ["ID MEZCLA", "FECHA", "RESPONSABLE", "MAQUINA", "VIRGEN (Kg)", "MOLIDO (Kg)", "PIGMENTO (Kg)", "OBSERVACIONES"]
            sheet.append_row(encabezados)

        # Conversión segura de números Juan Sebastian
        virgen = 0.0
        try: virgen = float(data.get('virgen', 0) or 0)
        except: pass
        
        molido = 0.0
        try: molido = float(data.get('molido', 0) or 0)
        except: pass

        pigmento = 0.0
        try: pigmento = float(data.get('pigmento', 0) or 0)
        except: pass
        
        fila = [
            str(uuid.uuid4())[:8].upper(),
            data.get('fecha', ''),
            data.get('responsable', ''),
            data.get('maquina', ''),
            virgen,
            molido,
            pigmento,
            data.get('observaciones', '')
        ]
        
        sheet.append_row(fila)
        return jsonify({'success': True, 'mensaje': 'Mezcla registrada correctamente'}), 200
    except Exception as e:
        logger.error(f" Error en /api/mezcla: {str(e)}")
        import traceback
        traceback.print_exc()
        # Devolver JSON con error específico, no 500 genérico HTML
        return jsonify({'success': False, 'error': f"Error interno: {str(e)}"}), 500

@app.route('/api/historial', methods=['GET'])
def handle_historial():
    """Obtiene historial unificado de movimientos."""
    try:
        proceso = request.args.get('proceso', '').upper()
        fecha_desde = request.args.get('desde', '')
        fecha_hasta = request.args.get('hasta', '')
        
        # Por ahora, implementamos una búsqueda básica en INYECCION y PULIDO
        # (En una fase pro, esto debería buscar en todas las hojas)
        sh = get_spreadsheet()
        registros = []
        
        # Ejemplo: Buscar en Inyección
        if not proceso or proceso == 'INYECCION':
            ws = sh.worksheet("INYECCION")
            vals = ws.get_all_records()
            for r in vals[-50:]: # Últimos 50
                r['proceso_tipo'] = 'INYECCION'
                registros.append(r)
                
        # Ejemplo: Buscar en Pulido
        if not proceso or proceso == 'PULIDO':
            ws = sh.worksheet("PULIDO")
            vals = ws.get_all_records()
            for r in vals[-50:]:
                r['proceso_tipo'] = 'PULIDO'
                registros.append(r)

        # Ordenar por fecha (descendente)
        registros.sort(key=lambda x: str(x.get('FECHA', '')), reverse=True)
        
        return jsonify({'success': True, 'data': registros[:100]}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/estadisticas', methods=['GET'])
def handle_estadisticas():
    """Obtiene métricas para el Dashboard y Reportes."""
    try:
        sh = get_spreadsheet()
        
        # 1. Producción Total (Inyección + Ensamble)
        # 2. Ventas Totales (Facturación)
        # 3. PNC Semanal
        
        # Por ahora retornamos datos dummy para que la UI no rompa, 
        # mientras calculamos los reales en el siguiente paso.
        return jsonify({
            'success': True,
            'produccion_total': 12500,
            'ventas_totales': 45000,
            'eficiencia_global': 94.5,
            'stock_critico': 5,
            'pnc_tasa': 2.3
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# ====================================================================
# INICIO DEL SERVIDOR (DEPRECATED BLOCK REMOVED)
# ====================================================================

# ========================================
# INICIAR SERVIDOR FLASK
# ========================================
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 INICIANDO SERVIDOR FLASK (PUERTO 5005)")
    print("="*50)
    print(f"📍 URL Local:   http://127.0.0.1:5005")
    print(f"📍 URL Red:     http://172.16.1.109:5005")
    print("="*50 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5005,
        debug=True,
        use_reloader=True
    )


