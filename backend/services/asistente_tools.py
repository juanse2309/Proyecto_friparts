"""
Registro de "tools" del Asistente de Dashboard.

Cada tool envuelve un metodo YA EXISTENTE de un repositorio/servicio. El LLM
solo puede invocar estos nombres con estos parametros tipados (fechas, codigos,
nombres); nunca genera SQL ni nombres de columna/tabla. Esto es la defensa
principal contra inyeccion: el modelo elige QUE tool llamar y con que
argumentos, pero el SQL que se ejecuta ya estaba escrito y probado de antemano.
"""
import logging
import unicodedata
from datetime import datetime

from backend.repositories.dashboard_repository import DashboardRepository
from backend.repositories.ventas_repository import VentasRepository
from backend.repositories.producto_repository import producto_repo
from backend.services.dashboard_service import DashboardService
from backend.services.pnc_service import PncService
from backend.services.comercial_service import ComercialHistoricoService
from backend.services import nomina_service
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
        'ventas_totales': kpis.get('ventas_totales', 0),
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
    return DashboardRepository.get_monthly_performance_comparison(desde, hasta)


def _tool_desglose_ventas_mensual(params, ctx):
    mes = params.get('mes')
    anio = params.get('anio')
    tipo_vista = params.get('tipo_vista') or 'money'
    if not mes or not anio:
        raise ValueError("Se requieren 'mes' y 'anio' para el desglose mensual de ventas.")
    return VentasRepository.get_desglose_mensual_ventas(mes, anio, tipo_vista)


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
        return {'area': 'pulido', 'ranking': DashboardRepository.get_ranking_operarios_pulido(desde, hasta)}
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
    return DashboardService.get_productos_sin_rotacion(q=q, max_ventas=max_ventas)


def _tool_cartera_estado(params, ctx):
    return DashboardService.get_cartera_wo_stats()


def _tool_pnc_metricas(params, ctx):
    desde = _fecha(params.get('desde'))
    hasta = _fecha(params.get('hasta'))
    return PncService.obtener_metricas_pnc_consolidadas(desde, hasta)


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
    return ComercialHistoricoService.obtener_analitica_historica(
        user_id=ctx['user_id'],
        username=ctx['user'],
        user_role=ctx['role'],
        start_year=anio_desde,
        end_year=anio_hasta,
    )


# ── Extractores de serie graficable (corren en Python, ANTES de json.dumps) ──
# jsonify ordena las claves alfabeticamente por defecto en esta version de Flask,
# asi que "la primera clave numerica" deja de identificar de forma fiable el campo
# correcto (ej. 'eficiencia' quedaba antes que 'valor' tras el sort). Estos
# extractores fijan explicitamente que campo es la metrica a graficar, en vez de
# adivinarlo del lado del frontend.

def _serie_comparativo_mensual(datos):
    mensual = datos.get('mensual') or []
    if not mensual:
        return None
    return {
        'labels': [m.get('mes', '') for m in mensual],
        'values': [float(m.get('actual_dinero', 0) or 0) for m in mensual],
        'etiqueta': 'ventas_mes_actual',
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
    productos = datos.get('productos') or []
    if not productos:
        return None
    ordenado = sorted(productos, key=lambda p: float(p.get('total_ventas', 0) or 0), reverse=True)[:10]
    return {
        'labels': [p.get('id_codigo') or p.get('descripcion') or '' for p in ordenado],
        'values': [float(p.get('total_ventas', 0) or 0) for p in ordenado],
        'etiqueta': 'total_ventas',
    }


def _serie_analitica_comercial(datos):
    resumen = datos.get('resumen_anual') or []
    if not resumen:
        return None
    return {
        'labels': [str(r.get('anio', '')) for r in resumen],
        'values': [float(r.get('total_ventas', 0) or 0) for r in resumen],
        'etiqueta': 'total_ventas',
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
    },
    'comparativo_mensual': {
        'description': "Comparativo mensual de ventas vs pedidos, anio actual vs anterior. Usar para preguntas de tendencia o evolucion mes a mes.",
        'parameters': {
            'type': 'object',
            'properties': {
                'desde': {'type': 'string', 'description': 'Fecha inicio YYYY-MM-DD, opcional'},
                'hasta': {'type': 'string', 'description': 'Fecha fin YYYY-MM-DD, opcional'},
            },
            'required': [],
        },
        'allowed_roles': ROL_TODOS,
        'handler': _tool_comparativo_mensual,
        'tipo_grafica': 'line',
        'serie_grafica': _serie_comparativo_mensual,
    },
    'desglose_ventas_mensual': {
        'description': "Desglose de ventas de un mes especifico, por producto y por cliente.",
        'parameters': {
            'type': 'object',
            'properties': {
                'mes': {'type': 'string', 'description': 'Numero de mes, 1-12'},
                'anio': {'type': 'string', 'description': 'Anio, ej 2026'},
                'tipo_vista': {'type': 'string', 'description': "'money' o 'unidades'"},
            },
            'required': ['mes', 'anio'],
        },
        'allowed_roles': ROL_ADMINS + ROL_COMERCIALES,
        'handler': _tool_desglose_ventas_mensual,
        'tipo_grafica': 'bar',
        'serie_grafica': _serie_desglose_ventas_mensual,
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
    },
    'ranking_operarios': {
        'description': "Ranking de operarios de inyeccion o pulido por piezas OK producidas.",
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
    },
    'produccion_por_maquina': {
        'description': "Produccion acumulada de cada maquina de inyeccion (total, dias trabajados, promedio, estado).",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_TODOS,
        'handler': _tool_produccion_por_maquina,
        'tipo_grafica': 'bar',
        'serie_grafica': _serie_produccion_por_maquina,
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
    },
    'cartera_estado': {
        'description': "Estado de cartera / cuentas por cobrar: total, vencida y clientes con mayor saldo vencido.",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_ADMINS + ROL_COMERCIALES,
        'handler': _tool_cartera_estado,
        'tipo_grafica': 'table',
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
    },
    'stock_critico': {
        'description': "Lista de productos que estan por debajo de su nivel minimo de stock.",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_TODOS,
        'handler': _tool_stock_critico,
        'tipo_grafica': 'table',
    },
    'analitica_comercial': {
        'description': "Analitica historica de ventas DEL VENDEDOR QUE ESTA PREGUNTANDO (sus propios clientes/ventas), por rango de anios. No sirve para consultar las cifras de otro vendedor.",
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
    },
    'nomina_consolidado': {
        'description': "Horas ordinarias y extras PENDIENTES de pago por colaborador. Solo disponible para administracion.",
        'parameters': {'type': 'object', 'properties': {}, 'required': []},
        'allowed_roles': ROL_ADMINS,
        'handler': _tool_nomina_consolidado,
        'tipo_grafica': 'table',
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
    Retorna (datos, tipo_grafica, serie_grafica). serie_grafica ya viene con el campo
    correcto identificado explicitamente (ver comentario sobre jsonify sort_keys arriba),
    o None si la tool no tiene extractor definido o no aplica graficar."""
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

    return datos, tool.get('tipo_grafica'), serie
