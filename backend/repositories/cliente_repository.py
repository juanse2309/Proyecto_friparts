"""
Repositorio de clientes 100% SQL-First.
Centraliza el acceso a la tabla db_clientes en PostgreSQL.
"""
import logging
from sqlalchemy import text
from backend.core.sql_database import db, rollback_seguro

logger = logging.getLogger(__name__)


class ClienteRepository:
    """Repositorio para operaciones de lectura sobre clientes."""

    @staticmethod
    def get_all():
        """Retorna todos los clientes desde SQL con llaves en minúscula para el frontend."""
        try:
            rows = db.session.execute(text('SELECT * FROM db_clientes')).mappings().all()

            def _get(row, candidates):
                for c in candidates:
                    if c in row and row[c]:
                        return str(row[c]).strip()
                return ''

            result = []
            for row in rows:
                nombre = _get(row, ['nombre', 'cliente', 'razon_social', 'nombre_empresa'])
                if not nombre:
                    continue
                result.append({
                    'nombre':    nombre,
                    'nit':       _get(row, ['nit', 'identificacion', 'nit_empresa']),
                    'direccion': _get(row, ['direccion']),
                    'ciudad':    _get(row, ['ciudad']),
                    'telefono':  _get(row, ['telefonos', 'telefono', 'celular']),
                    'email':     _get(row, ['email', 'correo', 'e_mail']),
                })
            logger.info(f"[ClienteRepository.get_all] {len(result)} clientes cargados con mapeo correcto.")
            return result
        except Exception as e:
            rollback_seguro()
            logger.error(f"[ClienteRepository.get_all] {e}")
            return []
