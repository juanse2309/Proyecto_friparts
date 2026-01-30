
import gspread
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Configuration
GSHEET_KEY = os.environ.get("GSHEET_KEY", "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM")
CREDENTIALS_PATHS = [
    "credentials_apps.json",
    "/etc/secrets/credentials_apps.json",
    "./config/credentials_apps.json",
]

def cargar_credenciales():
    for path in CREDENTIALS_PATHS:
        if os.path.exists(path):
            return path
    return None

try:
    creds_path = cargar_credenciales()
    if not creds_path:
        print("Error: No credentials found.")
        exit(1)
        
    gc = gspread.service_account(filename=creds_path)
    sh = gc.open_by_key(GSHEET_KEY)
    
    worksheet = sh.worksheet("RESPONSABLES")
    headers = worksheet.row_values(1)
    print(f"Headers: {headers}")
    
    # Print first row of data to see example values
    first_row = worksheet.row_values(2)
    print(f"First Row: {first_row}")

except Exception as e:
    print(f"Error: {e}")
