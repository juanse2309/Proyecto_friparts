from flask import Blueprint, jsonify, request, session
from backend.utils.auth_middleware import require_role
from backend.core.database import sheets_client
from backend.config.settings import Hojas
from backend.services.nomina_service import (
    get_ultima_fecha_corte,
    filtrar_registros_post_corte,
    consolidar_horas,
    construir_detalle_diario,
)
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
    """Obtiene el historial de asistencia posterior al último corte para el colaborador logueado."""
    colaborador = session.get('user')
    if not colaborador:
        return jsonify({'status': 'error', 'message': 'Acceso denegado. Usuario no autenticado en sesión.'}), 401
        
    try:
        from datetime import datetime
        
        # 1. Obtener fecha de corte desde el servicio centralizado
        ultima_fecha_corte = get_ultima_fecha_corte()
        
        ws = sheets_client.get_worksheet(Hojas.CONTROL_ASISTENCIA)
        if not ws:
            return jsonify({'status': 'error', 'message': 'No se encontró la hoja de control de asistencia'}), 404
            
        registros = sheets_client.get_all_records_seguro(ws)
        
        # 2. Filtrar solo los del colaborador logueado
        registros_colab = [
            r for r in registros
            if str(r.get('COLABORADOR', '')).strip().upper() == colaborador.strip().upper()
        ]
        
        # 3. Aplicar filtro estricto de corte (fecha > ultima_fecha_corte)
        registros_post_corte = filtrar_registros_post_corte(registros_colab, ultima_fecha_corte)
        
        # 4. Construir respuesta
        mis_registros = []
        for r in registros_post_corte:
            fecha_str = str(r.get('FECHA', '')).strip()
            # Normalizar a YYYY-MM-DD para la respuesta
            if '-' in fecha_str:
                fecha_fmt = fecha_str
            else:
                try:
                    fecha_fmt = datetime.strptime(fecha_str, '%d/%m/%Y').strftime('%Y-%m-%d')
                except Exception:
                    fecha_fmt = fecha_str
            
            mis_registros.append({
                'fecha': fecha_fmt,
                'ingreso_real': r.get('INGRESO_REAL', r.get('INGRESO REAL', '')),
                'salida_real': r.get('SALIDA_REAL', r.get('SALIDA REAL', '')),
                'horas_ordinarias': r.get('HORAS_ORDINARIAS', r.get('HORAS ORDINARIAS', 0)),
                'horas_extras': r.get('HORAS_EXTRAS', r.get('HORAS EXTRAS', 0))
            })

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

# get_ultima_fecha_corte() → ahora vive en backend.services.nomina_service

@asistencia_bp.route('/consolidado_pendiente', methods=['GET'])
@require_role(['administracion'])
def obtener_consolidado_pendiente():
    """Obtiene el resumen de horas pendientes desde el último corte (estrictamente mayor)."""
    try:
        # 1. Fecha de corte desde el servicio centralizado
        ultima_fecha_corte = get_ultima_fecha_corte()

        # 2. Consultar asistencia
        ws_asistencia = sheets_client.get_worksheet(Hojas.CONTROL_ASISTENCIA)
        if not ws_asistencia:
            return jsonify({'status': 'error', 'message': 'No se encontró la hoja de asistencia'}), 404

        registros = sheets_client.get_all_records_seguro(ws_asistencia)

        # 3. Filtro estricto: solo registros con fecha > ultima_fecha_corte
        registros_filtrados = filtrar_registros_post_corte(registros, ultima_fecha_corte)

        # 4. Consolidar horas y detalle
        consolidado = consolidar_horas(registros_filtrados)
        detalle_diario = construir_detalle_diario(registros_filtrados)
        total_regs = len(registros_filtrados)

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
