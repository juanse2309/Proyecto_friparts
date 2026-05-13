
import os
import sys
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Asegurar que el path del proyecto esté disponible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app import app
from backend.core.sql_database import db
from backend.models.sql_models import Pedido
from sqlalchemy import text

def curar_pedidos():
    with app.app_context():
        logger.info("🚀 Iniciando proceso de curación de integridad en db_pedidos...")
        
        # 1. Identificar duplicados (Mismo id_pedido e id_codigo)
        # Buscamos registros donde el par (id_pedido, id_codigo) se repita
        sql_duplicados = """
            SELECT id_pedido, id_codigo, COUNT(*) as repetidos
            FROM db_pedidos
            WHERE estado NOT IN ('COMPLETADO', 'DESPACHADO', 'ENTREGADO', 'FACTURADO', 'CANCELADO')
            GROUP BY id_pedido, id_codigo
            HAVING COUNT(*) > 1
        """
        duplicados = db.session.execute(text(sql_duplicados)).fetchall()
        
        if not duplicados:
            logger.info("✅ No se encontraron duplicados exactos por (ID_PEDIDO, ID_CODIGO).")
        else:
            logger.info(f"🔍 Encontrados {len(duplicados)} grupos de productos duplicados.")
            
            for d in duplicados:
                id_p = d[0]
                cod = d[1]
                
                # Obtener todos los registros para este par, ordenados por id_sql descendente
                rows = Pedido.query.filter_by(id_pedido=id_p, id_codigo=cod).order_by(Pedido.id_sql.desc()).all()
                
                # El primero (más reciente) se queda
                principal = rows[0]
                restantes = rows[1:]
                
                logger.info(f"📦 Pedido {id_p} | Código {cod}: Manteniendo ID_SQL {principal.id_sql}, consolidando {len(restantes)} duplicados.")
                
                # Consolidación antes de borrar (Juan Sebastian Request)
                for r in restantes:
                    principal.cantidad = float(principal.cantidad or 0) + float(r.cantidad or 0)
                    principal.total = float(principal.total or 0) + float(r.total or 0)
                    db.session.delete(r)
                
                logger.info(f"✨ Consolidación exitosa para {id_p} | {cod}: Cantidad final {principal.cantidad}")
        
        # 2. Corregir inconsistencias de prefijos (9319 vs FR-9319 en el mismo pedido)
        # Esto es un caso especial solicitado por el usuario anteriormente
        sql_prefijos = """
            SELECT p1.id_pedido, p1.id_codigo as cod1, p2.id_codigo as cod2
            FROM db_pedidos p1
            JOIN db_pedidos p2 ON p1.id_pedido = p2.id_pedido 
                AND REPLACE(p1.id_codigo, 'FR-', '') = REPLACE(p2.id_codigo, 'FR-', '')
                AND p1.id < p2.id
            WHERE p1.estado NOT IN ('COMPLETADO', 'CANCELADO')
        """
        inconsistentes = db.session.execute(text(sql_prefijos)).fetchall()
        
        if inconsistentes:
            logger.info(f"⚠️ Detectados {len(inconsistentes)} casos de duplicidad por prefijo FR-")
            for inc in inconsistentes:
                # Eliminamos el más antiguo (p1)
                sql_del = text("DELETE FROM db_pedidos WHERE id_pedido = :id_p AND id_codigo = :cod")
                db.session.execute(sql_del, {"id_p": inc[0], "cod": inc[1]})
        
        # 3. Commit de limpieza
        db.session.commit()
        logger.info("✨ Curación de integridad completada con éxito.")

if __name__ == "__main__":
    curar_pedidos()
