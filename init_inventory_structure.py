
import os
import gspread
import logging
from google.oauth2.service_account import Credentials

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def init_sheet():
    try:
        creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
        gc = gspread.authorize(creds)
        ss = gc.open_by_key(GSHEET_KEY)
        
        # 1. Update PRODUCTOS sheet
        ws_productos = ss.worksheet("PRODUCTOS")
        headers = ws_productos.row_values(1)
        
        if "COMPROMETIDO" not in headers:
            # Find P. TERMINADO position
            try:
                p_term_idx = headers.index("P. TERMINADO")
                # Insert COMPROMETIDO after P. TERMINADO
                headers.insert(p_term_idx + 1, "COMPROMETIDO")
                # Correctly insert ONE column with row_count rows
                column_data = ["COMPROMETIDO"] + [0] * (ws_productos.row_count - 1)
                ws_productos.insert_cols([column_data], p_term_idx + 2)
                logger.info("Added COMPROMETIDO column to PRODUCTOS")
            except ValueError:
                logger.error("P. TERMINADO column not found")
        else:
            logger.info("COMPROMETIDO column already exists in PRODUCTOS")

        # 2. Create CONTEOS sheet if not exists
        try:
            ss.worksheet("CONTEOS")
            logger.info("CONTEOS sheet already exists")
        except gspread.exceptions.WorksheetNotFound:
            ws_conteos = ss.add_worksheet(title="CONTEOS", rows=1000, cols=8)
            ws_conteos.append_row([
                "FECHA", "RESPONSABLE", "ID CODIGO", "CONTEO_1", "CONTEO_2", "CONTEO_3", "ESTADO", "OBSERVACIONES"
            ])
            logger.info("Created CONTEOS sheet")

    except Exception as e:
        logger.error(f"Error initializing sheet: {e}")

if __name__ == "__main__":
    init_sheet()
