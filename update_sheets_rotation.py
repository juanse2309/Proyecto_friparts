from backend.core.database import sheets_client as gc
from backend.config.settings import Hojas

def update_sheet():
    ws = gc.get_worksheet(Hojas.PARAMETROS_INVENTARIO)
    if not ws:
        print("Hoja no encontrada")
        return
    headers = ws.row_values(1)
    new_cols = []
    if 'CLASE_ROTACION' not in headers:
        new_cols.append('CLASE_ROTACION')
    if 'CONTADOR_OC' not in headers:
        new_cols.append('CONTADOR_OC')
    
    if new_cols:
        next_col = len(headers) + 1
        for i, col_name in enumerate(new_cols):
             ws.update_cell(1, next_col + i, col_name)
             print(f"Columna {col_name} añadida.")
        
        # Populate with default values if empty
        data = ws.get_all_records()
        if data:
            num_rows = len(data)
            # Fill CLASE_ROTACION with 'C' and CONTADOR_OC with 0 by default
            start_row = 2
            end_row = num_rows + 1
            
            headers_updated = ws.row_values(1)
            clase_col_idx = headers_updated.index('CLASE_ROTACION') + 1
            contador_col_idx = headers_updated.index('CONTADOR_OC') + 1
            
            # Using update for efficiency if possible, but let's do batches if many
            # Since it's probably not thousands, simple loop or range update
            if 'CLASE_ROTACION' in new_cols:
                cells = ws.range(start_row, clase_col_idx, end_row, clase_col_idx)
                for cell in cells:
                    cell.value = 'C'
                ws.update_cells(cells)
                print("Default 'C' set for CLASE_ROTACION")
            
            if 'CONTADOR_OC' in new_cols:
                cells = ws.range(start_row, contador_col_idx, end_row, contador_col_idx)
                for cell in cells:
                    cell.value = 0
                ws.update_cells(cells)
                print("Default 0 set for CONTADOR_OC")
    else:
        print("Columnas ya existen.")

if __name__ == "__main__":
    update_sheet()
