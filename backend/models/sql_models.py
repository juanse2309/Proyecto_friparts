"""
sql_models.py — Modelos SQLAlchemy 100% SQL-First
Tablas planas, sin relationships, sin ForeignKey.
extend_existing=True previene errores de Mapper al recargar el módulo.
"""
from datetime import datetime
import uuid
import time
import random
from sqlalchemy.orm import validates
from backend.core.sql_database import db
from backend.utils.formatters import normalizar_codigo_sin_prefijo, preservar_o_normalizar_prefijo
from backend.utils.time_utils import get_colombia_time


class Producto(db.Model):
    __tablename__ = 'db_productos'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # unique=True: soporta INSERT ... ON CONFLICT(codigo_sistema) para el UPSERT
    # masivo de World Office (ver ProductoRepository.upsert_productos_wo). La
    # constraint real en Postgres (uq_productos_codigo_sistema) la crea
    # scratch/migrar_productos_unique.py -- este flag solo refleja el estado
    # esperado del esquema, no la aplica por si solo.
    codigo_sistema  = db.Column(db.String(50),  unique=True, index=True, nullable=True)
    id_codigo       = db.Column(db.String(50),  index=True, nullable=True)
    descripcion     = db.Column(db.String(500), nullable=True)
    precio          = db.Column(db.Numeric(18, 2), default=0)
    por_pulir       = db.Column(db.Numeric(18, 2), default=0)
    p_terminado     = db.Column(db.Numeric(18, 2), default=0)
    comprometido    = db.Column(db.Numeric(18, 2), default=0)
    producto_ensamblado = db.Column(db.Numeric(18, 2), default=0)
    stock_minimo    = db.Column(db.Numeric(18, 2), default=10)
    stock_maximo    = db.Column(db.Numeric(18, 2), default=100)
    punto_reorden   = db.Column(db.Numeric(18, 2), default=20)
    imagen          = db.Column(db.String(500),  nullable=True)
    oem             = db.Column(db.String(200),  nullable=True)
    dolares         = db.Column(db.Numeric(18, 2), default=0)
    stock_bodega    = db.Column(db.Numeric(18, 2), default=0)
    diametro_interno = db.Column(db.Numeric(10, 2), nullable=True)
    diametro_externo = db.Column(db.Numeric(10, 2), nullable=True)
    altura          = db.Column(db.Numeric(10, 2), nullable=True)
    pared           = db.Column(db.Numeric(10, 2), nullable=True)


class ProduccionInyeccion(db.Model):
    __tablename__ = 'db_inyeccion'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_inyeccion    = db.Column(db.String(80),  index=True, nullable=True)
    fecha_inicia    = db.Column(db.DateTime,    index=True, nullable=True)
    fecha_fin       = db.Column(db.DateTime,    nullable=True)
    id_codigo       = db.Column(db.String(50),  index=True, nullable=True)
    responsable     = db.Column(db.String(150), nullable=True)
    maquina         = db.Column(db.String(80),  nullable=True)
    cantidad_real   = db.Column(db.BigInteger,  default=0)
    estado          = db.Column(db.String(50),  nullable=True)
    molde           = db.Column(db.Integer,     nullable=True)
    cavidades       = db.Column(db.Integer,     default=1) # Columna principal (int4)
    
    # --- Audit Trail 3 Firmas ---
    programado_por  = db.Column(db.String(150), nullable=True)
    iniciado_por    = db.Column(db.String(150), nullable=True)
    finalizado_por  = db.Column(db.String(150), nullable=True)
    validado_por    = db.Column(db.String(150), nullable=True)
    
    # --- Columnas Operativas ---
    hora_llegada         = db.Column(db.String(20),  nullable=True)
    hora_inicio          = db.Column(db.String(20),  nullable=True)
    hora_termina         = db.Column(db.String(20),  nullable=True)
    cant_contador        = db.Column(db.BigInteger,  default=0) # Sincronizado con BigInt real
    almacen_destino      = db.Column(db.String(100), default='POR PULIR')
    codigo_ensamble      = db.Column(db.String(100), nullable=True)
    orden_produccion     = db.Column(db.String(100), nullable=True)
    observaciones        = db.Column(db.Text,        nullable=True)
    produccion_teorica   = db.Column(db.Numeric(12, 2), default=0)
    peso_bujes           = db.Column(db.Numeric(12, 4), default=0)
    pnc_total            = db.Column(db.BigInteger,  default=0)
    pnc_detalle          = db.Column(db.Text,        nullable=True)
    peso_lote            = db.Column(db.Numeric(18, 4), default=0)
    entrada              = db.Column(db.Numeric(18, 2), default=0)
    salida               = db.Column(db.Numeric(18, 2), default=0)
    
    # --- Métricas ---
    duracion_segundos    = db.Column(db.Integer, default=0)
    tiempo_total_minutos = db.Column(db.Numeric(10, 2), default=0)
    segundos_por_unidad  = db.Column(db.Integer, default=0)
    departamento         = db.Column(db.String(100), default='Inyeccion')

    @validates('id_codigo')
    def _sanitizar_id_codigo(self, key, value):
        """Blindaje obligatorio: db_inyeccion persiste la referencia TAL CUAL la
        reportó la planta —preservando 'MT-', 'CAR-', 'CB-' o la ausencia de
        prefijo— sin reetiquetar números puros como 'FR-'. La unificación entre
        'FR-9843' y '9843' se resuelve en las consultas (sql_normalizar_codigo_fr /
        sql_expr_codigo_sin_prefijo_fr), nunca alterando el dato al escribirlo."""
        return preservar_o_normalizar_prefijo(value) if value else value


