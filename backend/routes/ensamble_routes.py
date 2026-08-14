from flask import Blueprint, request, jsonify, session, current_app
from datetime import datetime
import logging
from backend.core.sql_database import db
from backend.models.sql_models import ProgramacionEnsamble, Ensamble, Producto
from backend.services.bom_service import calcular_descuentos_ensamble
from sqlalchemy import text
from backend.services.audit_service import OwnershipMismatchException
from backend.services.ensamble_service import EnsambleService, BomNoDisponibleException
from backend.config.constants import FALLBACK_OPERARIO
from backend.utils.auth_middleware import _obtener_usuario_activo, require_role, ROL_ADMINS, ROL_JEFES, ROL_OPERARIOS

ensamble_bp = Blueprint('ensamble_bp', __name__)
logger = logging.getLogger(__name__)

ROLES_ENSAMBLE = ROL_ADMINS + ['AUXILIAR INVENTARIO', 'ENSAMBLE']
# '/api/inyeccion/ensamble_desde_producto' se consume desde inyeccion.js (página
# 'inyeccion', con audiencia mucho más amplia que 'ensamble') -- usa el set
# de planta completo en vez de ROLES_ENSAMBLE.
ROLES_PLANTA = ROL_ADMINS + ROL_JEFES + ROL_OPERARIOS

