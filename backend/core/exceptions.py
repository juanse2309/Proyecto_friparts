"""Excepciones personalizadas de la aplicación."""

class AppException(Exception):
    """Excepción base de la aplicación."""
    def __init__(self, mensaje: str, codigo: int = 500):
        self.mensaje = mensaje
        self.codigo = codigo
        super().__init__(self.mensaje)


class ProductoNoEncontrado(AppException):
    """Se lanza cuando no se encuentra un producto."""
    def __init__(self, codigo: str):
        super().__init__(f"Producto '{codigo}' no encontrado", 404)
        self.codigo_producto = codigo


class StockInsuficiente(AppException):
    """Se lanza cuando no hay stock suficiente."""
    def __init__(self, codigo: str, disponible: int, requerido: int):
        mensaje = f"Stock insuficiente para '{codigo}'. Disponible: {disponible}, Requerido: {requerido}"
        super().__init__(mensaje, 400)
        self.codigo_producto = codigo
        self.disponible = disponible
        self.requerido = requerido


class AlmacenInvalido(AppException):
    """Se lanza cuando el almacén no es válido."""
    def __init__(self, almacen: str):
        super().__init__(f"Almacen '{almacen}' no valido", 400)
        self.almacen = almacen


class DatosInvalidos(AppException):
    """Se lanza cuando los datos del request son inválidos."""
    def __init__(self, errores: list):
        mensaje = "Datos invalidos: " + ", ".join(errores)
        super().__init__(mensaje, 400)
        self.errores = errores