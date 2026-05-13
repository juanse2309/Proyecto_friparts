from flask import Blueprint, request, jsonify
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
    Historial Global v4.2 ORM-Pure (Espejo de Mapeo).
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
        
        logger.info(f"🔍 [Historial] Consulta v4.2 ORM-Espejo ({f_desde} -> {f_hasta})")
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
                # Consulta ORM Simple
                res_pul = ProduccionPulido.query.filter(ProduccionPulido.fecha.between(f_desde, f_hasta)).all()
                
                for r in res_pul:
                    try:
                        # id_pulido es la clave para buscar revueltos (OID 25 / TEXT)
                        p_id = str(getattr(r, 'id_pulido', '') or '').strip()
                        
                        # 2.1 Consulta secundaria para revueltos
                        det_revueltos = ""
                        if p_id:
                            revs = BujeRevuelto.query.filter(BujeRevuelto.id_pulido == p_id).all()
                            if revs:
                                det_revueltos = " | REVUELTOS: " + ", ".join([f"{str(rv.id_codigo)}({rv.cantidad})" for rv in revs])

                        # 2.2 Construcción de Detalle (Sin rastro de Mezcla ni molido_kg)
                        obs = str(getattr(r, 'observaciones', '') or '').strip()
                        detalle_final = f"Obs: {obs}{det_revueltos}" if obs else det_revueltos.strip(" | ")

                        movimientos.append({
                            'Fecha': getattr(r.fecha, 'strftime', lambda x: '')('%d/%m/%Y') if r.fecha else '',
                            'Tipo': 'PULIDO',
                            'Producto': str(getattr(r, 'codigo', '') or ''),
                            'Responsable': str(getattr(r, 'responsable', 'SISTEMA') or ''),
                            'Cant': float(getattr(r, 'cantidad_real', 0) or 0),
                            'Orden': str(getattr(r, 'orden_prod', '') or p_id),
                            'Extra': f"OP: {str(getattr(r, 'orden_prod', '') or '')}",
                            'Detalle': detalle_final.strip(),
                            'HORA_INICIO': format_time_py(getattr(r, 'hora_inicio', None)),
                            'HORA_FIN': format_time_py(getattr(r, 'hora_fin', None)),
                            'hoja': 'db_pulido',
                            'fila': getattr(r, 'id', 0)
                        })
                    except Exception as e_row:
                        print(f'Error en fila Pulido: {e_row}')
                        logger.error(f"❌ Error procesando fila Pulido (ID {getattr(r, 'id', '?') }): {e_row}")
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
