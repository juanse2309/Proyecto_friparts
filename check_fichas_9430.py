import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from backend.app import get_spreadsheet, Hojas

def inspect_fichas():
    try:
        ss = get_spreadsheet()
        ws = ss.worksheet(Hojas.FICHAS)
        regs = ws.get_all_records()
        
        target = '9430'
        matches = [r for r in regs if target in str(r.get('ID CODIGO', '')) or target in str(r.get('BUJE ENSAMBLE', ''))]
        
        print(f"--- FICHAS Matching '{target}' ---")
        for m in matches:
            print(m)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_fichas()
