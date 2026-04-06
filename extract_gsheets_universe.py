import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os

# --- Google Sheets IDs and Scopes ---
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
    print("🚀 Extracting ALL System Names for Fuzzy Matching...")
    gc = get_gsheets_client()
    ss = gc.open_by_key(GSHEET_KEY)
    
    universe = set()
    
    sheets_to_extract = ["INYECCION", "PULIDO", "FICHAS", "NUEVA_FICHA_MAESTRA"]
    
    for s_name in sheets_to_extract:
        print(f"📊 Processing {s_name}...")
        ws = ss.worksheet(s_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Determine column to pick based on sheet
        if s_name == "FICHAS":
            col = "ID CODIGO"
        elif s_name == "NUEVA_FICHA_MAESTRA":
            col = "SubProducto"
        else:
            # For INYECCION and PULIDO, try 'CODIGO' or 'ID'
            col = "CODIGO" if "CODIGO" in df.columns else "ID"
            if col not in df.columns:
                # Look for first column that might contain codes
                candidates = [c for c in df.columns if "COD" in str(c).upper() or "REF" in str(c).upper()]
                col = candidates[0] if candidates else df.columns[0]
        
        if col in df.columns:
            vals = df[col].dropna().astype(str).str.strip().str.upper()
            universe.update(vals.unique())
            print(f"   Found {len(vals.unique())} unique codes in {s_name}")

    # Save the consolidated universe
    pd.DataFrame(list(universe), columns=["SystemCode"]).to_csv('system_universe.csv', index=False)
    print(f"✅ Consolidated universe saved. Total unique records: {len(universe)}")

if __name__ == "__main__":
    main()
