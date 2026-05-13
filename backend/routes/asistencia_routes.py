from flask import Blueprint, jsonify, request, session
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_JEFES, ROL_COMERCIALES, ROL_OPERARIOS
from backend.services.nomina_service import (
    get_ultima_fecha_corte,
    filtrar_registros_post_corte,
    consolidar_horas,
    construir_detalle_diario,
)
import logging
import pandas as pd
from datetime import datetime
from backend.core.sql_database import db

logger = logging.getLogger(__name__)
asistencia_bp = Blueprint('asistencia', __name__)

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

        # 1. Definir Áreas de Responsabilidad (Reglas de Oro)
        AREAS_POR_ROL = {
            'JEFE INYECCION':     ['INYECCION', 'ENSAMBLE'],
            'JEFE ALMACEN':       ['ALISTAMIENTO', 'ALMACEN', 'BODEGA'],
            'JEFE PULIDO':        ['PULIDO'],
            'JEFE DE PLANTA':     ['INYECCION', 'PULIDO', 'ENSAMBLE', 'ALMACEN', 'ALISTAMIENTO', 'PLANTA', 'PRODUCCION'],
            'STAFF FRIMETALS':    ['STAFF FRIMETALS', 'METALES', 'PLANTA'],
            'ADMIN FRIMETALS':    ['STAFF FRIMETALS', 'METALES', 'PLANTA', 'ADMINISTRACION'],
        }

        # 2. Construir Filtro
        ADMS = ['ADMIN', 'GERENCIA', 'ADMINISTRACION', 'GERENCIA GLOBAL', 'ADMINISTRADOR']
        es_admin_global = any(r in user_role for r in ADMS)

        # Obtener departamento del usuario actual
        sql_propio = text("SELECT departamento FROM db_usuarios WHERE username = :user")
        propio_res = db.session.execute(sql_propio, {'user': user_name}).fetchone()
        mi_depto = propio_res[0] if propio_res and propio_res[0] else 'SIN_DEPTO'

        # Determinar lista de departamentos visibles para este usuario
        deptos_visibles = AREAS_POR_ROL.get(user_role, [mi_depto])
        # Asegurar que siempre vea su propio departamento aunque no esté en el mapa
        if mi_depto and mi_depto not in deptos_visibles:
            deptos_visibles.append(mi_depto)

        # LÓGICA DE VISIBILIDAD:
        # 1. Admins Globales: Ven TODO without restrictions
        # 2. Jefes/Staff: Ven sus departamentos asignados + ellos mismos
        if es_admin_global:
            sql = text("""
                SELECT * FROM db_usuarios 
                WHERE activo = true 
                ORDER BY username ASC
            """)
            params = {}
        else:
            # Filtro por Áreas de Responsabilidad (Flexible)
            sql = text("""
                SELECT * FROM db_usuarios 
                WHERE activo = true 
                AND (
                    upper(departamento) IN :deptos
                    OR username = :current_user
                )
                ORDER BY username ASC
            """)
            # Normalizar a mayúsculas para el match IN
            params = {
                'deptos': tuple(d.upper() for d in deptos_visibles),
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
@require_role(ROL_ADMINS + ROL_JEFES)
def guardar_asistencia():
    """Guarda los registros de asistencia masivos en PostgreSQL."""
    try:
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
                existente.jefe = usuario_registra
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
                    jefe=usuario_registra,
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
@require_role(ROL_ADMINS + ROL_JEFES)
def guardar_ausencia():
    """Guarda un registro de ausencia en SQL y Google Sheets."""
    try:
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
            jefe=reg.get('registrado_por', 'Sistema'),
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
                horas_ordinarias, horas_extras, jefe, estado, motivo, comentarios, estado_pago 
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
    """Resumen de horas con blindaje total y soporte para registros antiguos (NULL -> PENDIENTE)."""
    try:
        from sqlalchemy import text
        from backend.models.sql_models import CorteNomina
        
        # 1. Obtener última fecha de corte con parseo seguro (Pandas)
        ultimo_corte = db.session.query(CorteNomina).order_by(CorteNomina.fecha_corte.desc()).first()
        ultima_fecha_str = seguro_formatear_fecha(ultimo_corte.fecha_corte) if ultimo_corte else "Sin cortes previos"

        # 2. Query de Consolidado con filtro de división (Metales vs Global)
        division = request.args.get('division', '').lower()
        condicion_rol = ""
        if division == 'frimetals':
            condicion_rol = "AND u.rol ILIKE 'staff frimetals'"
        else:
            # Juan Sebastian: Para FriParts, excluimos personal de metales para total aislamiento
            condicion_rol = "AND u.rol NOT ILIKE 'staff frimetals'"

        sql = text(f"""
            SELECT 
                u.username as colaborador,
                u.departamento as departamento,
                COALESCE(SUM(CAST(a.horas_ordinarias AS NUMERIC)), 0) as horas_ordinarias,
                COALESCE(SUM(CAST(a.horas_extras AS NUMERIC)), 0) as horas_extras,
                COUNT(a.id) as registros_contados
            FROM db_usuarios u
            LEFT JOIN db_asistencia a 
                ON u.username = a.colaborador 
                AND COALESCE(a.estado_pago, 'PENDIENTE') = 'PENDIENTE'
            WHERE u.activo = true
            {condicion_rol}
            GROUP BY u.username, u.departamento
            ORDER BY u.username ASC
        """)
        rows = db.session.execute(sql).mappings().all()

        consolidado_array = []
        for r in rows:
            consolidado_array.append({
                'colaborador': r['colaborador'],
                'departamento': r['departamento'] or 'N/A',
                'horas_ordinarias': round(float(r['horas_ordinarias']), 2),
                'horas_extras': round(float(r['horas_extras']), 2),
                'estado': 'PENDIENTE',
                'registros': int(r['registros_contados'])
            })

        # 3. Detalle para el CSV (incluyendo NULL -> PENDIENTE)
        detalle_diario = []
        try:
            sql_detalle = text(f"""
                SELECT 
                    a.fecha, a.colaborador, a.ingreso_real, a.salida_real,
                    a.horas_ordinarias, a.horas_extras, a.motivo, a.comentarios
                FROM db_asistencia a
                JOIN db_usuarios u ON a.colaborador = u.username
                WHERE COALESCE(a.estado_pago, 'PENDIENTE') = 'PENDIENTE'
                {condicion_rol}
                ORDER BY a.colaborador, a.fecha
            """)
            registros_filtrados = db.session.execute(sql_detalle).mappings().all()
            
            for r in registros_filtrados:
                detalle_diario.append({
                    'colaborador': r['colaborador'],
                    'fecha': seguro_formatear_fecha(r['fecha'], '%d/%m/%Y'),
                    'ingreso': r['ingreso_real'],
                    'salida': r['salida_real'],
                    'horas_ordinarias': round(float(r['horas_ordinarias'] or 0), 2),
                    'horas_extras': round(float(r['horas_extras'] or 0), 2),
                    'motivo': r['motivo'] or '',
                    'comentarios': r['comentarios'] or ''
                })
        except Exception as e_det:
            logger.error(f"Error en detalle CSV: {e_det}")

        return jsonify({
            'status': 'success',
            'ultima_fecha_corte': ultima_fecha_str,
            'fecha': ultima_fecha_str, # Sincronización para frontend
            'consolidado': consolidado_array, 
            'detalle_diario': detalle_diario,
            'total_registros_pendientes': len(detalle_diario)
        }), 200

    except Exception as e:
        logger.error(f"FALLO CRÍTICO CONSOLIDADO: {e}")
        return jsonify({
            'status': 'success',
            'consolidado': [],
            'detalle_diario': [],
            'total_registros_pendientes': 0,
            'ultima_fecha_corte': 'Error en el servidor',
            'fecha': 'Error'
        }), 200

@asistencia_bp.route('/ejecutar_corte', methods=['POST'])
@require_role(ROL_ADMINS)
def ejecutar_corte():
    """Registra un nuevo corte en la tabla cortes_nomina existente y procesa registros."""
    try:
        from sqlalchemy import text, func
        from datetime import datetime
        import uuid
        from backend.core.sql_database import db
        from backend.models.sql_models import CorteNomina, RegistroAsistencia

        data = request.json
        usuario = data.get('usuario', 'Sistema')
        division = data.get('division', 'friparts').lower()
        id_corte_uuid = str(uuid.uuid4())[:8].upper()
        
        # 1. Detectar Periodo Filtrado por División
        # Un cierre en FriMetals no debe afectar registros de FriParts
        from backend.models.sql_models import Usuario
        
        condicion_rol = "AND u.rol ILIKE 'staff frimetals'" if division == 'frimetals' else "AND u.rol NOT ILIKE 'staff frimetals'"

        # Query para detectar p_inicio y p_fin localmente
        sql_periodo = text(f"""
            SELECT MIN(a.fecha), MAX(a.fecha)
            FROM db_asistencia a
            JOIN db_usuarios u ON a.colaborador = u.username
            WHERE COALESCE(a.estado_pago, 'PENDIENTE') = 'PENDIENTE'
            {condicion_rol}
        """)
        res_periodo = db.session.execute(sql_periodo).fetchone()
        
        p_inicio = res_periodo[0] if res_periodo else None
        p_fin = res_periodo[1] if res_periodo else None

        # 2. Histórico
        nuevo_corte = CorteNomina(
            id_corte=f"{id_corte_uuid}-{division.upper()}",
            fecha_corte=datetime.now(),
            usuario_que_corta=usuario,
            periodo_inicio=p_inicio,
            periodo_fin=p_fin
        )
        db.session.add(nuevo_corte)
        
        # 3. UPDATE Masivo aislado por división
        try:
            sql_update = text(f"""
                UPDATE db_asistencia 
                SET estado_pago = 'PROCESADO' 
                FROM db_usuarios u
                WHERE db_asistencia.colaborador = u.username
                AND COALESCE(db_asistencia.estado_pago, 'PENDIENTE') = 'PENDIENTE'
                AND db_asistencia.fecha <= :fecha_limite
                {condicion_rol}
            """)
            db.session.execute(sql_update, {"fecha_limite": p_fin})
            db.session.commit()
            logger.info(f"✅ Corte {id_corte_uuid} ({division}) finalizado: Registros hasta {p_fin} marcados como PROCESADO.")
        except Exception as e_sql:
            db.session.rollback()
            raise e_sql

        return jsonify({
            'status': 'success',
            'periodo': f"{seguro_formatear_fecha(p_inicio, '%d/%m')} a {seguro_formatear_fecha(p_fin, '%d/%m')}",
            'message': f'Corte {id_corte_uuid} ejecutado con éxito.'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error ejecución corte: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
