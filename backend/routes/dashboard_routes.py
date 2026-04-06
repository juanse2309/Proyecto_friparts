"""
Rutas de dashboard.
"""
from flask import Blueprint, jsonify
from backend.repositories.dashboard_repository import dashboard_repo
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route('/', methods=['GET'])
def obtener_dashboard():
    """Obtiene estadísticas del dashboard."""
    try:
        estadisticas = dashboard_repo.obtener_estadisticas()
        
        return jsonify({
            'status': 'success',
            'produccion': estadisticas.get('produccion', {}),
            'ventas': estadisticas.get('ventas', {}),
            'stock_critico': estadisticas.get('stock', {}),
            'pnc': estadisticas.get('pnc', {})
        }), 200
        
    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Error obteniendo datos'
        }), 500

import time
import collections
import datetime
from flask import request
from backend.core.database import sheets_client as gc
from backend.config.settings import Hojas

# Cache con llave por filtro (Timeout: 10 mins)
# Estructura: {(desde, hasta): {"data": ..., "timestamp": ...}}
DASHBOARD_COMPLEX_CACHE = {}

def to_int_seguro(valor, default=0):
    try:
        if valor is None: return default
        if isinstance(valor, (int, float)): return int(valor)
        # Limpiar separadores de miles (puntos y comas)
        s = str(valor).strip().replace('.', '').replace(',', '')
        if s == '' or s.lower() == 'none': return default
        return int(float(s))
    except:
        return default

def clean_currency(val):
    if not val: return 0
    try:
        s = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
        return float(s)
    except ValueError:
        return 0


def parsear_fecha_dashboard(fecha_str):
    """Parsea DD/MM/YYYY o YYYY-MM-DD o objeto date/datetime"""
    if not fecha_str: return None
    if isinstance(fecha_str, (datetime.date, datetime.datetime)):
        return fecha_str.date() if isinstance(fecha_str, datetime.datetime) else fecha_str
    if not isinstance(fecha_str, str): return None
    try:
        if '-' in fecha_str:
            return datetime.datetime.strptime(fecha_str.split(' ')[0], '%Y-%m-%d').date()
        return datetime.datetime.strptime(fecha_str.split(' ')[0], '%d/%m/%Y').date()
    except:
        return None

def get_all_records_seguro(ws):
    """Obtiene registros de una hoja de forma robusta, manejando headers duplicados o vacíos."""
    if not ws: return []
    try:
        datos = ws.get_all_values()
        if not datos: return []
        
        headers = [h.strip() for h in datos[0]]
        # Manejar headers vacíos o duplicados para gspread.get_all_records() no falle
        # Pero aquí lo hacemos manual:
        last_valid_idx = -1
        for i, h in enumerate(headers):
            if h: last_valid_idx = i
            
        header_keys = []
        seen = {}
        for i in range(last_valid_idx + 1):
            h = headers[i]
            if not h:
                h = f"COL_{i}"
            if h in seen:
                seen[h] += 1
                h = f"{h}_{seen[h]}"
            else:
                seen[h] = 0
            header_keys.append(h)
            
        records = []
        for row in datos[1:]:
            record = {}
            for i, key in enumerate(header_keys):
                val = row[i] if i < len(row) else ""
                record[key] = val
            records.append(record)
        return records
    except Exception as e:
        logger.error(f"Error en get_all_records_seguro: {e}")
        return []


