import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
from thefuzz import fuzz, process
import json

# --- CONFIGURATION ---
GSHEET_KEY = '1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM'
CREDENTIALS_PATH = 'credentials_apps.json'
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SOURCE_FILE = 'Fichas tecnicas.xlsx'  # We'll check if it's CSV or Excel

def get_gsheets_client():
    if os.path.exists(CREDENTIALS_PATH):
        creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPE)
        return gspread.authorize(creds)
    else:
        raise FileNotFoundError(f"Credentials not found at {CREDENTIALS_PATH}")

def load_system_catalog():
    print("🚀 Fetching system catalog from Google Sheets...")
    gc = get_gsheets_client()
    ss = gc.open_by_key(GSHEET_KEY)
    
    catalog = []
    sheets_to_load = {
        "INYECCION": ["CODIGO", "ID"],
        "PULIDO": ["CODIGO", "ID"]
    }
    
    for s_name, possible_cols in sheets_to_load.items():
        print(f"  📊 Loading {s_name}...")
        ws = ss.worksheet(s_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Find which columns exist
        available_cols = [c for c in possible_cols if c in df.columns]
        if not available_cols:
            # Fallback: take first column if search fails
            available_cols = [df.columns[0]]
            
        for col in available_cols:
            vals = df[col].dropna().astype(str).str.strip()
            for v in vals:
                if v and v != '-':
                    catalog.append({
                        "name": v,
                        "sheet": s_name
                    })
    
    # Also include FICHAS (standard BOM) from the local CSV if available or fetch it
    # The user didn't explicitly ask for FICHAS in the "bases actuales" list
    # but it's part of the system. I'll stick to the user's list for now.
    
    return pd.DataFrame(catalog).drop_duplicates(subset=['name'])

def load_source_names():
    print(f"📂 Loading source names from {SOURCE_FILE}...")
    try:
        # Try reading as Excel first (header is at row 1, index 0 is title)
        df = pd.read_excel(SOURCE_FILE, header=1)
    except Exception as e:
        print(f"  ⚠️ Failed to read as Excel ({e}), trying as CSV...")
        df = pd.read_csv(SOURCE_FILE, skiprows=1)
        
    print(f"  Found columns: {df.columns.tolist()}")
    
    # Extract unique names from 'Producto' and 'SubProducto'
    products = df['Producto'].dropna().astype(str).str.strip()
    subproducts = df['SubProducto'].dropna().astype(str).str.strip()
    
    # Combine and filtering "Total" rows
    all_names = pd.concat([products, subproducts]).unique()
    filtered_names = [n for n in all_names if n and "Total" not in n]
    
    print(f"  ✅ Extracted {len(filtered_names)} unique names from source.")
    return filtered_names

def run_fuzzy_matching():
    catalog_df = load_system_catalog()
    source_names = load_source_names()
    
    system_names = catalog_df['name'].tolist()
    
    results = []
    print(f"🔍 Starting Fuzzy Matching for {len(source_names)} entries...")
    
    for i, name in enumerate(source_names):
        if i % 50 == 0:
            print(f"  Processing {i}/{len(source_names)}...")
            
        # extractOne returns (match, score)
        best_match, score = process.extractOne(name, system_names, scorer=fuzz.token_sort_ratio)
        
        # Find the sheet for the best match
        sheet_origin = catalog_df[catalog_df['name'] == best_match]['sheet'].iloc[0]
        
        results.append({
            "Nombre_Nuevo_Excel": name,
            "Mejor_Coincidencia_Sistema_Actual": best_match,
            "Nivel_de_Confianza_Porcentaje": score,
            "Sheet_Origen": sheet_origin
        })
        
    # Export to CSV
    output_file = 'proposed_mapping_dictionary.csv'
    pd.DataFrame(results).to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"✅ Mapping generated: {output_file}")

if __name__ == "__main__":
    run_fuzzy_matching()
