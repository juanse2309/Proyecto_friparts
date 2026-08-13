"""
Registro de "tools" del Asistente de Dashboard.

Cada tool envuelve un metodo YA EXISTENTE de un repositorio/servicio. El LLM
solo puede invocar estos nombres con estos parametros tipados (fechas, codigos,
nombres); nunca genera SQL ni nombres de columna/tabla. Esto es la defensa
principal contra inyeccion: el modelo elige QUE tool llamar y con que
argumentos, pero el SQL que se ejecuta ya estaba escrito y probado de antemano.
"""
import calendar
import logging
import unicodedata
from datetime import datetime

from backend.repositories.dashboard_repository import DashboardRepository
from backend.repositories.ventas_repository import VentasRepository
from backend.repositories.producto_repository import producto_repo
from backend.services.dashboard_service import DashboardService
from backend.services.pnc_service import PncService
from backend.services.comercial_service import ComercialHistoricoService
from backend.services.programacion_service import ProgramacionService
from backend.services import nomina_service
from backend.models.sql_models import Pedido, Producto, ProgramacionEnsamble
from backend.utils.auth_middleware import ROL_ADMINS, ROL_COMERCIALES, ROL_JEFES

logger = logging.getLogger(__name__)

ROL_TODOS = ROL_ADMINS + ROL_COMERCIALES + ROL_JEFES


def _fecha(valor):
    """Valida que un parametro de fecha tenga forma YYYY-MM-DD; si no, lo descarta."""
    if not valor:
        return None
    try:
        datetime.strptime(str(valor)[:10], '%Y-%m-%d')
        return str(valor)[:10]
    except (ValueError, TypeError):
        return None


def _normalizar_rol(raw_role):
    raw = str(raw_role or '').strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', raw) if unicodedata.category(c) != 'Mn')


def _rol_autorizado(role_norm, allowed_roles):
    """Mismo criterio flexible/inclusivo que auth_middleware.require_role:
    Admins tienen God Mode, y para el resto basta con que el rol permitido
    sea substring del rol del usuario (soporta variantes como 'JEFE INYECCION')."""
    if role_norm in [r.upper() for r in ROL_ADMINS]:
        return True
    allowed_upper = [r.upper() for r in allowed_roles]
    return any(allowed in role_norm for allowed in allowed_upper)


# ── Handlers: wrappers de solo lectura sobre repos/servicios existentes ──────

def _tool_ventas_periodo(params, ctx):
    desde = _fecha(params.get('desde'))
    hasta = _fecha(params.get('hasta'))
    kpis = DashboardRepository.get_dashboard_kpis(desde, hasta)
    return {
        'concepto': (
            'ventas_unidades y ventas_totales_cop son la MISMA venta en dos unidades (piezas '
            'vs pesos) -- no se suman entre si. inyeccion_ok/pulido_ok/ensambles_ok son piezas '
            'PRODUCIDAS, pedidos_solicitados son piezas PEDIDAS por clientes -- ninguno de esos '
            'es lo mismo que ventas_unidades (piezas ya facturadas), no los mezcles ni sumes.'
        ),
        'ventas_unidades': kpis.get('ventas_unidades', 0),
        'ventas_totales_cop': kpis.get('ventas_totales', 0),
        'inyeccion_ok': kpis.get('inyeccion_ok', 0),
        'pulido_ok': kpis.get('pulido_ok', 0),
        'ensambles_ok': kpis.get('ensambles_ok', 0),
        'pedidos_solicitados': kpis.get('pedidos_solicitados', 0),
        'scrap_total': kpis.get('scrap_total', 0),
        'perdida_calidad_dinero': kpis.get('perdida_calidad_dinero', 0),
        'periodo': {'desde': desde, 'hasta': hasta},
    }


