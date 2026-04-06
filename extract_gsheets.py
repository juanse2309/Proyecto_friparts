import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import os

# --- CONFIGURATION ---
GSHEET_KEY = '1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM'
CREDENTIALS_PATH = 'credentials_apps.json'
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def get_gsheets_client():
    if os.path.exists(CREDENTIALS_PATH):
        creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPE)
        return gspread.authorize(creds)
    else:
        raise FileNotFoundError("Credentials not found")

def main():
    print("🚀 Connecting to Google Sheets...")
    gc = get_gsheets_client()
    ss = gc.open_by_key(GSHEET_KEY)
    
    # 1. Extract FICHAS (Simple Mapping)
    print("📊 Extracting FICHAS...")
    ws_fichas = ss.worksheet("FICHAS")
    fichas_data = ws_fichas.get_all_records()
    df_fichas = pd.DataFrame(fichas_data)
    df_fichas.to_csv('current_fichas.csv', index=False)
    
    # 2. Extract NUEVA_FICHA_MAESTRA (BOM Master)
    print("📊 Extracting NUEVA_FICHA_MAESTRA...")
    ws_maestra = ss.worksheet("NUEVA_FICHA_MAESTRA")
    maestra_data = ws_maestra.get_all_records()
    df_maestra = pd.DataFrame(maestra_data)
    df_maestra.to_csv('current_nueva_ficha_maestra.csv', index=False)
    
    print("✅ Extraction complete. Files saved: current_fichas.csv, current_nueva_ficha_maestra.csv")

if __name__ == "__main__":
    main()
