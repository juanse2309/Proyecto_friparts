
import gspread
from google.oauth2.service_account import Credentials
import json

# Config básica
GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

try:
    creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)
    ws = ss.worksheet("PRODUCTOS")
    
    headers = ws.row_values(1)
    
    try:
        col_idx = headers.index("POR PULIR") + 1
        col_cod = headers.index("ID CODIGO") + 1
        col_sis = headers.index("CODIGO SISTEMA") + 1
    except ValueError:
        print("Error: Columna POR PULIR no encontrada")
        exit(1)
        
    registros = ws.get_all_values()
    
    found = False
    for i, row in enumerate(registros):
        if i == 0: continue # Header
        
        try:
            stock = row[col_idx-1].replace(',', '').strip()
            stock = int(float(stock)) if stock else 0
            
            if stock > 0:
                codigo = row[col_cod-1]
                sis = row[col_sis-1]
                print(f"ENCONTRADO: {codigo} (Sistema: {sis}) - Stock: {stock}")
                found = True
                break
        except:
            continue
            
    if not found:
        print("NO SE ENCONTRO NINGUN PRODUCTO CON STOCK EN POR PULIR")

except Exception as e:
    print(f"Error: {e}")
