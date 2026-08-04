"""
BaseRepository — CRUD genérico 100% SQL, blindado contra inyección SQL.

Única pieza que sobrevive del antiguo God Service `repository_service.py`:
todo lo demás (KPIs de Dashboard, Ventas/Pedidos, Productos/Stock) ya vive en
repositorios de dominio dedicados bajo `backend/repositories/`.
"""
import re
import logging
from sqlalchemy import text
from backend.core.sql_database import db, rollback_seguro
from backend.config.business_rules import COLUMNS_TO_LEGACY
from backend.utils.numeric_helpers import _num

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# BLINDAJE ANTI-SQLi PARA EL CRUD GENÉRICO
# Los valores de datos siempre van parametrizados (:llave) vía SQLAlchemy,
# pero los NOMBRES de tabla/columna no se pueden parametrizar así — hay que
# interpolarlos en el texto del SQL. Esta whitelist de forma (alfanumérico +
# guion bajo, sin espacios ni comillas/punto y coma/comentarios SQL) es la
# única barrera entre esa interpolación y una inyección SQL clásica.
# ─────────────────────────────────────────────────────────────
_IDENTIFICADOR_VALIDO = re.compile(r'^[a-zA-Z0-9_]+$')


def _validar_identificador(nombre, tipo="identificador"):
    """Valida un nombre de tabla/columna antes de interpolarlo en SQL crudo."""
    if not nombre or not isinstance(nombre, str) or not _IDENTIFICADOR_VALIDO.match(nombre):
        raise ValueError(f"Nombre de {tipo} inválido o potencialmente inseguro: {nombre!r}")
    return nombre


class BaseRepository:
    """CRUD genérico 100% SQL para cualquier tabla, con validación de identificadores."""

    def _map_to_legacy(self, data):
        """Traduce llaves SQL → nombres legacy de Sheets."""
        if data is None:
            return data

        def transform(row):
            new_row = {}
            for k, v in row.items():
                if k == 'id':
                    continue
                legacy_key = COLUMNS_TO_LEGACY.get(k, k.replace('_', ' ').upper())

                # Convertir Decimal a float para serialización JSON
                from decimal import Decimal
                if isinstance(v, Decimal):
                    v = _num(v)

                # Convertir Date a String ISO para el frontend
                import datetime
                if isinstance(v, (datetime.date, datetime.datetime)):
                    v = v.strftime('%Y-%m-%d')

                new_row[legacy_key] = v
            return new_row

        if isinstance(data, list):
            return [transform(r) for r in data]
        return transform(data)

    def _query(self, sql, params=None):
        """Ejecuta SQL crudo y retorna lista de dicts."""
        try:
            result = db.session.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings()]
        except Exception as e:
            rollback_seguro()
            logger.error(f"[BaseRepository._query] {e}")
            return []

    def get_all(self, table_name, to_legacy=True):
        """Retorna todos los registros de una tabla."""
        try:
            _validar_identificador(table_name, "tabla")
            result = db.session.execute(text(f'SELECT * FROM "{table_name}"'))
            data = [dict(row) for row in result.mappings()]
            return self._map_to_legacy(data) if to_legacy else data
        except Exception as e:
            rollback_seguro()
            logger.error(f"[get_all] {table_name}: {e}")
            return []

    def get_by_filters(self, table_name, filters, to_legacy=True):
        """Consulta con filtros simples col=valor."""
        try:
            if not filters:
                return self.get_all(table_name, to_legacy)
            _validar_identificador(table_name, "tabla")
            for k in filters:
                _validar_identificador(k, "columna")
            where = " AND ".join([f'"{k}" = :{k}' for k in filters])
            result = db.session.execute(
                text(f'SELECT * FROM "{table_name}" WHERE {where}'), filters
            )
            data = [dict(row) for row in result.mappings()]
            return self._map_to_legacy(data) if to_legacy else data
        except Exception as e:
            rollback_seguro()
            logger.error(f"[get_by_filters] {table_name}: {e}")
            return []

    def insert_one(self, table_name, data):
        """Inserta un registro. Retorna True/False."""
        try:
            _validar_identificador(table_name, "tabla")
            for k in data:
                _validar_identificador(k, "columna")
            cols = ', '.join([f'"{k}"' for k in data])
            vals = ', '.join([f':{k}' for k in data])
            db.session.execute(text(f'INSERT INTO "{table_name}" ({cols}) VALUES ({vals})'), data)
            db.session.commit()
            return True
        except Exception as e:
            rollback_seguro()
            logger.error(f"[insert_one] {table_name}: {e}")
            return False

    def update_one(self, table_name, filters, data):
        """Actualiza un registro por filtros."""
        try:
            _validar_identificador(table_name, "tabla")
            for k in data:
                _validar_identificador(k, "columna")
            for k in filters:
                _validar_identificador(k, "columna")
            set_clause   = ', '.join([f'"{k}" = :d_{k}' for k in data])
            where_clause = ' AND '.join([f'"{k}" = :f_{k}' for k in filters])
            params = {f'd_{k}': v for k, v in data.items()}
            params.update({f'f_{k}': v for k, v in filters.items()})
            db.session.execute(
                text(f'UPDATE "{table_name}" SET {set_clause} WHERE {where_clause}'), params
            )
            db.session.commit()
            return True
        except Exception as e:
            rollback_seguro()
            logger.error(f"[update_one] {table_name}: {e}")
            return False


# Instancia global única
base_repository = BaseRepository()
