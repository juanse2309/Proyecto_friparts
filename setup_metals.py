from backend.core.database import sheets_client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_metals_sheets():
    # 1. METALS_PERSONAL
    try:
        ws = sheets_client.get_worksheet("METALS_PERSONAL")
        if not ws:
            logger.info("Creando METALS_PERSONAL...")
            # Use spreadsheet object to create
            ss = sheets_client.spreadsheet
            ws = ss.add_worksheet(title="METALS_PERSONAL", rows=100, cols=10)
            ws.append_row(["RESPONSABLE", "DEPARTAMENTO", "DOCUMENTO", "ACTIVO"])
            ws.append_row(["OPERARIO PRUEBA METAL", "Tornos", "12345", "SI"])
        else:
            logger.info("METALS_PERSONAL ya existe.")
    except Exception as e:
        logger.error(f"Error METALS_PERSONAL: {e}")

    # 2. METALS_PRODUCTOS
    try:
        ws = sheets_client.get_worksheet("METALS_PRODUCTOS")
        if not ws:
            logger.info("Creando METALS_PRODUCTOS...")
            ss = sheets_client.spreadsheet
            ws = ss.add_worksheet(title="METALS_PRODUCTOS", rows=1000, cols=10)
            ws.append_row(["CODIGO", "DESCRIPCION", "MAQUINA_INICIAL", "PROCESOS", "STOCK_MINIMO"])
            ws.append_row(["MET-001", "Base Metalica T1", "Tornos", "Tornos, Soldadura, Pintura", "10"])
        else:
            logger.info("METALS_PRODUCTOS ya existe.")
    except Exception as e:
        logger.error(f"Error METALS_PRODUCTOS: {e}")

    # 3. METALS_PRODUCCION
    try:
        ws = sheets_client.get_worksheet("METALS_PRODUCCION")
        if not ws:
            logger.info("Creando METALS_PRODUCCION...")
            ss = sheets_client.spreadsheet
            ws = ss.add_worksheet(title="METALS_PRODUCCION", rows=5000, cols=15)
            headers = [
                "ID_REGISTRO", "FECHA", "OPERARIO", "MAQUINA", 
                "CODIGO_PRODUCTO", "PROCESO", "CANT_SOLICITADA", 
                "HORA_INICIO", "HORA_FIN", "CANT_LOGRADA", 
                "PNC", "TIEMPO_TOTAL", "ESTADO", "SIGUIENTE_PROCESO"
            ]
            ws.append_row(headers)
        else:
            logger.info("METALS_PRODUCCION ya existe.")
    except Exception as e:
        logger.error(f"Error METALS_PRODUCCION: {e}")

if __name__ == "__main__":
    setup_metals_sheets()
