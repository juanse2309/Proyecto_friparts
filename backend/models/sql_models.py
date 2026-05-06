"""
sql_models.py — Modelos SQLAlchemy 100% SQL-First
Tablas planas, sin relationships, sin ForeignKey.
extend_existing=True previene errores de Mapper al recargar el módulo.
"""
from datetime import datetime
import uuid
import time
import random
from backend.core.sql_database import db


class Producto(db.Model):
    __tablename__ = 'db_productos'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_sistema  = db.Column(db.String(50),  index=True, nullable=True)
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
    cantidad_real   = db.Column(db.Numeric(18, 2), default=0)
    estado          = db.Column(db.String(50),  nullable=True)
    molde           = db.Column(db.Integer,     nullable=True)
    cavidades       = db.Column(db.Integer,     default=1)
    # Métricas Globales
    duracion_segundos    = db.Column(db.Integer, default=0)
    tiempo_total_minutos = db.Column(db.Numeric(10, 2), default=0)
    segundos_por_unidad  = db.Column(db.Numeric(10, 2), default=0)
    departamento         = db.Column(db.String(100), default='Inyeccion')


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


class PncPulido(db.Model):
    __tablename__ = 'db_pnc_pulido'
    __table_args__ = {'extend_existing': True}

    id_row           = db.Column(db.Integer, primary_key=True, default=lambda: int(time.time() % 100000000) + random.randint(100000000, 900000000))
    id_pnc_pulido    = db.Column(db.String(80), index=True, default=lambda: uuid.uuid4().hex[:8])
    id_pulido        = db.Column(db.String(80), index=True)
    codigo           = db.Column(db.String(50), index=True) 
    cantidad         = db.Column(db.Numeric(18, 2), default=0)
    criterio         = db.Column(db.String(200), nullable=True)
    codigo_ensamble  = db.Column(db.String(50), nullable=True)


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


class ProduccionPulido(db.Model):
    __tablename__ = 'db_pulido'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pulido       = db.Column(db.String(80),  index=True, nullable=True)
    fecha           = db.Column(db.Date,        index=True, nullable=True)
    codigo          = db.Column(db.String(50),  index=True, nullable=True)
    responsable     = db.Column(db.String(150), nullable=True)
    cantidad_real   = db.Column(db.Numeric(18, 2), default=0)
    pnc_inyeccion   = db.Column(db.Integer,     default=0)
    pnc_pulido      = db.Column(db.Integer,     default=0)
    hora_inicio     = db.Column(db.DateTime,    nullable=True)
    hora_fin        = db.Column(db.DateTime,    nullable=True)
    estado          = db.Column(db.String(50),  default='FINALIZADO') # EN_PROCESO, PAUSADO, FINALIZADO
    # bujes_buenos eliminado - cantidad_real es la verdad única
    tiempo_total_minutos = db.Column(db.Numeric(10, 2), default=0)
    duracion_segundos    = db.Column(db.Integer, default=0)
    segundos_por_unidad  = db.Column(db.Numeric(10, 2), default=0)
    orden_produccion = db.Column(db.String(100), nullable=True)
    observaciones   = db.Column(db.Text,        nullable=True)
    criterio_pnc_inyeccion = db.Column(db.String(200), nullable=True)
    criterio_pnc_pulido    = db.Column(db.String(200), nullable=True)
    departamento           = db.Column(db.String(100), default='PULIDO')
    lote                   = db.Column(db.String(100), nullable=True)
    cantidad_recibida      = db.Column(db.Numeric(18, 2), default=0)
    almacen_destino        = db.Column(db.String(100), default='P. TERMINADO')


class PausasPulido(db.Model):
    __tablename__ = 'db_pausas_pulido'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pulido       = db.Column(db.Integer,     index=True, nullable=True)
    motivo          = db.Column(db.String(200), nullable=True)
    hora_inicio     = db.Column(db.DateTime,    nullable=True)
    hora_fin        = db.Column(db.DateTime,    nullable=True)


class RawVentas(db.Model):
    __tablename__ = 'db_ventas'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha           = db.Column(db.Date,        index=True, nullable=True)
    documento       = db.Column(db.String(80),  index=True, nullable=True)
    cliente         = db.Column(db.String(200), index=True, nullable=True)
    productos       = db.Column(db.String(100), index=True, nullable=True)
    cantidad        = db.Column(db.Numeric(18, 2), default=0)
    total_ingresos  = db.Column(db.Numeric(18, 2), default=0)
    precio_promedio = db.Column(db.Numeric(18, 2), default=0)
    clasificacion   = db.Column(db.String(80),  nullable=True)
    estado          = db.Column(db.String(50),  nullable=True)


