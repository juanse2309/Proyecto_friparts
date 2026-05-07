import os
import uuid
import logging
import traceback
import pytz
from datetime import datetime
from flask import Blueprint, jsonify, request
from backend.utils.auth_middleware import require_role, ROL_ADMINS
from backend.models.sql_models import db, ProduccionInyeccion, PncInyeccion, ProgramacionInyeccion
from backend.config.settings import Settings

logger = logging.getLogger(__name__)
inyeccion_bp = Blueprint('inyeccion_bp', __name__)

def process_pdf_and_drive_internal(data, pnc=0, producto_nombre="", is_batch=False, items_batch=None):
    """
    Versión interna para generación de PDF y subida a Drive.
    Resiliente a errores de cuota o permisos.
    """
    try:
        from backend.utils.report_service import PDFGenerator
        from backend.utils.report_service import PDFGenerator
        
        # 1. Determinar Metadatos y Nombre de Archivo
        maquina = str(data.get('maquina') or 'S-M').replace(" ", "-")
        fecha_raw = str(data.get('fecha_inicio') or datetime.now().strftime('%Y-%m-%d'))
        fecha_clean = fecha_raw.split(' ')[0].replace('/', '-') 
        op = str(data.get('orden_produccion') or 'S-OP').replace(" ", "-")
        tmp_filename = f"{fecha_clean}_{op}_{maquina}.pdf".replace(" ", "_")
        
        import re
        tmp_filename = re.sub(r'[\\/*?:"<>|]', "", tmp_filename)
        tmp_path = os.path.join(os.getcwd(), "temp_reports")
        if not os.path.exists(tmp_path):
            os.makedirs(tmp_path)
            
        local_file = os.path.join(tmp_path, tmp_filename)
        
        # 2. Generar PDF
        if is_batch:
            success = PDFGenerator.generar_reporte_inyeccion_lote(data, items_batch, local_file)
        else:
            success = PDFGenerator.generar_reporte_inyeccion(data, local_file, pnc, producto_nombre)

        if not success:
            return False, "Error al generar el archivo PDF localmente."

        # 3. [DISABLED] Subir a Drive (Eliminado por decommissoning Google)
        logger.info(f" ✅ PDF generado localmente: {tmp_filename}. (Subida a Drive deshabilitada)")
        return True, None

    except Exception as e:
        logger.error(f" ❌ ERROR CRÍTICO en proceso PDF/Drive: {str(e)}")
        return False, str(e)
    finally:
        if 'local_file' in locals() and os.path.exists(local_file):
            try: os.remove(local_file)
            except: pass

