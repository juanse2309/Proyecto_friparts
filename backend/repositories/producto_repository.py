"""
Repositorio de productos 100% SQL-First.
Centraliza el acceso a la tabla db_productos en PostgreSQL.
"""
from typing import Optional, List, Dict
from sqlalchemy import func
from backend.core.sql_database import db
from backend.models.sql_models import Producto, MetalsProducto
import logging

logger = logging.getLogger(__name__)


class ProductoRepository:
    """
    Repositorio para operaciones con productos vía SQLAlchemy.
    Soporta múltiples divisiones (FriParts / FriMetals).
    """

    def __init__(self, tenant: str = "friparts"):
        self.tenant = tenant.lower()
        # Seleccionar modelo base según división
        self.model = MetalsProducto if self.tenant == "frimetals" else Producto
    
    def buscar_por_codigo(self, codigo: str) -> Optional[Dict]:
        """
        Busca un producto en SQL por código o ID.
        """
        try:
            from backend.utils.formatters import normalizar_codigo
            cod_norm = normalizar_codigo(codigo)
            
            if self.tenant == "frimetals":
                p = db.session.query(MetalsProducto).filter(MetalsProducto.codigo.ilike(f"%{cod_norm}%")).first()
            else:
                p = db.session.query(Producto).filter(
                    (Producto.codigo_sistema.ilike(f"%{cod_norm}%")) | 
                    (Producto.id_codigo.ilike(f"%{cod_norm}%"))
                ).first()
            
            if not p:
                return None
                
            return self._to_dict(p)
            
        except Exception as e:
            logger.error(f"Error buscando producto SQL {codigo} ({self.tenant}): {e}")
            return None
    
    def listar_todos(self) -> List[Dict]:
        """
        Lista todos los productos de la tabla correspondiente.
        """
        try:
            productos = db.session.query(self.model).all()
            return [self._to_dict(p) for p in productos]
        except Exception as e:
            logger.error(f"Error listando productos SQL ({self.tenant}): {e}")
            return []
    
    def obtener_stock(self, codigo: str, almacen: str) -> float:
        """
        Obtiene el stock de un producto desde SQL.
        """
        try:
            p = self.buscar_por_codigo(codigo)
            if not p: return 0
            
            # Mapear nombre de almacén a columna SQL
            mapeo = {
                'POR PULIR': 'POR PULIR',
                'P. TERMINADO': 'P. TERMINADO',
                'PRODUCTO ENSAMBLADO': 'PRODUCTO ENSAMBLADO',
                'COMPROMETIDO': 'COMPROMETIDO'
            }
            col = mapeo.get(almacen.upper(), 'P. TERMINADO')
            return float(p.get(col, 0))
        except:
            return 0
    
    def actualizar_stock(self, codigo: str, nuevo_stock: float, almacen: str) -> bool:
        """
        Actualiza una columna de stock en SQL.
        """
        try:
            from backend.utils.formatters import normalizar_codigo
            cod_norm = normalizar_codigo(codigo)
            
            p = db.session.query(Producto).filter(
                (func.upper(Producto.codigo_sistema) == cod_norm) | 
                (func.upper(Producto.id_codigo) == cod_norm)
            ).first()
            
            if not p: return False
            
            almacen_upper = almacen.upper()
            if 'PULIR' in almacen_upper: p.por_pulir = nuevo_stock
            elif 'TERMINADO' in almacen_upper: p.p_terminado = nuevo_stock
            elif 'ENSAMBLADO' in almacen_upper: p.producto_ensamblado = nuevo_stock
            elif 'COMPROMETIDO' in almacen_upper: p.comprometido = nuevo_stock
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando stock SQL: {e}")
            return False

    def buscar_por_termino(self, termino: str, limite: int = 50) -> List[Dict]:
        """
        Busca productos por término en SQL.
        Soporta búsqueda parcial: '9304' encontrará 'FR-9304'.
        """
        try:
            t = f"%{termino.strip()}%"
            if self.tenant == "frimetals":
                res = db.session.query(MetalsProducto).filter(
                    (MetalsProducto.codigo.ilike(t)) |
                    (MetalsProducto.descripcion.ilike(t))
                ).limit(limite).all()
            else:
                res = db.session.query(Producto).filter(
                    (Producto.codigo_sistema.ilike(t)) |
                    (Producto.id_codigo.ilike(t)) |
                    (Producto.descripcion.ilike(t)) |
                    (Producto.oem.ilike(t))
                ).limit(limite).all()
            
            return [self._to_dict(p) for p in res]
        except Exception as e:
            logger.error(f"Error en buscar_por_termino ({self.tenant}): {e}")
            return []

    def _to_dict(self, p) -> Dict:
        """Convierte modelo SQLAlchemy a diccionario amigable para el frontend."""
        if self.tenant == "frimetals":
            # Simplificado: El campo ahora es INTEGER en DB
            precio_val = getattr(p, 'precio', 0) or 0

            return {
                'id': getattr(p, 'codigo', 'S/C'), # Usamos codigo como ID
                'codigo': getattr(p, 'codigo', 'S/C'),
                'descripcion': getattr(p, 'descripcion', 'Sin descripción'),
                'precio': "{:.2f}".format(precio_val) # Enviar como cadena limpia
            }
            
        return {
            'id': p.id,
            'CODIGO SISTEMA': p.codigo_sistema,
            'ID CODIGO': p.id_codigo,
            'DESCRIPCION': p.descripcion,
            'PRECIO': float(p.precio or 0),
            'POR PULIR': float(p.por_pulir or 0),
            'P. TERMINADO': float(p.p_terminado or 0),
            'COMPROMETIDO': float(p.comprometido or 0),
            'PRODUCTO ENSAMBLADO': float(p.producto_ensamblado or 0),
            'STOCK MINIMO': float(p.stock_minimo or 10),
            'IMAGEN': p.imagen or '',
            'OEM': p.oem or ''
        }


producto_repo = ProductoRepository(tenant="friparts")