class PncInyeccion(db.Model):
    __tablename__ = 'db_pnc_inyeccion'
    __table_args__ = {'extend_existing': True}

    id_row           = db.Column(db.Integer, primary_key=True, default=lambda: int(time.time() % 100000000) + random.randint(100000000, 900000000))
    id_pnc_inyeccion = db.Column(db.String(80), index=True, default=lambda: uuid.uuid4().hex[:8])
    id_inyeccion     = db.Column(db.String(80), index=True)
    id_codigo        = db.Column(db.String(50), index=True)
    cantidad         = db.Column(db.Numeric(18, 2), default=0)
    criterio         = db.Column(db.String(200), nullable=True)
    codigo_ensamble  = db.Column(db.String(50), nullable=True)

    # --- Trazabilidad de personas (migrate_pnc_responsable_validado_por.py) ---
    # responsable: operario de INYECCIÓN dueño del lote (db_inyeccion.responsable).
    # validado_por: quien audita la merma. Se llena EXCLUSIVAMENTE desde la
    # identidad autenticada (JWT) en InyeccionService.validar_lote — nunca desde
    # el payload, que es autorreportado y puede falsificar la firma.
    responsable      = db.Column(db.String(150), nullable=True)
    validado_por     = db.Column(db.String(150), nullable=True)

    # --- Desglose de Defectos ---
    quemado_manchado         = db.Column(db.Numeric(18, 2), default=0)
    incompleto_falta_llenado = db.Column(db.Numeric(18, 2), default=0)
    rebaba_excesiva          = db.Column(db.Numeric(18, 2), default=0)
    burbuja_porosidad        = db.Column(db.Numeric(18, 2), default=0)
    deformacion_rechupado    = db.Column(db.Numeric(18, 2), default=0)

    @validates('id_codigo')
    def _sanitizar_id_codigo(self, key, value):
        """Blindaje obligatorio: ningún registro puede persistirse con prefijo 'FR-' colgando."""
        return normalizar_codigo_sin_prefijo(value) if value else value


class PncPulido(db.Model):
    __tablename__ = 'db_pnc_pulido'
    __table_args__ = {'extend_existing': True}

    id_row           = db.Column(db.Integer, primary_key=True, default=lambda: int(time.time() % 100000000) + random.randint(100000000, 900000000))
    id_pnc_pulido    = db.Column(db.String(80), index=True, default=lambda: uuid.uuid4().hex[:8])
    id_pulido        = db.Column(db.Text, index=True) # OID 25
    codigo           = db.Column(db.String(50), index=True)
    cantidad         = db.Column(db.Numeric(18, 2), default=0)
    criterio         = db.Column(db.String(200), nullable=True)
    codigo_ensamble  = db.Column(db.String(50), nullable=True)

    # --- Trazabilidad de personas (migrate_pnc_responsable_validado_por.py) ---
    # responsable: operaria de PULIDO que produjo la merma. Llega en el DTO de
    # validación (items[].operaria_pulido); es obligatoria si hay PNC de pulido.
    # validado_por: quien audita, desde el JWT. Ver nota en PncInyeccion.
    responsable      = db.Column(db.String(150), nullable=True)
    validado_por     = db.Column(db.String(150), nullable=True)

    @validates('codigo')
    def _sanitizar_codigo(self, key, value):
        """Blindaje obligatorio: ningún registro puede persistirse con prefijo 'FR-' colgando."""
        return normalizar_codigo_sin_prefijo(value) if value else value


class PncEnsamble(db.Model):
    __tablename__ = 'db_pnc_ensamble'
    __table_args__ = {'extend_existing': True}

    id_row           = db.Column(db.Integer, primary_key=True, default=lambda: int(time.time() % 100000000) + random.randint(100000000, 900000000))
    id_pnc_ensamble  = db.Column(db.String(80), index=True, default=lambda: uuid.uuid4().hex[:8])
    id_ensamble      = db.Column(db.String(80), index=True)
    id_codigo        = db.Column(db.String(50), index=True)
    cantidad         = db.Column(db.Numeric(18, 2), default=0)
    criterio         = db.Column(db.String(200), nullable=True)
    codigo_ensamble  = db.Column(db.String(50), nullable=True)

    @validates('id_codigo')
    def _sanitizar_id_codigo(self, key, value):
        """Blindaje obligatorio: ningún registro puede persistirse con prefijo 'FR-' colgando."""
        return normalizar_codigo_sin_prefijo(value) if value else value