def _tool_comparativo_mensual(params, ctx):
    desde = _fecha(params.get('desde'))
    hasta = _fecha(params.get('hasta'))
    incluir_pedidos = bool(params.get('incluir_pedidos', False))
    raw = DashboardRepository.get_monthly_performance_comparison(desde, hasta)
    anio_actual = raw.get('year_actual')
    anio_anterior = raw.get('year_prev')
    mensual = raw.get('mensual') or []

    # DashboardRepository devuelve, por mes, 4 cifras de dinero como campos
    # hermanos del mismo objeto: 'actual_dinero'/'prev_dinero' (ventas anio
    # actual/anterior) y 'actual_pedidos'/'prev_pedidos' (pedidos anio
    # actual/anterior) -- mas alias duplicados. Separar en secciones top-level
    # con 'concepto' explicando "NO sumar" NO fue suficiente: en produccion el
    # modelo igual sumo ventas_facturadas_cop + pedidos_solicitados_cop en una
    # respuesta ($625,209,132 + $433,674,947 = $1,058,884,079 reportado como
    # "cierre de julio", incorrecto). Una advertencia en texto es una sugerencia,
    # no un bloqueo real. La defensa que si funciona es no darle al modelo el
    # dato de pedidos en dinero salvo que la pregunta EXPLICITAMENTE lo pida
    # (incluir_pedidos=true) -- no puede sumar un numero que nunca recibio.
    resultado = {
        'anio_actual': anio_actual,
        'anio_anterior': anio_anterior,
        # 'unidades' va primero porque es lo que mas se consulta en la practica --
        # el jefe de planta prioriza volumen fisico sobre dinero facturado.
        'ventas_unidades': {
            'concepto': (
                'UNIDADES de ventas ya facturadas por mes (piezas, no dinero). NO sumar el '
                'anio actual con el anterior -- son para comparar, no combinar.'
            ),
            'meses': [{
                'mes': m.get('mes'),
                f'{anio_actual}_unds': m.get('actual_unidades', 0),
                f'{anio_anterior}_unds': m.get('prev_unidades', 0),
            } for m in mensual],
        },
        'ventas_facturadas_cop': {
            'concepto': (
                'Dinero de VENTAS ya facturadas por mes. NO sumar el anio actual con el '
                'anterior -- son para comparar, no combinar.'
            ),
            'meses': [{
                'mes': m.get('mes'),
                f'{anio_actual}_cop': m.get('actual_dinero', 0),
                f'{anio_anterior}_cop': m.get('prev_dinero', 0),
            } for m in mensual],
        },
    }

    if incluir_pedidos:
        resultado['pedidos_unidades'] = {
            'concepto': (
                'UNIDADES de pedidos solicitados por clientes por mes (no necesariamente ya '
                'despachados). Concepto DISTINTO de ventas_unidades (facturado vs solo '
                'solicitado) -- preséntalos por separado, nunca sumados.'
            ),
            'meses': [{
                'mes': m.get('mes'),
                f'{anio_actual}_unds': m.get('actual_pedidos_unidades', 0),
                f'{anio_anterior}_unds': m.get('prev_pedidos_unidades', 0),
            } for m in mensual],
        }
        resultado['pedidos_solicitados_cop'] = {
            'concepto': (
                'Dinero de PEDIDOS solicitados por clientes por mes (no necesariamente ya '
                'facturados/despachados). Concepto DISTINTO de ventas_facturadas_cop '
                '(solicitado vs ya facturado) -- preséntalos por separado, nunca sumados.'
            ),
            'meses': [{
                'mes': m.get('mes'),
                f'{anio_actual}_cop': m.get('actual_pedidos', 0),
                f'{anio_anterior}_cop': m.get('prev_pedidos', 0),
            } for m in mensual],
        }

    return resultado


def _tool_desglose_ventas_mensual(params, ctx):
    mes = params.get('mes')
    anio = params.get('anio')
    tipo_vista = params.get('tipo_vista') or 'money'
    if not mes or not anio:
        raise ValueError("Se requieren 'mes' y 'anio' para el desglose mensual de ventas.")
    raw = VentasRepository.get_desglose_mensual_ventas(mes, anio, tipo_vista)
    productos = raw.get('productos') or []
    clientes = raw.get('clientes') or []

    # 'productos' y 'clientes' son DOS DESGLOSES DEL MISMO total del mes (por
    # producto y por cliente), no dos montos separados -- mismo patron de riesgo
    # que el bug de comparativo_mensual (ver ahi). Se agrega un total explicito +
    # 'concepto' para que el modelo no sume ambos desgloses pensando que son
    # cifras independientes.
    total_mes = sum(float(p.get('total_ventas', 0) or 0) for p in productos)
    return {
        'mes': mes,
        'anio': anio,
        'total_mes_cop': total_mes,
        'concepto': (
            'total_mes_cop es el total real de ventas del mes. "por_producto" y "por_cliente" '
            'son DOS DESGLOSES DISTINTOS de ese MISMO total (cada uno ya suma el 100%, solo '
            'agrupado diferente) -- NO sumar por_producto con por_cliente, ni sumarlos a '
            'total_mes_cop.'
        ),
        'por_producto': productos,
        'por_cliente': clientes,
    }


def _tool_backorder_cliente(params, ctx):
    cliente = params.get('cliente')
    if not cliente:
        raise ValueError("Se requiere el nombre del cliente.")
    desde = _fecha(params.get('desde'))
    hasta = _fecha(params.get('hasta'))
    return VentasRepository.get_backorder_detalle_por_cliente(cliente, desde, hasta)


def _tool_ranking_operarios(params, ctx):
    area = str(params.get('area') or 'inyeccion').strip().lower()
    desde = _fecha(params.get('desde'))
    hasta = _fecha(params.get('hasta'))
    if area == 'pulido':
        ranking = DashboardRepository.get_ranking_operarios_pulido(desde, hasta)
        # 'eficiencia'/'minutos' de get_ranking_operarios_pulido dependen de
        # db_costos.tiempo_estandar, que solo esta cargado para ~25% de las
        # referencias (96 de 386 verificado en produccion) -- para un operario
        # que trabaja mayormente en referencias SIN tiempo estandar cargado, el
        # calculo (tiempo_std / tiempo_real) queda artificialmente bajisimo
        # (valores reales vistos: 4.8%, 5%, 9.2%), no porque el operario rinda
        # mal. Mismo problema de fondo por el que el Arquitecto de Software ya
        # dio de baja el modulo hermano
        # DashboardService.calcular_eficiencia_pulido_por_referencia (ver ese
        # comentario). El ranking real del dashboard
        # (/avanzado/produccion_operario_ranking) tampoco expone 'eficiencia' --
        # solo usa 'nombre'/'valor'. Se quita aqui por la misma razon, para no
        # ser el unico lugar de la app presentando una metrica ya identificada
        # como no confiable.
        ranking = [
            {k: v for k, v in r.items() if k not in ('eficiencia', 'minutos')}
            for r in ranking
        ]
        return {'area': 'pulido', 'ranking': ranking}
    return {'area': 'inyeccion', 'ranking': DashboardRepository.get_ranking_operarios_inyeccion(desde, hasta)}


