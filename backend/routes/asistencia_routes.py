from flask import Blueprint, jsonify, request, session
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_JEFES, ROL_COMERCIALES, ROL_OPERARIOS
from backend.services.nomina_service import (
    get_ultima_fecha_corte,
    filtrar_registros_post_corte,
    consolidar_horas,
    construir_detalle_diario,
    # ── Nuevas responsabilidades del servicio ──
    ejecutar_corte_db,
    get_consolidado_pendiente,
    get_detalle_diario_pendiente,
)
import logging
import pandas as pd
from datetime import datetime
from backend.core.sql_database import db

logger = logging.getLogger(__name__)
asistencia_bp = Blueprint('asistencia', __name__)

# Roles autorizados para gestionar nómina unificada cross-division (heredado del middleware central)
ROLES_NOMINA_GLOBAL = ROL_ADMINS

def seguro_formatear_fecha(valor, formato='%d/%m/%Y %H:%M'):
    """Convierte cualquier objeto (str, datetime, timestamp, null) a un string de fecha seguro."""
    if not valor: return ""
    try:
        dt = pd.to_datetime(valor)
        if pd.isna(dt): return ""
        return dt.strftime(formato)
    except:
        return str(valor)

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
@asistencia_bp.route('/personal_a_cargo', methods=['GET'])
def obtener_colaboradores():
    """Obtiene lista de colaboradores filtrada por Áreas de Responsabilidad. Incluye al Jefe."""
    try:
        from sqlalchemy import text
        from datetime import datetime
        
        user_name = session.get('user')
        user_role = session.get('role', '').upper()
        hoy = datetime.now().strftime('%Y-%m-%d')

        if not user_name:
            return jsonify({'status': 'error', 'message': 'Sesión no válida'}), 401

        # Helper AGRESIVO para normalizar horas locas (ej: "5:00:00 p. m.")
        def formatear_a_24h(hora_str):
            if not hora_str: return "00:00"
            s = str(hora_str).lower().strip()
            
            import re
            # 1. Extraer HH y MM mediante regex
            match = re.search(r'(\d{1,2})[\s:](\d{2})', s)
            if not match:
                return "00:00"
                
            hh = int(match.group(1))
            mm = int(match.group(2))
            
            # 2. Detección Blindada de PM (busca 'p' sola, 'pm', 'p.m.')
            es_pm = 'p' in s
            
            # 3. Conversión a 24h
            if es_pm and hh < 12:
                hh += 12
            elif not es_pm and hh == 12:
                hh = 0
            
            return f"{hh:02d}:{mm:02d}"

        # 1. Identificación de Poder (Dynamic RBAC)
        ADMS = ['ADMIN', 'GERENCIA', 'ADMINISTRACION', 'GERENCIA GLOBAL', 'ADMINISTRADOR']
        es_admin_global = any(r in user_role for r in ADMS)
        es_jefe = 'JEFE' in user_role

        # 2. Obtener departamento del usuario actual (Pivote de Seguridad)
        sql_propio = text("SELECT upper(trim(departamento)) FROM db_usuarios WHERE username = :user")
        propio_res = db.session.execute(sql_propio, {'user': user_name}).fetchone()
        mi_depto = propio_res[0] if propio_res and propio_res[0] else 'SIN_DEPTO'
        
        # 2.1. Derivar departamento base (Ej: 'JEFE ALMACEN' -> 'ALMACEN')
        depto_base = mi_depto.replace('JEFE ', '').strip()
        deptos_match = (mi_depto, depto_base)

        # 3. Determinar Áreas Visibles
        if es_admin_global:
            deptos_visibles = None # Ver todo
        elif es_jefe:
            # Lógica Genérica: El Jefe solo ve su propio departamento (Match Exacto)
            deptos_visibles = [mi_depto]
        else:
            # Operarios solo se ven a sí mismos (handled below in the query logic or result filtering)
            deptos_visibles = [mi_depto]

        # LÓGICA DE VISIBILIDAD BLINDADA:
        if es_admin_global:
            sql = text("""
                SELECT * FROM db_usuarios 
                WHERE activo = true 
                ORDER BY username ASC
            """)
            params = {}
        else:
            # Filtro por Coincidencia de Departamento (Soporta prefijo JEFE)
            sql = text("""
                SELECT * FROM db_usuarios 
                WHERE activo = true 
                AND (
                    upper(trim(departamento)) IN :deptos
                    OR username = :current_user
                )
                ORDER BY username ASC
            """)
            params = {
                'deptos': deptos_match,
                'current_user': user_name
            }

        rows = db.session.execute(sql, params).mappings().all()

        # 3. Marcar estado de hoy
        sql_hoy = text("SELECT colaborador, ingreso_real, salida_real FROM db_asistencia WHERE fecha = :hoy")
        registros_hoy = db.session.execute(sql_hoy, {'hoy': hoy}).mappings().all()
        dict_hoy = {r['colaborador']: r for r in registros_hoy}

        colaboradores = []
        for r in rows:
            # Lógica de nombre unificada: nombre_completo > username
            nombre_final = r['nombre_completo'] if r['nombre_completo'] else r['username']
            
            # Buscar si ya tiene registro hoy usando el nombre final (Full Name)
            reg = dict_hoy.get(nombre_final, {})
            
            h_inc_oficial = formatear_a_24h(r['hora_entrada'])
            h_sal_oficial = formatear_a_24h(r['hora_salida'])
            
            colaboradores.append({
                'nombre': nombre_final,
                'username': r['username'],
                'departamento': r['departamento'] or r['rol'].upper(),
                'area': r['departamento'] or r['rol'].upper(),
                'hora_entrada_oficial': h_inc_oficial,
                'hora_salida_oficial': h_sal_oficial,
                'hora_entrada': formatear_a_24h(reg.get('ingreso_real')) if reg.get('ingreso_real') else h_inc_oficial, 
                'hora_salida': formatear_a_24h(reg.get('salida_real')) if reg.get('salida_real') else h_sal_oficial,
                'registrado_hoy': bool(reg),
                'ya_ingreso': bool(reg and reg.get('ingreso_real') and reg.get('ingreso_real') != 'AUSENTE'),
                'ya_salio': bool(reg and reg.get('salida_real') and reg.get('salida_real') != ''),
                'estado': reg.get('estado', 'PENDIENTE'),
                'motivo': reg.get('motivo', ''),
                'comentarios': reg.get('comentarios', '')
            })

        return jsonify({
            'status': 'success',
            'count': len(colaboradores),
            'colaboradores': colaboradores
        }), 200
        
    except Exception as e:
        logger.error(f"Error en personal_a_cargo (SQL-RBAC): {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/guardar', methods=['POST'])
@asistencia_bp.route('/registrar_masivo', methods=['POST'])
def guardar_asistencia():
    """Guarda los registros de asistencia masivos en PostgreSQL."""
    try:
        # Validación de Permisos Manual para permitir 'JEFE' wildcard
        user_role = session.get('role', '').upper()
        ADMS = ['ADMIN', 'GERENCIA', 'ADMINISTRACION', 'GERENCIA GLOBAL', 'ADMINISTRADOR']
        es_autorizado = any(r in user_role for r in ADMS) or 'JEFE' in user_role
        
        if not es_autorizado:
            return jsonify({'status': 'error', 'message': 'No tiene permisos para reportar asistencia'}), 403
        data = request.json
        if not data or 'registros' not in data:
            return jsonify({'status': 'error', 'message': 'Datos inválidos o vacíos'}), 400
        
        from backend.models.sql_models import RegistroAsistencia
        from backend.core.sql_database import db

        registros_recibidos = data['registros']
        usuario_registra = session.get('user', 'Sistema')
        conteo = 0

        for reg in registros_recibidos:
            nombre = reg.get('colaborador') or reg.get('nombre')
            if not nombre: continue

            # Determinar fecha (ISO -> Date)
            f_str = reg.get('fecha') or datetime.now().strftime('%Y-%m-%d')
            try:
                fecha_dt = datetime.strptime(f_str, '%Y-%m-%d').date()
            except:
                fecha_dt = datetime.now().date()

            # Buscar si ya existe registro para ese colaborador-día para evitar duplicados
            existente = RegistroAsistencia.query.filter_by(
                fecha=fecha_dt, 
                colaborador=nombre
            ).first()

            h_ord = float(reg.get('horas_ordinarias', 0) or reg.get('horas_normales', 0) or 0)
            h_ext = float(reg.get('horas_extras', 0) or 0)

            if existente:
                # Actualización
                existente.ingreso_real = reg.get('ingreso_real') or reg.get('hora_entrada', '')
                existente.salida_real = reg.get('salida_real') or reg.get('hora_salida', '')
                existente.horas_ordinarias = h_ord
                existente.horas_extras = h_ext
                # Columna 'jefe' eliminada para evitar caídas del servidor
                existente.estado = reg.get('estado', 'REGISTRADO')
                existente.comentarios = reg.get('comentarios', '')
            else:
                # Inserción
                nuevo = RegistroAsistencia(
                    fecha=fecha_dt,
                    colaborador=nombre,
                    ingreso_real=reg.get('ingreso_real') or reg.get('hora_entrada', ''),
                    salida_real=reg.get('salida_real') or reg.get('hora_salida', ''),
                    horas_ordinarias=h_ord,
                    horas_extras=h_ext,
                    # Columna 'jefe' eliminada
                    estado=reg.get('estado', 'REGISTRADO'),
                    estado_pago='PENDIENTE',
                    comentarios=reg.get('comentarios', '')
                )
                db.session.add(nuevo)
            
            conteo += 1

        db.session.commit()
        logger.info(f"💾 SQL: {conteo} registros de asistencia procesados exitosamente.")
        
        return jsonify({
            'status': 'success',
            'message': f'Se procesaron {conteo} registros en SQL correctamente.'
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error guardando asistencia en SQL: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/guardar_ausencia', methods=['POST'])
def guardar_ausencia():
    """Guarda un registro de ausencia en SQL."""
    try:
        # Validación de Permisos Manual
        user_role = session.get('role', '').upper()
        ADMS = ['ADMIN', 'GERENCIA', 'ADMINISTRACION', 'GERENCIA GLOBAL', 'ADMINISTRADOR']
        es_autorizado = any(r in user_role for r in ADMS) or 'JEFE' in user_role
        
        if not es_autorizado:
            return jsonify({'status': 'error', 'message': 'No tiene permisos para reportar ausencias'}), 403
        data = request.json
        if not data or 'registro' not in data:
            return jsonify({'status': 'error', 'message': 'Datos inválidos'}), 400
        
        reg = data['registro']
        from backend.models.sql_models import RegistroAsistencia
        from backend.core.sql_database import db

        # 1. SQL
        nueva_ausencia = RegistroAsistencia(
            fecha=reg.get('fecha'),
            colaborador=reg.get('colaborador'),
            ingreso_real='AUSENTE',
            salida_real='',
            horas_ordinarias=0,
            horas_extras=0,
            # Columna 'jefe' eliminada
            estado='AUSENTE',
            estado_pago='PENDIENTE', 
            motivo=reg.get('motivo', ''),
            comentarios=reg.get('comentarios', '')
        )
        db.session.add(nueva_ausencia)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Ausencia registrada correctamente en SQL'}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error guardando ausencia: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/mis_horas', methods=['GET'])
@require_role(ROL_ADMINS + ROL_JEFES + ROL_COMERCIALES + ROL_OPERARIOS)
def obtener_mis_horas():
    """Obtiene el historial de asistencia del usuario logueado usando SQL crudo con blindaje total."""
    try:
        from sqlalchemy import text
        from datetime import datetime
        from backend.core.sql_database import db

        colaborador = session.get('user')
        if not colaborador:
            return jsonify({'status': 'error', 'message': 'Acceso denegado'}), 401

        # Obtener nombre completo para búsqueda robusta
        from backend.models.sql_models import Usuario
        u = Usuario.query.filter_by(username=colaborador).first()
        nombre_buscar = u.nombre_completo if u and u.nombre_completo else colaborador

        # 1. SQL flexible (Muestra las últimas 50 independientemente del pago)
        sql = text("""
            SELECT 
                id, fecha, colaborador, ingreso_real, salida_real, 
                horas_ordinarias, horas_extras, estado, motivo, comentarios, estado_pago 
            FROM db_asistencia 
            WHERE (colaborador ILIKE :full_name OR colaborador ILIKE :username_pattern)
            ORDER BY fecha DESC, id DESC 
            LIMIT 50
        """)

        # Patrones flexibles
        username_pattern = f"{colaborador.split(' ')[0]}%" if ' ' in colaborador else f"{colaborador}%"
        full_name_pattern = f"%{nombre_buscar}%"
        
        result = db.session.execute(sql, {
            "full_name": full_name_pattern,
            "username_pattern": username_pattern
        })
        rows = result.mappings().all()
        
        mis_registros = []
        for row in rows:
            # Formateo de fecha robusto con Pandas
            fecha_str = seguro_formatear_fecha(row['fecha'], '%d/%m (%a)')
            # Traducir días si es necesario (Pandas .strftime('%a') suele dar ingles)
            dias_map = {'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié', 'Thu': 'Jue', 'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom'}
            for eng, esp in dias_map.items():
                fecha_str = fecha_str.replace(eng, esp)

            mis_registros.append({
                'fecha': fecha_str,
                'llegada': row['ingreso_real'] or '-',
                'salida': row['salida_real'] or '-',
                'horas_normales': round(float(row['horas_ordinarias'] or 0), 2),
                'horas_extras': round(float(row['horas_extras'] or 0), 2),
                'estado': row['estado'],
                'motivo': row['motivo'],
                'estado_pago': row['estado_pago'] or 'PENDIENTE'
            })
        
        return jsonify({
            'status': 'success',
            'registros': mis_registros,
            'rol': session.get('role', 'OPERARIO').upper()
        }), 200
        
    except Exception as e:
        import logging
        logging.error(f"FALLO CRÍTICO en obtener_mis_horas: {e}")
        # Blindaje: Devolver lista vacía para no romper el frontend
        return jsonify({
            'status': 'success',
            'registros': [],
            'error_info': str(e)
        }), 200

@asistencia_bp.route('/registros_dia', methods=['GET'])
def obtener_registros_dia():
    """Obtiene registros de una fecha específica desde SQL."""
    fecha = request.args.get('fecha')
    if not fecha: return jsonify({'status': 'error', 'message': 'Fecha inválida'}), 400
        
    try:
        from backend.models.sql_models import RegistroAsistencia
        registros = RegistroAsistencia.query.filter_by(fecha=fecha).all()
        
        res = []
        for r in registros:
            res.append({
                'colaborador': r.colaborador, 'ingreso_real': r.ingreso_real,
                'salida_real': r.salida_real, 'horas_ordinarias': r.horas_ordinarias,
                'horas_extras': r.horas_extras, 'estado': r.estado, 'motivo': r.motivo
            })
        
        return jsonify({'status': 'success', 'registros': res}), 200
    except Exception as e:
        logger.error(f"Error en obtener_registros_dia: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@asistencia_bp.route('/consolidado_pendiente', methods=['GET'])
@require_role(ROL_ADMINS)
def obtener_consolidado_pendiente():
    """Orquestador de respuesta. Lógica de negocio en nomina_service."""
    # 1. Validar sesión activa
    if not session or not session.get('user'):
        return jsonify({
            'status': 'error',
            'message': 'Sesión inválida o nula. Debe autenticarse en el sistema.'
        }), 401

    try:
        from backend.models.sql_models import CorteNomina

        division = request.args.get('division', 'friparts').lower()

        # 2. Validar rol para permitir bypass ('all')
        user_role = str(session.get('role', '')).upper()
        is_global_admin = user_role in ROLES_NOMINA_GLOBAL

        if division == 'all':
            if not is_global_admin:
                return jsonify({
                    'status': 'error',
                    'message': 'Acceso denegado: Se requiere rol administrativo global para consultar información consolidada unificada.'
                }), 403
        elif division not in ('friparts', 'frimetals'):
            return jsonify({
                'status': 'error',
                'message': f'División inválida: {division!r}. Las opciones válidas son "friparts", "frimetals" o "all".'
            }), 400

        # Delegar al servicio
        consolidado_array = get_consolidado_pendiente(division)
        detalle_diario = get_detalle_diario_pendiente(division)

        # Último corte (solo para el label informativo del frontend)
        ultimo_corte = db.session.query(CorteNomina).order_by(CorteNomina.fecha_corte.desc()).first()
        ultima_fecha_str = seguro_formatear_fecha(ultimo_corte.fecha_corte) if ultimo_corte else "Sin cortes previos"

        return jsonify({
            'status': 'success',
            'ultima_fecha_corte': ultima_fecha_str,
            'fecha': ultima_fecha_str,
            'consolidado': consolidado_array,
            'detalle_diario': detalle_diario,
            'total_registros_pendientes': len(detalle_diario)
        }), 200

    except Exception as e:
        logger.error(f"FALLO CRÍTICO CONSOLIDADO: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error en el servidor al consolidar la nómina: {str(e)}',
            'consolidado': [],
            'detalle_diario': [],
            'total_registros_pendientes': 0,
            'ultima_fecha_corte': 'Error en el servidor',
            'fecha': 'Error'
        }), 500

@asistencia_bp.route('/ejecutar_corte', methods=['POST'])
@require_role(ROL_ADMINS)
def ejecutar_corte():
    """Orquestador de respuesta. Lógica de negocio en nomina_service.ejecutar_corte_db()."""
    # 1. Validar sesión activa
    if not session or not session.get('user'):
        return jsonify({
            'status': 'error',
            'message': 'Sesión inválida o nula. Debe autenticarse en el sistema.'
        }), 401

    # 2. Obtener y validar el payload de manera segura
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({
            'status': 'error',
            'message': 'El cuerpo de la solicitud no es un JSON válido.'
        }), 400

    usuario = data.get('usuario', '').strip()
    division = data.get('division', '').strip().lower()

    # 3. Validar campos requeridos en el payload
    if not usuario:
        return jsonify({
            'status': 'error',
            'message': 'El payload no contiene la información del usuario que autoriza el corte ("usuario" requerido).'
        }), 400

    # 4. Validar privilegios sobre la división seleccionada
    user_role = str(session.get('role', '')).upper()
    is_global_admin = user_role in ROLES_NOMINA_GLOBAL

    if division == 'all':
        if not is_global_admin:
            return jsonify({
                'status': 'error',
                'message': 'Acceso denegado: Se requiere rol administrativo global para ejecutar cortes consolidados (ALL).'
            }), 403
    elif division not in ('friparts', 'frimetals'):
        return jsonify({
            'status': 'error',
            'message': f'División inválida: {division!r}. Las opciones válidas son "friparts", "frimetals" o "all".'
        }), 400

    try:
        resultado = ejecutar_corte_db(division=division, usuario=usuario)
        return jsonify({
            'status': 'success',
            'periodo': (
                f"{seguro_formatear_fecha(resultado['p_inicio'], '%d/%m')} "
                f"a {seguro_formatear_fecha(resultado['p_fin'], '%d/%m')}"
            ),
            'message': f"Corte {resultado['id_corte']} ejecutado con éxito."
        }), 200
    except ValueError as e:
        # Sin datos pendientes
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error ejecución corte: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
