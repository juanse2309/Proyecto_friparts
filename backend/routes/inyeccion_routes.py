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
        from backend.utils.drive_service import drive_service
        
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

        # 3. Subir a Drive (Encapsulado para Quota / Permisos)
        try:
            folder_id = Settings.DRIVE_REPORTS_FOLDER_ID
            drive_id = drive_service.subir_archivo(local_file, tmp_filename, folder_id=folder_id)
            if drive_id:
                logger.info(f" ✅ PDF subido exitosamente: {tmp_filename} (ID: {drive_id})")
                return True, None
            else:
                return False, "Error: El PDF se generó pero la subida a Drive falló (posible problema de cuota)."
        except Exception as drive_err:
            logger.error(f" ⚠️ Error subiendo a Drive: {drive_err}")
            return False, f"Error en Drive: {str(drive_err)}"

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
            from backend.utils.formatters import normalizar_codigo
            from backend.app import registrar_entrada, registrar_salida # Mantener por ahora
            
            codigo_raw = item.get('codigo_producto') or item.get('id_codigo')
            id_cod = normalizar_codigo(codigo_raw)
            id_iny = item.get('id_inyeccion') or f"INY-{uuid.uuid4().hex[:8].upper()}"
            cant_real = float(item.get('cantidad_real', 0) or 0)
            pnc_val = float(item.get('pnc', 0) or 0)
            
            # --- PASO 1: Registro PostgreSQL ---
            existente = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion=id_iny).first()
            if existente:
                registro = existente
                registro.id_codigo = id_cod
                registro.cantidad_real = float(cant_real)
                registro.responsable = responsable
                registro.maquina = maquina
                registro.fecha_inicia = fecha_dt
                registro.estado = nuevo_estado
            else:
                registro = ProduccionInyeccion(
                    id_inyeccion=id_iny,
                    fecha_inicia=fecha_dt,
                    id_codigo=id_cod,
                    responsable=responsable,
                    maquina=maquina,
                    cantidad_real=float(cant_real),
                    estado=nuevo_estado
                )
                db.session.add(registro)

            # Estandarización de Departamento
            registro.departamento = 'Inyeccion'

            # Cálculo de Métricas (Si vienen horas en el item o en el turno)
            h_inicio = item.get('hora_inicio') or turno.get('hora_inicio')
            h_fin = item.get('hora_fin') or turno.get('hora_fin')

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
                        
                    # Guardar timestamps como naive Bogota para TIMESTAMP WITHOUT TIME ZONE
                    registro.fecha_inicia = dt_inicio.replace(tzinfo=None)
                    registro.fecha_fin = dt_fin.replace(tzinfo=None)
                except Exception as e_time:
                    logger.warning(f"Error calculando tiempos inyeccion: {e_time}")

            # Registro de PNC (id_row autogenerado en modelo)
            db.session.query(PncInyeccion).filter_by(id_inyeccion=id_iny).delete()
            if pnc_val > 0:
                logger.info(f" [SQL-PNC] Iniciando guardado de {pnc_val} piezas no conformes para el producto {id_cod}")
                nuevo_pnc = PncInyeccion(
                    id_pnc_inyeccion=uuid.uuid4().hex[:8],
                    id_inyeccion=id_iny,
                    id_codigo=id_cod,
                    cantidad=float(pnc_val),
                    criterio=item.get('criterio_pnc'),
                    codigo_ensamble=item.get('codigo_ensamble')
                )
                db.session.add(nuevo_pnc)
                logger.info(f" ✅ [SQL-PNC] Registrados con éxito {pnc_val} registros de piezas no conformes para el producto {id_cod}")

            # --- PASO 2: Actualizar Stock (Sólo si es validación) ---
            if es_validacion:
                try:
                    # Descontar componentes (BOM)
                    from backend.services.bom_service import calcular_descuentos_ensamble
                    bom_res = calcular_descuentos_ensamble(id_cod, int(cant_real))
                    if bom_res.get('success'):
                        for comp in bom_res.get('componentes', []):
                            registrar_salida(comp['codigo_inventario'], comp['cantidad_total_descontar'], "STOCK_BODEGA")
                    # Sumar a 'POR PULIR'
                    registrar_entrada(id_cod, cant_real - pnc_val, "POR PULIR")
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
