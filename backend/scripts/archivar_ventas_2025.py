# -*- coding: utf-8 -*-
"""
Script de Migración Independiente: Archivar Ventas 2025
------------------------------------------------------
Este script permite mover únicamente los registros de ventas del año 2025
desde la tabla 'db_ventas' hacia una nueva tabla histórica 'ventas_historico_2025'.
Esto ayuda a alivianar la tabla principal y optimizar el rendimiento del Dashboard.

IMPORTANTE: NO ejecutar en el flujo automático de despliegue.
Debe ser ejecutado manualmente tras confirmación visual:
    python backend/scripts/archivar_ventas_2025.py
"""

import os
import sys
import logging
import psycopg2

# Configurar logs para la consola
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ArchivarVentas2025")

DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://admin_juan:5uM2TSjhKB2nIRPR41xJlmgJ5tKgaonX@dpg-d7f5mrpf9bms73a0a1g0-a.virginia-postgres.render.com/fritech_db'
)

def ejecutar_migracion():
    logger.info("📡 Iniciando migración de histórico de ventas 2025...")
    
    conn = None
    try:
        # 1. Establecer conexión con PostgreSQL
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # 2. Crear tabla ventas_historico_2025 si no existe, replicando el esquema de db_ventas
        logger.info("Verificando existencia de la tabla 'ventas_historico_2025'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ventas_historico_2025 (
                id SERIAL PRIMARY KEY,
                fecha DATE,
                documento VARCHAR(80),
                nombres VARCHAR(200),
                productos VARCHAR(100),
                cantidad NUMERIC(18, 2) DEFAULT 0,
                total_ingresos NUMERIC(18, 2) DEFAULT 0,
                precio_promedio NUMERIC(18, 2) DEFAULT 0,
                clasificacion VARCHAR(80)
            );
        """)
        
        # Agregar índices opcionales para mejorar búsquedas futuras en la histórica
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_hist_2025_fecha ON ventas_historico_2025(fecha);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_hist_2025_productos ON ventas_historico_2025(productos);")
        
        # 3. Contar registros del 2025 en db_ventas
        cursor.execute("""
            SELECT COUNT(*) FROM db_ventas 
            WHERE fecha >= '2025-01-01' AND fecha <= '2025-12-31';
        """)
        total_2025 = cursor.fetchone()[0]
        
        if total_2025 == 0:
            logger.info("ℹ️ No se encontraron registros de ventas para el año 2025 en 'db_ventas'.")
            cursor.close()
            conn.close()
            return
            
        logger.info(f"📊 Se encontraron {total_2025} registros del año 2025 listos para archivar.")
        
        # 4. Insertar registros en ventas_historico_2025
        logger.info("Copiando registros de 2025 a 'ventas_historico_2025'...")
        cursor.execute("""
            INSERT INTO ventas_historico_2025 (fecha, documento, nombres, productos, cantidad, total_ingresos, precio_promedio, clasificacion)
            SELECT fecha, documento, nombres, productos, cantidad, total_ingresos, precio_promedio, clasificacion
            FROM db_ventas
            WHERE fecha >= '2025-01-01' AND fecha <= '2025-12-31';
        """)
        filas_insertadas = cursor.rowcount
        logger.info(f"✅ Se insertaron {filas_insertadas} registros en 'ventas_historico_2025'.")
        
        # 5. Eliminar registros de db_ventas
        logger.info("Eliminando registros de 2025 de la tabla maestra 'db_ventas'...")
        cursor.execute("""
            DELETE FROM db_ventas
            WHERE fecha >= '2025-01-01' AND fecha <= '2025-12-31';
        """)
        filas_eliminadas = cursor.rowcount
        logger.info(f"✅ Se eliminaron {filas_eliminadas} registros de 'db_ventas'.")
        
        # Validación de integridad
        if filas_insertadas != filas_eliminadas:
            raise Exception(f"Error de integridad: filas insertadas ({filas_insertadas}) no coinciden con las eliminadas ({filas_eliminadas}).")
        
        # 6. Confirmar la transacción
        conn.commit()
        logger.info("🎉 ¡Migración completada con éxito! Todos los cambios han sido aplicados.")
        
    except Exception as e:
        logger.error(f"❌ Error durante el proceso de migración: {e}")
        if conn:
            logger.info("🔄 Ejecutando Rollback para evitar inconsistencias...")
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()
            logger.info("📡 Conexión a la base de datos cerrada.")

if __name__ == '__main__':
    # Confirmación de ejecución manual interactiva en consola
    print("=" * 60)
    print("ADVERTENCIA: Este script modificará los datos de producción.")
    print("=" * 60)
    confirmacion = input("¿Está seguro de que desea archivar los datos de ventas del 2025? (si/no): ").strip().lower()
    if confirmacion in ('si', 'sí', 'yes', 'y'):
        ejecutar_migracion()
    else:
        print("Migración cancelada por el usuario.")
