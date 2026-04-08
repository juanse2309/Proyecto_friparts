from flask import Blueprint, jsonify, render_template, Response
from backend.utils.auth_middleware import require_role
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import difflib
import csv
import io

admin_bp = Blueprint('admin_bp', __name__)

# Cache para el endpoint de admin dashboard (10 min TTL)
import time as _time
ADMIN_DASHBOARD_CACHE = {}  # key: (start, end) -> {"timestamp": float, "data": dict}
ADMIN_CACHE_TTL = 600  # 10 minutos

# Helper function to clean currency strings to int/float (Precision Fix)
def clean_currency(val):
    if not val: return 0.0
    if isinstance(val, (int, float)): return float(val)
    # Requerimiento: replace('$', '').replace('.', '').replace(',', '.')
    s = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(s)
    except:
        return 0.0

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
        # Asegurar que tome hasta el final del día actual (Ej: 30 de marzo inclusive)
        actual_end = datetime.now().replace(hour=23, minute=59, second=59)

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
        # 1. --- PROCESAR RAW_VENTAS (Métricas y Rankings) ---
        ws_raw = sheets_client.get_worksheet("RAW_VENTAS")
        raw_values = ws_raw.get_all_values() if ws_raw else []
        
        # Almacenamos métricas consolidadas (Dinero y Unidades) directamente desde RAW_VENTAS
        stats_mensuales = defaultdict(lambda: {
            "actual_total_dinero": 0.0, "actual_pedidos_dinero": 0.0,
            "actual_total_unid": 0,    "actual_pedidos_unid": 0,
            "prev_total_dinero": 0.0,   "prev_pedidos_dinero": 0.0,
            "prev_total_unid": 0,      "prev_pedidos_unid": 0
        })

        for i in range(1, len(raw_values)):
            row = raw_values[i]
            if len(row) < 8: continue # Col H es index 7
            
            fecha_str = row[2].strip()
            cantidad = clean_number(row[4])
            total_ingreso = clean_currency(row[5])
            clasificacion = row[7].strip().lower()
            es_pedido = "pedido" in clasificacion

            if not fecha_str: continue

            try:
                # Filtrar registros cancelados (búsqueda en toda la fila para mayor robustez)
                if any(str(cell).strip().upper() == "CANCELADO" for cell in row):
                    continue

                dt_obj = None
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        dt_obj = datetime.strptime(fecha_str, fmt)
                        break
                    except: continue
                if not dt_obj: continue

                m = dt_obj.month

                # A. Periodo actual
                if actual_start <= dt_obj <= actual_end:
                    if es_pedido:
                        # La métrica "Pedidos" (línea naranja) suma solo registros tipo PEDIDO
                        stats_mensuales[m]["actual_pedidos_dinero"] += total_ingreso
                        stats_mensuales[m]["actual_pedidos_unid"] += cantidad
                    else:
                        # La métrica "Ventas" (barra azul) suma solo registros tipo VENTA (Facturadas)
                        # Esto asegura que no se sumen pedidos en las barras, evitando discrepancias de escala.
                        stats_mensuales[m]["actual_total_dinero"] += total_ingreso
                        stats_mensuales[m]["actual_total_unid"] += cantidad

                # B. Periodo anterior
                elif prev_start <= dt_obj <= prev_end:
                    if es_pedido:
                        stats_mensuales[m]["prev_pedidos_dinero"] += total_ingreso
                        stats_mensuales[m]["prev_pedidos_unid"] += cantidad
                    else:
                        stats_mensuales[m]["prev_total_dinero"] += total_ingreso
                        stats_mensuales[m]["prev_total_unid"] += cantidad

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
                
                # A. Mensual Summary (SALTADO: Se usa RAW_VENTAS para mayor precisión)
                val_a = row[0].strip()
                p_month = parse_sheet_month(val_a)
                # (Ignoramos Cols A, B, C de DB_DASHBOARD_VENTAS para dinero_mensual)

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
                # DINERO (Calculado directamente de RAW_VENTAS)
                "actual_dinero":   stats_mensuales[m]["actual_total_dinero"], # Suma Ventas + Pedidos
                "actual_pedidos":  stats_mensuales[m]["actual_pedidos_dinero"],
                "prev_dinero":     stats_mensuales[m]["prev_total_dinero"],
                "prev_pedidos":    stats_mensuales[m]["prev_pedidos_dinero"],
                # UNIDADES (Calculadas directamente de RAW_VENTAS)
                "actual_unidades":          stats_mensuales[m]["actual_total_unid"],
                "actual_pedidos_unidades":  stats_mensuales[m]["actual_pedidos_unid"],
                "prev_unidades":            stats_mensuales[m]["prev_total_unid"],
                "prev_pedidos_unidades":    stats_mensuales[m]["prev_pedidos_unid"]
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

