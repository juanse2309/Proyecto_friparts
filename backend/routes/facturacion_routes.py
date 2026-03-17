from flask import Blueprint, request, jsonify, send_file
import pandas as pd
import io
from datetime import datetime
import logging
from backend.config.settings import Hojas
from backend.core.database import sheets_client
from gspread.utils import rowcol_to_a1

facturacion_bp = Blueprint('facturacion_bp', __name__)
logger = logging.getLogger(__name__)

# Helper local para reemplazar obtener_hoja de app.py
def obtener_hoja(nombre_hoja):
    return sheets_client.get_or_create_worksheet(nombre_hoja)


def procesar_datos_wo(ids_filter=None):
    """Lógica centralizada para filtrar, cruzar y formatear datos WO v2.
       ids_filter: Lista opcional de 'ID PEDIDO' para exportar solo esos.
    """
    # 1. Obtener Datos
    ws_pedidos = obtener_hoja(Hojas.PEDIDOS)
    registros_pedidos = ws_pedidos.get_all_records()
    
    # Filtro: ESTADO == 'PENDIENTE'
    pedidos_pendientes = [r for r in registros_pedidos if str(r.get('ESTADO', '')).strip().upper() == 'PENDIENTE']
    
    # Filtro adicional por selección de usuario
    if ids_filter and len(ids_filter) > 0:
        ids_set = set(str(x) for x in ids_filter)
        pedidos_pendientes = [r for r in pedidos_pendientes if str(r.get('ID PEDIDO', '')) in ids_set]
    
    if not pedidos_pendientes:
        return pd.DataFrame()

    # 2. Obtener Maestros (Clientes y Productos)
    try:
        ws_clientes = obtener_hoja(Hojas.CLIENTES)
        registros_clientes = ws_clientes.get_all_records()
        mapa_clientes = {str(c.get('CLIENTE', '')).strip().upper(): str(c.get('NIT', '')).strip() for c in registros_clientes}
    except Exception as e:
        logger.error(f"Error leyendo Clientes: {e}")
        mapa_clientes = {}

    try:
        ws_productos = obtener_hoja(Hojas.PRODUCTOS)
        registros_productos = ws_productos.get_all_records()
        mapa_productos = {}
        for p in registros_productos:
            id_cod = str(p.get('ID CODIGO', '')).strip()
            if id_cod:
                mapa_productos[id_cod] = {
                    'PRECIO': p.get('PRECIO', 0),
                    'DESCRIPCION': p.get('DESCRIPCION', '')
                }
    except Exception as e:
        logger.error(f"Error leyendo Productos: {e}")
        mapa_productos = {}

    # 3. Procesar Filas
    rows_finales = []
    
    # Mapeo estricto de columnas requerido por World Office
    columnas_wo = [
        'Encab: Empresa',
        'Encab: Tipo Documento',
        'Encab: Prefijo',
        'Encab: Documento Número',
        'Encab: Fecha',
        'Encab: Tercero Interno',
        'Encab: Tercero Externo',
        'Encab: Nota',
        'Encab: FormaPago',
        'Encab: Fecha Entrega'
    ]
    
    # Personalizado 1 al 15 vacíos
    for i in range(1, 16):
        columnas_wo.append(f'Encab: Personalizado {i}')
        
    columnas_wo.extend([
        'Encab: Sucursal',
        'Detalle: Producto',
        'Detalle: Bodega',
        'Detalle: UnidadDeMedida',
        'Detalle: Cantidad',
        'Detalle: IVA',
        'Detalle: Valor Unitario',
        'Detalle: Descuento'
    ])
    
    for p in pedidos_pendientes:
        # Cruce Cliente
        nombre_cliente = str(p.get('CLIENTE', '')).strip().upper()
        nit_cliente = mapa_clientes.get(nombre_cliente, p.get('NIT', '')) # Fallback a NIT del pedido
        
        # Cruce Producto
        id_codigo = str(p.get('ID CODIGO', '')).strip()
        data_prod = mapa_productos.get(id_codigo, {})
        precio_venta = data_prod.get('PRECIO', p.get('PRECIO UNITARIO', 0)) # Fallback a precio pedido
        
        # Formatos
        try:
            fecha_raw = p.get('FECHA', '')
            fecha_fmt = pd.to_datetime(fecha_raw).strftime('%d/%m/%Y') if fecha_raw else datetime.now().strftime('%d/%m/%Y')
        except:
            fecha_fmt = datetime.now().strftime('%d/%m/%Y')
            
        cantidad = p.get('CANTIDAD', 0)
        
        row = {
            'Encab: Empresa': 'FRIPARTS SAS',
            'Encab: Tipo Documento': 'PD',
            'Encab: Prefijo': '',
            'Encab: Documento Número': str(p.get('ID PEDIDO', '')),
            'Encab: Fecha': fecha_fmt,
            'Encab: Tercero Interno': '9003153002',
            'Encab: Tercero Externo': nit_cliente,
            'Encab: Nota': str(p.get('COMENTARIOS', '')),
            'Encab: FormaPago': str(p.get('FORMA DE PAGO', '')),
            'Encab: Fecha Entrega': fecha_fmt,
            'Encab: Sucursal': 'Principal',
            'Detalle: Producto': id_codigo,
            'Detalle: Bodega': 'Principal',
            'Detalle: UnidadDeMedida': 'Und.',
            'Detalle: Cantidad': cantidad,
            'Detalle: IVA': 0.19,
            'Detalle: Valor Unitario': precio_venta,
            'Detalle: Descuento': p.get('DESCUENTO %', 0) or 0
        }
        
        # Rellenar todos los 'Encab: Personalizado X' con vacío
        for i in range(1, 16):
            row[f'Encab: Personalizado {i}'] = ""
            
        rows_finales.append(row)
        
    df = pd.DataFrame(rows_finales)
    
    # Asegurar orden exacto
    if not df.empty:
        # Asegurarse de que las columnas faltantes existan, por si acaso
        for col in columnas_wo:
            if col not in df.columns:
                df[col] = "" 
        df = df[columnas_wo]
        
    return df

