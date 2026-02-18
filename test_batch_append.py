
import logging
import uuid
import datetime
import pytz
from backend.core.database import sheets_client
from backend.config.settings import Hojas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_batch_append():
    try:
        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        
        # Simular datos de un pedido con 5 referencias (prueba rápida)
        id_pedido = f"TEST-{str(uuid.uuid4())[:8].upper()}"
        tz_colombia = pytz.timezone('America/Bogota')
        hora_actual = datetime.datetime.now(tz_colombia).strftime('%I:%M %p')
        
        expected_headers = [
            "ID PEDIDO", "FECHA", "HORA", "ID CODIGO", "DESCRIPCION", "VENDEDOR", 
            "CLIENTE", "NIT", "DIRECCION", "CIUDAD", "FORMA DE PAGO", "DESCUENTO %", "TOTAL", 
            "ESTADO", "CANTIDAD", "PRECIO UNITARIO", "PROGRESO", "CANT_ALISTADA",
            "PROGRESO_DESPACHO", "CANT_ENVIADA", "DELEGADO_A", "ESTADO_DESPACHO", "NO_DISPONIBLE"
        ]
        
        batch_data = []
        for i in range(110):
            row_dict = {h: "" for h in expected_headers}
            row_dict.update({
                "ID PEDIDO": id_pedido,
                "FECHA": "2026-02-18",
                "HORA": hora_actual,
                "ID CODIGO": f"999{i}",
                "DESCRIPCION": f"PRUEBA ESTRÉS BATCH {i+1}",
                "VENDEDOR": "Andrés (Prueba Límite)",
                "CLIENTE": "CLIENTE PRUEBA 110 ITEMS",
                "ESTADO": "PENDIENTE",
                "CANTIDAD": 1,
                "PRECIO UNITARIO": 100,
                "TOTAL": 100,
                "ESTADO_DESPACHO": "FALSE",
                "NO_DISPONIBLE": "FALSE"
            })
            batch_data.append([row_dict[h] for h in expected_headers])
            
        logger.info(f"🚀 Enviando lote de {len(batch_data)} referencias a Google Sheets...")
        ws.append_rows(batch_data)
        logger.info(f"✅ ¡ÉXITO! Se subieron 110 referencias en un solo paquete para el pedido {id_pedido}")
        
    except Exception as e:
        logger.error(f"❌ Error en la prueba: {e}")

if __name__ == "__main__":
    test_batch_append()