def _tool_produccion_por_maquina(params, ctx):
    return DashboardRepository.get_produccion_por_maquina()


def _tool_scrap_detalle(params, ctx):
    item_id = params.get('id_codigo') or params.get('referencia')
    if not item_id:
        raise ValueError("Se requiere el codigo de producto (id_codigo).")
    desde = _fecha(params.get('desde'))
    hasta = _fecha(params.get('hasta'))
    return {'item_id': item_id, 'detalle': DashboardService.get_scrap_detalle(item_id, desde, hasta)}


def _tool_productos_sin_rotacion(params, ctx):
    q = params.get('q')
    try:
        max_ventas = int(params.get('max_ventas', 0) or 0)
    except (TypeError, ValueError):
        max_ventas = 0
    raw = DashboardService.get_productos_sin_rotacion(q=q, max_ventas=max_ventas)

    # El DTO original trae 'stock' y 'stock_terminado' como el MISMO numero
    # duplicado con dos nombres -- se quita el alias para que el modelo no lo
    # lea como dos cantidades distintas y las sume.
    productos = [
        {k: v for k, v in p.items() if k != 'stock_terminado'}
        for p in (raw.get('productos') or [])
    ]
    total = raw.get('total', len(productos))
    concepto = f"'total' es el conteo REAL ({total}); 'productos' esta limitada a los primeros {len(productos)} (mayor stock primero) -- no asumir que len(productos) es el total."
    return {**raw, 'total': total, 'concepto': concepto, 'productos': productos}


def _tool_cartera_estado(params, ctx):
    # Antes usaba DashboardService.get_cartera_wo_stats() (solo 3 totales + top 5
    # clientes). CarteraService.obtener_cartera_agrupada() es el mismo dato que
    # alimenta el modulo de Cartera real: por cliente, con edades de mora
    # (corriente/1-30/31-60/61-90/+90) y vendedor -- mucho mas util para que el
    # asistente pueda responder cosas como "quien tiene mora de mas de 90 dias"
    # en vez de solo el total agregado.
    from backend.services.cartera_service import CarteraService
    agrupada = CarteraService.obtener_cartera_agrupada()

    total_cartera = sum(c['saldo_total'] for c in agrupada)
    total_vencida = sum(c['d1_30'] + c['d31_60'] + c['d61_90'] + c['mas_90'] for c in agrupada)

    clientes_ordenados = sorted(agrupada, key=lambda c: c['saldo_total'], reverse=True)
    # total_clientes_con_saldo es el conteo REAL (antes de truncar) -- sin esto,
    # "cuantos clientes deben" se contestaba contando la lista 'clientes' (solo
    # los 30 mas grandes), no el total real. Mismo patron de bug que las demas
    # tools con listas truncadas (alertas_abastecimiento, pedidos_pendientes_
    # facturacion, ensamble_tareas_pendientes ya traen su total explicito).
    return {
        'total_cartera_cop': total_cartera,
        'total_vencida_cop': total_vencida,
        'total_corriente_cop': total_cartera - total_vencida,
        'total_clientes_con_saldo': len(agrupada),
        'concepto': (
            "'clientes' trae solo los 30 con mayor saldo (de "
            f"{len(agrupada)} clientes con saldo en total) -- usar "
            "'total_clientes_con_saldo' para el conteo real, no len(clientes)."
        ),
        'clientes': clientes_ordenados[:30],
    }


def _tool_pnc_metricas(params, ctx):
    desde = _fecha(params.get('desde'))
    hasta = _fecha(params.get('hasta'))
    raw = PncService.obtener_metricas_pnc_consolidadas(desde, hasta)
    # 'modos_falla_area' (piezas) y 'modos_falla_dinero_area' (COP) son el MISMO
    # motivo de falla en dos unidades distintas -- no se suman entre si. Y
    # 'totales_area' (agrupado por area) y 'pareto_referencias' (agrupado por
    # referencia, solo top 10) son dos cortes del MISMO total de piezas PNC.
    raw['concepto'] = (
        'modos_falla_area = piezas PNC; modos_falla_dinero_area = el MISMO dato en pesos COP '
        '(no se suman entre si). totales_area (por area) y pareto_referencias (top 10 '
        'referencias) son dos cortes del mismo total de piezas PNC, no cifras adicionales.'
    )
    return raw


def _tool_stock_producto(params, ctx):
    codigo = params.get('codigo')
    if not codigo:
        raise ValueError("Se requiere el codigo de producto.")
    producto = producto_repo.buscar_por_codigo(codigo)
    if not producto:
        return {'encontrado': False, 'codigo': codigo}
    return {'encontrado': True, **producto}


def _tool_stock_critico(params, ctx):
    return {'productos': producto_repo.get_stock_critico_sql()}


