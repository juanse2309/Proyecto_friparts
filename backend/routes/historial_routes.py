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
from backend.utils.auth_middleware import require_role, ROL_ADMINS

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

        # 1. INYECCIÓN — SQL nativo con CAST para evitar comparación Date vs DateTime (timestamp)
        if not tipo_filtro or tipo_filtro == 'INYECCION':
            try:
                sql_iny = """
                    SELECT
                        id, id_inyeccion::TEXT, fecha_inicia, fecha_fin,
                        id_codigo::TEXT, responsable::TEXT, maquina::TEXT,
                        cantidad_real, estado::TEXT, molde, cavidades,
                        hora_llegada::TEXT, hora_inicio::TEXT, hora_termina::TEXT,
                        cant_contador, almacen_destino::TEXT, codigo_ensamble::TEXT,
                        orden_produccion::TEXT, observaciones::TEXT,
                        pnc_total, departamento::TEXT
                    FROM db_inyeccion
                    WHERE CAST(fecha_inicia AS DATE) BETWEEN :desde AND :hasta
                    ORDER BY fecha_inicia DESC
                """
                logger.info(
                    f"🔍 [Historial-INYECCION] SQL enviado a PostgreSQL: "
                    f"SELECT ... FROM db_inyeccion WHERE CAST(fecha_inicia AS DATE) "
                    f"BETWEEN '{f_desde}' AND '{f_hasta}'"
                )
                res_raw = db.session.execute(text(sql_iny), {"desde": f_desde, "hasta": f_hasta})
                res_iny = [dict(row._mapping) for row in res_raw]
                logger.info(f"✅ [Historial-INYECCION] Registros encontrados: {len(res_iny)} (rango {f_desde} → {f_hasta})")

                for r in res_iny:
                    try:
                        fi = r.get('fecha_inicia')
                        movimientos.append({
                            'Fecha': fi.strftime('%d/%m/%Y') if fi else '',
                            'Tipo': 'INYECCION',
                            'Producto': safe_str(r.get('id_codigo', '')),
                            'Responsable': safe_str(r.get('responsable', 'SISTEMA')),
                            'Cant': float(str(r.get('cantidad_real') or 0).replace(',', '.')),
                            'Orden': safe_str(r.get('orden_produccion', '')) or safe_str(r.get('id_inyeccion', '')),
                            'Extra': f"Molde: {r.get('molde', '')}",
                            'Detalle': safe_str(r.get('observaciones', '')),
                            'HORA_INICIO': safe_str(r.get('hora_inicio', '')),
                            'HORA_FIN': safe_str(r.get('hora_termina', '')),
                            'hoja': 'db_inyeccion',
                            'fila': int(r.get('id', 0))
                        })
                    except Exception as e_row:
                        logger.error(f"❌ [Historial-INYECCION] Error procesando fila (ID {r.get('id', '?')}): {e_row}")
                        continue
            except Exception as e:
                logger.error(f"❌ [Historial-INYECCION] Error crítico en bloque: {e}")
                import traceback
                logger.error(traceback.format_exc())

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
                from sqlalchemy import func, cast, Date as SADate

                # PNC INYECCIÓN — cast DateTime → Date para comparación correcta de rango
                iny_query = db.session.query(PncInyeccion, ProduccionInyeccion).outerjoin(
                    ProduccionInyeccion, PncInyeccion.id_inyeccion == ProduccionInyeccion.id_inyeccion
                ).filter(
                    cast(ProduccionInyeccion.fecha_inicia, SADate) >= f_desde,
                    cast(ProduccionInyeccion.fecha_inicia, SADate) <= f_hasta
                )
                logger.info(
                    f"🔍 [Historial-PNC-INY] CAST(fecha_inicia AS DATE) >= '{f_desde}' AND <= '{f_hasta}'"
                )
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

                # PNC PULIDO — ProduccionPulido.fecha también es DateTime
                pul_query = db.session.query(PncPulido, ProduccionPulido).outerjoin(
                    ProduccionPulido, PncPulido.id_pulido == ProduccionPulido.id_pulido
                ).filter(
                    cast(ProduccionPulido.fecha, SADate) >= f_desde,
                    cast(ProduccionPulido.fecha, SADate) <= f_hasta
                )
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

                # PNC ENSAMBLE — Ensamble.fecha es DateTime
                ens_query = db.session.query(PncEnsamble, Ensamble).outerjoin(
                    Ensamble, PncEnsamble.id_ensamble == Ensamble.id_ensamble
                ).filter(
                    cast(Ensamble.fecha, SADate) >= f_desde,
                    cast(Ensamble.fecha, SADate) <= f_hasta
                )
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


