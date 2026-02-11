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

@facturacion_bp.route('/api/exportar/world-office', methods=['POST'])
def exportar_world_office():
    """
    Genera un archivo Excel compatible con World Office a partir de pedidos pendientes.
    """
    try:
        data = request.json
        consecutivo_inicio = int(data.get('consecutivo', 0))
        pedidos_ids = data.get('pedidos', []) # Lista de ID PEDIDO

        if not consecutivo_inicio or not pedidos_ids:
            return jsonify({'success': False, 'error': 'Faltan datos requeridos (consecutivo o pedidos)'}), 400

        logger.info(f"📄 Iniciando exportación WO. Consecutivo: {consecutivo_inicio}, Pedidos: {len(pedidos_ids)}")

        # 1. Obtener Datos
        ws_pedidos = obtener_hoja(Hojas.PEDIDOS)
        registros_pedidos = ws_pedidos.get_all_records()
        
        # Filtrar solo los pedidos seleccionados (Robustez con strip)
        pedidos_filtrados = [r for r in registros_pedidos if str(r.get('ID PEDIDO', '')).strip() in pedidos_ids]
        
        if not pedidos_filtrados:
            return jsonify({'success': False, 'error': 'No se encontraron los pedidos seleccionados'}), 404

        # Obtener Productos (para cruzar códigos) y Responsables (para vendedores)
        # Usamos cache si está disponible o fetch directo
        ws_productos = obtener_hoja(Hojas.PRODUCTOS)
        productos_raw = ws_productos.get_all_records()
        
        ws_responsables = obtener_hoja(Hojas.RESPONSABLES)
        responsables_raw = ws_responsables.get_all_records()

        # Crear diccionarios de cruce
        # Mapa: ID CODIGO -> CODIGO SISTEMA
        mapa_productos = {}
        for p in productos_raw:
            id_cod = str(p.get('ID CODIGO', '')).strip().upper()
            cod_sistema = str(p.get('CODIGO SISTEMA', '') or p.get('CODIGO', '')).strip().upper()
            if id_cod:
                mapa_productos[id_cod] = cod_sistema
        
        # Mapa: NOMBRE VENDEDOR -> DOCUMENTO
        mapa_vendedores = {}
        for r in responsables_raw:
            nombre = str(r.get('RESPONSABLE', '')).strip().upper()  # CORREGIDO: era 'NOMBRE', ahora 'RESPONSABLE'
            doc = str(r.get('DOCUMENTO', '')).strip()
            if nombre:
                mapa_vendedores[nombre] = doc

        # 2. Procesar Datos
        wo_rows = []
        
        # Agrupar por Pedido para asignar consecutivos
        # Importante: Mantener el orden de pedidos_ids para asignar consecutivos en orden
        # O agrupar por ID PEDIDO primero
        
        # Crear un dict de pedidos para acceso rápido
        pedidos_dict = {}
        for r in pedidos_filtrados:
            id_p = str(r.get('ID PEDIDO', '')).strip() # Corregido: strip() aquí también
            if id_p not in pedidos_dict:
                pedidos_dict[id_p] = []
            pedidos_dict[id_p].append(r)
            
        consecutivo_actual = consecutivo_inicio
        
        for id_p in pedidos_ids: # Iterar en el orden enviado por el frontend
            # Asegurar que id_p busqueda tambien este limpio (aunque deberia venir limpio)
            id_p_clean = str(id_p).strip()
            
            if id_p_clean not in pedidos_dict:
                continue
                
            items_pedido = pedidos_dict[id_p_clean]
            
            # Datos de cabecera (tomados del primer item)
            primer_item = items_pedido[0]
            fecha_original = str(primer_item.get('FECHA', '')).strip()
            
            # Formatear fecha a DD/MM/YYYY
            fecha_wo = fecha_original
            try:
                # Intenta parsear ISO YYYY-MM-DD
                if '-' in fecha_original:
                    dt = datetime.strptime(fecha_original, '%Y-%m-%d')
                    fecha_wo = dt.strftime('%d/%m/%Y')
            except ValueError:
                # Si falla, intenta mantener original o loggear
                pass
            
            # Vendedor -> Tercero Interno (Documento)
            vendedor_nombre = str(primer_item.get('VENDEDOR', '')).strip().upper()
            tercero_interno = mapa_vendedores.get(vendedor_nombre, vendedor_nombre) 
            
            # Debug log
            if tercero_interno == vendedor_nombre:
                logger.warning(f"⚠️ NO MATCH VENDEDOR. Buscado: '{vendedor_nombre}'. Disponibles: {list(mapa_vendedores.keys())[:5]}...")
            else:
                logger.info(f"✅ Match Vendedor: '{vendedor_nombre}' -> '{tercero_interno}'")

            # Cliente (NIT)
            nit_cliente = str(primer_item.get('NIT', '')).strip()
            nit_limpio = ''.join(filter(str.isdigit, nit_cliente))
            nombre_cliente = str(primer_item.get('CLIENTE', '')).strip().upper()
            
            doc_numero = consecutivo_actual
            logger.info(f"📋 Procesando pedido {id_p_clean} → Consecutivo: {doc_numero}")
            consecutivo_actual += 1
            
            for item in items_pedido:
                # Datos de detalle
                id_codigo = str(item.get('ID CODIGO', '')).strip().upper()
                codigo_sistema = mapa_productos.get(id_codigo, f"NO-MAP-{id_codigo}")
                
                cantidad = item.get('CANTIDAD', 0)
                try:
                    cantidad = float(cantidad)
                except:
                    cantidad = 0
                    
                # Precio
                precio_raw = item.get('PRECIO UNITARIO', 0) or item.get('PRECIO', 0)
                if isinstance(precio_raw, str):
                    precio_limpio = precio_raw.replace('$', '').replace(',', '').strip()
                    try: 
                        precio = float(precio_limpio)
                    except: 
                        precio = 0
                else:
                    precio = float(precio_raw)
                
                row = {
                    'Encab: Empresa': nombre_cliente, # Petición usuario: Nombre Cliente en Empresa
                    'Encab: Tipo Documento': 'PED',
                    'Encab: Prefijo': 'PED',
                    'Encab: Documento Número': doc_numero,
                    'Encab: Fecha': fecha_wo,
                    'Encab: Tercero Interno': tercero_interno,
                    'Encab: Tercero Externo': nit_limpio,
                    'Encab: Nota': 'Pedido',
                    'Encab: FormaPago': 'Credito',
                    'Detalle: Producto': codigo_sistema,
                    'Detalle: Bodega': 'Principal',
                    'Detalle: UnidadDeMedida': 'Und.',
                    'Detalle: Cantidad': cantidad,
                    'Detalle: IVA': '0,19',
                    'Detalle: Valor Unitario': precio,
                    'Detalle: Vencimiento': fecha_wo
                }
                wo_rows.append(row)
        
        # 3. Generar Excel usando Plantilla
        
        # Ruta absoluta al archivo de plantilla
        from flask import current_app

        # 3. Generar Excel usando Plantilla
        
        # Ruta absoluta al archivo de plantilla
        from flask import current_app
        import os
        
        # Asumiendo estructura de proyecto:
        # /backend/routes/facturacion_routes.py
        # /frontend/static/docs/...
        
        # current_app.root_path apunta a /backend (generalmente)
        PROJECT_ROOT = os.path.dirname(current_app.root_path) 
        TEMPLATE_PATH = os.path.join(PROJECT_ROOT, 'frontend', 'static', 'docs', 'DocumentosComprasEncabezadosMovimientoInventarioWO.xls')
        
        if not os.path.exists(TEMPLATE_PATH):
            raise FileNotFoundError(f"No se encontró la plantilla en: {TEMPLATE_PATH}")
            
        # Leer columnas de la plantilla (requiere xlrd)
        df_template = pd.read_excel(TEMPLATE_PATH)
        columnas_plantilla = list(df_template.columns)
        
        # Ajustar nombres de columnas de filas generadas para coincidir EXACTAMENTE con plantilla
        # Mapeo de mis campos internos -> campos de plantilla
        mapa_columnas = {
            'Encab: Empresa': 'Encab: Empresa',
            'Encab: Tipo Documento': 'Encab: Tipo Documento',
            'Encab: Prefijo': 'Encab: Prefijo',
            'Encab: Documento Número': 'Encab: Documento Número',
            'Encab: Fecha': 'Encab: Fecha',
            'Encab: Tercero Interno': 'Encab: Tercero Interno',
            'Encab: Tercero Externo': 'Encab: Tercero Externo',
            'Encab: Nota': 'Encab: Nota',
            'Encab: FormaPago': 'Encab: FormaPago',
            'Detalle: Producto': 'Detalle: Producto',
            'Detalle: Bodega': 'Detalle: Bodega',
            'Detalle: UnidadDeMedida': 'Detalle: UnidadDeMedida',
            'Detalle: Cantidad': 'Detalle: Cantidad',
            'Detalle: IVA': 'Detalle: IVA',
            'Detalle: Valor Unitario': 'Detalle: Valor Unitario',
            'Detalle: Vencimiento': 'Detalle: Vencimiento'
        }
        
        rows_finales = []
        for row_data in wo_rows:
            new_row = {}
            # Inicializar todas las columnas de la plantilla con vacío
            for col in columnas_plantilla:
                new_row[col] = "" # O None
            
            # Llenar datos conocidos
            for key, val in row_data.items():
                if key in mapa_columnas:
                    target_col = mapa_columnas[key]
                    if target_col in new_row:
                        new_row[target_col] = val
            
            # Defaults fijos si la plantilla lo requiere
            if 'Encab: Estado' in new_row: new_row['Encab: Estado'] = 'Aprobado' # Ejemplo
            
            rows_finales.append(new_row)
            
        df = pd.DataFrame(rows_finales, columns=columnas_plantilla)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ImportarWO')
        
        output.seek(0)
        
        filename = f"Export_WO_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"❌ Error exportando WO: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

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
