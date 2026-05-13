from flask import Blueprint, request, jsonify, send_file
from backend.utils.auth_middleware import require_role, ROL_ADMINS
import pandas as pd
import io
import re
from datetime import datetime
import logging
from backend.core.sql_database import db
from backend.models.sql_models import Pedido, Producto, DbCostos
from sqlalchemy import text

facturacion_bp = Blueprint('facturacion_bp', __name__)
logger = logging.getLogger(__name__)


def procesar_datos_wo(ids_filter=None, consecutivo_inicial=None):
    """Lógica centralizada: Genera Excel y Actualiza SQL simultáneamente."""
    
    # 1. Obtener ítems originales de SQL
    query = Pedido.query.filter(Pedido.estado == 'PENDIENTE')
    if ids_filter:
        query = query.filter(Pedido.id_pedido.in_(ids_filter))
    
    items_sql = query.order_by(Pedido.id_pedido.asc()).all()
    if not items_sql:
        return pd.DataFrame(), 0

    # 2. Preparar Maestros (Clientes para NITs)
    try:
        res_clientes = db.session.execute(text("SELECT nombre, identificacion FROM db_clientes")).mappings().all()
        mapa_clientes = {str(c['nombre']).strip().upper(): str(c['identificacion']).strip() for c in res_clientes}
    except:
        mapa_clientes = {}


    # 3. Mapeo WO Estricto (57 columnas)
    columnas_wo = [
        'Encab: Empresa', 'Encab: Tipo Documento', 'Encab: Prefijo', 'Encab: Documento Número',
        'Encab: Fecha', 'Encab: Tercero Interno', 'Encab: Tercero Externo', 'Encab: Nota',
        'Encab: FormaPago', 'Encab: Fecha Entrega', 'Encab: Prefijo Documento Externo',
        'Encab: Número_Documento_Externo', 'Encab: Verificado', 'Encab: Anulado',
        'Encab: Personalizado 1', 'Encab: Personalizado 2', 'Encab: Personalizado 3',
        'Encab: Personalizado 4', 'Encab: Personalizado 5', 'Encab: Personalizado 6',
        'Encab: Personalizado 7', 'Encab: Personalizado 8', 'Encab: Personalizado 9',
        'Encab: Personalizado 10', 'Encab: Personalizado 11', 'Encab: Personalizado 12',
        'Encab: Personalizado 13', 'Encab: Personalizado 14', 'Encab: Personalizado 15',
        'Encab: Sucursal', 'Encab: Clasificación', 'Detalle: Producto', 'Detalle: Bodega',
        'Detalle: UnidadDeMedida', 'Detalle: Cantidad', 'Detalle: IVA', 'Detalle: Valor Unitario',
        'Detalle: Descuento', 'Detalle: Vencimiento', 'Detalle: Nota', 'Detalle: Centro costos',
        'Detalle: Personalizado1', 'Detalle: Personalizado2', 'Detalle: Personalizado3',
        'Detalle: Personalizado4', 'Detalle: Personalizado5', 'Detalle: Personalizado6',
        'Detalle: Personalizado7', 'Detalle: Personalizado8', 'Detalle: Personalizado9',
        'Detalle: Personalizado10', 'Detalle: Personalizado11', 'Detalle: Personalizado12',
        'Detalle: Personalizado13', 'Detalle: Personalizado14', 'Detalle: Personalizado15',
        'Detalle: Código Centro Costos'
    ]

    rows_finales = []
    mapeo_internos = {}
    
    # Manejo seguro del consecutivo
    try:
        curr_cons = int(str(consecutivo_inicial).strip()) if consecutivo_inicial and str(consecutivo_inicial).strip() else None
    except:
        curr_cons = None

    items_con_exito = 0

    for item in items_sql:
        id_orig = item.id_pedido
        
        # Asignar/Recuperar consecutivo para este pedido
        if id_orig not in mapeo_internos:
            if curr_cons:
                val_cons = str(curr_cons)
                curr_cons += 1
            else:
                # MANTENER FORMATO COMPLETO (Ej: PED-1001)
                val_cons = str(id_orig).strip().upper()
            mapeo_internos[id_orig] = val_cons
        
        doc_nro = mapeo_internos[id_orig]

        # --- ACTUALIZACIÓN SQL (Quemado de ID) ---
        old_id = item.id_pedido
        item.id_pedido = doc_nro  # Se sobreescribe el ID original con el consecutivo de WO
        item.wo_consecutivo = doc_nro
        item.estado = 'EXPORTADO_WO'
        
        logger.info(f"🔄 ID de pedido actualizado: {old_id} -> {doc_nro}")
        items_con_exito += 1

        # --- CONSTRUCCIÓN FILA EXCEL ---
        nit_raw = mapa_clientes.get(str(item.cliente or '').upper(), item.nit or '')
        match_nit = re.search(r'(\d+)', str(nit_raw))
        nit_limpio = match_nit.group(1) if match_nit else str(nit_raw).strip()
        
        f_pag = str(item.forma_de_pago or 'Contado').replace('é', 'e').replace('á', 'a').replace('í', 'i').replace('ó', 'o')
        
        # Resolución Dinámica del Vendedor — consulta directa a db_usuarios
        vendedor_db = str(item.vendedor or '').strip()
        v_id = '900315300'  # Fallback: NIT Friparts (sólo último recurso)
        if vendedor_db:
            try:
                row_user = db.session.execute(
                    text("SELECT cedula FROM db_usuarios "
                         "WHERE UPPER(TRIM(nombre_completo)) = UPPER(TRIM(:nombre))"),
                    {"nombre": vendedor_db}
                ).first()
                if row_user and row_user[0]:
                    v_id = str(row_user[0]).strip()
            except Exception as ue:
                logger.warning(f"[WO] No se pudo resolver cédula para '{vendedor_db}': {ue}")
        
        # Trazabilidad Crítica
        print(f"DEBUG WO: Pedido {id_orig} | Vendedor DB: {item.vendedor} | ID Asignado: {v_id}")
        
        try:
            d_val = str(item.descuento or '0').replace('%', '').strip()
            desc = float(d_val) / 100.0 if d_val else 0.0
        except:
            desc = 0.0

        row = {col: "" for col in columnas_wo}
        row.update({
            'Encab: Empresa': 'FRIPARTS SAS', 'Encab: Tipo Documento': 'PED', 'Encab: Prefijo': 'PED',
            'Encab: Documento Número': doc_nro, 
            'Encab: Fecha': item.fecha.strftime('%d/%m/%Y') if item.fecha else datetime.now().strftime('%d/%m/%Y'),
            'Encab: Tercero Interno': v_id, 'Encab: Tercero Externo': nit_limpio,
            'Encab: Nota': 'PEDIDO', 'Encab: FormaPago': f_pag, 
            'Encab: Fecha Entrega': item.fecha.strftime('%d/%m/%Y') if item.fecha else datetime.now().strftime('%d/%m/%Y'),
            'Detalle: Producto': item.id_codigo, 'Detalle: Bodega': 'Principal', 'Detalle: UnidadDeMedida': 'Und.',
            'Detalle: Cantidad': float(item.cantidad or 0), 'Detalle: IVA': 0.19, 
            'Detalle: Valor Unitario': float(item.precio_unitario or 0),
            'Detalle: Descuento': desc, 
            'Detalle: Vencimiento': item.fecha.strftime('%d/%m/%Y') if item.fecha else datetime.now().strftime('%d/%m/%Y')
        })
        rows_finales.append(row)

    df = pd.DataFrame(rows_finales)
    if not df.empty: df = df[columnas_wo]
    
    return df, items_con_exito

