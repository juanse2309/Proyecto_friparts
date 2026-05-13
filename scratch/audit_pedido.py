
import os
import sys

# Add the project root to sys.path
project_root = r"e:\OneDrive\RYZEN\Documentos\Proyectos de programacion\proyecto_bujes - copia"
sys.path.append(project_root)

from backend.app import app
from backend.core.sql_database import db
from backend.models.sql_models import Pedido
from sqlalchemy import text

def audit_order(id_pedido):
    with app.app_context():
        print(f"--- Auditoría para Pedido: {id_pedido} ---")
        
        # 1. Consultar todos los items del pedido
        pedidos = Pedido.query.filter_by(id_pedido=id_pedido).all()
        print(f"Total de filas encontradas en db_pedidos: {len(pedidos)}")
        
        for p in pedidos:
            print(f"ID_SQL: {p.id_sql} | Referencia: {p.id_codigo} | Cantidad: {p.cantidad} | Descripción: {p.descripcion}")

        # 2. Buscar específicamente las referencias KIT-03-5002 y KIT-02-5003 en todo el pedido
        ref1 = "KIT-03-5002"
        ref2 = "KIT-02-5003"
        
        items_ref1 = [p for p in pedidos if p.id_codigo == ref1]
        items_ref2 = [p for p in pedidos if p.id_codigo == ref2]
        
        print(f"\n--- Detalle de Referencias Críticas ---")
        print(f"Items con {ref1}: {len(items_ref1)}")
        for i, p in enumerate(items_ref1):
             print(f"  [{i+1}] Cantidad: {p.cantidad}")
             
        print(f"Items con {ref2}: {len(items_ref2)}")
        for i, p in enumerate(items_ref2):
             print(f"  [{i+1}] Cantidad: {p.cantidad}")

if __name__ == "__main__":
    audit_order("PED-638363")
    # También intentaré buscar por 638363 solo por si acaso
    # audit_order("638363")
