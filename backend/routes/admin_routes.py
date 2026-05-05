from flask import Blueprint, jsonify, render_template, Response, request
from backend.utils.auth_middleware import require_role, ROL_ADMINS

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
@require_role(ROL_ADMINS)
def get_admin_dashboard_data():
    from flask import request
    from backend.core.repository_service import repository_service
    
    start_date_str = request.args.get('start')
    end_date_str = request.args.get('end')
    
    # --- CACHE CHECK ---
    nocache = request.args.get('nocache') == '1'
    cache_key = (start_date_str or '', end_date_str or '')
    
    if nocache:
        ADMIN_DASHBOARD_CACHE.pop(cache_key, None)
    
    cached = ADMIN_DASHBOARD_CACHE.get(cache_key)
    if cached and (_time.time() - cached["timestamp"] < ADMIN_CACHE_TTL):
        return jsonify(cached["data"])
    
    # --- SQL NATIVE DATA FETCHING ---
    try:
        metrics = repository_service.get_admin_dashboard_metrics_sql(start_date_str, end_date_str)
        
        # Consolidación final por cliente para panel gerencial (calculado en backend sobre resultados SQL)
        from collections import defaultdict
        consolidado_map = defaultdict(lambda: {"unidades": 0, "dinero": 0})
        
        for item in metrics["incumplimiento_unidades"]:
            consolidado_map[item["cliente"]]["unidades"] += item["unidades_fallidas"]
        for item in metrics["incumplimiento_dinero"]:
            consolidado_map[item["cliente"]]["dinero"] += item["dinero_perdido"]
            
        inc_consolidado = []
        for cli, vals in consolidado_map.items():
            inc_consolidado.append({
                "cliente": cli,
                "unidades_fallidas": vals["unidades"],
                "dinero_perdido": vals["dinero"]
            })
        
        response_data = {
            "success": True,
            "status": "success",
            "data": {
                "mensual": metrics["mensual"],
                "top_productos_dinero": metrics["top_productos"],
                "peores_productos_dinero": metrics["peores_productos"],
                "backorder": metrics["backorder"],
                "incumplimiento_unidades": metrics["incumplimiento_unidades"],
                "incumplimiento_dinero": metrics["incumplimiento_dinero"],
                "resumen_unidades": metrics.get("resumen_unidades", 0),
                "resumen_dinero": metrics.get("resumen_dinero", 0),
                "incumplimiento_consolidado": sorted(inc_consolidado, key=lambda x: x["unidades_fallidas"], reverse=True)
            }
        }

        # Guardar en cache
        ADMIN_DASHBOARD_CACHE[cache_key] = {"timestamp": _time.time(), "data": response_data}
        return jsonify(response_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
        
@admin_bp.route('/api/admin/backorder/detalle', methods=['GET'])
@require_role(ROL_ADMINS)
def get_backorder_detalle():
    """Retorna el detalle de productos pendientes para un cliente específico."""
    try:
        cliente = request.args.get('cliente')
        start = request.args.get('desde')
        end = request.args.get('hasta')
        
        if not cliente:
            return jsonify({"success": False, "message": "El parámetro 'cliente' es obligatorio"}), 400
            
        from backend.core.repository_service import repository_service
        detalle = repository_service.get_backorder_detalle_por_cliente_sql(cliente, start, end)
        
        return jsonify({
            "success": True,
            "status": "success",
            "data": detalle
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@admin_bp.route('/api/admin/auditoria-fichas', methods=['GET'])
@require_role(ROL_ADMINS)
def auditoria_fichas_fuzzy():
    """
    Realiza una auditoría de nombres (Fuzzy Matching) entre la nueva ficha maestra
    y las tablas de producción en PostgreSQL.
    """
    try:
        from backend.models.sql_models import FichaMaestra, ProduccionInyeccion, ProduccionPulido
        from backend.core.sql_database import db
        
        # 1. Obtener datos de FichaMaestra
        fichas = FichaMaestra.query.all()
        nuevos_nombres = set()
        for f in fichas:
            if f.producto: nuevos_nombres.add(f.producto.strip())
            if f.subproducto: nuevos_nombres.add(f.subproducto.strip())

        # 2. Obtener nombres de producción
        nombres_iny = {r[0] for r in db.session.query(ProduccionInyeccion.id_codigo).distinct().all() if r[0]}
        nombres_pul = {r[0] for r in db.session.query(ProduccionPulido.codigo).distinct().all() if r[0]}

        existentes_map = {}
        for n in nombres_iny: existentes_map[n] = "INYECCION"
        for n in nombres_pul: existentes_map[n] = "PULIDO"
        existentes_lista = list(existentes_map.keys())

        # 3. Fuzzy Matching
        mapeo_propuesto = []
        for nombre_nuevo in sorted(list(nuevos_nombres)):
            coincidencias = difflib.get_close_matches(nombre_nuevo, existentes_lista, n=1, cutoff=0.3)
            mejor_match = coincidencias[0] if coincidencias else "SIN COINCIDENCIA"
            confianza = difflib.SequenceMatcher(None, nombre_nuevo, mejor_match).ratio() if coincidencias else 0.0
            origen = existentes_map.get(mejor_match, "N/A")

            mapeo_propuesto.append({
                "Nombre_Nuevo_Maestra": nombre_nuevo,
                "Mejor_Coincidencia_Actual": mejor_match,
                "Porcentaje_Confianza": f"{round(confianza * 100, 1)}%",
                "Hoja_Origen_Actual": origen
            })

        output = io.StringIO()
        fieldnames = ["Nombre_Nuevo_Maestra", "Mejor_Coincidencia_Actual", "Porcentaje_Confianza", "Hoja_Origen_Actual"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mapeo_propuesto)
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=auditoria_fichas_mapping_sql.csv"}
        )
    except Exception as e:
        logger.error(f"Error auditoria SQL: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