class DbClientes(db.Model):
    __tablename__ = 'db_clientes'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre          = db.Column(db.String(200), index=True, nullable=True)
    identificacion  = db.Column(db.String(50),  index=True, nullable=True)
    direccion       = db.Column(db.String(300), nullable=True)
    telefonos       = db.Column(db.String(100), nullable=True)
    ciudad          = db.Column(db.String(100), nullable=True)



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
    jefe                = db.Column(db.String(150), nullable=True)
    estado              = db.Column(db.String(50),  nullable=True)
    estado_pago         = db.Column(db.String(50),  default='PENDIENTE')
    motivo              = db.Column(db.String(255), nullable=True)
    comentarios         = db.Column(db.Text,        nullable=True)


class Pedido(db.Model):
    __tablename__ = 'db_pedidos'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
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


class Ensamble(db.Model):
    __tablename__ = 'db_ensambles'
    __table_args__ = {'extend_existing': True}

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_ensamble    = db.Column(db.String(80),  nullable=True, default=lambda: uuid.uuid4().hex[:8])
    id_codigo      = db.Column(db.String(50),  index=True, nullable=True)
    responsable    = db.Column(db.String(150), nullable=True)
    cantidad       = db.Column(db.Integer,     default=0)
    hora_inicio    = db.Column(db.DateTime,    nullable=True)
    hora_fin       = db.Column(db.DateTime,    nullable=True)
    fecha          = db.Column(db.Date,        index=True, nullable=True)
    observaciones  = db.Column(db.Text,        nullable=True)
    # Campos de trazabilidad (Asegurar que coincidan con la DB real)
    op_numero      = db.Column(db.String(100), nullable=True)
    almacen_para_descargar = db.Column(db.String(100), nullable=True)
    almacen_destino        = db.Column(db.String(100), nullable=True)
    qty            = db.Column(db.Numeric(18, 4), default=1)
    buje_ensamble  = db.Column(db.String(100), nullable=True)
    buje_origen    = db.Column(db.String(100), nullable=True)
    consumo_total  = db.Column(db.Numeric(18, 4), default=0)
    # Métricas Globales
    duracion_segundos    = db.Column(db.Integer, default=0)
    tiempo_total_minutos = db.Column(db.Numeric(10, 2), default=0)
    segundos_por_unidad  = db.Column(db.Numeric(10, 2), default=0)
    departamento         = db.Column(db.String(100), default='Ensamble')
    estado               = db.Column(db.String(50),  default='FINALIZADO') # EN_PROCESO, FINALIZADO


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
    rol             = db.Column(db.String(50),  default='operario')
    jefe            = db.Column(db.String(150), nullable=True) # Jefe directo para filtrado RBAC
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

    id              = db.Column(db.String(80), primary_key=True)
    fecha           = db.Column(db.String(50))
    responsable     = db.Column(db.String(150), index=True)
    departamento    = db.Column(db.String(100))
    proceso         = db.Column(db.String(150))
    maquina         = db.Column(db.String(100))
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
    responsable     = db.Column(db.String(150), unique=True)
    departamento    = db.Column(db.String(100))
    documento       = db.Column(db.String(50))
    activo          = db.Column(db.String(10), default='SI')


class DbProveedor(db.Model):
    __tablename__ = 'db_proveedores'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre          = db.Column(db.String(200), index=True)
    nit             = db.Column(db.String(50))
    direccion       = db.Column(db.String(300))
    contacto        = db.Column(db.String(150))
    telefono        = db.Column(db.String(100))
    correo          = db.Column(db.String(150))
    proceso         = db.Column(db.String(100))
    forma_pago      = db.Column(db.String(100))
    evaluacion      = db.Column(db.String(50))


class OrdenCompra(db.Model):
    __tablename__ = 'ordenes_de_compra'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha_solicitud = db.Column(db.String(50))
    n_oc            = db.Column(db.String(50), index=True)
    proveedor       = db.Column(db.String(200))
    producto        = db.Column(db.String(50), index=True)
    cantidad        = db.Column(db.Numeric(18, 2), default=0)
    fecha_factura   = db.Column(db.String(50))
    n_factura       = db.Column(db.String(80))
    cantidad_fact   = db.Column(db.Numeric(18, 2), default=0)
    fecha_llegada   = db.Column(db.String(50))
    cantidad_recibida = db.Column(db.Numeric(18, 2), default=0)
    diferencia      = db.Column(db.Numeric(18, 2), default=0)
    observaciones   = db.Column(db.Text)
    cantidad_enviada = db.Column(db.Numeric(18, 2), default=0)
    estado_proceso  = db.Column(db.String(100))


class MetalsCliente(db.Model):
    __tablename__ = 'metals_clientes'
    __table_args__ = {'extend_existing': True}

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre          = db.Column(db.String(200), index=True)
    nit             = db.Column(db.String(50))
    direccion       = db.Column(db.String(300))
    ciudad          = db.Column(db.String(100))
    telefono        = db.Column(db.String(100))
