import os
import uuid
import logging
import traceback
import pytz
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_JEFES
from backend.models.sql_models import db, ProduccionInyeccion, PncInyeccion, ProgramacionInyeccion, DistribucionOpPedidos, Pedido, TrazabilidadLote
from backend.config.settings import Settings

logger = logging.getLogger(__name__)
inyeccion_bp = Blueprint('inyeccion_bp', __name__)

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
        from backend.utils.formatters import normalizar_codigo, to_float, to_int
        data = request.json
        turno = data.get('turno', {})
        items = data.get('items', [])
        
        if not items:
            return jsonify({'success': False, 'error': 'No hay items para registrar'}), 400

        from backend.utils.formatters import resolver_operario
        responsable = resolver_operario(turno.get('responsable'))
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
        
        movimientos_inventario = []

        for item in items:
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
            if es_validacion:
                registro.validado_por = session.get('user', 'SISTEMA')
            else:
                registro.finalizado_por = session.get('user', 'SISTEMA')
            
            # --- BLINDAJE DE DATOS (int(round(float)) para BigInt/Integer) ---
            disparos      = to_float(item.get('cantidad') or item.get('contador_maq') or 0)
            num_cavidades = to_int(item.get('no_cavidades') or item.get('cavidades') or 1)
            cant_real     = to_int(item.get('cantidad_real') or 0)
            p_bujes       = to_float(item.get('peso_bujes') or 0)
            
            # Asignación a modelo unificado (int4/bigint)
            registro.cantidad_real = cant_real
            registro.cavidades     = num_cavidades
            registro.molde         = to_int(item.get('molde') or 0)
            
            # Sincronización de Contadores y Métricas Recuperadas (JSON Mapping)
            disparos      = to_float(item.get('cant_contador') or item.get('disparos') or 0)
            registro.cant_contador      = to_int(disparos) # Blindaje BigInt
            registro.produccion_teorica = to_float(item.get('produccion_teorica') or (disparos * num_cavidades))
            registro.peso_bujes         = to_float(item.get('peso_bujes') or 0)
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
            pnc_val = to_int(item.get('pnc') or item.get('pnc_total') or 0)
            registro.pnc_total   = pnc_val
            pnc_det = item.get('criterio_pnc') or item.get('pnc_detalle')
            registro.pnc_detalle = normalizar_criterio(pnc_det, "inyeccion") if pnc_det else None # NULL en DB
            
            # Pesos y Movimientos
            registro.entrada = str(to_float(item.get('entrada') or turno.get('entrada_manual') or 0))
            registro.salida  = str(to_float(item.get('salida') or turno.get('salida_manual') or 0))

            # --- Cálculo de Tiempos y Métricas ---
            h_inicio = registro.hora_inicio
            h_fin = registro.hora_termina

            if h_inicio and h_fin:
                try:
                    hi_h, hi_m = h_inicio.split(':')
                    hf_h, hf_m = h_fin.split(':')
                    
                    # Usar la FECHA del formulario (fecha_dt), NO datetime.now()
                    dt_inicio = datetime(fecha_dt.year, fecha_dt.month, fecha_dt.day,
                                         int(hi_h), int(hi_m), 0)
                    dt_fin = datetime(fecha_dt.year, fecha_dt.month, fecha_dt.day,
                                      int(hf_h), int(hf_m), 0)
                    
                    diff = dt_fin - dt_inicio
                    segundos = int(diff.total_seconds())
                    if segundos < 0: segundos += 86400 # Cruce medianoche
                    
                    registro.duracion_segundos = segundos
                    registro.tiempo_total_minutos = round(segundos / 60.0, 2)
                    
                    if cant_real > 0:
                        registro.segundos_por_unidad = int(round(segundos / cant_real))
                    else:
                        registro.segundos_por_unidad = 0
                        
                    registro.fecha_inicia = dt_inicio
                    registro.fecha_fin = dt_fin
                except Exception as e_time:
                    logger.warning(f"Error calculando tiempos inyeccion: {e_time}")

            # Registro de PNC detallado (Desglose Misión 1) - Modificado para el nuevo diseño de columnas
            db.session.query(PncInyeccion).filter_by(id_inyeccion=id_iny, id_codigo=id_cod).delete()
            
            pnc_list_global = data.get('pnc_list', [])
            pnc_items_para_este_codigo = [p for p in pnc_list_global if p.get('codigo') == codigo_raw or normalizar_codigo(p.get('codigo')) == id_cod]
            
            quemado_manchado = 0
            incompleto_falta_llenado = 0
            rebaba_excesiva = 0
            burbuja_porosidad = 0
            deformacion_rechupado = 0

            for p_def in pnc_items_para_este_codigo:
                c_pnc = to_float(p_def.get('cantidad') or 0)
                if c_pnc <= 0:
                    continue
                crit = str(p_def.get('criterio') or 'Otro').lower().strip()
                
                if any(x in crit for x in ["quemado", "mancha", "contaminado"]):
                    quemado_manchado += c_pnc
                elif any(x in crit for x in ["incompleto", "escaso", "falta", "llenado"]):
                    incompleto_falta_llenado += c_pnc
                elif "rebaba" in crit:
                    rebaba_excesiva += c_pnc
                elif any(x in crit for x in ["burbuja", "porosidad"]):
                    burbuja_porosidad += c_pnc
                elif any(x in crit for x in ["deform", "rechupe", "chupado", "hundido", "flujo"]):
                    deformacion_rechupado += c_pnc
                else:
                    deformacion_rechupado += c_pnc

            total_pnc_detallado = quemado_manchado + incompleto_falta_llenado + rebaba_excesiva + burbuja_porosidad + deformacion_rechupado
            
            if total_pnc_detallado > 0:
                nuevo_pnc = PncInyeccion(
                    id_pnc_inyeccion=uuid.uuid4().hex[:8],
                    id_inyeccion=id_iny,
                    id_codigo=id_cod,
                    cantidad=total_pnc_detallado,
                    criterio=f"Quemado: {int(quemado_manchado)}, Falta Llenado: {int(incompleto_falta_llenado)}, Rebaba: {int(rebaba_excesiva)}, Burbujas: {int(burbuja_porosidad)}, Deformacion: {int(deformacion_rechupado)}",
                    codigo_ensamble=registro.codigo_ensamble,
                    quemado_manchado=quemado_manchado,
                    incompleto_falta_llenado=incompleto_falta_llenado,
                    rebaba_excesiva=rebaba_excesiva,
                    burbuja_porosidad=burbuja_porosidad,
                    deformacion_rechupado=deformacion_rechupado
                )
                db.session.add(nuevo_pnc)
                registro.pnc_total = int(round(total_pnc_detallado))
                registro.pnc_detalle = nuevo_pnc.criterio
            elif pnc_val > 0:
                # Fallback por si usan el formulario viejo
                nuevo_pnc = PncInyeccion(
                    id_pnc_inyeccion=uuid.uuid4().hex[:8],
                    id_inyeccion=id_iny,
                    id_codigo=id_cod,
                    cantidad=float(pnc_val),
                    criterio=registro.pnc_detalle or 'Otro',
                    codigo_ensamble=registro.codigo_ensamble,
                    deformacion_rechupado=float(pnc_val)
                )
                db.session.add(nuevo_pnc)

            # --- PASO 2: Actualizar Stock (Sólo si es validación) ---
            if es_validacion:
                try:
                    # Encontrar o crear el lote de trazabilidad
                    lote_traz = db.session.query(TrazabilidadLote).filter_by(
                        id_inyeccion=id_iny,
                        id_codigo=id_cod
                    ).first()
                    
                    if lote_traz:
                        # Si existe, actualizamos su cantidad inyectada
                        lote_traz.cantidad_inyectada = cant_real
                        lote_traz.por_pulir = cant_real
                    else:
                        # Si no existe (registro manual en validación), lo creamos
                        fecha_ref = registro.fecha_inicia or datetime.now()
                        maquina_clean = str(registro.maquina or 'MAQ').replace(' ', '')
                        op_clean = str(registro.orden_produccion or 'SIN_OP').replace(' ', '')
                        id_lote_key = f"{fecha_ref.strftime('%Y%m%d')}-{maquina_clean}-{op_clean}-{id_cod}"
                        lote_traz = TrazabilidadLote(
                            id_lote=id_lote_key,
                            orden_produccion=registro.orden_produccion,
                            id_codigo=id_cod,
                            maquina=registro.maquina,
                            id_inyeccion=id_iny,
                            estado_actual='PENDIENTE_VALIDACION',
                            fecha_creacion=fecha_ref,
                            responsable=registro.responsable or 'Paola',
                            cantidad_inyectada=cant_real,
                            por_pulir=cant_real
                        )
                        db.session.add(lote_traz)
                        db.session.flush()

                    # Consultar todos los reportes de pulido para este lote específico
                    from backend.models.sql_models import ProduccionPulido
                    pulidos = db.session.query(ProduccionPulido).filter_by(lote=lote_traz.id_lote).all()
                    pulido_buenos = sum(p.cantidad_real for p in pulidos if p.cantidad_real)
                    pnc_pulido = sum(p.pnc_pulido for p in pulidos if p.pnc_pulido)

                    # Cruce aritmético del WIP
                    sobrante = max(0, cant_real - (pulido_buenos + pnc_pulido))

                    # Descontar materia prima según el BOM
                    from backend.services.bom_service import calcular_descuentos_ensamble
                    bom_res = calcular_descuentos_ensamble(id_cod, cant_real)
                    if bom_res.get('success'):
                        for comp in bom_res.get('componentes', []):
                            mov = registrar_salida(comp['codigo_inventario'], comp['cantidad_total_descontar'], "STOCK_BODEGA")
                            if mov and "error" not in mov:
                                movimientos_inventario.append(mov)

                    # Actualizar inventario final (Validation is single point of entry)
                    if pulido_buenos > 0:
                        mov_ent = registrar_entrada(id_cod, pulido_buenos, "P. TERMINADO")
                        if mov_ent and "error" not in mov_ent:
                            movimientos_inventario.append(mov_ent)
                    if sobrante > 0:
                        mov_ent_sobrante = registrar_entrada(id_cod, sobrante, "POR PULIR")
                        if mov_ent_sobrante and "error" not in mov_ent_sobrante:
                            movimientos_inventario.append(mov_ent_sobrante)

                    # Actualizar estado de la trazabilidad
                    lote_traz.estado_actual = 'APROBADO_CERRADO'

                except Exception as e_stock:
                    logger.error(f"Error stock en validación form {id_cod}: {e_stock}")

                # --- Lógica de Cubetas de Contingencia Express para Validación Manual ---
                op_actual = registro.orden_produccion
                if op_actual and str(op_actual).strip() != 'SIN OP':
                    try:
                        from backend.models.sql_models import DistribucionOpPedidos
                        
                        op_limpia = str(op_actual or '').strip()
                        from backend.utils.formatters import normalizar_codigo
                        codigo_limpio = normalizar_codigo(id_cod)
                        
                        # Buscar las cubetas por OP y Referencia
                        cubetas = db.session.query(DistribucionOpPedidos).filter(
                            DistribucionOpPedidos.op_world_office == op_limpia,
                            DistribucionOpPedidos.codigo_producto == codigo_limpio
                        ).order_by(DistribucionOpPedidos.id_distribucion.asc()).all()

                        piezas_por_repartir = float(registro.cantidad_real or 0)
                        
                        # Validación y creación de cubeta de contingencia
                        if not cubetas and piezas_por_repartir > 0:
                            # Intentar buscar el id_pedido de otra cubeta asociada a la misma OP
                            pedido_asoc = db.session.query(DistribucionOpPedidos.id_pedido).filter(
                                DistribucionOpPedidos.op_world_office == op_limpia
                            ).first()
                            id_pedido_final = pedido_asoc[0] if (pedido_asoc and pedido_asoc[0]) else f"PED-IMPREVISTO-{op_limpia}"
                            
                            logger.info(f" ⚠️ [INYECCION-CONTINGENCIA-MANUAL] Creando cubeta temporal para OP: {op_limpia}, Producto: {codigo_limpio}, Pedido: {id_pedido_final}")
                            nueva_cubeta = DistribucionOpPedidos(
                                op_world_office=op_limpia,
                                id_pedido=id_pedido_final,
                                codigo_producto=codigo_limpio,
                                cant_requerida=piezas_por_repartir,
                                cant_inyectada=piezas_por_repartir,
                                cant_pulida=0,
                                cant_ensamblada=0,
                                cant_alistada=0
                            )
                            db.session.add(nueva_cubeta)
                            db.session.flush() # Sincronizar temporalmente en sesión
                            cubetas = [nueva_cubeta]
                            piezas_por_repartir = 0.0 # Consumido por completo
                        
                        logger.info(f" 📦 [INYECCION-FIFO-MANUAL] Propagando {piezas_por_repartir} piezas a {len(cubetas)} cubetas. OP: {op_limpia}, Producto: {codigo_limpio}")

                        for cubeta in cubetas:
                            if piezas_por_repartir <= 0:
                                break
                            
                            falta = max(0, (cubeta.cant_requerida or 0) - (cubeta.cant_inyectada or 0))
                            if falta > 0:
                                if piezas_por_repartir >= falta:
                                    cubeta.cant_inyectada = (cubeta.cant_inyectada or 0) + falta
                                    piezas_por_repartir -= falta
                                else:
                                    cubeta.cant_inyectada = (cubeta.cant_inyectada or 0) + piezas_por_repartir
                                    piezas_por_repartir = 0
                    except Exception as e_dist:
                        logger.error(f"Error en distribucion FIFO manual {id_cod}: {e_dist}")

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
                cant_pnc = to_float(pnc_data.get('cantidad') or 0)
                motivo = pnc_data.get('criterio') or pnc_data.get('motivo') or 'Otros'
                motivo_norm = normalizar_criterio(motivo, "inyeccion")
                
                if cant_pnc > 0:
                    nuevo_pnc_row = PncInyeccion(
                        id_pnc_inyeccion=uuid.uuid4().hex[:8],
                        id_inyeccion=id_iny_lote,
                        id_codigo=cod_norm,
                        cantidad=cant_pnc,
                        criterio=motivo_norm
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
            'pdf_status': "success" if pdf_ok else "failed",
            'movimientos_inventario': movimientos_inventario
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

        from backend.utils.formatters import resolver_operario
        responsable = resolver_operario(data.get('responsable'))
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

        # Validar Máquina Ocupada (Permitir Modo Overlap para pruebas - DESACTIVADO PARA PRODUCCIÓN)
        # es_prueba = '9999' in str(id_inyeccion) or 'PRUEBA' in str(id_inyeccion).upper() or '9999' in str(data.get('orden_produccion', '')) or 'PRUEBA' in str(data.get('orden_produccion', '')).upper()
        # 
        # if not es_prueba:
        #     maquina_ocupada = db.session.query(ProduccionInyeccion).filter(
        #         ProduccionInyeccion.maquina == maquina,
        #         ProduccionInyeccion.estado.in_(['ABIERTO', 'EN_PROCESO'])
        #     ).first()
        #     if maquina_ocupada:
        #         return jsonify({
        #             "success": False, 
        #             "error": f"Máquina Ocupada: La máquina {maquina} ya tiene una orden activa. Finalice la orden actual antes de iniciar una nueva."
        #         }), 400
        # else:
        #     logger.info(f"🧪 [SANDBOX] Permitiendo Modo Overlap para lote de prueba {id_inyeccion} en máquina {maquina}.")

        # Lógica estándar de producción estricta:
        maquina_ocupada = db.session.query(ProduccionInyeccion).filter(
            ProduccionInyeccion.maquina == maquina,
            ProduccionInyeccion.estado.in_(['ABIERTO', 'EN_PROCESO'])
        ).first()
        
        if maquina_ocupada:
            return jsonify({
                "success": False, 
                "error": f"Máquina Ocupada: La máquina {maquina} ya tiene una orden activa. Finalice la orden actual antes de iniciar una nueva."
            }), 400

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
            estado='ABIERTO',
            departamento='Inyeccion',
            molde=data.get('molde') or 0,
            cavidades=data.get('cavidades') or 1,
            almacen_destino=data.get('almacen_destino') or 'PRODUCCION',
            cantidad_real=0
        )
        db.session.add(registro)

        # --- MES PASO 1: Crear Lote de Trazabilidad (Cabecera) ---
        # id_lote con formato YYYYMMDD-Maquina-OP-idCodigo para evitar colisión PK
        op_clean = str(data.get('orden_produccion') or 'SIN_OP').replace(' ', '')
        id_lote_key = f"{fecha_dt.strftime('%Y%m%d')}-{maquina.replace(' ', '')}-{op_clean}-{id_codigo}"
        if not db.session.get(TrazabilidadLote, id_lote_key):
            lote_traz = TrazabilidadLote(
                id_lote=id_lote_key,
                orden_produccion=data.get('orden_produccion'),
                id_codigo=id_codigo,
                maquina=maquina,
                id_inyeccion=id_inyeccion,
                estado_actual='ABIERTO_PRODUCCION',
                fecha_creacion=ahora.replace(tzinfo=None),
                responsable=responsable,
                cantidad_inyectada=0,
                por_pulir=0
            )
            db.session.add(lote_traz)
            logger.info(f"🟢 [Trazabilidad] Lote creado: {id_lote_key} | Estado: ABIERTO_PRODUCCION")

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
    Endpoint para validación rápida de un lote completo.
    Calcula el cruce aritmético del WIP y actualiza el inventario de forma atómica.
    """
    try:
        from backend.models.sql_models import TrazabilidadLote, ProduccionPulido, ProduccionInyeccion
        from backend.app import registrar_entrada, registrar_salida
        from backend.services.bom_service import calcular_descuentos_ensamble

        payload = request.get_json(silent=True) or {}
        items_payload = payload.get('items', [])
        items_dict = { str(item.get('codigo', '')): item for item in items_payload }

        lotes_traz = TrazabilidadLote.query.filter_by(id_inyeccion=id_inyeccion).all()
        if not lotes_traz:
            # Intentar por id_lote directamente
            single_lote = TrazabilidadLote.query.get(id_inyeccion)
            if single_lote:
                lotes_traz = [single_lote]

        if not lotes_traz:
            return jsonify({"success": False, "error": "Lote no encontrado en trazabilidad"}), 404

        for lote_traz in lotes_traz:
            if lote_traz.estado_actual == 'APROBADO_CERRADO':
                continue

            codigo = str(lote_traz.id_codigo)
            cantidad_inyectada = lote_traz.cantidad_inyectada or 0

            # Consultar todos los reportes de pulido para este lote específico
            pulidos = ProduccionPulido.query.filter_by(lote=lote_traz.id_lote).all()
            pulido_buenos = sum(p.cantidad_real for p in pulidos if p.cantidad_real)
            
            # Sobreescritura oficial desde el Payload de Validación
            pnc_inyeccion = 0
            pnc_pulido = 0
            if codigo in items_dict:
                pnc_inyeccion = float(items_dict[codigo].get('pnc_inyeccion', 0))
                pnc_pulido = float(items_dict[codigo].get('pnc_pulido', 0))

            from backend.models.sql_models import PncInyeccion, PncPulido
            import uuid

            # Eliminar registros PNC anteriores creados en validaciones previas para este lote/código
            db.session.query(PncInyeccion).filter_by(id_inyeccion=lote_traz.id_inyeccion, id_codigo=codigo).delete()
            db.session.query(PncPulido).filter_by(codigo=codigo, codigo_ensamble='AUDITORIA PULIDO').filter(PncPulido.id_pulido.like(f"VAL-{lote_traz.id_lote}%")).delete()

            if pnc_inyeccion > 0:
                db.session.add(PncInyeccion(
                    id_pnc_inyeccion=uuid.uuid4().hex[:8],
                    id_inyeccion=lote_traz.id_inyeccion,
                    id_codigo=codigo,
                    cantidad=int(pnc_inyeccion),
                    criterio='PNC Reportado en Validación',
                    codigo_ensamble='AUDITORIA INYECCION'
                ))

            if pnc_pulido > 0:
                db.session.add(PncPulido(
                    id_pnc_pulido=uuid.uuid4().hex[:8],
                    id_pulido=f"VAL-{lote_traz.id_lote}",
                    codigo=codigo,
                    cantidad=int(pnc_pulido),
                    criterio='PNC Pulido en Validación',
                    codigo_ensamble='AUDITORIA PULIDO'
                ))

            # Cruce aritmético del WIP: se resta lo bueno y TODO el PNC oficial reportado en validación
            sobrante = max(0, cantidad_inyectada - (pulido_buenos + pnc_inyeccion + pnc_pulido))

            es_prueba = '9999' in str(lote_traz.id_lote) or 'PRUEBA' in str(lote_traz.id_lote).upper() or '9999' in str(lote_traz.orden_produccion) or 'PRUEBA' in str(lote_traz.orden_produccion).upper()

            if not es_prueba:
                # Descontar materia prima según el BOM
                if cantidad_inyectada > 0:
                    bom_res = calcular_descuentos_ensamble(codigo, cantidad_inyectada)
                    if bom_res.get('success'):
                        for comp in bom_res.get('componentes', []):
                            registrar_salida(comp['codigo_inventario'], comp['cantidad_total_descontar'], "STOCK_BODEGA")

                # Actualizar inventario final (Validation is single point of entry)
                if pulido_buenos > 0:
                    registrar_entrada(codigo, pulido_buenos, "P. TERMINADO")
                if sobrante > 0:
                    registrar_entrada(codigo, sobrante, "POR PULIR")
            else:
                logger.info(f"🧪 [SANDBOX] Lote {lote_traz.id_lote} validado en MODO PRUEBA. Se ignoró cruce de inventario.")

            # Actualizar estados
            lote_traz.estado_actual = 'APROBADO_CERRADO'

            # Marcar registros de inyeccion asociados como CERRADOS
            registros_iny = ProduccionInyeccion.query.filter_by(
                id_inyeccion=lote_traz.id_inyeccion,
                id_codigo=codigo
            ).all()
            for r in registros_iny:
                r.estado = 'CERRADO'
                from datetime import datetime
                r.fecha_fin = datetime.now()
                r.cantidad_real = pulido_buenos
                r.cant_contador = pulido_buenos + pnc_inyeccion + pnc_pulido
                r.pnc_total = pnc_inyeccion

        db.session.commit()
        # Invalidar caché del MES
        try:
            from backend.app import clear_mes_cache
            clear_mes_cache()
        except:
            pass

        logger.info(f"✅ [Validación] Lote {id_inyeccion} cerrado y validado correctamente.")
        return jsonify({"success": True, "message": f"Lote {id_inyeccion} validado e inventario actualizado"})

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error validando lote {id_inyeccion}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@inyeccion_bp.route('/api/inyeccion/dashboard_stats', methods=['GET'])
@require_role(ROL_ADMINS + ['JEFE INYECCION', 'INYECCION'])
def get_inyeccion_stats():
    # Placeholder
    return jsonify({"success": True, "message": "Estadísticas de inyección (WIP)"})


@inyeccion_bp.route('/api/programacion/guardar', methods=['POST'])
def guardar_programacion_diaria():
    """
    Registra la planificación del turno de la tarde anterior en db_programacion
    y crea su distribución asociada de cubetas por pedido en db_distribucion_op_pedidos
    dejando op_world_office como NULL.
    Soporta múltiples productos en el mismo montaje de forma atómica.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400

        # --- Extracción y Validación de campos principales ---
        maquina = data.get('maquina')
        fecha_str = data.get('fecha')
        
        if not all([maquina, fecha_str]):
            return jsonify({"success": False, "error": "Los campos maquina y fecha son obligatorios"}), 400

        # Parsear fecha de forma robusta
        try:
            fecha_dt = datetime.strptime(fecha_str.split('T')[0], '%Y-%m-%d').date()
        except Exception as e_date:
            logger.error(f"Error parseando fecha '{fecha_str}': {e_date}")
            return jsonify({"success": False, "error": "Formato de fecha inválido. Usar YYYY-MM-DD"}), 400

        # Extraer parámetros comunes
        responsable_planta = data.get('responsable_planta')
        observaciones = data.get('observaciones')
        pedidos_asignados = data.get('pedidos_asignados', [])

        # Parsear molde
        try:
            molde_val = int(float(data.get('molde'))) if data.get('molde') is not None else None
        except (ValueError, TypeError) as e_molde:
            return jsonify({"success": False, "error": f"Error en formato de molde: {str(e_molde)}"}), 400

        # Obtener lista de productos (Multi-SKU) o construir fallback para flujo singular
        productos = data.get('productos')
        if not productos:
            codigo_sistema = data.get('codigo_sistema')
            if not codigo_sistema:
                return jsonify({"success": False, "error": "Debes especificar al menos un producto (codigo_sistema o productos)"}), 400
            
            try:
                cavidades_val = int(float(data.get('cavidades'))) if data.get('cavidades') is not None else 1
                cantidad_val = float(data.get('cantidad') or 0)
            except (ValueError, TypeError) as e_num:
                return jsonify({"success": False, "error": f"Error en formato de cavidades/cantidad: {str(e_num)}"}), 400

            productos = [{
                "codigo_sistema": codigo_sistema,
                "cavidades": cavidades_val,
                "cantidad": cantidad_val
            }]

        # --- Iniciar Transacción Atómica ---
        programaciones_creadas = []
        for prod_data in productos:
            cod_sistema = prod_data.get('codigo_sistema')
            if not cod_sistema:
                raise ValueError("Cada producto del montaje debe especificar 'codigo_sistema'")

            try:
                cav_val = int(float(prod_data.get('cavidades') or 1))
                cant_val = float(prod_data.get('cantidad') or 0)
            except (ValueError, TypeError) as e_num:
                raise ValueError(f"Error en campos numéricos para producto {cod_sistema}: {e_num}")

            nueva_prog = ProgramacionInyeccion(
                fecha=fecha_dt,
                codigo_sistema=cod_sistema,
                maquina=maquina,
                cantidad=cant_val,
                estado='PROGRAMADO',
                molde=molde_val,
                cavidades=cav_val,
                responsable_planta=responsable_planta,
                observaciones=observaciones,
                op_world_office=None  # Aún no se conoce la OP la tarde anterior
            )
            db.session.add(nueva_prog)
            programaciones_creadas.append(nueva_prog)

        # Insertar registros correspondientes en db_distribucion_op_pedidos
        for pedido in pedidos_asignados:
            id_pedido = pedido.get('id_pedido')
            cant_req = pedido.get('cant_requerida')
            # Si no viene codigo_producto en la cubeta, se asocia al primer producto programado
            cod_prod_cubeta = pedido.get('codigo_producto') or productos[0].get('codigo_sistema')

            if not id_pedido or cant_req is None:
                raise ValueError("Cada pedido asignado debe incluir 'id_pedido' y 'cant_requerida'")

            try:
                cant_req_val = int(float(cant_req))
            except (ValueError, TypeError):
                raise ValueError(f"Cantidad requerida inválida para el pedido {id_pedido}")

            nueva_dist = DistribucionOpPedidos(
                op_world_office=None,  # Nullable para ser actualizado en la mañana
                id_pedido=id_pedido,
                codigo_producto=cod_prod_cubeta,
                cant_requerida=cant_req_val,
                cant_inyectada=0,
                cant_pulida=0,
                cant_ensamblada=0,
                cant_alistada=0
            )
            db.session.add(nueva_dist)

        # Guardar en base de datos de manera atómica
        db.session.commit()

        logger.info(f"✅ {len(programaciones_creadas)} Programación(es) creada(s) exitosamente. Pedidos distribuidos: {len(pedidos_asignados)}")
        return jsonify({
            "success": True,
            "message": f"Programación diaria ({len(programaciones_creadas)} referencias) y cubetas creadas correctamente",
            "id_programacion": programaciones_creadas[0].id if programaciones_creadas else None
        }), 201

    except ValueError as val_err:
        db.session.rollback()
        logger.warning(f"⚠️ Error de validación en guardar_programacion_diaria: {val_err}")
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error crítico en guardar_programacion_diaria: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error interno del servidor al guardar la programación"}), 500


