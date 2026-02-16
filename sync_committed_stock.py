
import logging
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import gspread

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sync_committed_stock():
    try:
        logger.info("🚀 Starting Committed Stock Synchronization...")

        # 1. Get all Orders
        logger.info("📦 Reading PEDIDOS sheet...")
        ws_pedidos = sheets_client.get_worksheet(Hojas.PEDIDOS)
        pedidos_records = ws_pedidos.get_all_records()
        
        # 2. Calculate Committed Totals per Product
        committed_totals = {}  # { "CODE": quantity }
        
        logger.info(f"🔄 Processing {len(pedidos_records)} order lines...")
        
        count_ignored = 0
        count_processed = 0

        for r in pedidos_records:
            # Normalize fields
            estado = str(r.get("ESTADO", "")).strip().upper()
            estado_despacho = str(r.get("ESTADO_DESPACHO", "FALSE")).strip().upper()
            codigo = str(r.get("ID CODIGO", "")).strip().upper()
            
            try:
                cantidad = float(r.get("CANTIDAD", 0) or 0)
            except ValueError:
                cantidad = 0

            # Logic:
            # We only count items that are NOT dispatched AND belong to active orders.
            # - If Order is ANULADO -> Ignore
            # - If Order is COMPLETADO -> Ignore (Assumed fully done)
            # - If Item is Despachado (TRUE) -> Ignore (Already deducted from stock)
            
            if estado in ["ANULADO", "COMPLETADO"]:
                count_ignored += 1
                continue
                
            if estado_despacho == "TRUE":
                count_ignored += 1
                continue
            
            # Add to committed
            if codigo:
                committed_totals[codigo] = committed_totals.get(codigo, 0) + cantidad
                count_processed += 1

        logger.info(f"✅ Processed {count_processed} active items. Ignored {count_ignored} (completed/dispatched/cancelled).")
        logger.info(f"📊 Found {len(committed_totals)} unique products with committed stock.")

        # 3. Update PRODUCTOS Sheet
        logger.info("📂 Reading PRODUCTOS sheet...")
        ws_productos = sheets_client.get_worksheet(Hojas.PRODUCTOS)
        productos_records = ws_productos.get_all_records()
        headers = ws_productos.row_values(1)
        
        if "COMPROMETIDO" not in headers:
            logger.error("❌ Column 'COMPROMETIDO' not found in PRODUCTOS sheet.")
            # Optional: Create it? For now, just error.
            return

        col_idx = headers.index("COMPROMETIDO") + 1
        
        logger.info("💾 Preparing batch update...")
        
        updates = []
        zero_updates = 0
        
        # We need to map Product Code -> Row Number
        # And specifically handle the updates
        
        # Strategy:
        # Iterate over ALL products in the sheet.
        # If product code is in committed_totals, set that value.
        # If product code is NOT in committed_totals, set 0 (Reset).
        
        for idx, p in enumerate(productos_records):
            # Try both CODIGO SISTEMA and ID CODIGO
            c_sis = str(p.get("CODIGO SISTEMA", "")).strip().upper()
            id_cod = str(p.get("ID CODIGO", "")).strip().upper()
            
            fila = idx + 2
            
            # Determine committed value
            qty = 0
            if c_sis in committed_totals:
                qty = committed_totals[c_sis]
            elif id_cod in committed_totals:
                qty = committed_totals[id_cod]
            
            # Optimization: Only update if value is different? 
            # Retrieving current value from 'p' might be string or int.
            # To be safe and ensure consistency, we overwrite everything or just valid ones.
            # Let's overwrite all to ensure 100% sync (resetting non-committed to 0).
            
            updates.append({
                'range': gspread.utils.rowcol_to_a1(fila, col_idx),
                'values': [[qty]]
            })
            
            if qty == 0:
                zero_updates += 1

        if updates:
            logger.info(f"📡 Sending {len(updates)} updates to Google Sheets...")
            # Batch update in chunks to avoid timeouts if list is huge
            chunk_size = 500
            for i in range(0, len(updates), chunk_size):
                chunk = updates[i:i+chunk_size]
                ws_productos.batch_update(chunk)
                logger.info(f"   ...updated chunk {i} to {i+len(chunk)}")
                
            logger.info("✨ Synchronization Complete!")
            logger.info(f"   - Total Products Updated: {len(updates)}")
            logger.info(f"   - Products with 0 committed: {zero_updates}")
            logger.info(f"   - Products with active commitments: {len(updates) - zero_updates}")
        else:
            logger.warning("⚠️ No updates found.")
            
    except Exception as e:
        logger.error(f"❌ Critical Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    sync_committed_stock()
