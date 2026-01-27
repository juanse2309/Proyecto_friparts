"""
Repositorio de productos.
Centraliza TODO el acceso a la hoja PRODUCTOS.
"""
from typing import Optional, List, Dict
from backend.core.database import sheets_client
from backend.config.settings import Hojas, Almacenes
from backend.utils.formatters import normalizar_codigo, to_int
import logging

logger = logging.getLogger(__name__)


class ProductoRepository:
    """Repositorio para operaciones con productos."""
    
    def __init__(self):
        self.hoja = Hojas.PRODUCTOS
    
    def buscar_por_codigo(self, codigo: str) -> Optional[Dict]:
        """
        Busca un producto por código (acepta FR-9304 o 9304).
        
        Args:
            codigo: Código del producto (con o sin prefijo)
        
        Returns:
            Dict con datos del producto o None si no se encuentra
        """
        try:
            ws = sheets_client.get_worksheet(self.hoja)
            if not ws:
                logger.error(f"Hoja {self.hoja} no encontrada")
                return None
            
            registros = ws.get_all_records()
            codigo_normalizado = normalizar_codigo(codigo)
            
            for idx, registro in enumerate(registros):
                codigo_sistema = str(registro.get('CODIGO SISTEMA', '')).strip()
                id_codigo = str(registro.get('ID CODIGO', '')).strip()
                
                # Buscar por código completo o normalizado
                if (codigo_sistema == codigo or 
                    codigo_sistema == codigo_normalizado or
                    id_codigo == codigo or
                    normalizar_codigo(codigo_sistema) == codigo_normalizado):
                    
                    # Agregar número de fila para updates
                    registro['_fila'] = idx + 2
                    return registro
            
            logger.warning(f"Producto no encontrado: {codigo}")
            return None
            
        except Exception as e:
            logger.error(f"Error buscando producto {codigo}: {e}")
            return None
    
    def listar_todos(self) -> List[Dict]:
        """Obtiene todos los productos."""
        try:
            ws = sheets_client.get_worksheet(self.hoja)
            if not ws:
                return []
            return ws.get_all_records()
        except Exception as e:
            logger.error(f"Error listando productos: {e}")
            return []
    
    def obtener_stock(self, codigo: str, almacen: str) -> int:
        """
        Obtiene el stock de un producto en un almacén específico.
        
        Args:
            codigo: Código del producto
            almacen: Nombre del almacén
        
        Returns:
            int: Cantidad en stock (0 si no existe)
        """
        try:
            producto = self.buscar_por_codigo(codigo)
            if not producto:
                return 0
            
            # Normalizar nombre de almacén
            almacen_norm = Almacenes.normalizar(almacen)
            return to_int(producto.get(almacen_norm, 0))
            
        except Exception as e:
            logger.error(f"Error obteniendo stock: {e}")
            return 0
    
    def actualizar_stock(self, codigo: str, nuevo_stock: int, almacen: str) -> bool:
        """
        Actualiza el stock de un producto en un almacén.
        
        Args:
            codigo: Código del producto
            nuevo_stock: Nueva cantidad
            almacen: Nombre del almacén
        
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            producto = self.buscar_por_codigo(codigo)
            if not producto:
                logger.error(f"Producto {codigo} no encontrado para actualizar stock")
                return False
            
            ws = sheets_client.get_worksheet(self.hoja)
            headers = ws.row_values(1)
            
            # Normalizar almacén
            almacen_norm = Almacenes.normalizar(almacen)
            
            if almacen_norm not in headers:
                logger.error(f"Columna {almacen_norm} no existe en PRODUCTOS")
                return False
            
            col_index = headers.index(almacen_norm) + 1
            fila = producto['_fila']
            
            ws.update_cell(fila, col_index, nuevo_stock)
            logger.info(f"Stock actualizado: {codigo} en {almacen_norm} = {nuevo_stock}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando stock: {e}")
            return False
    
    def buscar_por_termino(self, termino: str, limite: int = 20) -> List[Dict]:
        """
        Busca productos por término (código, descripción, OEM).
        
        Args:
            termino: Texto a buscar
            limite: Número máximo de resultados
        
        Returns:
            Lista de productos que coinciden
        """
        try:
            ws = sheets_client.get_worksheet(self.hoja)
            if not ws:
                return []
            
            registros = ws.get_all_records()
            resultados = []
            termino_lower = termino.lower()
            
            for registro in registros:
                # Buscar en múltiples campos
                codigo_sistema = str(registro.get('CODIGO SISTEMA', '')).lower()
                id_codigo = str(registro.get('ID CODIGO', '')).lower()
                descripcion = str(registro.get('DESCRIPCION', '')).lower()
                oem = str(registro.get('OEM', '')).lower()
                
                if (termino_lower in codigo_sistema or
                    termino_lower in id_codigo or
                    termino_lower in descripcion or
                    termino_lower in oem):
                    resultados.append(registro)
                    
                    if len(resultados) >= limite:
                        break
            
            return resultados
            
        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            return []


# Instancia única
producto_repo = ProductoRepository()
