
import gspread
from google.oauth2.service_account import Credentials

GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

try:
    creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)
    ws = ss.worksheet("PRODUCTOS")
    
    registros = ws.get_all_records()
    
    print("--- Verificando producto 93009 ---")
    found = False
    for r in registros:
        if '93009' in str(r.get('CODIGO SISTEMA', '')) or '93009' in str(r.get('CODIGO', '')):
            print(f"Prod: {r.get('CODIGO SISTEMA')} | P.PULIR: '{r.get('POR PULIR')}' | P.TERM: '{r.get('P. TERMINADO')}' | IMG: '{r.get('IMAGEN')}'")
            found = True
            
    if not found:
        print("No se encontró 93009")

except Exception as e:
    print(f"Error: {e}")
