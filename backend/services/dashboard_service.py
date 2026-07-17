import logging
from backend.core.sql_database import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

class DashboardService:
    @staticmethod
    def get_cartera_wo_stats():
        """
        Obtiene los indicadores principales de la tabla cartera_wo (World Office)
        Maneja fallos de conexión o excepciones devolviendo diccionarios vacíos por defecto.
        """
        try:
            # Totales calculados dinámicamente sobre el detalle (Zona Horaria Colombia)
            query_totales = text("""
                SELECT 
                    COALESCE(SUM(saldo_documento), 0), 
                    COALESCE(SUM(CASE WHEN fecha_vencimiento < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Bogota')::date THEN saldo_documento ELSE 0 END), 0) 
                FROM cartera_wo
            """)
            totales = db.session.execute(query_totales).fetchone()
            
            total_cartera = float(totales[0]) if totales else 0.0
            total_vencida = float(totales[1]) if totales else 0.0
            
            # Clientes críticos: Agrupando las facturas vencidas por cliente
            query_top = text("""
                SELECT nombre, SUM(CASE WHEN fecha_vencimiento < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Bogota')::date THEN saldo_documento ELSE 0 END) as saldo_vencido 
                FROM cartera_wo 
                GROUP BY nombre 
                HAVING SUM(CASE WHEN fecha_vencimiento < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Bogota')::date THEN saldo_documento ELSE 0 END) > 0 
                ORDER BY saldo_vencido DESC 
                LIMIT 5
            """)
            top_clientes = [{"nombre": row[0], "saldo_vencido": float(row[1])} for row in db.session.execute(query_top).fetchall()]
            
            return {
                "total_cartera": total_cartera,
                "total_vencida": total_vencida,
                "clientes_criticos": top_clientes
            }
        except Exception as e:
            logger.error(f"Error consultando métricas de cartera: {e}")
            # Retorno seguro (default values) en caso de fallo
            return {
                "total_cartera": 0.0,
                "total_vencida": 0.0,
                "clientes_criticos": []
            }
