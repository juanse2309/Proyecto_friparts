from backend.core.database import sheets_client
from backend.config.settings import Hojas
import json

def fix_alignment():
    print("🚀 Iniciando script de limpieza de PEDIDOS...")
    try:
        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        
        # 1. ACTUALIZAR CABECERAS
        # La estructura definitiva debe ser:
        # 0:ID PEDIDO, 1:FECHA, 2:ID CODIGO, 3:DESCRIPCION, 4:VENDEDOR, 5:CLIENTE, 6:NIT, 
        # 7:DIRECCION, 8:CIUDAD, 9:FORMA DE PAGO, 10:DESCUENTO %, 11:TOTAL, 12:ESTADO, 
        # 13:CANTIDAD, 14:PRECIO UNITARIO, 15:PROGRESO, 16:CANT_ALISTADA, 
        # 17:PROGRESO_DESPACHO, 18:CANT_ENVIADA, 19:DELEGADO_A, 20:ESTADO_DESPACHO
        
        headers_definitivos = [
            "ID PEDIDO", "FECHA", "ID CODIGO", "DESCRIPCION", "VENDEDOR", 
            "CLIENTE", "NIT", "DIRECCION", "CIUDAD", "FORMA DE PAGO", "DESCUENTO %", "TOTAL", 
            "ESTADO", "CANTIDAD", "PRECIO UNITARIO", "PROGRESO", "CANT_ALISTADA",
            "PROGRESO_DESPACHO", "CANT_ENVIADA", "DELEGADO_A", "ESTADO_DESPACHO"
        ]
        
        print("📝 Actualizando encabezados...")
        ws.update('A1', [headers_definitivos])
        
        # 2. DETECTAR Y CORREGIR FILAS DESPLAZADAS
        # Obtenemos todos los valores crudos para ver qué hay realmente en cada celda
        all_values = ws.get_all_values()
        data_rows = all_values[1:] # Saltar headers
        
        updates = []
        
        for idx, row in enumerate(data_rows):
            fila_sheet = idx + 2
            
            # CRITERIO DE DETECCIÓN:
            # Si en la columna 12 (i=11) hay algo que parece un ESTADO (ej: 'PENDIENTE', 'EN ALISTAMIENTO') 
            # en lugar de un TOTAL numérico, es que está desplazada.
            # O si la fila es más corta de lo esperado.
            
            val_11 = row[11] if len(row) > 11 else ""
            
            # Si el valor en la columna 12 (TOTAL) es un estado, significa que faltan DIR y CIU (2 columnas)
            es_estado = val_11.upper() in ["PENDIENTE", "EN ALISTAMIENTO", "COMPLETADO", "PARCIAL", "DESPACHADO"]
            
            if es_estado:
                print(f"⚠️ Fila {fila_sheet} (Pedido {row[0]}) detectada como DESPLAZADA. Reajustando...")
                
                # Ejemplo de fila desplazada observada:
                # [ID, FEC, COD, DESC, VEND, CLI, NIT, DIR, CIU, PAGO, DESC%, TOTAL, ESTADO, CANT, PRECIO, ...]
                # Pero si DIR/CIU no estaban en headers, quizás el backend las mandó y cayeron en FORMA, DESC, TOTAL...
                
                # Vamos a reconstruir la fila asumiendo el envío que falló:
                # El backend mandó: ID(0), FEC(1), COD(2), DESC(3), VEND(4), CLI(5), NIT(6), DIR(7), CIU(8), PAGO(9), DESC(10), TOTAL(11), EST(12), ...
                
                # Si leemos la fila actual, DIR cayó en la col 7 (FORMA DE PAGO antigua).
                # Necesitamos insertar 2 espacios vacíos o mover los datos.
                
                # Si la fila tiene los datos pero en las columnas equivocadas:
                new_row = list(row)
                
                # Asegurar longitud
                while len(new_row) < 21:
                    new_row.append("")
                
                # Si el estado está en la 11, todo desde la 7 debe moverse 2 a la derecha?
                # Veamos una fila real del usuario:
                # PED-5E64B4AF(0)	2026-02-11(1)	7004(2)	BUJE...(3)	Andrés...(4)	MACHADO...(5)	CC 1068975688(6)	CARRERA 30 77 78 P1(7)	Bogota D.C.(8)	Contado(9)	35%(10)	119080(11)	PENDIENTE(12)	8(13)	22900(14)
                
                # Si los encabezados eran:
                # ID(0), FECHA(1), COD(2), DESC(3), VEND(4), CLI(5), NIT(6), PAGO(7), DESC(8), TOTAL(9), ESTADO(10), CANT(11), PRECIO(12)
                
                # Entonces:
                # 7 (PAGO) tiene "CARRERA 30..." (DIRECCION)
                # 8 (DESC) tiene "Bogota D.C." (CIUDAD)
                # 9 (TOTAL) tiene "Contado" (FORMA DE PAGO)
                # 10 (ESTADO) tiene "35%" (DESCUENTO)
                # 11 (CANT) tiene "119080" (TOTAL)
                # 12 (PRECIO) tiene "PENDIENTE" (ESTADO)
                # 13 (...) tiene "8" (CANTIDAD)
                # 14 (...) tiene "22900" (PRECIO)
                
                # ¡EXACTO! El desajuste es de 2 columnas hacia la izquierda en los encabezados.
                
                # Si la fila ya TIENE los datos (porque el backend los mandó), solo hay que reubicar los encabezados (ya hecho)
                # Y verificar si hay filas VIEJAS que NO tengan DIR ni CIU.
                
            else:
                # Si NO es estado en la 11, podría ser una fila VIEJA (sin DIR ni CIU)
                # ID(0), FECHA(1), COD(2), DESC(3), VEND(4), CLI(5), NIT(6), PAGO(7), DESC(8), TOTAL(9), ESTADO(10), CANT(11), PRECIO(12)
                
                # Si es vieja, necesitamos INSERTAR dos columnas vacías en 7 y 8.
                try:
                    # Si la columna 9 (TOTAL) es un número, es una fila vieja o ya corregida
                    float(str(row[9]).replace(',','').replace('$',''))
                    
                    # Si el estado está en la 10, es vieja. (En la nueva el estado debe estar en la 12)
                    if len(row) > 12 and row[12].upper() in ["PENDIENTE", "EN ALISTAMIENTO", "COMPLETADO", "DESPACHADO"]:
                         # Ya está bien (es nueva con DIR/CIU)
                         pass
                    else:
                        print(f"📜 Fila {fila_sheet} detectada como ANTIGUA (sin DIR/CIU). Insertando espacios...")
                        new_row = list(row)
                        # Insertar DIR/CIU vacíos en 7 y 8
                        new_row.insert(7, "")
                        new_row.insert(8, "")
                        while len(new_row) < 21: new_row.append("")
                        updates.append({
                            'range': f'A{fila_sheet}:U{fila_sheet}',
                            'values': [new_row[:21]]
                        })
                except:
                    # Si no es número, ignorar o procesar como desplazada si aplica
                    pass

        # Aplicar correcciones
        if updates:
            print(f"💾 Aplicando {len(updates)} correcciones de alineación...")
            # Batch update por trozos para no saturar API
            for i in range(0, len(updates), 50):
                batch = updates[i:i+50]
                ws.batch_update(batch)
            print("✅ Limpieza completada.")
        else:
            print("✨ No se encontraron filas que requieran ajuste manual.")

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_alignment()