@ensamble_bp.route('/api/ensamble/programacion', methods=['GET'])
@require_role(ROLES_ENSAMBLE)
def listar_programacion():
    try:
        # Listar todas las programaciones no completadas primero
        schedules = ProgramacionEnsamble.query.order_by(
            ProgramacionEnsamble.estado.desc(), 
            ProgramacionEnsamble.fecha_programada.asc()
        ).all()
        
        res = []
        for s in schedules:
            res.append({
                'id_prog': s.id_prog,
                'id_codigo': s.id_codigo,
                'cantidad_objetivo': s.cantidad_objetivo,
                'cantidad_realizada': s.cantidad_realizada,
                'fecha_programada': s.fecha_programada.strftime('%Y-%m-%d') if s.fecha_programada else '',
                'estado': s.estado
            })
        return jsonify({'success': True, 'data': res})
    except Exception as e:
        logger.error(f"Error al listar programación ensamble: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ensamble_bp.route('/api/ensamble/session_active', methods=['GET'])
@require_role(ROLES_ENSAMBLE)
def get_active_ensamble_session():
    """Busca si el operario tiene un trabajo activo en db_ensambles."""
    responsable = request.args.get('responsable')
    if not responsable:
        return jsonify({"success": False, "error": "Responsable requerido"}), 400
    
    try:
        # Buscar en db_ensambles (plural como exige DBeaver)
        sesion = Ensamble.query.filter(
            Ensamble.responsable == responsable,
            Ensamble.estado.in_(['EN_PROCESO', 'PAUSADO', 'TRABAJANDO'])
        ).order_by(Ensamble.id.desc()).first()
        
        if sesion:
            return jsonify({
                "success": True,
                "session": {
                    "id_ensamble": sesion.id_ensamble,
                    "id_codigo": sesion.id_codigo,
                    "orden_produccion": sesion.op_numero,
                    "cantidad": float(sesion.cantidad or 0),
                    "estado": sesion.estado,
                    "hora_inicio_dt": sesion.hora_inicio.isoformat() if sesion.hora_inicio else None,
                    "tiempo_pausa_acumulado": sesion.tiempo_pausa_acumulado or 0,
                    "hora_pausa": sesion.hora_pausa.isoformat() if sesion.hora_pausa else None
                }
            })
        return jsonify({"success": True, "session": None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@ensamble_bp.route('/api/ensamble/programacion', methods=['POST'])
@require_role(ROLES_ENSAMBLE)
def crear_programacion():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        id_codigo = data.get('id_codigo')
        cantidad_objetivo = int(data.get('cantidad_objetivo', 0))
        fecha_str = data.get('fecha_programada')
        
        if not id_codigo or cantidad_objetivo <= 0 or not fecha_str:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        
        fecha_prog = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy import text

        stmt = insert(ProgramacionEnsamble).values(
            id_codigo=id_codigo,
            cantidad_objetivo=cantidad_objetivo,
            op_numero=data.get('op_numero'),
            fecha_programada=fecha_prog,
            estado='PENDIENTE'
        )

        # UPSERT ante conflicto en uq_programacion_ensamble
        stmt = stmt.on_conflict_do_update(
            index_elements=['fecha_programada', 'id_codigo', text("COALESCE(op_numero, '')")],
            set_={
                'cantidad_objetivo': stmt.excluded.cantidad_objetivo,
                'estado': stmt.excluded.estado
            }
        ).returning(ProgramacionEnsamble.id_prog)

        res = db.session.execute(stmt).fetchone()
        db.session.commit()
        
        id_prog_val = res[0] if res else None
        return jsonify({'success': True, 'id_prog': id_prog_val})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al crear programación ensamble: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ensamble_bp.route('/api/ensamble/bom_stock/<id_codigo>', methods=['GET'])
@require_role(ROLES_ENSAMBLE)
def obtener_bom_con_stock(id_codigo):
    try:
        # 1. Obtener la BOM
        bom_res = calcular_descuentos_ensamble(id_codigo, 1) # Cantidad 1 para ver el ratio
        
        if not bom_res.get('success'):
            return jsonify(bom_res), 404
        
        componentes = bom_res.get('componentes', [])
        resultado = []
        
        for comp in componentes:
            codigo_inv = comp['codigo_inventario']
            # 2. Consultar stock en db_productos
            producto = Producto.query.filter_by(codigo_sistema=codigo_inv).first()
            
            stock = float(producto.p_terminado or 0) if producto else 0
            # Cuántos alcanza a armar con ese stock (stock / cantidad_por_kit)
            ratio = float(comp['cantidad_por_kit'])
            alcanza = int(stock // ratio) if ratio > 0 else 0
            
            resultado.append({
                'componente': comp['codigo_ficha'],
                'codigo_inventario': codigo_inv,
                'stock_almacen': stock,
                'cantidad_por_unidad': ratio,
                'alcanza_para': alcanza
            })
            
        return jsonify({
            'success': True,
            'id_codigo': id_codigo,
            'componentes': resultado
        })
    except Exception as e:
        logger.error(f"Error al obtener BOM con stock: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ensamble_bp.route('/api/ensamble/tareas_pendientes', methods=['GET'])
@require_role(ROLES_ENSAMBLE)
def tareas_pendientes():
    try:
        tareas = ProgramacionEnsamble.query.filter(
            ProgramacionEnsamble.estado != 'COMPLETADO'
        ).order_by(ProgramacionEnsamble.fecha_programada.asc()).all()
        
        res = []
        for t in tareas:
            faltante = max(0, t.cantidad_objetivo - t.cantidad_realizada)
            res.append({
                'id_prog': t.id_prog,
                'id_codigo': t.id_codigo,
                'cantidad_objetivo': t.cantidad_objetivo,
                'cantidad_realizada': t.cantidad_realizada,
                'faltante': faltante,
                'fecha_programada': t.fecha_programada.strftime('%Y-%m-%d') if t.fecha_programada else '',
                'estado': t.estado
            })
        return jsonify({'success': True, 'data': res})
    except Exception as e:
        logger.error(f"Error al listar tareas pendientes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ensamble_bp.route('/api/ensamble/reportar', methods=['POST'])
@require_role(ROLES_ENSAMBLE)
def reportar_ensamble_multi():
    """Controlador puro: delega el reporte multi-registro en EnsambleService."""
    data = request.get_json()
    try:
        usuario_activo = _obtener_usuario_activo()
        resultado = EnsambleService.reportar_multi(data, usuario_activo)
        return jsonify({
            'success': True,
            'message': f"Se procesaron {resultado['registros_procesados']} registros con éxito.",
            'id_ensamble': resultado['id_ensamble'],
            'movimientos_inventario': resultado['movimientos_inventario']
        })
    except OwnershipMismatchException as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "ENSAMBLE_SESSION_OWNERSHIP_MISMATCH",
            "responsable_db": e.responsable_db,
            "responsable_in": e.responsable_in
        }), 409
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ ERROR REPORTE MULTI-ENSAMBLE: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ====================================================================
# EJECUCIÓN DE ENSAMBLE (iniciar/finalizar sesión + BOM)
# Movido desde backend/app.py
# ====================================================================

@ensamble_bp.route('/api/inyeccion/ensamble_desde_producto', methods=['GET'])
@require_role(ROLES_PLANTA)
def obtener_ensamble_desde_producto():
    """Dado un código de producto, retorna su BOM completo desde NUEVA_FICHA_MAESTRA."""
    codigo_entrada = request.args.get('codigo', '').strip()
    try:
        resultado = EnsambleService.obtener_bom_desde_producto(codigo_entrada)
        return jsonify({'success': True, **resultado}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f" Error en obtener_ensamble_desde_producto: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ensamble_bp.route('/api/ensamble/iniciar', methods=['POST'])
@require_role(ROLES_ENSAMBLE)
def iniciar_ensamble():
    """
    Persistencia inmediata al iniciar ensamble.
    Crea un registro EN_PROCESO en db_ensambles para que sea visible en el PC de inmediato.
    Sigue el patrón de Pulido: persistirInicioSQL.
    """
    data = request.get_json()
    try:
        resultado = EnsambleService.iniciar(data)
        if resultado['ya_registrado']:
            return jsonify({
                "success": True,
                "message": "Ensamble ya registrado",
                "id_ensamble": resultado['id_ensamble']
            }), 200
        return jsonify({
            "success": True,
            "message": "Ensamble iniciado y persistido en SQL",
            "id_ensamble": resultado['id_ensamble']
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"❌ Error en iniciar_ensamble: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ensamble_bp.route('/api/ensamble/finalizar', methods=['POST'])
@require_role(ROLES_ENSAMBLE)
def finalizar_ensamble():
    """
    Finaliza un ensamble con explosión de materiales (BOM) y descarga de inventario (Fases 1-5).
    """
    data = request.json
    try:
        resultado = EnsambleService.finalizar(data)
        return jsonify({'success': True, 'id_ensamble': resultado['id_ensamble']}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except BomNoDisponibleException as e:
        return jsonify({'success': False, 'error': e.message}), 400
    except Exception as e:
        logger.error(f"❌ Error en finalizar_ensamble: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