def _tool_analitica_comercial(params, ctx):
    # user_id/username/role SIEMPRE vienen del contexto de sesion real, nunca
    # de lo que pida el LLM: evita que un comercial consulte las cifras de otro.
    try:
        anio_desde = int(params.get('anio_desde') or 2024)
        anio_hasta = int(params.get('anio_hasta') or 2026)
    except (TypeError, ValueError):
        anio_desde, anio_hasta = 2024, 2026
    raw = ComercialHistoricoService.obtener_analitica_historica(
        user_id=ctx['user_id'],
        username=ctx['user'],
        user_role=ctx['role'],
        start_year=anio_desde,
        end_year=anio_hasta,
    )

    # 'resumen_anual' (por anio individual), 'resumen_zonas' y 'top_clientes' son
    # TRES cortes DISTINTOS del MISMO dinero total del rango de anios consultado
    # -- no cifras independientes que se puedan sumar entre si. Ademas
    # resumen_zonas/top_clientes son acumulados de TODO el rango (no por anio),
    # mientras resumen_anual SI esta separado anio por anio: si se mezclan sin
    # aclarar el alcance, el modelo puede confundir "ventas de 2026" con el
    # acumulado 2024-2026 de una zona. top_clientes ademas esta truncado (no es
    # el 100% de los clientes).
    return {
        'periodo': raw.get('periodo'),
        'vista_global_toda_la_empresa': (raw.get('seguridad') or {}).get('vista_global'),
        'ventas_por_anio': {
            'concepto': 'Total de ventas de CADA anio individual dentro del periodo consultado.',
            'anios': raw.get('resumen_anual') or [],
        },
        'ventas_por_zona': {
            'concepto': (
                'Total de ventas por zona ACUMULADO de TODO el periodo consultado (no es por '
                'anio individual). La suma de todas las zonas es el mismo total que la suma de '
                'ventas_por_anio -- son el mismo dinero visto de dos formas, NO se suman entre si.'
            ),
            'zonas': raw.get('resumen_zonas') or [],
        },
        'top_clientes': {
            'concepto': (
                'Los clientes con mayor venta ACUMULADA de todo el periodo (lista truncada, NO '
                'es el 100% de los clientes ni del total). NO sumar con ventas_por_anio ni con '
                'ventas_por_zona.'
            ),
            'clientes': raw.get('top_clientes') or [],
        },
    }


def _tool_pedidos_pendientes_facturacion(params, ctx):
    # Misma consulta que /api/facturacion/pedidos-pendientes (facturacion_routes.py),
    # reusada tal cual: agrupa lineas de Pedido en estado PENDIENTE por id_pedido.
    pendientes = Pedido.query.filter(Pedido.estado == 'PENDIENTE').all()
    agrupados = {}
    for r in pendientes:
        id_ped = r.id_pedido
        if id_ped not in agrupados:
            agrupados[id_ped] = {
                'id_pedido': id_ped, 'fecha': str(r.fecha), 'cliente': r.cliente,
                'vendedor': r.vendedor, 'items_count': 0, 'total_cop': 0,
            }
        cant = float(r.cantidad or 0)
        prec = float(r.precio_unitario or 0)
        agrupados[id_ped]['items_count'] += 1
        agrupados[id_ped]['total_cop'] += (cant * prec)

    resultado = sorted(agrupados.values(), key=lambda x: x['fecha'], reverse=True)
    return {'total_pedidos_pendientes': len(resultado), 'pedidos': resultado[:100]}


def _tool_alertas_abastecimiento(params, ctx):
    # Misma consulta que /api/procura/alertas_abastecimiento (procura_routes.py):
    # productos cuyo stock en bodega esta por debajo del minimo configurado.
    productos = Producto.query.all()
    alertas = []
    for p in productos:
        stock = float(p.stock_bodega or 0)
        minimo = float(p.stock_minimo or 0)
        if stock < minimo:
            alertas.append({
                'producto': p.id_codigo or p.codigo_sistema,
                'descripcion': p.descripcion,
                'stock_actual': stock,
                'minimo_requerido': minimo,
                'faltante': minimo - stock,
                'urgencia': 'CRITICA_SIN_STOCK' if stock == 0 else 'BAJO_MINIMO',
            })
    alertas.sort(key=lambda x: x['faltante'], reverse=True)
    return {'total_alertas': len(alertas), 'alertas': alertas[:100]}


def _tool_programacion_maquinas(params, ctx):
    # Envuelve ProgramacionService.obtener_dashboard_mes() (metodo ya existente,
    # usado por /api/mes/dashboard): trabajo activo + cola por cada maquina de inyeccion.
    maquinas = ProgramacionService.obtener_dashboard_mes()
    return {'maquinas': maquinas}


def _tool_ensamble_tareas_pendientes(params, ctx):
    # Misma consulta que /api/ensamble/tareas_pendientes (ensamble_routes.py).
    tareas = ProgramacionEnsamble.query.filter(
        ProgramacionEnsamble.estado != 'COMPLETADO'
    ).order_by(ProgramacionEnsamble.fecha_programada.asc()).all()

    resultado = [{
        'id_codigo': t.id_codigo,
        'cantidad_objetivo': t.cantidad_objetivo,
        'cantidad_realizada': t.cantidad_realizada,
        'faltante': max(0, (t.cantidad_objetivo or 0) - (t.cantidad_realizada or 0)),
        'fecha_programada': t.fecha_programada.strftime('%Y-%m-%d') if t.fecha_programada else '',
        'estado': t.estado,
    } for t in tareas]
    return {'total_pendientes': len(resultado), 'tareas': resultado[:100]}


# ── Extractores de serie graficable (corren en Python, ANTES de json.dumps) ──
# jsonify ordena las claves alfabeticamente por defecto en esta version de Flask,
# asi que "la primera clave numerica" deja de identificar de forma fiable el campo
# correcto (ej. 'eficiencia' quedaba antes que 'valor' tras el sort). Estos
# extractores fijan explicitamente que campo es la metrica a graficar, en vez de
# adivinarlo del lado del frontend.

