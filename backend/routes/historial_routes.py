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
    Ensamble, Mezcla, BujeRevuelto,
    PncInyeccion, PncPulido, PncEnsamble
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

        # 6. PNC
        if not tipo_filtro or tipo_filtro == 'PNC':
            try:
                # PNC INYECCIÓN
                iny_query = db.session.query(PncInyeccion, ProduccionInyeccion).outerjoin(
                    ProduccionInyeccion, PncInyeccion.id_inyeccion == ProduccionInyeccion.id_inyeccion
                ).filter(ProduccionInyeccion.fecha_inicia.between(f_desde, f_hasta))
                
                for pnc, prod in iny_query.all():
                    movimientos.append({
                        'Fecha': getattr(prod.fecha_inicia, 'strftime', lambda x: '')('%d/%m/%Y') if prod and prod.fecha_inicia else 'S/F',
                        'Tipo': 'PNC',
                        'Producto': safe_str(getattr(pnc, 'id_codigo', '')),
                        'Responsable': 'INYECCION',
                        'Cant': float(str(getattr(pnc, 'cantidad', 0) or 0).replace(',', '.')),
                        'Orden': safe_str(getattr(pnc, 'id_inyeccion', '')),
                        'Extra': 'PNC Inyeccion',
                        'Detalle': f"Criterio: {safe_str(getattr(pnc, 'criterio', ''))} | Notas: {safe_str(getattr(pnc, 'codigo_ensamble', ''))}",
                        'HORA_INICIO': '',
                        'HORA_FIN': '',
                        'hoja': 'db_pnc_inyeccion',
                        'fila': getattr(pnc, 'id_row', 0)
                    })
                    
                # PNC PULIDO
                pul_query = db.session.query(PncPulido, ProduccionPulido).outerjoin(
                    ProduccionPulido, PncPulido.id_pulido == ProduccionPulido.id_pulido
                ).filter(ProduccionPulido.fecha.between(f_desde, f_hasta))
                
                for pnc, prod in pul_query.all():
                    movimientos.append({
                        'Fecha': getattr(prod.fecha, 'strftime', lambda x: '')('%d/%m/%Y') if prod and prod.fecha else 'S/F',
                        'Tipo': 'PNC',
                        'Producto': safe_str(getattr(pnc, 'codigo', '')),
                        'Responsable': 'PULIDO',
                        'Cant': float(str(getattr(pnc, 'cantidad', 0) or 0).replace(',', '.')),
                        'Orden': safe_str(getattr(pnc, 'id_pulido', '')),
                        'Extra': 'PNC Pulido',
                        'Detalle': f"Criterio: {safe_str(getattr(pnc, 'criterio', ''))} | Notas: {safe_str(getattr(pnc, 'codigo_ensamble', ''))}",
                        'HORA_INICIO': '',
                        'HORA_FIN': '',
                        'hoja': 'db_pnc_pulido',
                        'fila': getattr(pnc, 'id_row', 0)
                    })
                    
                # PNC ENSAMBLE
                ens_query = db.session.query(PncEnsamble, Ensamble).outerjoin(
                    Ensamble, PncEnsamble.id_ensamble == Ensamble.id_ensamble
                ).filter(Ensamble.fecha.between(f_desde, f_hasta))
                
                for pnc, prod in ens_query.all():
                    movimientos.append({
                        'Fecha': getattr(prod.fecha, 'strftime', lambda x: '')('%d/%m/%Y') if prod and prod.fecha else 'S/F',
                        'Tipo': 'PNC',
                        'Producto': safe_str(getattr(pnc, 'id_codigo', '')),
                        'Responsable': 'ENSAMBLE',
                        'Cant': float(str(getattr(pnc, 'cantidad', 0) or 0).replace(',', '.')),
                        'Orden': safe_str(getattr(pnc, 'id_ensamble', '')),
                        'Extra': 'PNC Ensamble',
                        'Detalle': f"Criterio: {safe_str(getattr(pnc, 'criterio', ''))} | Notas: {safe_str(getattr(pnc, 'codigo_ensamble', ''))}",
                        'HORA_INICIO': '',
                        'HORA_FIN': '',
                        'hoja': 'db_pnc_ensamble',
                        'fila': getattr(pnc, 'id_row', 0)
                    })

            except Exception as e:
                logger.error(f"Error PNC en historial: {e}")

        return jsonify(movimientos)

    except Exception as e:
        logger.error(f"Error crítico Historial v4.2: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@historial_bp.route('/api/historial/actualizar', methods=['POST'])
def actualizar_registro_historial():
    """
    Endpoint para editar registros corregidos por Auditoría / Gerencia desde el Historial Global.
    Mapea campos visuales a las columnas reales en las diferentes tablas (db_inyeccion, db_pulido, etc).
    """
    try:
        data = request.json
        hoja = data.get('hoja')
        fila = data.get('fila')
        datos = data.get('datos', {})
        usuario = data.get('usuario', 'SISTEMA')
        
        if not hoja or not fila:
            return jsonify({'success': False, 'error': 'Faltan datos de hoja o fila'}), 400
            
        # Determinar modelo
        model = None
        if hoja == 'db_inyeccion':
            model = ProduccionInyeccion
        elif hoja == 'db_pulido':
            model = ProduccionPulido
        elif hoja == 'db_ensambles':
            model = Ensamble
        elif hoja == 'db_mezcla':
            model = Mezcla
        elif hoja == 'db_ventas':
            model = RawVentas
        else:
            return jsonify({'success': False, 'error': f'Hoja no soportada: {hoja}'}), 400
            
        registro = model.query.get(fila)
        if not registro:
            return jsonify({'success': False, 'error': 'Registro no encontrado en la base de datos'}), 404
            
        # Mapeo estricto a las columnas actuales (Blindaje ante cambios recientes)
        MAPEO = {
            'RESPONSABLE': 'responsable',
            'DEPARTAMENTO': 'departamento',
            'MAQUINA': 'maquina',
            'ORDEN PRODUCCION': 'orden_produccion',
            'ID CODIGO': 'id_codigo',
            'CODIGO ENSAMBLE': 'codigo_ensamble',
            'FECHA INICIA': 'fecha_inicia',
            'HORA LLEGADA': 'hora_llegada',
            'HORA INICIO': 'hora_inicio',
            'HORA TERMINA': 'hora_termina',
            'HORA FIN': 'hora_fin',
            'No. CAVIDADES': 'cavidades',
            'CONTADOR MAQ.': 'cant_contador',
            'CANT. CONTADOR': 'cant_contador',
            'CANTIDAD REAL': 'cantidad_real',
            'ALMACEN DESTINO': 'almacen_destino',
            'PESO BUJES': 'peso_bujes',
            'OBSERVACIONES': 'observaciones',
            'CANTIDAD RECIBIDA': 'cantidad_recibida',
            'BUJES BUENOS': 'cantidad_real',
            'PNC': 'pnc_pulido',
            'CANTIDAD': 'cantidad',
            'OP NUMERO': 'op_numero',
            'ID ENSAMBLE': 'id_ensamble',
            'BUJE ENSAMBLE': 'buje_ensamble',
            'QTY (Unitaria)': 'qty',
            'ALMACEN ORIGEN': 'almacen_para_descargar',
            'VIRGEN (Kg)': 'virgen_kg',
            'MOLIDO (Kg)': 'molido_kg',
            'PIGMENTO (Kg)': 'pigmento_kg',
        }
        
        from backend.models.sql_models import OperacionLog
        try:
            nuevo_log = OperacionLog(
                modulo="HISTORIAL_GLOBAL",
                operario=usuario,
                accion=f"Edicion registro en {hoja} (ID {fila})",
                detalles=f"Cambios: {datos}"
            )
            db.session.add(nuevo_log)
        except Exception as log_e:
            logger.warning(f"No se pudo guardar OperacionLog: {log_e}")

        for key, value in datos.items():
            if key in MAPEO:
                col_name = MAPEO[key]
                if hasattr(registro, col_name):
                    # Transformaciones seguras de tipo
                    if value == '' or value is None:
                        # Dependiendo del campo podriamos setear None, pero lo dejamos como string vacio o 0
                        # Para evitar fallos si es numerico:
                        col_type = str(getattr(model, col_name).type)
                        if 'Integer' in col_type or 'Numeric' in col_type or 'Float' in col_type:
                            value = 0
                        else:
                            value = ''
                    else:
                        col_type = str(getattr(model, col_name).type)
                        if 'Integer' in col_type or 'Numeric' in col_type or 'Float' in col_type:
                            try:
                                value = float(str(value).replace(',', '.'))
                            except ValueError:
                                value = 0

                    setattr(registro, col_name, value)
                    
        db.session.commit()
        logger.info(f"✅ [Historial] Registro ID {fila} en {hoja} modificado correctamente por {usuario}")
        return jsonify({'success': True, 'mensaje': 'Registro actualizado correctamente'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error actualizando registro desde historial: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
