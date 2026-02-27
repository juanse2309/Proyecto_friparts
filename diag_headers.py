from backend.core.database import sheets_client as gc
from backend.config.settings import Hojas

def diag_sheet():
    ws = gc.get_worksheet(Hojas.PARAMETROS_INVENTARIO)
    if not ws:
        print("Hoja no encontrada")
        return
    headers = ws.row_values(1)
    print(f"Headers: {headers}")

if __name__ == "__main__":
    diag_sheet()
