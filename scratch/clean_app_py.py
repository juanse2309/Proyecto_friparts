import os

file_path = r"backend/app.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's target the exact string that starts around _mes_cache and goes to mes_dashboard
# We will replace from the broken prog_todas line down to the next route.
target_str = """_mes_cache = {
    'dashboard': {'data': None, 'ts': 0},
    'prog_todas': {'data': Ndef clear_mes_cache():
    \"\"\"Limpia todos los caches de lectura del MES (Llamar en toda operacion de escritura).\"\"\"
    global _mes_cache
    logger.info("🗑️ [CACHE] Invalidando cache MES por operacion de escritura")
    for key in _mes_cache:
        _mes_cache[key]['ts'] = 0

@app.route('/api/mes/programaciones/<maquina>', methods=['GET'])
def mes_get_programaciones(maquina):
    \"\"\"Obtiene programaciones activas desde SQL (db_programacion).\"\"\"
    try:
        from backend.models.sql_models import ProgramacionInyeccion
        import datetime
        maquina_upper = maquina.upper()
        
        today_date = datetime.date.today()
        
        # Filtro: estado es activo (PROGRAMADO, EN_PROCESO) y fecha >= hoy
        query = db.session.query(ProgramacionInyeccion).filter(
            ProgramacionInyeccion.estado.in_(['PROGRAMADO', 'EN_PROCESO']),
            ProgramacionInyeccion.fecha >= today_date
        )
        
        lotes = query.all()
        
        # Auditoría log antes de filtrar por máquina
        today = today_date.strftime('%Y-%m-%d')
        logger.info(f"DEBUG: Cargando {len(lotes)} lotes para la cola de trabajo del {today}")
        
        # Filtrar por máquina si es necesario
        if maquina_upper != 'TODAS':
            lotes = [r for r in lotes if (r.maquina or '').upper() == maquina_upper]
            
        # Formatear para el frontend (adaptado al modelo simplificado)
        data = []
        for r in lotes:
            data.append({
                'id':            r.id,
                'fecha':         r.fecha.strftime('%Y-%m-%d') if r.fecha else '',
                'codigo_sistema': r.codigo_sistema,
                'maquina':       (r.maquina or '').upper(),
                'molde':         r.molde,
                'cavidades':     r.cavidades,
                'cantidad':      float(r.cantidad or 0),
                'estado':        (r.estado or 'PENDIENTE').upper(),
                'orden_produccion': r.op_world_office or 'SIN_OP'
            })

        return jsonify(data), 200
    except Exception as e:
        logger.error(f"❌ Error en mes_get_programaciones SQL: {e}")
        return jsonify([]), 200ce or 'SIN_OP'
            })

        return jsonify(data), 200
    except Exception as e:
        logger.error(f"â Œ Error en mes_get_programaciones SQL: {e}")
        return jsonify([]), 200"""

replacement_str = """_mes_cache = {
    'dashboard': {'data': None, 'ts': 0},
    'prog_todas': {'data': None, 'ts': 0},
    'pendientes_calidad': {'data': None, 'ts': 0},
    'pendientes_validacion': {'data': None, 'ts': 0}
}
MES_CACHE_TTL = 60 # Aumentado a 60s para proteger cuota de API

def clear_mes_cache():
    \"\"\"Limpia todos los caches de lectura del MES (Llamar en toda operacion de escritura).\"\"\"
    global _mes_cache
    logger.info("🗑️ [CACHE] Invalidando cache MES por operacion de escritura")
    for key in _mes_cache:
        _mes_cache[key]['ts'] = 0

@app.route('/api/mes/programaciones/<maquina>', methods=['GET'])
def mes_get_programaciones(maquina):
    \"\"\"Obtiene programaciones activas desde SQL (db_programacion).\"\"\"
    try:
        from backend.models.sql_models import ProgramacionInyeccion
        import datetime
        maquina_upper = maquina.upper()
        
        today_date = datetime.date.today()
        
        # Filtro: estado es activo (PROGRAMADO, EN_PROCESO) y fecha >= hoy
        query = db.session.query(ProgramacionInyeccion).filter(
            ProgramacionInyeccion.estado.in_(['PROGRAMADO', 'EN_PROCESO']),
            ProgramacionInyeccion.fecha >= today_date
        )
        
        lotes = query.all()
        
        # Auditoría log antes de filtrar por máquina
        today = today_date.strftime('%Y-%m-%d')
        logger.info(f"DEBUG: Cargando {len(lotes)} lotes para la cola de trabajo del {today}")
        
        # Filtrar por máquina si es necesario
        if maquina_upper != 'TODAS':
            lotes = [r for r in lotes if (r.maquina or '').upper() == maquina_upper]
            
        # Formatear para el frontend (adaptado al modelo simplificado)
        data = []
        for r in lotes:
            data.append({
                'id':            r.id,
                'fecha':         r.fecha.strftime('%Y-%m-%d') if r.fecha else '',
                'codigo_sistema': r.codigo_sistema,
                'maquina':       (r.maquina or '').upper(),
                'molde':         r.molde,
                'cavidades':     r.cavidades,
                'cantidad':      float(r.cantidad or 0),
                'estado':        (r.estado or 'PENDIENTE').upper(),
                'orden_produccion': r.op_world_office or 'SIN_OP'
            })

        return jsonify(data), 200
    except Exception as e:
        logger.error(f"❌ Error en mes_get_programaciones SQL: {e}")
        return jsonify([]), 200"""

if target_str in content:
    content = content.replace(target_str, replacement_str)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: app.py has been cleaned up and updated.")
else:
    # If exact string with special characters has minor differences (like line endings), let's do a more robust split
    print("FAILED: Exact target string not found. Trying fallback split...")
    parts = content.split("def mes_dashboard():")
    if len(parts) == 2:
        # We find the part before mes_dashboard that contains "_mes_cache"
        header_part, after_dashboard = parts
        cache_idx = header_part.rfind("_mes_cache = {")
        if cache_idx != -1:
            clean_header_part = header_part[:cache_idx] + replacement_str + "\n\n"
            content = clean_header_part + "def mes_dashboard():" + after_dashboard
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("SUCCESS: Fallback split replacement completed.")
        else:
            print("FAILED: Could not find _mes_cache start.")
    else:
        print("FAILED: Could not split by mes_dashboard.")
