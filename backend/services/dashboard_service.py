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

    @staticmethod
    def get_rendimiento():
        """
        Devuelve el desglose de rendimiento de los últimos 12 meses con el índice del mes actual.
        """
        try:
            from backend.core.repository_service import repository_service
            import datetime
            now = datetime.datetime.now()
            current_month = now.month
            current_year = now.year
            
            mensual_data = repository_service.get_rendimiento_mensual_sql()
            
            rendimiento = []
            mes_actual_idx = 0
            
            # mensual_data contains data mapping from 1 to 12
            for idx, item in enumerate(mensual_data):
                p_monto = float(item.get('actual_pedidos') or 0)
                v_monto = float(item.get('actual_dinero') or 0)
                p_und = float(item.get('actual_pedidos_unidades') or 0)
                v_und = float(item.get('actual_unidades') or 0)
                
                pct_monto = (v_monto / p_monto * 100) if p_monto > 0 else 0.0
                pct_unidades = (v_und / p_und * 100) if p_und > 0 else 0.0
                
                rendimiento.append({
                    "mes": item.get('mes', str(idx+1)),
                    "anio": current_year,
                    "ventas_monto": v_monto,
                    "pedidos_monto": p_monto,
                    "ventas_unidades": v_und,
                    "pedidos_unidades": p_und,
                    "pct_cumplimiento_monto": round(float(pct_monto), 2),
                    "pct_cumplimiento_unidades": round(float(pct_unidades), 2)
                })
                
                if (idx + 1) == current_month:
                    mes_actual_idx = idx

            return {
                "mes_actual_idx": mes_actual_idx,
                "data": rendimiento
            }
            
        except Exception as e:
            logger.error(f"Error consultando rendimiento: {e}")
            return {"mes_actual_idx": 0, "data": []}
