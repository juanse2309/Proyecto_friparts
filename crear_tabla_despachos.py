import sys
import os

# Asegurar que el directorio raíz está en el PATH para importar 'backend'
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app import app, db
from backend.models.sql_models import DespachoPedido

with app.app_context():
    try:
        # Crear únicamente la tabla asociada al modelo DespachoPedido
        DespachoPedido.__table__.create(db.engine)
        print("✅ Tabla 'db_despachos_pedido' creada con éxito en PostgreSQL.")
    except Exception as e:
        print(f"❌ Error al crear la tabla: {e}")
