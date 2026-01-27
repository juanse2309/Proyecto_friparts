"""
Repositorio de dashboard.
Obtiene estadísticas y métricas.
"""
from backend.core.database import sheets_client
from backend.config.settings import Hojas
from backend.utils.formatters import to_int
import logging

logger = logging.getLogger(__name__)


class DashboardRepository:
    """Repositorio para datos del dashboard."""
    
    def obtener_estadisticas(self, filtro_fecha=None):
        """
        Obtiene estadísticas generales.
        
        Returns:
            Dict con métricas del dashboard
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
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}
    
    def _obtener_produccion(self):
        """Obtiene totales de producción."""
        try:
            ws = sheets_client.get_worksheet(Hojas.INYECCION)
            if not ws:
                return {'total': 0}
            
            registros = ws.get_all_records()
            total = sum(to_int(r.get('CANTIDAD REAL', 0)) for r in registros)
            
            return {
                'total': total,
                'registros': len(registros)
            }
        except:
            return {'total': 0}
    
    def _obtener_ventas(self):
        """Obtiene totales de ventas."""
        try:
            ws = sheets_client.get_worksheet(Hojas.FACTURACION)
            if not ws:
                return {'total': 0}
            
            registros = ws.get_all_records()
            total = sum(to_int(r.get('TOTAL VENTA', 0)) for r in registros)
            
            return {
                'total': total,
                'facturas': len(registros)
            }
        except:
            return {'total': 0}
    
    def _obtener_stock_critico(self):
        """Obtiene productos con stock bajo."""
        try:
            ws = sheets_client.get_worksheet(Hojas.PRODUCTOS)
            if not ws:
                return {'productos': []}
            
            registros = ws.get_all_records()
            criticos = []
            
            for r in registros:
                stock_total = (
                    to_int(r.get('POR PULIR', 0)) +
                    to_int(r.get('P. TERMINADO', 0))
                )
                stock_minimo = to_int(r.get('STOCK MINIMO', 10))
                
                if stock_total < stock_minimo:
                    criticos.append({
                        'codigo': r.get('CODIGO SISTEMA', ''),
                        'descripcion': r.get('DESCRIPCION', ''),
                        'stock_actual': stock_total,
                        'stock_minimo': stock_minimo
                    })
            
            return {
                'productos': criticos[:10],
                'total': len(criticos)
            }
        except:
            return {'productos': []}
    
    def _obtener_pnc_pendientes(self):
        """Obtiene PNC pendientes."""
        return {'total': 0, 'pendientes': []}


# Instancia única
dashboard_repo = DashboardRepository()