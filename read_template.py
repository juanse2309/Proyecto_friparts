import pandas as pd
import sys

file_path = r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\static\docs\DocumentosComprasEncabezadosMovimientoInventarioWO.xls'

try:
    # Intentar leer con engine por defecto (xlrd para xls)
    df = pd.read_excel(file_path)
    print("COLUMNS:" + "|".join([str(c) for c in df.columns]))
except Exception as e:
    print(f"ERROR:{e}")
