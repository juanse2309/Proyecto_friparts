import os
import json
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# Scopes required for Drive archival
SCOPES = ['https://www.googleapis.com/auth/drive.file']

TOKEN_PATH = 'token.json'
CLIENT_SECRETS_PATH = 'client_secrets.json'

def get_user_credentials():
    """
    Carga las credenciales de usuario desde token.json.
    Si no existen o no son válidas, retorna None.
    """
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            logger.error(f"Error cargando token.json: {e}")

    # Si no hay credenciales válidas, intentar refrescar
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Guardar el token refrescado
                with open(TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
                logger.info("Token de usuario refrescado correctamente.")
                return creds
            except Exception as e:
                logger.error(f"Error refrescando token: {e}")
                return None
        else:
            return None
    
    return creds

def run_auth_flow():
    """
    Ejecuta el flujo interactivo para generar token.json.
    Requiere que client_secrets.json esté presente.
    """
    if not os.path.exists(CLIENT_SECRETS_PATH):
        print(f"ERROR: No se encontró '{CLIENT_SECRETS_PATH}'.")
        print("Descarga el JSON de 'OAuth 2.0 Client IDs' desde Google Cloud Console.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Guardar las credenciales para la próxima vez
    with open(TOKEN_PATH, 'w') as token:
        token.write(creds.to_json())
    
    print(f"EXITO: Se ha generado '{TOKEN_PATH}' correctamente.")
    return creds

if __name__ == "__main__":
    # Si se ejecuta directamente, inicia el flujo
    run_auth_flow()
