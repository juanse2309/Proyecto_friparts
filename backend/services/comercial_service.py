import logging
import re
from datetime import datetime, date
from sqlalchemy import text
from backend.core.sql_database import db

logger = logging.getLogger(__name__)

# Aislamiento estricto por igualdad exacta (no LIKE): permite uso de indice B-Tree
# sobre db_ventas.vendedor y evita falsos positivos entre nombres similares.
FILTRO_SCOPE_ROL = "(:es_comercial = FALSE OR UPPER(TRIM(COALESCE(v.vendedor, ''))) = UPPER(TRIM(:vendedor_user)))"
FILTRO_VENDEDOR_OPCIONAL = "(:vendedor_filtro = '' OR UPPER(TRIM(COALESCE(v.vendedor, ''))) = UPPER(TRIM(:vendedor_filtro)))"


class ComercialHistoricoService:
    """
    Servicio de extracción y analítica comercial histórica.
    Lee vendedor y zona de forma plana desde las columnas nativas de db_ventas
    (pobladas por World Office: Nombres_tercero_interno / Ciudad_Encabezado).
    Garantiza aislamiento estricto por rol y fidelidad contable restando
    devoluciones (Notas Crédito) directamente en PostgreSQL.
    """

    @staticmethod
    def _expr_ajustado_nc(columna: str) -> str:
        """CASE que invierte el signo de `columna` cuando el registro es una Nota Crédito."""
        return f"""
            CASE
                WHEN UPPER(TRIM(COALESCE(v.clasificacion, ''))) LIKE '%NC%'
                  OR UPPER(TRIM(COALESCE(v.documento, ''))) LIKE '%NC%'
                THEN -ABS(COALESCE(v.{columna}, 0))
                ELSE COALESCE(v.{columna}, 0)
            END
        """

    @staticmethod
    def _resolver_alias_vendedor(user_id: int, username: str) -> str:
        """
        Resuelve el valor a comparar contra db_ventas.vendedor (match exacto):
        prioriza db_usuarios.alias_vendedor_wo (nombre tal como lo escribe World
        Office) y cae al nombre de login si el alias no está configurado.
        """
        try:
            from backend.models.sql_models import Usuario
            if user_id is not None:
                usuario = Usuario.query.get(int(user_id))
                if usuario and usuario.alias_vendedor_wo and usuario.alias_vendedor_wo.strip():
                    return usuario.alias_vendedor_wo.strip()
        except Exception as e:
            logger.warning(f"[COMERCIAL_SERVICE] No se pudo resolver alias_vendedor_wo para user_id={user_id}: {e}")
        return str(username or '')

    @staticmethod
    def _resolver_fecha_corte(fecha_corte_raw) -> date:
        """
        Valida y convierte fecha_corte a un date real. Si no viene o es invalida,
        usa hoy. Nunca deja pasar un string sin validar hacia la consulta SQL.
        """
        if fecha_corte_raw:
            try:
                return datetime.strptime(str(fecha_corte_raw)[:10], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                logger.warning(f"[COMERCIAL_SERVICE] fecha_corte inválida recibida: {fecha_corte_raw!r}. Usando hoy.")
        return datetime.now().date()

    @staticmethod
    def obtener_analitica_historica(user_id: int, username: str, user_role: str, start_year: int = 2024, end_year: int = 2026) -> dict:
        """
        Extrae datos consolidados de ventas (Año, Mes, Zona, Cliente) entre start_year y end_year.
        Resta devoluciones/NC. Vendedor y zona se leen directo de db_ventas (sin JOIN).
        """
        role_upper = str(user_role or '').strip().upper()
        es_global = role_upper in ['ADMIN', 'ADMINISTRACION', 'ADMINISTRADOR', 'GERENCIA']
        es_comercial = not es_global

        ventas_expr = ComercialHistoricoService._expr_ajustado_nc('total_ingresos')
        cantidad_expr = ComercialHistoricoService._expr_ajustado_nc('cantidad')
        vendedor_scope = ComercialHistoricoService._resolver_alias_vendedor(user_id, username)

        params = {
            'start_year': int(start_year),
            'end_year': int(end_year),
            'es_comercial': es_comercial,
            'vendedor_user': vendedor_scope,
            'vendedor_filtro': ''  # sin acotar adicionalmente en esta vista
        }

        query = text(f"""
            SELECT
                EXTRACT(YEAR FROM v.fecha)::INTEGER AS anio,
                EXTRACT(MONTH FROM v.fecha)::INTEGER AS mes,
                COALESCE(NULLIF(TRIM(v.zona), ''), 'SIN ZONA') AS zona,
                COALESCE(NULLIF(TRIM(v.nombres), ''), 'CLIENTE DESCONOCIDO') AS cliente,
                ROUND(SUM({ventas_expr})::NUMERIC, 2) AS total_ventas,
                ROUND(SUM({cantidad_expr})::NUMERIC, 2) AS total_unidades,
                COUNT(v.id)::INTEGER AS total_transacciones
            FROM db_ventas v
            WHERE v.fecha >= MAKE_DATE(:start_year, 1, 1)
              AND v.fecha <= MAKE_DATE(:end_year, 12, 31)
              AND {FILTRO_SCOPE_ROL}
              AND {FILTRO_VENDEDOR_OPCIONAL}
            GROUP BY 1, 2, 3, 4
            ORDER BY anio ASC, mes ASC, total_ventas DESC;
        """)

        try:
            rows = [dict(r) for r in db.session.execute(query, params).mappings().all()]
        except Exception as e:
            logger.error(f"[COMERCIAL_SERVICE] Error ejecutando consulta histórica: {e}")
            raise e

        query_resumen = text(f"""
            SELECT
                EXTRACT(YEAR FROM v.fecha)::INTEGER AS anio,
                ROUND(SUM({ventas_expr})::NUMERIC, 2) AS total_ventas,
                ROUND(SUM({cantidad_expr})::NUMERIC, 2) AS total_unidades,
                COUNT(v.id)::INTEGER AS total_transacciones
            FROM db_ventas v
            WHERE v.fecha >= MAKE_DATE(:start_year, 1, 1)
              AND v.fecha <= MAKE_DATE(:end_year, 12, 31)
              AND {FILTRO_SCOPE_ROL}
              AND {FILTRO_VENDEDOR_OPCIONAL}
            GROUP BY EXTRACT(YEAR FROM v.fecha)
            ORDER BY anio ASC;
        """)

        query_zonas = text(f"""
            SELECT
                COALESCE(NULLIF(TRIM(v.zona), ''), 'SIN ZONA') AS zona,
                ROUND(SUM({ventas_expr})::NUMERIC, 2) AS total_ventas,
                ROUND(SUM({cantidad_expr})::NUMERIC, 2) AS total_unidades
            FROM db_ventas v
            WHERE v.fecha >= MAKE_DATE(:start_year, 1, 1)
              AND v.fecha <= MAKE_DATE(:end_year, 12, 31)
              AND {FILTRO_SCOPE_ROL}
              AND {FILTRO_VENDEDOR_OPCIONAL}
            GROUP BY COALESCE(NULLIF(TRIM(v.zona), ''), 'SIN ZONA')
            ORDER BY total_ventas DESC;
        """)

        query_top_clientes = text(f"""
            SELECT
                COALESCE(NULLIF(TRIM(v.nombres), ''), 'CLIENTE DESCONOCIDO') AS cliente,
                ROUND(SUM({ventas_expr})::NUMERIC, 2) AS total_ventas,
                ROUND(SUM({cantidad_expr})::NUMERIC, 2) AS total_unidades
            FROM db_ventas v
            WHERE v.fecha >= MAKE_DATE(:start_year, 1, 1)
              AND v.fecha <= MAKE_DATE(:end_year, 12, 31)
              AND {FILTRO_SCOPE_ROL}
              AND {FILTRO_VENDEDOR_OPCIONAL}
            GROUP BY COALESCE(NULLIF(TRIM(v.nombres), ''), 'CLIENTE DESCONOCIDO')
            ORDER BY total_ventas DESC
            LIMIT 50;
        """)

        resumen_anual = [dict(r) for r in db.session.execute(query_resumen, params).mappings().all()]
        resumen_zonas = [dict(r) for r in db.session.execute(query_zonas, params).mappings().all()]
        top_clientes = [dict(r) for r in db.session.execute(query_top_clientes, params).mappings().all()]

        return {
            'success': True,
            'periodo': {'start_year': start_year, 'end_year': end_year},
            'seguridad': {'vista_global': es_global, 'usuario': username},
            'resumen_anual': resumen_anual,
            'resumen_zonas': resumen_zonas,
            'top_clientes': top_clientes,
            'detalle_agrupado': rows
        }

    @staticmethod
    def _query_ytd(user_id: int, username: str, user_role: str, start_year: int, end_year: int,
                    vendedor_filtro: str, corte_dt: date):
        """
        Ejecuta las 2 consultas de agregación YTD (anual y por zona) 100% en SQL.
        El corte YTD compara (mes, dia) por tupla para ser exacto entre años
        bisiestos y no bisiestos (evita el corrimiento que introduce DOY tras el 29-feb).
        """
        role_upper = str(user_role or '').strip().upper()
        es_global = role_upper in ['ADMIN', 'ADMINISTRACION', 'ADMINISTRADOR', 'GERENCIA']
        es_comercial = not es_global

        ventas_expr = ComercialHistoricoService._expr_ajustado_nc('total_ingresos')
        cantidad_expr = ComercialHistoricoService._expr_ajustado_nc('cantidad')
        vendedor_scope = ComercialHistoricoService._resolver_alias_vendedor(user_id, username)

        params = {
            'start_year': int(start_year),
            'end_year': int(end_year),
            'es_comercial': es_comercial,
            'vendedor_user': vendedor_scope,
            'vendedor_filtro': str(vendedor_filtro or '').strip(),
            'corte_dt': corte_dt
        }

        where_ytd = f"""
            WHERE EXTRACT(YEAR FROM v.fecha)::INTEGER BETWEEN :start_year AND :end_year
              AND (EXTRACT(MONTH FROM v.fecha), EXTRACT(DAY FROM v.fecha))
                  <= (EXTRACT(MONTH FROM :corte_dt), EXTRACT(DAY FROM :corte_dt))
              AND {FILTRO_SCOPE_ROL}
              AND {FILTRO_VENDEDOR_OPCIONAL}
        """

        query_anual = text(f"""
            SELECT
                EXTRACT(YEAR FROM v.fecha)::INTEGER AS anio,
                ROUND(SUM({ventas_expr})::NUMERIC, 2) AS total_ventas,
                ROUND(SUM({cantidad_expr})::NUMERIC, 2) AS total_unidades,
                COUNT(v.id)::INTEGER AS total_transacciones
            FROM db_ventas v
            {where_ytd}
            GROUP BY EXTRACT(YEAR FROM v.fecha)
            ORDER BY anio ASC;
        """)

        query_zona = text(f"""
            SELECT
                EXTRACT(YEAR FROM v.fecha)::INTEGER AS anio,
                COALESCE(NULLIF(TRIM(v.zona), ''), 'SIN ZONA') AS zona,
                ROUND(SUM({ventas_expr})::NUMERIC, 2) AS total_ventas,
                ROUND(SUM({cantidad_expr})::NUMERIC, 2) AS total_unidades,
                COUNT(v.id)::INTEGER AS total_transacciones
            FROM db_ventas v
            {where_ytd}
            GROUP BY 1, 2
            ORDER BY zona ASC, anio ASC;
        """)

        try:
            ytd_anual = [dict(r) for r in db.session.execute(query_anual, params).mappings().all()]
            ytd_zona = [dict(r) for r in db.session.execute(query_zona, params).mappings().all()]
        except Exception as e:
            logger.error(f"[COMERCIAL_SERVICE] Error generando agregación YTD: {e}")
            raise e

        return ytd_anual, ytd_zona, es_global

    @staticmethod
    def generar_excel_ytd_stream(user_id: int, username: str, user_role: str, start_year: int, end_year: int,
                                  vendedor_filtro: str = '', fecha_corte=None):
        """
        Genera el .xlsx de analítica comercial YTD/Y-o-Y y devuelve (buffer, nombre_archivo)
        listo para pasarle a send_file. Encapsula toda la dependencia de pandas/openpyxl
        para que el controlador quede limpio.
        """
        import pandas as pd
        import io

        corte_dt = ComercialHistoricoService._resolver_fecha_corte(fecha_corte)

        ytd_anual, ytd_zona, _ = ComercialHistoricoService._query_ytd(
            user_id=user_id, username=username, user_role=user_role,
            start_year=start_year, end_year=end_year,
            vendedor_filtro=vendedor_filtro, corte_dt=corte_dt
        )

        df_anual = pd.DataFrame(ytd_anual)
        df_zona = pd.DataFrame(ytd_zona)

        # Reshape puro (no reagrega nada): pivotea filas ya sumadas por SQL para lectura Y-o-Y.
        if not df_zona.empty:
            pivot_yoy = df_zona.pivot_table(index='zona', columns='anio', values='total_ventas', fill_value=0)
        else:
            pivot_yoy = pd.DataFrame()

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_anual.to_excel(writer, index=False, sheet_name='YTD Anual')
            df_zona.to_excel(writer, index=False, sheet_name='YTD por Zona')
            pivot_yoy.to_excel(writer, sheet_name='YoY Zona (Pivot)')
        output.seek(0)

        vendedor_slug = re.sub(r'[^A-Za-z0-9_-]+', '_', vendedor_filtro.strip())[:40] if vendedor_filtro else 'GLOBAL'
        nombre_archivo = f"Comercial_YTD_{start_year}-{end_year}_{vendedor_slug}_{corte_dt.isoformat()}.xlsx"

        return output, nombre_archivo
