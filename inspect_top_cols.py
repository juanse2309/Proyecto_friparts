import sys, os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from backend.core.database import sheets_client

def clean_currency(val):
    if not val: return 0
    if isinstance(val, (int, float)): return val
    s = str(val).replace('$', '').replace('.', '').replace(',', '').strip()
    try: return int(s)
    except: return 0

def clean_number(val):
    if not val: return 0
    if isinstance(val, (int, float)): return val
    s = str(val).replace('.', '').replace(',', '').strip()
    try: return int(s)
    except: return 0

ws = sheets_client.spreadsheet.worksheet("DB_DASHBOARD_VENTAS")
data = ws.get_all_values()

print("=== TOP 10 MÁS VENDIDOS ===")
print(f"{'#':<3} {'Col G (producto $)':<50} {'Col H (dinero)':<18} {'Col I (producto u)':<50} {'Col J (raw)':<15} {'J parsed':<10}")
for i in range(2, min(15, len(data))):
    row = data[i]
    row += [''] * (14 - len(row))
    g = row[6].strip()[:45]
    h_raw = row[7]
    h = clean_currency(row[7])
    i_col = row[8].strip()[:45]
    j_raw = row[9]
    j = clean_number(row[9])
    if g:
        print(f"{i-1:<3} {g:<50} {h:<18,} {i_col:<50} {j_raw:<15} {j:<10,}")

print(f"\n=== TOP 10 MENOS VENDIDOS ===")
print(f"{'#':<3} {'Col K (producto $)':<50} {'Col L (dinero)':<18} {'Col M (producto u)':<50} {'Col N (raw)':<15} {'N parsed':<10}")
for i in range(2, min(15, len(data))):
    row = data[i]
    row += [''] * (14 - len(row))
    k = row[10].strip()[:45]
    l_raw = row[11]
    l = clean_currency(row[11])
    m = row[12].strip()[:45]
    n_raw = row[13]
    n = clean_number(row[13])
    if k:
        print(f"{i-1:<3} {k:<50} {l:<18,} {m:<50} {n_raw:<15} {n:<10,}")
