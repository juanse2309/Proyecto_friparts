
import sys
import os

# Add root to sys.path to allow importing backend modules
sys.path.append(os.getcwd())

from backend.core.database import sheets_client

def update_user():
    print("🚀 Iniciando actualización de usuario en RESPONSABLES...")
    
    try:
        ws = sheets_client.get_worksheet("RESPONSABLES")
        if not ws:
            print("❌ Error: No se encontró la hoja RESPONSABLES.")
            return

        records = ws.get_all_records()
        
        target_name = "Zoenia Ocanto"
        target_doc = "1140428518"
        target_role = "Auxiliar Inventario" # Permissions: inyeccion, historial, etc.
        
        # Check if user exists
        row_index = -1
        user_found = False
        
        # gspread uses 1-based index. 
        # records usually includes header, so row 2 is the first data row.
        # But get_all_records returns dicts. 
        # Better strategy: find cell by value if possible, or iterate.
        
        # Re-fetch as list of lists to be sure about indices
        all_values = ws.get_all_values()
        # Row 0 is header
        headers = all_values[0]
        
        try:
            col_responsable = headers.index("RESPONSABLE")
            col_documento = headers.index("DOCUMENTO")
            col_depto = headers.index("DEPARTAMENTO")
            # Optional Password Column
            try:
                col_pass = headers.index("CONTRASEÑA")
            except:
                col_pass = -1
        except ValueError as e:
            print(f"❌ Error en estructura de hoja: {e}")
            return

        for i, row in enumerate(all_values):
            if i == 0: continue # Skip header
            
            # Check name loosely
            name_cell = row[col_responsable]
            if name_cell.strip().lower() == target_name.lower():
                row_index = i + 1 # 1-based index
                user_found = True
                print(f"✅ Usuario encontrado en fila {row_index}")
                break
        
        if not user_found:
            print("⚠️ Usuario no encontrado. Creando nuevo...")
            # Prepare new row
            # We need to match the number of columns
            new_row = [""] * len(headers)
            new_row[col_responsable] = target_name
            new_row[col_documento] = target_doc
            new_row[col_depto] = target_role
            if col_pass != -1:
                new_row[col_pass] = "" # Clear pass
            
            ws.append_row(new_row)
            print("✅ Nuevo usuario agregado.")
            
        else:
            # Update existing
            print(f"🔄 Actualizando fila {row_index}...")
            # Update Documento
            ws.update_cell(row_index, col_documento + 1, target_doc)
            # Update Departamento
            ws.update_cell(row_index, col_depto + 1, target_role)
            # Reset Password (empty it so Document works)
            if col_pass != -1:
                ws.update_cell(row_index, col_pass + 1, "")
            
            print(f"✅ Datos actualizados: Doc={target_doc}, Rol={target_role}")

    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    update_user()