@dashboard_bp.route('/stats', methods=['GET'])
def obtener_metricas_bi():
    """
    Endpoint Unificado para Visión de Científico de Datos.
    Soporta ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
    """
    try:
        desde_str = request.args.get('desde')
        hasta_str = request.args.get('hasta')
        nocache = request.args.get('nocache')
        
        desde = parsear_fecha_dashboard(desde_str) if desde_str else None
        hasta = parsear_fecha_dashboard(hasta_str) if hasta_str else None
        
        cache_key = (str(desde), str(hasta))
        ahora = time.time()
        
        if nocache != '1' and cache_key in DASHBOARD_COMPLEX_CACHE:
            entry = DASHBOARD_COMPLEX_CACHE[cache_key]
            if ahora - entry["timestamp"] < 600:
                print(f"DEBUG: Sirviendo /stats desde CACHE para {cache_key}")
                return jsonify({"status": "success", "success": True, "data": entry["data"]}), 200

        # --- RECOPILACIÓN DE DATOS ---
        # 1. Inyección
        ws_iny = gc.get_worksheet(Hojas.INYECCION)
        reg_iny = get_all_records_seguro(ws_iny)
        
        # 2. Pulido
        ws_pul = gc.get_worksheet(Hojas.PULIDO)
        reg_pul = get_all_records_seguro(ws_pul)
        
        # 3. Pedidos
        ws_ped = gc.get_worksheet(Hojas.PEDIDOS)
        reg_ped = get_all_records_seguro(ws_ped)
        
        # 3.1 Ensambles (NUEVO para Dashboard BI)
        ws_ens = gc.get_worksheet(Hojas.ENSAMBLES)
        reg_ens = get_all_records_seguro(ws_ens)
        
        # 3.5 Costos (Opcional, no fallar si no existe)
        costos_map = {}
        puntos_map = {}
        tiempo_map = {}
        faltan_costos_pnc = set()
        try:
            ws_costos = gc.get_worksheet("DB_COSTOS")
            reg_costos = get_all_records_seguro(ws_costos)
            for r in reg_costos:
                ref = str(r.get("Referencia") or "").strip().upper()
                c_tot_str = r.get("Costo total")
                if c_tot_str is None:
                    c_tot_str = r.get("Costo_total", 0)
                cst = clean_currency(c_tot_str)
                if ref: 
                    costos_map[ref] = cst
                    pts_str = "1.0"
                    tmp_str = "0.0"
                    for k, v in r.items():
                        kl = str(k).upper().replace("_", " ")
                        if "PUNTOS" in kl and "PIEZA" in kl: pts_str = str(v)
                        if "TIEMPO" in kl: tmp_str = str(v)

                    try: puntos_map[ref] = float(pts_str.replace(',', '.').strip()) if pts_str.replace(',', '.').strip() else 1.0
                    except: puntos_map[ref] = 1.0
                    try: tiempo_map[ref] = float(tmp_str.replace(',', '.').strip()) if tmp_str.replace(',', '.').strip() else 0.0
                    except: tiempo_map[ref] = 0.0
        except Exception as e:
            logger.warning(f"No se pudo cargar DB_COSTOS para PNC: {e}")
        
        # 4. PNC (Scrap)
        ws_pnc_iny = gc.get_worksheet(Hojas.PNC_INYECCION)
        ws_pnc_pul = gc.get_worksheet(Hojas.PNC_PULIDO)
        ws_pnc_ens = gc.get_worksheet(Hojas.PNC_ENSAMBLE)
        ws_pnc_alm = gc.get_worksheet(Hojas.PNC)
        
        reg_pnc_iny = get_all_records_seguro(ws_pnc_iny)
        reg_pnc_pul = get_all_records_seguro(ws_pnc_pul)
        reg_pnc_ens = get_all_records_seguro(ws_pnc_ens)
        reg_pnc_alm = get_all_records_seguro(ws_pnc_alm)


        # --- PROCESAMIENTO ---
        MESES_ESP = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}

        import re
        import datetime
        def parse_time_to_seconds(time_str):
            try:
                if isinstance(time_str, datetime.datetime):
                    time_str = time_str.time()
                if isinstance(time_str, datetime.time):
                    return time_str.hour * 3600 + time_str.minute * 60 + time_str.second

                # Si viene como float (fracción de día de Excel/Sheets)
                if isinstance(time_str, (int, float)):
                    fragmento = float(time_str) % 1.0
                    return int(round(fragmento * 86400))
                
                s = str(time_str).strip().lower()
                if not s or s == 'none': return None
                
                # Extrae patrones como "12:30", "12.30", "1:45 pm", "13:00:00"
                match = re.search(r'(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*(am|pm)?', s)
                if match:
                    h = int(match.group(1))
                    m = int(match.group(2))
                    sec = int(match.group(3)) if match.group(3) else 0
                    ampm = match.group(4)
                    
                    if ampm:
                        if ampm == 'pm' and h < 12: h += 12
                        if ampm == 'am' and h == 12: h = 0
                    return h * 3600 + m * 60 + sec
            except:
                pass
            return None

        def calcular_segundos_reales(inicio, fin):
            try:
                # DEBUG TEMPORAL
                with open('time_debug.log', 'a', encoding='utf-8') as f:
                    f.write(f"inicio: '{inicio}' ({type(inicio)}), fin: '{fin}' ({type(fin)})\n")
            except: pass
            
            try:
                if not inicio or not fin: return 0
                s1 = parse_time_to_seconds(inicio)
                s2 = parse_time_to_seconds(fin)
                if s1 is None or s2 is None: return 0
                diff = s2 - s1
                if diff < 0:
                    diff += 86400  # Cruzó la medianoche
                return diff
            except Exception as e:
                print(f"DEBUG TIME FAIL: inicio={inicio}, fin={fin} Error: {e}")
                return 0

        stats = {
            "inyeccion": {
                "total_ok": 0, 
                "total_pnc": 0,
                "operadores": collections.defaultdict(lambda: collections.defaultdict(lambda: {"qty": 0, "fecha": ""})),
                "maquinas": collections.defaultdict(int),
                "fechas": collections.defaultdict(int)
            },
            "pulido": {
                "total_ok": 0, 
                "total_pnc": 0, 
                "operadores": collections.defaultdict(lambda: collections.defaultdict(lambda: {"qty": 0, "fecha": ""})),
                "pnc_ops": collections.defaultdict(int),
                "costo_pnc_ops": collections.defaultdict(float),
                "pnc_operario_ops": collections.defaultdict(int),
                "pnc_maquina_ops": collections.defaultdict(int),
                "costo_pnc_operario_ops": collections.defaultdict(float),
                "costo_pnc_maquina_ops": collections.defaultdict(float),
                "tiempo_real_ops": collections.defaultdict(float),
                "tiempo_std_ops": collections.defaultdict(float),
                "mensual": collections.defaultdict(lambda: {"piezas": 0, "std": 0, "real": 0}),
                "mensual_operadoras": collections.defaultdict(lambda: collections.defaultdict(float))
            },
            "pedidos": {"total_solicitado": 0},
            "ensamble": {
                "total_ok": 0,
                "tiempo_real_segundos": 0,
                "operadores": collections.defaultdict(int)
            },
            "pnc_total": {"inyeccion": 0, "pulido": 0, "ensamble": 0, "almacen": 0},
            "pnc_almacen_detalle": collections.defaultdict(lambda: {"cantidad": 0, "costo": 0}),
            "perdida_calidad_dinero": 0,
            "tendencia": collections.defaultdict(lambda: {"inyeccion": 0, "pulido": 0, "ensamble": 0})
        }
        
        # Helper interno para totalizar el impacto monetario PNC
        def sumar_perdida_pnc(producto, cantidad):
            prod_clean = str(producto or "GENERICO").strip().upper()
            if prod_clean not in costos_map and prod_clean != "GENERICO" and "SIN" not in prod_clean:
                faltan_costos_pnc.add(prod_clean)
            costo_unitario = costos_map.get(prod_clean, 0)
            costo_lote = cantidad * costo_unitario
            stats["perdida_calidad_dinero"] += costo_lote
            return costo_lote

        # Mapeos auxiliares para unir PNC con operadoras de forma robusta
        id_pul_to_op = {}
        id_pul_to_date = {} 
        id_iny_to_date = {}
        id_iny_to_prod = {}



        # Auxiliar para filtrar fecha
        def dentro_de_rango(f_str):
            if not desde and not hasta: return True
            f = parsear_fecha_dashboard(f_str)
            if not f: return False
            if desde and f < desde: return False
            if hasta and f > hasta: return False
            return True

        # Procesar Inyección
        for r in reg_iny:
            f_str = r.get("FECHA") or r.get("FECHA INICIA") or r.get("FECHA_INICIO")
            if not dentro_de_rango(f_str): continue
            
            ok = to_int_seguro(r.get("CANTIDAD REAL") or r.get("CANTIDAD_REAL"))
            pnc = to_int_seguro(r.get("PNC") or r.get("pnc") or r.get("CANTIDAD PNC"))
            op = str(r.get("RESPONSABLE") or r.get("RESPONSABLE ") or "").strip().upper()
            maq = str(r.get("MÁQUINA") or r.get("MAQUINA") or "").strip().upper()
            prod = str(r.get("CODIGO") or r.get("codigo") or r.get("ID CODIGO") or "GENERICO").strip().upper()
            
            if not op or op == "NONE": continue # Saneamiento
            
            # Guardar relación ID -> Fecha/Producto para el PNC
            id_iny = str(r.get("ID INYECCION") or "").strip()
            if id_iny: 
                id_iny_to_date[id_iny] = f_str
                id_iny_to_prod[id_iny] = prod

            stats["inyeccion"]["total_ok"] += ok
            stats["inyeccion"]["total_pnc"] += pnc
            stats["inyeccion"]["operadores"][op][prod]["qty"] += ok
            # Guardamos la fecha más reciente si hay varias
            curr_date = str(parsear_fecha_dashboard(f_str)) if f_str else ""
            if curr_date > stats["inyeccion"]["operadores"][op][prod]["fecha"]:
                stats["inyeccion"]["operadores"][op][prod]["fecha"] = curr_date

            if maq: stats["inyeccion"]["maquinas"][maq] += ok
            
            f_dt = parsear_fecha_dashboard(f_str)
            if f_dt: stats["tendencia"][str(f_dt)]["inyeccion"] += ok
            if f_dt: stats["inyeccion"]["fechas"][str(f_dt)] += ok # Added for daily totals


        # Procesar Pulido (Ranking Profundo)
        for r in reg_pul:
            f_str = r.get("FECHA") or r.get("fecha")
            if not dentro_de_rango(f_str): continue
            
            ok = to_int_seguro(r.get("CANTIDAD REAL") or r.get("BUJES BUENOS"))
            pnc = to_int_seguro(r.get("PNC"))
            op = str(r.get("RESPONSABLE") or r.get("responsable") or r.get("RESPONSABLE ") or "").strip().upper()
            prod = str(r.get("CODIGO") or r.get("codigo") or r.get("ID CODIGO") or "GENERICO").strip().upper()
            
            if not op or op == "NONE": continue
            
            # Matemática de Tiempos
            h_ini = r.get("HORA INICIO") or r.get("hora_inicio") or ""
            h_fin = r.get("HORA FIN") or r.get("hora_fin") or ""
            segundos_reales = calcular_segundos_reales(h_ini, h_fin)
            segundos_std_unitario = tiempo_map.get(prod, 0.0)
            segundos_std_totales = ok * segundos_std_unitario

            # Guardar relación ID -> Operador/Fecha para el PNC
            id_pul = str(r.get("ID PULIDO") or "").strip()
            f_dt = parsear_fecha_dashboard(f_str)
            if id_pul: 
                id_pul_to_op[id_pul] = op
                id_pul_to_date[id_pul] = f_dt # Guardar como objeto date

            stats["pulido"]["total_ok"] += ok
            stats["pulido"]["total_pnc"] += pnc
            stats["pulido"]["operadores"][op][prod]["qty"] += ok
            # Guardamos la fecha más reciente
            curr_date = str(f_dt) if f_dt else ""
            if curr_date > stats["pulido"]["operadores"][op][prod]["fecha"]:
                stats["pulido"]["operadores"][op][prod]["fecha"] = curr_date

            stats["pulido"]["tiempo_real_ops"][op] += segundos_reales
            stats["pulido"]["tiempo_std_ops"][op] += segundos_std_totales

            if f_dt:
                key_mes = f"{MESES_ESP.get(f_dt.month, 'S/M')} {f_dt.year}"
                stats["pulido"]["mensual"][key_mes]["piezas"] += ok
                stats["pulido"]["mensual"][key_mes]["std"] += segundos_std_totales
                stats["pulido"]["mensual"][key_mes]["real"] += segundos_reales
                
                # Sumar los puntos obtenidos en este mes para esa operadora
                stats["pulido"]["mensual_operadoras"][key_mes][op] += ok * puntos_map.get(prod, 1.0)
                
                stats["tendencia"][str(f_dt)]["pulido"] += ok


        # Procesar Pedidos (Fulfillment)
        for r in reg_ped:
            f_str = r.get("FECHA")
            if not dentro_de_rango(f_str): continue
            cant = to_int_seguro(r.get("CANTIDAD"))
            stats["pedidos"]["total_solicitado"] += cant

        # Procesar Scrap (PNC)
        # Soportar tanto 'CANTIDAD PNC' (app.py) con 'CANTIDAD' (hojas crudas)
        for r in reg_pnc_iny:
            f_pnc = r.get("FECHA") or r.get("fecha")
            id_iny = str(r.get("ID INYECCION") or "").strip()
            # Si no hay fecha en PNC, usar la de la producción vinculada
            if not f_pnc and id_iny in id_iny_to_date:
                f_pnc = id_iny_to_date[id_iny]
            
            if dentro_de_rango(f_pnc): 
                cant = to_int_seguro(r.get("CANTIDAD PNC") or r.get("CANTIDAD"))
                stats["pnc_total"]["inyeccion"] += cant
                
                prod_iny = id_iny_to_prod.get(id_iny, "GENERICO")
                sumar_perdida_pnc(prod_iny, cant)
        
        for r in reg_pnc_pul:
            id_pul = str(r.get("ID PULIDO") or "").strip()
            op_pnc = id_pul_to_op.get(id_pul)
            f_pnc = r.get("FECHA") or r.get("fecha") or id_pul_to_date.get(id_pul) # Objeto date o str
            # Obtención de Razón más robusta (revisa varios posibles nombres de columna)
            razon_raw = r.get("RAZÓN") or r.get("RAZON") or r.get("MOTIVO") or r.get("DEFECTO") or r.get("OBSERVACIONES") or ""
            razon = str(razon_raw).strip().lower()

            if dentro_de_rango(f_pnc): 
                cant = to_int_seguro(r.get("CANTIDAD PNC") or r.get("CANTIDAD"))
                prod_pnc = str(r.get("CODIGO", "") or "GENERICO").strip()
                stats["pnc_total"]["pulido"] += cant
                cost_lote = sumar_perdida_pnc(prod_pnc, cant)
                
                if op_pnc:
                    # Clasificación por Razón (Refinado por User Feedback)
                    # Se consideran FALLA MÁQUINA si provienen de procesos previos o fallas técnicas
                    keywords_maquina = [
                        "maquina", "máquina", "porosidad", "fundición", "fundicion", 
                        "mecanizado", "rechupe", "manchado", "contaminado", "escaso",
                        "inyeccion", "inyección", "molde", "materia", "falla"
                    ]
                    es_maquina = any(kw in razon for kw in keywords_maquina)
                    
                    if es_maquina:
                        stats["pulido"]["pnc_maquina_ops"][op_pnc] += cant
                        stats["pulido"]["costo_pnc_maquina_ops"][op_pnc] += cost_lote
                    else:
                        stats["pulido"]["pnc_operario_ops"][op_pnc] += cant
                        stats["pulido"]["costo_pnc_operario_ops"][op_pnc] += cost_lote
                        
                    # Mantener compatibilidad
                    stats["pulido"]["pnc_ops"][op_pnc] += cant
                    stats["pulido"]["costo_pnc_ops"][op_pnc] += cost_lote

        for r in (reg_pnc_ens or []):
            f_pnc = r.get("FECHA") or r.get("fecha")
            if dentro_de_rango(f_pnc): 
                cant = to_int_seguro(r.get("CANTIDAD PNC") or r.get("CANTIDAD"))
                stats["pnc_total"]["ensamble"] += cant
                prod_ens = str(r.get("CODIGO", "") or "GENERICO").strip()
                sumar_perdida_pnc(prod_ens, cant)

        # 4.1 Procesar Ensambles OK (Deduplicación Especial)
        # Agrupamos por bloque exacto para evitar triplicar kits (CB, INT, CAR)
        # Y rastreamos intervalos para Auditoría de Solapamientos
        ens_blocks = {} # (op, fecha, h_ini, h_fin) -> max_qty
        op_intervals_ens = collections.defaultdict(list) # (op, fecha) -> [(s_start, s_end, qty)]

        for r in (reg_ens or []):
            f_str = str(r.get("FECHA") or r.get("fecha") or "").strip()
            if not dentro_de_rango(f_str): continue
            
            op = str(r.get("OPERARIO") or r.get("RESPONSABLE") or "").strip().upper()
            h_ini = r.get("HORA INICIO") or r.get("HORA_INICIO") or ""
            h_fin = r.get("HORA FIN") or r.get("HORA_FIN") or ""
            qty = to_int_seguro(r.get("CANTIDAD") or r.get("CANTIDAD REAL"))
            
            if not op or not f_str: continue
            
            # Deduplicación de Kit: Si son las mismas horas y operario, es la misma producción
            block_key = (op, f_str, h_ini, h_fin)
            if block_key not in ens_blocks:
                ens_blocks[block_key] = qty
                s_start = parse_time_to_seconds(h_ini)
                s_end = parse_time_to_seconds(h_fin)
                if s_start is not None and s_end is not None:
                    # Rastrear para Auditoría de Solapamientos (Diferentes kits en mismo horario)
                    op_intervals_ens[(op, f_str)].append((s_start, s_end, qty))

        # Suma Inteligente con Unión de Intervalos (Evitar solapamientos de tiempo)
        for (op, f_str), intervals in op_intervals_ens.items():
            intervals.sort() # Ordenar por inicio
            
            last_end = -1
            f_dt = parsear_fecha_dashboard(f_str)
            
            for s_start, s_end, qty in intervals:
                # 1. Sumar cantidad (contamos cada bloque único como producción completa)
                stats["ensamble"]["total_ok"] += qty
                stats["ensamble"]["operadores"][op] += qty
                if f_dt:
                    stats["tendencia"][str(f_dt)]["ensamble"] += qty
                
                # 2. Calcular tiempo real sin solapamientos
                if s_start >= last_end:
                    # Bloque secuencial o nuevo
                    diff = s_end - s_start
                    if diff < 0: diff += 86400
                    stats["ensamble"]["tiempo_real_segundos"] += diff
                    last_end = s_end
                else:
                    # Solapamiento: solo sumamos la parte nueva si termina después
                    if s_end > last_end:
                        diff = s_end - last_end
                        if diff < 0: diff += 86400
                        stats["ensamble"]["tiempo_real_segundos"] += diff
                        last_end = s_end
                    # Si no termina después, está contenido totalmente, no suma tiempo extra

        for r in reg_pnc_alm:
            f_pnc = r.get("FECHA") or r.get("fecha")
            if dentro_de_rango(f_pnc): 
                cant = to_int_seguro(r.get("CANTIDAD PNC") or r.get("CANTIDAD"))
                prod_pnc = str(r.get("ID CODIGO", "") or r.get("CODIGO ENSAMBLE", "") or r.get("ID PRODUCTO", "") or r.get("PRODUCTO", "") or r.get("CODIGO", "")).strip()
                if not prod_pnc: prod_pnc = "Sin ID"
                stats["pnc_total"]["almacen"] += cant
                cost_lote = sumar_perdida_pnc(prod_pnc, cant)
                stats["pnc_almacen_detalle"][prod_pnc]["cantidad"] += cant
                stats["pnc_almacen_detalle"][prod_pnc]["costo"] += cost_lote





        # --- FORMATEO FINAL ---
        fulfillment_rate = 0
        if stats["pedidos"]["total_solicitado"] > 0:
            fulfillment_rate = round((stats["inyeccion"]["total_ok"] / stats["pedidos"]["total_solicitado"]) * 100, 1)

        # --- Rankings Pulido ---
        rank_pulido = {}
        for op, prods in stats["pulido"]["operadores"].items():
            buenas_totales = sum(d["qty"] for d in prods.values())
            # [LIMPIEZA]: Si no tiene piezas buenas en el rango, no lo incluimos
            if buenas_totales == 0: continue
            
            pnc_propio = stats["pulido"]["pnc_operario_ops"][op]
            pnc_maquina = stats["pulido"]["pnc_maquina_ops"][op]
            
            # [JUSTICIA]: Yield solo afecta por PNC Propio
            yield_calidad = round((buenas_totales / (buenas_totales + pnc_propio) * 100), 1) if (buenas_totales + pnc_propio) > 0 else 0
            
            rank_pulido[op] = {
                "nombre": op,
                "buenas": buenas_totales,
                "pnc_propio": pnc_propio,
                "pnc_maquina": pnc_maquina,
                "yield_calidad": yield_calidad,
                "eficiencia_productiva_pct": round((stats["pulido"]["tiempo_std_ops"][op] / stats["pulido"]["tiempo_real_ops"][op] * 100), 1) if stats["pulido"]["tiempo_real_ops"][op] > 0 else 0,
                "puntos_reales": sum(d["qty"] * puntos_map.get(p, 1.0) for p, d in prods.items()),
                "operario_referencia": sorted([
                    {"ref": p, "cantidad": d["qty"], "ultima_fecha": d["fecha"], "pts_u": puntos_map.get(p, 1.0), "costo_u": costos_map.get(p, 0.0)} 
                    for p, d in prods.items()
                ], key=lambda x: x["cantidad"], reverse=True)
            }

        result_data = {
            "rango": {"desde": str(desde) if desde else "Inicio", "hasta": str(hasta) if hasta else "Fin"},
            "kpis": {
                "inyeccion_ok": stats["inyeccion"]["total_ok"],
                "pulido_ok": stats["pulido"]["total_ok"],
                "pedidos_solicitado": stats["pedidos"]["total_solicitado"],
                "cumplimiento_pct": fulfillment_rate,
                "perdida_calidad_dinero": stats["perdida_calidad_dinero"],
                "scrap_total": sum(stats["pnc_total"].values()),
                "scrap_detalle": stats["pnc_total"],
                "scrap_almacen_desglose": sorted([{"producto": k, "cantidad": v["cantidad"], "costo": v["costo"]} for k, v in stats["pnc_almacen_detalle"].items()], key=lambda x: x["cantidad"], reverse=True),
                "faltan_costos_pnc": list(faltan_costos_pnc)
            },
            "rankings": {
                "inyeccion_ops": sorted([
                    {
                        "nombre": op, 
                        "valor": sum(d["qty"] for d in prods.values()), 
                        "mix": sorted([{"prod": p, "qty": d["qty"], "fecha": d["fecha"], "pts": d["qty"] * puntos_map.get(p, 1.0), "u_pts": puntos_map.get(p, 1.0)} for p, d in prods.items()], key=lambda x: x["qty"], reverse=True),
                        "insight": f"Operador enfocado en: {sorted([{'prod': p, 'qty': d['qty']} for p, d in prods.items()], key=lambda x: x['qty'], reverse=True)[0]['prod'] if prods else 'Variado'}"
                    } for op, prods in stats["inyeccion"]["operadores"].items()
                ], key=lambda x: x["valor"], reverse=True), # Removemos el [:10] para mandar todos
                "pulido_profundo": {
                    op: {
                        "mix": sorted([
                            {
                                "prod": p, 
                                "qty": q["qty"], 
                                "pts": q["qty"] * puntos_map.get(p, 1.0), 
                                "u_pts": puntos_map.get(p, 1.0),
                                "costo": costos_map.get(p, 0.0),
                                "fecha": q["fecha"]
                            } for p, q in prods.items()
                        ], key=lambda x: x["qty"], reverse=True),
                        "buenas": sum(d["qty"] for d in prods.values()),
                        "puntos": sum([d["qty"] * puntos_map.get(p, 1.0) for p, d in prods.items()]),
                        "tiempo_estandar": sum([d["qty"] * tiempo_map.get(p, 0.0) for p, d in prods.items()]),
                        "eficiencia_productiva_pct": round((stats["pulido"]["tiempo_std_ops"].get(op, 0) / stats["pulido"]["tiempo_real_ops"].get(op, 1e-9) * 100), 1) if stats["pulido"]["tiempo_real_ops"].get(op, 0) > 0 else 0,
                        "pnc": stats["pulido"]["pnc_ops"].get(op, 0),
                        "pnc_operario": stats["pulido"]["pnc_operario_ops"].get(op, 0),
                        "pnc_maquina": stats["pulido"]["pnc_maquina_ops"].get(op, 0),
                        "costo_pnc": stats["pulido"]["costo_pnc_ops"].get(op, 0),
                        "yield_calidad": round((sum(d["qty"] for d in prods.values()) / (sum(d["qty"] for d in prods.values()) + stats["pulido"]["pnc_operario_ops"].get(op, 0)) * 100), 1) if (sum(d["qty"] for d in prods.values()) + stats["pulido"]["pnc_operario_ops"].get(op, 0)) > 0 else 100,
                        "insight": f"Especialista destacado en este rango, produciendo principalmente: {sorted([{'prod': p, 'qty': d['qty']} for p, d in prods.items()], key=lambda x: x['qty'], reverse=True)[0]['prod'] if prods else 'Variado'}"
                    } for op, prods in stats["pulido"]["operadores"].items() if sum(d["qty"] for d in prods.values()) > 0
                }
            },

            "analytics_pulido": {
                "consolidado_mensual": sorted([
                    {
                        "mes": m,
                        "total_piezas": v["piezas"],
                        "eficiencia_productiva_promedio": round((v["std"] / v["real"] * 100), 1) if v["real"] > 0 else 0
                    } for m, v in stats["pulido"]["mensual"].items()
                ], key=lambda x: x["mes"], reverse=True),

                "merma_por_origen": {
                    "maquina": sum(stats["pulido"]["pnc_maquina_ops"].values()),
                    "operario": sum(stats["pulido"]["pnc_operario_ops"].values())
                },
                
                "evolucion_puntos_op": {
                    m: {op: pts for op, pts in ops.items() if pts > 0} 
                    for m, ops in stats["pulido"]["mensual_operadoras"].items()
                },
                
                "operario_referencia": {op: {
                    p: {
                        "cantidad_total": d["qty"],
                        "puntos_unidad": puntos_map.get(p, 1.0),
                        "costo_unidad": costos_map.get(p, 0.0),
                        "ultima_fecha": d["fecha"]
                    } for p, d in prods.items()
                } for op, prods in stats["pulido"]["operadores"].items() if sum(d["qty"] for d in prods.values()) > 0}
            },

            "maquinas": sorted([{"maquina": k, "valor": v} for k, v in stats["inyeccion"]["maquinas"].items()], key=lambda x: x["valor"], reverse=True),
            "tendencia": sorted([{"fecha": k, "iny": v["inyeccion"], "pul": v["pulido"]} for k, v in stats["tendencia"].items()], key=lambda x: x["fecha"])
        }

        # --- IA INSIGHTS MULTI-VARIABLE (CARROUSEL) ---
        insights = []
        
        # 1. Cumplimiento
        insights.append(f"Tasa de cumplimiento: {fulfillment_rate}%. {'Objetivo superado 🎯' if fulfillment_rate >= 100 else 'Pendiente por completar.'}")
        
        # 2. Cuellos de botella
        if stats["inyeccion"]["total_ok"] > stats["pulido"]["total_ok"]:
            diff = stats["inyeccion"]["total_ok"] - stats["pulido"]["total_ok"]
            insights.append(f"Cuello de botella: Pulido tiene {diff:,} piezas en cola acumuladas.")
        else:
            insights.append("Flujo de producción: El ritmo de Inyección y Pulido está perfectamente sincronizado.")

        # 3. Scrap / PNC (Refinado)
        merma_maquina = result_data["analytics_pulido"]["merma_por_origen"]["maquina"]
        merma_operador = result_data["analytics_pulido"]["merma_por_origen"]["operario"]
        total_scrap = merma_maquina + merma_operador
        
        if total_scrap > 0:
            if merma_maquina > merma_operador:
                insights.append(f"Calidad: El {round((merma_maquina/total_scrap)*100)}% del scrap viene de fallas técnicas (Máquina/Porosidad). Se recomienda mantenimiento.")
            else:
                insights.append(f"Calidad: Se detectó un {round((merma_operador/total_scrap)*100)}% de merma por error humano. Reforzar capacitación en técnica de pulido.")
            
        # 4. Top Performance & Productividad
        if stats["pulido"]["operadores"]:
            # Líder de Volumen
            top_pul_vol = max(result_data["rankings"]["pulido_profundo"].items(), key=lambda x: x[1]["buenas"])[0]
            # Líder de Calidad (Mejor Yield ignorando máquina)
            top_pul_cal = max(result_data["rankings"]["pulido_profundo"].items(), key=lambda x: x[1]["yield_calidad"])[0]
            # Líder de Eficiencia Real (Tiempo)
            top_pul_ef = max(result_data["rankings"]["pulido_profundo"].items(), key=lambda x: x[1]["eficiencia_productiva_pct"])[0]
            
            insights.append(f"Líder de Pulido: {top_pul_vol} tiene la mayor producción de piezas.")
            insights.append(f"Eficiencia: {top_pul_ef} destaca con el mejor ritmo de trabajo vs tiempo estándar.")
            insights.append(f"Estrella de Calidad: {top_pul_cal} mantiene el mejor promedio de piezas perfectas (Yield Real).")

        if stats["inyeccion"]["operadores"]:
            top_iny = max(stats["inyeccion"]["operadores"].items(), key=lambda x: sum(d["qty"] for d in x[1].values()))[0]
            insights.append(f"Líder de Inyección: {top_iny} es el operador más productivo del periodo.")

        result_data["insights_ia"] = insights
        # Mantener retrocompatibilidad
        result_data["insight_ia"] = insights[0] if insights else "Esperando datos..." # Corrected line
        # Cachear resultado
        DASHBOARD_COMPLEX_CACHE[cache_key] = {"data": result_data, "timestamp": ahora}
        
        print("DEBUG: /stats procesado correctamente. Enviando datos.")
        return jsonify({"status": "success", "success": True, "data": result_data}), 200


    except Exception as e:
        logger.error(f"Error en dashboard BI: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Mantener rutas viejas por compatibilidad si es necesario o redireccionarlas
@dashboard_bp.route('/inyeccion', methods=['GET'])
def metricas_inyeccion_legacy():
    return obtener_metricas_bi()

@dashboard_bp.route('/pulido', methods=['GET'])
def metricas_pulido_legacy():
    return obtener_metricas_bi()