@inyeccion_bp.route('/api/pedidos/pendientes/<codigo>', methods=['GET'])
def obtener_pedidos_pendientes(codigo):
    """
    Obtiene el listado de pedidos abiertos (PENDIENTE, ABIERTO, etc.) o con
    cantidades pendientes de despacho para un código de producto específico.
    """
    try:
        if not codigo:
            return jsonify({"success": False, "error": "Código de producto es requerido"}), 400

        # Consultar pedidos usando coincidencia por contenedor ilike
        pedidos_activos = db.session.query(Pedido).filter(
            Pedido.id_codigo.ilike(f"%{codigo}%"),
            Pedido.estado.in_(['PENDIENTE', 'ABIERTO', 'Alistamiento', 'ALISTADO'])
        ).all()

        resultados = []
        for p in pedidos_activos:
            try:
                cant_solicitada = float(p.cantidad or 0)
                cant_alistada = float(p.cant_alistada or 0)
            except (ValueError, TypeError):
                cant_solicitada = 0.0
                cant_alistada = 0.0

            cant_pendiente = max(0.0, cant_solicitada - cant_alistada)

            # Incluir el pedido si tiene saldo pendiente o si su estado es abierto
            if cant_pendiente > 0 or p.estado in ['PENDIENTE', 'ABIERTO']:
                resultados.append({
                    "id_pedido": p.id_pedido,
                    "cliente": p.cliente or "CLIENTE GENERAL",
                    "cantidad_solicitada": int(cant_solicitada),
                    "cantidad_pendiente": int(cant_pendiente)
                })

        # Evitar duplicados agrupando por ID de pedido (Consolidación Real)
        pedidos_unicos = {}
        for res in resultados:
            id_ped = res["id_pedido"]
            if id_ped not in pedidos_unicos:
                pedidos_unicos[id_ped] = res
            else:
                # Sumamos cantidades en caso de duplicidad física en BD
                pedidos_unicos[id_ped]["cantidad_solicitada"] += res["cantidad_solicitada"]
                pedidos_unicos[id_ped]["cantidad_pendiente"] += res["cantidad_pendiente"]

        return jsonify({
            "success": True,
            "pedidos": list(pedidos_unicos.values())
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en obtener_pedidos_pendientes para el código {codigo}: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error interno del servidor al consultar pedidos"}), 500


@inyeccion_bp.route('/api/produccion/verificar_demanda/<codigo>', methods=['GET'])
def verificar_demanda_b2b(codigo):
    """
    Agrega las unidades de pedidos B2B pendientes contra el stock actual en bodega.
    Suma las cantidades directamente para evitar falsas duplicaciones.
    """
    try:
        if not codigo:
            return jsonify({"success": False, "error": "El código es requerido"}), 400

        from backend.models.sql_models import Pedido, Producto

        # 1. Consultar pedidos con normalización flexible ILIKE
        pedidos_activos = db.session.query(Pedido).filter(
            Pedido.id_codigo.ilike(f"%{codigo}%"),
            Pedido.estado.in_(['PENDIENTE', 'ABIERTO', 'Alistamiento', 'ALISTADO', 'EXPORTADO_WO'])
        ).all()

        unidades_pedidas_b2b = 0.0
        for p in pedidos_activos:
            try:
                cant_solicitada = float(p.cantidad or 0)
                cant_alistada = float(p.cant_alistada or 0)
            except (ValueError, TypeError):
                cant_solicitada = 0.0
                cant_alistada = 0.0

            cant_pendiente = max(0.0, cant_solicitada - cant_alistada)
            unidades_pedidas_b2b += cant_pendiente

        # 2. Consultar el stock actual en bodega del producto
        prod = db.session.query(Producto).filter(
            (Producto.codigo_sistema.ilike(f"%{codigo}%")) |
            (Producto.id_codigo.ilike(f"%{codigo}%"))
        ).first()

        stock_terminado = 0.0
        stock_bodega = 0.0

        if prod:
            stock_terminado = float(prod.p_terminado or 0)
            stock_bodega = float(prod.stock_bodega or 0)

        stock_actual_disponible = stock_terminado + stock_bodega

        # --- AUDITORÍA DE DEMANDA ---
        print(f"--- AUDITORÍA DE DEMANDA PARA: {codigo} ---")
        print(f"Unidades calculadas B2B: {unidades_pedidas_b2b}")
        print(f"Stock Disponible: {stock_actual_disponible}")

        return jsonify({
            "success": True,
            "codigo": codigo,
            "unidades_pedidas_b2b": int(round(unidades_pedidas_b2b)),
            "stock_actual_disponible": int(round(stock_actual_disponible)),
            "stock_terminado": int(round(stock_terminado)),
            "stock_bodega": int(round(stock_bodega))
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en verificar_demanda para {codigo}: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error interno al verificar la demanda"}), 500



@inyeccion_bp.route('/api/mes/iniciar_trabajo', methods=['POST'])
def mes_iniciar_trabajo():
    """
    Fase 4: Inicia el trabajo en la máquina a partir de una programación vespertina.
    Registra la OP de World Office, actualiza estado a EN_PROCESO para la
    referencia programada seleccionada,
    propaga la OP a las cubetas de pedidos y crea el lote de inyección correspondiente.
    """
    try:
        data = request.get_json()
        id_prog = data.get('id_programacion')
        op_world_office = data.get('op_world_office')

        if not id_prog or not op_world_office:
            return jsonify({"success": False, "error": "Los campos id_programacion y op_world_office son obligatorios"}), 400

        # Normalizar OP
        op_world_office = str(op_world_office).strip().upper()

        # 1. Buscar la programación vespertina de referencia en db_programacion
        prog_inicial = db.session.query(ProgramacionInyeccion).get(id_prog)
        if not prog_inicial:
            return jsonify({"success": False, "error": "Programación no encontrada"}), 404

        # 2. Agrupar el bloque entero (Montaje)
        programaciones_bloque = db.session.query(ProgramacionInyeccion).filter(
            ProgramacionInyeccion.maquina == prog_inicial.maquina,
            ProgramacionInyeccion.fecha == prog_inicial.fecha,
            ProgramacionInyeccion.estado == 'PROGRAMADO',
            ProgramacionInyeccion.molde == prog_inicial.molde
        ).all()
        
        if prog_inicial not in programaciones_bloque:
            programaciones_bloque.append(prog_inicial)

        # 3. Generar un lote ID_INYECCION compartido para el lote físico del montaje
        id_inyeccion_bloque = f"INY-{uuid.uuid4().hex[:8].upper()}"
        colombia_tz = pytz.timezone('America/Bogota')
        ahora = datetime.now(colombia_tz).replace(tzinfo=None)

        logger.info(f"⚡ Iniciando trabajo para la máquina {prog_inicial.maquina}, Referencias: {len(programaciones_bloque)}")
        
        from backend.utils.formatters import resolver_operario
        operario_inicia = resolver_operario(data.get('responsable') or data.get('operario') or prog_inicial.responsable_planta)

        # 4. Procesar en bloque de forma atómica
        for prog in programaciones_bloque:
            # Actualizar estado de la programación diaria
            prog.estado = 'EN_PROCESO'
            prog.op_world_office = op_world_office

            # Propagar la OP a las cubetas de pedidos correspondientes
            db.session.query(DistribucionOpPedidos).filter(
                DistribucionOpPedidos.codigo_producto == prog.codigo_sistema,
                DistribucionOpPedidos.op_world_office.is_(None)
            ).update({DistribucionOpPedidos.op_world_office: op_world_office}, synchronize_session=False)

            # Crear lote en ProduccionInyeccion (db_inyeccion)
            hora_inicio_str = ahora.strftime('%H:%M')
            nueva_prod = ProduccionInyeccion(
                id_inyeccion=id_inyeccion_bloque,
                fecha_inicia=ahora,
                id_codigo=prog.codigo_sistema,
                responsable=operario_inicia,
                maquina=prog.maquina,
                molde=prog.molde,
                cavidades=prog.cavidades,
                estado='EN_PROCESO',
                orden_produccion=op_world_office,
                observaciones=prog.observaciones,
                programado_por=prog.responsable_planta,
                iniciado_por=operario_inicia,
                hora_inicio=hora_inicio_str,
                cantidad_real=0,
                cant_contador=0,
                almacen_destino='POR PULIR',
                departamento='Inyeccion'
            )
            db.session.add(nueva_prod)

            # --- MES PASO 1: Crear Lote de Trazabilidad por cada referencia del montaje ---
            id_lote_mes = f"{prog.fecha.strftime('%Y%m%d')}-{prog.maquina.replace(' ', '')}-{op_world_office}-{prog.codigo_sistema}"
            if not db.session.get(TrazabilidadLote, id_lote_mes):
                lote_traz = TrazabilidadLote(
                    id_lote=id_lote_mes,
                    orden_produccion=op_world_office,
                    id_codigo=prog.codigo_sistema,
                    maquina=prog.maquina,
                    id_inyeccion=id_inyeccion_bloque,
                    estado_actual='ABIERTO_PRODUCCION',
                    fecha_creacion=ahora,
                    responsable=prog.responsable_planta or "Supervisor",
                    cantidad_inyectada=0,
                    por_pulir=0
                )
                db.session.add(lote_traz)
                logger.info(f"🟢 [Trazabilidad] Lote MES creado: {id_lote_mes} | OP: {op_world_office} | Ref: {prog.codigo_sistema}")

        db.session.commit()
        
        # Opcional: Invalidar el cache del MES
        try:
            from backend.app import clear_mes_cache
            clear_mes_cache()
        except:
            pass

        logger.info(f"🚀 Trabajo iniciado en bloque en {prog_inicial.maquina}. OP: {op_world_office}. Lote único: {id_inyeccion_bloque}")

        return jsonify({
            "success": True,
            "message": f"Trabajo iniciado con éxito en la {prog_inicial.maquina} para {len(programaciones_bloque)} referencias del montaje.",
            "id_inyeccion": id_inyeccion_bloque
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al iniciar trabajo en el MES: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error interno al iniciar el trabajo"}), 500


@inyeccion_bp.route('/api/mes/reportar', methods=['POST'])
def mes_reportar():
    """
    Fase 4: Finalización de Turno y Reporte de Inyección (Lógica de Cubetas FIFO).
    Procesa el cierre a partir de los cierres (contador físico) y las cubetas de pedidos
    para la OP asociada de forma transaccional y limpia.
    """
    try:
        data = request.get_json() or {}
        id_iny = data.get('id_inyeccion')
        cierres = int(data.get('cierres', 0))
        hf_str = data.get('hora_fin')
        hi_str = data.get('hora_inicio')

        if not id_iny:
            return jsonify({"success": False, "error": "El campo id_inyeccion es obligatorio"}), 400

        from backend.utils.formatters import resolver_operario
        operario_final = resolver_operario(data.get('responsable') or data.get('operario'))

        # 1. Buscar registros en db_inyeccion asociados to este id_inyeccion
        prods_en_lote = db.session.query(ProduccionInyeccion).filter(
            ProduccionInyeccion.id_inyeccion == id_iny
        ).all()
        
        if not prods_en_lote:
            return jsonify({"success": False, "error": "Lote de producción no encontrado"}), 404

        # 2. Procesar cada producto en el lote físicamente
        colombia_tz_rep = pytz.timezone('America/Bogota')
        ahora_rep = datetime.now(colombia_tz_rep).replace(tzinfo=None)
        total_teorica = 0

        for prod in prods_en_lote:
            cavidades = prod.cavidades or 1
            piezas_inyectadas = cierres * cavidades
            total_teorica += piezas_inyectadas

            # Guardar el operario final
            if operario_final:
                prod.responsable = operario_final

            # ── Hora inicio y fin: primero la del frontend (si viene), sino timestamp del servidor ──
            if hi_str:
                prod.hora_inicio = hi_str
            
            hora_fin_resuelta = hf_str or ahora_rep.strftime('%H:%M')
            prod.hora_termina = hora_fin_resuelta

            # Sincronizar fechas con los valores ingresados (o servidor)
            fecha_base = prod.fecha_inicia or ahora_rep
            try:
                # Ajustar inicio si el operario lo editó en el popup
                if hi_str:
                    h_i, m_i = map(int, hi_str.split(':'))
                    fecha_base = fecha_base.replace(hour=h_i, minute=m_i, second=0, microsecond=0)
                    prod.fecha_inicia = fecha_base
                    
                h_f, m_f = map(int, hora_fin_resuelta.split(':'))
                prod.fecha_fin = fecha_base.replace(hour=h_f, minute=m_f, second=0, microsecond=0)


                # Calcular duración y métricas
                delta = prod.fecha_fin - fecha_base
                prod.duracion_segundos = max(0, int(delta.total_seconds()))
                prod.tiempo_total_minutos = round(prod.duracion_segundos / 60.0, 2)
                if piezas_inyectadas > 0:
                    prod.segundos_por_unidad = int(round(prod.duracion_segundos / piezas_inyectadas))
                else:
                    prod.segundos_por_unidad = 0
            except Exception as ex:
                logger.warning(f"⚠️ Error al calcular tiempos en reportar: {ex}")
                prod.fecha_fin = ahora_rep

            # Guardar la cantidad producida y actualizar estado a PENDIENTE
            prod.cantidad_real = piezas_inyectadas
            prod.cant_contador = piezas_inyectadas
            prod.produccion_teorica = piezas_inyectadas
            prod.estado = 'PENDIENTE'

            # ── MES PASO 2: Actualizar cantidad_inyectada en TODOS los lotes de trazabilidad
            # (un montaje multi-referencia genera un lote por referencia, no solo el primero)
            lotes_cierre = db.session.query(TrazabilidadLote).filter_by(
                id_inyeccion=id_iny,
                id_codigo=prod.id_codigo
            ).all()
            if lotes_cierre:
                for lote_cierre in lotes_cierre:
                    lote_cierre.cantidad_inyectada = piezas_inyectadas
                    lote_cierre.por_pulir = piezas_inyectadas
                    logger.info(f"🔄 [Trazabilidad] Lote {lote_cierre.id_lote} ({prod.id_codigo}) → {piezas_inyectadas} piezas | por_pulir: {piezas_inyectadas}")
            else:
                # Fallback: buscar cualquier lote vinculado al id_inyeccion
                lote_generico = db.session.query(TrazabilidadLote).filter_by(id_inyeccion=id_iny).first()
                if lote_generico:
                    lote_generico.cantidad_inyectada = piezas_inyectadas
                    lote_generico.por_pulir = piezas_inyectadas
                    logger.warning(f"⚠️ [Trazabilidad] Fallback – lote {lote_generico.id_lote} actualizado con {piezas_inyectadas} piezas (por_pulir: {piezas_inyectadas})")

            # 3. Lógica FIFO para cubetas (db_distribucion_op_pedidos)
            op_actual = prod.orden_produccion
            if op_actual and str(op_actual).strip() != 'SIN OP':
                from backend.models.sql_models import DistribucionOpPedidos
                
                op_limpia = str(op_actual or '').strip()
                from backend.utils.formatters import normalizar_codigo
                codigo_limpio = normalizar_codigo(prod.id_codigo)
                
                # Buscamos todas las cubetas asociadas a esta OP y producto
                cubetas = db.session.query(DistribucionOpPedidos).filter(
                    DistribucionOpPedidos.op_world_office == op_limpia,
                    DistribucionOpPedidos.codigo_producto == codigo_limpio
                ).order_by(DistribucionOpPedidos.id_distribucion.asc()).all()

                piezas_por_repartir = piezas_inyectadas
                
                # Validación y creación de cubeta de contingencia
                if not cubetas and piezas_por_repartir > 0:
                    # Intentar buscar el id_pedido de otra cubeta asociada a la misma OP
                    pedido_asoc = db.session.query(DistribucionOpPedidos.id_pedido).filter(
                        DistribucionOpPedidos.op_world_office == op_limpia
                    ).first()
                    id_pedido_final = pedido_asoc[0] if (pedido_asoc and pedido_asoc[0]) else f"PED-IMPREVISTO-{op_limpia}"
                    
                    logger.info(f" ⚠️ [INYECCION-CONTINGENCIA] Creando cubeta temporal para OP: {op_limpia}, Producto: {codigo_limpio}, Pedido: {id_pedido_final}")
                    nueva_cubeta = DistribucionOpPedidos(
                        op_world_office=op_limpia,
                        id_pedido=id_pedido_final,
                        codigo_producto=codigo_limpio,
                        cant_requerida=piezas_por_repartir,
                        cant_inyectada=piezas_por_repartir,
                        cant_pulida=0,
                        cant_ensamblada=0,
                        cant_alistada=0
                    )
                    db.session.add(nueva_cubeta)
                    db.session.flush() # Sincronizar temporalmente en sesión
                    cubetas = [nueva_cubeta]
                    piezas_por_repartir = 0.0 # Consumido por completo
                
                logger.info(f" 📦 [INYECCION-FIFO] Propagando {piezas_por_repartir} piezas a {len(cubetas)} cubetas. OP: {op_limpia}, Producto: {codigo_limpio}")

                for cubeta in cubetas:
                    if piezas_por_repartir <= 0:
                        break
                    
                    falta = max(0, (cubeta.cant_requerida or 0) - (cubeta.cant_inyectada or 0))
                    if falta > 0:
                        if piezas_por_repartir >= falta:
                            cubeta.cant_inyectada = (cubeta.cant_inyectada or 0) + falta
                            piezas_por_repartir -= falta
                        else:
                            cubeta.cant_inyectada = (cubeta.cant_inyectada or 0) + piezas_por_repartir
                            piezas_por_repartir = 0

            # 4. Finalizar programación asociada en db_programacion
            db.session.query(ProgramacionInyeccion).filter(
                ProgramacionInyeccion.codigo_sistema == prod.id_codigo,
                ProgramacionInyeccion.maquina == prod.maquina,
                ProgramacionInyeccion.estado == 'EN_PROCESO'
            ).update({"estado": 'FINALIZADO'}, synchronize_session=False)

        # 5. Confirmar transacción de forma atómica
        db.session.commit()

        # Limpiar caché del MES
        try:
            from backend.app import clear_mes_cache
            clear_mes_cache()
        except:
            pass

        logger.info(f"✅ Lote {id_iny} reportado y finalizado exitosamente. Total piezas: {total_teorica}")
        return jsonify({
            "success": True,
            "count": len(prods_en_lote),
            "teorica": total_teorica,
            "message": "Turno finalizado con éxito. Cubetas de prioridad actualizadas por FIFO."
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al reportar turno en el MES: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error interno al finalizar el turno"}), 500


@inyeccion_bp.route('/api/pnc/registrar_inyeccion', methods=['POST'])
def registrar_pnc_inyeccion():
    """
    Registra el reporte de PNC para un lote de inyección, mapeando los defectos
    a columnas numéricas específicas de la tabla db_pnc_inyeccion.
    """
    try:
        data = request.get_json() or {}
        id_iny = data.get('id_inyeccion')
        id_codigo = data.get('id_codigo') or data.get('codigo')
        defectos = data.get('defectos') or {}
        
        if not id_iny:
            return jsonify({"success": False, "error": "El campo id_inyeccion es obligatorio"}), 400

        # Normalizar el código de producto
        from backend.utils.formatters import normalizar_codigo
        id_cod = normalizar_codigo(id_codigo) if id_codigo else None

        # Fallback de producto si no se recibe
        if not id_cod:
            first_prod = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion=id_iny).first()
            if first_prod:
                id_cod = first_prod.id_codigo

        if not id_cod:
            return jsonify({"success": False, "error": "El campo id_codigo es obligatorio"}), 400

        # Limpiar registros previos de PNC de este código en esta inyección
        db.session.query(PncInyeccion).filter_by(id_inyeccion=id_iny, id_codigo=id_cod).delete()

        # Acumular cantidades por defecto
        quemado_manchado = 0
        incompleto_falta_llenado = 0
        rebaba_excesiva = 0
        burbuja_porosidad = 0
        deformacion_rechupado = 0

        # Si viene en formato de lista
        if isinstance(defectos, list):
            defectos_dict = {}
            for item in defectos:
                crit = item.get('criterio') or item.get('motivo')
                cant = float(item.get('cantidad') or 0)
                if crit and cant > 0:
                    defectos_dict[crit] = defectos_dict.get(crit, 0) + cant
            defectos = defectos_dict

        for key, val in defectos.items():
            cant = float(val or 0)
            if cant <= 0:
                continue
            
            key_lower = str(key).lower().strip()
            # Mapeo:
            if any(x in key_lower for x in ["quemado", "mancha", "contaminado"]):
                quemado_manchado += cant
            elif any(x in key_lower for x in ["incompleto", "escaso", "falta", "llenado"]):
                incompleto_falta_llenado += cant
            elif "rebaba" in key_lower:
                rebaba_excesiva += cant
            elif any(x in key_lower for x in ["burbuja", "porosidad"]):
                burbuja_porosidad += cant
            elif any(x in key_lower for x in ["deform", "rechupe", "chupado", "hundido", "flujo"]):
                deformacion_rechupado += cant
            else:
                deformacion_rechupado += cant

        total_cantidad = quemado_manchado + incompleto_falta_llenado + rebaba_excesiva + burbuja_porosidad + deformacion_rechupado

        # Guardar en base de datos si el total es mayor a cero
        prod_iny = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion=id_iny, id_codigo=id_cod).first()
        
        if total_cantidad > 0:
            codigo_ensamble = prod_iny.codigo_ensamble if prod_iny else None

            nuevo_pnc = PncInyeccion(
                id_pnc_inyeccion=uuid.uuid4().hex[:8],
                id_inyeccion=id_iny,
                id_codigo=id_cod,
                cantidad=total_cantidad,
                criterio=f"Quemado: {int(quemado_manchado)}, Falta Llenado: {int(incompleto_falta_llenado)}, Rebaba: {int(rebaba_excesiva)}, Burbujas: {int(burbuja_porosidad)}, Deformacion: {int(deformacion_rechupado)}",
                codigo_ensamble=codigo_ensamble,
                quemado_manchado=quemado_manchado,
                incompleto_falta_llenado=incompleto_falta_llenado,
                rebaba_excesiva=rebaba_excesiva,
                burbuja_porosidad=burbuja_porosidad,
                deformacion_rechupado=deformacion_rechupado
            )
            db.session.add(nuevo_pnc)

            # Sincronizar pnc_total, pnc_detalle y cantidad_real en el registro de ProduccionInyeccion correspondiente
            if prod_iny:
                prod_iny.pnc_total = int(round(total_cantidad))
                prod_iny.pnc_detalle = nuevo_pnc.criterio
                cant_bruta = prod_iny.cant_contador or prod_iny.cantidad_real or 0
                prod_iny.cantidad_real = max(0, int(round(cant_bruta - total_cantidad)))

            db.session.commit()
            logger.info(f"✅ PNC registrado para {id_cod} en {id_iny}: Total: {total_cantidad}")
            return jsonify({
                "success": True,
                "message": "PNC registrado correctamente en db_pnc_inyeccion",
                "total_pnc": total_cantidad
            }), 200
        else:
            if prod_iny:
                prod_iny.pnc_total = 0
                prod_iny.pnc_detalle = ""
                cant_bruta = prod_iny.cant_contador or prod_iny.cantidad_real or 0
                prod_iny.cantidad_real = int(round(cant_bruta))
            db.session.commit()
            return jsonify({
                "success": True,
                "message": "No se reportaron defectos de PNC",
                "total_pnc": 0
            }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        logger.error(f"❌ Error en registrar_pnc_inyeccion: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


