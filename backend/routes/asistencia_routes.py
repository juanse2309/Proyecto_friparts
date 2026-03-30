from flask import Blueprint, jsonify, request, session
from backend.utils.auth_middleware import require_role
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import logging

logger = logging.getLogger(__name__)
asistencia_bp = Blueprint('asistencia', __name__)

def normalizar_hora(hora_str):
    """Convierte strings de hora sucios o localizados (ej: ' 5:00:00 p. m.') a formato HH:mm."""
    if not hora_str or not isinstance(hora_str, str):
        return ""
    
    import re
    # Limpiar espacios extraños, puntos y normalizar am/pm
    h = hora_str.strip().lower()
    h = h.replace('.', '') # quitar puntos de p.m. -> pm
    h = re.sub(r'\s+', ' ', h) # normalizar múltiples espacios a uno solo
    
    # Intentar parsear con formatos comunes
    from datetime import datetime
    formatos = [
        '%I:%M:%S %p', # 05:00:00 pm
        '%I:%M %p',    # 05:00 pm
        '%H:%M:%S',    # 17:00:00
        '%H:%M',       # 17:00
        '%I:%M:%S%p',  # 05:00:00pm
        '%I:%M%p'      # 05:00pm
    ]
    
    # Manejo especial para el formato con espacio antes de am/pm que a veces falla en windows/linux
    h = h.replace('a m', 'am').replace('p m', 'pm')
    
    for fmt in formatos:
        try:
            return datetime.strptime(h, fmt).strftime('%H:%M')
        except:
            continue
            
    # Si nada funciona, intentar extraer solo HH:mm con regex
    match = re.search(r'(\d{1,2}:\d{2})', h)
    if match:
        time_part = match.group(1)
        # Si contiene 'p' y no es 12, sumar 12
        if 'p' in h:
            h_int, m_int = map(int, time_part.split(':'))
            if h_int < 12: h_int += 12
            return f"{h_int:02d}:{m_int:02d}"
        return time_part
        
    return ""