def _serie_comparativo_mensual(datos):
    # Unidades primero: es lo que mas se consulta en la practica.
    anio_actual = datos.get('anio_actual')
    anio_anterior = datos.get('anio_anterior')
    meses = (datos.get('ventas_unidades') or {}).get('meses') or []
    if not meses or anio_actual is None:
        return None
    campo_actual = f'{anio_actual}_unds'

    if len(meses) == 1:
        # Un JSON con un solo mes -> una "linea"/tendencia de 1 punto no dice nada
        # (ni siquiera se alcanza a dibujar una linea con un solo punto; se veia
        # el grafico practicamente vacio, un unico puntico). Con un solo mes lo
        # util es comparar ese mes contra el mismo mes del anio anterior, que es
        # justo lo que el texto de la respuesta ya menciona.
        campo_anterior = f'{anio_anterior}_unds'
        m = meses[0]
        return {
            'labels': [str(anio_anterior), str(anio_actual)],
            'values': [float(m.get(campo_anterior, 0) or 0), float(m.get(campo_actual, 0) or 0)],
            'etiqueta': f"ventas_{m.get('mes', '')}_unds",
            'ordenar': False,  # son 2 barras cronologicas (anio anterior -> actual), no un ranking
        }

    # Varios meses -> tendencia cronologica real, NO reordenar por valor (eso
    # tiene sentido para un ranking de clientes/productos, no para una serie
    # de tiempo: enero debe seguir mostrandose antes que febrero).
    return {
        'labels': [m.get('mes', '') for m in meses],
        'values': [float(m.get(campo_actual, 0) or 0) for m in meses],
        'etiqueta': f'ventas_{campo_actual}',
        'ordenar': False,
    }


def _serie_ranking_operarios(datos):
    ranking = datos.get('ranking') or []
    if not ranking:
        return None
    return {
        'labels': [r.get('nombre', '') for r in ranking],
        'values': [float(r.get('valor', 0) or 0) for r in ranking],
        'etiqueta': 'piezas_ok',
    }


def _serie_produccion_por_maquina(datos):
    maquinas = datos.get('maquinas') or {}
    if not maquinas:
        return None
    items = list(maquinas.items())
    return {
        'labels': [nombre for nombre, _ in items],
        'values': [float(v.get('produccion_total', 0) or 0) for _, v in items],
        'etiqueta': 'produccion_total',
    }


def _serie_desglose_ventas_mensual(datos):
    # Unidades primero: es lo que mas se consulta en la practica.
    productos = datos.get('por_producto') or []
    if not productos:
        return None
    ordenado = sorted(productos, key=lambda p: float(p.get('unidades', 0) or 0), reverse=True)[:10]
    return {
        'labels': [p.get('id_codigo') or p.get('descripcion') or '' for p in ordenado],
        'values': [float(p.get('unidades', 0) or 0) for p in ordenado],
        'etiqueta': 'unidades',
    }


def _serie_analitica_comercial(datos):
    # Unidades primero: es lo que mas se consulta en la practica.
    resumen = (datos.get('ventas_por_anio') or {}).get('anios') or []
    if not resumen:
        return None
    return {
        'labels': [str(r.get('anio', '')) for r in resumen],
        'values': [float(r.get('total_unidades', 0) or 0) for r in resumen],
        'etiqueta': 'total_unidades',
    }


def _serie_cartera_estado(datos):
    clientes = datos.get('clientes') or []
    if not clientes:
        return None
    top = sorted(clientes, key=lambda c: float(c.get('saldo_total', 0) or 0), reverse=True)[:10]
    return {
        'labels': [c.get('nombre', '') for c in top],
        'values': [float(c.get('saldo_total', 0) or 0) for c in top],
        'etiqueta': 'saldo_total_cop',
    }


def _serie_alertas_abastecimiento(datos):
    alertas = datos.get('alertas') or []
    if not alertas:
        return None
    top = sorted(alertas, key=lambda a: float(a.get('faltante', 0) or 0), reverse=True)[:10]
    return {
        'labels': [a.get('producto', '') for a in top],
        'values': [float(a.get('faltante', 0) or 0) for a in top],
        'etiqueta': 'faltante_unidades',
    }


def _tool_nomina_consolidado(params, ctx):
    # La nomina tiene gating inconsistente en asistencia_routes.py (mezcla
    # @require_role con checks manuales) -- no confiamos solo en que el
    # registro de tools ya filtro por rol y volvemos a validar aqui.
    if _normalizar_rol(ctx.get('role')) not in [r.upper() for r in ROL_ADMINS]:
        raise PermissionError("Esta consulta requiere rol administrativo.")
    division = ctx.get('tenant') or 'friparts'
    return {'division': division, 'colaboradores': nomina_service.get_consolidado_pendiente(division)}


# ── Definiciones (schema + rol + handler + tipo de grafica sugerido) ────────

def _enlace(pagina, etiqueta, seccion=None):
    """Boton 'ver en el modulo' que el frontend ofrece junto a la respuesta.
    'pagina' es el nombre que espera window.cargarPagina() (SPA existente, ya
    respeta permisos por rol); 'seccion' es un id opcional dentro de esa
    pagina para hacer scroll (solo tiene sentido dentro de 'dashboard', que
    es una sola pagina con varias secciones)."""
    return {'pagina': pagina, 'seccion': seccion, 'etiqueta': etiqueta}


