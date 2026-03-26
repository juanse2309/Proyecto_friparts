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
        
        # 3.5 Costos (Opcional, no fallar si no existe)
        costos_map = {}
        puntos_map = {}
        tiempo_map = {}
        faltan_costos_pnc = set()
        try:
            ws_costos = gc.get_worksheet("DB_COSTOS")
            reg_costos = gc.get_all_records_seguro(ws_costos)
            for r in reg_costos:
                ref = str(r.get("Referencia") or "").strip().upper()
                c_tot_str = r.get("Costo total")
                if c_tot_str is None:
                    c_tot_str = r.get("Costo_total", 0)
                cst = clean_currency(c_tot_str)
                if ref: 
                    costos_map[ref] = cst
                    pts_str = str(r.get("Puntos_por_pieza") or r.get("Puntos por pieza") or 1.0)
                    tmp_str = str(r.get("Tiempo_estandar") or r.get("Tiempo estandar") or 0.0)
                    try: puntos_map[ref] = float(pts_str)
                    except: puntos_map[ref] = 1.0
                    try: tiempo_map[ref] = float(tmp_str)
                    except: tiempo_map[ref] = 0.0
        except Exception as e:
            logger.warning(f"No se pudo cargar DB_COSTOS para PNC: {e}")
        
        # 4. PNC (Scrap)
        ws_pnc_iny = gc.get_worksheet(Hojas.PNC_INYECCION)
        ws_pnc_pul = gc.get_worksheet(Hojas.PNC_PULIDO)
        ws_pnc_ens = gc.get_worksheet(Hojas.PNC_ENSAMBLE)
        ws_pnc_alm = gc.get_worksheet(Hojas.PNC)
        
        reg_pnc_iny = gc.get_all_records_seguro(ws_pnc_iny)
        reg_pnc_pul = gc.get_all_records_seguro(ws_pnc_pul)
        reg_pnc_ens = gc.get_all_records_seguro(ws_pnc_ens)
        reg_pnc_alm = gc.get_all_records_seguro(ws_pnc_alm)


        # --- PROCESAMIENTO ---
        stats = {
            "inyeccion": {
                "total_ok": 0, # Renamed from total_pz to total_ok for consistency with pulido
                "total_pnc": 0,
                "operadores": collections.defaultdict(lambda: collections.defaultdict(int)),
                "maquinas": collections.defaultdict(int),
                "fechas": collections.defaultdict(int)
            },
            "pulido": {
                "total_ok": 0, 
                "total_pnc": 0, 
                "operadores": collections.defaultdict(lambda: collections.defaultdict(int)),
                "pnc_ops": collections.defaultdict(int),
                "costo_pnc_ops": collections.defaultdict(float)
            },
            "pedidos": {"total_solicitado": 0},
            "pnc_total": {"inyeccion": 0, "pulido": 0, "ensamble": 0, "almacen": 0},
            "pnc_almacen_detalle": collections.defaultdict(lambda: {"cantidad": 0, "costo": 0}),
            "perdida_calidad_dinero": 0,
            "tendencia": collections.defaultdict(lambda: {"inyeccion": 0, "pulido": 0})
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
            stats["inyeccion"]["operadores"][op][prod] += ok # Changed to nested defaultdict
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
            # OJO: La hoja tiene un espacio al final "RESPONSABLE "
            op = str(r.get("RESPONSABLE") or r.get("responsable") or r.get("RESPONSABLE ") or "").strip().upper()
            prod = str(r.get("CODIGO") or r.get("codigo") or r.get("ID CODIGO") or "GENERICO").strip().upper()
            
            if not op or op == "NONE": continue
            
            # Guardar relación ID -> Operador/Fecha para el PNC
            id_pul = str(r.get("ID PULIDO") or "").strip()
            f_dt = parsear_fecha_dashboard(f_str)
            if id_pul: 
                id_pul_to_op[id_pul] = op
                id_pul_to_date[id_pul] = f_dt # Guardar como objeto date

            stats["pulido"]["total_ok"] += ok
            stats["pulido"]["total_pnc"] += pnc
            stats["pulido"]["operadores"][op][prod] += ok 


            
            f_dt = parsear_fecha_dashboard(f_str)
            if f_dt: stats["tendencia"][str(f_dt)]["pulido"] += ok


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
            
            if dentro_de_rango(f_pnc): 
                cant = to_int_seguro(r.get("CANTIDAD PNC") or r.get("CANTIDAD"))
                prod_pnc = str(r.get("CODIGO", "") or "GENERICO").strip()
                stats["pnc_total"]["pulido"] += cant
                cost_lote = sumar_perdida_pnc(prod_pnc, cant)
                if op_pnc:
                    stats["pulido"]["pnc_ops"][op_pnc] += cant
                    stats["pulido"]["costo_pnc_ops"][op_pnc] += cost_lote

        for r in reg_pnc_ens:
            f_pnc = r.get("FECHA") or r.get("fecha")
            if dentro_de_rango(f_pnc): 
                cant = to_int_seguro(r.get("CANTIDAD PNC") or r.get("CANTIDAD"))
                prod_pnc = str(r.get("CODIGO", "") or "GENERICO").strip()
                stats["pnc_total"]["ensamble"] += cant
                sumar_perdida_pnc(prod_pnc, cant)

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
                        "valor": sum(prods.values()), 
                        "mix": sorted([{"prod": p, "qty": q, "pts": q * puntos_map.get(p, 1.0), "u_pts": puntos_map.get(p, 1.0)} for p, q in prods.items()], key=lambda x: x["qty"], reverse=True),
                        "insight": f"Operador enfocado en: {sorted([{'prod': p, 'qty': q} for p, q in prods.items()], key=lambda x: x['qty'], reverse=True)[0]['prod'] if prods else 'Variado'}"
                    } for op, prods in stats["inyeccion"]["operadores"].items()
                ], key=lambda x: x["valor"], reverse=True), # Removemos el [:10] para mandar todos
                "pulido_profundo": {
                    op: {
                        "mix": sorted([{"prod": p, "qty": q, "pts": q * puntos_map.get(p, 1.0), "u_pts": puntos_map.get(p, 1.0)} for p, q in prods.items()], key=lambda x: x["qty"], reverse=True),
                        "buenas": sum(prods.values()),
                        "puntos": sum([q * puntos_map.get(p, 1.0) for p, q in prods.items()]),
                        "tiempo_estandar": sum([q * tiempo_map.get(p, 0.0) for p, q in prods.items()]),
                        "pnc": stats["pulido"]["pnc_ops"].get(op, 0),
                        "costo_pnc": stats["pulido"]["costo_pnc_ops"].get(op, 0),
                        "insight": f"Especialista destacado en este rango, produciendo principalmente: {sorted([{'prod': p, 'qty': q} for p, q in prods.items()], key=lambda x: x['qty'], reverse=True)[0]['prod'] if prods else 'Variado'}"
                    } for op, prods in stats["pulido"]["operadores"].items()
                }
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

            
        # 3. Scrap / PNC
        total_scrap = sum(stats["pnc_total"].values())
        if total_scrap > 0:
            p_scrap = round((total_scrap / (stats["inyeccion"]["total_ok"] + 1)) * 100, 2)
            insights.append(f"Calidad: El índice de merma global es del {p_scrap}%. {'Controlar Almacén' if stats['pnc_total']['almacen'] > 0 else 'Rangos estables.'}")
            
        # 4. Top Performance
        if stats["inyeccion"]["operadores"]:
            top_iny = max(stats["inyeccion"]["operadores"].items(), key=lambda x: sum(x[1].values()))[0]
            insights.append(f"Líder de Inyección: {top_iny} es el operador más productivo del periodo.")
            
        if stats["pulido"]["operadores"]:
            top_pul = max(stats["pulido"]["operadores"].items(), key=lambda x: sum([q * puntos_map.get(p, 1.0) for p, q in x[1].items()]))[0]
            insights.append(f"Líder de Pulido: {top_pul} mantiene el mayor puntaje de esfuerzo.")

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