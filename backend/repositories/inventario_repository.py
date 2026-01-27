"""
Repositorio de inventario.
Gestiona movimientos de stock entre almacenes.
"""
from typing import Dict, Tuple
from backend.repositories.producto_repository import producto_repo
from backend.config.settings import Almacenes
from backend.core.exceptions import ProductoNoEncontrado, StockInsuficiente, AlmacenInvalido
import logging

logger = logging.getLogger(__name__)


class InventarioRepository:
    """Repositorio para operaciones de inventario."""
    
    def registrar_entrada(self, codigo: str, cantidad: int, almacen: str) -> Tuple[bool, str]:
        """
        Registra una entrada de inventario (suma al stock).
        
        Args:
            codigo: Código del producto
            cantidad: Cantidad a agregar
            almacen: Almacén destino
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Validar almacén
            if not Almacenes.es_valido(almacen):
                raise AlmacenInvalido(almacen)
            
            # Obtener stock actual
            stock_actual = producto_repo.obtener_stock(codigo, almacen)
            nuevo_stock = stock_actual + cantidad
            
            # Actualizar
            exito = producto_repo.actualizar_stock(codigo, nuevo_stock, almacen)
            
            if exito:
                mensaje = f"Entrada registrada: +{cantidad} en {almacen}. Nuevo stock: {nuevo_stock}"
                logger.info(f"{codigo}: {mensaje}")
                return True, mensaje
            else:
                return False, "Error actualizando stock"
                
        except AlmacenInvalido as e:
            logger.error(str(e))
            return False, e.mensaje
        except Exception as e:
            logger.error(f"Error en entrada: {e}")
            return False, str(e)
    
    def registrar_salida(self, codigo: str, cantidad: int, almacen: str) -> Tuple[bool, str]:
        """
        Registra una salida de inventario (resta del stock).
        
        Args:
            codigo: Código del producto
            cantidad: Cantidad a restar
            almacen: Almacén origen
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Validar almacén
            if not Almacenes.es_valido(almacen):
                raise AlmacenInvalido(almacen)
            
            # Obtener stock actual
            stock_actual = producto_repo.obtener_stock(codigo, almacen)
            
            # Validar stock suficiente
            if stock_actual < cantidad:
                raise StockInsuficiente(codigo, stock_actual, cantidad)
            
            nuevo_stock = stock_actual - cantidad
            
            # Actualizar
            exito = producto_repo.actualizar_stock(codigo, nuevo_stock, almacen)
            
            if exito:
                mensaje = f"Salida registrada: -{cantidad} de {almacen}. Nuevo stock: {nuevo_stock}"
                logger.info(f"{codigo}: {mensaje}")
                return True, mensaje
            else:
                return False, "Error actualizando stock"
                
        except (AlmacenInvalido, StockInsuficiente) as e:
            logger.error(str(e))
            return False, e.mensaje
        except Exception as e:
            logger.error(f"Error en salida: {e}")
            return False, str(e)
    
    def mover_entre_almacenes(self, codigo: str, cantidad: int, origen: str, destino: str) -> Tuple[bool, str]:
        """
        Mueve inventario de un almacén a otro (salida + entrada atómica).
        
        Args:
            codigo: Código del producto
            cantidad: Cantidad a mover
            origen: Almacén origen
            destino: Almacén destino
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Registrar salida
            exito_salida, msg_salida = self.registrar_salida(codigo, cantidad, origen)
            if not exito_salida:
                return False, msg_salida
            
            # Registrar entrada
            exito_entrada, msg_entrada = self.registrar_entrada(codigo, cantidad, destino)
            if not exito_entrada:
                # ROLLBACK: devolver al origen
                logger.warning(f"Rollback: devolviendo {cantidad} a {origen}")
                self.registrar_entrada(codigo, cantidad, origen)
                return False, f"Error moviendo a destino: {msg_entrada}"
            
            mensaje = f"Movimiento exitoso: {cantidad} de {origen} a {destino}"
            logger.info(f"{codigo}: {mensaje}")
            return True, mensaje
            
        except Exception as e:
            logger.error(f"Error en movimiento: {e}")
            return False, str(e)


# Instancia única
inventario_repo = InventarioRepository()
