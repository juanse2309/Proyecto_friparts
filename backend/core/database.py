import json
import os
import gspread
import threading
from google.oauth2.service_account import Credentials
from backend.config.settings import Settings
import logging

logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    """
    Gestión de conexión a Google Sheets con Thread-Local Storage.
    Permite el uso seguro con Gunicorn gthread.
    """
    _instance = None
    _lock = threading.Lock()
    _local = threading.local()  # Almacenamiento local por hilo

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self):
        """Retorna el cliente gspread exclusivo para el hilo actual."""
        if not hasattr(self._local, 'client'):
            logger.info(f"Iniciando nueva conexión GSheets para hilo {threading.get_ident()}")
            self._conectar()
        return self._local.client

    @property
    def spreadsheet(self):
        """Retorna el spreadsheet exclusivo para el hilo actual."""
        if not hasattr(self._local, 'spreadsheet'):
            self._conectar()
        return self._local.spreadsheet

    def _conectar(self):
        """Establece conexión y la guarda en el almacenamiento local del hilo."""
        try:
            creds = self._cargar_credenciales()
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(Settings.GSHEET_KEY)
            
            # Guardar en thread-local
            self._local.client = client
            self._local.spreadsheet = spreadsheet
            
            logger.info(f"Conexión establecida para hilo {threading.get_ident()}: {Settings.GSHEET_FILE_NAME}")
        except Exception as e:
            logger.error(f"Error conectando a Google Sheets (Hilo {threading.get_ident()}): {e}")
            raise

    def _cargar_credenciales(self) -> Credentials:
        """Carga credenciales desde variable de entorno o archivo."""
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # 1. Intentar desde variable de entorno
        creds_json = Settings.GOOGLE_CREDENTIALS_JSON
        if creds_json:
            try:
                # logger.info("Cargando credenciales desde variable de entorno...")
                creds_info = json.loads(creds_json)
                return Credentials.from_service_account_info(creds_info, scopes=scope)
            except json.JSONDecodeError as e:
                logger.error(f"Error en formato JSON: {e}")
        
        # 2. Intentar desde archivo
        # logger.info("Buscando archivo de credenciales...")
        for path in Settings.CREDENTIALS_PATHS:
            if os.path.exists(path):
                # logger.info(f"Credenciales encontradas en: {path}")
                return Credentials.from_service_account_file(path, scopes=scope)
        
        raise FileNotFoundError(
            "No se encontraron credenciales. "
            "Configura GOOGLE_CREDENTIALS_JSON o coloca credentials_apps.json"
        )
    
    def get_worksheet(self, nombre: str):
        """Obtiene una hoja por nombre usando la conexión del hilo actual."""
        try:
            return self.spreadsheet.worksheet(nombre)
        except gspread.exceptions.WorksheetNotFound:
            logger.warning(f"Hoja '{nombre}' no encontrada")
            return None
    
    def get_or_create_worksheet(self, nombre: str, rows: int = 1000, cols: int = 20):
        """Obtiene una hoja o la crea si no existe."""
        ws = self.get_worksheet(nombre)
        if ws is None:
            logger.info(f"Creando hoja '{nombre}'...")
            ws = self.spreadsheet.add_worksheet(title=nombre, rows=rows, cols=cols)
        return ws


# Instancia singleton global
# (La gestión de hilos ocurre internamente en la propiedad .client)
sheets_client = GoogleSheetsClient()
