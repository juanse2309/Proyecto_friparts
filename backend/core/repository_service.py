"""
repository_service.py — Capa de Acceso a Datos 100% SQL-First
Todos los métodos leen exclusivamente de PostgreSQL.
El "Traductor Legacy" convierte nombres de columnas SQL → nombres originales de Sheets
para que el frontend funcione sin modificaciones.
"""
from backend.core.sql_database import db
from sqlalchemy import text, func, cast, Numeric
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# MAPA DE TABLAS  (nombre de hoja Sheets → nombre tabla SQL)
# ─────────────────────────────────────────────────────────────
SHEET_TO_TABLE = {
    'INYECCION':            'db_inyeccion',
    'PULIDO':               'db_pulido',
    'CONTROL_ASISTENCIA':   'db_asistencia',
    'PRODUCTOS':            'db_productos',
    'DB_Clientes':          'db_clientes',
    'CLIENTES':             'db_clientes',
    'RESPONSABLES':         'usuarios_raw',
    'PEDIDOS':              'db_pedidos',
    'ENSAMBLES':            'db_ensambles',
    'PNC':                  'db_pnc',
    'RAW_VENTAS':           'db_ventas',
    'db_costos':            'db_costos',
    'METALS_PRODUCTOS':     'metals_productos',
    # Fallbacks / Alias para evitar errores de transicion
    'produccion_inyeccion': 'db_inyeccion',
    'programacion_inyeccion': 'db_programacion',
}

# ─────────────────────────────────────────────────────────────
# TRADUCTOR LEGACY  (columna SQL → nombre original en Sheets)
# Front-end espera exactamente estos nombres.
# ─────────────────────────────────────────────────────────────
COLUMNS_TO_LEGACY = {
    # Productos
    'codigo_sistema':       'CODIGO SISTEMA',
    'id_codigo':            'ID CODIGO',
    'descripcion':          'DESCRIPCION',
    'precio':               'PRECIO',
    'por_pulir':            'POR PULIR',
    'p_terminado':          'P. TERMINADO',
    'comprometido':         'COMPROMETIDO',
    'producto_ensamblado':  'PRODUCTO ENSAMBLADO',
    'imagen':               'IMAGEN',
    'stock_minimo':         'STOCK MINIMO',
    'stock_maximo':         'STOCK MAXIMO',
    'punto_reorden':        'PUNTO REORDEN',
    'oem':                  'OEM',
    'dolares':              'DOLARES',
    'medida':               'MEDIDA',
    'ubicacion':            'UBICACION',
    'categoria':            'CATEGORIA',

    # Producción – genérico
    'cantidad_real':        'CANTIDAD REAL',
    'pnc':                  'PNC',
    'estado':               'ESTADO',
    'responsable':          'RESPONSABLE',
    'maquina':              'MAQUINA',
    'fecha':                'FECHA',
    'turno':                'TURNO',

    # Inyección
    'id_inyeccion':         'ID INYECCION',

    # Pulido
    'id_pulido':            'ID PULIDO',
    'hora_inicio':          'HORA INICIO',
    'hora_fin':             'HORA FIN',
    'cantidad_real':        'CANTIDAD REAL',

    # Ventas / Pedidos
    'documento':            'ID PEDIDO',
    'id_pedido':            'ID PEDIDO',
    'nro_pedido':           'Nro Pedido',
    'pedido_id':            'ID PEDIDO',
    'cliente':              'Cliente',
    'productos':            'PRODUCTOS',
    'cantidad':             'CANTIDAD',
    'total_ingresos':       'TOTAL VENTA',
    'precio_promedio':      'PRECIO PROMEDIO',
    'clasificacion':        'CLASIFICACION',
    'precio_unitario':      'PRECIO UNITARIO',
    'total':                'TOTAL',
    'nit':                  'NIT',
    'observaciones':        'OBSERVACIONES',

    # Clientes
    'nombre':               'NOMBRE',
    'identificacion':       'NIT',
    'nit':                  'NIT',
    'direccion':            'DIRECCION',
    'telefonos':            'TELEFONOS',
    'ciudad':               'CIUDAD',
    'email':                'EMAIL',
    'contacto':             'CONTACTO',


    # Asistencia
    'colaborador':          'COLABORADOR',
    'ingreso_real':         'INGRESO REAL',
    'salida_real':          'SALIDA REAL',
    'horas_ordinarias':     'HORAS ORDINARIAS',
    'horas_extras':         'HORAS EXTRAS',
    'registrado_por':       'REGISTRADO POR',
    'motivo':               'MOTIVO',
    'comentarios':          'COMENTARIOS',

    # Costos
    'referencia':           'REFERENCIA',
    'costo_total':          'COSTO TOTAL',
    'puntos_pieza':         'PUNTOS PIEZA',
    'tiempo_minutos':       'TIEMPO MINUTOS',

    # PNC
    'proceso':              'PROCESO',
    'accion':               'ACCION',
}


