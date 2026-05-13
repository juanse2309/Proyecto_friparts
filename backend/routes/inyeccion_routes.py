import os
import uuid
import logging
import traceback
import pytz
from datetime import datetime
from flask import Blueprint, jsonify, request
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_JEFES
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

        # Extraer ID de Inyección del turno para unificar el lote
        id_iny_lote = turno.get('id_inyeccion') or f"INY-{uuid.uuid4().hex[:8].upper()}"
        responsable_lote = turno.get('responsable')
        maquina_lote = turno.get('maquina')

        for item in items:
            from backend.utils.formatters import normalizar_codigo, to_float, to_int
            from backend.app import registrar_entrada, registrar_salida
            
            # --- Identificación del Registro ---
            id_sql = item.get('id_sql') or item.get('id')
            id_iny = item.get('id_inyeccion') or id_iny_lote
            codigo_raw = item.get('codigo_producto') or item.get('id_codigo')
            id_cod = normalizar_codigo(codigo_raw)
            
            # 1. Búsqueda Robusta del Registro Existente (Evitar Duplicados)
            registro = None
            if id_sql:
                registro = db.session.get(ProduccionInyeccion, id_sql)
            
            if not registro and id_iny:
                # Buscar por id_inyeccion + id_codigo (Lógica principal de lotes)
                registro = db.session.query(ProduccionInyeccion).filter_by(
                    id_inyeccion=id_iny, 
                    id_codigo=id_cod
                ).first()

            # Fallback Manual: Si no hay ID de lote pero hay Maquina + Responsable + Código + Fecha hoy
            if not registro and not id_sql:
                registro = db.session.query(ProduccionInyeccion).filter(
                    ProduccionInyeccion.maquina == maquina,
                    ProduccionInyeccion.responsable == responsable,
                    ProduccionInyeccion.id_codigo == id_cod,
                    db.func.date(ProduccionInyeccion.fecha_inicia) == fecha_dt,
                    ProduccionInyeccion.estado == 'EN_PROCESO'
                ).order_by(ProduccionInyeccion.id.desc()).first()

            if not registro:
                logger.info(f"🆕 [Inyeccion] Creando nuevo registro: {id_iny} - {id_cod}")
                registro = ProduccionInyeccion(id_inyeccion=id_iny, estado=nuevo_estado, id_codigo=id_cod)
                db.session.add(registro)
            else:
                logger.info(f"🔄 [Inyeccion] Actualizando registro existente (ID SQL: {registro.id})")

            # --- Sincronización de Campos ---
            registro.id_codigo      = id_cod
            registro.responsable    = responsable
            registro.maquina        = maquina
            registro.fecha_inicia   = fecha_dt
            registro.estado         = nuevo_estado
            registro.departamento   = 'Inyeccion'
            
            # --- BLINDAJE DE DATOS (int(round(float)) para BigInt/Integer) ---
            disparos      = float(item.get('cantidad') or item.get('contador_maq') or 0)
            num_cavidades = int(round(float(item.get('no_cavidades') or item.get('cavidades') or 1)))
            cant_real     = int(round(float(item.get('cantidad_real') or 0)))
            p_bujes       = float(item.get('peso_bujes') or 0)
            
            # Asignación a modelo unificado (int4/bigint)
            registro.cantidad_real = cant_real
            registro.cavidades     = num_cavidades
            registro.molde         = int(round(float(item.get('molde') or 0)))
            
            # Sincronización de Contadores y Métricas Recuperadas (JSON Mapping)
            disparos      = float(item.get('cant_contador') or item.get('disparos') or 0)
            registro.cant_contador      = int(round(disparos)) # Blindaje BigInt
            registro.produccion_teorica = float(item.get('produccion_teorica') or (disparos * num_cavidades))
            registro.peso_bujes         = float(item.get('peso_bujes') or 0)
            registro.peso_lote          = str(round(cant_real * registro.peso_bujes, 4))
            
            # Metadatos y Tiempos (Fix hora_llegada)
            registro.observaciones  = item.get('observaciones') or ''
            registro.hora_llegada   = item.get('hora_llegada') or item.get('horaLlegada') or turno.get('hora_llegada')
            registro.hora_inicio    = item.get('hora_inicio') or turno.get('hora_inicio')
            registro.hora_termina   = item.get('hora_fin') or item.get('hora_termina') or turno.get('hora_fin') or turno.get('hora_termina')
            registro.almacen_destino = item.get('almacen_destino') or turno.get('almacen_destino', 'POR PULIR')
            registro.codigo_ensamble = item.get('codigo_ensamble')
            registro.orden_produccion = item.get('orden_produccion') or turno.get('orden_produccion')
            
            # Sanitización de PNC
            pnc_val = int(round(float(item.get('pnc') or item.get('pnc_total') or 0)))
            registro.pnc_total   = pnc_val
            pnc_det = item.get('criterio_pnc') or item.get('pnc_detalle')
            registro.pnc_detalle = pnc_det if pnc_det else None # NULL en DB
            
            # Pesos y Movimientos
            registro.entrada = str(float(item.get('entrada') or turno.get('entrada_manual') or 0))
            registro.salida  = str(float(item.get('salida') or turno.get('salida_manual') or 0))

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
                    registro.tiempo_total_minutos = round(segundos / 60.0, 2)
                    
                    if cant_real > 0:
                        registro.segundos_por_unidad = int(round(segundos / cant_real))
                    else:
                        registro.segundos_por_unidad = 0
                        
                    registro.fecha_inicia = dt_inicio.replace(tzinfo=None)
                    registro.fecha_fin = dt_fin.replace(tzinfo=None)
                except Exception as e_time:
                    logger.warning(f"Error calculando tiempos inyeccion: {e_time}")

            # Registro de PNC
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
                    # Casteo seguro: cantidad_real puede ser String con decimales
                    cant_for_bom = int(float(str(registro.cantidad_real or 0)))
                    bom_res = calcular_descuentos_ensamble(id_cod, cant_for_bom)
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

        # 4. Procesar PNC Adicionales del Modal de Cierre (NUEVO)
        pnc_list = data.get('pnc_list', [])
        if pnc_list:
            logger.info(f" 🚩 Procesando {len(pnc_list)} PNC adicionales para el lote {id_iny_lote}")
            
            # Limpiar PNC previos vinculados al lote para evitar duplicados en re-validación
            db.session.query(PncInyeccion).filter_by(id_inyeccion=id_iny_lote).delete()
            
            for pnc_data in pnc_list:
                cod_raw = pnc_data.get('codigo', '')
                cod_norm = normalizar_codigo(cod_raw)
                cant_pnc = float(pnc_data.get('cantidad') or 0)
                motivo = pnc_data.get('motivo', 'SIN ESPECIFICAR')
                
                if cant_pnc > 0:
                    nuevo_pnc_row = PncInyeccion(
                        id_pnc_inyeccion=uuid.uuid4().hex[:8],
                        id_inyeccion=id_iny_lote,
                        id_codigo=cod_norm,
                        cantidad=cant_pnc,
                        criterio=motivo,
                        responsable=responsable_lote,
                        maquina=maquina_lote,
                        departamento='Inyeccion'
                    )
                    db.session.add(nuevo_pnc_row)

        db.session.commit()
        logger.info(f" ✅ Lote {id_iny_lote} ({nuevo_estado}) procesado con {len(items)} items.")
        
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
            id_codigo=id_codigo,
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