def actualizar_estado_exportado(ids_exportados):
    """Actualiza el estado de los pedidos a 'EXPORTADO_WO' en Google Sheets"""
    if not ids_exportados:
        return 0
        
    ws_pedidos = obtener_hoja(Hojas.PEDIDOS)
    registros = ws_pedidos.get_all_records()
    
    # Obtener el índice de la columna ESTADO
    try:
        encabezados = ws_pedidos.row_values(1)
        if 'ESTADO' not in encabezados:
            logger.error("Columna ESTADO no encontrada en PEDIDOS")
            return 0
        col_estado_idx = encabezados.index('ESTADO') + 1 # 1-based index
    except Exception as e:
        logger.error(f"Error obteniendo cabeceras de PEDIDOS: {e}")
        return 0
        
    ids_set = set(str(x) for x in ids_exportados)
    updates_batch = []
    filas_actualizadas = 0
    
    for idx, r in enumerate(registros):
        id_pedido = str(r.get('ID PEDIDO', ''))
        estado_actual = str(r.get('ESTADO', '')).strip().upper()
        
        # Actualizamos la fila (idx+2 porque registros ignora cabecera y list_index es 0-based)
        if id_pedido in ids_set and estado_actual == 'PENDIENTE':
            fila_sheet = idx + 2
            celda = f"{rowcol_to_a1(fila_sheet, col_estado_idx)}"
            updates_batch.append({'range': celda, 'values': [['EXPORTADO_WO']]})
            filas_actualizadas += 1
            
    if updates_batch:
        try:
            ws_pedidos.batch_update(updates_batch, value_input_option='USER_ENTERED')
            logger.info(f"Actualizados {filas_actualizadas} pedidos a EXPORTADO_WO")
        except Exception as e:
            logger.error(f"Error en batch_update de PEDIDOS: {e}")
            return 0
            
    return filas_actualizadas



