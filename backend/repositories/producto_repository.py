"""
Repositorio de productos 100% SQL-First.
Centraliza el acceso a la tabla db_productos en PostgreSQL.
"""
from typing import Optional, List, Dict
from sqlalchemy import func, text
from backend.core.sql_database import db, rollback_seguro
from backend.models.sql_models import Producto, MetalsProducto
from backend.utils.numeric_helpers import _safe_float
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
    
    def actualizar_saldo(self, codigo: str, nuevo_stock: float, almacen: str) -> bool:
        """
        Setter de capa de datos: fija el valor ABSOLUTO final de una columna
        de stock y hace commit() de inmediato (no componible con otras
        operaciones de la misma transacción).

        Distinto de `StockService.actualizar_stock` (backend/services/stock_service.py),
        que ajusta por DELTA (suma/resta) y usa flush() para poder encadenarse
        dentro de una transacción más grande — ese es el motor real usado por
        el resto del backend. Este método solo lo usa `InventarioRepository`
        (que calcula el delta él mismo antes de llamar aquí con el valor final).
        No se unificaron por tener contratos incompatibles (absoluto vs. delta,
        commit vs. flush) — ver docstring de módulo de stock_service.py.
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

    def get_productos_all(self) -> List[Dict]:
        """Retorna todos los productos con nombres legacy para el frontend.
        Blindaje total: usa getattr + _safe_float para tolerar discrepancias
        entre el modelo ORM y el schema real de db_productos post-migracion WO.

        Nota: distinto de `listar_todos()`/`_to_dict()` (usados por metals_routes.py
        y la búsqueda por código) — este método devuelve un shape legacy más amplio
        (STOCK MAXIMO, PUNTO REORDEN, MEDIDA, UBICACION, DOLARES, CATEGORIA) que
        algunos callers de FriParts siguen esperando tal cual. No se unificaron
        para no arriesgar romper esos contratos existentes.
        """
        try:
            rows = Producto.query.all()
            result = []
            skipped = 0
            for p in rows:
                try:
                    result.append({
                        'CODIGO SISTEMA':      getattr(p, 'codigo_sistema', '') or '',
                        'ID CODIGO':           getattr(p, 'id_codigo', '') or '',
                        'DESCRIPCION':         getattr(p, 'descripcion', '') or 'Sin descripción',
                        'PRECIO':              _safe_float(getattr(p, 'precio', 0)),
                        'POR PULIR':           _safe_float(getattr(p, 'por_pulir', 0)),
                        'P. TERMINADO':        _safe_float(getattr(p, 'p_terminado', 0)),
                        'COMPROMETIDO':        _safe_float(getattr(p, 'comprometido', 0)),
                        'PRODUCTO ENSAMBLADO': _safe_float(getattr(p, 'producto_ensamblado', 0)),
                        'STOCK MINIMO':        _safe_float(getattr(p, 'stock_minimo', 0)),
                        'STOCK MAXIMO':        _safe_float(getattr(p, 'stock_maximo', 0)),
                        'PUNTO REORDEN':       _safe_float(getattr(p, 'punto_reorden', 0)),
                        'IMAGEN':              getattr(p, 'imagen', '') or '',
                        'OEM':                 getattr(p, 'oem', '') or '',
                        'MEDIDA':              getattr(p, 'medida', '') or '',
                        'UBICACION':           getattr(p, 'ubicacion', '') or '',
                        'DOLARES':             _safe_float(getattr(p, 'dolares', 0)),
                        'CATEGORIA':           getattr(p, 'categoria', '') or '',
                    })
                except Exception as e_row:
                    skipped += 1
                    codigo = getattr(p, 'codigo_sistema', None) or getattr(p, 'id_codigo', '?')
                    logger.error(f"[get_productos_all] Fila corrupta ignorada ({codigo}): {e_row}")
                    continue
            logger.info(f"[get_productos_all] {len(result)} productos retornados. {skipped} filas ignoradas.")
            return result
        except Exception as e:
            rollback_seguro()
            import traceback
            logger.error(f"[get_productos_all] Error crítico: {e}\n{traceback.format_exc()}")
            return []

    def get_stock_critico_sql(self) -> List[Dict]:
        """Retorna productos cuyo stock está por debajo del mínimo definido."""
        try:
            sql = """
                SELECT codigo_sistema, descripcion, stock_minimo,
                       (COALESCE(p_terminado::NUMERIC, 0) + COALESCE(stock_bodega::NUMERIC, 0)) as stock_actual
                FROM db_productos
                WHERE (COALESCE(p_terminado::NUMERIC, 0) + COALESCE(stock_bodega::NUMERIC, 0)) < COALESCE(stock_minimo::NUMERIC, 0)
                ORDER BY stock_minimo::NUMERIC DESC
            """
            rows = db.session.execute(text(sql)).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            rollback_seguro()
            logger.error(f"[get_stock_critico_sql] {e}")
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
