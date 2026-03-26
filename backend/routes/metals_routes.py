from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client
from backend.repositories.producto_repository import ProductoRepository
import logging
import datetime
import uuid
import json
import time # Juan Sebastian: Para manejo de caché

metals_bp = Blueprint('metals', __name__)
logger = logging.getLogger(__name__)

# ====================================================================
# PRODUCTOS
# ====================================================================

@metals_bp.route('/api/metals/productos/listar', methods=['GET'])
def listar_productos_metals():
    """Lista productos de Frimetals usando el repositorio unificado (DRY)."""
    try:
        logger.info("🌐 [API] Consultando productos de Frimetals via ProductoRepository")
        repo = ProductoRepository(tenant="frimetals")
        productos = repo.listar_todos()
        return jsonify({"success": True, "productos": productos})
    except Exception as e:
        logger.error(f"Error listando productos metals: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ====================================================================
# PRODUCCIÓN — REGISTRO SIMPLIFICADO (sin flujo de lotes)
# ====================================================================

@metals_bp.route('/api/metals/produccion/registrar', methods=['POST'])
def registrar_produccion_metals():
    try:
        data = request.json

        proceso = data.get('proceso', '')
        proceso_label = data.get('proceso_label', proceso)
        maquina = data.get('maquina', '')
        codigo_producto = data.get('codigo_producto', '')
        descripcion = data.get('descripcion_producto', '')
        responsable = data.get('responsable', '')
        fecha_js = data.get('fecha', '')
        hora_inicio = data.get('hora_inicio', '')
        hora_fin = data.get('hora_fin', '')
        tiempo_min = data.get('tiempo_min', '')
        cantidad_ok = data.get('cantidad_ok', 0)
        pnc = data.get('pnc', 0)
        observaciones = data.get('observaciones', '')
        campos_extra = data.get('campos_extra', {})

        if not codigo_producto or not proceso or not maquina:
            return jsonify({"success": False, "message": "Faltan datos: Producto, Proceso o Máquina"}), 400

        # Obtener departamento del responsable
        departamento = ''
        try:
            ws_personal = sheets_client.get_worksheet("METALS_PERSONAL")
            if ws_personal:
                personal = sheets_client.get_all_records_seguro(ws_personal)
                operario = next((p for p in personal if p.get('RESPONSABLE') == responsable), None)
                if operario:
                    departamento = operario.get('DEPARTAMENTO', '')
        except Exception as pe:
            logger.warning(f"No se pudo obtener departamento: {pe}")

        # Formatear fecha DD/MM/YYYY
        fecha_sheet = fecha_js
        if '-' in fecha_js:
            partes = fecha_js.split('-')
            if len(partes) == 3:
                fecha_sheet = f"{partes[2]}/{partes[1]}/{partes[0]}"

        # Formatear tiempo
        tiempo_str = ''
        if tiempo_min is not None and tiempo_min != '':
            try:
                mins = int(tiempo_min)
                tiempo_str = f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"
            except:
                pass

        # Serializar campos extra como JSON string
        campos_extra_str = json.dumps(campos_extra, ensure_ascii=False) if campos_extra else ''

        id_reg = f"MET-{str(uuid.uuid4())[:8].upper()}"

        ws_prod = sheets_client.get_worksheet("METALS_PRODUCCION")
        if not ws_prod:
            return jsonify({"success": False, "message": "Hoja METALS_PRODUCCION no encontrada"}), 500

        fila = [
            id_reg,
            fecha_sheet,
            responsable,
            departamento,
            proceso_label,
            maquina,
            codigo_producto,
            descripcion,
            str(cantidad_ok),
            str(pnc),
            hora_inicio,
            hora_fin,
            tiempo_str,
            observaciones,
            campos_extra_str
        ]

        ws_prod.append_row(fila)
        logger.info(f"✅ [Metals] Registro guardado: {id_reg} — {proceso_label} / {maquina}")

        return jsonify({"success": True, "id": id_reg})

    except Exception as e:
        logger.error(f"Error registrando producción metals: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ====================================================================
# HISTORIAL
# ====================================================================

@metals_bp.route('/api/metals/produccion/historial', methods=['GET'])
def get_metals_historial():
    try:
        ws = sheets_client.get_worksheet("METALS_PRODUCCION")
        if not ws:
            return jsonify({"success": False, "message": "Hoja no encontrada"}), 500
        
        records = sheets_client.get_all_records_seguro(ws)

        # Calcular Estadísticas (Juan Sebastian)
        hoy_str = datetime.date.today().strftime("%d/%m/%Y")
        mes_str = datetime.date.today().strftime("/%m/%Y")
        
        stats = {
            "hoy": 0,
            "mes": 0,
            "pnc": 0,
            "procesos": 0
        }

        procesos_hoy = set()

        for r in records:
            fecha = r.get('FECHA', '')
            try:
                ok = int(r.get('CANTIDAD_OK', 0) or 0)
                pnc = int(r.get('PNC', 0) or 0)
            except:
                ok, pnc = 0, 0

            if fecha == hoy_str:
                stats["hoy"] += ok
                procesos_hoy.add(r.get('PROCESO', ''))
            
            if mes_str in fecha:
                stats["mes"] += 1
                stats["pnc"] += pnc

        stats["procesos"] = len(procesos_hoy)

        return jsonify({
            "success": True, 
            "registros": records[::-1],
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error en historial metals: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
