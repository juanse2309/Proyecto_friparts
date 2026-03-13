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

print("=== MUESTRA DE INCUMPLIMIENTO UNIDADES (Cols O-R) ===")
print(f"{'Fila':<5} {'Cliente (Col O)':<25} {'Producto (Col P)':<30}  {'Pedidos (Q)':<15} {'Ventas (R)':<15} -> {'Incumplimiento (Fallo)':<20}")

cli_u = ""
for i in range(2, min(20, len(data))):
    row = data[i]
    row += [''] * (25 - len(row))
    
    u_cli_col = row[14].strip()
    u_prod_col = row[15].strip()
    
    if u_cli_col.lower().startswith("total "):
        cli_u = u_cli_col[6:].strip()
        print(f"{i+1:<5} [ACTUALIZANDO CLIENTE: {cli_u}]")
    elif u_prod_col and cli_u and not u_prod_col.lower().startswith("total "):
        q_raw = row[16]
        r_raw = row[17]
        p_unds = clean_number(q_raw)
        v_unds = clean_number(r_raw)
        fallo = max(0, p_unds - v_unds)
        if fallo > 0:
            print(f"{i+1:<5} {cli_u[:23]:<25} {u_prod_col[:28]:<30}  {q_raw:<15} {r_raw:<15} -> 🔴 {fallo:,} uds")
        else:
            print(f"{i+1:<5} {cli_u[:23]:<25} {u_prod_col[:28]:<30}  {q_raw:<15} {r_raw:<15} -> 🟢 OK")

print("\n=== MUESTRA DE INCUMPLIMIENTO DINERO (Cols U-X) ===")
print(f"{'Fila':<5} {'Cliente (Col U)':<25} {'Producto (Col V)':<30}  {'Pedidos (W)':<15} {'Ventas (X)':<15} -> {'Incumplimiento (Pérdida)':<20}")

cli_d = ""
for i in range(2, min(20, len(data))):
    row = data[i]
    row += [''] * (25 - len(row))
    
    d_cli_col = row[20].strip()
    d_prod_col = row[21].strip()
    
    if d_cli_col.lower().startswith("total "):
        cli_d = d_cli_col[6:].strip()
        print(f"{i+1:<5} [ACTUALIZANDO CLIENTE: {cli_d}]")
    elif d_prod_col and cli_d and not d_prod_col.lower().startswith("total "):
        w_raw = row[22]
        x_raw = row[23]
        p_money = clean_currency(w_raw)
        v_money = clean_currency(x_raw)
        perdida = max(0, p_money - v_money)
        if perdida > 0:
            print(f"{i+1:<5} {cli_d[:23]:<25} {d_prod_col[:28]:<30}  {w_raw:<15} {x_raw:<15} -> 🔴 ${perdida:,}")
        else:
            print(f"{i+1:<5} {cli_d[:23]:<25} {d_prod_col[:28]:<30}  {w_raw:<15} {x_raw:<15} -> 🟢 OK")
