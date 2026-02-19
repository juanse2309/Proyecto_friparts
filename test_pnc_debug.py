
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import datetime
import uuid

# Config básica
GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
GSHEET_FILE_NAME = "Proyecto_Friparts"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def cargar_credenciales():
    return Credentials.from_service_account_file("credentials_apps.json", scopes=scope)

def test_pnc_write():
    try:
        creds = cargar_credenciales()
        gc = gspread.authorize(creds)
        ss = gc.open_by_key(GSHEET_KEY)
        
        hoja_pnc = "PNC PULIDO"
        try:
            ws = ss.worksheet(hoja_pnc)
        except:
            print(f"Hoja {hoja_pnc} no encontrada")
            return

        print(f"--- Diagnóstico para {hoja_pnc} ---")
        
        # 1. Ver col_values(1)
        col1 = ws.col_values(1)
        print(f"Filas actuales en Col A: {len(col1)}")
        print(f"Últimos 5 valores en Col A: {col1[-5:]}")
        
        next_row = len(col1) + 1
        print(f"Calculado next_row: {next_row}")
        
        # Simulando el update
        id_pnc = f"TEST-DEBUG-{str(uuid.uuid4())[:5]}"
        fila_pnc = [
            id_pnc, 
            "TEST-OP", 
            "PROD-TEST", 
            1, 
            "DEBUG", 
            "Test Script", 
            datetime.datetime.now().strftime("%d/%m/%Y"), 
            "Tester", 
            "PENDIENTE"
        ]
        
        rango_celdas = f"A{next_row}:I{next_row}"
        print(f"Intentando update en rango: {rango_celdas}")
        
        try:
            ws.update(rango_celdas, [fila_pnc], value_input_option='USER_ENTERED')
            print("✅ Update exitoso")
        except Exception as e:
            print(f"❌ Update falló: {e}")
            print("Intentando append_row...")
            ws.append_row(fila_pnc, value_input_option='USER_ENTERED')
            print("✅ Append row ejecutado")

    except Exception as e:
        print(f"Error general: {e}")

if __name__ == "__main__":
    test_pnc_write()