class ProduccionPulido(db.Model):
    __tablename__ = 'db_pulido'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pulido       = db.Column(db.String(100), index=True, nullable=True) # VARCHAR
    fecha           = db.Column(db.DateTime, index=True, nullable=True)
    # default=get_colombia_time: fallback Python-side por si algún insert no pasa por
    # PulidoService (que ya fija fecha_registro explícitamente con la misma fuente de
    # verdad). server_default=func.now() queda solo como red de seguridad a nivel DB
    # (nunca se dispara mientras SQLAlchemy siga enviando el default de Python).
    fecha_registro  = db.Column(db.DateTime, index=True, default=get_colombia_time, server_default=db.func.now())
    codigo          = db.Column(db.String(100), index=True, nullable=True) # VARCHAR
    responsable     = db.Column(db.String(200), nullable=True) # VARCHAR
    cantidad_real   = db.Column(db.Integer,     default=0) # int4 en DB
    pnc_inyeccion   = db.Column(db.Integer,     default=0)
    pnc_pulido      = db.Column(db.Integer,     default=0)
    hora_inicio     = db.Column(db.DateTime,    nullable=True)
    hora_fin        = db.Column(db.DateTime,    nullable=True)
    estado          = db.Column(db.String(50),  default='FINALIZADO')
    tiempo_total_minutos = db.Column(db.Numeric(10, 2), default=0)
    duracion_segundos    = db.Column(db.Integer, default=0)
    segundos_por_unidad  = db.Column(db.Numeric(10, 2), default=0)
    orden_produccion     = db.Column(db.String(100), nullable=True) # VARCHAR
    observaciones        = db.Column(db.Text,        nullable=True) # TEXT
    criterio_pnc_inyeccion = db.Column(db.Text, nullable=True)
    criterio_pnc_pulido    = db.Column(db.Text, nullable=True)
    departamento           = db.Column(db.String(100), default='PULIDO')
    lote                   = db.Column(db.String(100), nullable=True) # VARCHAR
    cantidad_recibida      = db.Column(db.Numeric(18, 2), default=0)
    almacen_destino        = db.Column(db.String(100), default='P. TERMINADO')
    hora_pausa             = db.Column(db.DateTime,    nullable=True)
    tiempo_pausa_acumulado = db.Column(db.Integer,     default=0)


class PausasPulido(db.Model):
    __tablename__ = 'db_pausas_pulido'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pulido       = db.Column(db.Text,     index=True, nullable=True) # OID 25
    motivo          = db.Column(db.String(200), nullable=True)
    hora_inicio     = db.Column(db.DateTime,    nullable=True)
    hora_fin        = db.Column(db.DateTime,    nullable=True)


class RawVentas(db.Model):
    __tablename__ = 'db_ventas'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha           = db.Column(db.Date,        index=True, nullable=True)
    documento       = db.Column(db.String(80),  index=True, nullable=True)
    nombres         = db.Column(db.String(200), index=True, nullable=True)
    productos       = db.Column(db.String(100), index=True, nullable=True)
    cantidad        = db.Column(db.Numeric(18, 2), default=0)
    total_ingresos  = db.Column(db.Numeric(18, 2), default=0)
    precio_promedio = db.Column(db.Numeric(18, 2), default=0)
    clasificacion   = db.Column(db.String(80),  nullable=True)
    vendedor        = db.Column(db.String(150), index=True, nullable=True)
    zona            = db.Column(db.String(100), index=True, nullable=True)
    # estado no existe en la DB real


class DbClientes(db.Model):
    __tablename__ = 'db_clientes'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre          = db.Column(db.String(200), index=True, nullable=True)
    # NO unique: un mismo NIT puede tener varias direcciones/sucursales
    # (confirmado contra Vista_Tabla_Direcciones de World Office, ej. NIT
    # 830008309 tiene sede en Bogota y en Funza). La llave real de UPSERT
    # por fila es id_direccion_wo (IdTerceroDireccion de WO), no identificacion.
    identificacion  = db.Column(db.String(50),  index=True, nullable=True)
    direccion       = db.Column(db.String(300), nullable=True)
    telefonos       = db.Column(db.String(100), nullable=True)
    ciudad          = db.Column(db.String(100), nullable=True)
    # id_direccion_wo: IdTerceroDireccion de Vista_Tabla_Direcciones (WO).
    # Llave natural de UPSERT por sucursal/direccion. Nullable porque las filas
    # capturadas manualmente antes de esta sincronizacion no tienen este id.
    id_direccion_wo = db.Column(db.Integer, unique=True, nullable=True, index=True)



class RegistroAsistencia(db.Model):
    __tablename__ = 'db_asistencia'
    __table_args__ = {'extend_existing': True}

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha               = db.Column(db.Date,        index=True, nullable=True)
    colaborador         = db.Column(db.String(150), index=True, nullable=True)
    ingreso_real        = db.Column(db.String(20),  nullable=True)
    salida_real         = db.Column(db.String(20),  nullable=True)
    horas_ordinarias    = db.Column(db.Numeric(10, 2), default=0)
    horas_extras        = db.Column(db.Numeric(10, 2), default=0)
    # El campo en la BD real se llama 'jefe'

    estado              = db.Column(db.String(50),  nullable=True)
    estado_pago         = db.Column(db.String(50),  default='PENDIENTE')
    motivo              = db.Column(db.String(255), nullable=True)
    comentarios         = db.Column(db.Text,        nullable=True)
    
    # --- Auditoría de Creación y Edición ---
    registrado_por      = db.Column(db.String(150), nullable=True)
    editado_por         = db.Column(db.String(150), nullable=True)
    fecha_edicion       = db.Column(db.DateTime,    nullable=True)
    motivo_edicion      = db.Column(db.String(255), nullable=True)