@facturacion_bp.route('/api/facturacion/pedidos-pendientes', methods=['GET'])
@require_role(ROL_ADMINS + ['JEFE ALMACEN'])
def obtener_pedidos_pendientes():
    """Obtiene pedidos PENDIENTES desde SQL."""
    try:
        pendientes = Pedido.query.filter(Pedido.estado == 'PENDIENTE').all()
        agrupados = {}
        for r in pendientes:
            id_ped = r.id_pedido
            if id_ped not in agrupados:
                agrupados[id_ped] = {
                    'id': id_ped, 'fecha': str(r.fecha), 'cliente': r.cliente,
                    'vendedor': r.vendedor, 'items_count': 0, 'total': 0, 'items': []
                }
            cant = float(r.cantidad or 0); prec = float(r.precio_unitario or 0)
            agrupados[id_ped]['items_count'] += 1
            agrupados[id_ped]['total'] += (cant * prec)
            agrupados[id_ped]['items'].append({'cod': r.id_codigo, 'cant': cant})
            
        resultado = sorted(agrupados.values(), key=lambda x: x['fecha'], reverse=True)
        return jsonify({'success': True, 'pedidos': resultado})
    except Exception as e:
        logger.error(f"Error en obtener_pedidos_pendientes SQL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@facturacion_bp.route('/api/exportar/world-office', methods=['POST'])
@require_role(ROL_ADMINS + ['JEFE ALMACEN'])
def exportar_world_office():
    """Genera Excel y Actualiza SQL simultáneamente."""
    try:
        data = request.get_json(silent=True) or {}
        ids_filter = data.get('ids', None)
        consecutivo_inicial = data.get('consecutivo_inicial', None)
        
        df, cnt = procesar_datos_wo(ids_filter, consecutivo_inicial)
        
        if df.empty:
            return jsonify({'success': False, 'error': 'No hay datos para exportar.'}), 400

        # PERSISTENCIA EN SQL
        db.session.commit()
        logger.info(f"✅ SQL Commit: {cnt} items exportados exitosamente.")

        # GENERAR ARCHIVO
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ImportarWO')
        output.seek(0)
        
        response = send_file(
            output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True, download_name=f'PEDIDOS_WO_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
        response.headers['X-Pedidos-Actualizados'] = str(cnt)
        response.headers['Access-Control-Expose-Headers'] = 'X-Pedidos-Actualizados'
        return response
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en exportación WO: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@facturacion_bp.route('/api/exportar/world-office/preview', methods=['POST'])
@require_role(ROL_ADMINS + ['JEFE ALMACEN'])
def preview_world_office():
    """Vista previa sin persistencia (rollback automático de la sesión)."""
    try:
        data = request.get_json(silent=True) or {}
        ids_filter = data.get('ids', None)
        consecutivo_inicial = data.get('consecutivo_inicial', None)
        
        df, _ = procesar_datos_wo(ids_filter, consecutivo_inicial)
        
        # OBLIGATORIO: Hacer rollback para que el preview NO guarde cambios en la BD
        db.session.rollback()
        
        if df.empty: return jsonify({'success': True, 'data': []})
        preview = df.fillna('').head(100).to_dict(orient='records')
        return jsonify({'success': True, 'data': preview})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
