"""
Migración: índices funcionales para las comparaciones de código normalizado
que ya se usan en filtros WHERE, pero que hasta ahora no podían usar ningún
índice porque el índice existente cubre la columna cruda, no la expresión.

Afecta dos expresiones distintas ya usadas en el código:

1. sql_expr_codigo_sin_prefijo_fr() (backend/utils/formatters.py) --
   REPLACE(UPPER(TRIM(columna)), 'FR-', '') -- usada en:
     - InyeccionService.registrar_lote (backend/services/inyeccion_service.py)
       sobre db_inyeccion.id_codigo, en el hot path de cada registro de
       producción.
     - pedidos_routes.py sobre db_pedidos.id_codigo.

2. El PREFIX_PATTERN de productos_routes.py (listar_productos) --
   REGEXP_REPLACE(columna, '^(FR-|CAR-|INT-|ENS-|CB-|DE-|HR-|KIT-|AL-)', '', 'i')
   -- usada sobre db_productos.id_codigo y db_precio_venta.codigo en el JOIN
   de precios del catálogo completo.

También agrega un índice (no funcional) sobre
db_trazabilidad_lotes.estado_actual, el campo de filtrado central del ciclo
de vida del lote (ABIERTO_PRODUCCION -> EN_PULIDO -> PENDIENTE_VALIDACION ->
APROBADO_CERRADO) que hasta ahora no tenía índice propio.

No destructiva: CREATE INDEX CONCURRENTLY IF NOT EXISTS en todos los casos.
CONCURRENTLY evita el lock de escritura que un CREATE INDEX normal tomaría
sobre tablas que reciben escrituras constantes en horario de planta (no se
puede envolver en una transacción normal, por eso se corre en modo
autocommit sobre una conexión aparte del engine).
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

INDICES = [
    (
        "idx_db_inyeccion_id_codigo_sin_fr",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_db_inyeccion_id_codigo_sin_fr "
        "ON db_inyeccion (REPLACE(UPPER(TRIM(id_codigo)), 'FR-', ''))"
    ),
    (
        "idx_db_pedidos_id_codigo_sin_fr",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_db_pedidos_id_codigo_sin_fr "
        "ON db_pedidos (REPLACE(UPPER(TRIM(id_codigo)), 'FR-', ''))"
    ),
    (
        "idx_db_productos_id_codigo_norm",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_db_productos_id_codigo_norm "
        "ON db_productos (REGEXP_REPLACE(id_codigo, '^(FR-|CAR-|INT-|ENS-|CB-|DE-|HR-|KIT-|AL-)', '', 'i'))"
    ),
    (
        "idx_db_precio_venta_codigo_norm",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_db_precio_venta_codigo_norm "
        "ON db_precio_venta (REGEXP_REPLACE(codigo, '^(FR-|CAR-|INT-|ENS-|CB-|DE-|HR-|KIT-|AL-)', '', 'i'))"
    ),
    (
        "idx_db_trazabilidad_lotes_estado_actual",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_db_trazabilidad_lotes_estado_actual "
        "ON db_trazabilidad_lotes (estado_actual)"
    ),
]

with app.app_context():
    conn = db.engine.connect()
    conn = conn.execution_options(isolation_level="AUTOCOMMIT")
    try:
        for nombre, sql in INDICES:
            try:
                conn.execute(text(sql))
                print(f"OK: {nombre}")
            except Exception as e:
                print(f"ERROR creando {nombre}: {e}")
    finally:
        conn.close()
