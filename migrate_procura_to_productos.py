import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.core.database import sheets_client
from backend.config.settings import Hojas
import gspread

# Usar el traductor de BOM para asegurar códigos limpios
from backend.services.bom_service import traducir_codigo_componente

def log(msg):
    print(f"[*] {msg}")

def __buscar_producto_inteligente(codigo_buscado, prod_records):
    target = str(codigo_buscado).strip().upper()
    if not target: return None, None
    PREFIJOS_FLEX = ("CAR", "INT", "ENS", "CB")
    es_comp = target.startswith(PREFIJOS_FLEX)

    for idx, r in enumerate(prod_records):
        v_sis = str(r.get("CODIGO SISTEMA", "")).strip().upper()
        v_id = str(r.get("ID CODIGO", "")).strip().upper()
        if target == v_sis or target == v_id:
            return idx + 2, r
        if es_comp:
            if v_sis.startswith(target) or v_id.startswith(target):
                return idx + 2, r
    return None, None

def check_and_add_columns(ws, exist_headers, new_columns):
    updates = False
    for col in new_columns:
        if col not in exist_headers:
            exist_headers.append(col)
            updates = True
    if updates:
        log(f"Añadiendo nuevas cabeceras a la hoja: {new_columns}")
        range_str = f"A1:{gspread.utils.rowcol_to_a1(1, len(exist_headers))}"
        ws.update(range_name=range_str, values=[exist_headers])
    return exist_headers

