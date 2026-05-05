from flask import Blueprint, jsonify, request
from backend.models.sql_models import db, MetalsProduccion, MetalsPersonal
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

        # Obtener departamento del responsable desde SQL
        departamento = ''
        try:
            operario = MetalsPersonal.query.filter_by(responsable=responsable).first()
            if operario:
                departamento = operario.departamento or ''
        except Exception as pe:
            logger.warning(f"No se pudo obtener departamento SQL: {pe}")

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

        try:
            nuevo_registro = MetalsProduccion(
                id=id_reg,
                fecha=fecha_sheet,
                responsable=responsable,
                departamento=departamento,
                proceso=proceso_label,
                maquina=maquina,
                codigo=codigo_producto,
                descripcion=descripcion,
                cantidad_ok=float(cantidad_ok),
                pnc=float(pnc),
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                tiempo=tiempo_str,
                observaciones=observaciones,
                campos_extra=campos_extra_str
            )
            db.session.add(nuevo_registro)
            db.session.commit()
            logger.info(f"✅ [Metals SQL] Registro guardado: {id_reg} — {proceso_label}")
            return jsonify({"success": True, "id": id_reg})
        except Exception as e_sql:
            db.session.rollback()
            raise e_sql

    except Exception as e:
        logger.error(f"Error registrando producción metals: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ====================================================================
# HISTORIAL
# ====================================================================

@metals_bp.route('/api/metals/produccion/historial', methods=['GET'])
def get_metals_historial():
    """Retorna el historial de producción de Metales desde SQL."""
    try:
        registros_db = MetalsProduccion.query.order_by(MetalsProduccion.id.desc()).limit(100).all()
        
        records = []
        for r in registros_db:
            records.append({
                'ID': r.id,
                'FECHA': r.fecha,
                'RESPONSABLE': r.responsable,
                'DEPARTAMENTO': r.departamento,
                'PROCESO': r.proceso,
                'MAQUINA': r.maquina,
                'CÓDIGO': r.codigo,
                'DESCRIPCIÓN': r.descripcion,
                'CANTIDAD_OK': float(r.cantidad_ok or 0),
                'PNC': float(r.pnc or 0),
                'HORA_INICIO': r.hora_inicio,
                'HORA_FIN': r.hora_fin,
                'TIEMPO': r.tiempo,
                'OBSERVACIONES': r.observaciones,
                'CAMPOS_EXTRA': r.campos_extra
            })

        # Estadísticas (Juan Sebastian)
        hoy_str = datetime.date.today().strftime("%d/%m/%Y")
        mes_str = datetime.date.today().strftime("/%m/%Y")
        
        stats = {"hoy": 0, "mes": 0, "pnc": 0, "procesos": 0}
        procesos_hoy = set()

        for r in records:
            if r['FECHA'] == hoy_str:
                stats["hoy"] += int(r['CANTIDAD_OK'])
                procesos_hoy.add(r['PROCESO'])
            if mes_str in r['FECHA']:
                stats["mes"] += 1
                stats["pnc"] += int(r['PNC'])

        stats["procesos"] = len(procesos_hoy)
        return jsonify({"success": True, "registros": records, "stats": stats})
    except Exception as e:
        logger.error(f"Error en historial metals: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
