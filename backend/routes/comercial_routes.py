import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, render_template, session, send_file
from backend.utils.auth_middleware import require_role, ROL_ADMINS, ROL_COMERCIALES, obtener_identidad_segura
from backend.services.comercial_service import ComercialHistoricoService

logger = logging.getLogger(__name__)

comercial_bp = Blueprint('comercial', __name__)

ROLES_PERMITIDOS_COMERCIAL = ROL_ADMINS + ROL_COMERCIALES + ['GERENCIA']

@comercial_bp.route('/comercial/historico', methods=['GET'])
@require_role(ROLES_PERMITIDOS_COMERCIAL)
def render_comercial_historico():
    """Rinde la plantilla HTML independiente para la Analítica Comercial Histórica."""
    return render_template('comercial_historico.html')

@comercial_bp.route('/api/comercial/historico', methods=['GET'])
@require_role(ROLES_PERMITIDOS_COMERCIAL)
def api_obtener_comercial_historico():
    """
    Endpoint dedicado para la extracción analítica de ventas históricas.
    Retorna agregaciones pre-calculadas en PostgreSQL con aislamiento por rol.
    """
    try:
        user_name, user_role = obtener_identidad_segura(request)
        user_id = session.get('user_id') or session.get('usuario_id') or 0
        
        start_year = request.args.get('start_year', default=2024, type=int)
        end_year = request.args.get('end_year', default=2026, type=int)

        data = ComercialHistoricoService.obtener_analitica_historica(
            user_id=user_id,
            username=user_name,
            user_role=user_role,
            start_year=start_year,
            end_year=end_year
        )

        return jsonify(data), 200

    except Exception as e:
        logger.error(f"[COMERCIAL_ROUTES] Error en /api/comercial/historico: {e}")
        return jsonify({'success': False, 'error': 'Error interno extrayendo datos analíticos', 'detalle': str(e)}), 500


@comercial_bp.route('/api/comercial/historico/detalle', methods=['GET'])
@require_role(ROLES_PERMITIDOS_COMERCIAL)
def api_obtener_comercial_detalle():
    """
    Detalle consolidado paginado (Año, Mes, Zona, Cliente). Server-side: la agregación,
    el filtro de búsqueda y el LIMIT/OFFSET corren en PostgreSQL — nunca se envían
    más de `tam_pagina` filas (tope duro 200) al navegador.
    """
    try:
        user_name, user_role = obtener_identidad_segura(request)
        user_id = session.get('user_id') or session.get('usuario_id') or 0

        start_year = request.args.get('start_year', default=2024, type=int)
        end_year = request.args.get('end_year', default=2026, type=int)
        pagina = request.args.get('pagina', default=1, type=int)
        tam_pagina = request.args.get('tam_pagina', default=100, type=int)
        busqueda = request.args.get('busqueda', default='', type=str)

        data = ComercialHistoricoService.obtener_detalle_paginado(
            user_id=user_id,
            username=user_name,
            user_role=user_role,
            start_year=start_year,
            end_year=end_year,
            pagina=pagina,
            tam_pagina=tam_pagina,
            busqueda=busqueda
        )

        return jsonify(data), 200

    except Exception as e:
        logger.error(f"[COMERCIAL_ROUTES] Error en /api/comercial/historico/detalle: {e}")
        return jsonify({'success': False, 'error': 'Error interno extrayendo el detalle', 'detalle': str(e)}), 500


@comercial_bp.route('/api/comercial/crecimiento-clientes', methods=['GET'])
@require_role(ROLES_PERMITIDOS_COMERCIAL)
def api_obtener_crecimiento_clientes():
    """
    Controlador delgado: captura y sanitiza los parámetros de QueryString
    (anio_base, anio_comparacion, zona, busqueda) y delega toda la agregación
    SQL y el cálculo de crecimiento YoY al servicio.
    """
    try:
        user_name, user_role = obtener_identidad_segura(request)
        user_id = session.get('user_id') or session.get('usuario_id') or 0

        anio_actual = datetime.now().year
        anio_base = request.args.get('anio_base', default=anio_actual - 1, type=int)
        anio_comparacion = request.args.get('anio_comparacion', default=anio_actual, type=int)
        zona = request.args.get('zona', default='', type=str).strip()
        busqueda = request.args.get('busqueda', default='', type=str).strip()

        data = ComercialHistoricoService.obtener_crecimiento_clientes(
            user_id=user_id,
            username=user_name,
            user_role=user_role,
            anio_base=anio_base,
            anio_comparacion=anio_comparacion,
            zona=zona,
            busqueda=busqueda
        )

        return jsonify(data), 200

    except Exception as e:
        logger.error(f"[COMERCIAL_ROUTES] Error en /api/comercial/crecimiento-clientes: {e}")
        return jsonify({'success': False, 'error': 'Error interno calculando el crecimiento de clientes', 'detalle': str(e)}), 500


@comercial_bp.route('/api/comercial/historico/excel', methods=['GET'])
@require_role(ROLES_PERMITIDOS_COMERCIAL)
def exportar_comercial_excel():
    """
    Controlador delgado: solo captura parámetros de la request y delega toda
    la generación (SQL, pandas, openpyxl) al servicio.
    """
    try:
        user_name, user_role = obtener_identidad_segura(request)
        user_id = session.get('user_id') or session.get('usuario_id') or 0

        start_year = request.args.get('start_year', default=2024, type=int)
        end_year = request.args.get('end_year', default=2026, type=int)
        vendedor_filtro = request.args.get('vendedor', default='', type=str)
        fecha_corte = request.args.get('corte', default=None, type=str)  # YYYY-MM-DD opcional

        buffer, nombre_archivo = ComercialHistoricoService.generar_excel_ytd_stream(
            user_id=user_id,
            username=user_name,
            user_role=user_role,
            start_year=start_year,
            end_year=end_year,
            vendedor_filtro=vendedor_filtro,
            fecha_corte=fecha_corte
        )

        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=nombre_archivo
        )

    except Exception as e:
        logger.error(f"[COMERCIAL_ROUTES] Error en /api/comercial/historico/excel: {e}")
        return jsonify({'success': False, 'error': 'Error interno generando el Excel', 'detalle': str(e)}), 500
