
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from backend.core.database import sheets_client

def list_sheets():
    try:
        ss = sheets_client.spreadsheet
        worksheets = ss.worksheets()
        print(f"Hojas disponibles: {[ws.title for ws in worksheets]}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_sheets()