def main():
    log("Iniciando migración de PARAMETROS_INVENTARIO -> PRODUCTOS...")
    
    ws_prod = sheets_client.get_worksheet(Hojas.PRODUCTOS)
    ws_param = sheets_client.get_worksheet(Hojas.PARAMETROS_INVENTARIO)
    
    if not ws_prod or not ws_param:
        log("ERROR: No se pudieron encontrar las hojas de cálculo.")
        return

    prod_records = sheets_client.get_all_records_seguro(ws_prod)
    param_records = sheets_client.get_all_records_seguro(ws_param)
    
    prod_headers = ws_prod.row_values(1)
    
    COLUMNAS_ESPERADAS = [
        "STOCK_BODEGA", "MINIMO", "CLASE_ROTACION", 
        "EN_ZINCADO", "EN_GRANALLADO", "CONTADOR_OC"
    ]
    
    # 1. Asegurar nuevas columnas
    prod_headers = check_and_add_columns(ws_prod, prod_headers, COLUMNAS_ESPERADAS)
    col_index = {h: idx + 1 for idx, h in enumerate(prod_headers)}
    
    updates_dict = {}
    rows_to_append = []
    
    filas_actualizadas = 0
    filas_creadas = 0

    log(f"Procesando {len(param_records)} registros de Origen...")

    for rp in param_records:
        cod_raw = str(rp.get("CÓDIGO", rp.get("CODIGO", rp.get("REFERENCIA", "")))).strip()
        if not cod_raw: continue
        
        # Obtenemos código limpio (ej. C-9304 -> CAR9304)
        codigo_limpio = traducir_codigo_componente(cod_raw)
        if not codigo_limpio: continue

        stock_param = int(rp.get("STOCK_ACTUAL", 0) or 0)
        minimo = int(rp.get("EXISTENCIAS MÍNIMAS", rp.get("EXISTENCIAS MINIMAS", 0)) or 0)
        contador_oc = int(rp.get("CONTADOR_OC", 0) or 0)
        descripcion = str(rp.get("DESCRIPCIÓN", rp.get("DESCRIPCION", ""))).strip()
        
        # En_zincado / granallado empiezan en 0 para esta migración base
        en_zincado = 0
        en_granallado = 0
        
        # Logica ABC
        clase = "C"
        if contador_oc >= 10 or minimo >= 1000: clase = "A"
        elif contador_oc >= 4 or minimo >= 400: clase = "B"

        fila_encontrada, datos_existentes = __buscar_producto_inteligente(codigo_limpio, prod_records)
        
        # Checking if this item is in the pseudo inserted list
        ya_insertado = None
        for i, row_list in enumerate(rows_to_append):
            # ID CODIGO mapping is basically matching index col_index["ID CODIGO"]-1
            if row_list[col_index["ID CODIGO"]-1] == codigo_limpio:
                ya_insertado = row_list
                break

        if fila_encontrada and not ya_insertado:
            # ACTUALIZAR fila existente en base
            stock_bodega_actual = int(datos_existentes.get("STOCK_BODEGA", 0) or 0)
            nuevo_stock_bodega = stock_bodega_actual + stock_param
            
            updates_dict[(fila_encontrada, col_index["STOCK_BODEGA"])] = nuevo_stock_bodega
            updates_dict[(fila_encontrada, col_index["MINIMO"])] = minimo
            updates_dict[(fila_encontrada, col_index["CLASE_ROTACION"])] = clase
            updates_dict[(fila_encontrada, col_index["CONTADOR_OC"])] = contador_oc
            updates_dict[(fila_encontrada, col_index["EN_ZINCADO"])] = en_zincado
            updates_dict[(fila_encontrada, col_index["EN_GRANALLADO"])] = en_granallado
            
            # Update memory dict to prevent double counting
            datos_existentes["STOCK_BODEGA"] = nuevo_stock_bodega
            filas_actualizadas += 1
            log(f" [UPDATE] {codigo_limpio}: STOCK_BODEGA -> {nuevo_stock_bodega} (+{stock_param})")
            
        elif ya_insertado:
            # ACTUALIZAR a fila recién creada que aún no va a sheets (está en rows_to_append)
            stock_bodega_actual = int(ya_insertado[col_index["STOCK_BODEGA"]-1] or 0)
            nuevo_stock = stock_bodega_actual + stock_param
            ya_insertado[col_index["STOCK_BODEGA"]-1] = nuevo_stock
            
            # Overwrite properties if this occurrence has them (e.g. higher min)
            if minimo > int(ya_insertado[col_index["MINIMO"]-1] or 0):
                ya_insertado[col_index["MINIMO"]-1] = minimo
            
            log(f" [UPDATE-PRE-INSERT] {codigo_limpio}: STOCK_BODEGA -> {nuevo_stock} (Acumulado en buffer)")
            
        else:
            # INSERTAR
            nueva_fila = [""] * len(prod_headers)
            
            def set_val(col_name, val):
                if col_name in col_index: 
                    nueva_fila[col_index[col_name]-1] = val
                    
            set_val("ID CODIGO", codigo_limpio)
            set_val("CODIGO SISTEMA", codigo_limpio)
            set_val("DESCRIPCION", descripcion)
            set_val("STOCK_BODEGA", stock_param)
            set_val("MINIMO", minimo)
            set_val("CLASE_ROTACION", clase)
            set_val("CONTADOR_OC", contador_oc)
            set_val("EN_ZINCADO", en_zincado)
            set_val("EN_GRANALLADO", en_granallado)
            set_val("POR PULIR", 0)
            set_val("P. TERMINADO", 0)
            
            rows_to_append.append(nueva_fila)
            filas_creadas += 1
            log(f" [INSERT] {codigo_limpio}: Nuevo insumo - Bodega: {stock_param}")

    log("Aplicando actualizaciones por lotes...")
    if updates_dict:
        batch_data = []
        for (r, c), val in updates_dict.items():
            batch_data.append({
                'range': gspread.utils.rowcol_to_a1(r, c),
                'values': [[val]]
            })
        for i in range(0, len(batch_data), 150):
            # Enviar batch en chunks para evitar quotas
            chunk = batch_data[i:i+150]
            ws_prod.batch_update(chunk)
            log(f"Batch guardado: {len(chunk)} celdas...")
        
    log("Insertando nuevas filas...")
    if rows_to_append:
        ws_prod.append_rows(rows_to_append, value_input_option='USER_ENTERED')
        
    log("\n============== REPORTE FINAL ==============")
    log(f"Componentes Existentes Actualizados: {filas_actualizadas}")
    log(f"Componentes Nuevos Creados:          {filas_creadas}")
    log(f"Total procesado:                     {filas_actualizadas + filas_creadas}")
    log("=========================================\n")

if __name__ == '__main__':
    main()
