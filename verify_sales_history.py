
import sys
import os
import logging
import json
import urllib.request
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.config.settings import Hojas
from backend.core.database import sheets_client

def parsear_fecha_flexible(fecha_str):
    """Copy of the parser function from app.py"""
    if not fecha_str or fecha_str in ['None', '']: return None
    import datetime as dt
    formatos = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
    for fmt in formatos:
        try:
            return dt.datetime.strptime(str(fecha_str).strip(), fmt)
        except: pass
    return None

def test_logic_direct():
    logger.info("🧪 [TEST 1] Testing Logic Directly (using sheets_client)...")
    try:
        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        registros = ws.get_all_records()
        logger.info(f"   Found {len(registros)} total records in PEDIDOS.")
        
        matches = 0
        for r in registros:
            estado = str(r.get("ESTADO", "")).strip().upper()
            estado_despacho = str(r.get("ESTADO_DESPACHO", "")).strip().upper()
            
            es_venta = (estado_despacho == 'TRUE') or (estado in ['COMPLETADO', 'ENVIADO', 'DESPACHADO', 'ENTREGADO'])
            
            if es_venta:
                matches += 1
                if matches <= 3:
                    logger.info(f"   MATCH FOUND: ID={r.get('ID PEDIDO')} | Estado={estado} | Despacho={estado_despacho}")
        
        logger.info(f"✅ Logic Check: Found {matches} 'Sales' records.")
            
    except Exception as e:
        logger.error(f"❌ Error in Logic Test: {e}")

def test_api_endpoint():
    logger.info("🧪 [TEST 2] Testing API Endpoint (http://127.0.0.1:5000/api/historial-global?tipo=VENTA)...")
    try:
        url = "http://127.0.0.1:5000/api/historial-global?tipo=VENTA"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                movimientos = data.get('movimientos', [])
                logger.info(f"✅ API Success! Retrieved {len(movimientos)} records.")
                
                # Check for VENTA type
                ventas = [m for m in movimientos if m.get('Tipo') == 'VENTA']
                logger.info(f"   Filtered 'VENTA' records count: {len(ventas)}")
                
                if ventas:
                    logger.info("   First record sample:")
                    logger.info(json.dumps(ventas[0], indent=2))
                else:
                    logger.warning("   ⚠️ No VENTA records returned by API. Server might not have reloaded yet.")
            else:
                logger.error(f"❌ API Error: Status {response.status}")
    except Exception as e:
        logger.error(f"❌ Error connecting to API: {e}")
        logger.warning("   (Server might not be running or port is different)")

if __name__ == "__main__":
    test_logic_direct()
    logger.info("-" * 40)
    test_api_endpoint()
