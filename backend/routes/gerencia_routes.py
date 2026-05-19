from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import traceback
from backend.core.sql_database import db
from backend.models.sql_models import DistribucionOpPedidos, Pedido, PncInyeccion, ProduccionInyeccion
from backend.services.bom_service import calcular_descuentos_ensamble

gerencia_bp = Blueprint('gerencia_bp', __name__)
logger = logging.getLogger(__name__)

def requiere_ensamble(codigo):
    """
    Determina de forma dinámica si un código de producto requiere ensamble (BOM)
    utilizando el servicio oficial bom_service.
    """
    try:
        bom_res = calcular_descuentos_ensamble(codigo, 1)
        return bom_res.get('success', False)
    except Exception as e:
        logger.error(f"Error validando BOM para {codigo}: {e}")
        return False

@gerencia_bp.route('/api/gerencia/trazabilidad', methods=['GET'])
def obtener_trazabilidad_gerencial():
    """
    Torre de Control Gerencial:
    Consolida el estado productivo por Pedido de db_distribucion_op_pedidos
    calculando el avance real por estación y semáforos ejecutivos.
    """
    try:
        # 1. Obtener todos los id_pedido únicos que tienen cubetas asociadas o pedidos registrados
        # Para mantener el rendimiento, traemos los id_pedido de las cubetas activas
        id_pedidos_activos = [r[0] for r in db.session.query(DistribucionOpPedidos.id_pedido).distinct().all() if r[0]]
        
        # Helper de parseo numérico
        def _clean_num(val):
            if val is None:
                return 0.0
            s = str(val).strip()
            if s in ['', 'None', 'null', 'undefined']:
                return 0.0
            s = s.replace('%', '').replace('$', '').replace(' ', '').replace(',', '')
            try:
                return float(s)
            except:
                return 0.0

        resultados = []
        for id_pedido in id_pedidos_activos:
            # Buscar info del pedido original en db_pedidos
            items_pedido_original = db.session.query(Pedido).filter(Pedido.id_pedido == id_pedido).all()
            
            if not items_pedido_original:
                continue

            pedido_info = items_pedido_original[0]
            cliente = pedido_info.cliente or "CLIENTE GENERAL"
            fecha_prometida = pedido_info.fecha.strftime('%d/%m/%Y') if pedido_info.fecha else "SIN FECHA"
            
            # Buscar cubetas asociadas a este pedido para extraer la OP vinculada si existe
            primera_cubeta = db.session.query(DistribucionOpPedidos).filter(
                DistribucionOpPedidos.id_pedido == id_pedido
            ).first()
            op_actual = primera_cubeta.op_world_office if primera_cubeta else "SIN OP VINCULADA"
            
            productos_trazabilidad = []
            todo_alistado_100 = True
            alguna_retencion_pnc = False
            
            for it in items_pedido_original:
                codigo_original = it.id_codigo
                codigo_limpio = str(codigo_original).replace('FR-', '').strip()
                cant_req = _clean_num(it.cantidad)
                
                # Intentar buscar todas las cubetas de avance para esta referencia del pedido
                cubetas = db.session.query(DistribucionOpPedidos).filter(
                    DistribucionOpPedidos.id_pedido == id_pedido,
                    DistribucionOpPedidos.codigo_producto == codigo_limpio
                ).all()
                
                if cubetas:
                    cant_inyectada = sum(c.cant_inyectada or 0 for c in cubetas)
                    cant_pulida = sum(c.cant_pulida or 0 for c in cubetas)
                    cant_ensamblada = sum(c.cant_ensamblada or 0 for c in cubetas)
                    cant_alistada = sum(c.cant_alistada or 0 for c in cubetas)
                    
                    # Buscar si alguna de las cubetas tiene la OP vinculada
                    for c in cubetas:
                        if c.op_world_office:
                            op_actual = c.op_world_office
                            break
                else:
                    cant_inyectada = 0
                    cant_pulida = 0
                    cant_ensamblada = 0
                    cant_alistada = 0

                # Prevenir división por cero y calcular porcentajes reales
                def calc_pct(producido):
                    if cant_req <= 0:
                        return 100
                    return min(100, round(((producido or 0) / cant_req) * 100))

                pct_iny = calc_pct(cant_inyectada)
                pct_pul = calc_pct(cant_pulida)
                pct_emp = calc_pct(cant_alistada)
                
                # Validar de forma dinámica si requiere Ensamble
                req_ens = requiere_ensamble(codigo_limpio)
                pct_ens = calc_pct(cant_ensamblada) if req_ens else "no_requiere"
                
                # Si algún ítem no ha alcanzado el 100% de alistamiento (despacho/almacén),
                # no se puede catalogar el pedido completo como LISTO PARA DESPACHO
                if cant_alistada < cant_req:
                    todo_alistado_100 = False
                    
                # Validar de forma resiliente si existe algún PNC registrado para esta referencia
                pnc_asociado = db.session.query(PncInyeccion).filter(
                    PncInyeccion.id_codigo == codigo_limpio
                ).first()
                
                if pnc_asociado:
                    alguna_retencion_pnc = True
                
                productos_trazabilidad.append({
                    "codigo": codigo_original,
                    "op": op_actual,
                    "cant_requerida": cant_req,
                    "inyectado": {
                        "cantidad": cant_inyectada,
                        "porcentaje": pct_iny
                    },
                    "pulido": {
                        "cantidad": cant_pulida,
                        "porcentaje": pct_pul
                    },
                    "ensamble": {
                        "requiere": req_ens,
                        "cantidad": cant_ensamblada if req_ens else None,
                        "porcentaje": pct_ens
                    },
                    "empaque": {
                        "cantidad": cant_alistada,
                        "porcentaje": pct_emp
                    }
                })
                
            # Determinar estado global con base en las prioridades de semáforo
            if alguna_retencion_pnc:
                estado_global = "RETENIDO EN PLANTA"
            elif todo_alistado_100 and len(items_pedido_original) > 0:
                estado_global = "LISTO PARA DESPACHO"
            else:
                estado_global = "EN PROCESO"
                
            resultados.append({
                "id_pedido": id_pedido,
                "cliente": cliente,
                "fecha_prometida": fecha_prometida,
                "estado_global": estado_global,
                "productos": productos_trazabilidad
            })
            
        return jsonify({
            "success": True,
            "data": resultados
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en obtener_trazabilidad_gerencial: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error interno al consolidar trazabilidad"}), 500
