
import sys
import os

# Agregar path raiz
sys.path.append(os.getcwd())

from backend.config.settings import Hojas
from backend.core.database import sheets_client

def obtener_hoja(nombre_hoja):
    return sheets_client.get_or_create_worksheet(nombre_hoja)

def check():
    print("--- DIAGNÓSTICO DE VENDEDORES ---")
    
    # 1. Obtener Responsables
    print("Leyendo Responsables...")
    ws_resp = obtener_hoja(Hojas.RESPONSABLES)
    resp_raw = ws_resp.get_all_records()
    
    mapa = {}
    print(f"\nEncontrados {len(resp_raw)} responsables:")
    
    if resp_raw:
        print(f"CLAVES EN RESPONSABLES: {list(resp_raw[0].keys())}")
        
    for r in resp_raw:
        nombre_raw = str(r.get('NOMBRE', ''))
        nombre_key = nombre_raw.strip().upper()
        doc = str(r.get('DOCUMENTO', '')).strip()
        mapa[nombre_key] = doc
        print(f"  - '{nombre_raw}' -> key='{nombre_key}' -> doc='{doc}' (len key: {len(nombre_key)})")

    # 2. Obtener Pedidos (ultimos 50 para no saturar)
    print("\nLeyendo Pedidos (últimos 20)...")
    ws_ped = obtener_hoja(Hojas.PEDIDOS)
    ped_raw = ws_ped.get_all_records()[-20:]
    
    print("\nVerificando cruce:")
    for p in ped_raw:
        vend_raw = str(p.get('VENDEDOR', ''))
        vend_key = vend_raw.strip().upper()
        
        match = mapa.get(vend_key)
        estado = "✅ MATCH" if match else "❌ FAIL"
        val_final = match if match else vend_key
        
        print(f"  Pedido {p.get('ID PEDIDO')}: Vendedor='{vend_raw}' -> key='{vend_key}' (len: {len(vend_key)}) -> {estado} -> Final: '{val_final}'")

if __name__ == "__main__":
    check()