@inyeccion_bp.route('/api/inyeccion/lote', methods=['POST'])
def registrar_inyeccion_lote():
    """
    PASO 1-3: SQL-First Validation Workflow.
    Paso 1: SQL Data. Paso 2: Stock. Paso 3: Estado VALIDADO. Paso 4: PDF (Opcional).
    """
    try:
        data = request.json
        turno = data.get('turno', {})
        items = data.get('items', [])
        
        if not items:
            return jsonify({'success': False, 'error': 'No hay items para registrar'}), 400

        responsable = str(turno.get('responsable', '')).strip()
        maquina = str(turno.get('maquina', '')).strip()
        fecha_str = turno.get('fecha_inicio', '')
        
        try:
            bogota_tz = pytz.timezone('America/Bogota')
            ahora_col = datetime.now(bogota_tz)
            fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else ahora_col.date()
        except:
            fecha_dt = ahora_col.date()

        # Usar un flag para determinar si es VALIDACIÓN (Paola) o REGISTRO (Operario)
        es_validacion = turno.get('es_validacion', False)
        nuevo_estado = 'VALIDADO' if es_validacion else 'PENDIENTE'

        for item in items:
            from backend.utils.formatters import normalizar_codigo, to_float, to_int
            from backend.app import registrar_entrada, registrar_salida
            
            # --- Identificación del Registro ---
            id_sql = item.get('id_sql') or item.get('id')
            id_iny = item.get('id_inyeccion') or f"INY-{uuid.uuid4().hex[:8].upper()}"
            codigo_raw = item.get('codigo_producto') or item.get('id_codigo')
            id_cod = normalizar_codigo(codigo_raw)
            
            # Intentar buscar por ID primario (SQL) primero para evitar colisiones en lotes mixtos
            registro = None
            if id_sql:
                registro = db.session.get(ProduccionInyeccion, id_sql)
            
            if not registro:
                # Fallback: buscar por id_inyeccion + id_codigo si es validación
                registro = db.session.query(ProduccionInyeccion).filter_by(
                    id_inyeccion=id_iny, 
                    id_codigo=id_cod
                ).first()

            if not registro:
                registro = ProduccionInyeccion(id_inyeccion=id_iny, estado=nuevo_estado)
                db.session.add(registro)

            # --- Sincronización de Campos (Mapping Completo) ---
            registro.id_codigo      = id_cod
            registro.responsable    = responsable
            registro.maquina        = maquina
            registro.fecha_inicia   = fecha_dt
            registro.estado         = nuevo_estado
            registro.departamento   = 'Inyeccion'
            
            # Datos de Producción
            registro.cantidad_real  = to_float(item.get('cantidad_real'))
            registro.cavidades      = to_int(item.get('no_cavidades') or item.get('cavidades'), default=1)
            registro.molde          = to_int(item.get('molde') or item.get('observaciones')) # Molde suele venir en observaciones en el frontend
            
            # Nuevas Columnas Sincronizadas
            registro.hora_llegada   = turno.get('hora_llegada')
            registro.hora_inicio    = item.get('hora_inicio') or turno.get('hora_inicio')
            registro.hora_termina   = item.get('hora_fin') or item.get('hora_termina') or turno.get('hora_fin') or turno.get('hora_termina')
            registro.contador_maq   = to_float(item.get('contador_maq'))
            registro.cant_contador  = to_float(item.get('cant_contador'))
            registro.tomados_en_proceso = to_float(item.get('tomados_en_proceso'))
            registro.peso_tomadas_en_proceso = to_float(item.get('peso_tomadas_en_proceso'))
            registro.almacen_destino = item.get('almacen_destino') or turno.get('almacen_destino', 'POR PULIR')
            registro.codigo_ensamble = item.get('codigo_ensamble')
            registro.orden_produccion = item.get('orden_produccion') or turno.get('orden_produccion')
            registro.observaciones   = item.get('observaciones')
            registro.peso_vela_maquina = to_float(item.get('peso_vela_maquina') or turno.get('peso_vela_maquina'))
            registro.peso_bujes      = to_float(item.get('peso_bujes'))
            registro.id_programacion = str(item.get('id_programacion') or turno.get('id_programacion', ''))
            registro.produccion_teorica = to_float(item.get('produccion_teorica'))
            registro.pnc_total       = to_float(item.get('pnc') or item.get('pnc_total'))
            registro.pnc_detalle     = item.get('criterio_pnc') or item.get('pnc_detalle')
            registro.peso_lote       = to_float(item.get('peso_lote'))
            registro.calidad_responsable = item.get('calidad_responsable')
            registro.entrada         = to_float(item.get('entrada') or turno.get('entrada_manual'))
            registro.salida          = to_float(item.get('salida') or turno.get('salida_manual'))

            # --- Cálculo de Tiempos y Métricas ---
            h_inicio = registro.hora_inicio
            h_fin = registro.hora_termina

            if h_inicio and h_fin:
                try:
                    colombia_tz = pytz.timezone('America/Bogota')
                    ahora_col = datetime.now(colombia_tz)
                    
                    hi_h, hi_m = h_inicio.split(':')
                    hf_h, hf_m = h_fin.split(':')
                    
                    dt_inicio = ahora_col.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0)
                    dt_fin = ahora_col.replace(hour=int(hf_h), minute=int(hf_m), second=0, microsecond=0)
                    
                    diff = dt_fin - dt_inicio
                    segundos = int(diff.total_seconds())
                    if segundos < 0: segundos += 86400 # Cruce medianoche
                    
                    registro.duracion_segundos = segundos
                    registro.tiempo_total_minutos = float(round(segundos / 60.0, 2))
                    
                    if registro.cantidad_real > 0:
                        registro.segundos_por_unidad = float(round(segundos / registro.cantidad_real, 2))
                    else:
                        registro.segundos_por_unidad = 0.0
                        
                    # Sincronizar timestamps DateTime si es necesario
                    registro.fecha_inicia = dt_inicio.replace(tzinfo=None)
                    registro.fecha_fin = dt_fin.replace(tzinfo=None)
                except Exception as e_time:
                    logger.warning(f"Error calculando tiempos inyeccion: {e_time}")

            # Registro de PNC
            pnc_val = registro.pnc_total
            db.session.query(PncInyeccion).filter_by(id_inyeccion=id_iny, id_codigo=id_cod).delete()
            if pnc_val > 0:
                nuevo_pnc = PncInyeccion(
                    id_pnc_inyeccion=uuid.uuid4().hex[:8],
                    id_inyeccion=id_iny,
                    id_codigo=id_cod,
                    cantidad=float(pnc_val),
                    criterio=registro.pnc_detalle,
                    codigo_ensamble=registro.codigo_ensamble
                )
                db.session.add(nuevo_pnc)

            # --- PASO 2: Actualizar Stock (Sólo si es validación) ---
            if es_validacion:
                try:
                    from backend.services.bom_service import calcular_descuentos_ensamble
                    bom_res = calcular_descuentos_ensamble(id_cod, int(registro.cantidad_real))
                    if bom_res.get('success'):
                        for comp in bom_res.get('componentes', []):
                            registrar_salida(comp['codigo_inventario'], comp['cantidad_total_descontar'], "STOCK_BODEGA")
                    registrar_entrada(id_cod, registro.cantidad_real - pnc_val, "POR PULIR")
                except Exception as e_stock:
                    logger.error(f"Error stock {id_cod}: {e_stock}")

        # --- PASO 3: Confirmar Transacción SQL ---
        id_prog = turno.get('id_programacion')
        if id_prog and id_prog != 'LEGACY':
            db.session.query(ProgramacionInyeccion).filter_by(id=id_prog).update({'estado': 'COMPLETADO'})

        db.session.commit()
        logger.info(f" ✅ Lote {nuevo_estado} en SQL: {len(items)} items.")
        
        # --- PASO 4: PDF (Opcional y Resiliente) ---
        pdf_ok = False
        try:
            pdf_ok, _ = process_pdf_and_drive_internal(data=turno, items_batch=items, is_batch=True)
        except Exception as e_pdf:
            logger.error(f" ⚠️ Error en módulo PDF (Omitiendo): {e_pdf}")

        return jsonify({
            'success': True,
            'mensaje': f'Lote {nuevo_estado} exitosamente',
            'pdf_generated': pdf_ok,
            'pdf_status': "success" if pdf_ok else "failed"
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f" ❌ Error en registrar_inyeccion_lote: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inyeccion_bp.route('/api/inyeccion/iniciar_turno', methods=['POST'])
def iniciar_turno_inyeccion():
    """
    Persistencia inmediata al iniciar turno de inyección.
    Crea un registro PENDIENTE en db_inyeccion para que sea visible en el PC de inmediato.
    Sigue el patrón de Pulido: persistirInicioSQL.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        colombia_tz = pytz.timezone('America/Bogota')
        ahora = datetime.now(colombia_tz)

        responsable = str(data.get('responsable', '')).strip()
        maquina = str(data.get('maquina', '')).strip()
        fecha_str = data.get('fecha_inicio', ahora.strftime('%Y-%m-%d'))

        if not responsable or not maquina:
            return jsonify({"success": False, "error": "Responsable y máquina requeridos"}), 400

        try:
            fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except:
            fecha_dt = ahora.date()

        id_inyeccion = data.get('id_inyeccion') or f"INY-{uuid.uuid4().hex[:8].upper()}"
        id_codigo = data.get('id_codigo')

        # [RESTRICCIÓN PAOLA] No permitir registros sin código para evitar huérfanos
        if not id_codigo:
            logger.warning(f"⚠️ [Inyeccion] Intento de iniciar_turno rechazado: falta id_codigo. Responsable: {responsable}")
            return jsonify({
                "success": False, 
                "error": "El código de producto es obligatorio para iniciar el registro en SQL."
            }), 400

        # Buscar si ya existe (evitar duplicados)
        existente = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion=id_inyeccion).first()
        if existente:
            return jsonify({"success": True, "message": "Turno ya registrado", "id_inyeccion": id_inyeccion}), 200

        # Crear registro PENDIENTE (visible inmediatamente en el PC)
        h_inicio = data.get('hora_inicio')
        dt_inicio = None
        if h_inicio:
            try:
                hi_h, hi_m = h_inicio.split(':')
                dt_inicio = ahora.replace(hour=int(hi_h), minute=int(hi_m), second=0, microsecond=0).replace(tzinfo=None)
            except:
                dt_inicio = ahora.replace(tzinfo=None)
        else:
            dt_inicio = ahora.replace(tzinfo=None)

        registro = ProduccionInyeccion(
            id_inyeccion=id_inyeccion,
            fecha_inicia=dt_inicio or fecha_dt,
            responsable=responsable,
            maquina=maquina,
            estado='EN_PROCESO',
            departamento='Inyeccion',
            cantidad_real=0  # Se actualizará al finalizar
        )
        db.session.add(registro)
        db.session.commit()

        logger.info(f"✅ [Inyeccion] Turno iniciado y persistido: {id_inyeccion} ({responsable} en {maquina})")

        return jsonify({
            "success": True,
            "message": "Turno iniciado y persistido en SQL",
            "id_inyeccion": id_inyeccion
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en iniciar_turno_inyeccion: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@inyeccion_bp.route('/api/inyeccion/dashboard_stats', methods=['GET'])
@require_role(ROL_ADMINS + ['JEFE INYECCION', 'INYECCION'])
def get_inyeccion_stats():
    # Placeholder
    return jsonify({"success": True, "message": "Estadísticas de inyección (WIP)"})
