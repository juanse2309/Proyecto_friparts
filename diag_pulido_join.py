from backend.core.database import sheets_client
from backend.config.settings import Hojas
import collections

def get_all_records_seguro(ws):
    if not ws: return []
    try:
        datos = ws.get_all_values()
        if not datos: return []
        headers = [h.strip() for h in datos[0]]
        last_valid_idx = -1
        for i, h in enumerate(headers):
            if h: last_valid_idx = i
        header_keys = []
        seen = {}
        for i in range(last_valid_idx + 1):
            h = headers[i]
            if not h: h = f"COL_{i}"
            if h in seen:
                seen[h] += 1
                h = f"{h}_{seen[h]}"
            else: seen[h] = 0
            header_keys.append(h)
        records = []
        for row in datos[1:]:
            record = {}
            for i, key in enumerate(header_keys):
                val = row[i] if i < len(row) else ""
                record[key] = val
            records.append(record)
        return records
    except: return []

print("Buscando IDs en PULIDO...")
ws_pul = sheets_client.get_worksheet(Hojas.PULIDO)
reg_pul = get_all_records_seguro(ws_pul)
ids_pul = set(str(r.get("ID PULIDO") or "").strip() for r in reg_pul)
print(f"Total IDs en PULIDO: {len(ids_pul)}")

print("\nBuscando IDs en PNC_PULIDO...")
ws_pnc = sheets_client.get_worksheet(Hojas.PNC_PULIDO)
reg_pnc = get_all_records_seguro(ws_pnc)
ids_pnc = [str(r.get("ID PULIDO") or "").strip() for r in reg_pnc]
print(f"Total registros en PNC_PULIDO: {len(ids_pnc)}")

matches = [id for id in ids_pnc if id in ids_pul]
print(f"IDs que SI cruzaron: {len(matches)}")
if ids_pnc:
    print(f"Ejemplo IDs PNC: {ids_pnc[:5]}")
if reg_pul:
    print(f"Ejemplo IDs PUL: {[str(r.get('ID PULIDO')) for r in reg_pul[:5]]}")
