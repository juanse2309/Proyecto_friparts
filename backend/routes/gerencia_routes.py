from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import traceback
from backend.core.sql_database import db
from backend.models.sql_models import DistribucionOpPedidos, Pedido, PncInyeccion, ProduccionInyeccion
from backend.services.bom_service import calcular_descuentos_ensamble

gerencia_bp = Blueprint('gerencia_bp', __name__)
logger = logging.getLogger(__name__)

# Catálogos oficiales de motivos de rechazo (PNC)
INYECCION_CRITERIOS = ["Rechupe", "Quemado", "Retención", "Incompleto/Escaso", "Contaminado", "Mancha", "Deformado", "Otros"]
PULIDO_CRITERIOS = ["Rayado", "Porosidad", "Exceso de Rebaba", "Medida Incorrecta", "Mal Acabado", "Otros"]
ENSAMBLE_CRITERIOS = ["Falta de Componente", "Mal Ajuste", "Inserto Defectuoso", "Daño Físico", "Otros"]

def normalizar_criterio(criterio, area):
    if not criterio:
        return "Otros"
    
    crit_lower = str(criterio).lower().strip()
    
    # Remover cualquier indicio de números entre paréntesis como "(90)"
    import re
    crit_lower = re.sub(r'\s*\(\d+\)\s*', '', crit_lower).strip()
    
    if area == "inyeccion":
        if "rechupe" in crit_lower:
            return "Rechupe"
        if "quemado" in crit_lower:
            return "Quemado"
        if "retencion" in crit_lower or "retención" in crit_lower:
            return "Retención"
        if "escaso" in crit_lower or "incompleto" in crit_lower:
            return "Incompleto/Escaso"
        if "contamina" in crit_lower:
            return "Contaminado"
        if "mancha" in crit_lower:
            return "Mancha"
        if "deforma" in crit_lower:
            return "Deformado"
        for c in INYECCION_CRITERIOS[:-1]:
            if c.lower() in crit_lower:
                return c
        return "Otros"
        
    elif area == "pulido":
        if "rayado" in crit_lower or "raya" in crit_lower:
            return "Rayado"
        if "porosidad" in crit_lower or "poros" in crit_lower:
            return "Porosidad"
        if "rebaba" in crit_lower:
            return "Exceso de Rebaba"
        if "medida" in crit_lower or "incorrecta" in crit_lower:
            return "Medida Incorrecta"
        if "acabado" in crit_lower:
            return "Mal Acabado"
        for c in PULIDO_CRITERIOS[:-1]:
            if c.lower() in crit_lower:
                return c
        return "Otros"
        
    elif area == "ensamble":
        if "componente" in crit_lower or "falta" in crit_lower:
            return "Falta de Componente"
        if "ajuste" in crit_lower or "mal aju" in crit_lower:
            return "Mal Ajuste"
        if "inserto" in crit_lower or "defectuoso" in crit_lower:
            return "Inserto Defectuoso"
        if "daño" in crit_lower or "fisico" in crit_lower or "físico" in crit_lower:
            return "Daño Físico"
        for c in ENSAMBLE_CRITERIOS[:-1]:
            if c.lower() in crit_lower:
                return c
        return "Otros"
        
    return "Otros"

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

