import json
import os
import gspread
import threading
import time
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
    
    # Global Cache across all threads
    _global_cache = {}
    _cache_ttl = 300  # 5 minutos

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
        """Obtiene una hoja por nombre usando la conexión del hilo actual.
        Agrega hooks a métodos de escritura para invalidar su caché automáticamente."""
        try:
            ws = self.spreadsheet.worksheet(nombre)
            
            # Monkey patching methods to clear cache on writes
            original_update_cell = ws.update_cell
            def override_update_cell(*args, **kwargs):
                result = original_update_cell(*args, **kwargs)
                self.clear_cache(nombre)
                return result
            ws.update_cell = override_update_cell
            
            original_append_row = ws.append_row
            def override_append_row(*args, **kwargs):
                result = original_append_row(*args, **kwargs)
                self.clear_cache(nombre)
                return result
            ws.append_row = override_append_row
            
            original_append_rows = ws.append_rows
            def override_append_rows(*args, **kwargs):
                result = original_append_rows(*args, **kwargs)
                self.clear_cache(nombre)
                return result
            ws.append_rows = override_append_rows
            
            original_update = ws.update
            def override_update(*args, **kwargs):
                result = original_update(*args, **kwargs)
                self.clear_cache(nombre)
                return result
            ws.update = override_update

            return ws
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
    
    def clear_cache(self, nombre_hoja: str = None):
        """Limpia la caché. Si se especifica nombre_hoja, solo limpia esa entrada."""
        with self._lock:
            if nombre_hoja:
                if nombre_hoja in self._global_cache:
                    del self._global_cache[nombre_hoja]
                    logger.info(f"Caché limpiado explícitamente para hoja: {nombre_hoja}")
            else:
                self._global_cache.clear()
                logger.info("Caché global de Google Sheets limpiado.")

    def get_all_records_seguro(self, ws):
        """
        Obtiene registros de una hoja interceptando con Simple Cache para evitar límite 429.
        Maneja headers duplicados o vacíos nativamente.
        """
        if not ws: return []
        
        cache_key = ws.title
        now = time.time()
        
        # 1. Intentar Cache Hit
        with self._lock:
            if cache_key in self._global_cache:
                c_data = self._global_cache[cache_key]
                cache_data, timestamp = c_data[0], c_data[-1]
                age = now - timestamp
                if age < self._cache_ttl:
                    logger.info(f"⚡ Mostrando datos de caché ({cache_key}) de hace {int(age)} segundos.")
                    return cache_data
            
        # 2. Cache Miss - Obtener de Google Sheets API
        try:
            # logger.info(f"📡 Cache MISS para '{cache_key}'. Leyendo de API de Google...")
            datos = ws.get_all_values()
            if not datos: return []
            
            headers = [str(h).strip() for h in datos[0]]
            
            last_valid_idx = -1
            for i, h in enumerate(headers):
                if h: last_valid_idx = i
                
            header_keys = []
            seen = {}
            limite = last_valid_idx + 1 if last_valid_idx != -1 else len(headers)
            
            for i in range(limite):
                h = headers[i]
                if not h: h = f"COL_{i+1}"
                
                if h in seen:
                    seen[h] += 1
                    h = f"{h}_{seen[h]}"
                else:
                    seen[h] = 0
                header_keys.append(h)
                
            records = []
            for row in datos[1:]:
                record = {}
                for i, key in enumerate(header_keys):
                    val = row[i] if i < len(row) else ""
                    record[key] = val
                records.append(record)
                
            # Guardar en Caché antes de retornar (records, dataframe_placeholder, timestamp)
            with self._lock:
                self._global_cache[cache_key] = (records, None, now)
                
            return records
            
        except gspread.exceptions.APIError as e:
            if '429' in str(e):
                logger.error(f"❌ Rate limit excedido (429) en hoja '{cache_key}'.")
                raise Exception("Servidor saturado, reintentando en 10 segundos...") from e
            logger.error(f"❌ Error API en get_all_records_seguro: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error crítico en get_all_records_seguro: {e}")
            return []

    def get_dataframe(self, nombre_hoja: str):
        """
        Obtiene un Pandas DataFrame con los datos cacheados de la hoja.
        Utilizado para búsqueda vectorial de alta velocidad.
        """
        import pandas as pd
        ws = self.get_worksheet(nombre_hoja)
        if not ws: return pd.DataFrame()
        
        cache_key = ws.title
        now = time.time()
        
        with self._lock:
            if cache_key in self._global_cache:
                c_data = self._global_cache[cache_key]
                records, df, timestamp = c_data[0], c_data[1], c_data[-1]
                if now - timestamp < self._cache_ttl:
                    if df is not None:
                        return df.copy()
                    else:
                        df = pd.DataFrame(records)
                        # Ensure string encoding and no nulls for vectorized ops
                        df = df.fillna('')
                        self._global_cache[cache_key] = (records, df, timestamp)
                        return df.copy()
        
        # If no cache or expired, call getting records
        records = self.get_all_records_seguro(ws)
        df = pd.DataFrame(records).fillna('')
        with self._lock:
            self._global_cache[cache_key] = (records, df, time.time())
        return df.copy()


# Instancia singleton global
# (La gestión de hilos ocurre internamente en la propiedad .client)
sheets_client = GoogleSheetsClient()
