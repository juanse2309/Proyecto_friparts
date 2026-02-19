
import gspread
from google.oauth2.service_account import Credentials

GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

try:
    creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)
    ws = ss.worksheet("PRODUCTOS")
    
    # Obtener todos los registros (diccionarios)
    registros = ws.get_all_records()
    
    print("--- Verificando productos '93' ---")
    count = 0
    for r in registros:
        codigo = str(r.get('CODIGO SISTEMA', ''))
        if '93' in codigo:
            p_pulir = r.get('POR PULIR', '')
            p_term = r.get('P. TERMINADO', '')
            imagen = r.get('IMAGEN', '')
            
            print(f"Prod: {codigo} | P.PULIR: '{p_pulir}' | P.TERM: '{p_term}' | IMG: '{imagen}'")
            count += 1
            if count >= 5: break

except Exception as e:
    print(f"Error: {e}")
