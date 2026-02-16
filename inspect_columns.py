import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.database import sheets_client
from backend.config.settings import Hojas

def inspect():
    try:
        # Inspect CLIENTES
        print(f"--- Inspecting {Hojas.CLIENTES} ---")
        ws_clientes = sheets_client.get_or_create_worksheet(Hojas.CLIENTES)
        records_clientes = ws_clientes.get_all_records()
        if records_clientes:
            print(f"Columns: {list(records_clientes[0].keys())}")
            print(f"Sample Row: {records_clientes[0]}")
        else:
            print("Empty sheet")

        # Inspect PEDIDOS
        print(f"\n--- Inspecting {Hojas.PEDIDOS} ---")
        ws_pedidos = sheets_client.get_or_create_worksheet(Hojas.PEDIDOS)
        records_pedidos = ws_pedidos.get_all_records()
        if records_pedidos:
             print(f"Columns: {list(records_pedidos[0].keys())}")
             print(f"Sample Row: {records_pedidos[0]}")
        else:
            print("Empty sheet")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
