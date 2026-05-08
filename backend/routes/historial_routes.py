from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
from sqlalchemy import between
from backend.core.sql_database import db
from backend.models.sql_models import (
    ProduccionInyeccion, ProduccionPulido, Ensamble, 
    Pedido, Pnc, Mezcla, Molido, RawVentas,
    PncInyeccion, PncPulido, PncEnsamble
)


historial_bp = Blueprint('historial_bp', __name__)
logger = logging.getLogger(__name__)

@historial_bp.route('/api/historial-global', methods=['GET'])
def obtener_historial_global():
    """
    Obtiene historial consolidado 100% SQL-Native con casteo seguro y Bypass de OID 25 para Ensamble.
    """
    try:
        from sqlalchemy import between, text
        from backend.models.sql_models import (
            ProduccionInyeccion, ProduccionPulido, Ensamble, 
            Pedido, Pnc, Mezcla, Molido, RawVentas,
            PncInyeccion, PncPulido, PncEnsamble
        )

        
        desde_str = request.args.get('desde', '')
        hasta_str = request.args.get('hasta', '')
        tipo_filtro = request.args.get('tipo', '')
        
        hoy = datetime.now().date()
        fecha_desde = datetime.strptime(desde_str, '%Y-%m-%d').date() if desde_str else hoy
        fecha_hasta = datetime.strptime(hasta_str, '%Y-%m-%d').date() if hasta_str else hoy
        
        movimientos = []

        # 1. INYECCIÓN
        if not tipo_filtro or tipo_filtro == 'INYECCION':
            try:
                res_iny = ProduccionInyeccion.query.filter(ProduccionInyeccion.fecha_inicia.between(fecha_desde, fecha_hasta)).all()
                for r in res_iny:
                    movimientos.append({
                        'Fecha': r.fecha_inicia.strftime('%d/%m/%Y') if r.fecha_inicia else '',
                        'Tipo': 'INYECCION',
                        'Producto': str(r.id_codigo or ''),
                        'Responsable': str(r.responsable or 'SISTEMA'),
                        'Cant': int(float(r.cantidad_real or 0)),
                        'Orden': str(r.id_inyeccion or ''),
                        'Extra': str(r.maquina or ''),
                        'Detalle': f"Molde: {r.molde or ''} | Cav: {r.cavidades or 1}",
                        'hoja': 'db_inyeccion',
                        'fila': r.id
                    })
            except Exception as e_iny:
                logger.error(f"Error en bloque INYECCION: {e_iny}")

        # 2. PULIDO
        if not tipo_filtro or tipo_filtro == 'PULIDO':
            try:
                res_pul = ProduccionPulido.query.filter(ProduccionPulido.fecha.between(fecha_desde, fecha_hasta)).all()
                for r in res_pul:
                    movimientos.append({
                        'Fecha': r.fecha.strftime('%d/%m/%Y') if r.fecha else '',
                        'Tipo': 'PULIDO',
                        'Producto': str(r.codigo or ''),
                        'Responsable': str(r.responsable or 'SISTEMA'),
                        'Cant': int(float(r.cantidad_real or 0)),
                        'Orden': str(r.orden_produccion or r.id_pulido or ''),
                        'Extra': f"OP: {r.orden_produccion or ''}",
                        'Detalle': str(r.observaciones or f"PNC Iny: {r.pnc_inyeccion or 0}"),
                        'hoja': 'db_pulido',
                        'fila': r.id
                    })
            except Exception as e_pul:
                logger.error(f"Error en bloque PULIDO: {e_pul}")

        # 3. VENTAS (db_ventas - Facturación Real)
        if not tipo_filtro or tipo_filtro in ['VENTA', 'VENTAS', 'FACTURACION']:
            try:
                res_ven = RawVentas.query.filter(RawVentas.fecha.between(fecha_desde, fecha_hasta)).all()
                for r in res_ven:
                    movimientos.append({
                        'Fecha': r.fecha.strftime('%d/%m/%Y') if r.fecha else '',
                        'Tipo': 'VENTA',
                        'Producto': str(r.productos or ''),
                        'Responsable': str(r.cliente or 'CLIENTE DESCONOCIDO'),
                        'Cant': int(float(r.cantidad or 0)),
                        'Orden': str(r.documento or ''),
                        'Extra': str(r.clasificacion or ''),
                        'Detalle': f"Estado: {r.estado or ''} | Ingreso: ${r.total_ingresos or 0}",
                        'hoja': 'db_ventas',
                        'fila': r.id
                    })
            except Exception as e_ven:
                logger.error(f"Error en bloque VENTAS (db_ventas): {e_ven}")


        # 🔥 4. ENSAMBLE (CONSULTA RAW CON BYPASS OID 25)
        if not tipo_filtro or tipo_filtro == 'ENSAMBLE':
            try:
                # SQL Plano para saltar validación de tipos del modelo
                query_sql = text("""
                    SELECT id, fecha, id_codigo, responsable, cantidad, op_numero, buje_ensamble, observaciones, id_ensamble
                    FROM db_ensambles 
                    WHERE CAST(fecha AS DATE) BETWEEN :f1 AND :f2
                """)
                res_ens = db.session.execute(query_sql, {"f1": fecha_desde, "f2": fecha_hasta})
                
                for r in res_ens:
                    # Formateo seguro de fecha
                    f_reg = ''
                    if r.fecha:
                        if hasattr(r.fecha, 'strftime'): f_reg = r.fecha.strftime('%d/%m/%Y')
                        else: f_reg = str(r.fecha).split(' ')[0]

                    movimientos.append({
                        'Fecha': f_reg,
                        'Tipo': 'ENSAMBLE',
                        'Producto': str(r.id_codigo or ''),
                        'Responsable': str(r.responsable or 'SISTEMA'),
                        'Cant': int(float(r.cantidad or 0)),
                        'Orden': str(r.op_numero or r.id_ensamble or ''),
                        'Extra': str(r.buje_ensamble or ''),
                        'Detalle': str(r.observaciones or ''),
                        'hoja': 'db_ensambles',
                        'fila': r.id
                    })
            except Exception as e_ens:
                logger.error(f"⚠️ Error individual en bloque ENSAMBLE (Bypass SQL activado): {str(e_ens)}")

        # 5. MEZCLA (Casteo Float Crítico)
        if not tipo_filtro or tipo_filtro == 'MEZCLA':
            try:
                res_mez = Mezcla.query.filter(Mezcla.fecha.between(fecha_desde, fecha_hasta)).all()
                for r in res_mez:
                    movimientos.append({
                        'Fecha': r.fecha.strftime('%d/%m/%Y') if r.fecha else '',
                        'Tipo': 'MEZCLA',
                        'Producto': 'PREPARACION MATERIAL',
                        'Responsable': str(r.responsable or 'SISTEMA'),
                        'Cant': f"{float(r.virgen_kg or 0)}Kg V",
                        'Orden': f"MEZ-{r.id}",
                        'Extra': str(r.maquina or ''),
                        'Detalle': str(r.observaciones or ''),
                        'hoja': 'db_mezcla',
                        'fila': r.id,
                        'MOLIDO': float(r.molido_kg or 0),
                        'PIGMENTO': float(r.pigmento_kg or 0),
                        'VIRGEN': float(r.virgen_kg or 0)
                    })
            except Exception as e_mez:
                logger.error(f"Error en bloque MEZCLA: {e_mez}")

        # 5.1 MOLIDO (NUEVO)
        if not tipo_filtro or tipo_filtro == 'MEZCLA' or tipo_filtro == 'MOLIDO':
            try:
                res_mol = Molido.query.filter(between(Molido.fecha_registro, fecha_desde, fecha_hasta)).all()
                for r in res_mol:
                    movimientos.append({
                        'Fecha': r.fecha_registro.strftime('%d/%m/%Y'),
                        'Tipo': 'MOLIDO',
                        'Producto': str(r.tipo_material or 'Molido'),
                        'Responsable': str(r.responsable or 'SISTEMA'),
                        'Cant': f"{float(r.peso_kg or 0)} Kg",
                        'Orden': f"MOL-{r.id}",
                        'Extra': str(r.tipo_material or ''),
                        'Detalle': str(r.observaciones or ''),
                        'hoja': 'db_molido',
                        'fila': r.id
                    })
            except Exception as e_mol:
                logger.error(f"Error en bloque MOLIDO: {e_mol}")

        # 6. PNC (Defectos - Unificado de todas las áreas)
        if not tipo_filtro or tipo_filtro == 'PNC':
            try:
                # 6.1 PNC General (db_pnc)
                res_pnc = Pnc.query.filter(Pnc.fecha.between(fecha_desde, fecha_hasta)).all()
                for r in res_pnc:
                    movimientos.append({
                        'Fecha': r.fecha.strftime('%d/%m/%Y') if r.fecha else '',
                        'Tipo': 'PNC',
                        'Producto': str(r.id_codigo or ''),
                        'Responsable': 'CONTROL CALIDAD',
                        'Cant': int(float(r.cantidad or 0)),
                        'Orden': str(r.id_pnc or ''),
                        'Extra': str(r.criterio or ''),
                        'Detalle': f"Ref Ensamble: {r.codigo_ensamble or ''}",
                        'hoja': 'db_pnc',
                        'fila': r.id
                    })

                # 6.2 PNC Inyección (db_pnc_inyeccion)
                # Nota: Estas tablas no tienen fecha propia, se asocian a la fecha de consulta o se busca por el registro padre
                # Pero el usuario pidió unificarlas. Si no tienen fecha, buscaremos los que coincidan con la lógica de hoy o registros recientes.
                # Mejor: Buscamos por registros que tengan el id_row reciente si no hay fecha.
                # Sin embargo, para no romper el flujo de fecha, solo buscaremos en db_pnc que sí tiene fecha, 
                # O consultaremos las tablas de producción que SI tienen PNC y fecha.
                
                # OPTIMIZACIÓN: Buscamos en tablas de producción registros con PNC > 0
                res_iny_pnc = ProduccionInyeccion.query.filter(
                    ProduccionInyeccion.fecha_inicia.between(fecha_desde, fecha_hasta),
                    ProduccionInyeccion.pnc_total != '0'
                ).all()
                for r in res_iny_pnc:
                    movimientos.append({
                        'Fecha': r.fecha_inicia.strftime('%d/%m/%Y'),
                        'Tipo': 'PNC',
                        'Producto': str(r.id_codigo or ''),
                        'Responsable': 'INYECCION (Defectos)',
                        'Cant': int(float(r.pnc_total or 0)),
                        'Orden': str(r.id_inyeccion or ''),
                        'Extra': 'PNC INYECCION',
                        'Detalle': f"[PNC_DETAIL] {r.pnc_detalle or '{}'}",
                        'hoja': 'db_inyeccion',
                        'fila': r.id
                    })

                res_pul_pnc = ProduccionPulido.query.filter(
                    ProduccionPulido.fecha.between(fecha_desde, fecha_hasta),
                    (ProduccionPulido.pnc_inyeccion > 0) | (ProduccionPulido.pnc_pulido > 0)
                ).all()
                for r in res_pul_pnc:
                    cant_pnc = (r.pnc_inyeccion or 0) + (r.pnc_pulido or 0)
                    movimientos.append({
                        'Fecha': r.fecha.strftime('%d/%m/%Y'),
                        'Tipo': 'PNC',
                        'Producto': str(r.codigo or ''),
                        'Responsable': 'PULIDO (Defectos)',
                        'Cant': int(cant_pnc),
                        'Orden': str(r.orden_produccion or ''),
                        'Extra': 'PNC PULIDO/INY',
                        'Detalle': f"Iny: {r.pnc_inyeccion} | Pul: {r.pnc_pulido} | {r.criterio_pnc_pulido or ''}",
                        'hoja': 'db_pulido',
                        'fila': r.id
                    })

            except Exception as e_pnc:
                logger.error(f"Error en bloque PNC Unificado: {e_pnc}")


        # 3. Ordenamiento final por fecha descendente
        movimientos.sort(key=lambda x: datetime.strptime(x['Fecha'], '%d/%m/%Y') if x['Fecha'] else hoy, reverse=True)

        return jsonify({
            'success': True,
            'data': movimientos,
            'total': len(movimientos)
        }), 200

    except Exception as e:
        import traceback
        logger.error(f"Error crítico en historial global SQL: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': f"Error de serialización SQL: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Error crítico en historial global SQL: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
