from flask import Blueprint, request, jsonify
from sqlalchemy import text
from datetime import datetime
import logging
import psycopg2.extensions
# Registrar OID 25 (TEXT) como UNICODE para evitar errores de mapeo
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)

from backend.core.sql_database import db
from backend.models.sql_models import (
    ProduccionInyeccion, ProduccionPulido, RawVentas, 
    Ensamble, Mezcla, BujeRevuelto
)

historial_bp = Blueprint('historial_bp', __name__)
logger = logging.getLogger(__name__)

def safe_str(val):
    """Convierte cualquier valor a string de forma segura."""
    if val is None: return ''
    return str(val).strip()

def format_time_py(dt_obj):
    """Formatea objetos DateTime de Python a HH:MM."""
    if not dt_obj: return ''
    if hasattr(dt_obj, 'strftime'):
        return dt_obj.strftime('%H:%M')
    # Si ya es un string, intentar limpiar
    return safe_str(dt_obj)

@historial_bp.route('/api/historial-global', methods=['GET'])
def obtener_historial_global():
    """
    Historial Global v5.0 SQL-Limpio (Dict Mapping).
    Sincronizado con llaves en Mayúscula para el frontend.
    """
    try:
        desde_str = request.args.get('desde', '')
        hasta_str = request.args.get('hasta', '')
        tipo_filtro = request.args.get('tipo', '')
        
        # Rango de fechas
        hoy = datetime.now().date()
        f_desde = datetime.strptime(desde_str, '%Y-%m-%d').date() if desde_str else hoy
        f_hasta = datetime.strptime(hasta_str, '%Y-%m-%d').date() if hasta_str else hoy
        
        logger.info(f"🔍 [Historial] Consulta v5.0 SQL-Limpio ({f_desde} -> {f_hasta})")
        movimientos = []

        # 1. INYECCIÓN
        if not tipo_filtro or tipo_filtro == 'INYECCION':
            try:
                res = ProduccionInyeccion.query.filter(ProduccionInyeccion.fecha_inicia.between(f_desde, f_hasta)).all()
                for r in res:
                    movimientos.append({
                        'Fecha': getattr(r.fecha_inicia, 'strftime', lambda x: '')('%d/%m/%Y') if r.fecha_inicia else '',
                        'Tipo': 'INYECCION',
                        'Producto': safe_str(getattr(r, 'id_codigo', '')),
                        'Responsable': safe_str(getattr(r, 'responsable', 'SISTEMA')),
                        'Cant': float(str(getattr(r, 'cantidad_real', 0) or 0).replace(',', '.')),
                        'Orden': safe_str(getattr(r, 'orden_produccion', '')) or safe_str(getattr(r, 'id_inyeccion', '')),
                        'Extra': f"Molde: {getattr(r, 'molde', '')}",
                        'Detalle': safe_str(getattr(r, 'observaciones', '')),
                        'HORA_INICIO': format_time_py(getattr(r, 'hora_inicio', None)),
                        'HORA_FIN': format_time_py(getattr(r, 'hora_termina', None)),
                        'hoja': 'db_inyeccion',
                        'fila': getattr(r, 'id', 0)
                    })
            except Exception as e:
                logger.error(f"Error Inyeccion: {e}")

        # 2. PULIDO (Lógica Quirúrgica v4.4)
        if not tipo_filtro or tipo_filtro == 'PULIDO':
            try:
                # Consulta SQL con Casts explícitos
                sql_pul = """
                    SELECT 
                        id, id_pulido::TEXT, fecha, codigo::TEXT, responsable::TEXT, 
                        cantidad_real, orden_produccion::TEXT, observaciones::TEXT,
                        hora_inicio, hora_fin
                    FROM db_pulido
                    WHERE CAST(fecha AS DATE) BETWEEN :desde AND :hasta
                """
                res_raw = db.session.execute(text(sql_pul), {"desde": f_desde, "hasta": f_hasta})
                res_pul = [dict(row._mapping) for row in res_raw]

                # Batch Pre-fetch Revueltos (v5.2 - Zero queries in loop)
                all_pul_ids = [str(r.get('id_pulido') or '').strip() for r in res_pul]
                all_pul_ids = [pid for pid in all_pul_ids if pid]

                revueltos_map = {}
                if all_pul_ids:
                    placeholders = ', '.join([f':pid_{i}' for i in range(len(all_pul_ids))])
                    sql_revs = f"SELECT id_pulido::TEXT as id_pulido, id_codigo::TEXT as id_codigo, COALESCE(cantidad, 0) as cantidad FROM db_bujes_revueltos WHERE id_pulido IN ({placeholders})"
                    params_revs = {f'pid_{i}': pid for i, pid in enumerate(all_pul_ids)}
                    revs_raw = db.session.execute(text(sql_revs), params_revs)
                    for rv in revs_raw:
                        rv_dict = dict(rv._mapping)
                        pid = str(rv_dict['id_pulido'])
                        if pid not in revueltos_map:
                            revueltos_map[pid] = []
                        revueltos_map[pid].append(rv_dict)

                for r in res_pul:
                    try:
                        p_id = str(r.get('id_pulido') or '').strip()
                        
                        # Lookup directo en memoria (cero DB calls)
                        revs = revueltos_map.get(p_id, [])
                        det_revueltos = ""
                        if revs:
                            det_revueltos = " | REVUELTOS: " + ", ".join([f"{str(rv['id_codigo'])}({float(rv['cantidad'] or 0)})" for rv in revs])

                        obs = str(r.get('observaciones') or '').strip()
                        detalle_final = f"Obs: {obs}{det_revueltos}" if obs else det_revueltos.strip(" | ")

                        movimientos.append({
                            'Fecha': r['fecha'].strftime('%d/%m/%Y') if r['fecha'] else '',
                            'Tipo': 'PULIDO',
                            'Producto': str(r['codigo'] or ''),
                            'Responsable': str(r['responsable'] or 'SISTEMA'),
                            'cantidad_real': float(r['cantidad_real'] or 0),
                            'Cant': float(r['cantidad_real'] or 0),
                            'Orden': str(r['orden_produccion'] or p_id or '-'),
                            'Extra': f"OP: {str(r['orden_produccion'] or '')}",
                            'Detalle': str(detalle_final.strip()),
                            'HORA_INICIO': format_time_py(r['hora_inicio']),
                            'HORA_FIN': format_time_py(r['hora_fin']),
                            'hoja': 'db_pulido',
                            'fila': int(r['id'])
                        })
                    except Exception as e_row:
                        db.session.rollback()
                        print(f'Error en fila Pulido: {e_row}')
                        logger.error(f"❌ Error procesando fila Pulido (ID {r.get('id', '?')}): {e_row}")
                        continue
            except Exception as e_block:
                print(f'Error en Pulido: {e_block}')
                logger.error(f"❌ ERROR CRÍTICO EN BLOQUE PULIDO: {e_block}")
                import traceback
                logger.error(traceback.format_exc())

        # 3. ENSAMBLE
        if not tipo_filtro or tipo_filtro == 'ENSAMBLE':
            try:
                res = Ensamble.query.filter(Ensamble.fecha.between(f_desde, f_hasta)).all()
                for r in res:
                    movimientos.append({
                        'Fecha': getattr(r.fecha, 'strftime', lambda x: '')('%d/%m/%Y') if r.fecha else '',
                        'Tipo': 'ENSAMBLE',
                        'Producto': safe_str(getattr(r, 'id_codigo', '')),
                        'Responsable': safe_str(getattr(r, 'responsable', 'SISTEMA')),
                        'Cant': float(str(getattr(r, 'cantidad', 0) or 0).replace(',', '.')),
                        'Orden': safe_str(getattr(r, 'op_numero', '')) or safe_str(getattr(r, 'id_ensamble', '')),
                        'Extra': safe_str(getattr(r, 'buje_ensamble', '')),
                        'Detalle': safe_str(getattr(r, 'observaciones', '')),
                        'HORA_INICIO': format_time_py(getattr(r, 'hora_inicio', None)),
                        'HORA_FIN': format_time_py(getattr(r, 'hora_fin', None)),
                        'hoja': 'db_ensambles',
                        'fila': getattr(r, 'id', 0)
                    })
            except Exception as e:
                logger.error(f"Error Ensamble: {e}")

        # 4. MEZCLA
        if not tipo_filtro or tipo_filtro == 'MEZCLA':
            try:
                res = Mezcla.query.filter(Mezcla.fecha.between(f_desde, f_hasta)).all()
                for r in res:
                    movimientos.append({
                        'Fecha': getattr(r.fecha, 'strftime', lambda x: '')('%d/%m/%Y') if r.fecha else '',
                        'Tipo': 'MEZCLA',
                        'Producto': 'PREPARACION MATERIAL',
                        'Responsable': safe_str(getattr(r, 'responsable', 'SISTEMA')),
                        'Cant': f"{float(getattr(r, 'virgen_kg', 0) or 0)}Kg V",
                        'Extra': f"{float(getattr(r, 'molido_kg', 0) or 0)}Kg M",
                        'Detalle': safe_str(getattr(r, 'observaciones', '')),
                        'HORA_INICIO': '',
                        'HORA_FIN': '',
                        'hoja': 'db_mezcla',
                        'fila': getattr(r, 'id', 0)
                    })
            except Exception as e:
                logger.error(f"Error Mezcla: {e}")

        # 5. VENTAS
        if not tipo_filtro or tipo_filtro in ['VENTA', 'VENTAS', 'FACTURACION']:
            try:
                res = RawVentas.query.filter(RawVentas.fecha.between(f_desde, f_hasta)).all()
                for r in res:
                    movimientos.append({
                        'Fecha': getattr(r.fecha, 'strftime', lambda x: '')('%d/%m/%Y') if r.fecha else '',
                        'Tipo': 'VENTA',
                        'Producto': safe_str(getattr(r, 'productos', '')),
                        'Responsable': safe_str(getattr(r, 'nombres', 'CLIENTE DESCONOCIDO')),
                        'Cant': float(str(getattr(r, 'cantidad', 0) or 0).replace(',', '.')),
                        'Orden': safe_str(getattr(r, 'documento', '')),
                        'Extra': safe_str(getattr(r, 'clasificacion', '')),
                        'Detalle': f"Ingreso: ${float(getattr(r, 'total_ingresos', 0) or 0)}",
                        'HORA_INICIO': '',
                        'HORA_FIN': '',
                        'hoja': 'db_ventas',
                        'fila': getattr(r, 'id', 0)
                    })
            except Exception as e:
                logger.error(f"Error Ventas: {e}")

        return jsonify(movimientos)

    except Exception as e:
        logger.error(f"Error crítico Historial v4.2: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
