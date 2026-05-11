from flask import Blueprint, jsonify, request
from backend.models.sql_models import db, MetalsProduccion, MetalsPersonal, MetalsPedido
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
        id_pedido = data.get('id_pedido', '')
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
            db.session.rollback()
            logger.warning(f"No se pudo obtener departamento SQL: {pe}")
            departamento = '' # Fallback seguro

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

        try:
            nuevo_registro = MetalsProduccion(
                # El id se maneja automáticamente por el Serial de la DB
                fecha=fecha_sheet,
                responsable=responsable,
                departamento=departamento,
                proceso=proceso_label,
                maquina=maquina,
                id_pedido=id_pedido,
                codigo=codigo_producto,
                descripcion=descripcion,
                cantidad_ok=float(cantidad_ok or 0),
                pnc=float(pnc or 0),
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                tiempo=tiempo_str,
                observaciones=observaciones,
                campos_extra=campos_extra_str
            )
            db.session.add(nuevo_registro)
            db.session.commit()
            
            # --- TRIGGER DE SINCRONIZACIÓN AUTOMÁTICA (Juan Sebastian) ---
            if id_pedido and codigo_producto:
                try:
                    # 1. Sumar producción histórica para este item en este pedido
                    total_producido = db.session.query(db.func.sum(MetalsProduccion.cantidad_ok)).filter(
                        MetalsProduccion.id_pedido == id_pedido,
                        MetalsProduccion.codigo == codigo_producto
                    ).scalar() or 0
                    
                    # 2. Buscar el item en el pedido original para saber el total requerido
                    item_pedido = MetalsPedido.query.filter_by(id_pedido=id_pedido, id_codigo=codigo_producto).first()
                    
                    if item_pedido and item_pedido.cantidad > 0:
                        nuevo_progreso = min(100, int((total_producido / item_pedido.cantidad) * 100))
                        
                        # 3. Actualizar progreso del item
                        item_pedido.progreso = nuevo_progreso
                        
                        # 4. Si es el 100%, opcionalmente cambiar estado
                        if nuevo_progreso == 100:
                            item_pedido.estado = 'FINALIZADO'
                        elif item_pedido.estado == 'PENDIENTE':
                            item_pedido.estado = 'PRODUCCION'
                            
                        db.session.commit()
                        logger.info(f"🔄 [Sync] Pedido {id_pedido} actualizado al {nuevo_progreso}%")
                except Exception as sync_e:
                    logger.error(f"⚠️ Error en sincronización de progreso: {sync_e}")

            logger.info(f"✅ [Metals SQL] Registro guardado — {proceso_label}")
            return jsonify({"success": True})
        except Exception as e_sql:
            db.session.rollback()
            logger.error(f"Error SQL al registrar: {e_sql}")
            return jsonify({"success": False, "message": "Error en base de datos. Verifique si el registro ya existe."}), 500

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

@metals_bp.route('/api/metals/dashboard/stats', methods=['GET'])
def get_metals_dashboard_stats():
    """Endpoint para el Dashboard de Metales con manejo robusto de errores."""
    try:
        hoy_str = datetime.date.today().strftime("%d/%m/%Y")
        
        # KPI 1: Piezas producidas hoy (Suma de cantidad_ok)
        try:
            piezas_hoy_raw = db.session.query(db.func.sum(MetalsProduccion.cantidad_ok)).filter(
                MetalsProduccion.fecha == hoy_str
            ).scalar()
            piezas_hoy = int(piezas_hoy_raw or 0)
        except Exception as e_piezas:
            logger.error(f"Error sumando piezas hoy: {e_piezas}")
            piezas_hoy = 0
        
        # KPI 2: Pedidos activos (al menos un item con progreso < 100)
        try:
            pedidos_activos = db.session.query(MetalsPedido.id_pedido).filter(
                MetalsPedido.progreso < 100
            ).distinct().count()
        except Exception as e_ped:
            logger.error(f"Error contando pedidos activos: {e_ped}")
            db.session.rollback()
            pedidos_activos = 0
        
        # Lista actividad reciente (5 registros)
        actividad = []
        try:
            recientes = MetalsProduccion.query.order_by(MetalsProduccion.id.desc()).limit(5).all()
            for r in recientes:
                actividad.append({
                    "fecha": r.fecha or '',
                    "proceso": r.proceso or 'Sin proceso',
                    "responsable": r.responsable or 'Sin responsable',
                    "cantidad": int(r.cantidad_ok or 0)
                })
        except Exception as e_rec:
            logger.error(f"Error listando actividad reciente: {e_rec}")
            db.session.rollback()
            
        return jsonify({
            "success": True,
            "piezas_hoy": piezas_hoy,
            "pedidos_activos": pedidos_activos,
            "actividad_reciente": actividad
        })
    except Exception as e:
        logger.error(f"Error general en dashboard stats: {e}")
        db.session.rollback()
        return jsonify({
            "success": False, 
            "error": str(e), 
            "piezas_hoy": 0, 
            "pedidos_activos": 0,
            "actividad_reciente": []
        }), 200
