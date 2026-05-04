"""
database.py — Centralized Google Sheets & SQL Database Configuration.
Optimizado para carga bajo demanda (Lazy Loading).
"""
import os
import json
import logging
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE SCOPES ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class SheetsClient:
    """Cliente de Google Sheets con Singleton y reconexión automática."""
    _instance = None
    _gc = None
    _spreadsheet = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SheetsClient, cls).__new__(cls)
        return cls._instance

    def _get_creds(self):
        """Carga credenciales desde variable de entorno o archivo local."""
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            try:
                return Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
            except Exception as e:
                logger.error(f"Error cargando credenciales desde ENV: {e}")

        paths = ["credentials_apps.json", "./config/credentials_apps.json", "/etc/secrets/credentials_apps.json"]
        for path in paths:
            if os.path.exists(path):
                try:
                    return Credentials.from_service_account_file(path, scopes=SCOPES)
                except Exception as e:
                    logger.warning(f"No se pudo cargar desde {path}: {e}")
        return None

    def _authorize(self):
        """Autoriza gspread solo si es necesario."""
        if self._gc is None:
            creds = self._get_creds()
            if creds:
                self._gc = gspread.authorize(creds)
                logger.info("✅ [GSHEET] Autorizado exitosamente.")
            else:
                logger.error("❌ [GSHEET] No se encontraron credenciales válidas.")
        return self._gc

    def get_spreadsheet(self, key=None):
        """Obtiene el objeto spreadsheet principal."""
        if self._spreadsheet is None:
            gc = self._authorize()
            if gc:
                gs_key = key or os.environ.get('GSHEET_KEY')
                if gs_key:
                    self._spreadsheet = gc.open_by_key(gs_key)
                    logger.info(f"✅ [GSHEET] Spreadsheet '{self._spreadsheet.title}' abierto.")
        return self._spreadsheet

    def get_worksheet(self, name):
        """Obtiene una pestaña específica por nombre."""
        try:
            ss = self.get_spreadsheet()
            if ss:
                return ss.worksheet(name)
        except Exception as e:
            logger.error(f"Error obteniendo hoja '{name}': {e}")
        return None

    def get_all_records_seguro(self, ws):
        """Obtiene todos los registros de forma robusta."""
        if not ws: return []
        try:
            return ws.get_all_records()
        except Exception as e:
            logger.error(f"Error leyendo registros: {e}")
            return []

# Instancia única exportada para compatibilidad legacy
sheets_client = SheetsClient()
