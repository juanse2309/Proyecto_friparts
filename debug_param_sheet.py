import sys, os
sys.path.append(os.path.abspath('.'))
from backend.core.database import sheets_client as gc
from backend.config.settings import Hojas

try:
    ws = gc.get_worksheet(Hojas.PARAMETROS_INVENTARIO)
    if ws:
        records = ws.get_all_records()
        with open('debug_param.txt', 'w', encoding='utf-8') as f:
            if records:
                f.write("Headers:\n")
                f.write(str(list(records[0].keys())) + "\n")
                f.write("First 3 records:\n")
                for r in records[:3]:
                    f.write(str(r) + "\n")
            else:
                f.write("No records found in PARAMETROS_INVENTARIO\n")
    else:
        with open('debug_param.txt', 'w', encoding='utf-8') as f:
            f.write("Worksheet PARAMETROS_INVENTARIO not found\n")
except Exception as e:
    with open('debug_param.txt', 'w', encoding='utf-8') as f:
        f.write(f"Error: {e}\n")
