"""
Gestión centralizada de conexión a Google Sheets.
Implementa patrón Singleton para evitar múltiples conexiones.
"""
import json
import os
import gspread
from google.oauth2.service_account import Credentials
from backend.config.settings import Settings
import logging

logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """Cliente singleton para Google Sheets."""
    
    _instance = None
    _client = None
    _spreadsheet = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._conectar()
    
    def _conectar(self):
        """Establece conexión con Google Sheets."""
        try:
            creds = self._cargar_credenciales()
            self._client = gspread.authorize(creds)
            self._spreadsheet = self._client.open_by_key(Settings.GSHEET_KEY)
            logger.info(f"Conectado a Google Sheets: {Settings.GSHEET_FILE_NAME}")
        except Exception as e:
            logger.error(f"Error conectando a Google Sheets: {e}")
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
                logger.info("Cargando credenciales desde variable de entorno...")
                creds_info = json.loads(creds_json)
                return Credentials.from_service_account_info(creds_info, scopes=scope)
            except json.JSONDecodeError as e:
                logger.error(f"Error en formato JSON: {e}")
        
        # 2. Intentar desde archivo
        logger.info("Buscando archivo de credenciales...")
        for path in Settings.CREDENTIALS_PATHS:
            if os.path.exists(path):
                logger.info(f"Credenciales encontradas en: {path}")
                return Credentials.from_service_account_file(path, scopes=scope)
        
        # 3. Error si no se encuentra
        raise FileNotFoundError(
            "No se encontraron credenciales. "
            "Configura GOOGLE_CREDENTIALS_JSON o coloca credentials_apps.json"
        )
    
    def get_worksheet(self, nombre: str):
        """Obtiene una hoja por nombre."""
        try:
            return self._spreadsheet.worksheet(nombre)
        except gspread.exceptions.WorksheetNotFound:
            logger.warning(f"Hoja '{nombre}' no encontrada")
            return None
    
    def get_or_create_worksheet(self, nombre: str, rows: int = 1000, cols: int = 20):
        """Obtiene una hoja o la crea si no existe."""
        ws = self.get_worksheet(nombre)
        if ws is None:
            logger.info(f"Creando hoja '{nombre}'...")
            ws = self._spreadsheet.add_worksheet(title=nombre, rows=rows, cols=cols)
        return ws
    
    @property
    def client(self):
        """Retorna el cliente de gspread."""
        return self._client
    
    @property
    def spreadsheet(self):
        """Retorna el spreadsheet actual."""
        return self._spreadsheet


# Instancia singleton
sheets_client = GoogleSheetsClient()