@admin_bp.route('/api/admin/auditoria-fichas', methods=['GET'])
@require_role(['admin', 'administrador', 'administracion', 'gerencia'])
def auditoria_fichas_fuzzy():
    """
    Realiza una auditoría de nombres (Fuzzy Matching) entre la nueva ficha maestra
    y las hojas de producción existentes, exportando los resultados en un archivo CSV.
    """
    try:
        # 1. Obtener datos de la NUEVA_FICHA_MAESTRA
        ws_nueva = sheets_client.get_worksheet(Hojas.NUEVA_FICHA_MAESTRA)
        if not ws_nueva:
            return jsonify({"success": False, "error": "No se encontró la hoja NUEVA_FICHA_MAESTRA"}), 404
        
        datos_nuevos = sheets_client.get_all_records_seguro(ws_nueva)
        
        # Filtrar filas de "Total" y extraer nombres únicos
        nuevos_nombres = set()
        for r in datos_nuevos:
            prod = str(r.get("Producto", "")).strip()
            subprod = str(r.get("SubProducto", "")).strip()
            
            if not prod or "total" in prod.lower():
                continue
                
            nuevos_nombres.add(prod)
            if subprod and "total" not in subprod.lower():
                nuevos_nombres.add(subprod)

        # 2. Obtener nombres existentes de las hojas de origen
        def extraer_nombres_unicos(nombre_hoja, columnas):
            ws = sheets_client.get_worksheet(nombre_hoja)
            if not ws: return set()
            records = sheets_client.get_all_records_seguro(ws)
            nombres = set()
            for r in records:
                for col in columnas:
                    val = str(r.get(col, "")).strip()
                    if val and "total" not in val.lower():
                        nombres.add(val)
            return nombres

        nombres_iny = extraer_nombres_unicos(Hojas.INYECCION, ["PRODUCTO", "ID CODIGO", "CODIGO"])
        nombres_pul = extraer_nombres_unicos(Hojas.PULIDO, ["PRODUCTO", "ID CODIGO", "CODIGO"])

        # Mapeo de búsqueda: nombre -> hoja_origen
        existentes_map = {}
        for n in nombres_iny: existentes_map[n] = "INYECCION"
        for n in nombres_pul: existentes_map[n] = "PULIDO"

        existentes_lista = list(existentes_map.keys())

        # 3. Realizar Fuzzy Matching
        mapeo_propuesto = []
        for nombre_nuevo in sorted(list(nuevos_nombres)):
            coincidencias = difflib.get_close_matches(nombre_nuevo, existentes_lista, n=1, cutoff=0.3)
            
            if coincidencias:
                mejor_match = coincidencias[0]
                confianza = difflib.SequenceMatcher(None, nombre_nuevo, mejor_match).ratio()
                origen = existentes_map[mejor_match]
            else:
                mejor_match = "SIN COINCIDENCIA"
                confianza = 0.0
                origen = "N/A"

            mapeo_propuesto.append({
                "Nombre_Nuevo_Maestra": nombre_nuevo,
                "Mejor_Coincidencia_Actual": mejor_match,
                "Porcentaje_Confianza": f"{round(confianza * 100, 1)}%",
                "Hoja_Origen_Actual": origen
            })

        # 4. Generar CSV en memoria (StringIO)
        output = io.StringIO()
        fieldnames = ["Nombre_Nuevo_Maestra", "Mejor_Coincidencia_Actual", "Porcentaje_Confianza", "Hoja_Origen_Actual"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(mapeo_propuesto)
        
        # 5. Retornar el archivo como descarga
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=auditoria_fichas_mapping.csv"}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