def _num(value):
    """Convierte Decimal/None a float para JSON-serializable."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class RepositoryService:
    """Servicio centralizado para acceso 100% SQL a PostgreSQL."""

    # ── HELPERS INTERNOS ──────────────────────────────────────

    def _map_to_legacy(self, data):
        """Traduce llaves SQL → nombres legacy de Sheets."""
        if data is None:
            return data

        def transform(row):
            new_row = {}
            for k, v in row.items():
                if k == 'id':
                    continue
                legacy_key = COLUMNS_TO_LEGACY.get(k, k.replace('_', ' ').upper())
                
                # Convertir Decimal a float para serialización JSON
                from decimal import Decimal
                if isinstance(v, Decimal):
                    v = _num(v)
                
                # Convertir Date a String ISO para el frontend
                import datetime
                if isinstance(v, (datetime.date, datetime.datetime)):
                    v = v.strftime('%Y-%m-%d')
                
                new_row[legacy_key] = v
            return new_row

        if isinstance(data, list):
            return [transform(r) for r in data]
        return transform(data)

    def _query(self, sql, params=None):
        """Ejecuta SQL crudo y retorna lista de dicts."""
        try:
            result = db.session.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings()]
        except Exception as e:
            db.session.rollback()
            logger.error(f"[RepositoryService._query] {e}")
            return []

    # ── GENÉRICO ──────────────────────────────────────────────

    def get_all(self, table_name, to_legacy=True):
        """Retorna todos los registros de una tabla."""
        try:
            result = db.session.execute(text(f'SELECT * FROM "{table_name}"'))
            data = [dict(row) for row in result.mappings()]
            return self._map_to_legacy(data) if to_legacy else data
        except Exception as e:
            db.session.rollback()
            logger.error(f"[get_all] {table_name}: {e}")
            return []

    def get_by_filters(self, table_name, filters, to_legacy=True):
        """Consulta con filtros simples col=valor."""
        try:
            if not filters:
                return self.get_all(table_name, to_legacy)
            where = " AND ".join([f'"{k}" = :{k}' for k in filters])
            result = db.session.execute(
                text(f'SELECT * FROM "{table_name}" WHERE {where}'), filters
            )
            data = [dict(row) for row in result.mappings()]
            return self._map_to_legacy(data) if to_legacy else data
        except Exception as e:
            db.session.rollback()
            logger.error(f"[get_by_filters] {table_name}: {e}")
            return []

    def insert_one(self, table_name, data):
        """Inserta un registro. Retorna True/False."""
        try:
            cols = ', '.join([f'"{k}"' for k in data])
            vals = ', '.join([f':{k}' for k in data])
            db.session.execute(text(f'INSERT INTO "{table_name}" ({cols}) VALUES ({vals})'), data)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"[insert_one] {table_name}: {e}")
            return False

    def update_one(self, table_name, filters, data):
        """Actualiza un registro por filtros."""
        try:
            set_clause   = ', '.join([f'"{k}" = :d_{k}' for k in data])
            where_clause = ' AND '.join([f'"{k}" = :f_{k}' for k in filters])
            params = {f'd_{k}': v for k, v in data.items()}
            params.update({f'f_{k}': v for k, v in filters.items()})
            db.session.execute(
                text(f'UPDATE "{table_name}" SET {set_clause} WHERE {where_clause}'), params
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"[update_one] {table_name}: {e}")
            return False

    # ── PRODUCTOS ─────────────────────────────────────────────

    def get_productos_all(self):
        """Retorna todos los productos con nombres legacy para el frontend."""
        from backend.models.sql_models import Producto
        try:
            rows = Producto.query.all()
            result = []
            for p in rows:
                result.append({
                    'CODIGO SISTEMA':       p.codigo_sistema or '',
                    'ID CODIGO':            p.id_codigo or '',
                    'DESCRIPCION':          p.descripcion or 'Sin descripción',
                    'PRECIO':               _num(p.precio),
                    'POR PULIR':            _num(p.por_pulir),
                    'P. TERMINADO':         _num(p.p_terminado),
                    'COMPROMETIDO':         _num(p.comprometido),
                    'PRODUCTO ENSAMBLADO':  _num(p.producto_ensamblado),
                    'STOCK MINIMO':         _num(p.stock_minimo),
                    'STOCK MAXIMO':         _num(p.stock_maximo),
                    'IMAGEN':               p.imagen or '',
                    'OEM':                  p.oem or '',
                    'MEDIDA':               p.medida or '',
                    'UBICACION':            p.ubicacion or '',
                    'DOLARES':              _num(p.dolares),
                })
            logger.info(f"[get_productos_all] {len(result)} productos retornados desde SQL.")
            return result
        except Exception as e:
            logger.error(f"[get_productos_all] {e}")
            return []

    def buscar_producto(self, codigo):
        """Busca un producto por código (normalizado). Retorna dict legacy o None."""
        from backend.models.sql_models import Producto
        from backend.utils.formatters import normalizar_codigo
        try:
            codigo_norm = normalizar_codigo(codigo)
            p = Producto.query.filter(
                (Producto.codigo_sistema == codigo_norm) |
                (Producto.id_codigo == codigo_norm)
            ).first()
            if not p:
                return None
            return {
                'CODIGO SISTEMA':       p.codigo_sistema or '',
                'ID CODIGO':            p.id_codigo or '',
                'DESCRIPCION':          p.descripcion or 'Sin descripción',
                'PRECIO':               _num(p.precio),
                'POR PULIR':            _num(p.por_pulir),
                'P. TERMINADO':         _num(p.p_terminado),
                'COMPROMETIDO':         _num(p.comprometido),
                'PRODUCTO ENSAMBLADO':  _num(p.producto_ensamblado),
                'STOCK MINIMO':         _num(p.stock_minimo),
                'IMAGEN':               p.imagen or '',
                '_id_sql':              p.id,
            }
        except Exception as e:
            logger.error(f"[buscar_producto] {codigo}: {e}")
            return None
    def buscar_por_termino_sql(self, termino, limit=50):
        """Busca productos por término (SQL ILIKE) en múltiples columnas."""
        from backend.models.sql_models import Producto
        try:
            t = f"%{termino}%"
            rows = Producto.query.filter(
                (Producto.codigo_sistema.ilike(t)) |
                (Producto.id_codigo.ilike(t)) |
                (Producto.descripcion.ilike(t)) |
                (Producto.oem.ilike(t))
            ).limit(limit).all()
            
            result = []
            for p in rows:
                result.append({
                    'CODIGO SISTEMA':       p.codigo_sistema or '',
                    'ID CODIGO':            p.id_codigo or '',
                    'DESCRIPCION':          p.descripcion or 'Sin descripción',
                    'PRECIO':               _num(p.precio),
                    'POR PULIR':            _num(p.por_pulir),
                    'P. TERMINADO':         _num(p.p_terminado),
                    'COMPROMETIDO':         _num(p.comprometido),
                    'PRODUCTO ENSAMBLADO':  _num(p.producto_ensamblado),
                    'STOCK MINIMO':         _num(p.stock_minimo),
                    'IMAGEN':               p.imagen or '',
                    'OEM':                  p.oem or '',
                    'UNIDAD':               'PZ' # Fallback legacy
                })
            return result
        except Exception as e:
            logger.error(f"[buscar_por_termino_sql] {termino}: {e}")
            return []

    def actualizar_stock_sql(self, codigo, campo_sql, nuevo_valor):
        """Actualiza un campo de stock en la tabla productos."""
        from backend.models.sql_models import Producto
        from backend.utils.formatters import normalizar_codigo
        try:
            codigo_norm = normalizar_codigo(codigo)
            p = Producto.query.filter(
                (Producto.codigo_sistema == codigo_norm) |
                (Producto.id_codigo == codigo_norm)
            ).first()
            if not p:
                return False
            setattr(p, campo_sql, nuevo_valor)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"[actualizar_stock_sql] {e}")
            return False

    # ── CLIENTES ──────────────────────────────────────────────

    def get_clientes_all(self):
        """Retorna todos los clientes desde SQL con llaves en minúscula para el frontend."""
        try:
            # Query flexible
            rows = db.session.execute(text('SELECT * FROM db_clientes')).mappings().all()
            
            def _get(row, candidates):
                for c in candidates:
                    if c in row and row[c]:
                        return str(row[c]).strip()
                return ''
            
            result = []
            for row in rows:
                nombre = _get(row, ['nombre', 'cliente', 'razon_social', 'nombre_empresa'])
                if not nombre:
                    continue
                result.append({
                    'nombre':    nombre,
                    'nit':       _get(row, ['nit', 'identificacion', 'nit_empresa']),
                    'direccion': _get(row, ['direccion']),
                    'ciudad':    _get(row, ['ciudad']),
                    'telefono':  _get(row, ['telefonos', 'telefono', 'celular']),
                    'email':     _get(row, ['email', 'correo', 'e_mail']),
                })
            logger.info(f"[get_clientes_all] {len(result)} clientes cargados con mapeo corecto.")
            return result
        except Exception as e:
            db.session.rollback()
            logger.error(f"[get_clientes_all] {e}")
            return []

    def get_pedidos_pendientes_sql(self):
        try:
            sql = """
                SELECT 
                    p.id_pedido, 
                    p.fecha, 
                    p.hora,
                    p.estado, 
                    p.delegado_a,
                    p.vendedor,
                    COALESCE(p.cliente, c.nombre, 'Cliente Desconocido') as nombre_cliente,
                    COALESCE(p.direccion, c.direccion, 'S/D - S/C') as direccion_cliente,
                    COALESCE(p.ciudad, c.ciudad, '') as ciudad_cliente,
                    p.id_codigo, 
                    p.descripcion, 
                    p.cantidad, 
                    p.total,
                    p.observaciones,
                    p.progreso,
                    p.progreso_despacho,
                    p.cant_alistada
                FROM db_pedidos p
                LEFT JOIN (
                    SELECT DISTINCT ON (identificacion) identificacion, nombre, direccion, ciudad 
                    FROM db_clientes
                ) c ON p.nit = c.identificacion
                WHERE p.estado NOT IN ('COMPLETADO', 'DESPACHADO', 'ENTREGADO', 'FACTURADO', 'CANCELADO')
                  AND p.estado IS NOT NULL
                ORDER BY p.fecha ASC, p.id_pedido ASC
            """
            rows = db.session.execute(text(sql)).mappings().all()
            
            agrupados = {}
            for r in rows:
                nro_pedido = r['id_pedido'] # CLAVE PARA AGRUPAR (Ej: PED-9798)
                
                if not nro_pedido:
                    continue
                    
                if nro_pedido not in agrupados:
                    # Lógica inteligente para formatear la dirección
                    ciudad = str(r['ciudad_cliente']).strip()
                    direccion = str(r['direccion_cliente']).strip()

                    # Si la ciudad es 'S/C', o si el nombre de la ciudad ya está escrito dentro de la dirección, no la concatenamos.
                    if ciudad and ciudad.upper() != 'S/C' and ciudad.upper() not in direccion.upper():
                        dir_completa = f"{direccion} - {ciudad}"
                    else:
                        dir_completa = direccion

                    # Limpieza extra
                    dir_completa = dir_completa.replace(' - S/C', '').replace('- S/C', '').strip(' -')
                    
                    agrupados[nro_pedido] = {
                        "id": nro_pedido,
                        "id_pedido": nro_pedido,
                        "nro_pedido": nro_pedido,
                        "fecha": str(r['fecha'])[:10] if r['fecha'] else '',
                        "hora": str(r['hora'] or '').strip(),
                        "cliente": r['nombre_cliente'],
                        "direccion": dir_completa,
                        "vendedor": r['vendedor'] or '',
                        "estado": r['estado'],
                        "delegado_a": r['delegado_a'] or '',
                        "observaciones": r['observaciones'] or '',
                        "progreso": r['progreso'] or '0',
                        "progreso_despacho": r['progreso_despacho'] or '0',
                        "productos": []
                    }
                else:
                    # Robustez: Si la primera fila no tenía hora pero esta sí, capturarla
                    if not agrupados[nro_pedido]["hora"] and r['hora']:
                        agrupados[nro_pedido]["hora"] = str(r['hora']).strip()
                
                # Función segura de limpieza para el dashboard
                def _safe_float(val):
                    if not val: return 0
                    s = str(val).replace('$', '').replace(',', '').strip()
                    try: return int(float(s))
                    except: return 0

                # Lógica de visualización única (Evitar duplicados incluso si hay error en DB)
                def _norm_code(c):
                    return str(c or '').strip().upper().replace('FR-', '')

                codigo_actual = str(r['id_codigo'] or '').strip().upper()
                codigo_norm = _norm_code(codigo_actual)
                
                # Buscar si este producto ya fue procesado para este pedido (Verdad Única)
                ya_existe = any(_norm_code(p['codigo']) == codigo_norm for p in agrupados[nro_pedido]["productos"])
                
                if not ya_existe:
                    # Solo agregamos si es la primera vez que lo vemos en este pedido
                    cant_ali = _safe_float(r['cant_alistada'])
                    agrupados[nro_pedido]["productos"].append({
                        "id_sql": r.get('id_sql'), # Incluir para trazabilidad
                        "codigo": codigo_actual,
                        "descripcion": r['descripcion'] or '',
                        "cantidad": _safe_float(r['cantidad']),
                        "total": _safe_float(r['total']),
                        "cant_alistada": cant_ali,
                        "cant_lista": cant_ali
                    })
                else:
                    # Si ya existe, lo ignoramos para no duplicar cantidades en pantalla
                    pass
            
            return list(agrupados.values())
        except Exception as e:
            db.session.rollback()
            logger.error(f"[get_pedidos_pendientes_sql] ERROR SQL: {e}")
            return []


    # ── DASHBOARD / KPIs ──────────────────────────────────────

    def get_dashboard_kpis(self, desde=None, hasta=None):
        """
        Calcula KPIs de producción 100% SQL-Native con CAST ROBUSTO.
        Resistente a strings inválidos como '30/12/1899' en columnas TEXT.
        """
        try:
            params = {'desde': desde, 'hasta': hasta}
            filt_iny = " WHERE fecha_inicia BETWEEN :desde AND :hasta" if desde and hasta else " WHERE 1=1"
            filt_gen = " WHERE fecha BETWEEN :desde AND :hasta" if desde and hasta else " WHERE 1=1"

            # Helper para SQL de casting robusto solicitado por el usuario
            def _user_cast(col):
                return f"COALESCE(NULLIF(regexp_replace({col}::text, '[^0-9.]', '', 'g'), ''), '0')::NUMERIC"

            # Helper para moneda (trata $ y comas/puntos)
            def _sql_cast_num(col):
                return f"COALESCE(NULLIF(regexp_replace(regexp_replace({col}::text, '[$. ]', '', 'g'), ',', '.', 'g'), '')::NUMERIC, 0)"

            # --- Inyección (db_pnc_inyeccion) ---
            # Cantidad OK viene de la tabla principal
            sql_iny_ok = f"SELECT SUM({_user_cast('cantidad_real')}) FROM db_inyeccion {filt_iny}"
            # Cantidad PNC viene de la tabla de detalle (NUEVA db_pnc_inyeccion)
            sql_iny_pnc = f"""
                SELECT SUM({_user_cast('p.cantidad')})
                FROM db_pnc_inyeccion p
                LEFT JOIN db_inyeccion i ON p.id_inyeccion = i.id_inyeccion
                {filt_iny.replace('WHERE ', 'WHERE i.') if 'WHERE' in filt_iny else 'WHERE 1=1'}
            """
            r_iny_ok = db.session.execute(text(sql_iny_ok), params).fetchone()
            r_iny_pnc = db.session.execute(text(sql_iny_pnc), params).fetchone()
            iny_ok = _num(r_iny_ok[0]) if r_iny_ok else 0
            iny_pnc = _num(r_iny_pnc[0]) if r_iny_pnc else 0
            
            # --- Pulido (db_pnc_pulido) ---
            sql_pul_ok = f"SELECT SUM({_user_cast('cantidad_real')}) FROM db_pulido {filt_gen}"
            sql_pul_pnc = f"""
                SELECT SUM({_user_cast('p.cantidad')})
                FROM db_pnc_pulido p
                LEFT JOIN db_pulido d ON p.id_pulido = d.id_pulido
                {filt_gen.replace('WHERE ', 'WHERE d.') if 'WHERE' in filt_gen else 'WHERE 1=1'}
            """
            r_pul_ok = db.session.execute(text(sql_pul_ok), params).fetchone()
            r_pul_pnc = db.session.execute(text(sql_pul_pnc), params).fetchone()
            pul_ok = _num(r_pul_ok[0]) if r_pul_ok else 0
            pul_pnc = _num(r_pul_pnc[0]) if r_pul_pnc else 0

            # --- Ensamble (db_pnc_ensamble) ---
            sql_ens_ok = f"SELECT SUM({_user_cast('cantidad')}) FROM db_ensambles {filt_gen}"
            sql_ens_pnc = f"""
                SELECT SUM({_user_cast('p.cantidad')})
                FROM db_pnc_ensamble p
                LEFT JOIN db_ensambles d ON p.id_ensamble = d.id_ensamble
                {filt_gen.replace('WHERE ', 'WHERE d.') if 'WHERE' in filt_gen else 'WHERE 1=1'}
            """
            r_ens_ok = db.session.execute(text(sql_ens_ok), params).fetchone()
            r_ens_pnc = db.session.execute(text(sql_ens_pnc), params).fetchone()
            ens_ok = _num(r_ens_ok[0]) if r_ens_ok else 0
            ens_pnc = _num(r_ens_pnc[0]) if r_ens_pnc else 0

            # --- Ventas (db_ventas) ---
            sql_ven = f"SELECT COALESCE(SUM({_sql_cast_num('total_ingresos')}), 0) FROM db_ventas {filt_gen}"
            r_ven = db.session.execute(text(sql_ven), params).fetchone()
            ventas_totales = _num(r_ven[0])

            # --- Pedidos (db_ventas con clasificacion=pedido) ---
            sql_ped = f"SELECT COALESCE(SUM({_sql_cast_num('total_ingresos')}), 0) FROM db_ventas {filt_gen} AND clasificacion ILIKE '%pedido%'"
            r_ped = db.session.execute(text(sql_ped), params).fetchone()
            pedidos_sum = _num(r_ped[0])

            # --- Pérdida en Dinero ---
            perdida_dinero = self.get_perdida_economica_scrap(desde, hasta)

            # --- Mezcla ---
            sql_mez = f"SELECT SUM({_user_cast('virgen_kg')} + {_user_cast('molido_kg')}) FROM db_mezcla {filt_gen}"
            r_mez = db.session.execute(text(sql_mez), params).fetchone()
            mezcla_total = _num(r_mez[0])

            return {
                'inyeccion_ok':  iny_ok,
                'inyeccion_pnc': iny_pnc,
                'pulido_ok':     pul_ok,
                'pulido_pnc':    pul_pnc,
                'ensambles_ok':  ens_ok,
                'ensamble_pnc':  ens_pnc,
                'ventas_totales': ventas_totales,
                'pedidos_solicitados': pedidos_sum,
                'mezcla_total_kg': mezcla_total,
                'scrap_total':   iny_pnc + pul_pnc + ens_pnc,
                'perdida_calidad_dinero': perdida_dinero
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"[get_dashboard_kpis] {e}")
            return {
                'inyeccion_ok': 0, 'inyeccion_pnc': 0,
                'pulido_ok': 0, 'pulido_pnc': 0,
                'ensambles_ok': 0, 'ensamble_pnc': 0,
                'scrap_total': 0, 'ventas_totales': 0,
                'pedidos_solicitados': 0,
                'perdida_calidad_dinero': 0,
                'scrap_detalle': {'inyeccion': 0, 'pulido': 0, 'ensamble': 0, 'almacen': 0}
            }



    def get_ranking_operarios_inyeccion(self, desde=None, hasta=None, limit=20):
        """Ranking de operarios de inyección (SQL-Native) con CAST ROBUSTO."""
        try:
            # Ranking resiliente a basura y basado en detalle de scrap
            sql = f"""
                SELECT 
                    i.responsable, 
                    SUM(COALESCE(NULLIF(regexp_replace(i.cantidad_real::text, '[^0-9]', '', 'g'), ''), '0')::INTEGER) as total,
                    COALESCE(pnc.total_pnc, 0) as scrap
                FROM db_inyeccion i
                LEFT JOIN (
                    SELECT id_inyeccion, 
                           SUM(COALESCE(NULLIF(regexp_replace(cantidad::text, '[^0-9.]', '', 'g'), ''), '0')::NUMERIC) as total_pnc
                    FROM db_pnc_inyeccion
                    GROUP BY id_inyeccion
                ) pnc ON i.id_inyeccion = pnc.id_inyeccion
                WHERE 1=1
            """
            params = {'lim': limit}
            if desde and hasta:
                sql += ' AND i.fecha_inicia BETWEEN :desde AND :hasta'
                params['desde'] = desde
                params['hasta'] = hasta
            sql += ' GROUP BY i.responsable, pnc.total_pnc ORDER BY total DESC LIMIT :lim'

            rows = db.session.execute(text(sql), params).fetchall()
            return [{'nombre': r[0] or '?', 'valor': _num(r[1]), 'pnc': _num(r[2])} for r in rows]
        except Exception as e:
            db.session.rollback()
            logger.error(f"[get_ranking_operarios_inyeccion] {e}")
            return []

    def get_ranking_maquinas(self, desde=None, hasta=None):
        """Distribución por máquina (SQL-Native) con CAST ROBUSTO."""
        try:
            def _cast(col):
                return f"COALESCE(NULLIF(regexp_replace({col}::text, '[^0-9]', '', 'g'), '')::INTEGER, 0)"

            sql = f"SELECT maquina, SUM({_cast('cantidad_real')}) as total FROM db_inyeccion WHERE 1=1"
            params = {}
            if desde and hasta:
                sql += ' AND fecha_inicia BETWEEN :desde AND :hasta'
                params['desde'] = desde
                params['hasta'] = hasta
            sql += ' GROUP BY maquina ORDER BY total DESC'

            rows = db.session.execute(text(sql), params).fetchall()
            return [{'maquina': r[0] or '?', 'valor': _num(r[1])} for r in rows]
        except Exception as e:
            db.session.rollback()
            logger.error(f"[get_ranking_maquinas] {e}")
            return []

    def get_ranking_operarios_pulido(self, desde=None, hasta=None, limit=20):
        """Ranking extendido de pulido (SQL-Native) con Puntos y Eficiencia."""
        try:
            params = {'lim': limit}
            filt = ""
            if desde and hasta:
                filt = " AND p.fecha BETWEEN :desde AND :hasta"
                params['desde'] = desde
                params['hasta'] = hasta

            sql = f"""
                SELECT 
                    p.responsable,
                    COALESCE(SUM(NULLIF(regexp_replace(p.cantidad_real::text, '[^0-9]', '', 'g'), '')::INTEGER), 0) as buenas,
                    COALESCE(SUM(NULLIF(regexp_replace(p.pnc_pulido::text, '[^0-9]', '', 'g'), '')::INTEGER), 0) as pnc,
                    COALESCE(SUM(NULLIF(regexp_replace(p.tiempo_total_minutos::text, '[^0-9]', '', 'g'), '')::INTEGER), 0) as tiempo_real,
                    COALESCE(SUM(NULLIF(regexp_replace(p.cantidad_real::text, '[^0-9]', '', 'g'), '')::INTEGER * COALESCE(NULLIF(regexp_replace(REPLACE(c.puntos_por_pieza::text, ',', '.'), '[^0-9.]', '', 'g'), ''), '0')::NUMERIC), 0) as puntos,
                    COALESCE(SUM(NULLIF(regexp_replace(p.cantidad_real::text, '[^0-9]', '', 'g'), '')::INTEGER * COALESCE(NULLIF(regexp_replace(REPLACE(c.tiempo_estandar::text, ',', '.'), '[^0-9.]', '', 'g'), ''), '0')::NUMERIC), 0) as tiempo_std
                FROM db_pulido p
                LEFT JOIN db_costos c ON TRIM(p.codigo::TEXT) = TRIM(c.referencia::TEXT)
                WHERE 1=1 {filt}
                GROUP BY p.responsable
                ORDER BY puntos DESC
                LIMIT :lim
            """
            rows = db.session.execute(text(sql), params).fetchall()
            
            resultado = []
            for r in rows:
                nombre = r[0] or '?'
                buenas = int(r[1])
                pnc = int(r[2])
                t_real = int(r[3])
                puntos = int(r[4])
                t_std = float(r[5])
                
                # Eficiencia = (Tiempo Standard / Tiempo Real) * 100
                eficiencia = round((t_std / t_real * 100), 1) if t_real > 0 else 0
                
                resultado.append({
                    'nombre': nombre,
                    'valor': buenas,
                    'pnc': pnc,
                    'puntos': puntos,
                    'eficiencia': eficiencia,
                    'minutos': t_real
                })
            return resultado
        except Exception as e:
            db.session.rollback()
            logger.error(f"[get_ranking_operarios_pulido] {e}")
            return []

    # ── NUEVAS FUNCIONES SQL-NATIVE ──────────────────────────

    def get_stock_critico_sql(self):
        """Retorna productos cuyo stock está por debajo del mínimo definido."""
        try:
            sql = """
                SELECT codigo_sistema, descripcion, stock_minimo, 
                       (COALESCE(p_terminado::NUMERIC, 0) + COALESCE(stock_bodega::NUMERIC, 0)) as stock_actual
                FROM db_productos
                WHERE (COALESCE(p_terminado::NUMERIC, 0) + COALESCE(stock_bodega::NUMERIC, 0)) < COALESCE(stock_minimo::NUMERIC, 0)
                ORDER BY stock_minimo::NUMERIC DESC
            """
            rows = db.session.execute(text(sql)).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_stock_critico_sql] {e}")
            return []

    def get_perdida_economica_scrap(self, desde=None, hasta=None):
        """
        Calcula la pérdida financiera por scrap usando id_codigo en todas las tablas de detalle.
        """
        try:
            params = {'desde': desde, 'hasta': hasta}
            filt_iny = " WHERE i.fecha_inicia BETWEEN :desde AND :hasta" if desde and hasta else " WHERE 1=1"
            filt_pul = " WHERE d.fecha BETWEEN :desde AND :hasta" if desde and hasta else " WHERE 1=1"
            filt_ens = " WHERE e.fecha BETWEEN :desde AND :hasta" if desde and hasta else " WHERE 1=1"

            # Cast ultra-robusto: Comas a puntos + Limpieza regex
            def _user_cast(col):
                return f"COALESCE(NULLIF(regexp_replace(REPLACE({col}::text, ',', '.'), '[^0-9.]', '', 'g'), ''), '0')::NUMERIC"

            sql = f"""
                WITH unique_costs AS (
                    SELECT TRIM(referencia::TEXT) as ref_costo, MAX({_user_cast('costo_total')}) as cost
                    FROM db_costos
                    GROUP BY TRIM(referencia::TEXT)
                ),
                scrap_unificado AS (
                    -- Bloque INYECCIÓN: Usa id_codigo
                    SELECT 
                        TRIM(REPLACE(p.id_codigo::TEXT, 'FR-', '')) as ref, 
                        SUM({_user_cast('p.cantidad')}) as qty 
                    FROM db_pnc_inyeccion p
                    LEFT JOIN db_inyeccion i ON p.id_inyeccion = i.id_inyeccion
                    {filt_iny}
                    GROUP BY TRIM(REPLACE(p.id_codigo::TEXT, 'FR-', ''))
                    
                    UNION ALL
                    
                    -- Bloque PULIDO: Usa p.codigo (Mapeo DBeaver)
                    SELECT 
                        TRIM(REPLACE(p.codigo::TEXT, 'FR-', '')) as ref, 
                        SUM({_user_cast('p.cantidad')}) as qty 
                    FROM db_pnc_pulido p
                    LEFT JOIN db_pulido d ON p.id_pulido = d.id_pulido
                    {filt_pul}
                    GROUP BY TRIM(REPLACE(p.codigo::TEXT, 'FR-', ''))
                    
                    UNION ALL
                    
                    -- Bloque ENSAMBLE: Usa p.id_codigo (Mapeo DBeaver)
                    SELECT 
                        TRIM(REPLACE(p.id_codigo::TEXT, 'FR-', '')) as ref, 
                        SUM({_user_cast('p.cantidad')}) as qty 
                    FROM db_pnc_ensamble p
                    LEFT JOIN db_ensambles e ON p.id_ensamble = e.id_ensamble
                    {filt_ens}
                    GROUP BY TRIM(REPLACE(p.id_codigo::TEXT, 'FR-', ''))
                )
                SELECT COALESCE(SUM(COALESCE(s.qty, 0) * COALESCE(c.cost, 0)), 0)
                FROM scrap_unificado s
                JOIN unique_costs c ON s.ref = c.ref_costo
                WHERE s.qty > 0
            """
            logger.debug(f"[SQL_DEBUG] get_perdida_economica_scrap (FINAL FIXED): {sql}")
            
            res = db.session.execute(text(sql), params).fetchone()
            total = _num(res[0]) if res and res[0] else 0
            return total
        except Exception as e:
            logger.error(f"[get_perdida_economica_scrap] ERROR: {e}")
            return 0

    def get_rendimiento_mensual_sql(self, start_date=None, end_date=None):
        """
        Calcula el rendimiento mensual (comparativo 2025 vs 2026) 100% SQL-Native.
        Resistente a strings de moneda sucios.
        """
        try:
            meses_map = {1:'ene',2:'feb',3:'mar',4:'abr',5:'may',6:'jun',7:'jul',8:'ago',9:'sep',10:'oct',11:'nov',12:'dic'}
            
            def _sql_cast_num(col):
                return f"COALESCE(NULLIF(regexp_replace(REPLACE({col}::text, ',', '.'), '[^0-9.]', '', 'g'), ''), '0')::NUMERIC"

            # Si el usuario pide nombres, lo incluimos en el WHERE o GROUP BY si fuera necesario, 
            # pero el gráfico de rendimiento usualmente es global por mes.
            # Aseguramos el uso de 'nombres' si hubiera filtros por cliente en el futuro.
            sql = f"""
                SELECT 
                    EXTRACT(MONTH FROM fecha)::INTEGER as mes,
                    EXTRACT(YEAR FROM fecha)::INTEGER as ano,
                    SUM(COALESCE(CASE WHEN clasificacion = 'Ventas' THEN {_sql_cast_num('total_ingresos')} ELSE 0 END, 0)) as ventas,
                    SUM(COALESCE(CASE WHEN clasificacion = 'Pedidos' THEN {_sql_cast_num('total_ingresos')} ELSE 0 END, 0)) as pedidos,
                    SUM(COALESCE(CASE WHEN clasificacion = 'Ventas' THEN {_sql_cast_num('cantidad')} ELSE 0 END, 0)) as v_unds,
                    SUM(COALESCE(CASE WHEN clasificacion = 'Pedidos' THEN {_sql_cast_num('cantidad')} ELSE 0 END, 0)) as p_unds
                FROM db_ventas
                WHERE EXTRACT(YEAR FROM fecha) IN (2025, 2026)
                GROUP BY ano, mes
                ORDER BY ano, mes
            """
            rows = db.session.execute(text(sql)).fetchall()
            logger.info(f"[get_rendimiento_mensual_sql] Filas obtenidas: {len(rows)}")
            
            # Organizar por mes (1-12)
            data_map = {m: {
                "mes": meses_map[m],
                "actual_dinero": 0, "actual_pedidos": 0,
                "prev_dinero": 0, "prev_pedidos": 0,
                "actual_unidades": 0, "actual_pedidos_unidades": 0,
                "prev_unidades": 0, "prev_pedidos_unidades": 0,
                "ventas_dinero": 0, "pedidos_dinero": 0,
                "ventas_qty": 0, "pedidos_qty": 0
            } for m in range(1, 13)}

            for r in rows:
                m, y = r[0], r[1]
                if not m or m not in data_map: continue
                v, p, v_u, p_u = _num(r[2]), _num(r[3]), _num(r[4]), _num(r[5])
                if y == 2026:
                    data_map[m].update({
                        "actual_dinero": v, "actual_pedidos": p,
                        "actual_unidades": v_u, "actual_pedidos_unidades": p_u,
                        "ventas_dinero": v, "pedidos_dinero": p,
                        "ventas_qty": v_u, "pedidos_qty": p_u
                    })
                else:
                    data_map[m].update({
                        "prev_dinero": v, "prev_pedidos": p,
                        "prev_unidades": v_u, "prev_pedidos_unidades": p_u
                    })
            
            return list(data_map.values())
        except Exception as e:
            logger.error(f"[get_rendimiento_mensual_sql] {e}")
            return []

    def get_admin_dashboard_metrics_sql(self, start_date=None, end_date=None):
        """Encapsula todas las métricas de Jefatura (SQL-Native) coincidiendo con frontend."""
        try:
            params = {'start': start_date, 'end': end_date}
            filt = " WHERE fecha BETWEEN :start AND :end" if start_date and end_date else " WHERE 1=1"
            
            def _sql_cast_num(col):
                return f"COALESCE(NULLIF(regexp_replace(REPLACE({col}::text, ',', '.'), '[^0-9.]', '', 'g'), ''), '0')::NUMERIC"

            # 1. Top Productos (Dinero)
            sql_top_d = f"""
                SELECT productos, SUM({_sql_cast_num('total_ingresos')}) as total
                FROM db_ventas {filt} AND clasificacion = 'Ventas'
                GROUP BY productos ORDER BY total DESC LIMIT 10
            """
            top_d = db.session.execute(text(sql_top_d), params).fetchall()
            
            # 2. Peores Productos (Dinero)
            sql_peor_d = f"""
                SELECT productos, SUM({_sql_cast_num('total_ingresos')}) as total
                FROM db_ventas {filt} AND clasificacion = 'Ventas'
                GROUP BY productos ORDER BY total ASC LIMIT 10
            """
            peor_d = db.session.execute(text(sql_peor_d), params).fetchall()

            # 3. Incumplimiento (Backorder) - SQL Native con Impacto Financiero
            # Se elimina el filtro de fecha temporalmente para validar volumen
            sql_inc = f"""
                WITH unique_costs AS (
                    SELECT 
                        TRIM(UPPER(referencia::TEXT)) as ref, 
                        MAX(COALESCE(NULLIF(regexp_replace(REPLACE(costo_total::text, ',', '.'), '[^0-9.]', '', 'g'), ''), '0')::NUMERIC) as cost
                    FROM db_costos
                    WHERE referencia IS NOT NULL
                    GROUP BY TRIM(UPPER(referencia::TEXT))
                ),
                totals AS (
                    SELECT 
                        nombres,
                        productos as producto,
                        TRIM(split_part(REPLACE(productos::TEXT, 'FR-', ''), ' ', 1)) as ref_final,
                        SUM(CASE WHEN clasificacion = 'Pedidos' THEN {_sql_cast_num('cantidad')} ELSE 0 END) as p_qty,
                        SUM(CASE WHEN clasificacion = 'Ventas' THEN {_sql_cast_num('cantidad')} ELSE 0 END) as v_qty
                    FROM db_ventas
                    GROUP BY nombres, productos, 3
                )
                SELECT 
                    t.nombres,
                    t.producto, 
                    t.ref_final,
                    COALESCE(t.p_qty, 0) as p_qty, 
                    COALESCE(t.v_qty, 0) as v_qty, 
                    (COALESCE(t.p_qty, 0) - COALESCE(t.v_qty, 0)) as diff_qty,
                    COALESCE((COALESCE(t.p_qty, 0) - COALESCE(t.v_qty, 0)) * COALESCE(c.cost, 0), 0) as diff_money
                FROM totals t
                LEFT JOIN unique_costs c ON t.ref_final = c.ref
                WHERE (COALESCE(t.p_qty, 0) - COALESCE(t.v_qty, 0)) > 0
                ORDER BY diff_money DESC 
                LIMIT 50
            """
            back_rows = db.session.execute(text(sql_inc), params).fetchall()

            # --- DEBUG LOGS (Instrucción del usuario) ---
            for i, r in enumerate(back_rows[:5]):
                logger.info(f"DEBUG BACKORDER: Producto: [{r[1]}], Codigo_Limpio: [{r[2]}], Costo Encontrado: [{r[6]}]")
            
            # Mapeo a listas específicas para el Dashboard Admin
            inc_unidades = []
            inc_dinero = []
            backorder_list = []
            
            for r in back_rows:
                # r tiene 7 columnas: cli, prod, ref_fin, p_qty, v_qty, diff_q, diff_m
                cli, prod, ref_fin, p_qty, v_qty, diff_q, diff_m = r
                inc_unidades.append({"cliente": cli, "producto": prod, "unidades_fallidas": _num(diff_q)})
                inc_dinero.append({"cliente": cli, "producto": prod, "dinero_perdido": _num(diff_m)})
                backorder_list.append({
                    "producto": prod, 
                    "cliente": cli,
                    "clean_ref": ref_fin,
                    "pedidos_qty": _num(p_qty), 
                    "ventas_qty": _num(v_qty), 
                    "pendiente_qty": _num(diff_q),
                    "pendiente_money": _num(diff_m)
                })

            # Obtener Scrap para el resumen
            scrap_money = self.get_perdida_economica_scrap(start_date, end_date)

            return {
                "mensual": self.get_rendimiento_mensual_sql(start_date, end_date),
                "top_productos": [{"producto": r[0], "ventas_dinero": _num(r[1])} for r in top_d],
                "peores_productos": [{"producto": r[0], "ventas_dinero": _num(r[1])} for r in peor_d],
                "backorder": backorder_list,
                "incumplimiento_dinero": inc_dinero,
                "incumplimiento_unidades": inc_unidades,
                "resumen_unidades": 0, # Unidades no calculadas aquí, se mantienen en 0 por ahora
                "resumen_dinero": scrap_money
            }
        except Exception as e:
            logger.error(f"[get_admin_dashboard_metrics_sql] {e}")
            return {
                "mensual": [], 
                "top_productos": [], 
                "peores_productos": [],
                "backorder": [], 
                "incumplimiento_dinero": [], 
                "incumplimiento_unidades": [],
                "resumen_unidades": 0,
                "resumen_dinero": 0
            }


    # ── HISTORIAL / TRAZABILIDAD ───────────────────────────────

    def get_historial_inyeccion(self, codigo):
        """Retorna historial de inyección para un código."""
        from backend.models.sql_models import ProduccionInyeccion
        from backend.utils.formatters import normalizar_codigo
        try:
            cod = normalizar_codigo(codigo)
            rows = ProduccionInyeccion.query.filter_by(codigo_sistema=cod).all()
            return [{
                'FECHA':          r.fecha or '',
                'ID INYECCION':   r.id_inyeccion or '',
                'RESPONSABLE':    r.responsable or '',
                'MAQUINA':        r.maquina or '',
                'CANTIDAD REAL':  _num(r.cantidad_real),
                'PNC':            _num(r.pnc),
                'ESTADO':         r.estado or '',
            } for r in rows]
        except Exception as e:
            logger.error(f"[get_historial_inyeccion] {e}")
            return []

    def get_historial_pulido(self, codigo):
        """Retorna historial de pulido para un código."""
        from backend.models.sql_models import ProduccionPulido
        from backend.utils.formatters import normalizar_codigo
        try:
            cod = normalizar_codigo(codigo)
            rows = ProduccionPulido.query.filter_by(codigo=cod).all()
            return [{
                'FECHA':         r.fecha or '',
                'ID PULIDO':     r.id_pulido or '',
                'RESPONSABLE':   r.responsable or '',
                'CANTIDAD REAL': _num(r.cantidad_real),
                'PNC':           _num(r.pnc),
                'HORA INICIO':   r.hora_inicio or '',
                'HORA FIN':      r.hora_fin or '',
            } for r in rows]
        except Exception as e:
            logger.error(f"[get_historial_pulido] {e}")
            return []

    def get_ventas_por_codigo(self, codigo):
        """Retorna ventas donde el código aparece en la columna 'productos'."""
        from backend.models.sql_models import RawVentas
        from backend.utils.formatters import normalizar_codigo
        try:
            cod = normalizar_codigo(codigo)
            rows = RawVentas.query.filter(RawVentas.productos.ilike(f'%{cod}%')).all()
            return [{
                'FECHA':          r.fecha or '',
                'DOCUMENTO':      r.documento or '',
                'CLIENTE':        r.cliente or '',
                'PRODUCTOS':      r.productos or '',
                'CANTIDAD':       _num(r.cantidad),
                'TOTAL VENTA':    _num(r.total_ingresos),
            } for r in rows]
        except Exception as e:
            logger.error(f"[get_ventas_por_codigo] {e}")
            return []

    def get_backorder_detalle_por_cliente_sql(self, cliente_nombre, start_date=None, end_date=None):
        """Retorna el detalle de productos pendientes para un cliente específico con impacto financiero."""
        from sqlalchemy import text
        from backend.core.sql_database import db
        
        def _sql_cast_num(col):
            return f"COALESCE(NULLIF(regexp_replace(REPLACE({col}::text, ',', '.'), '[^0-9.]', '', 'g'), ''), '0')::NUMERIC"
        
        filt = ""
        params = {"cliente": f"%{cliente_nombre}%"}
        if start_date and end_date:
            filt = "AND fecha BETWEEN :sd AND :ed"
            params["sd"] = start_date
            params["ed"] = end_date

        sql = text(f"""
            WITH totals AS (
                SELECT 
                    productos as full_desc,
                    TRIM(split_part(REPLACE(productos::TEXT, 'FR-', ''), ' ', 1)) as ref_final,
                    SUM(CASE WHEN clasificacion = 'Pedidos' THEN {_sql_cast_num('cantidad')} ELSE 0 END) as p_qty,
                    SUM(CASE WHEN clasificacion = 'Ventas' THEN {_sql_cast_num('cantidad')} ELSE 0 END) as v_qty
                FROM db_ventas
                WHERE nombres ILIKE :cliente {filt}
                GROUP BY productos
            ),
            unique_costs AS (
                SELECT referencia, MAX({_sql_cast_num('costo_total')}) as cost
                FROM db_costos
                GROUP BY referencia
            )
            SELECT 
                t.full_desc,
                t.ref_final,
                t.p_qty,
                t.v_qty,
                (t.p_qty - t.v_qty) as diff_qty,
                COALESCE(c.cost, 0) as unit_cost
            FROM totals t
            LEFT JOIN unique_costs c ON t.ref_final = c.referencia
            WHERE (t.p_qty - t.v_qty) > 0
            ORDER BY (t.p_qty - t.v_qty) DESC
        """)
        
        try:
            results = db.session.execute(sql, params).fetchall()
            detalle = []
            for r in results:
                diff = _num(r[4])
                cost = _num(r[5])
                detalle.append({
                    "descripcion": r[0],
                    "referencia": r[1],
                    "pedidos": _num(r[2]),
                    "ventas": _num(r[3]),
                    "pendiente": diff,
                    "impacto": diff * cost
                })
            return detalle
        except Exception as e:
            logger.error(f"[get_backorder_detalle_por_cliente_sql] {e}")
            return []


# Instancia global única
repository_service = RepositoryService()
