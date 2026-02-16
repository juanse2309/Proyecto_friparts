import pandas as pd
import os

PROJECT_ROOT = r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia'
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, 'frontend', 'static', 'docs', 'DocumentosComprasEncabezadosMovimientoInventarioWO.xls')

try:
    df = pd.read_excel(TEMPLATE_PATH)
    cols = list(df.columns)
    print(f"Total columns: {len(cols)}")
    print("Columns list:")
    print(cols)
    
    unnamed = [c for c in cols if "Unnamed" in str(c) or str(c).strip() == ""]
    if unnamed:
        print(f"\n WARNING: Found suspicious columns: {unnamed}")
    else:
        print("\n No 'Unnamed' or empty columns found.")
        
except Exception as e:
    print(f"Error: {e}")
