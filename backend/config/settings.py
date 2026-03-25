"""
Configuración centralizada de la aplicación.
Carga variables desde .env y valida que existan.
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Settings:
    """Configuración global de la aplicación."""
    
    # Google Sheets
    GSHEET_KEY = os.getenv('GSHEET_KEY', '1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM')
    GSHEET_FILE_NAME = os.getenv('GSHEET_FILE_NAME', 'BASES PARA NUEVA APP')
    
    # Google Drive Reports Folder (New!)
    DRIVE_REPORTS_FOLDER_ID = os.getenv('DRIVE_REPORTS_FOLDER_ID', '1qI-v_B-0C1y2D3E4F5G6H7I8J9K0L1M2') # Placeholder ID
    
    # Cache
    CACHE_TTL = int(os.getenv('CACHE_TTL', 120))
    CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    ENV = os.getenv('FLASK_ENV', 'development')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    
    # Credenciales
    GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')
    CREDENTIALS_PATHS = [
        "credentials_apps.json",
        "/etc/secrets/credentials_apps.json",
        "./config/credentials_apps.json"
    ]


class Hojas:
    """Nombres de las hojas en Google Sheets (Friparts)."""
    INYECCION = "INYECCION"
    PNC_INYECCION = "PNC INYECCION"
    PNC_PULIDO = "PNC PULIDO"
    PNC_ENSAMBLE = "PNC ENSAMBLE"
    PNC = "PNC"
    PRODUCTOS = "PRODUCTOS"
    ENSAMBLES = "ENSAMBLES"
    FICHAS = "FICHAS"
    RESPONSABLES = "RESPONSABLES"
    PULIDO = "PULIDO"
    FACTURACION = "FACTURACION"
    CLIENTES = "DB_Clientes"
    PEDIDOS = "PEDIDOS"
    DB_PRODUCTOS = "DB_Productos"
    PARAMETROS_INVENTARIO = "PARAMETROS_INVENTARIO"
    ORDENES_DE_COMPRA = "ORDENES_DE_COMPRA"
    DB_PROVEEDORES = "DB_PROVEEDORES"
    FICHAS_INT_CAR = "FICHAS_INT_CAR"
    CONTROL_ASISTENCIA = "CONTROL_ASISTENCIA"
    CORTES_NOMINA = "CORTES_NOMINA"

class Almacenes:
    """Nombres de almacenes estandarizados."""
    POR_PULIR = "POR PULIR"
    TERMINADO = "P. TERMINADO"
    ENSAMBLADO = "PRODUCTO ENSAMBLADO"
    CLIENTE = "CLIENTE"
    
    # Mapeo para normalización (FIX: typo duplicado)
    MAPEO = {
        'POR PULIR': 'POR PULIR',
        'P. TERMINADO': 'P. TERMINADO',
        'PRODUCTO ENSAMBLADO': 'PRODUCTO ENSAMBLADO',
        'PRODUCTO ENSAMBLado': 'PRODUCTO ENSAMBLADO',
        'CLIENTE': 'CLIENTE'
    }
    
    @classmethod
    def normalizar(cls, almacen: str) -> str:
        return cls.MAPEO.get(almacen, almacen)
    
    @classmethod
    def es_valido(cls, almacen: str) -> bool:
        return almacen in cls.MAPEO


class TenantConfig:
    """
    Diccionario de contexto multi-tenant.
    Mapea un nombre de recurso lógico al nombre real de la hoja en Google Sheets
    dependiendo de la empresa (tenant) activa.

    Uso:
        hoja = TenantConfig.get('frimetals', 'PRODUCTOS')
        # → 'METALS_PRODUCTOS'
    """

    _MAP: dict = {
        # ----------------------------------------------------------------
        # FRIPARTS  (empresa original)
        # ----------------------------------------------------------------
        "friparts": {
            "PRODUCTOS":    "PRODUCTOS",
            "DB_PRODUCTOS": "DB_Productos",
            "CLIENTES":     "DB_Clientes",
            "PEDIDOS":      "PEDIDOS",
            "PERSONAL":     "RESPONSABLES",
        },
        # ----------------------------------------------------------------
        # FRIMETALS  (nueva unidad de negocio)
        # ----------------------------------------------------------------
        "frimetals": {
            "PRODUCTOS":    "METALS_PRODUCTOS",
            "DB_PRODUCTOS": "METALS_PRODUCTOS",  # una sola hoja maestra
            "CLIENTES":     "METALS_CLIENTES",
            "PEDIDOS":      "METALS_PEDIDOS",
            "PERSONAL":     "METALS_PERSONAL",
        },
    }

    @classmethod
    def get(cls, tenant: str, recurso: str) -> str:
        """
        Retorna el nombre real de la hoja para el tenant y recurso dados.

        Args:
            tenant:  'friparts' | 'frimetals'
            recurso: clave lógica, ej. 'PRODUCTOS', 'CLIENTES', 'PEDIDOS'

        Returns:
            Nombre exacto de la hoja en Google Sheets.

        Raises:
            ValueError: si el tenant o el recurso no están registrados.
        """
        tenant = tenant.lower()
        if tenant not in cls._MAP:
            raise ValueError(f"Tenant desconocido: '{tenant}'. Valores válidos: {list(cls._MAP)}")
        hoja = cls._MAP[tenant].get(recurso)
        if hoja is None:
            raise ValueError(
                f"Recurso '{recurso}' no definido para tenant '{tenant}'. "
                f"Disponibles: {list(cls._MAP[tenant])}"
            )
        return hoja

    @classmethod
    def tenants(cls) -> list:
        """Retorna la lista de tenants registrados."""
        return list(cls._MAP.keys())