class Pedido(db.Model):
    __tablename__ = 'db_pedidos'
    __table_args__ = {'extend_existing': True}

    id_sql          = db.Column("id", db.Integer, primary_key=True, autoincrement=True)
    fecha           = db.Column(db.Date,        index=True, nullable=True)
    hora            = db.Column(db.String(20),  nullable=True)
    id_pedido       = db.Column(db.String(80),  index=True, nullable=True) # ID PEDIDO
    vendedor        = db.Column(db.String(150), nullable=True)
    cliente         = db.Column(db.String(200), index=True, nullable=True)
    nit             = db.Column(db.String(50),  nullable=True)
    direccion       = db.Column(db.String(255), nullable=True)
    ciudad          = db.Column(db.String(100), nullable=True)
    forma_de_pago   = db.Column(db.String(100), nullable=True)
    descuento       = db.Column(db.String(50),  nullable=True)
    wo_consecutivo  = db.Column(db.String(50),  nullable=True)
    id_codigo       = db.Column(db.String(100), index=True, nullable=True) # ID CODIGO
    descripcion     = db.Column(db.String(500), nullable=True)
    cantidad        = db.Column(db.Numeric(18, 2), default=0)
    precio_unitario = db.Column(db.Numeric(18, 2), default=0)
    total           = db.Column(db.Numeric(18, 2), default=0)
    estado          = db.Column(db.String(50),  nullable=True) # PENDIENTE, ALISTADO, etc.
    progreso        = db.Column(db.String(10),  default='0%')
    cant_alistada   = db.Column(db.String(50),  default='0')
    progreso_despacho = db.Column(db.String(10), default='0%')
    delegado_a      = db.Column(db.String(150), nullable=True)
    observaciones   = db.Column(db.Text,        nullable=True)


class DbClienteEquivalencias(db.Model):
    __tablename__ = 'db_cliente_equivalencias'
    __table_args__ = {'extend_existing': True}

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    alias            = db.Column(db.String(255), unique=True, nullable=False, index=True)
    nombre_canonical = db.Column(db.String(255), nullable=False)
    created_at       = db.Column(db.DateTime, server_default=db.func.now())


class Ensamble(db.Model):
    __tablename__ = 'db_ensambles'
    __table_args__ = {'extend_existing': True}

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_ensamble    = db.Column(db.String(80),  nullable=True, default=lambda: uuid.uuid4().hex[:8]) # varchar
    id_codigo      = db.Column(db.Text,  index=True, nullable=True) # TEXT
    responsable    = db.Column(db.Text, nullable=True) # TEXT
    cantidad       = db.Column(db.Integer,     default=0)
    hora_inicio    = db.Column(db.DateTime,    nullable=True)
    hora_fin       = db.Column(db.DateTime,    nullable=True)
    fecha          = db.Column(db.DateTime,    index=True, nullable=True)
    observaciones  = db.Column(db.Text,        nullable=True) # TEXT
    # Campos de trazabilidad (Asegurar que coincidan con la DB real)
    op_numero      = db.Column(db.Text, nullable=True) # TEXT
    almacen_para_descargar = db.Column(db.String(100), nullable=True)
    almacen_destino        = db.Column(db.String(100), nullable=True)
    qty                    = db.Column(db.Numeric(18, 4), default=1)
    buje_ensamble  = db.Column(db.Text, nullable=True) # TEXT
    buje_origen    = db.Column(db.String(100), nullable=True)
    consumo_total  = db.Column(db.Numeric(18, 4), default=0)
    # Métricas Globales
    duracion_segundos    = db.Column(db.Integer, default=0)
    tiempo_total_minutos = db.Column(db.Numeric(10, 2), default=0)
    segundos_por_unidad  = db.Column(db.Numeric(10, 2), default=0)
    departamento         = db.Column(db.String(100), default='Ensamble')
    estado               = db.Column(db.String(50),  default='FINALIZADO') # EN_PROCESO, FINALIZADO
    hora_pausa           = db.Column(db.DateTime,    nullable=True)
    tiempo_pausa_acumulado = db.Column(db.Integer,     default=0)


class Pnc(db.Model):
    __tablename__ = 'db_pnc'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha           = db.Column(db.DateTime,    index=True, nullable=True)
    id_pnc          = db.Column(db.String(80),  nullable=True)
    id_codigo       = db.Column(db.String(50),  index=True, nullable=True)
    cantidad        = db.Column(db.Numeric(18, 2), default=0)
    criterio        = db.Column(db.String(255), nullable=True)
    codigo_ensamble = db.Column(db.String(50),  nullable=True)
    responsable     = db.Column(db.String(150), nullable=True)

    @validates('id_codigo')
    def _sanitizar_id_codigo(self, key, value):
        """Blindaje obligatorio: ningún registro puede persistirse con prefijo 'FR-' colgando."""
        return normalizar_codigo_sin_prefijo(value) if value else value


