from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client
import logging
import datetime
import uuid

metals_bp = Blueprint('metals', __name__)
logger = logging.getLogger(__name__)

@metals_bp.route('/api/metals/productos/listar', methods=['GET'])
def listar_productos_metals():
    try:
        ws = sheets_client.get_worksheet("METALS_PRODUCTOS")
        if not ws:
            return jsonify({"success": False, "message": "Hoja METALS_PRODUCTOS no encontrada"}), 500
        
        records = ws.get_all_records()
        return jsonify({"success": True, "productos": records})
    except Exception as e:
        logger.error(f"Error listando productos metals: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@metals_bp.route('/api/metals/produccion/registrar', methods=['POST'])
def registrar_produccion_metals():
    try:
        data = request.json
        codigo_producto = data.get('codigo_producto')
        lote = data.get('lote')
        proceso_actual = data.get('proceso')

        if not codigo_producto or not lote or not proceso_actual:
            return jsonify({"success": False, "message": "Faltan datos críticos (Producto, Lote o Proceso)"}), 400

        logger.info(f"Validando secuencia para Lote {lote}, Producto {codigo_producto}, Proceso {proceso_actual}")
        
        # 1. Obtener definición del producto y su flujo
        ws_prod = sheets_client.get_worksheet("METALS_PRODUCTOS")
        if not ws_prod:
            return jsonify({"success": False, "message": "Error interno: Hoja de productos no encontrada"}), 500
        
        productos = ws_prod.get_all_records()
        def_prod = next((p for p in productos if str(p.get('CODIGO')) == str(codigo_producto)), None)
        
        if not def_prod:
            return jsonify({"success": False, "message": f"Producto {codigo_producto} no encontrado en METALS_PRODUCTOS"}), 404

        flujo_str = def_prod.get('PROCESOS', '')
        # Limpiar y convertir a lista: "Tornos, Soldadura" -> ["TORNOS", "SOLDADURA"]
        flujo = [p.strip().upper() for p in flujo_str.split(',') if p.strip()]
        
        if not flujo:
            return jsonify({"success": False, "message": "El producto no tiene un flujo de procesos definido"}), 400

        # 2. Consultar historial del lote
        ws_proc = sheets_client.get_worksheet("METALS_PRODUCCION")
        if not ws_proc:
            return jsonify({"success": False, "message": "Error interno: Hoja de producción no encontrada"}), 500
        
        registros_lote = ws_proc.get_all_records()
        # Filtrar por lote y producto, ordenados por aparición (ya que append_row añade al final)
        historial = [r for r in registros_lote if str(r.get('LOTE')) == str(lote) and str(r.get('CODIGO_PRODUCTO')) == str(codigo_producto)]
        
        proximo_esperado = ""
        if not historial:
            # Es el primer registro del lote
            proximo_esperado = flujo[0]
        else:
            # Ya hay registros. El último registro nos dice qué proceso se hizo.
            ultimo_proceso = str(historial[-1].get('PROCESO', '')).strip().upper()
            try:
                idx_ultimo = flujo.index(ultimo_proceso)
                if idx_ultimo + 1 < len(flujo):
                    proximo_esperado = flujo[idx_ultimo + 1]
                else:
                    return jsonify({"success": False, "message": f"La producción para el lote {lote} ya ha finalizado según el flujo definido"}), 400
            except ValueError:
                return jsonify({"success": False, "message": f"El proceso anterior '{ultimo_proceso}' no pertenece al flujo del producto"}), 400

        # 3. Validar si el proceso actual es el correcto
        if proceso_actual.strip().upper() != proximo_esperado:
            return jsonify({
                "success": False, 
                "message": f"Secuencia incorrecta. Para el lote {lote}, el proceso esperado es '{proximo_esperado}', pero se intentó registrar '{proceso_actual}'."
            }), 400

        # 4. Calcular Siguiente Proceso para guardar en el registro actual
        idx_actual = flujo.index(proceso_actual.strip().upper())
        siguiente_en_flujo = flujo[idx_actual + 1] if idx_actual + 1 < len(flujo) else "FINALIZADO"

        # 5. Registrar producción
        # Calcular tiempo total si hay horas
        tiempo_total = ""
        try:
            if data.get('hora_inicio') and data.get('hora_fin'):
                h1 = datetime.datetime.strptime(data['hora_inicio'], "%H:%M")
                h2 = datetime.datetime.strptime(data['hora_fin'], "%H:%M")
                delta = h2 - h1
                if delta.days < 0: # Caso cruce de medianoche
                    delta = datetime.timedelta(days=1) + delta
                
                horas = delta.seconds // 3600
                minutos = (delta.seconds % 3600) // 60
                tiempo_total = f"{horas}h {minutos}m"
        except Exception as te:
            logger.warning(f"Error calculando tiempo: {te}")

        id_reg = f"MET-{str(uuid.uuid4())[:8].upper()}"
        
        # Formatear fecha para sheets (DD/MM/YYYY)
        fecha_js = data.get('fecha', '')
        fecha_sheet = fecha_js
        if '-' in fecha_js:
            partes = fecha_js.split('-')
            if len(partes) == 3:
                fecha_sheet = f"{partes[2]}/{partes[1]}/{partes[0]}"

        fila = [
            id_reg,
            fecha_sheet,
            data.get('responsable'),
            data.get('maquina'),
            data.get('codigo_producto'),
            data.get('lote'),
            data.get('proceso'),
            data.get('cant_solicitada'),
            data.get('hora_inicio'),
            data.get('hora_fin'),
            data.get('cant_ok'),
            data.get('pnc'),
            tiempo_total,
            "COMPLETADO",
            siguiente_en_flujo
        ]
        
        ws_proc.append_row(fila)

        # 6. Si es el proceso final, actualizar stock en METALS_PRODUCTOS
        if siguiente_en_flujo == "FINALIZADO":
            try:
                cant_ok = int(data.get('cant_ok', 0))
                if cant_ok > 0:
                    headers_prod = ws_prod.row_values(1)
                    if 'STOCK' in headers_prod:
                        col_stock = headers_prod.index('STOCK') + 1
                        # Buscar fila del producto de nuevo para estar seguros
                        for idx, p in enumerate(productos):
                            if str(p.get('CODIGO')) == str(codigo_producto):
                                stock_actual = int(p.get('STOCK', 0) or 0)
                                ws_prod.update_cell(idx + 2, col_stock, stock_actual + cant_ok)
                                logger.info(f"✅ Stock actualizado para {codigo_producto}: +{cant_ok}")
                                break
            except Exception as se:
                logger.error(f"Error actualizando stock final: {se}")

        return jsonify({"success": True, "id": id_reg, "siguiente": siguiente_en_flujo})


    except Exception as e:
        logger.error(f"Error registrando producción metals: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@metals_bp.route('/api/metals/produccion/proximo_paso', methods=['GET'])
def get_proximo_paso():
    try:
        codigo_producto = request.args.get('codigo_producto')
        lote = request.args.get('lote')

        if not codigo_producto or not lote:
            return jsonify({"success": False, "message": "Faltan parámetros"}), 400

        ws_prod = sheets_client.get_worksheet("METALS_PRODUCTOS")
        productos = ws_prod.get_all_records()
        def_prod = next((p for p in productos if str(p.get('CODIGO')) == str(codigo_producto)), None)
        
        if not def_prod:
            return jsonify({"success": False, "message": "Producto no encontrado"}), 404

        flujo_str = def_prod.get('PROCESOS', '')
        flujo = [p.strip().upper() for p in flujo_str.split(',') if p.strip()]
        
        ws_proc = sheets_client.get_worksheet("METALS_PRODUCCION")
        registros_lote = ws_proc.get_all_records()
        historial = [r for r in registros_lote if str(r.get('LOTE')) == str(lote) and str(r.get('CODIGO_PRODUCTO')) == str(codigo_producto)]
        
        if not historial:
            return jsonify({"success": True, "proximo": flujo[0] if flujo else ""})
        
        ultimo_proceso = str(historial[-1].get('PROCESO', '')).strip().upper()
        try:
            idx = flujo.index(ultimo_proceso)
            if idx + 1 < len(flujo):
                return jsonify({"success": True, "proximo": flujo[idx + 1]})
            else:
                return jsonify({"success": True, "proximo": "FINALIZADO"})
        except ValueError:
            return jsonify({"success": False, "message": "Flujo inconsistente"}), 400

    except Exception as e:
        logger.error(f"Error en proximo_paso: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@metals_bp.route('/api/metals/produccion/historial', methods=['GET'])
def get_metals_historial():
    try:
        ws = sheets_client.get_worksheet("METALS_PRODUCCION")
        if not ws:
            return jsonify({"success": False, "message": "Hoja no encontrada"}), 500
        
        records = ws.get_all_records()
        # Invertir para mostrar lo más reciente primero
        return jsonify({"success": True, "historial": records[::-1]})
    except Exception as e:
        logger.error(f"Error en historial metals: {e}")
        return jsonify({"success": False, "message": str(e)}), 500



