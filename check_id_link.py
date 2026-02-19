
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
    
    ws_pnc = ss.worksheet("PNC PULIDO")
    ws_pul = ss.worksheet("PULIDO")
    
    # Obtener últimos registros
    last_pnc = ws_pnc.get_all_values()[-1]
    
    print(f"--- Último registro en PNC PULIDO ---")
    print(f"ID PNC (Col A): {last_pnc[0]}")
    print(f"ID OPERACION (Col B): {last_pnc[1]}") # Aquí debería estar el ID de Pulido
    
    id_pulido_en_pnc = last_pnc[1]
    
    # Buscar ese ID en la hoja PULIDO
    cell = ws_pul.find(id_pulido_en_pnc)
    
    if cell:
        print(f"\n✅ ENCONTRADO en hoja PULIDO en fila {cell.row}")
        row_pul = ws_pul.row_values(cell.row)
        print(f"Registro Pulido: {row_pul}")
        print("\nCONCLUSIÓN: SÍ, el 'ID OPERACION' en PNC es el 'ID_PULIDO' original.")
    else:
        print(f"\n❌ NO encontrado en hoja PULIDO. (Puede ser un dato de prueba eliminado o antiguo)")

except Exception as e:
    print(f"Error: {e}")
