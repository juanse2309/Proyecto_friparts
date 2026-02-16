import pandas as pd
import os
import sys

# Simulation of what app does
PROJECT_ROOT = r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia'
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, 'frontend', 'static', 'docs', 'DocumentosComprasEncabezadosMovimientoInventarioWO.xls')

print(f"Checking template: {TEMPLATE_PATH}")

if not os.path.exists(TEMPLATE_PATH):
    print("Template NOT FOUND")
    sys.exit(1)

try:
    # Try reading with xlrd (for .xls)
    df = pd.read_excel(TEMPLATE_PATH)
    print("\nColumns found in template:")
    for i, col in enumerate(df.columns):
        print(f"{i}: '{col}' (Type: {type(col)})")
    
    print("\nFirst row of data:")
    print(df.head(1).to_dict())

except Exception as e:
    print(f"Error reading template: {e}")
