"""
Repositorio de dashboard 100% SQL-First.
Obtiene estadísticas y métricas desde PostgreSQL.
"""
from backend.core.sql_database import db
from backend.models.sql_models import ProduccionInyeccion, RawVentas, Producto
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)


class DashboardRepository:
    """Repositorio para datos del dashboard vía SQLAlchemy."""
    
    def obtener_estadisticas(self, filtro_fecha=None):
        """
        Obtiene estadísticas generales desde SQL.
        """
        try:
            estadisticas = {
                'produccion': self._obtener_produccion(),
                'ventas': self._obtener_ventas(),
                'stock': self._obtener_stock_critico(),
                'pnc': self._obtener_pnc_pendientes()
            }
            return estadisticas
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas SQL: {e}")
            return {}
    
    def _obtener_produccion(self):
        """Obtiene totales de producción desde db_inyeccion."""
        try:
            # Sumar cantidad_real de la tabla de inyección
            total = db.session.query(func.sum(ProduccionInyeccion.cantidad_real)).scalar() or 0
            conteo = db.session.query(func.count(ProduccionInyeccion.id)).scalar() or 0
            
            return {
                'total': int(total),
                'registros': conteo
            }
        except Exception as e:
            logger.error(f"Error produccion SQL: {e}")
            return {'total': 0, 'registros': 0}
    
    def _obtener_ventas(self):
        """Obtiene totales de ventas desde db_ventas."""
        try:
            total = db.session.query(func.sum(RawVentas.total_ingresos)).scalar() or 0
            facturas = db.session.query(func.count(RawVentas.id)).scalar() or 0
            
            return {
                'total': float(total),
                'facturas': facturas
            }
        except Exception as e:
            logger.error(f"Error ventas SQL: {e}")
            return {'total': 0, 'facturas': 0}
    
    def _obtener_stock_critico(self):
        """Obtiene productos con stock bajo desde db_productos."""
        try:
            # Productos donde (p_terminado + por_pulir) - comprometido < stock_minimo
            productos_criticos = db.session.query(Producto).filter(
                (Producto.p_terminado + Producto.por_pulir - Producto.comprometido) < Producto.stock_minimo
            ).limit(10).all()
            
            criticos = []
            for p in productos_criticos:
                stock_actual = float((p.p_terminado or 0) + (p.por_pulir or 0) - (p.comprometido or 0))
                criticos.append({
                    'codigo': p.codigo_sistema,
                    'descripcion': p.descripcion,
                    'stock_actual': stock_actual,
                    'stock_minimo': float(p.stock_minimo or 0)
                })
            
            total_criticos = db.session.query(func.count(Producto.id)).filter(
                (Producto.p_terminado + Producto.por_pulir - Producto.comprometido) < Producto.stock_minimo
            ).scalar() or 0
            
            return {
                'productos': criticos,
                'total': total_criticos
            }
        except Exception as e:
            logger.error(f"Error stock SQL: {e}")
            return {'productos': [], 'total': 0}
    
    def _obtener_pnc_pendientes(self):
        """Métrica de PNC pendiente (Placeholder por ahora)."""
        return {'total': 0, 'pendientes': []}


# Instancia única
dashboard_repo = DashboardRepository()