@historial_bp.route('/api/historial/detalle', methods=['GET'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO'])
def obtener_detalle_historial():
    """
    Devuelve todos los campos detallados de un registro específico
    para poder editarlos con sus valores reales en el modal.
    """
    try:
        import decimal
        hoja = request.args.get('hoja')
        fila = request.args.get('fila')
        
        if not hoja or not fila:
            return jsonify({'success': False, 'error': 'Faltan parámetros hoja o fila'}), 400
            
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
            return jsonify({'success': False, 'error': 'Registro no encontrado'}), 404
            
        # Convertir a dict serializable
        datos = {}
        for col in registro.__table__.columns:
            val = getattr(registro, col.name)
            # Formatear fechas y datetimes
            if isinstance(val, datetime):
                datos[col.name] = val.isoformat()
            elif hasattr(val, 'strftime') and val.__class__.__name__ == 'date':
                datos[col.name] = val.isoformat()
            elif isinstance(val, decimal.Decimal):
                datos[col.name] = float(val)
            else:
                datos[col.name] = val
                
        return jsonify({'success': True, 'data': datos})
        
    except Exception as e:
        logger.error(f"Error obteniendo detalle de registro: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@historial_bp.route('/api/historial/actualizar', methods=['POST'])
@require_role(ROL_ADMINS + ['AUXILIAR INVENTARIO'])
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
            'CODIGO': 'codigo',
            'CODIGO ENSAMBLE': 'codigo_ensamble',
            'FECHA INICIA': 'fecha_inicia',
            'FECHA': 'fecha',
            'FECHA FIN': 'fecha_fin',
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
            'PNC_INYECCION': 'pnc_inyeccion',
            'CANTIDAD': 'cantidad',
            'OP NUMERO': 'op_numero',
            'ID ENSAMBLE': 'id_ensamble',
            'BUJE ENSAMBLE': 'buje_ensamble',
            'QTY (Unitaria)': 'qty',
            'CONSUMO_TOTAL': 'consumo_total',
            'ALMACEN ORIGEN': 'almacen_para_descargar',
            'VIRGEN (Kg)': 'virgen_kg',
            'MOLIDO (Kg)': 'molido_kg',
            'PIGMENTO (Kg)': 'pigmento_kg',
            'LOTE_INTERNO': 'lote_interno',
            'LOTE': 'lote',
            'ESTADO': 'estado',
            'HORA': 'hora',
            'CLIENTE': 'nombres',
            'DOCUMENTO': 'documento',
            'PRODUCTO': 'productos',
            'CLASIFICACION': 'clasificacion',
            'TOTAL_INGRESOS': 'total_ingresos',
            'PRECIO_PROMEDIO': 'precio_promedio'
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

        # Intentar determinar una fecha base para combinar con horas si es necesario
        fecha_base = None
        fecha_str = datos.get('FECHA') or datos.get('FECHA INICIA')
        if fecha_str:
            try:
                fecha_base = datetime.strptime(fecha_str.split('T')[0].split(' ')[0], '%Y-%m-%d').date()
            except ValueError:
                try:
                    fecha_base = datetime.strptime(fecha_str.split(' ')[0], '%d/%m/%Y').date()
                except ValueError:
                    pass

        if not fecha_base:
            for col_f in ['fecha', 'fecha_inicia']:
                if hasattr(registro, col_f) and getattr(registro, col_f):
                    val_f = getattr(registro, col_f)
                    if isinstance(val_f, datetime):
                        fecha_base = val_f.date()
                        break
                    elif hasattr(val_f, 'strftime') and val_f.__class__.__name__ == 'date':
                        fecha_base = val_f
                        break
        
        if not fecha_base:
            fecha_base = datetime.now().date()

        for key, value in datos.items():
            if key in MAPEO:
                col_name = MAPEO[key]
                
                # Resiliencia de mapeo para ID CODIGO / CODIGO
                if col_name == 'id_codigo' and not hasattr(registro, 'id_codigo') and hasattr(registro, 'codigo'):
                    col_name = 'codigo'
                elif col_name == 'codigo' and not hasattr(registro, 'codigo') and hasattr(registro, 'id_codigo'):
                    col_name = 'id_codigo'

                if hasattr(registro, col_name):
                    col_attr = getattr(model, col_name)
                    col_type = str(col_attr.type)
                    
                    if value == '' or value is None:
                        if 'Integer' in col_type or 'Numeric' in col_type or 'Float' in col_type or 'BigInteger' in col_type:
                            setattr(registro, col_name, 0)
                        else:
                            setattr(registro, col_name, None)
                        continue

                    # Conversión según el tipo de columna en SQLAlchemy
                    if 'DateTime' in col_type:
                        try:
                            # Caso 1: Es una hora en formato HH:MM o HH:MM:SS
                            if ':' in str(value) and len(str(value)) <= 8:
                                parts = str(value).split(':')
                                h = int(parts[0])
                                m = int(parts[1])
                                s = int(parts[2]) if len(parts) > 2 else 0
                                dt_value = datetime.combine(fecha_base, datetime.min.time().replace(hour=h, minute=m, second=s))
                                setattr(registro, col_name, dt_value)
                            # Caso 2: Es una fecha YYYY-MM-DD
                            else:
                                clean_val = str(value).split('T')[0].split(' ')[0]
                                try:
                                    dt_parsed = datetime.strptime(clean_val, '%Y-%m-%d')
                                except ValueError:
                                    dt_parsed = datetime.strptime(clean_val, '%d/%m/%Y')
                                
                                # Si ya tenía hora, intentar conservarla
                                old_val = getattr(registro, col_name)
                                if old_val and isinstance(old_val, datetime):
                                    dt_value = datetime.combine(dt_parsed.date(), old_val.time())
                                else:
                                    dt_value = dt_parsed
                                setattr(registro, col_name, dt_value)
                        except Exception as e_dt:
                            logger.warning(f"No se pudo parsear DateTime {value} para {col_name}: {e_dt}")

                    elif 'Date' in col_type:
                        try:
                            clean_val = str(value).split('T')[0].split(' ')[0]
                            try:
                                dt_parsed = datetime.strptime(clean_val, '%Y-%m-%d').date()
                            except ValueError:
                                dt_parsed = datetime.strptime(clean_val, '%d/%m/%Y').date()
                            setattr(registro, col_name, dt_parsed)
                        except Exception as e_d:
                            logger.warning(f"No se pudo parsear Date {value} para {col_name}: {e_d}")

                    elif 'Integer' in col_type or 'BigInteger' in col_type:
                        try:
                            setattr(registro, col_name, int(float(str(value).replace(',', '.'))))
                        except ValueError:
                            setattr(registro, col_name, 0)

                    elif 'Numeric' in col_type or 'Float' in col_type:
                        try:
                            setattr(registro, col_name, float(str(value).replace(',', '.')))
                        except ValueError:
                            setattr(registro, col_name, 0.0)

                    else:
                        setattr(registro, col_name, str(value).strip())
                    
        db.session.commit()
        logger.info(f"✅ [Historial] Registro ID {fila} en {hoja} modificado correctamente por {usuario}")
        return jsonify({'success': True, 'mensaje': 'Registro actualizado correctamente'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error actualizando registro desde historial: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
