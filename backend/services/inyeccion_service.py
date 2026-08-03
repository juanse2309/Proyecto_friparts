import logging
from sqlalchemy import text
from backend.models.sql_models import db

logger = logging.getLogger(__name__)

_MESES_ES = (
    'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'
)


class InyeccionService:

    @staticmethod
    def _formatear_fecha_es(fecha_dt):
        """DD/Mes/YYYY en español a partir de un datetime ya en hora Colombia (naive)."""
        if not fecha_dt:
            return ''
        return f"{fecha_dt.day:02d}/{_MESES_ES[fecha_dt.month - 1]}/{fecha_dt.year}"

    @staticmethod
    def obtener_pendientes_validacion():
        """
        Consulta los lotes de Inyección en estado PENDIENTE/FINALIZADO listos
        para validación y arma el DTO que consume el frontend.
        """
        try:
            sql = """
                SELECT
                    i.id as id_sql,
                    i.id_inyeccion,
                    i.fecha_inicia as fecha,
                    i.fecha_fin,
                    i.id_codigo,
                    i.responsable,
                    i.maquina,
                    i.molde,
                    i.cavidades,
                    i.estado,
                    i.cantidad_real,
                    i.hora_inicio,
                    i.hora_termina as hora_fin,
                    i.cant_contador,
                    i.almacen_destino,
                    i.orden_produccion,
                    i.observaciones,
                    COALESCE(i.pnc_total, 0) as pnc_total,
                    i.pnc_detalle,
                    i.peso_lote,
                    i.entrada,
                    i.salida
                FROM db_inyeccion i
                WHERE i.estado IN ('PENDIENTE', 'FINALIZADO')
                ORDER BY i.fecha_inicia DESC
            """
            pendientes = db.session.execute(text(sql)).mappings().all()

            data = []
            import re

            def _clean_num(val):
                if val is None:
                    return 0
                if isinstance(val, (int, float)):
                    return val
                clean = re.sub(r'[^0-9.]', '', str(val))
                return float(clean) if clean else 0

            for p in pendientes:
                buenas = _clean_num(p['cantidad_real'])
                pnc = _clean_num(p['pnc_total'])

                data.append({
                    'id_sql': p['id_sql'],
                    'id_inyeccion': p['id_inyeccion'],
                    'fecha': p['fecha'].isoformat() if p['fecha'] else '',
                    'fecha_display': InyeccionService._formatear_fecha_es(p['fecha']),
                    'hora_inicio': p['hora_inicio'] or (p['fecha'].strftime('%H:%M') if p['fecha'] else ''),
                    'hora_fin': p['hora_fin'] or (p['fecha_fin'].strftime('%H:%M') if p.get('fecha_fin') else ''),
                    'id_codigo': p['id_codigo'],
                    'responsable': p['responsable'],
                    'cantidad_inyectada': buenas + pnc,  # total bruto inyectado
                    'cantidad_real': buenas,  # buenas reportadas
                    'pnc': pnc,
                    'revueltos': 0,
                    'wip': 0,
                    'maquina': p['maquina'],
                    'molde': p['molde'],
                    'cavidades': p['cavidades'],
                    'cant_contador': _clean_num(p['cant_contador']),
                    'almacen_destino': p['almacen_destino'],
                    'orden_produccion': p['orden_produccion'],
                    'observaciones': p['observaciones'],
                    'pnc_detalle': p['pnc_detalle'],
                    'entrada': _clean_num(p['entrada']),
                    'salida': _clean_num(p['salida']),
                    'peso_lote': _clean_num(p['peso_lote'])
                })

            return {'success': True, 'data': data}

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en InyeccionService.obtener_pendientes_validacion: {e}")
            return {'success': False, 'error': str(e)}


inyeccion_service = InyeccionService()
