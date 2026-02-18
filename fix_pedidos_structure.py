
import logging
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import gspread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_pedidos_structure():
    try:
        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        rows = ws.get_all_values()
        if not rows:
            logger.error("No hay datos en la hoja PEDIDOS")
            return

        headers = rows[0]
        logger.info(f"Encabezados actuales: {headers}")

        # Estructura objetivo
        expected_headers = [
            "ID PEDIDO", "FECHA", "HORA", "ID CODIGO", "DESCRIPCION", "VENDEDOR", 
            "CLIENTE", "NIT", "DIRECCION", "CIUDAD", "FORMA DE PAGO", "DESCUENTO %", "TOTAL", 
            "ESTADO", "CANTIDAD", "PRECIO UNITARIO", "PROGRESO", "CANT_ALISTADA",
            "PROGRESO_DESPACHO", "CANT_ENVIADA", "DELEGADO_A", "ESTADO_DESPACHO", "NO_DISPONIBLE"
        ]

        # 1. Verificar si falta la columna HORA en la posición correcta
        if "HORA" not in headers:
            logger.info("Insertando columna HORA en la posición 3...")
            ws.insert_cols([["HORA"]], col=3)
            # Volvemos a obtener los datos después de la inserción estructural
            rows = ws.get_all_values()
            headers = rows[0]
        elif headers[2] != "HORA":
             logger.warning(f"La columna HORA está en la posición {headers.index('HORA')+1}, no en la 3.")
        
        # 2. Corregir desalineamiento en las filas
        # Detectamos desalineamiento si en la columna 'HORA' (índice 2) hay algo que parece un código (numérico)
        # o si en 'ID CODIGO' (índice 3) hay algo que parece una descripción.
        
        updates = []
        rows_to_fix = 0
        
        for row_idx, row in enumerate(rows[1:], start=2):
            # Si la fila tiene menos columnas de las esperadas o parece desplazada
            # Un indicador claro de error es que ID CODIGO (índice 3) tenga texto largo (descripción)
            # y HORA (índice 2) tenga el código.
            
            val_col_3 = str(row[2]) if len(row) > 2 else "" # HORA
            val_col_4 = str(row[3]) if len(row) > 3 else "" # ID CODIGO
            
            # Si el código está en la columna HORA (col 3) y la descripción en ID CODIGO (col 4)
            # Nota: El código suele ser numérico de 4 dígitos. La hora tiene AM/PM.
            if val_col_3.isdigit() and len(val_col_3) >= 4 and not ("AM" in val_col_3 or "PM" in val_col_3):
                logger.info(f"Fila {row_idx} parece desalineada. Corrigiendo...")
                
                # Desplazamos los datos desde la columna 3 hacia la derecha
                # El valor en col 3 (ID CODIGO) pasa a col 4, etc.
                # Pero primero limpiamos la col 3 para que quede vacía (o con una hora ficticia)
                
                new_row_part = [""] + row[2:] # Insertamos un espacio vacío en HORA y desplazamos el resto
                
                # Truncamos o extendemos para que coincida con el ancho de la hoja si es necesario
                # Pero batch_update es más eficiente por rangos
                updates.append({
                    'range': f'C{row_idx}:{gspread.utils.rowcol_to_a1(row_idx, len(row) + 1)}',
                    'values': [new_row_part]
                })
                rows_to_fix += 1

        if updates:
            logger.info(f"Aplicando {len(updates)} correcciones de filas...")
            # Dividir en bloques si son muchos para evitar timeouts del API
            for i in range(0, len(updates), 50):
                ws.batch_update(updates[i:i+50])
            logger.info("Filas corregidas exitosamente.")
        else:
            logger.info("No se detectaron filas desalineadas.")

        # 3. Asegurar encabezados finales
        current_headers = ws.row_values(1)
        if current_headers != expected_headers:
            logger.info("Actualizando encabezados finales...")
            # Aseguramos que el ancho sea suficiente
            if len(expected_headers) > len(current_headers):
                idx_diff = len(expected_headers) - len(current_headers)
                ws.add_cols(idx_diff)
            
            ws.update('A1', [expected_headers])

        logger.info("¡Proceso de reorganización completado!")

    except Exception as e:
        logger.error(f"Error durante la reorganización: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    fix_pedidos_structure()