def _target_periodo(nombre, params):
    """Resuelve el rango de fechas EXACTO al que responde una tool, para que el
    boton 'ver en el modulo' pueda sincronizar el filtro global del dashboard
    antes de navegar -- sin esto, el usuario podia preguntar por un mes distinto
    al filtro activo (ej. Julio con el dashboard filtrado en Agosto), hacer clic
    en el boton, y aterrizar en la seccion correcta pero con datos del filtro
    viejo todavia en pantalla.
    Devuelve (target_start, target_end) como 'YYYY-MM-DD' o (None, None) si la
    tool no tiene un periodo propio que sincronizar (ej. una consulta sin
    fechas como stock_critico, o una tool que no recibio fechas explicitas del
    modelo -- en ese caso el boton solo navega, sin tocar el filtro, igual que
    antes)."""
    params = params or {}
    desde = _fecha(params.get('desde'))
    hasta = _fecha(params.get('hasta'))
    if desde and hasta:
        return desde, hasta

    if nombre == 'desglose_ventas_mensual':
        try:
            mes = int(params.get('mes'))
            anio = int(params.get('anio'))
            if 1 <= mes <= 12:
                ultimo_dia = calendar.monthrange(anio, mes)[1]
                return f'{anio:04d}-{mes:02d}-01', f'{anio:04d}-{mes:02d}-{ultimo_dia:02d}'
        except (TypeError, ValueError):
            pass

    return None, None


