import os
import sys
import logging
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.getcwd())

# Mock row data (22 columns as expected by registrar_inyeccion)
mock_row_data = [
    "INY-TEST-001",           # 1  ID INYECCION
    "2026-03-03",            # 2  FECHA INICIA
    "2026-03-03",            # 3  FECHA FIN
    "INYECCION",             # 4  DEPARTAMENTO
    "MAQ-01",                # 5  MAQUINA
    "OPERADOR TEST",         # 6  RESPONSABLE
    "TEST-PROD",             # 7  ID CODIGO
    2,                       # 8  No. CAVIDADES
    "08:00",                 # 9  HORA LLEGADA
    "08:15",                 # 10 HORA INICIO
    "17:00",                 # 11 HORA TERMINA
    1000,                    # 12 CONTADOR MAQ.
    1000,                    # 13 CANT. CONTADOR
    5,                       # 14 TOMADOS EN PROCESO
    0.5,                     # 15 PESO TOMADAS
    2000,                    # 16 CANTIDAD REAL
    "ALMACEN_TEST",          # 17 ALMACEN DESTINO
    "ENS-001",               # 18 CODIGO ENSAMBLE
    "OP-12345",              # 19 ORDEN PRODUCCION
    "PRUEBA DE INTEGRACIÓN", # 20 OBSERVACIONES
    10.5,                    # 21 PESO VELA MAQUINA
    9.8                      # 22 PESO BUJES
]

def test_integration():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("IntegrationTest")
    
    try:
        from backend.app import process_pdf_and_drive
        logger.info("Iniciando prueba de integración PDF/Drive...")
        
        # Envoltorio para simular el comportamiento de ThreadPoolExecutor.submit
        process_pdf_and_drive(mock_row_data, pnc=50, producto_nombre="BUJE TEST PROFESIONAL")
        
        logger.info("Prueba finalizada. Por favor, revisa el output y Google Drive.")
        
    except Exception as e:
        import traceback
        logger.error(f"Falla en la prueba de integración: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_integration()