@facturacion_bp.route('/api/facturacion/pedidos-pendientes', methods=['GET'])
def obtener_pedidos_pendientes():
    """
    Obtiene los pedidos con estado 'PENDIENTE' para ser mostrados en la interfaz de exportación World Office.
    Agrupa los items por ID PEDIDO.
    """
    try:
        ws = obtener_hoja(Hojas.PEDIDOS)
        registros = ws.get_all_records()
        
        # Filtrar solo 'PENDIENTE' (pedidos recién subidos por Andrés)
        # Estos son los que necesitan ser exportados a World Office para preparación
        pendientes = [r for r in registros if str(r.get('ESTADO', '')).upper() == 'PENDIENTE']
        
        # Agrupar por ID
        pedidos_agrupados = {}
        
        for r in pendientes:
            id_pedido = str(r.get('ID PEDIDO', ''))
            if not id_pedido: continue
            
            if id_pedido not in pedidos_agrupados:
                pedidos_agrupados[id_pedido] = {
                    'id': id_pedido,
                    'fecha': r.get('FECHA', ''),
                    'cliente': r.get('CLIENTE', ''),
                    'vendedor': r.get('VENDEDOR', ''),
                    'items_count': 0,
                    'total': 0,
                    'items': []
                }
            
            # Sumar total (precaución con formatos de moneda)
            precio = r.get('PRECIO UNITARIO', 0) or r.get('PRECIO', 0)
            if isinstance(precio, str):
                precio = float(precio.replace('$', '').replace(',', '').strip() or 0)
            
            cantidad = float(r.get('CANTIDAD', 0) or 0)
            
            pedidos_agrupados[id_pedido]['items_count'] += 1
            pedidos_agrupados[id_pedido]['total'] += (precio * cantidad)
            pedidos_agrupados[id_pedido]['items'].append(r)
            
        # Convertir a lista y ordenar por fecha descendente
        resultado = list(pedidos_agrupados.values())
        resultado.sort(key=lambda x: x['fecha'], reverse=True)
        
        return jsonify({'success': True, 'pedidos': resultado})

    except Exception as e:
        logger.error(f"❌ Error obteniendo pedidos pendientes: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@facturacion_bp.route('/api/exportar/world-office', methods=['POST'])
def exportar_world_office():
    """
    Genera el archivo Excel para World Office (v2).
    Acepta 'ids' en el body para filtrar.
    """
    try:
        data = request.get_json(silent=True) or {}
        ids_filter = data.get('ids', None) # Lista de IDs seleccionados
        
        df = procesar_datos_wo(ids_filter)
        
        if df.empty:
            return jsonify({'success': False, 'error': 'No hay datos válidos para exportar (verifique el estado PENDIENTE)'}), 400

        # Obtener los IDs únicos de los pedidos que realmente están siendo exportados
        ids_exportados = df['Encab: Documento Número'].unique().tolist()

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ImportarWO')
        
        output.seek(0)
        
        # Actualizar estado a EXPORTADO_WO en un thread o aquí mismo
        pedidos_actualizados = actualizar_estado_exportado(ids_exportados)
        
        # Custom headers para dar feedback al frontend
        response = send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Pedidos_WO_{datetime.now().strftime("%Y-%m-%d")}.xlsx'
        )
        response.headers['X-Pedidos-Actualizados'] = str(pedidos_actualizados)
        response.headers['Access-Control-Expose-Headers'] = 'X-Pedidos-Actualizados'
        return response

    except Exception as e:
        logger.error(f"❌ Error Exportando WO: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@facturacion_bp.route('/api/exportar/world-office/preview', methods=['POST'])
def preview_world_office():
    """
    Retorna JSON con los datos que se exportarían para vista previa.
    Acepta 'ids' en el body para filtrar.
    """
    try:
        data = request.get_json(silent=True) or {}
        ids_filter = data.get('ids', None)
        
        df = procesar_datos_wo(ids_filter)
        
        if df.empty:
            return jsonify({'success': True, 'data': []})
            
        # Convertir a dict para JSON
        # Reemplazar NaN con null o string vacío
        preview_data = df.fillna('').head(50).to_dict(orient='records')
        
        return jsonify({'success': True, 'data': preview_data})
        
    except Exception as e:
        logger.error(f"Error generando preview WO: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
