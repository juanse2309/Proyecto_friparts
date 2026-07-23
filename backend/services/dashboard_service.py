import logging
from backend.core.sql_database import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

class DashboardService:
    @staticmethod
    def generar_insights_bot_planta(kpis, stock_critico, pulido_profundo, ranking_iny_ops):
        """
        Genera el informe ejecutivo de IA del Bot de Planta con:
        1. Volumen Consolidado de Producción
        2. Desviaciones de Producción (Brechas de flujo entre Inyección y Pulido)
        3. Alertas Operativas, Financieras y de Mermas (Scrap)
        4. Top Productividad y Liderazgos Operativos
        """
        insights = []

        iny_ok = float(kpis.get('inyeccion_ok', 0) or 0)
        pul_ok = float(kpis.get('pulido_ok', 0) or 0)
        ens_ok = float(kpis.get('ensambles_ok', 0) or 0)
        total_ok = iny_ok + pul_ok + ens_ok

        # 1. Volumen Consolidado
        insights.append(
            f"VOLUMEN_CONSOLIDADO|Volumen Consolidado: Inyección {iny_ok:,.0f} Pz | Pulido {pul_ok:,.0f} Pz | Ensamble {ens_ok:,.0f} Pz. Total OK: {total_ok:,.0f} Pz."
        )

        # 2. Desviaciones de Producción (Flujo de planta)
        brecha_iny_pul = iny_ok - pul_ok
        if brecha_iny_pul > 0:
            insights.append(
                f"DESVIACION|Brecha de Producción: Inyección superó a Pulido por {brecha_iny_pul:,.0f} Pz acumuladas por pulir."
            )
        elif brecha_iny_pul < 0:
            insights.append(
                f"DESVIACION|Flujo Inverso: Pulido procesó {abs(brecha_iny_pul):,.0f} Pz provenientes de lotes en inventario WIP."
            )
        else:
            insights.append(
                f"DESVIACION|Flujo Balanceado: Balance 1:1 perfecto entre piezas inyectadas y pulidas."
            )

        # 3. Alertas Operativas y de Mermas
        costo_scrap = float(kpis.get('perdida_calidad_dinero', 0) or 0)
        total_scrap = float(kpis.get('scrap_total', 0) or 0)
        fpy = float(kpis.get('fpy_global', 99.2) or 99.2)

        if costo_scrap > 0:
            insights.append(
                f"ALERTA_SCRAP|Impacto Financiero de Mermas: ${costo_scrap:,.0f} COP perdidos por {total_scrap:,.0f} piezas de scrap (FPY: {fpy:.1f}%)."
            )

        n_critico = len(stock_critico) if isinstance(stock_critico, list) else 0
        if n_critico > 0:
            insights.append(
                f"ALERTA_STOCK|Alerta de Inventario: {n_critico} referencias están en nivel crítico por debajo del mínimo."
            )

        # 4. Líderes de Productividad
        if ranking_iny_ops and len(ranking_iny_ops) > 0:
            top_iny = ranking_iny_ops[0]
            insights.append(
                f"LIDER_INY|Líder Inyección: {top_iny.get('nombre', 'Operario')} con {float(top_iny.get('valor', 0)):,.0f} Pz OK producidas."
            )

        if pulido_profundo and isinstance(pulido_profundo, dict):
            top_pul = sorted(pulido_profundo.items(), key=lambda x: x[1].get('buenas', 0), reverse=True)
            if top_pul:
                top_pul_nombre, top_pul_data = top_pul[0]
                insights.append(
                    f"LIDER_PUL|Líder Pulido: {top_pul_nombre} con {top_pul_data.get('buenas', 0):,.0f} Pz OK ({top_pul_data.get('yield_calidad', 100)}% Yield)."
                )

        return insights

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

    @staticmethod
    def calcular_porcentajes_maquinas(ranking_maquinas):
        """
        Calcula el % de participación de cada máquina con prevención de ZeroDivisionError.
        Si la suma total de piezas es 0 o vacía, asigna 0.0% a todas las máquinas.
        """
        if not ranking_maquinas or not isinstance(ranking_maquinas, list):
            return []

        total_piezas = sum(float(m.get('valor', 0) or 0) for m in ranking_maquinas)
        
        resultado = []
        for m in ranking_maquinas:
            maq_name = str(m.get('maquina', '?')).strip()
            valor_num = float(m.get('valor', 0) or 0)
            
            if total_piezas <= 0:
                pct = 0.0
            else:
                pct = round((valor_num / total_piezas) * 100.0, 2)

            resultado.append({
                "maquina": maq_name,
                "valor": valor_num,
                "porcentaje": pct
            })

        return resultado

    @staticmethod
    def get_scrap_detalle(item_id):
        """
        Obtiene el desglose detallado del scrap/mermas para una referencia específica:
        Fecha, Máquina de origen y Cantidad.
        """
        if not item_id:
            return []
            
        try:
            from backend.utils.formatters import normalizar_codigo
            cod_norm = normalizar_codigo(str(item_id).strip())

            sql = text("""
                SELECT 
                    COALESCE(to_char(i.fecha_inicia, 'YYYY-MM-DD HH24:MI'), 'Sin fecha') as fecha,
                    COALESCE(NULLIF(TRIM(i.maquina::text), ''), 'Inyección') as maquina,
                    SUM(COALESCE(p.cantidad, 0))::numeric as cantidad
                FROM db_pnc_inyeccion p
                LEFT JOIN (
                    SELECT DISTINCT ON (id_inyeccion) id_inyeccion, fecha_inicia, maquina 
                    FROM db_inyeccion 
                    WHERE fecha_inicia IS NOT NULL
                    ORDER BY id_inyeccion, fecha_inicia DESC
                ) i ON p.id_inyeccion = i.id_inyeccion
                WHERE TRIM(UPPER(REPLACE(p.id_codigo::text, 'FR-', ''))) = :cod_norm
                  AND COALESCE(p.cantidad, 0) > 0
                GROUP BY COALESCE(to_char(i.fecha_inicia, 'YYYY-MM-DD HH24:MI'), 'Sin fecha'), COALESCE(NULLIF(TRIM(i.maquina::text), ''), 'Inyección')

                UNION ALL

                SELECT 
                    COALESCE(to_char(d.fecha, 'YYYY-MM-DD'), 'Sin fecha') as fecha,
                    'Pulido' as maquina,
                    SUM(COALESCE(p.cantidad, 0))::numeric as cantidad
                FROM db_pnc_pulido p
                LEFT JOIN db_pulido d ON p.id_pulido = d.id_pulido
                WHERE TRIM(UPPER(REPLACE(p.codigo::text, 'FR-', ''))) = :cod_norm
                  AND COALESCE(p.cantidad, 0) > 0
                GROUP BY COALESCE(to_char(d.fecha, 'YYYY-MM-DD'), 'Sin fecha')

                ORDER BY fecha DESC
                LIMIT 50
            """)

            rows = db.session.execute(sql, {"cod_norm": cod_norm}).mappings().all()
            
            return [{
                "fecha": r['fecha'],
                "maquina": r['maquina'],
                "cantidad": float(r['cantidad'] or 0)
            } for r in rows]

        except Exception as e:
            logger.error(f"Error consultando detalle de scrap para {item_id}: {e}")
            return []

    @staticmethod
    def get_productos_sin_rotacion(q=None, max_ventas=0, limit=50):
        """
        Obtiene productos de baja rotación en los últimos 12 meses.
        - max_ventas: Configurable dinámicamente de 0 a 50 unidades vendidas.
        - Stock P. Terminado: Mapeado 1:1 directo desde la sincronización oficial de World Office (inventario_wo / db_productos).
        """
        try:
            max_ventas_val = max(0, min(50, int(max_ventas or 0)))

            sql = """
                SELECT 
                    p.id,
                    COALESCE(NULLIF(TRIM(p.codigo_sistema), ''), p.id_codigo, 'S/C') as codigo,
                    COALESCE(NULLIF(TRIM(p.descripcion), ''), 'Sin descripción') as descripcion,
                    COALESCE(w.stock_wo, p.p_terminado, 0) as stock_terminado,
                    COALESCE(p.precio, 0) as precio,
                    COALESCE(v_tot.total_ventas, 0) as ventas_periodo
                FROM db_productos p
                LEFT JOIN (
                    SELECT DISTINCT ON (codigo_producto) codigo_producto, stock_wo
                    FROM inventario_wo
                    WHERE codigo_producto IS NOT NULL
                    ORDER BY codigo_producto
                ) w ON TRIM(UPPER(REPLACE(w.codigo_producto::text, 'FR-', ''))) = TRIM(UPPER(REPLACE(p.codigo_sistema::text, 'FR-', '')))
                LEFT JOIN (
                    SELECT 
                        TRIM(UPPER(REPLACE(productos::text, 'FR-', ''))) as ref,
                        SUM(COALESCE(cantidad, 0)) as total_ventas
                    FROM db_ventas
                    WHERE fecha >= (CURRENT_DATE - INTERVAL '12 months')
                    GROUP BY 1
                ) v_tot ON v_tot.ref = TRIM(UPPER(REPLACE(p.codigo_sistema::text, 'FR-', '')))
                WHERE p.codigo_sistema IS NOT NULL AND p.codigo_sistema != ''
                  AND COALESCE(v_tot.total_ventas, 0) <= :max_ventas
                  AND (
                      :q_raw != '%%' OR (
                          p.codigo_sistema ILIKE 'FR-%' OR p.codigo_sistema ILIKE 'MT-%' 
                          OR p.codigo_sistema ILIKE 'IM-%' OR p.codigo_sistema ILIKE 'DE-%'
                          OR p.id_codigo ILIKE 'FR-%' OR p.id_codigo ILIKE 'MT-%'
                      )
                  )
            """
            params = {
                'max_ventas': max_ventas_val,
                'q_raw': '%%',
                'q_norm': '%%'
            }

            if q and str(q).strip():
                q_clean = str(q).strip()
                q_norm = q_clean.upper().replace('FR-', '').strip()
                sql += """ AND (
                    p.codigo_sistema ILIKE :q_raw 
                    OR p.id_codigo ILIKE :q_raw 
                    OR p.descripcion ILIKE :q_raw
                    OR TRIM(UPPER(REPLACE(p.codigo_sistema::text, 'FR-', ''))) ILIKE :q_norm
                )"""
                params['q_raw'] = f"%{q_clean}%"
                params['q_norm'] = f"%{q_norm}%"

            sql += " ORDER BY stock_terminado DESC, p.id ASC LIMIT :limit"
            params['limit'] = limit

            logger.info(f"🔍 [get_productos_sin_rotacion] Consultando catálogo 100% con max_ventas={max_ventas_val}, q='{q or ''}'")
            rows = db.session.execute(text(sql), params).mappings().all()
            logger.info(f"✅ [get_productos_sin_rotacion] Filas obtenidas tras filtro: {len(rows)}")

            resultado = [{
                "id": r['id'],
                "codigo": r['codigo'],
                "descripcion": r['descripcion'],
                "stock": float(r['stock_terminado'] or 0),
                "stock_terminado": float(r['stock_terminado'] or 0),
                "precio": float(r['precio'] or 0),
                "ventas_periodo": float(r['ventas_periodo'] or 0)
            } for r in rows]

            return {
                "total": len(resultado),
                "max_ventas_aplicado": max_ventas_val,
                "productos": resultado
            }
        except Exception as e:
            logger.error(f"Error consultando productos sin/baja rotación: {e}")
            return {"total": 0, "productos": []}