class BujeRevuelto(db.Model):
    __tablename__ = 'db_bujes_revueltos'
    __table_args__ = {'extend_existing': True}

    id_bujes_revueltos = db.Column(db.String(80), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    id_pulido        = db.Column(db.String(100), index=True) # VARCHAR
    id_codigo        = db.Column(db.String(50), index=True) 
    cantidad         = db.Column(db.Numeric(18, 2), default=0)
    codigo_ensamble  = db.Column(db.String(50), nullable=True)
    responsable      = db.Column(db.String(150), nullable=True)


class DbCostos(db.Model):
    __tablename__ = 'db_costos'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    referencia      = db.Column(db.String(80),  index=True, nullable=True)
    costo_total     = db.Column(db.Numeric(18, 2), default=0)
    precio_de_venta = db.Column(db.String(50),  nullable=True) # Juan Sebastian: Puede contener '$' y puntos
    puntos_pieza    = db.Column(db.Numeric(10, 2), default=1)
    tiempo_minutos  = db.Column(db.Numeric(10, 2), default=0)


class Usuario(db.Model):
    __tablename__ = 'db_usuarios'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username        = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash   = db.Column(db.String(255), nullable=False)
    nombre_completo = db.Column(db.String(150), nullable=True)
    alias_vendedor_wo = db.Column(db.String(150), nullable=True) # Nombre exacto tal como llega en db_ventas.vendedor (World Office), para match estricto sin depender del nombre de login
    rol             = db.Column(db.String(50),  default='operario')
    cedula          = db.Column(db.String(20),  nullable=True) # Identificación oficial del usuario
    nit_empresa     = db.Column(db.String(50),  nullable=True, index=True) # Identificación empresarial para clientes B2B
    departamento    = db.Column(db.String(100), nullable=True) # Area asignada (ej: INYECCION, PULIDO)
    hora_entrada    = db.Column(db.String(20),  nullable=True) # Horario oficial
    hora_salida     = db.Column(db.String(20),  nullable=True) # Horario oficial
    activo          = db.Column(db.Boolean,     default=True)
    ultimo_acceso   = db.Column(db.DateTime,    default=datetime.utcnow)
class CorteNomina(db.Model):
    __tablename__ = 'db_cortes_nomina'
    __table_args__ = {'extend_existing': True}

    id_corte          = db.Column(db.String(50),  primary_key=True)
    fecha_corte       = db.Column(db.DateTime,    default=datetime.utcnow)
    usuario_que_corta = db.Column(db.String(150), nullable=False)
    periodo_inicio    = db.Column(db.Date,        nullable=True)
    periodo_fin       = db.Column(db.Date,        nullable=True)
    total_registros   = db.Column(db.Integer,     nullable=True)
    usuario_autoriza  = db.Column(db.String(150), nullable=True)
    estado            = db.Column(db.String(50),  nullable=True)
    division          = db.Column(db.String(50),  nullable=True)


class Maquina(db.Model):
    __tablename__ = 'db_maquinas'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre          = db.Column(db.String(100), unique=True, nullable=False)
    activa          = db.Column(db.Boolean, default=True)
    descripcion     = db.Column(db.String(255), nullable=True)


class ProgramacionInyeccion(db.Model):
    __tablename__ = 'db_programacion'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha           = db.Column(db.Date, index=True)
    codigo_sistema  = db.Column(db.String(50), index=True)
    maquina         = db.Column(db.String(80))
    cantidad        = db.Column(db.Numeric(18, 2), default=0)
    estado          = db.Column(db.String(50), default='PENDIENTE')
    molde           = db.Column(db.Integer, nullable=True)
    cavidades       = db.Column(db.Integer, default=1)
    responsable_planta = db.Column(db.String(150), nullable=True)
    observaciones   = db.Column(db.Text, nullable=True)
    op_world_office = db.Column(db.String(100), index=True, nullable=True)



class Mezcla(db.Model):
    __tablename__ = 'db_mezcla'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha           = db.Column(db.Date, index=True)
    hora            = db.Column(db.String(20))
    responsable     = db.Column(db.String(150))
    maquina         = db.Column(db.String(80))
    virgen_kg       = db.Column(db.Numeric(10, 2), default=0)
    molido_kg       = db.Column(db.Numeric(10, 2), default=0)
    pigmento_kg     = db.Column(db.Numeric(10, 2), default=0)
    lote_interno    = db.Column(db.String(50), index=True)
    observaciones   = db.Column(db.Text)

class Molido(db.Model):
    __tablename__ = 'db_molido'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha_registro  = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    responsable     = db.Column(db.String(150))
    peso_kg         = db.Column(db.Numeric(10, 2), default=0)
    tipo_material   = db.Column(db.String(50)) # 'Recuperado', 'Contaminado'
    observaciones   = db.Column(db.Text)


class FichaMaestra(db.Model):
    __tablename__ = 'nueva_ficha_maestra'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    producto        = db.Column(db.String(50), index=True) # Codigo Padre
    subproducto     = db.Column(db.String(50), index=True) # Codigo Componente
    cantidad        = db.Column(db.Numeric(18, 2), default=0)


class Molde(db.Model):
    """Modelo para la tabla db_moldes — validación de cavidades max por molde."""
    __tablename__ = 'db_moldes'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre          = db.Column(db.String(100), unique=True, nullable=False, index=True)
    cavidades_max   = db.Column(db.Integer, default=1)
    activo          = db.Column(db.Boolean, default=True)
    descripcion     = db.Column(db.String(255), nullable=True)


class RelProductoMolde(db.Model):
    """Modelo para rel_producto_molde — qué molde produce cada referencia Friparts
    y con cuántas cavidades. Un molde puede tener varias filas (combo/moneda
    alternativa); tipo_vinculo distingue CAVIDAD_FIJA de MONEDA_ALTERNATIVA."""
    __tablename__ = 'rel_producto_molde'
    __table_args__ = {'extend_existing': True}

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_molde        = db.Column(db.String(50), index=True, nullable=False)
    codigo_referencia   = db.Column(db.String(50), index=True, nullable=False)
    cavidades           = db.Column(db.Integer, default=1)
    tipo_vinculo        = db.Column(db.String(30), default='CAVIDAD_FIJA')
    activo              = db.Column(db.Boolean, default=True)


class Portamolde(db.Model):
    """Modelo para db_portamoldes — catálogo de portamoldes físicos (A-P, Ñ).
    Cada código es una sola pieza física: cantidad_fisica=1 salvo que planta
    confirme copias."""
    __tablename__ = 'db_portamoldes'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo          = db.Column(db.String(10), unique=True, nullable=False, index=True)
    cantidad_fisica = db.Column(db.Integer, default=1)
    activo          = db.Column(db.Boolean, default=True)


class RelMoldePortamolde(db.Model):
    """Modelo para rel_molde_portamoldes — qué portamolde(s) necesita cada
    molde para montarse en una máquina."""
    __tablename__ = 'rel_molde_portamoldes'
    __table_args__ = {'extend_existing': True}

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_molde        = db.Column(db.String(50), index=True, nullable=False)
    codigo_portamolde   = db.Column(db.String(10), index=True, nullable=False)


class RelMaquinaPortamolde(db.Model):
    """Modelo para rel_maquina_portamolde — qué portamoldes acepta cada
    máquina según su capacidad (grandes: M,N,Ñ,O,P / chicas: A-M)."""
    __tablename__ = 'rel_maquina_portamolde'
    __table_args__ = {'extend_existing': True}

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    maquina             = db.Column(db.String(80), index=True, nullable=False)
    codigo_portamolde   = db.Column(db.String(10), index=True, nullable=False)


class Macho(db.Model):
    """Modelo para db_machos — inventario de machos independientes (no tienen
    SKU Friparts propio). diametro_interno_mm se usa con tolerancia +/-1mm
    para calzar contra el diámetro que pide una referencia; cantidad_fisica_disponible
    limita cuántas cavidades de esa medida se pueden montar simultáneamente."""
    __tablename__ = 'db_machos'
    __table_args__ = {'extend_existing': True}

    id                          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_macho                = db.Column(db.String(50), unique=True, nullable=False, index=True)
    diametro_interno_mm         = db.Column(db.Numeric(10, 2), nullable=True)
    cantidad_fisica_disponible  = db.Column(db.Integer, default=0)
    activo                      = db.Column(db.Boolean, default=True)


class SimuladorAsignacion(db.Model):
    """Modelo para simulador_asignaciones — estado propio y aislado del
    simulador de programación (2026-08-06). NO se relaciona con
    db_programacion/db_inyeccion; es un sandbox separado del MES real.
    codigo_macho es nullable (no todos los moldes usan macho); la
    compatibilidad molde<->macho se calcula por diámetro, no se guarda aquí."""
    __tablename__ = 'simulador_asignaciones'
    __table_args__ = {'extend_existing': True}

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    maquina             = db.Column(db.String(80), index=True, nullable=False)
    codigo_portamolde   = db.Column(db.String(10), nullable=False)
    codigo_molde        = db.Column(db.String(50), nullable=False)
    codigo_referencia   = db.Column(db.String(50), nullable=False)
    codigo_macho        = db.Column(db.String(50), nullable=True)
    cavidades           = db.Column(db.Integer, default=1)
    origen              = db.Column(db.String(30), nullable=False)
    estado              = db.Column(db.String(20), default='ACTIVA', index=True)
    responsable         = db.Column(db.String(150), nullable=True)
    creado_en           = db.Column(db.DateTime, default=datetime.utcnow)
    liberado_en         = db.Column(db.DateTime, nullable=True)


class OperacionLog(db.Model):
    """Modelo para registro de auditoría de operaciones en el sistema."""
    __tablename__ = 'db_logs'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha           = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    modulo          = db.Column(db.String(50), index=True)
    operario        = db.Column(db.String(150))
    accion          = db.Column(db.String(255))
    detalles        = db.Column(db.Text, nullable=True)


class MetalsProduccion(db.Model):
    __tablename__ = 'metals_produccion'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha           = db.Column(db.String(50))
    responsable     = db.Column(db.String(150), index=True)
    departamento    = db.Column(db.String(100))
    proceso         = db.Column(db.String(150))
    maquina         = db.Column(db.String(100))
    id_pedido       = db.Column(db.String(50), index=True)
    codigo          = db.Column(db.String(50), index=True)
    descripcion     = db.Column(db.String(500))
    cantidad_ok     = db.Column(db.Numeric(18, 2), default=0)
    pnc             = db.Column(db.Numeric(18, 2), default=0)
    hora_inicio     = db.Column(db.String(50))
    hora_fin        = db.Column(db.String(50))
    tiempo          = db.Column(db.String(50))
    observaciones   = db.Column(db.Text)
    campos_extra    = db.Column(db.Text)


class MetalsPersonal(db.Model):
    __tablename__ = 'metals_personal'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    responsable     = db.Column(db.String(150), index=True)
    departamento    = db.Column(db.String(100))
    documento       = db.Column(db.String(50))
    activo          = db.Column(db.String(10), default='SI')
    # Alineacion 2026-08-10: la tabla real en Postgres SI tiene esta columna
    # (confirmado via information_schema.columns) pero el modelo no la
    # declaraba, dejandola invisible para el ORM.
    telefono        = db.Column(db.String(100))


class MetalsProducto(db.Model):
    __tablename__ = 'metals_productos'
    __table_args__ = {'extend_existing': True}

    codigo          = db.Column(db.String(50), primary_key=True)
    descripcion     = db.Column(db.String(500))
    precio          = db.Column(db.Integer, default=0)


class DbProveedor(db.Model):
    __tablename__ = 'db_proveedores'
    __table_args__ = {'extend_existing': True}

    proveedores     = db.Column(db.String(200), index=True)
    nit             = db.Column(db.String(50), primary_key=True)
    direccion       = db.Column(db.String(300))
    persona_de_contacto = db.Column(db.String(150))
    telefono        = db.Column(db.String(100))
    correo          = db.Column(db.String(150))
    proceso         = db.Column(db.String(100))
    forma_de_pago   = db.Column(db.String(100))
    ultima_evaluacion = db.Column(db.String(50))


class OrdenCompra(db.Model):
    __tablename__ = 'ordenes_de_compra'
    __table_args__ = {'extend_existing': True}

    # Alineacion 2026-08-10: la tabla real no tenia columna `id` ni PK alguna
    # (confirmado via information_schema) -- el modelo la declaraba fantasma.
    # scratch/fix_ordenes_compra_metals_clientes_pk.py agrego id SERIAL +
    # PRIMARY KEY real antes de este cambio, asi que ahora es honesto.
    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Los dos db.Column("col_fisica", ...) siguientes preservan el nombre de
    # atributo Python (fecha_solicitud/cantidad_fact) porque
    # backend/routes/procura_routes.py los usa como kwargs al construir
    # OrdenCompra(...) -- solo cambia el nombre de columna FISICA, que en
    # Postgres es 'fecha_de_solicitud'/'cantidad_facturada', no lo que el
    # modelo asumia.
    fecha_solicitud = db.Column('fecha_de_solicitud', db.String(50))
    n_oc            = db.Column(db.String(50), index=True)
    proveedor       = db.Column(db.String(200))
    producto        = db.Column(db.String(50), index=True)
    # NOTA DE TIPO (hallazgo de la auditoria, no pedido explicito): TODAS las
    # columnas de ordenes_de_compra son `text` en Postgres, incluidas estas
    # "numericas" -- WO/la carga original las exporto como texto. Declararlas
    # Numeric hacia que SQLAlchemy fallara al LEER con
    # "InvalidRequestError: Unknown PG numeric type: 25" (25 = OID de text),
    # rompiendo cualquier OrdenCompra.query existente. Mismo patron ya usado
    # en este archivo para DbCostos.precio_de_venta ("Puede contener '$' y
    # puntos"). El codigo que escribe estos campos (procura_routes.py) ya les
    # pasa float() -- eso no cambia con este fix, solo la lectura.
    cantidad        = db.Column(db.String(50))
    fecha_factura   = db.Column(db.String(50))
    n_factura       = db.Column(db.String(80))
    cantidad_fact   = db.Column('cantidad_facturada', db.String(50))
    fecha_llegada   = db.Column(db.String(50))
    cantidad_recibida = db.Column(db.String(50))
    diferencia      = db.Column(db.String(50))
    observaciones   = db.Column(db.Text)
    estado_proceso  = db.Column(db.String(100))
    # Columna real que existia en Postgres pero nunca se habia declarado en
    # el modelo (hallazgo de la auditoria de esquema, no pedido explicito).
    cantidad_total_enviada = db.Column(db.String(50))


class MetalsCliente(db.Model):
    """Modelo sin usos en el codebase (verificado 2026-08-10: ningun
    routes/services referencia MetalsCliente) -- se pudo alinear renombrando
    los atributos Python directamente a los nombres reales de columna, sin
    necesidad de db.Column('nombre_fisico', ...) para preservar compatibilidad."""
    __tablename__ = 'metals_clientes'
    __table_args__ = {'extend_existing': True}

    # Alineacion 2026-08-10: la tabla real no tenia columna `id` ni PK alguna
    # (confirmado via information_schema) -- el modelo la declaraba fantasma.
    # scratch/fix_ordenes_compra_metals_clientes_pk.py agrego id SERIAL +
    # PRIMARY KEY real antes de este cambio, asi que ahora es honesto.
    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre          = db.Column(db.String(200), index=True)
    # 'nit' -> 'identificacion': la columna real en Postgres se llama
    # identificacion, no nit.
    identificacion  = db.Column(db.String(50))
    direccion       = db.Column(db.String(300))
    ciudad          = db.Column(db.String(100))
    # 'telefono' -> 'telefonos': la columna real en Postgres es plural.
    telefonos       = db.Column(db.String(100))


class MetalsPedido(db.Model):
    __tablename__ = 'metals_pedidos'
    __table_args__ = {'extend_existing': True}

    id_pedido       = db.Column(db.String(50), primary_key=True)
    fecha           = db.Column(db.String(50))
    hora            = db.Column(db.String(50))
    id_codigo       = db.Column(db.String(50), primary_key=True)
    descripcion     = db.Column(db.Text)
    vendedor        = db.Column(db.String(100))
    cliente         = db.Column(db.String(200))
    nit             = db.Column(db.String(50))
    direccion       = db.Column(db.String(300))
    ciudad          = db.Column(db.String(100))
    cantidad        = db.Column(db.Integer, default=0)
    precio_unitario = db.Column(db.Integer, default=0)
    total           = db.Column(db.Integer, default=0)
    estado          = db.Column(db.String(50), default='PENDIENTE')
    progreso        = db.Column(db.Integer, default=0)
    observaciones   = db.Column(db.Text)


class ProgramacionEnsamble(db.Model):
    __tablename__ = 'db_programacion_ensamble'
    __table_args__ = {'extend_existing': True}

    id_prog            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_codigo          = db.Column(db.String(50), index=True, nullable=True)
    op_numero          = db.Column(db.String(100), nullable=True)
    cantidad_objetivo  = db.Column(db.Integer, nullable=False)
    cantidad_realizada = db.Column(db.Integer, default=0)
    fecha_programada   = db.Column(db.Date, nullable=False)
    estado             = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, EN_PROCESO, COMPLETADO
class DistribucionOpPedidos(db.Model):
    """
    Sistema de cubetas para la Vista Gerencial. 
    Cruza el progreso de todas las etapas productivas basadas en OP y Pedido.
    """
    __tablename__ = 'db_distribucion_op_pedidos'
    __table_args__ = {'extend_existing': True}

    id_distribucion  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    op_world_office  = db.Column(db.String(100), index=True, nullable=True) # Nullable para planificación de la tarde anterior
    id_pedido        = db.Column(db.String(80), index=True, nullable=False)
    codigo_producto  = db.Column(db.String(100), index=True, nullable=False)
    cant_requerida   = db.Column(db.Integer, nullable=False, default=0)
    cant_inyectada   = db.Column(db.Integer, default=0)
    cant_pulida      = db.Column(db.Integer, default=0)
    cant_ensamblada  = db.Column(db.Integer, default=0)
    cant_alistada    = db.Column(db.Integer, default=0)

class DespachoPedido(db.Model):
    """
    Modelo para registrar el historial de envíos/despachos parciales o totales de un pedido.
    """
    __tablename__ = 'db_despachos_pedido'
    __table_args__ = {'extend_existing': True}

    id_despacho      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pedido        = db.Column(db.String(80), index=True, nullable=False)
    id_codigo        = db.Column(db.String(100), index=True, nullable=False)
    cantidad_enviada = db.Column(db.Integer, nullable=False, default=0)
    fecha            = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    transportadora   = db.Column(db.String(100), nullable=True)
    guia             = db.Column(db.String(100), nullable=True)
    responsable      = db.Column(db.String(150), nullable=True)

class TrazabilidadLote(db.Model):
    """
    Tabla pivote de estado del lote (Cabecera MES).
    Creada por Inyeccion al iniciar turno. Pulido la consume en Modo Lotes en Vivo.
    Validacion es el unico punto de escritura hacia db_productos (Paso 3).
    Sin FK -- patron SQL-First del proyecto.

    Ciclo de vida de estado_actual:
      ABIERTO_PRODUCCION -> EN_PULIDO -> PENDIENTE_VALIDACION -> APROBADO_CERRADO
    """
    __tablename__ = 'db_trazabilidad_lotes'
    __table_args__ = {'extend_existing': True}

    # PK textual -- formato: YYYYMMDD-Maquina-OP (ej: 20260602-MAQ1-OP12345)
    # Permite lookup natural desde Pulido sin JOIN.
    id_lote            = db.Column(db.String(120), primary_key=True)

    # Datos de la Orden de Produccion
    orden_produccion   = db.Column(db.String(100), index=True, nullable=True)
    id_codigo          = db.Column(db.String(50),  index=True, nullable=False)
    maquina            = db.Column(db.String(80),  nullable=True)

    # Referencia al registro padre en db_inyeccion (sin FK declarado)
    id_inyeccion       = db.Column(db.String(80),  index=True, nullable=True)

    # Estado del ciclo de vida del lote
    estado_actual      = db.Column(db.String(30),  nullable=False, default='ABIERTO_PRODUCCION')

    # Auditoria
    fecha_creacion     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    responsable        = db.Column(db.String(150), nullable=True)

    # Cantidad total inyectada -- actualizada al cierre del turno por mes_reportar.
    # Validacion la usa para calcular WIP: WIP = cantidad_inyectada - SUM(db_pulido.cantidad_real)
    cantidad_inyectada = db.Column(db.Integer, default=0)
    por_pulir          = db.Column(db.Integer, default=0)


class InventarioWO(db.Model):
    __tablename__ = 'inventario_wo'
    __table_args__ = {'extend_existing': True}

    codigo_producto = db.Column(db.String(50), primary_key=True)
    descripcion     = db.Column(db.String(500), nullable=True)
    stock_wo        = db.Column(db.Numeric(18, 2), default=0)
    precio_wo       = db.Column(db.Numeric(18, 2), default=0)
    codigo_alterno  = db.Column(db.String(100), nullable=True)
    referencia      = db.Column(db.String(100), nullable=True)

class SuscripcionesPush(db.Model):
    """
    Entidad plana (SQL-First) para almacenar los endpoints de Web Push de cada dispositivo/usuario.
    """
    __tablename__ = 'db_push_subscriptions'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id         = db.Column(db.String(100), db.ForeignKey('db_usuarios.username', ondelete='CASCADE'), index=True, nullable=False)
    endpoint        = db.Column(db.Text, nullable=False, unique=True)
    p256dh          = db.Column(db.Text, nullable=False)
    auth            = db.Column(db.Text, nullable=False)
    fecha_creacion  = db.Column(db.DateTime, default=datetime.utcnow)
