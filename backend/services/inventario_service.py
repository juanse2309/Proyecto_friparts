"""
Servicio de inventario.
Contiene la lógica de negocio para operaciones de inventario.
"""
from typing import Dict, Tuple
from backend.repositories.producto_repository import producto_repo
from backend.repositories.inventario_repository import inventario_repo
from backend.core.exceptions import ProductoNoEncontrado, DatosInvalidos
from backend.utils.validators import Validator
import logging

logger = logging.getLogger(__name__)


class InventarioService:
    """Servicio de inventario con lógica de negocio."""
    
    def registrar_entrada(self, datos: Dict) -> Dict:
        """
        Registra una entrada de inventario con validaciones.
        
        Args:
            datos: {
                "codigo_producto": str,
                "cantidad": int,
                "almacen_destino": str,
                "observaciones": str (opcional)
            }
        
        Returns:
            Dict con status y mensaje
        """
        try:
            # Validar campos requeridos
            valido, errores = Validator.validar_requeridos(
                datos, 
                ["codigo_producto", "cantidad", "almacen_destino"]
            )
            if not valido:
                raise DatosInvalidos(errores)
            
            # Validar cantidad
            valido, errores = Validator.validar_cantidad(datos["cantidad"])
            if not valido:
                raise DatosInvalidos(errores)
            
            # Validar almacén
            valido, errores = Validator.validar_almacen(datos["almacen_destino"])
            if not valido:
                raise DatosInvalidos(errores)
            
            # Verificar que el producto existe
            producto = producto_repo.buscar_por_codigo(datos["codigo_producto"])
            if not producto:
                raise ProductoNoEncontrado(datos["codigo_producto"])
            
            # Registrar entrada
            exito, mensaje = inventario_repo.registrar_entrada(
                codigo=datos["codigo_producto"],
                cantidad=int(datos["cantidad"]),
                almacen=datos["almacen_destino"]
            )
            
            if exito:
                return {
                    "status": "success",
                    "message": mensaje,
                    "producto": {
                        "codigo": producto.get("CODIGO SISTEMA"),
                        "descripcion": producto.get("DESCRIPCION")
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": mensaje
                }
                
        except (DatosInvalidos, ProductoNoEncontrado) as e:
            logger.error(f"Error en entrada: {e.mensaje}")
            return {
                "status": "error",
                "message": e.mensaje
            }
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return {
                "status": "error",
                "message": "Error interno del servidor"
            }
    
    def registrar_salida(self, datos: Dict) -> Dict:
        """
        Registra una salida de inventario con validaciones.
        
        Args:
            datos: {
                "codigo_producto": str,
                "cantidad": int,
                "almacen_origen": str,
                "observaciones": str (opcional)
            }
        
        Returns:
            Dict con status y mensaje
        """
        try:
            # Validar campos requeridos
            valido, errores = Validator.validar_requeridos(
                datos, 
                ["codigo_producto", "cantidad", "almacen_origen"]
            )
            if not valido:
                raise DatosInvalidos(errores)
            
            # Validar cantidad
            valido, errores = Validator.validar_cantidad(datos["cantidad"])
            if not valido:
                raise DatosInvalidos(errores)
            
            # Validar almacén
            valido, errores = Validator.validar_almacen(datos["almacen_origen"])
            if not valido:
                raise DatosInvalidos(errores)
            
            # Verificar que el producto existe
            producto = producto_repo.buscar_por_codigo(datos["codigo_producto"])
            if not producto:
                raise ProductoNoEncontrado(datos["codigo_producto"])
            
            # Registrar salida
            exito, mensaje = inventario_repo.registrar_salida(
                codigo=datos["codigo_producto"],
                cantidad=int(datos["cantidad"]),
                almacen=datos["almacen_origen"]
            )
            
            if exito:
                return {
                    "status": "success",
                    "message": mensaje,
                    "producto": {
                        "codigo": producto.get("CODIGO SISTEMA"),
                        "descripcion": producto.get("DESCRIPCION")
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": mensaje
                }
                
        except (DatosInvalidos, ProductoNoEncontrado) as e:
            logger.error(f"Error en salida: {e.mensaje}")
            return {
                "status": "error",
                "message": e.mensaje
            }
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return {
                "status": "error",
                "message": "Error interno del servidor"
            }
    
    def obtener_detalle_producto(self, codigo: str) -> Dict:
        """
        Obtiene el detalle completo de un producto con stock.
        
        Args:
            codigo: Código del producto
        
        Returns:
            Dict con información del producto
        """
        try:
            producto = producto_repo.buscar_por_codigo(codigo)
            if not producto:
                raise ProductoNoEncontrado(codigo)
            
            # Calcular stock total
            stock_por_pulir = producto_repo.obtener_stock(codigo, "POR PULIR")
            stock_terminado = producto_repo.obtener_stock(codigo, "P. TERMINADO")
            stock_ensamblado = producto_repo.obtener_stock(codigo, "PRODUCTO ENSAMBLADO")
            stock_comprometido = to_int(producto.get("COMPROMETIDO", 0))
            stock_disponible = stock_terminado - stock_comprometido
            stock_cliente = producto_repo.obtener_stock(codigo, "CLIENTE")
            
            stock_total = stock_por_pulir + stock_terminado + stock_ensamblado
            
            return {
                "status": "success",
                "producto": {
                    "codigo_sistema": producto.get("CODIGO SISTEMA"),
                    "id_codigo": producto.get("ID CODIGO"),
                    "descripcion": producto.get("DESCRIPCION"),
                    "descripcion_larga": producto.get("DESCRIPCION LARGA", ""),
                    "marca": producto.get("MARCA", ""),
                    "categoria": producto.get("CATEGORIA", ""),
                    "stock_total": stock_total,
                    "stock_por_pulir": stock_por_pulir,
                    "stock_terminado": stock_terminado,
                    "stock_comprometido": stock_comprometido,
                    "stock_disponible": stock_disponible,
                    "stock_ensamblado": stock_ensamblado,
                    "stock_cliente": stock_cliente,
                    "stock_minimo": int(producto.get("STOCK MINIMO", 10) or 10),
                    "imagen": producto.get("IMAGEN", ""),
                    "activo": True
                }
            }
            
        except ProductoNoEncontrado as e:
            return {
                "status": "error",
                "message": e.mensaje
            }
        except Exception as e:
            logger.error(f"Error obteniendo detalle: {e}")
            return {
                "status": "error",
                "message": "Error interno del servidor"
            }


# Instancia única
inventario_service = InventarioService()