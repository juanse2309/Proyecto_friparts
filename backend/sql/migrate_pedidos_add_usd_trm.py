"""
Migración: agrega `precio_usd` y `trm_aplicada` a db_pedidos.

Permite guardar, por línea de pedido, el valor original en dólares y la
TRM oficial (datos.gov.co) aplicada al momento de convertirlo a pesos --
necesario porque en pedidos de exportación el vendedor cotiza en USD y el
botón "Consultar TRM" del formulario (frontend/static/js/modules/pedidos.js)
convierte a COP antes de guardar. Sin estas columnas no había forma de saber
después si un precio_unitario en COP vino de una conversión USD ni a qué
tasa se hizo.

No destructiva: ADD COLUMN IF NOT EXISTS, sin backfill. Los pedidos ya
existentes quedan con estas columnas en NULL (se asumen 100% cotizados en
COP directamente).
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE db_pedidos
                ADD COLUMN IF NOT EXISTS precio_usd NUMERIC(18,2),
                ADD COLUMN IF NOT EXISTS trm_aplicada NUMERIC(18,4);
        """))

        db.session.commit()
        print("Migración exitosa: 'precio_usd' y 'trm_aplicada' agregadas a db_pedidos.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