TOOLS = {
    'ventas_periodo': {
        'description': "KPIs generales de ventas y produccion (inyeccion, pulido, ensamble, scrap, perdida por calidad) para un periodo de fechas. Usar para preguntas generales de 'cuanto vendimos/produjimos'.",
        'parameters': {
            'type': 'object',
            'properties': {
                'desde': {'type': 'string', 'description': 'Fecha inicio YYYY-MM-DD, opcional'},
                'hasta': {'type': 'string', 'description': 'Fecha fin YYYY-MM-DD, opcional'},
            },
            'required': [],
        },
        'allowed_roles': ROL_TODOS,
        'handler': _tool_ventas_periodo,
        'tipo_grafica': None,
        # Antes apuntaba a 'dashboard' sin seccion: si el usuario ya estaba en el
        # dashboard el boton no hacia nada visible. Apunta a la seccion real
        # donde vive el resumen de ventas/pedidos.
        'enlace': _enlace('dashboard', 'Ver Dashboard', 'dashboard-section-jefatura'),
    },
    'comparativo_mensual': {
        'description': (
            "Comparativo mensual de VENTAS (unidades y dinero facturado), anio actual vs "
            "anterior. Por defecto NO incluye pedidos -- para 'cuanto vendimos/se cerro/se "
            "factuo en el mes X' esto ya alcanza, no combines con otra tool de pedidos. Si la "
            "pregunta pide explicitamente comparar pedidos solicitados vs ventas facturadas, "
            "invoca con incluir_pedidos=true (asi el pedido y la venta vienen bien separados, "
            "en vez de tener que sumarlos vos mismo)."
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'desde': {'type': 'string', 'description': 'Fecha inicio YYYY-MM-DD, opcional'},
                'hasta': {'type': 'string', 'description': 'Fecha fin YYYY-MM-DD, opcional'},
                'incluir_pedidos': {
                    'type': 'boolean',
                    'description': (
                        "Poner en true SOLO si la pregunta pide explicitamente pedidos "
                        "solicitados ademas de ventas. Default false."
                    ),
                },
            },
            'required': [],
        },
        'allowed_roles': ROL_TODOS,
        'handler': _tool_comparativo_mensual,
        # 'bar' en vez de 'line': cuando la pregunta acota a un solo mes (caso mas
        # comun: "cuanto vendimos en julio"), una linea de 1 solo punto no se ve
        # (no hay 2do punto para trazar la linea) -- ver _serie_comparativo_mensual.
        'tipo_grafica': 'bar',
        'serie_grafica': _serie_comparativo_mensual,
        'enlace': _enlace('dashboard', 'Ver comparativo mensual', 'dashboard-section-jefatura'),
    },
    'desglose_ventas_mensual': {
        'description': (
            "Desglose de ventas de un mes especifico, por producto y por cliente. UNA sola "
            "llamada ya trae unidades Y dinero juntos para cada producto/cliente -- no hace "
            "falta llamarla dos veces con distinto tipo_vista para tener ambos datos."
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'mes': {'type': 'string', 'description': 'Numero de mes, 1-12'},
                'anio': {'type': 'string', 'description': 'Anio, ej 2026'},
                'tipo_vista': {
                    'type': 'string',
                    'description': (
                        "SOLO afecta el ORDEN de los resultados ('unidades' ordena por unidades "
                        "vendidas, 'money' por dinero) -- ambos campos vienen siempre en la "
                        "respuesta sin importar este valor. Opcional, default 'money'."
                    ),
                },
            },
            'required': ['mes', 'anio'],
        },
        'allowed_roles': ROL_ADMINS + ROL_COMERCIALES,
        'handler': _tool_desglose_ventas_mensual,
        'tipo_grafica': 'bar',
        'serie_grafica': _serie_desglose_ventas_mensual,
        'enlace': _enlace('dashboard', 'Ver desglose de ventas', 'dashboard-section-jefatura'),
    },
    'backorder_cliente': {
        'description': "Pedidos pendientes de despacho (backorder) de un cliente especifico.",
        'parameters': {
            'type': 'object',
            'properties': {
                'cliente': {'type': 'string', 'description': 'Nombre del cliente'},
                'desde': {'type': 'string', 'description': 'Fecha inicio YYYY-MM-DD, opcional'},
                'hasta': {'type': 'string', 'description': 'Fecha fin YYYY-MM-DD, opcional'},
            },
            'required': ['cliente'],
        },
        'allowed_roles': ROL_ADMINS + ROL_COMERCIALES,
        'handler': _tool_backorder_cliente,
        'tipo_grafica': 'table',
        'enlace': _enlace('dashboard', 'Ver Backorder', 'dashboard-section-incumplimiento'),
    },
    'ranking_operarios': {
        'description': (
            "Ranking de operarios de inyeccion o pulido por piezas OK producidas (campo "
            "'valor') y piezas no conformes ('pnc'). NO incluye un indicador de eficiencia "
            "confiable -- si preguntan por eficiencia/rendimiento porcentual de un operario, "
            "aclarar que no esta disponible, no inferirlo de 'valor' ni 'pnc'."
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'area': {'type': 'string', 'description': "'inyeccion' o 'pulido'"},
                'desde': {'type': 'string', 'description': 'Fecha inicio YYYY-MM-DD, opcional'},
                'hasta': {'type': 'string', 'description': 'Fecha fin YYYY-MM-DD, opcional'},
            },
            'required': [],
        },
        'allowed_roles': ROL_TODOS,
        'handler': _tool_ranking_operarios,
        'tipo_grafica': 'bar',
        'serie_grafica': _serie_ranking_operarios,
        'enlace': _enlace('dashboard', 'Ver ranking de operarios', 'dashboard-section-pulido-kpis'),
    },
    'produccion_por_maquina': {
        'description': "Produccion acumulada de cada maquina de inyeccion (total, dias trabajados, promedio, estado).",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_TODOS,
        'handler': _tool_produccion_por_maquina,
        'tipo_grafica': 'bar',
        'serie_grafica': _serie_produccion_por_maquina,
        'enlace': _enlace('dashboard', 'Ver producción por máquina', 'dashboard-section-inyeccion'),
    },
    'scrap_detalle': {
        'description': "Detalle de piezas de scrap/mermas (fecha y maquina de origen) para una referencia de producto especifica.",
        'parameters': {
            'type': 'object',
            'properties': {
                'id_codigo': {'type': 'string', 'description': 'Codigo del producto, ej FR-9380'},
                'desde': {'type': 'string', 'description': 'Fecha inicio YYYY-MM-DD, opcional'},
                'hasta': {'type': 'string', 'description': 'Fecha fin YYYY-MM-DD, opcional'},
            },
            'required': ['id_codigo'],
        },
        'allowed_roles': ROL_TODOS,
        'handler': _tool_scrap_detalle,
        'tipo_grafica': 'table',
        'enlace': _enlace('dashboard', 'Ver tendencia de scrap', 'dashboard-section-tendencia'),
    },
    'productos_sin_rotacion': {
        'description': "Productos de baja o nula rotacion en los ultimos 12 meses.",
        'parameters': {
            'type': 'object',
            'properties': {
                'q': {'type': 'string', 'description': 'Filtro de busqueda por codigo o descripcion, opcional'},
                'max_ventas': {'type': 'integer', 'description': 'Umbral maximo de unidades vendidas, 0-50'},
            },
            'required': [],
        },
        'allowed_roles': ROL_TODOS,
        'handler': _tool_productos_sin_rotacion,
        'tipo_grafica': 'table',
        'enlace': _enlace('dashboard', 'Ver productos sin rotación', 'dashboard-section-sin-rotacion'),
    },
    'cartera_estado': {
        'description': (
            "Cartera / cuentas por cobrar POR CLIENTE con edades de mora (corriente, 1-30, "
            "31-60, 61-90, mas de 90 dias) y vendedor asignado. Usar para preguntas de que "
            "cliente debe mas, quien tiene mora vieja, o el estado general de cartera. Si la "
            "pregunta menciona zonas o vendedores especificos, combinar con 'analitica_comercial'."
        ),
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_ADMINS + ROL_COMERCIALES,
        'handler': _tool_cartera_estado,
        'tipo_grafica': 'bar',
        'serie_grafica': _serie_cartera_estado,
        'enlace': _enlace('cartera', 'Ver módulo de Cartera'),
    },
    'pnc_metricas': {
        'description': "Metricas de calidad / PNC (piezas no conformes) consolidadas de inyeccion, pulido y ensamble para un periodo.",
        'parameters': {
            'type': 'object',
            'properties': {
                'desde': {'type': 'string', 'description': 'Fecha inicio YYYY-MM-DD, opcional'},
                'hasta': {'type': 'string', 'description': 'Fecha fin YYYY-MM-DD, opcional'},
            },
            'required': [],
        },
        'allowed_roles': ROL_TODOS,
        'handler': _tool_pnc_metricas,
        'tipo_grafica': 'table',
        'enlace': _enlace('pnc', 'Ver módulo de PNC'),
    },
    'stock_producto': {
        'description': "Ficha y stock actual de un producto especifico, buscado por su codigo.",
        'parameters': {
            'type': 'object',
            'properties': {
                'codigo': {'type': 'string', 'description': 'Codigo o referencia del producto'},
            },
            'required': ['codigo'],
        },
        'allowed_roles': ROL_TODOS,
        'handler': _tool_stock_producto,
        'tipo_grafica': None,
        'enlace': _enlace('inventario', 'Ver Inventario'),
    },
    'stock_critico': {
        'description': "Lista de productos que estan por debajo de su nivel minimo de stock.",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_TODOS,
        'handler': _tool_stock_critico,
        'tipo_grafica': 'table',
        'enlace': _enlace('inventario', 'Ver Inventario'),
    },
    'analitica_comercial': {
        'description': (
            "Analitica historica de ventas por anio, por ZONA (resumen_zonas) y top clientes "
            "(top_clientes). Si quien pregunta es ADMIN/GERENCIA ve la vista global de toda la "
            "empresa; si es un vendedor (rol COMERCIAL), ve SOLO sus propios clientes/ventas -- "
            "no sirve para consultar las cifras de otro vendedor. Usar para preguntas de ventas "
            "por zona, evolucion anual, o para complementar una pregunta de cartera que mencione "
            "zonas o vendedores."
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'anio_desde': {'type': 'integer', 'description': 'Anio inicial, ej 2024'},
                'anio_hasta': {'type': 'integer', 'description': 'Anio final, ej 2026'},
            },
            'required': [],
        },
        'allowed_roles': ROL_ADMINS + ROL_COMERCIALES,
        'handler': _tool_analitica_comercial,
        'tipo_grafica': 'line',
        'serie_grafica': _serie_analitica_comercial,
        'enlace': _enlace('comercial-historico', 'Ver Analítica Comercial'),
    },
    'nomina_consolidado': {
        'description': "Horas ordinarias y extras PENDIENTES de pago por colaborador. Solo disponible para administracion.",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_ADMINS,
        'handler': _tool_nomina_consolidado,
        'tipo_grafica': 'table',
        'enlace': _enlace('asistencia', 'Ver módulo de Asistencia'),
    },
    'pedidos_pendientes_facturacion': {
        'description': "Pedidos en estado PENDIENTE de facturar/despachar (agrupados por pedido, con cliente, vendedor y total). Usar para preguntas de 'que pedidos faltan por facturar/alistar'.",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_ADMINS + ROL_JEFES,
        'handler': _tool_pedidos_pendientes_facturacion,
        'tipo_grafica': 'table',
        'enlace': _enlace('facturacion', 'Ver módulo de Facturación'),
    },
    'alertas_abastecimiento': {
        'description': "Productos cuyo stock en bodega esta por debajo del minimo configurado (alertas de compra/abastecimiento).",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_ADMINS + ROL_JEFES,
        'handler': _tool_alertas_abastecimiento,
        'tipo_grafica': 'bar',
        'serie_grafica': _serie_alertas_abastecimiento,
        'enlace': _enlace('procura', 'Ver módulo de Procura'),
    },
    'programacion_maquinas': {
        'description': "Estado actual de cada maquina de inyeccion: que esta trabajando ahora mismo y que hay en cola de programacion (MES). Usar para 'que esta programado/trabajando en las maquinas'.",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_TODOS,
        'handler': _tool_programacion_maquinas,
        'tipo_grafica': 'table',
        'enlace': _enlace('inyeccion', 'Ver Inyección (MES)'),
    },
    'ensamble_tareas_pendientes': {
        'description': "Tareas de ensamble programadas que aun no estan completadas (cantidad objetivo vs realizada, faltante, fecha programada).",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_TODOS,
        'handler': _tool_ensamble_tareas_pendientes,
        'tipo_grafica': 'table',
        'enlace': _enlace('ensamble', 'Ver módulo de Ensamble'),
    },
}