@asistencia_bp.route('/colaboradores', methods=['GET'])
def obtener_colaboradores():
    """Obtiene lista de colaboradores con sus horarios oficiales."""
    try:
        ws = sheets_client.get_worksheet(Hojas.RESPONSABLES)
        if not ws:
            return jsonify({'status': 'error', 'message': 'No se encontró la hoja de responsables'}), 404
        
        registros = sheets_client.get_all_records_seguro(ws)
        colaboradores = []
        for r in registros:
            if r.get('RESPONSABLE') and r.get('ACTIVO?') == 'SI':
                colaboradores.append({
                    'nombre': r.get('RESPONSABLE'),
                    'departamento': r.get('DEPARTAMENTO'),
                    'hora_entrada': normalizar_hora(r.get('HORA ENTRADA TURNO')),
                    'hora_salida': normalizar_hora(r.get('HORA SALIDA TURNO'))
                })
        
        return jsonify({
            'status': 'success',
            'colaboradores': colaboradores
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo colaboradores: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/guardar', methods=['POST'])
@require_role(['administracion', 'jefe inyeccion', 'inyeccion', 'jefe pulido', 'pulido', 'jefe almacen', 'alistamiento', 'ensamble', 'auxiliar inventario'])
def guardar_asistencia():
    """Guarda los registros de asistencia en la hoja CONTROL_ASISTENCIA."""
    try:
        data = request.json
        if not data or 'registros' not in data:
            return jsonify({'status': 'error', 'message': 'Datos inválidos'}), 400
        
        ws = sheets_client.get_worksheet(Hojas.CONTROL_ASISTENCIA)
        if not ws:
            return jsonify({'status': 'error', 'message': 'No se encontró la hoja de control de asistencia'}), 404

        rows_to_append = []
        for reg in data['registros']:
            rows_to_append.append([
                reg.get('fecha'),
                reg.get('colaborador'),
                reg.get('ingreso_real'),
                reg.get('salida_real'),
                reg.get('horas_ordinarias'),
                reg.get('horas_extras'),
                reg.get('registrado_por', 'Sistema'), # Nueva columna de auditoría
                reg.get('estado', 'PRESENTE'),        # ESTADO
                reg.get('motivo', ''),                # MOTIVO
                reg.get('comentarios', '')            # COMENTARIOS
            ])

        if rows_to_append:
            ws.append_rows(rows_to_append)
        
        return jsonify({
            'status': 'success',
            'message': f'Se guardaron {len(rows_to_append)} registros correctamente'
        }), 200

    except Exception as e:
        logger.error(f"Error guardando asistencia: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/guardar_ausencia', methods=['POST'])
@require_role(['administracion', 'jefe inyeccion', 'inyeccion', 'jefe pulido', 'pulido', 'jefe almacen', 'alistamiento', 'ensamble', 'auxiliar inventario'])
def guardar_ausencia():
    """Guarda un registro de ausencia en la hoja CONTROL_ASISTENCIA."""
    try:
        data = request.json
        if not data or 'registro' not in data:
            return jsonify({'status': 'error', 'message': 'Datos inválidos'}), 400
        
        reg = data['registro']
        ws = sheets_client.get_worksheet(Hojas.CONTROL_ASISTENCIA)
        if not ws:
            return jsonify({'status': 'error', 'message': 'No se encontró la hoja de control de asistencia'}), 404

        row_to_append = [
            reg.get('fecha'),
            reg.get('colaborador'),
            reg.get('ingreso_real', 'AUSENTE'),
            reg.get('salida_real', ''),
            reg.get('horas_ordinarias', 0),
            reg.get('horas_extras', 0),
            reg.get('registrado_por', 'Sistema'),
            reg.get('estado', 'AUSENTE'),
            reg.get('motivo', ''),
            reg.get('comentarios', '')
        ]

        ws.append_row(row_to_append)
        
        return jsonify({
            'status': 'success',
            'message': 'Ausencia registrada correctamente'
        }), 200

    except Exception as e:
        logger.error(f"Error guardando ausencia: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/mis_horas', methods=['GET'])
def obtener_mis_horas():
    """Obtiene el historial de asistencia de la semana actual para el colaborador logueado."""
    colaborador = session.get('user')
    if not colaborador:
        return jsonify({'status': 'error', 'message': 'Acceso denegado. Usuario no autenticado en sesión.'}), 401
        
    try:
        from datetime import datetime
        
        # Nuevo Filtro: Solo lo posterior al último corte de nómina
        ultima_fecha_corte = get_ultima_fecha_corte()
        
        ws = sheets_client.get_worksheet(Hojas.CONTROL_ASISTENCIA)
        if not ws:
            return jsonify({'status': 'error', 'message': 'No se encontró la hoja de control de asistencia'}), 404
            
        registros = sheets_client.get_all_records_seguro(ws)
        mis_registros = []
        
        for r in registros:
            # Filtrar por nombre
            if str(r.get('COLABORADOR', '')).strip().upper() == colaborador.strip().upper():
                fecha_str = str(r.get('FECHA', ''))
                try:
                    # Asumiendo formato YYYY-MM-DD del frontend (o DD/MM/YYYY)
                    # Intentamos parsear para asegurar que es de esta semana
                    if '-' in fecha_str:
                        fecha_reg = datetime.strptime(fecha_str, '%Y-%m-%d')
                    else:
                        fecha_reg = datetime.strptime(fecha_str, '%d/%m/%Y')
                        
                    if not ultima_fecha_corte or fecha_reg > ultima_fecha_corte:
                        mis_registros.append({
                            'fecha': fecha_reg.strftime('%Y-%m-%d'),
                            'ingreso_real': r.get('INGRESO_REAL', r.get('INGRESO REAL', '')),
                            'salida_real': r.get('SALIDA_REAL', r.get('SALIDA REAL', '')),
                            'horas_ordinarias': r.get('HORAS_ORDINARIAS', r.get('HORAS ORDINARIAS', 0)),
                            'horas_extras': r.get('HORAS_EXTRAS', r.get('HORAS EXTRAS', 0))
                        })
                except Exception as parse_e:
                    logger.warning(f"Error parseando fecha {fecha_str} para {colaborador}: {parse_e}")
                    # Si falla el parseo, pero el nombre coincide, podríamos enviarlo igual o omitirlo
                    pass

        # Ordenar por fecha descendente
        mis_registros.sort(key=lambda x: x['fecha'], reverse=True)

        return jsonify({
            'status': 'success',
            'registros': mis_registros
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo mis_horas para {colaborador}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/registros_dia', methods=['GET'])
def obtener_registros_dia():
    """Obtiene todos los registros de asistencia para una fecha específica."""
    fecha = request.args.get('fecha')
    if not fecha:
        return jsonify({'status': 'error', 'message': 'Fecha no proporcionada'}), 400
        
    try:
        ws = sheets_client.get_worksheet(Hojas.CONTROL_ASISTENCIA)
        if not ws:
            return jsonify({'status': 'error', 'message': 'No se encontró la hoja de control de asistencia'}), 404
            
        registros = sheets_client.get_all_records_seguro(ws)
        registros_dia = []
        
        for r in registros:
            fecha_reg = str(r.get('FECHA', '')).strip()
            if fecha_reg == fecha:
                registros_dia.append({
                    'colaborador': r.get('COLABORADOR', ''),
                    'ingreso_real': r.get('INGRESO_REAL', r.get('INGRESO REAL', '')),
                    'salida_real': r.get('SALIDA_REAL', r.get('SALIDA REAL', '')),
                    'horas_ordinarias': r.get('HORAS_ORDINARIAS', r.get('HORAS ORDINARIAS', 0)),
                    'horas_extras': r.get('HORAS_EXTRAS', r.get('HORAS EXTRAS', 0)),
                    'estado': r.get('ESTADO', 'PRESENTE'),
                    'motivo': r.get('MOTIVO', '')
                })
        
        return jsonify({
            'status': 'success',
            'registros': registros_dia
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo registros_dia para {fecha}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def get_ultima_fecha_corte():
    """Helper para obtener la última fecha de corte desde CORTES_NOMINA."""
    try:
        from datetime import datetime
        ws_cortes = sheets_client.get_worksheet(Hojas.CORTES_NOMINA)
        if not ws_cortes:
            return None
        
        cortes = sheets_client.get_all_records_seguro(ws_cortes)
        if not cortes:
            return None
            
        ultimo_corte = cortes[-1]
        fecha_str = ""
        for k, v in ultimo_corte.items():
            if 'FECHA' in str(k).upper():
                fecha_str = str(v).strip()
                break
                
        if fecha_str:
            if 'T' in fecha_str:
                return datetime.fromisoformat(fecha_str.split('T')[0])
            else:
                return datetime.strptime(fecha_str.split(' ')[0], '%Y-%m-%d')
    except Exception as e:
        logger.warning(f"Error detectando última fecha de corte: {e}")
    return None

@asistencia_bp.route('/consolidado_pendiente', methods=['GET'])
@require_role(['administracion'])
def obtener_consolidado_pendiente():
    """Obtiene el resumen de horas pendientes desde el último corte."""
    try:
        # 1. Obtener última fecha de corte (usando helper)
        ultima_fecha_corte = get_ultima_fecha_corte()

        # 2. Consultar asistencia y filtrar
        ws_asistencia = sheets_client.get_worksheet(Hojas.CONTROL_ASISTENCIA)
        if not ws_asistencia:
            return jsonify({'status': 'error', 'message': 'No se encontró la hoja de asistencia'}), 404
            
        registros = sheets_client.get_all_records_seguro(ws_asistencia)
        consolidado = {}
        detalle_diario = []  # Lista de registros individuales para el CSV detallado
        total_regs = 0
        from datetime import datetime

        for r in registros:
            fecha_reg_str = str(r.get('FECHA', '')).strip()
            if not fecha_reg_str: continue
            
            try:
                # Formato esperado: YYYY-MM-DD
                fecha_reg = datetime.strptime(fecha_reg_str, '%Y-%m-%d')
            except:
                continue

            # Filtrar: Solo registros posteriores al último corte
            if ultima_fecha_corte and fecha_reg <= ultima_fecha_corte:
                continue
                
            # Helpers para castear valores vacíos o con comas de excel
            def parse_hours(val):
                if not val: return 0.0
                try: 
                    return float(str(val).replace(',', '.'))
                except ValueError:
                    return 0.0
            
            colab = r.get('COLABORADOR', 'Desconocido')
            h_ord = parse_hours(r.get('HORAS_ORDINARIAS', r.get('HORAS ORDINARIAS', 0)))
            h_ext = parse_hours(r.get('HORAS_EXTRAS', r.get('HORAS EXTRAS', 0)))
            
            if colab not in consolidado:
                consolidado[colab] = {'ordinarias': 0.0, 'extras': 0.0}
            
            # Suma acumulativa matemática con redondeo explícito
            consolidado[colab]['ordinarias'] += h_ord
            consolidado[colab]['extras'] += h_ext
            
            consolidado[colab]['ordinarias'] = round(consolidado[colab]['ordinarias'], 2)
            consolidado[colab]['extras'] = round(consolidado[colab]['extras'], 2)
            
            total_regs += 1

            # Guardar detalle diario para el CSV
            detalle_diario.append({
                'colaborador': colab,
                'fecha': fecha_reg_str,
                'ingreso': r.get('INGRESO_REAL', r.get('INGRESO REAL', '')),
                'salida': r.get('SALIDA_REAL', r.get('SALIDA REAL', '')),
                'horas_ordinarias': h_ord,
                'horas_extras': h_ext,
                'motivo': r.get('MOTIVO', ''),
                'comentarios': r.get('COMENTARIOS', '')
            })

        # Ordenar detalle por colaborador y luego por fecha
        detalle_diario.sort(key=lambda x: (x['colaborador'], x['fecha']))

        return jsonify({
            'status': 'success',
            'ultima_fecha_corte': ultima_fecha_corte.isoformat() if ultima_fecha_corte else 'Histórico inicial',
            'consolidado': consolidado,
            'detalle_diario': detalle_diario,
            'total_registros_pendientes': total_regs
        }), 200

    except Exception as e:
        logger.error(f"Error en consolidado_pendiente: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/ejecutar_corte', methods=['POST'])
@require_role(['administracion'])
def ejecutar_corte():
    """Registra un nuevo corte de nómina."""
    try:
        data = request.json
        total_registros = data.get('total_registros', 0)
        usuario = data.get('usuario', 'Sistema')
        
        ws_cortes = sheets_client.get_worksheet(Hojas.CORTES_NOMINA)
        if not ws_cortes:
            # Si no existe, intentar crearla o dar error
            return jsonify({'status': 'error', 'message': 'Hoja CORTES_NOMINA no detectada'}), 404
            
        import uuid
        from datetime import datetime
        
        id_corte = str(uuid.uuid4())[:8].upper()
        fecha_ahora = datetime.now().isoformat()
        
        ws_cortes.append_row([
            id_corte,
            fecha_ahora,
            usuario,
            total_registros
        ])
        
        return jsonify({
            'status': 'success',
            'message': f'Corte {id_corte} ejecutado correctamente con {total_registros} registros.',
            'fecha': fecha_ahora
        }), 200
        
    except Exception as e:
        logger.error(f"Error ejecutando corte: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
