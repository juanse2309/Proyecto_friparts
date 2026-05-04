import os
import logging
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from backend.config.settings import Settings

logger = logging.getLogger(__name__)

class DriveService:
    """Servicio para subir archivos a Google Drive usando Service Account."""
    
    def __init__(self):
        self._scopes = ['https://www.googleapis.com/auth/drive']
        self._credentials = self._cargar_credenciales()
        self.service = build('drive', 'v3', credentials=self._credentials)

    def _cargar_credenciales(self):
        """
        Intenta cargar credenciales de usuario (OAuth2 token.json).
        Si no existen, falla silenciosamente y usa Service Account.
        """
        try:
            from backend.utils.auth_helper import get_user_credentials
            user_creds = get_user_credentials()
            if user_creds:
                logger.info("Usando autenticación de USUARIO (OAuth2) para Drive.")
                return user_creds
        except Exception as e:
            logger.warning(f"No se pudieron cargar credenciales de usuario: {e}")

        logger.info("Cayendo en autenticación de SERVICE ACCOUNT para Drive.")
        
        # 1. Intentar desde variable de entorno
        creds_json = Settings.GOOGLE_CREDENTIALS_JSON
        if creds_json:
            try:
                creds_info = json.loads(creds_json)
                return Credentials.from_service_account_info(creds_info, scopes=self._scopes)
            except Exception as e:
                logger.error(f"Error cargando credenciales de entorno para Drive: {e}")
        
        # 2. Intentar desde archivos físicos
        for path in Settings.CREDENTIALS_PATHS:
            if os.path.exists(path):
                return Credentials.from_service_account_file(path, scopes=self._scopes)
        
        raise FileNotFoundError("No se encontraron credenciales de Google (User ni Service Account).")

    def subir_archivo(self, filepath, nombre_destino, folder_id=None):
        """
        Sube un archivo a Drive.
        filepath: Ruta local del archivo.
        nombre_destino: Nombre con el que se guardará en Drive.
        folder_id: ID de la carpeta de destino (opcional).
        """
        try:
            if not os.path.exists(filepath):
                logger.error(f"El archivo local no existe para subir: {filepath}")
                return None

            file_metadata = {'name': nombre_destino}
            if folder_id:
                # logger.debug(f"Subiendo a carpeta ID: {folder_id}")
                file_metadata['parents'] = [folder_id]
            
            # Detectar mime-type para PDFs
            media = MediaFileUpload(filepath, mimetype='application/pdf', resumable=True)
            
            # CRITICAL: Si folder_id es inválido o el service account no tiene permiso, 
            # Google retorna un 404 o 400.
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
            file_id = file.get('id')
            
            # --- Intento de Transferencia de Propiedad (Para evitar storageQuotaExceeded) ---
            # Si el Service Account no tiene cuota, transferimos el archivo al dueño de la carpeta.
            try:
                folder_meta = self.service.files().get(
                    fileId=folder_id, 
                    fields='owners', 
                    supportsAllDrives=True
                ).execute()
                
                owners = folder_meta.get('owners', [])
                if owners:
                    owner_email = owners[0].get('emailAddress')
                    self.service.permissions().create(
                        fileId=file_id,
                        body={'type': 'user', 'role': 'owner', 'emailAddress': owner_email},
                        transferOwnership=True,
                        supportsAllDrives=True
                    ).execute()
                    logger.info(f" 🚩 Propiedad transferida a: {owner_email}")
            except Exception as e_transfer:
                # Es normal que falle si no están en el mismo dominio de Workspace
                logger.debug(f" No se pudo transferir propiedad (esperado en algunos casos): {e_transfer}")

            logger.info(f" ✅ Archivo '{nombre_destino}' creado en Drive (Folder ID: {folder_id}). ID File: {file_id}")
            return file_id
        except Exception as e:
            logger.error(f"Falla crítica subiendo archivo a Drive (Folder: {folder_id}): {str(e)}")
            return None

# Instancia global
drive_service = DriveService()
