"""
Servicio de Ejecución de Ensamble (iniciar/finalizar sesión + BOM).
Extraído de backend/app.py.
"""
import logging
import uuid
from backend.core.sql_database import db
from backend.models.sql_models import Ensamble, PncEnsamble
from backend.services.bom_service import calcular_descuentos_ensamble
from backend.services.stock_service import StockService
from backend.utils.formatters import normalizar_codigo
from backend.utils.time_utils import get_colombia_time

logger = logging.getLogger(__name__)


class BomNoDisponibleException(Exception):
    """Se lanza cuando calcular_descuentos_ensamble no puede resolver la BOM del producto."""
    def __init__(self, message="No se pudo calcular la BOM del producto"):
        self.message = message
        super().__init__(self.message)


class EnsambleService:

    @staticmethod
    def obtener_bom_desde_producto(codigo_entrada):
        """Dado un código de producto, retorna su BOM completo desde NUEVA_FICHA_MAESTRA."""
        if not codigo_entrada:
            raise ValueError('Codigo producto requerido')

        codigo_sistema = normalizar_codigo(codigo_entrada)
        bom_res = calcular_descuentos_ensamble(codigo_sistema, 1)

        if bom_res.get('success'):
            componentes_bom = bom_res['componentes']
            opcion = {
                'codigo_ensamble': codigo_entrada,
                'buje_origen': codigo_sistema,
                'qty': componentes_bom[0].get('cantidad_por_kit', 1) if componentes_bom else 1,
                'tipo': 'producto',
                'componentes': [
                    {'buje_origen': c['codigo_inventario'], 'qty': c['cantidad_por_kit']} for c in componentes_bom
                ]
            }
            return {'codigo_sistema': codigo_sistema, 'opciones': [opcion]}
        return {'codigo_sistema': codigo_sistema, 'opciones': []}

    @staticmethod
    def iniciar(data):
        """
        Persistencia inmediata al iniciar ensamble. Crea un registro EN_PROCESO
        en db_ensambles para que sea visible en el PC de inmediato.

        NOTA DE SEGURIDAD: el `ALTER TABLE db_ensambles ADD COLUMN IF NOT EXISTS
        estado ...` que existía en la versión original (backend/app.py) fue
        eliminado por completo en esta migración — las mutaciones de esquema en
        caliente están prohibidas en la arquitectura de FRITECH. La columna
        `estado` es responsabilidad de las migraciones del esquema, no de un
        endpoint de negocio.
        """
        if not data:
            raise ValueError('No data provided')

        responsable = str(data.get('responsable', '')).strip()
        id_codigo = normalizar_codigo(data.get('id_codigo', ''))

        if not responsable or not id_codigo:
            raise ValueError('Responsable y código requeridos')

        try:
            ahora = get_colombia_time()

            id_ensamble = data.get('id_ensamble') or f"ENS-{uuid.uuid4().hex[:8].upper()}"

            existente = db.session.query(Ensamble).filter_by(id_ensamble=id_ensamble).first()
            if existente:
                return {'ya_registrado': True, 'id_ensamble': id_ensamble}

            h_inicio = data.get('hora_inicio')
            if h_inicio:
                try:
                    hi_h, hi_m = h_inicio.split(':')
                    dt_inicio = ahora.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0).replace(tzinfo=None)
                except Exception:
                    dt_inicio = ahora.replace(tzinfo=None)
            else:
                dt_inicio = ahora.replace(tzinfo=None)

            nuevo_ensamble = Ensamble(
                id_ensamble=id_ensamble,
                id_codigo=id_codigo,
                buje_ensamble=id_codigo,
                responsable=responsable,
                op_numero=data.get('orden_produccion', ''),
                fecha=ahora.date(),
                hora_inicio=dt_inicio,
                departamento='Ensamble',
                cantidad=0,  # Se actualizará al finalizar
                estado='EN_PROCESO'
            )
            db.session.add(nuevo_ensamble)
            db.session.commit()

            logger.info(f"✅ [Ensamble] Inicio persistido: {id_ensamble} ({responsable})")
            return {'ya_registrado': False, 'id_ensamble': id_ensamble}
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error en EnsambleService.iniciar: {e}")
            raise

    @staticmethod
    def finalizar(data):
        """
        Finaliza un ensamble con explosión de materiales (BOM) y descarga de
        inventario. Upsert sobre el registro creado por `iniciar` (si existe).
        """
        if not data:
            raise ValueError('No data provided')

        id_codigo = data.get('id_codigo', '').strip()
        cantidad = int(data.get('cantidad', 0))
        if not id_codigo or cantidad <= 0:
            raise ValueError('Código y cantidad requeridos')

        responsable = data.get('responsable', '').strip()
        defectos = data.get('defectos', [])

        try:
            ahora = get_colombia_time()

            # FASE 1: BOM
            bom_res = calcular_descuentos_ensamble(id_codigo, cantidad)
            if not bom_res.get('success'):
                raise BomNoDisponibleException(bom_res.get('error'))

            # FASE 2: Descarga de Inventario (Híbrida por Prefijo)
            almacen_origen = data.get('almacen_origen', 'STOCK_BODEGA')
            for comp in bom_res['componentes']:
                codigo_comp = str(comp['codigo_inventario']).upper()

                # REGLA: CAR/INT -> BODEGA | Otros -> P. TERMINADO
                if codigo_comp.startswith('CAR') or codigo_comp.startswith('INT'):
                    almacen_a_descontar = 'STOCK_BODEGA'
                else:
                    almacen_a_descontar = 'P. TERMINADO'

                exito, msg = StockService.registrar_salida(codigo_comp, comp['cantidad_total_descontar'], almacen_a_descontar)
                if not exito:
                    # Mantener By-pass: Solo advertir, no detener.
                    logger.warning(f" ⚠️ [HIBRIDO-ENSAMBLE] {msg}")

            # FASE 3: Ensamble (Mapeo completo de columnas SQL)
            id_ensamble_master = data.get('id_ensamble') or uuid.uuid4().hex[:8]

            primer_comp = bom_res['componentes'][0]['codigo_inventario'] if bom_res.get('componentes') else ''
            consumo_total = sum(float(c['cantidad_total_descontar']) for c in bom_res['componentes']) if bom_res.get('componentes') else 0

            id_codigo_clean = normalizar_codigo(id_codigo)

            # CÁLCULO DE TIEMPOS REALES (Procesar horas del frontend)
            duracion_s = 0
            tiempo_m = 0.0
            s_por_u = 0.0
            dt_inicio = ahora.replace(tzinfo=None)
            dt_fin = ahora.replace(tzinfo=None)

            h_ini = data.get('hora_inicio')
            h_fin = data.get('hora_fin')
            if h_ini and h_fin:
                try:
                    hi_h, hi_m = h_ini.split(':')
                    hf_h, hf_m = h_fin.split(':')
                    dt_inicio = ahora.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0).replace(tzinfo=None)
                    dt_fin = ahora.replace(hour=int(hf_h), minute=int(hf_m), second=0, microsecond=0).replace(tzinfo=None)

                    diff = dt_fin - dt_inicio
                    duracion_s = int(diff.total_seconds())
                    if duracion_s < 0:
                        duracion_s += 86400  # Cruce de medianoche
                    tiempo_m = float(round(duracion_s / 60.0, 2))
                    if cantidad > 0:
                        s_por_u = float(round(duracion_s / cantidad, 2))
                    logger.info(f"⏱️ [Ensamble] Tiempos: {h_ini}->{h_fin} = {duracion_s}s ({tiempo_m}min)")
                except Exception as e_time:
                    logger.warning(f"Error calculando tiempos ensamble: {e_time}")

            # Upsert: Si existe registro previo (de iniciar), actualizar; si no, crear nuevo
            existente = db.session.query(Ensamble).filter_by(id_ensamble=id_ensamble_master).first()
            if existente:
                nuevo_ensamble = existente
                nuevo_ensamble.id_codigo = id_codigo_clean
                nuevo_ensamble.buje_ensamble = id_codigo_clean
                nuevo_ensamble.cantidad = float(cantidad)
                nuevo_ensamble.qty = float(data.get('qty', 1) or 1)
                nuevo_ensamble.responsable = responsable
                nuevo_ensamble.op_numero = data.get('orden_produccion', '')
                nuevo_ensamble.almacen_para_descargar = almacen_origen
                nuevo_ensamble.almacen_destino = data.get('almacen_destino', '')
                nuevo_ensamble.buje_origen = primer_comp
                nuevo_ensamble.consumo_total = float(consumo_total)
                nuevo_ensamble.hora_inicio = dt_inicio
                nuevo_ensamble.hora_fin = dt_fin
                nuevo_ensamble.estado = 'FINALIZADO'
            else:
                nuevo_ensamble = Ensamble(
                    id_ensamble=id_ensamble_master,
                    id_codigo=id_codigo_clean,
                    buje_ensamble=id_codigo_clean,
                    cantidad=float(cantidad),
                    qty=float(data.get('qty', 1) or 1),
                    responsable=responsable,
                    op_numero=data.get('orden_produccion', ''),
                    almacen_para_descargar=almacen_origen,
                    almacen_destino=data.get('almacen_destino', ''),
                    buje_origen=primer_comp,
                    consumo_total=float(consumo_total),
                    fecha=ahora.date(),
                    hora_inicio=dt_inicio,
                    hora_fin=dt_fin,
                    departamento='Ensamble'
                )
                db.session.add(nuevo_ensamble)

            nuevo_ensamble.duracion_segundos = duracion_s
            nuevo_ensamble.tiempo_total_minutos = tiempo_m
            nuevo_ensamble.segundos_por_unidad = s_por_u

            # FASE 4: Calidad (id_pnc_ensamble TEXT UUID)
            for d in defectos:
                cant_pnc = float(d.get('cantidad', 0))
                if cant_pnc > 0:
                    db.session.add(PncEnsamble(
                        id_pnc_ensamble=uuid.uuid4().hex[:8],
                        id_ensamble=id_ensamble_master,
                        id_codigo=id_codigo,
                        cantidad=cant_pnc,
                        criterio=d.get('criterio', 'Defecto Ensamble')
                    ))

            # Cargar producto terminado
            StockService.registrar_entrada(id_codigo, cantidad, "PRODUCTO TERMINADO")

            # FASE 5: Transacción
            db.session.commit()
            logger.info(f"✅ ENSAMBLE EXITOSO: {id_codigo} (ID: {id_ensamble_master})")
            return {'id_ensamble': id_ensamble_master}
        except Exception as e:
            db.session.rollback()
            if not isinstance(e, BomNoDisponibleException):
                logger.error(f"❌ Error en EnsambleService.finalizar: {e}")
            raise