@gerencia_bp.route('/api/gerencia/metricas-pnc', methods=['GET'])
def obtener_metricas_pnc():
    """
    Dashboard PNC (Lean Manufacturing):
    Consolida las métricas de producto no conforme en 3 niveles leyendo
    de las tablas independientes de PNC (Inyección, Pulido, Ensamble)
    con soporte para rangos de fecha y cálculo de merma contextualizada.
    """
    try:
        from backend.models.sql_models import (
            PncInyeccion, PncPulido, PncEnsamble,
            ProduccionInyeccion, ProduccionPulido, Ensamble
        )
        from sqlalchemy import func
        from datetime import datetime

        # Capturar parámetros de fecha
        fecha_inicio_str = request.args.get('fecha_inicio')
        fecha_fin_str = request.args.get('fecha_fin')

        start_date = None
        end_date = None
        if fecha_inicio_str:
            try:
                start_date = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            except Exception as ex:
                logger.warning(f"Formato incorrecto para fecha_inicio: {fecha_inicio_str}. {ex}")
        if fecha_fin_str:
            try:
                end_date = datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            except Exception as ex:
                logger.warning(f"Formato incorrecto para fecha_fin: {fecha_fin_str}. {ex}")

        # 1. Consultas para PNC (con JOIN condicional para filtrar por rango de fecha)
        iny_query = db.session.query(PncInyeccion.criterio, PncInyeccion.cantidad, PncInyeccion.id_codigo)
        if start_date or end_date:
            iny_query = iny_query.join(ProduccionInyeccion, PncInyeccion.id_inyeccion == ProduccionInyeccion.id_inyeccion)
            if start_date:
                iny_query = iny_query.filter(ProduccionInyeccion.fecha_inicia >= start_date)
            if end_date:
                iny_query = iny_query.filter(ProduccionInyeccion.fecha_inicia <= end_date)
        iny_records = iny_query.all()

        pul_query = db.session.query(PncPulido.criterio, PncPulido.cantidad, PncPulido.codigo)
        if start_date or end_date:
            pul_query = pul_query.join(ProduccionPulido, PncPulido.id_pulido == ProduccionPulido.id_pulido)
            if start_date:
                pul_query = pul_query.filter(ProduccionPulido.fecha >= start_date)
            if end_date:
                pul_query = pul_query.filter(ProduccionPulido.fecha <= end_date)
        pul_records = pul_query.all()

        ens_query = db.session.query(PncEnsamble.criterio, PncEnsamble.cantidad, PncEnsamble.id_codigo)
        if start_date or end_date:
            ens_query = ens_query.join(Ensamble, PncEnsamble.id_ensamble == Ensamble.id_ensamble)
            if start_date:
                ens_query = ens_query.filter(Ensamble.fecha >= start_date)
            if end_date:
                ens_query = ens_query.filter(Ensamble.fecha <= end_date)
        ens_records = ens_query.all()

        # 2. Consultas para Producción Buenas en el mismo rango de fecha
        buenas_iny_query = db.session.query(func.sum(ProduccionInyeccion.cantidad_real))
        if start_date:
            buenas_iny_query = buenas_iny_query.filter(ProduccionInyeccion.fecha_inicia >= start_date)
        if end_date:
            buenas_iny_query = buenas_iny_query.filter(ProduccionInyeccion.fecha_inicia <= end_date)
        buenas_iny = float(buenas_iny_query.scalar() or 0.0)

        buenas_pul_query = db.session.query(func.sum(ProduccionPulido.cantidad_real))
        if start_date:
            buenas_pul_query = buenas_pul_query.filter(ProduccionPulido.fecha >= start_date)
        if end_date:
            buenas_pul_query = buenas_pul_query.filter(ProduccionPulido.fecha <= end_date)
        buenas_pul = float(buenas_pul_query.scalar() or 0.0)

        buenas_ens_query = db.session.query(func.sum(Ensamble.cantidad))
        if start_date:
            buenas_ens_query = buenas_ens_query.filter(Ensamble.fecha >= start_date)
        if end_date:
            buenas_ens_query = buenas_ens_query.filter(Ensamble.fecha <= end_date)
        buenas_ens = float(buenas_ens_query.scalar() or 0.0)

        # 3. Totales PNC por área
        total_iny_pnc = sum(float(r[1] or 0.0) for r in iny_records)
        total_pul_pnc = sum(float(r[1] or 0.0) for r in pul_records)
        total_ens_pnc = sum(float(r[1] or 0.0) for r in ens_records)

        totales_area = {
            "inyeccion": {
                "pnc": total_iny_pnc,
                "buenas": buenas_iny
            },
            "pulido": {
                "pnc": total_pul_pnc,
                "buenas": buenas_pul
            },
            "ensamble": {
                "pnc": total_ens_pnc,
                "buenas": buenas_ens
            }
        }

        # 4. Modos de falla por área
        modos_falla_area = {
            "inyeccion": {},
            "pulido": {},
            "ensamble": {}
        }
        for crit, cant, ref in iny_records:
            crit_key = normalizar_criterio(crit, "inyeccion")
            modos_falla_area["inyeccion"][crit_key] = modos_falla_area["inyeccion"].get(crit_key, 0.0) + float(cant or 0.0)

        for crit, cant, ref in pul_records:
            crit_key = normalizar_criterio(crit, "pulido")
            modos_falla_area["pulido"][crit_key] = modos_falla_area["pulido"].get(crit_key, 0.0) + float(cant or 0.0)

        for crit, cant, ref in ens_records:
            crit_key = normalizar_criterio(crit, "ensamble")
            modos_falla_area["ensamble"][crit_key] = modos_falla_area["ensamble"].get(crit_key, 0.0) + float(cant or 0.0)

        # 5. Pareto de Referencias
        pareto_dict = {}
        for crit, cant, ref in iny_records:
            if ref:
                ref_key = str(ref).strip().upper()
                pareto_dict[ref_key] = pareto_dict.get(ref_key, 0.0) + float(cant or 0.0)

        for crit, cant, ref in pul_records:
            if ref:
                ref_key = str(ref).strip().upper()
                pareto_dict[ref_key] = pareto_dict.get(ref_key, 0.0) + float(cant or 0.0)

        for crit, cant, ref in ens_records:
            if ref:
                ref_key = str(ref).strip().upper()
                pareto_dict[ref_key] = pareto_dict.get(ref_key, 0.0) + float(cant or 0.0)

        sorted_pareto = sorted(pareto_dict.items(), key=lambda x: x[1], reverse=True)[:10]
        pareto_referencias = [{"referencia": ref, "cantidad": val} for ref, val in sorted_pareto]

        # 6. KPIs Globales ─────────────────────────────────────────────
        total_pnc_global  = total_iny_pnc + total_pul_pnc + total_ens_pnc
        total_good_global = buenas_iny + buenas_pul + buenas_ens
        total_output      = total_good_global + total_pnc_global

        pnc_global_percentage = round(
            (total_pnc_global / total_output * 100) if total_output > 0 else 0.0, 2
        )

        # FPY = producto de los rendimientos por estación
        def _yield(buenas, pnc):
            denom = buenas + pnc
            return buenas / denom if denom > 0 else 1.0   # sin datos → 100 %

        fpy_global = round(
            _yield(buenas_iny, total_iny_pnc)
            * _yield(buenas_pul, total_pul_pnc)
            * _yield(buenas_ens, total_ens_pnc)
            * 100, 2
        )

        return jsonify({
            "success": True,
            "totales_area": totales_area,
            "modos_falla_area": modos_falla_area,
            "pareto_referencias": pareto_referencias,
            "pnc_global_percentage": pnc_global_percentage,
            "fpy_global": fpy_global
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en obtener_metricas_pnc: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error al calcular métricas de PNC"}), 500

