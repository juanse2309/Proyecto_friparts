from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import traceback
from backend.core.sql_database import db
from backend.services.pnc_service import pnc_service
from backend.utils.cache_manager import cached_route
from backend.utils.auth_middleware import require_role, ROL_ADMINS

gerencia_bp = Blueprint('gerencia_bp', __name__)
logger = logging.getLogger(__name__)


@gerencia_bp.route('/api/gerencia/metricas-pnc', methods=['GET'])
@require_role(ROL_ADMINS)
@cached_route(namespace='gerencia_pnc', ttl=600)
def obtener_metricas_pnc():
    """
    Dashboard PNC (Lean Manufacturing): consolida las métricas de producto
    no conforme (Inyección, Pulido, Ensamble) con soporte de rango de fecha.
    Toda la lógica de negocio vive en PncService — esta ruta solo lee
    query params y traduce el resultado a HTTP.
    """
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')

        resultado = pnc_service.obtener_metricas_pnc_consolidadas(fecha_inicio, fecha_fin)

        if not resultado.get("success"):
            return jsonify(resultado), 500

        return jsonify(resultado), 200

    except Exception as e:
        logger.error(f"❌ Error en obtener_metricas_pnc: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error al calcular métricas de PNC"}), 500

@gerencia_bp.route('/api/gerencia/importar-inventario-fisico', methods=['POST', 'GET'])
@require_role(ROL_ADMINS)
def importar_inventario_fisico():
    """
    Endpoint exclusivo de una sola ejecución para el cargue masivo del inventario físico final.
    - Realiza una nivelación a 0 de las existencias (respetando lo comprometido).
    - Lee el CSV desde la raíz y actualiza SÓLO productos existentes.
    - No inserta duplicados, genera reporte de omitidos.
    """
    try:
        from backend.models.sql_models import Producto
        from backend.utils.formatters import normalizar_codigo
        import csv
        import os

        # 1. Nivelación Inicial Selectiva
        # Poner en 0: por_pulir, p_terminado, stock_bodega y en_transito (si existe)
        # CRÍTICO: La columna 'comprometido' NO SE TOCA.
        update_values = {
            Producto.por_pulir: 0,
            Producto.p_terminado: 0,
            Producto.stock_bodega: 0
        }
        
        # Validar si en_transito realmente existe en el modelo actual para evitar fallos de mapeo
        if hasattr(Producto, 'en_transito'):
            update_values[getattr(Producto, 'en_transito')] = 0
            
        db.session.query(Producto).update(update_values)
        
        # 2. Procesamiento Seguro del CSV
        file_path = 'Existencias 20260528.csv'
        if not os.path.exists(file_path):
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Archivo maestro no encontrado en raíz: {file_path}"}), 404
            
        omitidos_no_encontrados = []
        total_exitosos = 0
        
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            contenido_completo = f.read()

        lineas_limpias = [linea.strip() for linea in contenido_completo.splitlines() if linea.strip()]

        if not lineas_limpias:
            db.session.rollback()
            return jsonify({"status": "error", "message": "El archivo CSV está vacío o es ilegible"}), 400

        primer_linea = lineas_limpias[0]
        delimitador = ';' if primer_linea.count(';') > primer_linea.count(',') else ','

        reader = csv.DictReader(lineas_limpias, delimiter=delimitador)
        reader.fieldnames = [str(name).strip() for name in reader.fieldnames if name]

        from sqlalchemy import func
        max_id = db.session.query(func.max(Producto.id)).scalar() or 0
        siguiente_id = max_id + 1

        with db.session.no_autoflush:
            for row in reader:
                codigo_raw = row.get('Código') or row.get('CÓDIGO') or row.get('codigo') or row.get('ï»¿Códgo')
                stock_real_raw = row.get('Stock Real') or row.get('STOCK REAL') or row.get('stock real')
                precio_raw = row.get('Precio') or row.get('PRECIO') or row.get('precio')
                
                if not codigo_raw:
                    continue
                    
                codigo_norm = normalizar_codigo(codigo_raw)
                
                # Búsqueda defensiva en código_sistema o id_codigo
                producto = db.session.query(Producto).filter(
                    (Producto.codigo_sistema == codigo_norm) | (Producto.id_codigo == codigo_norm)
                ).first()
                
                # Parsear numéricos por adelantado
                try:
                    stock_real = float(str(stock_real_raw).replace(',', '').strip()) if stock_real_raw else 0.0
                except ValueError:
                    stock_real = 0.0
                    
                try:
                    precio_val = float(str(precio_raw).replace('$', '').replace(',', '').strip()) if precio_raw else 0.0
                except ValueError:
                    precio_val = 0.0

                if producto:
                    producto.p_terminado = stock_real
                    producto.precio = precio_val
                    total_exitosos += 1
                else:
                    # Si el producto NO EXISTE, evaluar creación selectiva
                    if any(prefijo in str(codigo_raw).upper() for prefijo in ['FR-', 'KIT-', 'AL-']):
                        nuevo_producto = Producto(
                            id=siguiente_id,
                            codigo_sistema=codigo_norm,
                            id_codigo=str(codigo_raw).strip(),
                            descripcion=str(row.get('Descripción') or row.get('DESCRIPCIÓN') or '').strip(),
                            p_terminado=stock_real,
                            precio=precio_val,
                            stock_bodega=0,
                            por_pulir=0,
                            producto_ensamblado=0
                        )
                        siguiente_id += 1
                        
                        if hasattr(Producto, 'en_transito'):
                            setattr(nuevo_producto, 'en_transito', 0)
                            
                        db.session.add(nuevo_producto)
                        total_exitosos += 1
                    else:
                        # Omitir de forma segura (ej. BSL, BLA, MX)
                        omitidos_no_encontrados.append({
                            "codigo": codigo_raw,
                            "codigo_limpio": codigo_norm,
                            "descripcion": row.get("Descripción", "N/A"),
                            "precio_leido": precio_raw
                        })
                    
        # 3. Transaccionalidad de Grado Industrial
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "productos_actualizados": total_exitosos,
            "total_omitidos": len(omitidos_no_encontrados),
            "lista_omitidos": omitidos_no_encontrados
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Fallo crítico en carga masiva de inventario físico: {e}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": "Fallo en la transacción. Se ha hecho rollback de seguridad.", "detalle": str(e)}), 500


