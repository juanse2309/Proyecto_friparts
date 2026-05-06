import pandas as pd
import numpy as np
from backend.app import app, db
from backend.models.sql_models import ProduccionInyeccion

def rellenar_datos():
    with app.app_context():
        try:
            # Leemos el mismo archivo que ya tienes
            df_sheets = pd.read_csv("inyeccion_backup.csv.csv")
            
            # --- NUEVA LÍNEA: Limpia espacios invisibles o saltos de línea en los títulos ---
            df_sheets.columns = df_sheets.columns.str.strip()
            
        except FileNotFoundError:
            print("❌ Error: No se encontró el archivo 'inyeccion_backup.csv.csv'.")
            return

        # Limpiamos nulos
        df_sheets = df_sheets.replace({np.nan: None, pd.NaT: None})

        registros_actualizados = 0

        print("🔄 Buscando registros para actualizar...")
        
        # Iteramos sobre el CSV
        for index, row in df_sheets.iterrows():
            id_iny = row['ID INYECCION']
            
            # Buscamos el registro en la base de datos
            registro = ProduccionInyeccion.query.filter_by(id_inyeccion=id_iny).first()
            
            # Si existe en la BD, procedemos a actualizarlo
            if registro:
                # Solo rellenamos si una de las columnas nuevas está en NULL (ej. contador_maq)
                # Esto evita pisar datos si corres el script dos veces
                if registro.contador_maq is None:
                    registro.hora_llegada = row['HORA LLEGADA']
                    registro.hora_inicio = row['HORA INICIO']
                    registro.hora_termina = row['HORA TERMINA']
                    registro.contador_maq = row['CONTADOR MAQ.']
                    registro.cant_contador = row['CANT. CONTADOR']
                    registro.tomados_en_proceso = row['TOMADOS EN PROCESO']
                    registro.peso_tomadas_en_proceso = row['PESO TOMADAS EN PROCESO']
                    registro.almacen_destino = row['ALMACEN DESTINO']
                    registro.codigo_ensamble = row['CODIGO ENSAMBLE']
                    registro.orden_produccion = row['ORDEN PRODUCCION']
                    registro.observaciones = row['OBSERVACIONES']
                    registro.peso_vela_maquina = row['PESO VELA MAQUINA']
                    registro.peso_bujes = row['PESO BUJES']
                    registro.id_programacion = row['ID_PROGRAMACION']
                    registro.produccion_teorica = row['PRODUCCION_TEORICA']
                    registro.pnc_total = row['PNC_TOTAL']
                    registro.pnc_detalle = row['PNC_DETALLE']
                    registro.peso_lote = row['PESO_LOTE']
                    registro.calidad_responsable = row['CALIDAD_RESPONSABLE']
                    registro.entrada = row['ENTRADA']
                    
                    # --- NUEVA LÍNEA: Uso de .get() a prueba de fallos para la última columna ---
                    registro.salida = row.get('SALIDA', 0)
                    
                    registros_actualizados += 1

        try:
            # Hacemos el UPDATE masivo
            db.session.commit()
            print(f"✅ ¡Relleno Exitoso! Se rellenaron {registros_actualizados} registros con los datos faltantes.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error guardando la actualización: {e}")

if __name__ == "__main__":
    rellenar_datos()