import logging
import csv
import io
from flask import current_app
from backend.core.sql_database import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

class CarteraService:
    @staticmethod
    def generar_export_csv():
        """
        Generador que extrae la cartera usando cursores del servidor (streaming)
        y emite líneas CSV compatibles con Excel (UTF-8 con BOM).
        """
        # Capturamos la instancia real de la app antes de entrar al generador
        app = current_app._get_current_object()
        
        def generate():
            with app.app_context():
                # Enviar BOM de UTF-8 primero para que Excel reconozca correctamente los caracteres (tildes, eñes)
                yield '\ufeff'
                
                output = io.StringIO()
                # Excel suele preferir punto y coma para separar columnas en español
                writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                
                # Escribir encabezados requeridos exactamente
                writer.writerow(['Nombres', 'Identificacion', 'Vendedor', 'Fecha Vence', 'Valor Total', 'Por Vencer', '1 A 30', '31 A 60', '61 A 90', 'Más De 90', 'NumDias'])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

                connection = None
                try:
                    connection = db.engine.connect()
                    # Query detallado con orden contable
                    sql = text("""
                        SELECT 
                            nombre, identificacion, vendedor, fecha_vencimiento, saldo_documento 
                        FROM cartera_wo 
                        ORDER BY nombre ASC, fecha_vencimiento ASC
                    """)
                    
                    result = connection.execution_options(stream_results=True).execute(sql)
                    
                    from datetime import datetime
                    import pytz
                    
                    # Garantizar que la hora sea la correcta para Colombia
                    tz_col = pytz.timezone('America/Bogota')
                    hoy = datetime.now(tz_col).date()

                    for row in result:
                        nombre = str(row[0]).replace('\n', ' ').strip() if row[0] else ''
                        identificacion = str(row[1]).strip() if row[1] else ''
                        vendedor = str(row[2]).strip() if row[2] else ''
                        fecha_vencimiento = row[3] # Date object
                        saldo = float(row[4]) if row[4] else 0.0
                        
                        fvence_str = fecha_vencimiento.strftime('%Y-%m-%d') if fecha_vencimiento else ''
                        
                        # Variables para los rangos
                        por_vencer = 0.0
                        d1_30 = 0.0
                        d31_60 = 0.0
                        d61_90 = 0.0
                        mas_90 = 0.0
                        num_dias = 0
                        
                        if fecha_vencimiento:
                            num_dias = (hoy - fecha_vencimiento).days
                            if num_dias <= 0:
                                por_vencer = saldo
                            elif num_dias <= 30:
                                d1_30 = saldo
                            elif num_dias <= 60:
                                d31_60 = saldo
                            elif num_dias <= 90:
                                d61_90 = saldo
                            else:
                                mas_90 = saldo
                        else:
                            por_vencer = saldo

                        writer.writerow([nombre, identificacion, vendedor, fvence_str, round(saldo, 2), 
                                         round(por_vencer, 2), round(d1_30, 2), round(d31_60, 2), 
                                         round(d61_90, 2), round(mas_90, 2), num_dias])
                        yield output.getvalue()
                        output.seek(0)
                        output.truncate(0)

                except Exception as e:
                    logger.error(f"❌ Error crítico en streaming de exportación de cartera: {e}")
                    writer.writerow(['ERROR INTERNO', 'Se interrumpió la descarga debido a un fallo en el servidor.', '', '', ''])
                    yield output.getvalue()
                finally:
                    if connection:
                        connection.close()
                        logger.info("✅ Conexión de base de datos para streaming CSV cerrada de forma segura.")
                        
        return generate()
