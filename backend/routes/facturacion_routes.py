from flask import Blueprint, request, jsonify, send_file, session
from backend.utils.auth_middleware import require_role
import pandas as pd
import io
import re
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


def obtener_mapa_vendedores():
    """Mapea nombres de responsables a sus documentos de identidad."""
    try:
        ws = obtener_hoja(Hojas.RESPONSABLES)
        records = ws.get_all_records()
        # Mapa de nombres normalizados a documentos
        return {str(r.get('RESPONSABLE', r.get('NOMBRE', ''))).strip().upper(): str(r.get('DOCUMENTO', '')).strip() for r in records}
    except Exception as e:
        logger.error(f"Error mapeando vendedores: {e}")
        return {}


def procesar_datos_wo(ids_filter=None, consecutivo_inicial=None):
    """Lógica centralizada para filtrar, cruzar y formatear datos WO v2.
       ids_filter: Lista opcional de 'ID PEDIDO' para exportar solo esos.
       consecutivo_inicial: Valor numérico opcional para iniciar el conteo serial.
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
        return pd.DataFrame(), {}

    # Ordenar por fecha o ID original para mantener un orden predecible en la asignación serial
    # (El ID PEDIDO suele ser cronológico PED9600, PED9601...)
    pedidos_pendientes.sort(key=lambda x: str(x.get('ID PEDIDO', '')))

    # ... (obtener mapa_clientes y mapa_productos igual que antes)
    # ... (omitido aquí por brevedad, se mantiene el código original de clientes y productos)

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
    
    # Mapeo estricto de 57 columnas requerido por World Office (OLE DB)
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
        'Encab: Fecha Entrega',
        'Encab: Prefijo Documento Externo',
        'Encab: Número_Documento_Externo',
        'Encab: Verificado',
        'Encab: Anulado',
        'Encab: Personalizado 1',
        'Encab: Personalizado 2',
        'Encab: Personalizado 3',
        'Encab: Personalizado 4',
        'Encab: Personalizado 5',
        'Encab: Personalizado 6',
        'Encab: Personalizado 7',
        'Encab: Personalizado 8',
        'Encab: Personalizado 9',
        'Encab: Personalizado 10',
        'Encab: Personalizado 11',
        'Encab: Personalizado 12',
        'Encab: Personalizado 13',
        'Encab: Personalizado 14',
        'Encab: Personalizado 15',
        'Encab: Sucursal',
        'Encab: Clasificación',
        'Detalle: Producto',
        'Detalle: Bodega',
        'Detalle: UnidadDeMedida',
        'Detalle: Cantidad',
        'Detalle: IVA',
        'Detalle: Valor Unitario',
        'Detalle: Descuento',
        'Detalle: Vencimiento',
        'Detalle: Nota',
        'Detalle: Centro costos',
        'Detalle: Personalizado1',
        'Detalle: Personalizado2',
        'Detalle: Personalizado3',
        'Detalle: Personalizado4',
        'Detalle: Personalizado5',
        'Detalle: Personalizado6',
        'Detalle: Personalizado7',
        'Detalle: Personalizado8',
        'Detalle: Personalizado9',
        'Detalle: Personalizado10',
        'Detalle: Personalizado11',
        'Detalle: Personalizado12',
        'Detalle: Personalizado13',
        'Detalle: Personalizado14',
        'Detalle: Personalizado15',
        'Detalle: Código Centro Costos'
    ]
    
    # Diccionario para agrupar ítems por ID PEDIDO y asignarles el mismo consecutivo
    mapeo_consecutivos = {}
    
    # Manejo de consecutivo inicial manual
    consecutivo_actual = None
    if consecutivo_inicial and str(consecutivo_inicial).strip():
        try:
            consecutivo_actual = int(str(consecutivo_inicial).strip())
            logger.info(f"DEBUG: Consecutivo inicial recibido: {consecutivo_inicial} -> {consecutivo_actual}")
        except (ValueError, TypeError):
            consecutivo_actual = None
            logger.error(f"DEBUG: Error parseando consecutivo_inicial: {consecutivo_inicial}")
    else:
        logger.info("DEBUG: No se recibió consecutivo_inicial, usando IDs originales")

    # Mapeo de Vendedores dinámico (desde RESPONSABLES)
    vendedores_ids = obtener_mapa_vendedores()
    
    for p in pedidos_pendientes:
        id_pedido_original = str(p.get('ID PEDIDO', '')).strip()
        
        # Determinar el consecutivo a usar
        if id_pedido_original not in mapeo_consecutivos:
            if consecutivo_actual is not None:
                new_id = str(consecutivo_actual)
                consecutivo_actual += 1
            else:
                # Comportamiento por defecto: Extraer solo números del ID original (ej: PED9643 -> 9643)
                new_id = re.sub(r'[^0-9]', '', id_pedido_original)
            
            mapeo_consecutivos[id_pedido_original] = new_id
        
        doc_numero_wo = mapeo_consecutivos[id_pedido_original]
        
        # Cruce Cliente
        nombre_cliente = str(p.get('CLIENTE', '')).strip().upper()
        nit_raw = mapa_clientes.get(nombre_cliente, p.get('NIT', '')) # Fallback a NIT del pedido
        
        # Limpieza NIT (Extraer solo el primer bloque de números)
        match_nit = re.search(r'(\d+)', str(nit_raw))
        nit_limpio = match_nit.group(1) if match_nit else str(nit_raw).strip()
        
        # Cruce Producto
        id_codigo = str(p.get('ID CODIGO', '')).strip()
        data_prod = mapa_productos.get(id_codigo, {})
        precio_venta = data_prod.get('PRECIO', p.get('PRECIO UNITARIO', 0)) # Fallback a precio pedido
        
        # Formatos de Fecha
        try:
            fecha_raw = p.get('FECHA', '')
            fecha_fmt = pd.to_datetime(fecha_raw).strftime('%d/%m/%Y') if fecha_raw else datetime.now().strftime('%d/%m/%Y')
        except:
            fecha_fmt = datetime.now().strftime('%d/%m/%Y')
            
        cantidad = p.get('CANTIDAD', 0)
        
        # Limpieza Forma de Pago (Quitar tildes)
        forma_pago_raw = str(p.get('FORMA DE PAGO', ''))
        forma_pago_fmt = forma_pago_raw.replace('é', 'e').replace('É', 'E').replace('á', 'a').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        
        # Mapeo Vendedor (Tercero Interno)
        vendedor_nombre = str(p.get('VENDEDOR', '')).strip().upper()
        vendedor_id = vendedores_ids.get(vendedor_nombre, '900315300') # Fallback solicitado
        
        # Descuento siempre numérico (porcentaje decimal para WO: ej. 50% -> 0.5)
        try:
            val_desc = p.get('DESCUENTO %', 0)
            if val_desc is None or str(val_desc).strip() == "":
                descuento_num = 0.0
            else:
                # Si viene como string '50%' lo limpiamos
                raw_desc = str(val_desc).replace('%', '').strip()
                descuento_num = float(raw_desc) / 100.0
        except:
            descuento_num = 0.0
        
        # Iniciar diccionario con todas las claves y valor por defecto ""
        row = {col: "" for col in columnas_wo}
        
        # Sobrescribir los mapeados y valores fijos
        row['Encab: Empresa'] = 'FRIPARTS SAS'
        row['Encab: Tipo Documento'] = 'PED'
        row['Encab: Prefijo'] = 'PED'
        row['Encab: Documento Número'] = doc_numero_wo
        row['Encab: Fecha'] = fecha_fmt
        row['Encab: Tercero Interno'] = vendedor_id
        row['Encab: Tercero Externo'] = nit_limpio
        row['Encab: Nota'] = 'PEDIDO'
        row['Encab: FormaPago'] = forma_pago_fmt
        row['Encab: Fecha Entrega'] = fecha_fmt
        row['Encab: Sucursal'] = ''
        row['Detalle: Producto'] = id_codigo
        row['Detalle: Bodega'] = 'Principal'
        row['Detalle: UnidadDeMedida'] = 'Und.'
        row['Detalle: Cantidad'] = cantidad
        row['Detalle: IVA'] = 0.19
        row['Detalle: Valor Unitario'] = precio_venta
        row['Detalle: Descuento'] = descuento_num
        row['Detalle: Vencimiento'] = fecha_fmt
        
        rows_finales.append(row)
        
    df = pd.DataFrame(rows_finales)
    
    # Asegurar orden exacto preestablecido
    if not df.empty:
        df = df[columnas_wo]
        
    return df, mapeo_consecutivos

def actualizar_estado_exportado(pedidos_consecutivos):
    """Actualiza el estado de los pedidos a 'EXPORTADO_WO' y guarda el consecutivo en Google Sheets.
       pedidos_consecutivos: Diccionario {id_pedido: consecutivo}
    """
    if not pedidos_consecutivos:
        return 0
        
    ws_pedidos = obtener_hoja(Hojas.PEDIDOS)
    registros = ws_pedidos.get_all_records()
    
    # Obtener índices de columnas
    try:
        encabezados = ws_pedidos.row_values(1)
        if 'ESTADO' not in encabezados:
            logger.error("Columna ESTADO no encontrada en PEDIDOS")
            return 0
        col_estado_idx = encabezados.index('ESTADO') + 1

        if 'ID PEDIDO' not in encabezados:
            logger.error("Columna ID PEDIDO no encontrada en PEDIDOS")
            return 0
        col_id_idx = encabezados.index('ID PEDIDO') + 1
        
        # Asegurar columna WO_CONSECUTIVO
        if 'WO_CONSECUTIVO' not in encabezados:
            col_wo_idx = len(encabezados) + 1
            ws_pedidos.update_cell(1, col_wo_idx, 'WO_CONSECUTIVO')
        else:
            col_wo_idx = encabezados.index('WO_CONSECUTIVO') + 1
            
    except Exception as e:
        logger.error(f"Error obteniendo cabeceras de PEDIDOS: {e}")
        return 0
        
    updates_batch = []
    filas_actualizadas = 0
    
    for idx, r in enumerate(registros):
        id_pedido = str(r.get('ID PEDIDO', ''))
        estado_actual = str(r.get('ESTADO', '')).strip().upper()
        
        if id_pedido in pedidos_consecutivos and estado_actual == 'PENDIENTE':
            consecutivo = pedidos_consecutivos[id_pedido]
            fila_sheet = idx + 2
            
            # Update ESTADO
            updates_batch.append({
                'range': f"{rowcol_to_a1(fila_sheet, col_estado_idx)}",
                'values': [['EXPORTADO_WO']]
            })
            # Update WO_CONSECUTIVO
            updates_batch.append({
                'range': f"{rowcol_to_a1(fila_sheet, col_wo_idx)}",
                'values': [[consecutivo]]
            })
            
            # NUEVO: Sincronizar ID PEDIDO de vuelta a la hoja si cambió (formato PEDXXXX)
            new_id_ped = f"PED{consecutivo}"
            if id_pedido != new_id_ped:
                updates_batch.append({
                    'range': f"{rowcol_to_a1(fila_sheet, col_id_idx)}",
                    'values': [[new_id_ped]]
                })
                
            filas_actualizadas += 1
            
    if updates_batch:
        try:
            ws_pedidos.batch_update(updates_batch, value_input_option='USER_ENTERED')
            logger.info(f"Actualizados {filas_actualizadas} items con estados y consecutivos WO")
        except Exception as e:
            logger.error(f"Error en batch_update de PEDIDOS: {e}")
            return 0
            
    return filas_actualizadas



@facturacion_bp.route('/api/facturacion/pedidos-pendientes', methods=['GET'])
@require_role(['administracion', 'jefe almacen'])
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
@require_role(['administracion', 'jefe almacen'])
def exportar_world_office():
    """
    Genera el archivo Excel para World Office (v2).
    Acepta 'ids' en el body para filtrar.
    """
    try:
        data = request.get_json(silent=True) or {}
        ids_filter = data.get('ids', None) # Lista de IDs seleccionados
        consecutivo_inicial = data.get('consecutivo_inicial', None)
        
        print(f"DEBUG: [Exportar WO] ids: {len(ids_filter) if ids_filter else 'ALL'}, consecutivo: {consecutivo_inicial}")
        
        df, mapeo_consecutivos = procesar_datos_wo(ids_filter, consecutivo_inicial)
        
        if df.empty:
            return jsonify({'success': False, 'error': 'No hay datos válidos para exportar (verifique el estado PENDIENTE)'}), 400

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ImportarWO')
        
        output.seek(0)
        
        # Actualizar estado a EXPORTADO_WO y guardar consecutivos en PEDIDOS
        pedidos_actualizados = actualizar_estado_exportado(mapeo_consecutivos)
        
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
@require_role(['administracion', 'jefe almacen'])
def preview_world_office():
    """
    Retorna JSON con los datos que se exportarían para vista previa.
    Acepta 'ids' en el body para filtrar.
    """
    try:
        data = request.get_json(silent=True) or {}
        ids_filter = data.get('ids', None)
        consecutivo_inicial = data.get('consecutivo_inicial', None)
        
        print(f"DEBUG: [Preview WO] ids: {len(ids_filter) if ids_filter else 'ALL'}, consecutivo: {consecutivo_inicial}")
        
        df, _ = procesar_datos_wo(ids_filter, consecutivo_inicial)
        
        if df.empty:
            return jsonify({'success': True, 'data': []})
            
        # Convertir a dict para JSON
        # Reemplazar NaN con null o string vacío
        preview_data = df.fillna('').head(50).to_dict(orient='records')
        
        return jsonify({
            'success': True, 
            'data': preview_data,
            'debug_params': {
                'ids_count': len(ids_filter) if ids_filter else 0,
                'consecutivo_recibido': consecutivo_inicial
            }
        })
        
    except Exception as e:
        logger.error(f"Error generando preview WO: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
