import logging

from flask_sqlalchemy import SQLAlchemy

logger = logging.getLogger(__name__)

db = SQLAlchemy()


def rollback_seguro():
    """
    Aborta la transacción activa sin propagar errores secundarios.

    Regla 2 (Código Defensivo): tras un fallo SQL, PostgreSQL deja la transacción
    en estado 'aborted' y CUALQUIER consulta posterior sobre la misma sesión falla
    con InFailedSqlTransaction, dejando la conexión inutilizable dentro del pool.

    Se envuelve el rollback en su propio try/except porque si la conexión ya está
    caída, `db.session.rollback()` puede lanzar y enmascarar la excepción original
    que se estaba manejando.
    """
    try:
        db.session.rollback()
    except Exception as rb_err:
        logger.error(f"[rollback_seguro] Fallo al abortar la transacción: {rb_err}")
