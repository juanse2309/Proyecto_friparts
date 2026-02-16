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
    
    # Mapeo de columnas Template WO (DocumentosVentasEncabezadosMovimientoInventarioWO.xls)
    # Columnas fijas requeridas
    # A=0, ..., K=10 (Personalizado 1), ... AF=31 (Detalle: Bodega)
    
    # 1. Encabezados (A-K)
    cols_headers = [
        'Encab: Documento Número', 'Encab: Fecha', 'Encab: Tercero Externo', 'Encab: Vendedor Externo', 
        'Encab: Nota', 'Encab: Forma Pago', 'Encab: Descuento', 'Encab: IVA', 'Encab: Retención', 
        'Encab: Tipo Documento', 'Encab: Personalizado 1'
    ]
    
    # 2. Padding (L - AE) -> 20 columnas vacías (Indices 11 a 30)
    # Nombres ficticios para mantener posición, WO los ignorará si no están mapeados en su importador,
    # pero es vital que existan en el excel.
    cols_padding = [f'Encab: Personalizado {i}' for i in range(2, 22)] 
    # range(2, 22) genera 2, 3... 21.  Total 20 items.
    # 11 + 20 = 31 columnas. La siguiente será la 32 (Indice 31, col AF).
    
    # 3. Detalle (AF en adelante)
    cols_detalle = [
        'Detalle: Bodega', 'Detalle: Producto', 'Detalle: Cantidad', 
        'Detalle: Valor Unitario', 'Detalle: Valor Total', 
        'Detalle: Descripción', 'Detalle: Unidad Medida', 'Detalle: Centro Costo'
    ]
    
    columnas_plantilla = cols_headers + cols_padding + cols_detalle
    
    for p in pedidos_pendientes:
        # Cruce Cliente
        nombre_cliente = str(p.get('CLIENTE', '')).strip().upper()
        nit_cliente = mapa_clientes.get(nombre_cliente, p.get('NIT', '')) # Fallback a NIT del pedido
        
        # Cruce Producto
        id_codigo = str(p.get('ID CODIGO', '')).strip()
        data_prod = mapa_productos.get(id_codigo, {})
        precio_venta = data_prod.get('PRECIO', p.get('PRECIO UNITARIO', 0)) # Fallback a precio pedido
        descripcion = data_prod.get('DESCRIPCION', p.get('PRODUCTO', ''))
        
        # Formatos
        try:
            fecha_raw = p.get('FECHA', '')
            fecha_fmt = pd.to_datetime(fecha_raw).strftime('%d/%m/%Y') if fecha_raw else datetime.now().strftime('%d/%m/%Y')
        except:
            fecha_fmt = datetime.now().strftime('%d/%m/%Y')
            
        cantidad = p.get('CANTIDAD', 0)
        
        row = {
            'Encab: Tipo Documento': 'PED',
            'Encab: Tercero Externo': nit_cliente,
            'Encab: Fecha': fecha_fmt,
            'Encab: Nota': 'Carga Automática App Manufactura',
            'Encab: Personalizado 1': str(p.get('ID PEDIDO', '')), # ID Pedido para rastreo
            'Detalle: Bodega': '01',
            'Detalle: Producto': id_codigo,
            'Detalle: Descripción': descripcion,
            'Detalle: Cantidad': cantidad,
            'Detalle: Valor Unitario': precio_venta,
            'Encab: Vendedor Externo': p.get('VENDEDOR', ''),
             # Campos vacíos requeridos por estructura
            'Encab: Documento Número': '', # Dejar vacío para consecutivo automático WO? O usar el del pedido? WO suele asignar.
            'Encab: Forma Pago': '', 
            'Encab: Descuento': 0,
            'Encab: IVA': 0,
            'Encab: Retención': 0,
            'Detalle: Valor Total': 0, # WO recalcula
            'Detalle: Unidad Medida': '',
            'Detalle: Centro Costo': ''
        }
        
        # Rellenar padding con vacíos explicitamente en el row (opcional si se hace en dataframe, pero mejor asegurar)
        for col_pad in cols_padding:
            row[col_pad] = ""
            
        rows_finales.append(row)
        
    df = pd.DataFrame(rows_finales)
    
    # Asegurar columnas de plantilla
    for col in columnas_plantilla:
        if col not in df.columns:
            df[col] = "" # Rellenar vacías
            
    # Reordenar
    if not df.empty:
        df = df[columnas_plantilla]
        
    return df

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

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ImportarWO')
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Import_WO_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )

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
