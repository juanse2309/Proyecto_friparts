from flask import Blueprint, jsonify, render_template
from backend.utils.auth_middleware import require_role
from backend.core.database import sheets_client

admin_bp = Blueprint('admin_bp', __name__)

# Cache para el endpoint de admin dashboard (10 min TTL)
import time as _time
ADMIN_DASHBOARD_CACHE = {}  # key: (start, end) -> {"timestamp": float, "data": dict}
ADMIN_CACHE_TTL = 600  # 10 minutos

# Helper function to clean currency strings to int/float
def clean_currency(val):
    if not val: return 0
    if isinstance(val, (int, float)): return val
    s = str(val).replace('$', '').replace('.', '').replace(',', '').strip()
    try:
        return int(s)
    except:
        return 0

# Helper function to clean number strings
def clean_number(val):
    if not val: return 0
    if isinstance(val, (int, float)): return val
    s = str(val).replace('.', '').replace(',', '').strip()
    try:
        return int(s)
    except:
        return 0


@admin_bp.route('/api/admin/dashboard', methods=['GET'])
@require_role(['admin', 'administrador', 'administracion', 'gerencia', 'comercial'])
def get_admin_dashboard_data():
    from flask import request
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    start_date_str = request.args.get('start')
    end_date_str = request.args.get('end')
    
    # --- CACHE CHECK ---
    nocache = request.args.get('nocache') == '1'
    cache_key = (start_date_str or '', end_date_str or '')
    
    if nocache:
        ADMIN_DASHBOARD_CACHE.pop(cache_key, None)
        print(f"DEBUG: 🗑️ Cache invalidado manualmente para {cache_key}")
    
    cached = ADMIN_DASHBOARD_CACHE.get(cache_key)
    if cached and (_time.time() - cached["timestamp"] < ADMIN_CACHE_TTL):
        print(f"DEBUG: ⚡ Admin dashboard CACHE HIT para {cache_key}")
        return jsonify(cached["data"])
    
    print(f"DEBUG: 📡 Admin dashboard CACHE MISS para {cache_key}, consultando Sheets...")
    
    # Range limiters
    start_dt = None
    end_dt = None
    if start_date_str:
        try: start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
        except: pass
    if end_date_str:
        try: end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        except: pass

    # Mapping for month names
    meses_map = {
        1: 'ene', 2: 'feb', 3: 'mar', 4: 'abr', 5: 'may', 6: 'jun',
        7: 'jul', 8: 'ago', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dic'
    }

    # --- 0. CALCULAR RANGOS ---
    actual_start = start_dt
    actual_end = end_dt
    
    # Si no hay filtros, por defecto es el año actual
    if not actual_start:
        actual_start = datetime(datetime.now().year, 1, 1)
    if not actual_end:
        actual_end = datetime.now()

    # Rango del año pasado (mismos meses)
    def shift_year(dt, years):
        try:
            return dt.replace(year=dt.year + years)
        except ValueError:
            # Manejar 29 de febrero
            return dt + timedelta(days=years * 365)

    prev_start = shift_year(actual_start, -1)
    prev_end = shift_year(actual_end, -1)

    # Robust parser for sheet month labels like '2025-ene', '2025-sept'
    def parse_sheet_month(label):
        if not label or '-' not in label: return None
        try:
            parts = label.split('-')
            year = int(parts[0].strip())
            month_str = parts[1].strip().lower()
            
            month_map_rev = {
                'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'ago': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dic': 12
            }
            month_num = month_map_rev.get(month_str)
            if not month_num: return None
            
            # Devolvemos objeto fecha para comparar rangos y sort_key
            dt = datetime(year, month_num, 1)
            return {
                "dt": dt,
                "month_num": month_num,
                "label": meses_map[month_num],
                "year": year
            }
        except:
            return None

    try:
        # 1. --- PROCESAR RAW_VENTAS (Unidades Mensuales desglosadas y Rankings) ---
        ws_raw = sheets_client.get_worksheet("RAW_VENTAS")
        raw_values = ws_raw.get_all_values() if ws_raw else []
        
        # Almacenamos ventas Y pedidos por mes relativo (1-12) para alinear años
        # La columna H (index 7) de RAW_VENTAS indica "Pedidos" o "Ventas"
        unidades_mensuales = defaultdict(lambda: {
            "actual_ventas": 0, "actual_pedidos": 0,
            "prev_ventas": 0,   "prev_pedidos": 0
        })

        for i in range(1, len(raw_values)):
            row = raw_values[i]
            if len(row) < 6: continue
            
            fecha_str = row[2].strip()
            producto = row[1].strip()
            cantidad = clean_number(row[4])
            total_ingreso = clean_currency(row[5])
            clasificacion = row[7].strip().lower() if len(row) > 7 else "ventas"
            es_pedido = "pedido" in clasificacion

            if not fecha_str: continue

            try:
                dt_obj = None
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        dt_obj = datetime.strptime(fecha_str, fmt)
                        break
                    except: continue
                if not dt_obj: continue

                # A. Periodo actual (solo para unidades mensuales)
                if actual_start <= dt_obj <= actual_end:
                    # Acumular por tipo
                    if es_pedido:
                        unidades_mensuales[dt_obj.month]["actual_pedidos"] += cantidad
                    else:
                        unidades_mensuales[dt_obj.month]["actual_ventas"] += cantidad

                # B. Periodo anterior (mismo rango, año pasado)
                elif prev_start <= dt_obj <= prev_end:
                    if es_pedido:
                        unidades_mensuales[dt_obj.month]["prev_pedidos"] += cantidad
                    else:
                        unidades_mensuales[dt_obj.month]["prev_ventas"] += cantidad

            except: continue

        # 2. --- PROCESAR DB_DASHBOARD_VENTAS (Dinero y Presupuesto) ---
        ws_dash = sheets_client.get_worksheet("DB_DASHBOARD_VENTAS")
        # Almacenar dinero y pedidos por mes relativo — ambos años
        dinero_mensual = defaultdict(lambda: {
            "actual_v": 0, "actual_p": 0,
            "prev_v": 0,   "prev_p": 0
        })
        inc_unidades = []
        inc_dinero = []
        top_mejores_dinero = []
        top_mejores_unids  = []
        top_peores_dinero  = []
        top_peores_unids   = []
        
        if ws_dash:
            dash_values = ws_dash.get_all_values()
            cli_u, cli_d = "", ""
            ano_contexto = datetime.now().year

            for i in range(2, len(dash_values)):
                row = dash_values[i]
                row += [''] * (25 - len(row))
                
                # A. Mensual Summary (Cols A, B, C)
                val_a = row[0].strip()
                p_month = parse_sheet_month(val_a)
                if p_month:
                    dt = p_month["dt"]
                    month_num = p_month["month_num"]
                    ped_val = clean_currency(row[1])
                    ven_val = clean_currency(row[2])
                    
                    if actual_start <= dt <= actual_end:
                        dinero_mensual[month_num]["actual_p"] += ped_val
                        dinero_mensual[month_num]["actual_v"] += ven_val
                        ano_contexto = p_month["year"]
                    elif prev_start <= dt <= prev_end:
                        dinero_mensual[month_num]["prev_p"] += ped_val
                        dinero_mensual[month_num]["prev_v"] += ven_val

                # B. Top Productos Más Vendidos
                #    Dinero: Col G=6, H=7  |  Cantidad: Col I=8, J=9
                prod_mejor_d = row[6].strip() if len(row) > 6 else ""
                val_mejor_d  = clean_currency(row[7]) if len(row) > 7 else 0
                if prod_mejor_d and val_mejor_d > 0:
                    top_mejores_dinero.append({"producto": prod_mejor_d, "ventas_dinero": val_mejor_d})

                prod_mejor_u = row[8].strip() if len(row) > 8 else ""
                val_mejor_u  = clean_number(row[9]) if len(row) > 9 else 0
                if prod_mejor_u:
                    top_mejores_unids.append({"producto": prod_mejor_u, "ventas_unidades": val_mejor_u})

                # C. Top Productos Menos Vendidos
                #    Dinero: Col K=10, L=11  |  Cantidad: Col M=12, N=13
                prod_peor_d = row[10].strip() if len(row) > 10 else ""
                val_peor_d  = clean_currency(row[11]) if len(row) > 11 else 0
                if prod_peor_d and val_peor_d > 0:
                    top_peores_dinero.append({"producto": prod_peor_d, "ventas_dinero": val_peor_d})

                prod_peor_u = row[12].strip() if len(row) > 12 else ""
                val_peor_u  = clean_number(row[13]) if len(row) > 13 else 0
                if prod_peor_u:
                    top_peores_unids.append({"producto": prod_peor_u, "ventas_unidades": val_peor_u})

                # D. Bloque Incumplimiento Unidades (Col O=14, P=15, Q=17, R=18)
                if len(row) > 18:
                    u_cli_col = row[14].strip()
                    u_prod_col = row[15].strip()
                    
                    if u_cli_col:
                        if u_cli_col.lower().startswith("total "):
                            cli_u = u_cli_col[6:].strip()
                        else:
                            cli_u = u_cli_col
                    
                    if u_prod_col and cli_u and not u_prod_col.lower().startswith("total "):
                        p_unds = clean_number(row[17])
                        v_unds = clean_number(row[18])
                        fallo = max(0, p_unds - v_unds)
                        if fallo > 0:
                            inc_unidades.append({
                                "ano": ano_contexto, "cliente": cli_u, "producto": u_prod_col, 
                                "unidades_fallidas": fallo, "pedidos": p_unds, "ventas": v_unds
                            })

                # E. Bloque Incumplimiento Dinero (Col U=20, V=21, W=22, X=23)
                if len(row) > 23:
                    d_cli_col = row[20].strip()
                    d_prod_col = row[21].strip()
                    
                    if d_cli_col:
                        if d_cli_col.lower().startswith("total "):
                            cli_d = d_cli_col[6:].strip()
                        else:
                            cli_d = d_cli_col
                    
                    if d_prod_col and cli_d and not d_prod_col.lower().startswith("total "):
                        p_money = clean_currency(row[22])
                        v_money = clean_currency(row[23])
                        perdida = max(0, p_money - v_money)
                        if perdida >= 1000:
                            inc_dinero.append({
                                "ano": ano_contexto, "cliente": cli_d, "producto": d_prod_col, 
                                "dinero_perdido": perdida, "pedidos": p_money, "ventas": v_money
                            })

        # --- FORMATEAR RESPUESTA FINAL ---
        # Generar lista de meses basada en el rango seleccionado
        mensual_list = []
        curr = datetime(actual_start.year, actual_start.month, 1)
        limit = datetime(actual_end.year, actual_end.month, 1)
        
        while curr <= limit:
            m = curr.month
            mensual_list.append({
                "mes": meses_map[m],
                # Dinero (de DB_DASHBOARD_VENTAS — tabla pivote)
                "actual_dinero":   dinero_mensual[m]["actual_v"],
                "actual_pedidos":  dinero_mensual[m]["actual_p"],
                "prev_dinero":     dinero_mensual[m]["prev_v"],
                "prev_pedidos":    dinero_mensual[m]["prev_p"],
                # Unidades (de RAW_VENTAS — col Clasificacion)
                "actual_unidades":          unidades_mensuales[m]["actual_ventas"],
                "actual_pedidos_unidades":  unidades_mensuales[m]["actual_pedidos"],
                "prev_unidades":            unidades_mensuales[m]["prev_ventas"],
                "prev_pedidos_unidades":    unidades_mensuales[m]["prev_pedidos"]
            })
            # Siguiente mes
            if curr.month == 12: curr = curr.replace(year=curr.year+1, month=1)
            else: curr = curr.replace(month=curr.month+1)

        # Deduplicar top productos (la sheet puede tener filas repetidas)
        seen_mejor_d = set()
        top_mejores_d_dedup = []
        for p in top_mejores_dinero:
            if p["producto"] not in seen_mejor_d:
                seen_mejor_d.add(p["producto"])
                top_mejores_d_dedup.append(p)
                
        seen_mejor_u = set()
        top_mejores_u_dedup = []
        for p in top_mejores_unids:
            if p["producto"] not in seen_mejor_u:
                seen_mejor_u.add(p["producto"])
                top_mejores_u_dedup.append(p)
        
        seen_peor_d = set()
        top_peores_d_dedup = []
        for p in top_peores_dinero:
            if p["producto"] not in seen_peor_d:
                seen_peor_d.add(p["producto"])
                top_peores_d_dedup.append(p)

        seen_peor_u = set()
        top_peores_u_dedup = []
        for p in top_peores_unids:
            if p["producto"] not in seen_peor_u:
                seen_peor_u.add(p["producto"])
                top_peores_u_dedup.append(p)

        response_data = {
            "success": True,
            "status": "success",
            "data": {
                "mensual": mensual_list,
                "top_productos_dinero": top_mejores_d_dedup[:10],
                "top_productos_unidades": top_mejores_u_dedup[:10],
                "peores_productos_dinero": top_peores_d_dedup[:10],
                "peores_productos_unidades": top_peores_u_dedup[:10],
                "incumplimiento_unidades": sorted(inc_unidades, key=lambda x: x["unidades_fallidas"], reverse=True),
                "incumplimiento_dinero": sorted(inc_dinero, key=lambda x: x["dinero_perdido"], reverse=True),
                "incumplimiento_consolidado": [] # Se calcula abajo
            }
        }

        # --- CONSOLIDACIÓN POR CLIENTE PARA PANEL GERENCIAL ---
        consolidado_map = defaultdict(lambda: {"unidades": 0, "dinero": 0, "ano": ano_contexto})
        for item in inc_unidades:
            consolidado_map[item["cliente"]]["unidades"] += item["unidades_fallidas"]
        for item in inc_dinero:
            consolidado_map[item["cliente"]]["dinero"] += item["dinero_perdido"]
            
        inc_consolidado = []
        for cli, vals in consolidado_map.items():
            inc_consolidado.append({
                "cliente": cli,
                "unidades_fallidas": vals["unidades"],
                "dinero_perdido": vals["dinero"],
                "ano": vals["ano"]
            })
        
        response_data["data"]["incumplimiento_consolidado"] = sorted(inc_consolidado, key=lambda x: x["unidades_fallidas"], reverse=True)

        # Guardar en cache
        ADMIN_DASHBOARD_CACHE[cache_key] = {"timestamp": _time.time(), "data": response_data}
        print(f"DEBUG: ✅ Admin dashboard cacheado para {cache_key}")

        return jsonify(response_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
