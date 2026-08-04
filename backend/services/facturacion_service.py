"""
Servicio de Facturación (registro legacy directo, distinto del flujo de
exportación World Office que ya vive en facturacion_routes.py).
Extraído de backend/app.py.
"""
import logging
from backend.core.sql_database import db
from backend.models.sql_models import Producto
from backend.utils.formatters import normalizar_codigo

logger = logging.getLogger(__name__)


class FacturacionDatosInvalidosException(Exception):
    """
    Validación de negocio de FacturacionService.registrar (campos faltantes,
    cantidad inválida, stock insuficiente). Deliberadamente NO es un
    ValueError plano: antes del fix del ticket task_651f2d99 el bug de
    unpacking en registrar() también lanzaba `ValueError` de forma nativa, y
    un controlador que atrapara ValueError genérico lo habría convertido en
    400 ocultando ese 500. Se mantiene el tipo separado tras el fix por si
    algún otro `ValueError` inesperado aparece más adelante en el método.
    """
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


def _obtener_stock_terminado(codigo_sistema):
    """
    Stock actual en P. TERMINADO para un código. Réplica autocontenida de la
    cadena buscar_producto_en_inventario()->obtener_stock() que vivía en
    app.py — ahora que Facturación se muda de ahí, esa cadena queda sin
    ningún otro caller (confirmado por grep antes de purgarla de app.py).
    """
    codigo_norm = normalizar_codigo(codigo_sistema)
    producto = Producto.query.filter(
        (Producto.codigo_sistema == codigo_norm) |
        (Producto.id_codigo == codigo_norm)
    ).first()
    if not producto:
        return 0
    try:
        return int(float(producto.p_terminado or 0))
    except Exception:
        return 0


def registrar_log_operacion(modulo, datos):
    """Registra auditoría de operaciones en la base de datos SQL (db_logs)."""
    try:
        import json
        from backend.models.sql_models import OperacionLog

        detalles_json = json.dumps(datos) if isinstance(datos, (dict, list)) else str(datos)
        operario = "Sistema"
        if isinstance(datos, dict):
            operario = datos.get('OPERARIO') or datos.get('RESPONSABLE') or "Sistema"

        nuevo_log = OperacionLog(
            modulo=modulo,
            operario=str(operario),
            accion=f"Registro en {modulo}",
            detalles=detalles_json
        )
        db.session.add(nuevo_log)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.warning(f" ⚠️ [SQL-LOG] Fallo al registrar log: {e}")
        return False


def registrar_log_facturacion(fila):
    """Registra una facturacion en LOG_FACTURACION correctamente."""
    return registrar_log_operacion('FACTURACION', fila)


class FacturacionService:

    @staticmethod
    def registrar(data):
        """
        Registro legacy directo de una facturación (POST /api/facturacion,
        distinto del flujo de exportación masiva a World Office).

        FIX (ticket task_651f2d99): `StockService.registrar_salida` devuelve
        un único dict, nunca una tupla `(bool, str)`. El código original (y
        su migración tal cual desde backend/app.py) lo desempaquetaba en 2
        variables, lo que lanzaba `ValueError: too many values to unpack`
        siempre que la operación llegaba hasta aquí — todo POST
        /api/facturacion crasheaba con 500 antes de llegar a persistir nada.
        Se corrige comprobando la clave "error" del dict, igual que ya hace
        StockService.mover_inventario_entre_etapas.

        FIX adicional (bug #2, quedaba enmascarado por el de arriba): más
        abajo se llamaba `formatear_fecha_para_sheet(...)`, una función que
        nunca existió en este proyecto (ni en app.py original, ni en ningún
        otro módulo — confirmado por grep) y que habría lanzado NameError en
        cuanto el bug del unpacking dejara de dispararse primero. El destino
        de esa fecha es `registrar_log_facturacion` -> `registrar_log_operacion`,
        que serializa la fila como JSON en db_logs (ya no hay export a Google
        Sheets en este flujo, ver docstring del módulo) — no hace falta
        ningún formateo especial de "hoja de cálculo", se usa la fecha tal
        como llega en el payload.
        """
        if not data:
            raise FacturacionDatosInvalidosException('No se recibieron datos')

        errors = []
        required_fields = ["fecha_inicio", "cliente", "codigo_producto", "cantidad_vendida"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Campo '{field}' es obligatorio")
        if errors:
            raise FacturacionDatosInvalidosException(", ".join(errors))

        try:
            cantidad_vendida = int(data['cantidad_vendida'])
            if cantidad_vendida <= 0:
                errors.append("La cantidad vendida debe ser mayor a 0")
        except Exception:
            errors.append("La cantidad vendida debe ser un numero valido")
        if errors:
            raise FacturacionDatosInvalidosException(", ".join(errors))

        codigo_sis = normalizar_codigo(data['codigo_producto'])
        stock_disponible = _obtener_stock_terminado(codigo_sis)

        if stock_disponible < cantidad_vendida:
            raise FacturacionDatosInvalidosException(
                f"Stock insuficiente en P. TERMINADO. Disponible: {stock_disponible}, Solicitado: {cantidad_vendida}"
            )

        nit_cliente = "S/N"
        try:
            from backend.models.sql_models import DbClientes
            cliente_db = DbClientes.query.filter_by(nombre=data['cliente']).first()
            if cliente_db:
                nit_cliente = cliente_db.identificacion or "S/N"
        except Exception as e:
            logger.error(f"Error obteniendo NIT del cliente SQL: {e}")
            nit_cliente = "S/N"

        if not nit_cliente:
            nit_cliente = "S/N"

        from backend.services.stock_service import StockService
        resultado_salida = StockService.registrar_salida(codigo_sis, cantidad_vendida, "P. TERMINADO")

        if "error" in resultado_salida:
            raise FacturacionDatosInvalidosException(resultado_salida["error"])

        import uuid
        id_factura = f"FAC-{str(uuid.uuid4())[:8].upper()}"

        try:
            total_venta = float(data.get('total_venta', 0))
        except Exception:
            total_venta = 0

        fila_factura = [
            id_factura,
            data['cliente'],
            str(data['fecha_inicio']),
            nit_cliente,
            cantidad_vendida,
            total_venta,
            codigo_sis
        ]

        if not registrar_log_facturacion(fila_factura):
            raise RuntimeError("Error al guardar en LOG_FACTURACION")

        mensaje = f" Facturacion registrada: {cantidad_vendida} piezas de {codigo_sis} para {data['cliente']} (NIT: {nit_cliente})"
        return {'mensaje': mensaje}
