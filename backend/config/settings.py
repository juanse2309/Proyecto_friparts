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

