import logging
from sqlalchemy import text
from backend.core.sql_database import db

logger = logging.getLogger(__name__)

class ComercialHistoricoService:
    """
    Servicio de extracción y analítica comercial histórica.
    Garantiza aislamiento estricto por rol, cardinalidad 1:1 en atribución comercial,
    y fidelidad contable restando devoluciones (Notas Crédito) directamente en PostgreSQL.
    """

    @staticmethod
    def obtener_analitica_historica(user_id: int, username: str, user_role: str, start_year: int = 2024, end_year: int = 2026) -> dict:
        """
        Extrae datos consolidados de ventas (Año, Mes, Zona, Cliente) entre start_year y end_year.
        Resta devoluciones/NC y garantiza cardinalidad 1:1 en el LEFT JOIN de db_pedidos.
        """
        role_upper = str(user_role or '').strip().upper()
        # Admins y Gerencia tienen vista global. Comercial se restringe a sus registros.
        es_global = role_upper in ['ADMIN', 'ADMINISTRACION', 'ADMINISTRADOR', 'GERENCIA']
        es_comercial = not es_global

        query = text("""
            SELECT 
                EXTRACT(YEAR FROM v.fecha)::INTEGER                      AS anio,
                EXTRACT(MONTH FROM v.fecha)::INTEGER                     AS mes,
                COALESCE(NULLIF(TRIM(c.ciudad), ''), 'SIN ZONA')        AS zona,
                COALESCE(NULLIF(TRIM(v.nombres), ''), 'CLIENTE DESCONOCIDO') AS cliente,
                ROUND(SUM(
                    CASE 
                        WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%' 
                          OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%' 
                        THEN -ABS(COALESCE(v.total_ingresos, 0))
                        ELSE COALESCE(v.total_ingresos, 0)
                    END
                )::NUMERIC, 2) AS total_ventas,
                ROUND(SUM(
                    CASE 
                        WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%' 
                          OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%' 
                        THEN -ABS(COALESCE(v.cantidad, 0))
                        ELSE COALESCE(v.cantidad, 0)
                    END
                )::NUMERIC, 2) AS total_unidades,
                COUNT(v.id)::INTEGER                                     AS total_transacciones
            FROM db_ventas v
            LEFT JOIN db_clientes c 
                   ON TRIM(UPPER(v.nombres)) = TRIM(UPPER(c.nombre))
            LEFT JOIN (
                SELECT TRIM(UPPER(cliente)) AS cliente_norm, MAX(vendedor) AS vendedor 
                FROM db_pedidos 
                WHERE vendedor IS NOT NULL AND vendedor != ''
                GROUP BY TRIM(UPPER(cliente))
            ) p ON TRIM(UPPER(v.nombres)) = p.cliente_norm
            WHERE v.fecha >= MAKE_DATE(:start_year, 1, 1) 
              AND v.fecha <= MAKE_DATE(:end_year, 12, 31)
              AND (:es_comercial = FALSE OR TRIM(UPPER(COALESCE(p.vendedor, ''))) LIKE '%' || TRIM(UPPER(:vendedor_user)) || '%')
            GROUP BY 
                EXTRACT(YEAR FROM v.fecha),
                EXTRACT(MONTH FROM v.fecha),
                COALESCE(NULLIF(TRIM(c.ciudad), ''), 'SIN ZONA'),
                COALESCE(NULLIF(TRIM(v.nombres), ''), 'CLIENTE DESCONOCIDO')
            ORDER BY 
                anio ASC, 
                mes ASC, 
                total_ventas DESC;
        """)

        params = {
            'start_year': int(start_year),
            'end_year': int(end_year),
            'es_comercial': es_comercial,
            'vendedor_user': str(username or '')
        }

        try:
            result = db.session.execute(query, params)
            rows = [dict(row) for row in result.mappings().all()]
        except Exception as e:
            logger.error(f"[COMERCIAL_SERVICE] Error ejecutando consulta histórica: {e}")
            raise e

        # Agregaciones secundarias con deducción de NC para gráficos y resúmenes ejecutivos
        query_resumen = text("""
            SELECT 
                EXTRACT(YEAR FROM v.fecha)::INTEGER                      AS anio,
                ROUND(SUM(
                    CASE 
                        WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%' 
                          OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%' 
                        THEN -ABS(COALESCE(v.total_ingresos, 0))
                        ELSE COALESCE(v.total_ingresos, 0)
                    END
                )::NUMERIC, 2) AS total_ventas,
                ROUND(SUM(
                    CASE 
                        WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%' 
                          OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%' 
                        THEN -ABS(COALESCE(v.cantidad, 0))
                        ELSE COALESCE(v.cantidad, 0)
                    END
                )::NUMERIC, 2) AS total_unidades,
                COUNT(v.id)::INTEGER                                     AS total_transacciones
            FROM db_ventas v
            LEFT JOIN (
                SELECT TRIM(UPPER(cliente)) AS cliente_norm, MAX(vendedor) AS vendedor 
                FROM db_pedidos 
                WHERE vendedor IS NOT NULL AND vendedor != ''
                GROUP BY TRIM(UPPER(cliente))
            ) p ON TRIM(UPPER(v.nombres)) = p.cliente_norm
            WHERE v.fecha >= MAKE_DATE(:start_year, 1, 1) 
              AND v.fecha <= MAKE_DATE(:end_year, 12, 31)
              AND (:es_comercial = FALSE OR TRIM(UPPER(COALESCE(p.vendedor, ''))) LIKE '%' || TRIM(UPPER(:vendedor_user)) || '%')
            GROUP BY EXTRACT(YEAR FROM v.fecha)
            ORDER BY anio ASC;
        """)

        query_zonas = text("""
            SELECT 
                COALESCE(NULLIF(TRIM(c.ciudad), ''), 'SIN ZONA')        AS zona,
                ROUND(SUM(
                    CASE 
                        WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%' 
                          OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%' 
                        THEN -ABS(COALESCE(v.total_ingresos, 0))
                        ELSE COALESCE(v.total_ingresos, 0)
                    END
                )::NUMERIC, 2) AS total_ventas,
                ROUND(SUM(
                    CASE 
                        WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%' 
                          OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%' 
                        THEN -ABS(COALESCE(v.cantidad, 0))
                        ELSE COALESCE(v.cantidad, 0)
                    END
                )::NUMERIC, 2) AS total_unidades
            FROM db_ventas v
            LEFT JOIN db_clientes c 
                   ON TRIM(UPPER(v.nombres)) = TRIM(UPPER(c.nombre))
            LEFT JOIN (
                SELECT TRIM(UPPER(cliente)) AS cliente_norm, MAX(vendedor) AS vendedor 
                FROM db_pedidos 
                WHERE vendedor IS NOT NULL AND vendedor != ''
                GROUP BY TRIM(UPPER(cliente))
            ) p ON TRIM(UPPER(v.nombres)) = p.cliente_norm
            WHERE v.fecha >= MAKE_DATE(:start_year, 1, 1) 
              AND v.fecha <= MAKE_DATE(:end_year, 12, 31)
              AND (:es_comercial = FALSE OR TRIM(UPPER(COALESCE(p.vendedor, ''))) LIKE '%' || TRIM(UPPER(:vendedor_user)) || '%')
            GROUP BY COALESCE(NULLIF(TRIM(c.ciudad), ''), 'SIN ZONA')
            ORDER BY total_ventas DESC;
        """)

        query_top_clientes = text("""
            SELECT 
                COALESCE(NULLIF(TRIM(v.nombres), ''), 'CLIENTE DESCONOCIDO') AS cliente,
                ROUND(SUM(
                    CASE 
                        WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%' 
                          OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%' 
                        THEN -ABS(COALESCE(v.total_ingresos, 0))
                        ELSE COALESCE(v.total_ingresos, 0)
                    END
                )::NUMERIC, 2) AS total_ventas,
                ROUND(SUM(
                    CASE 
                        WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%' 
                          OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%' 
                        THEN -ABS(COALESCE(v.cantidad, 0))
                        ELSE COALESCE(v.cantidad, 0)
                    END
                )::NUMERIC, 2) AS total_unidades
            FROM db_ventas v
            LEFT JOIN (
                SELECT TRIM(UPPER(cliente)) AS cliente_norm, MAX(vendedor) AS vendedor 
                FROM db_pedidos 
                WHERE vendedor IS NOT NULL AND vendedor != ''
                GROUP BY TRIM(UPPER(cliente))
            ) p ON TRIM(UPPER(v.nombres)) = p.cliente_norm
            WHERE v.fecha >= MAKE_DATE(:start_year, 1, 1) 
              AND v.fecha <= MAKE_DATE(:end_year, 12, 31)
              AND (:es_comercial = FALSE OR TRIM(UPPER(COALESCE(p.vendedor, ''))) LIKE '%' || TRIM(UPPER(:vendedor_user)) || '%')
            GROUP BY COALESCE(NULLIF(TRIM(v.nombres), ''), 'CLIENTE DESCONOCIDO')
            ORDER BY total_ventas DESC
            LIMIT 50;
        """)

        resumen_anual = [dict(r) for r in db.session.execute(query_resumen, params).mappings().all()]
        resumen_zonas = [dict(r) for r in db.session.execute(query_zonas, params).mappings().all()]
        top_clientes = [dict(r) for r in db.session.execute(query_top_clientes, params).mappings().all()]

        return {
            'success': True,
            'periodo': {
                'start_year': start_year,
                'end_year': end_year
            },
            'seguridad': {
                'vista_global': es_global,
                'usuario': username
            },
            'resumen_anual': resumen_anual,
            'resumen_zonas': resumen_zonas,
            'top_clientes': top_clientes,
            'detalle_agrupado': rows
        }
