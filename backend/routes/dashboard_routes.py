"""
Rutas de dashboard.
"""
from flask import Blueprint, jsonify, request
from backend.core.repository_service import repository_service
# from backend.utils.formatters import to_int as to_int_seguro, clean_currency, parsear_fecha_dashboard
import logging
import collections
import time
import datetime
import pandas as pd
import io
from flask import send_file

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)

# Cache simple para el dashboard
DASHBOARD_COMPLEX_CACHE = {}


@dashboard_bp.route('/', methods=['GET'])
def obtener_dashboard():
    """Obtiene estadísticas del dashboard."""
    try:
        # REFACTOR: 100% SQL-First
        kpis = repository_service.get_dashboard_kpis()
        
        return jsonify({
            'status': 'success',
            'produccion': {'total': kpis.get('inyeccion_ok', 0) + kpis.get('pulido_ok', 0)},
            'ventas': {'total': kpis.get('ventas_totales', 0)},
            'stock_critico': [],
            'pnc': {'total': kpis.get('scrap_total', 0)}
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

        # --- RECOPILACIÓN DE DATOS REFACTORIZADA (100% SQL-FIRST) ---
        # 1. KPIs Generales, Rankings y Máquinas (Todo vía SQL puro)
        kpis = repository_service.get_dashboard_kpis(desde, hasta)
        ranking_iny_ops = repository_service.get_ranking_operarios_inyeccion(desde, hasta)
        ranking_pul_ops = repository_service.get_ranking_operarios_pulido(desde, hasta)
        ranking_maquinas = repository_service.get_ranking_maquinas(desde, hasta)
        analytics_pulido = repository_service.get_analytics_pulido(desde, hasta)
        
        # 2. Nuevas métricas SQL-Native (Stock Crítico y Pérdida Financiera)
        stock_critico = repository_service.get_stock_critico_sql()
        perdida_scrap = repository_service.get_perdida_economica_scrap(desde, hasta)

        # 3. Estructura de salida compatible con Dashboard.js (Safe Access)
        stats = {
            "inyeccion": {
                "total_ok": kpis.get('inyeccion_ok', 0), 
                "total_pnc": kpis.get('inyeccion_pnc', 0),
                "operadores": collections.defaultdict(lambda: collections.defaultdict(lambda: {"qty": 0, "fecha": ""})),
                "maquinas": [{'maquina': m.get('maquina', '?'), 'valor': m.get('valor', 0)} for m in ranking_maquinas],
                "fechas": collections.defaultdict(int)
            },
            "pulido": {
                "total_ok": kpis.get('pulido_ok', 0), 
                "total_pnc": kpis.get('pulido_pnc', 0), 
                "operadores": collections.defaultdict(lambda: collections.defaultdict(lambda: {"qty": 0, "fecha": ""})),
                "pnc_ops": {op.get('nombre', '?'): op.get('pnc', 0) for op in ranking_pul_ops},
                "tiempo_real_ops": collections.defaultdict(float),
                "tiempo_std_ops": collections.defaultdict(float),
                "mensual": collections.defaultdict(lambda: {"piezas": 0, "std": 0, "real": 0}),
                "mensual_operadoras": collections.defaultdict(lambda: collections.defaultdict(float))
            },
            "pedidos": {"total_solicitado": kpis.get('pedidos_solicitados', 0)},
            "ensamble": {
                "total_ok": kpis.get('ensambles_ok', 0),
                "total_pnc": kpis.get('ensamble_pnc', 0),
                "tiempo_real_segundos": 0,
                "operadores": collections.defaultdict(int)
            },
            "pnc_total": {
                "inyeccion": kpis.get('inyeccion_pnc', 0), 
                "pulido": kpis.get('pulido_pnc', 0), 
                "ensamble": kpis.get('ensamble_pnc', 0), 
                "almacen": 0
            },
            "pnc_almacen_detalle": collections.defaultdict(lambda: {"cantidad": 0, "costo": 0}),
            "perdida_calidad_dinero": perdida_scrap,
            "tendencia": collections.defaultdict(lambda: {"inyeccion": 0, "pulido": 0, "ensamble": 0})
        }

        # IA INSIGHTS (Safe calculation)
        total_sol = stats["pedidos"]["total_solicitado"] or 1
        fulfillment_rate = round((stats["inyeccion"]["total_ok"] / total_sol) * 100, 1)
        
        insights = [
            f"Tasa de cumplimiento: {fulfillment_rate}%.",
            f"Ventas totales registradas: ${kpis.get('ventas_totales', 0):,.0f}.",
            f"Alerta: {len(stock_critico)} productos con stock por debajo del mínimo."
        ]
        
        # 3. Tendencia de Producción
        tendencia = repository_service.get_tendencia_produccion_sql(desde, hasta)

        # 4. Estructura de salida compatible con Dashboard.js (Safe Access)
        result_data = {
            "rango": {"desde": str(desde) if desde else "Inicio", "hasta": str(hasta) if hasta else "Fin"},
            "kpis": {
                "inyeccion_ok": kpis.get('inyeccion_ok', 0),
                "pulido_ok": kpis.get('pulido_ok', 0),
                "ensamble_ok": kpis.get('ensambles_ok', 0),
                "pedidos_solicitado": kpis.get('pedidos_solicitados', 0),
                "cumplimiento_pct": fulfillment_rate,
                "perdida_calidad_dinero": kpis.get('perdida_calidad_dinero', 0),
                "scrap_total": kpis.get('scrap_total', 0),
                "scrap_detalle": kpis.get('scrap_detalle', {}),
                "scrap_almacen_desglose": kpis.get('scrap_almacen_desglose', []),
                "stock_critico": stock_critico
            },
            "rankings": {
                "inyeccion_ops": [
                    {"nombre": op['nombre'], "valor": op['valor'], "insight": "Top Inyección"} 
                    for op in ranking_iny_ops
                ],
                "pulido_profundo": {
                    op['nombre']: {
                        "buenas": op['valor'], 
                        "pnc": op['pnc'],
                        "puntos": op.get('puntos', 0),
                        "eficiencia": op.get('eficiencia', 0),
                        "yield_calidad": round((op['valor'] / (op['valor'] + op['pnc']) * 100), 1) if (op['valor'] + op['pnc']) > 0 else 100,
                    } for op in ranking_pul_ops
                }
            },
            "maquinas": [{'maquina': m.get('maquina', '?'), 'valor': m.get('valor', 0)} for m in ranking_maquinas],
            "tendencia": tendencia,
            "analytics_pulido": analytics_pulido,
            "insights_ia": insights,
            "insight_ia": insights[0]
        }
        
        DASHBOARD_COMPLEX_CACHE[cache_key] = {"data": result_data, "timestamp": ahora}
        return jsonify({"status": "success", "success": True, "data": result_data}), 200

    except Exception as e:
        import traceback
        logger.error(f"Error en dashboard BI: {e}\n{traceback.format_exc()}")
        # Devolver ceros en lugar de 500 para que el frontend no colapse
        fallback = {
            "kpis": {
                "inyeccion_ok": 0, "pulido_ok": 0, "scrap_total": 0,
                "perdida_calidad_dinero": 0, "faltan_costos_pnc": [],
                "scrap_detalle": {"inyeccion": 0, "pulido": 0, "ensamble": 0, "almacen": 0},
                "scrap_almacen_desglose": []
            },
            "rankings": {"inyeccion_ops": [], "pulido_profundo": {}},
            "maquinas": [], "tendencia": [],
            "analytics_pulido": {"evolucion_puntos_op": {}, "operario_referencia": {}},
            "insights_ia": [f"⚠️ Error temporal cargando datos: {str(e)[:80]}"],
            "insight_ia": f"⚠️ Error temporal: {str(e)[:80]}",
            "rango": {"desde": "", "hasta": ""}
        }
        return jsonify({"status": "success", "success": True, "data": fallback}), 200

# Mantener rutas viejas por compatibilidad si es necesario o redireccionarlas
@dashboard_bp.route('/inyeccion', methods=['GET'])
def metricas_inyeccion_legacy():
    return obtener_metricas_bi()

@dashboard_bp.route('/pulido', methods=['GET'])
def metricas_pulido_legacy():
    return obtener_metricas_bi()

@dashboard_bp.route('/ventas/desglose-mensual', methods=['GET'])
def get_desglose_mensual():
    """Endpoint para el Drill-down del gráfico mensual."""
    try:
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        tipo_vista = request.args.get('tipo_vista', 'money')
        if not mes or not anio:
            return jsonify({"success": False, "error": "Faltan parámetros mes y anio"}), 400
        
        data = repository_service.get_desglose_mensual_ventas_sql(mes, anio, tipo_vista)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Error en get_desglose_mensual: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@dashboard_bp.route('/ventas/exportar-desglose', methods=['GET'])
def exportar_desglose_mensual():
    """Genera Excel del desglose mensual con formato profesional."""
    try:
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        tipo_vista = request.args.get('tipo_vista', 'money')
        if not mes or not anio:
            return jsonify({"success": False, "error": "Faltan parámetros mes y anio"}), 400
        
        data = repository_service.get_desglose_mensual_ventas_sql(mes, anio, tipo_vista)
        if not data:
            return jsonify({"success": False, "error": "No hay datos para este periodo"}), 404
        
        # Inicializar DataFrame
        df = pd.DataFrame(data)
        
        # Asegurar que las columnas existen y están en orden
        columnas_esperadas = ['id_codigo', 'descripcion', 'unidades', 'total_ventas']
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = 0 if ('total' in col or 'unidades' in col) else ''
        
        df = df[columnas_esperadas]
        df.columns = ['Referencia', 'Descripción', 'Cantidad', 'Total (COP)']
        
        # Tipado numérico para Excel
        df['Cantidad'] = pd.to_numeric(df['Cantidad'], errors='coerce').fillna(0)
        df['Total (COP)'] = pd.to_numeric(df['Total (COP)'], errors='coerce').fillna(0)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Reporte Ventas')
            
            # Autofit dinámico
            worksheet = writer.sheets['Reporte Ventas']
            for idx, col in enumerate(df.columns):
                val_max_len = df[col].astype(str).map(len).max() if not df.empty else 0
                max_len = max(val_max_len, len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 60)

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Reporte_Ventas_{mes}_{anio}.xlsx'
        )
    except Exception as e:
        logger.error(f"❌ Error Crítico en Exportación Excel: {e}")
        return jsonify({"success": False, "error": f"Fallo en la generación del reporte: {str(e)}"}), 500
        return str(e), 500