def tools_visibles_para_rol(role):
    """Filtra el registro de tools segun el rol del usuario -- una tool que el
    rol no puede usar ni siquiera se declara al modelo (defensa en profundidad,
    ademas de la re-validacion que hace ejecutar_tool)."""
    role_norm = _normalizar_rol(role)
    return {
        name: tool for name, tool in TOOLS.items()
        if _rol_autorizado(role_norm, tool['allowed_roles'])
    }


def ejecutar_tool(nombre, params, ctx):
    """Valida rol + existencia y ejecuta el handler real. ctx = {user, user_id, role, tenant}.
    Retorna (datos, tipo_grafica, serie_grafica, enlace). serie_grafica ya viene con el campo
    correcto identificado explicitamente (ver comentario sobre jsonify sort_keys arriba),
    o None si la tool no tiene extractor definido o no aplica graficar. enlace es un dict
    {pagina, seccion, etiqueta} para que el frontend ofrezca un boton "ver en el modulo",
    o None si la tool no tiene un modulo real asociado en la UI."""
    tool = TOOLS.get(nombre)
    if not tool:
        raise ValueError(f"Tool desconocida: {nombre}")

    role_norm = _normalizar_rol(ctx.get('role'))
    if not _rol_autorizado(role_norm, tool['allowed_roles']):
        raise PermissionError(f"El rol actual no tiene acceso a la consulta '{nombre}'.")

    datos = tool['handler'](params or {}, ctx)

    serie = None
    extractor = tool.get('serie_grafica')
    if extractor:
        try:
            serie = extractor(datos)
        except Exception as e:
            logger.warning(f"[Asistente] No se pudo extraer serie de grafica de '{nombre}': {e}")

    enlace = tool.get('enlace')
    if enlace:
        target_start, target_end = _target_periodo(nombre, params)
        if target_start and target_end:
            # Copia nueva -- 'enlace' es el dict ESTATICO definido en TOOLS y se
            # comparte entre todas las peticiones concurrentes; mutarlo in-place
            # filtrarian las fechas de una consulta a la respuesta de otro usuario.
            enlace = {**enlace, 'target_start': target_start, 'target_end': target_end}

    return datos, tool.get('tipo_grafica'), serie, enlace