@inyeccion_bp.route('/api/inyeccion/validar/<id_inyeccion>', methods=['POST'])
@require_role(ROL_ADMINS + ROL_JEFES + ['AUXILIAR INVENTARIO', 'STAFF FRIMETALS', 'CALIDAD'])
def validar_lote_inyeccion(id_inyeccion):
    """
    Endpoint para validación rápida de un lote completo sin pasar por el formulario de Paola.
    """
    try:
        registros = ProduccionInyeccion.query.filter_by(id_inyeccion=id_inyeccion).all()
        if not registros:
            return jsonify({"success": False, "error": "Lote no encontrado"}), 404

        for r in registros:
            if r.estado != 'VALIDADO':
                r.estado = 'VALIDADO'
                # Opcional: Actualizar stock aquí si se requiere validación inmediata
                try:
                    from backend.services.bom_service import calcular_descuentos_ensamble
                    from backend.app import registrar_entrada, registrar_salida
                    # Casteo resiliente para evitar Error 500 si cantidad_real tiene decimales o es String
                    cant_val = int(float(str(r.cantidad_real or 0)))
                    bom_res = calcular_descuentos_ensamble(r.id_codigo, cant_val)
                    if bom_res.get('success'):
                        for comp in bom_res.get('componentes', []):
                            registrar_salida(comp['codigo_inventario'], comp['cantidad_total_descontar'], "STOCK_BODEGA")
                    registrar_entrada(r.id_codigo, (r.cantidad_real or 0) - (r.pnc_total or 0), "POR PULIR")
                except Exception as e_stock:
                    logger.error(f"Error stock en validación rápida {r.id_codigo}: {e_stock}")

        db.session.commit()
        logger.info(f"✅ [Inyeccion] Lote {id_inyeccion} validado correctamente.")
        return jsonify({"success": True, "message": f"Lote {id_inyeccion} validado correctamente"})

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error validando lote {id_inyeccion}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@inyeccion_bp.route('/api/inyeccion/dashboard_stats', methods=['GET'])
@require_role(ROL_ADMINS + ['JEFE INYECCION', 'INYECCION'])
def get_inyeccion_stats():
    # Placeholder
    return jsonify({"success": True, "message": "Estadísticas de inyección (WIP)"})
