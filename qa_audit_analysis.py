import pandas as pd
import os

# --- LOAD DATA ---
# New Excel (Source of Truth for tomorrow)
# We skip row 0 (Title) and row 1 (Header for Excel but first row of data for pandas if we are not careful)
df_new = pd.read_excel('Fichas tecnicas.xlsx', header=1)

# Current Sheets (Source of Truth for today)
df_fichas = pd.read_csv('current_fichas.csv')
# Current Sheets (Source of Truth for today)
df_fichas = pd.read_csv('current_fichas.csv')

def normalize(s):
    return str(s).strip().upper()

def get_current_bom(ref):
    ref_norm = normalize(ref)
    components = []
    
    # Check FICHAS (standard BOM)
    match_fichas = df_fichas[df_fichas['ID CODIGO'].apply(normalize) == ref_norm]
    for _, r in match_fichas.iterrows():
        comp = str(r.get('BUJE ENSAMBLE', '')).strip()
        qty = float(r.get('QTY', 1.0))
        components.append({'name': comp, 'qty': qty, 'source': 'FICHAS'})
        
    return components

def get_new_bom(ref_prefix):
    # The 'Producto' column in Excel contains strings like 'AL-001 AL-001 ALARGADOR...'
    # We search by prefix
    mask = df_new['Producto'].fillna('').str.contains(ref_prefix, case=False, na=False)
    matches = df_new[mask]
    
    components = []
    for _, r in matches.iterrows():
        sub = str(r.get('SubProducto', '')).strip()
        qty = r.get('Cantidad', 0)
        unit = str(r.get('UnidadDeMedida', '')).strip()
        if sub and 'Total' not in sub:
            components.append({'name': sub, 'qty': qty, 'unit': unit})
    return components

def run_audit():
    # Candidates for Audit
    samples = ['9430', '7025', 'AL-001', 'AL-002', 'BF-9735']
    
    print("# DATA QA AUDIT: 5 REPERENCES STRESS TEST\n")
    
    for ref in samples:
        print(f"## REFERENCE: {ref}")
        curr = get_current_bom(ref)
        new = get_new_bom(ref)
        
        print("### CURRENT SYSTEM (Sheets)")
        if curr:
            for c in curr:
                print(f"- {c['name']} | Qty: {c['qty']} ({c['source']})")
        else:
            print("- NO ENCONTRADO EN SHEETS")
            
        print("### NEW SYSTEM (Excel)")
        if new:
            for n in new:
                print(f"- {n['name']} | Qty: {n['qty']} {n['unit']}")
        else:
            print("- NO ENCONTRADO EN EXCEL")
        print("\n" + "-"*40 + "\n")

if __name__ == "__main__":
    run_audit()
