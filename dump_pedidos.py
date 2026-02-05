from backend.core.database import sheets_client
from backend.config.settings import Hojas

def dump_pedidos():
    ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
    headers = ws.row_values(1)
    records = ws.get_all_records()
    print(f"Headers found: {headers}")
    print(f"Total records: {len(records)}")
    if records:
        print(f"Keys in first record: {records[0].keys()}")
        print(f"First record: {records[0]}")
    else:
        print("Sheet is empty.")

if __name__ == "__main__":
    dump_pedidos()
