-- Vista materializada: pre-agrega db_ventas por (cliente_resuelto, producto) para
-- alimentar Backorder, Top Productos y Peores Productos del panel de Jefatura
-- (/api/admin/dashboard) sin filtro de fecha, que es el caso de uso por defecto.
--
-- Resuelve DENTRO de la vista el JOIN de alias de cliente (db_cliente_equivalencias)
-- y el filtro NOT ILIKE '%FRIPARTS%' que en la query en vivo forzaban un Seq Scan +
-- HashAggregate de ~7s sobre 100k+ filas de db_ventas en cada carga del dashboard
-- (medido con EXPLAIN ANALYZE). Al recalcularse solo en el refresh, esas ~7s pasan
-- de ocurrir en cada carga del dashboard a ocurrir una vez por sincronización de WO.
--
-- Se refresca con REFRESH MATERIALIZED VIEW CONCURRENTLY al terminar cada
-- sincronización exitosa de World Office — ver backend/routes/wo_routes.py
-- (endpoints /api/wo/recibir_comercial y /api/wo/sincronizar_automatica).
--
-- Cuando el usuario filtra el panel de Jefatura por rango de fechas, el repositorio
-- (dashboard_repository.py) NO usa esta vista (no tiene granularidad diaria) y cae
-- al camino en vivo sobre db_ventas para no romper ese filtro.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dashboard_ventas_analitica AS
SELECT
    CASE WHEN UPPER(TRIM(b.nombres)) ILIKE '%DISTRIBUJES%'
         THEN 'FELIPE DUARTE MORENO'
         ELSE COALESCE(e.nombre_canonical, b.nombres)
    END AS nombres,
    b.productos AS producto,
    SUM(CASE WHEN b.clasificacion ILIKE '%pedido%' THEN COALESCE(b.cantidad, 0) ELSE 0 END) AS pedidos_qty,
    SUM(CASE WHEN b.clasificacion ILIKE '%venta%'  THEN COALESCE(b.cantidad, 0) ELSE 0 END) AS ventas_qty,
    SUM(CASE WHEN b.clasificacion ILIKE '%venta%'  THEN COALESCE(b.total_ingresos, 0) ELSE 0 END) AS ventas_dinero,
    MAX(COALESCE(b.precio_promedio, 0)) AS avg_price
FROM db_ventas b
LEFT JOIN db_cliente_equivalencias e
    ON UPPER(TRIM(b.nombres)) = UPPER(TRIM(e.alias))
WHERE UPPER(TRIM(b.nombres)) NOT ILIKE '%FRIPARTS%'
GROUP BY 1, 2;

-- Obligatorio para poder usar REFRESH MATERIALIZED VIEW CONCURRENTLY (permite que el
-- dashboard siga leyendo la vista mientras se refresca tras una sincronizacion de WO,
-- en vez de bloquear lecturas durante el refresh).
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dashboard_ventas_analitica_pk
    ON mv_dashboard_ventas_analitica (nombres, producto);
