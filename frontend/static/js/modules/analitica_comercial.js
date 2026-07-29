/**
 * Módulo JavaScript: Crecimiento Interanual (YoY) por Cliente y Zona
 * REGLA INFLEXIBLE: CERO cálculos matemáticos en cliente.
 * Solo recibe el JSON ya calculado por el backend (venta_anio_base, venta_anio_comp,
 * variacion_cop, crecimiento_pct, clasificacion, es_nuevo) y lo renderiza en el DOM.
 * `clasificacion` decide el badge: NUEVO (azul), REACTIVADO (amarillo),
 * SIN_VENTA_EN_VENTANA (gris, con tooltip) o ACTIVO (% de crecimiento normal).
 *
 * Estructura HTML esperada en la plantilla que use este módulo:
 *   - <select id="filter-anio-base">     (año de comparación base)
 *   - <select id="filter-anio-comp">     (año a comparar)
 *   - <select id="filter-zona-crecimiento"> (opciones = claves de MAPEO_ZONAS + "Todas")
 *   - <input id="switch-ytd-crecimiento" type="checkbox">  (corte YTD hasta hoy en ambos años)
 *   - <span id="badge-ytd-info">  (leyenda "Comparando del 01-01 al MM-DD..." cuando ytd_aplicado=true)
 *   - <input id="input-search-crecimiento">  (búsqueda por nombre de cliente, server-side)
 *   - <button id="btn-refresh-crecimiento">
 *   - <tbody id="tbody-crecimiento">
 *   - <button id="tab-crecimiento-btn" data-bs-toggle="tab"> (dispara la carga perezosa al abrirse)
 *
 * Carga perezosa: NO se dispara ningún fetch al cargar la página histórica.
 * El primer cálculo solo ocurre cuando el usuario abre la pestaña "Crecimiento
 * Interanual" (evento shown.bs.tab) o hace clic explícito en "Cargar Analítica".
 */

document.addEventListener('DOMContentLoaded', () => {
    AnaliticaComercialModule.init();
});

const AnaliticaComercialModule = (() => {
    let yaCargadoInicial = false;
    let debounceTimer = null;
    let terminoBusqueda = '';

    const currencyFormatter = new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        maximumFractionDigits: 0
    });

    const debounce = (fn, delayMs) => (...args) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => fn(...args), delayMs);
    };

    // Solo registra listeners: cero llamadas de red al cargar la página histórica.
    const init = () => {
        setupEventListeners();
    };

    const setupEventListeners = () => {
        const btnRefresh = document.getElementById('btn-refresh-crecimiento');
        const anioBaseSelect = document.getElementById('filter-anio-base');
        const anioCompSelect = document.getElementById('filter-anio-comp');
        const zonaSelect = document.getElementById('filter-zona-crecimiento');
        const switchYtd = document.getElementById('switch-ytd-crecimiento');
        const inputSearch = document.getElementById('input-search-crecimiento');
        const tabCrecimientoBtn = document.getElementById('tab-crecimiento-btn');

        if (btnRefresh) btnRefresh.addEventListener('click', cargarCrecimiento);
        if (anioBaseSelect) anioBaseSelect.addEventListener('change', cargarCrecimiento);
        if (zonaSelect) zonaSelect.addEventListener('change', cargarCrecimiento);
        if (switchYtd) switchYtd.addEventListener('change', cargarCrecimiento);

        // Sincroniza el switch con el año de comparación ya seleccionado al cargar
        // la pestaña (antes de la primera consulta), no solo tras un 'change' futuro.
        if (anioCompSelect && switchYtd) {
            const anioActual = new Date().getFullYear();
            switchYtd.checked = (Number(anioCompSelect.value) === anioActual);
        }

        // Si el usuario selecciona el año en curso como año de comparación, activa
        // el switch YTD automáticamente (evita comparar 12 meses vs un año parcial
        // sin que el usuario tenga que acordarse de marcarlo). Año anterior lo desmarca.
        if (anioCompSelect) {
            anioCompSelect.addEventListener('change', () => {
                if (switchYtd) {
                    const anioActual = new Date().getFullYear();
                    switchYtd.checked = (Number(anioCompSelect.value) === anioActual);
                }
                cargarCrecimiento();
            });
        }

        // Debounce: la búsqueda corre en PostgreSQL (ILIKE), no se filtra el array en el cliente.
        if (inputSearch) {
            const buscarDebounced = debounce(() => {
                terminoBusqueda = inputSearch.value.trim();
                cargarCrecimiento();
            }, 300);
            inputSearch.addEventListener('input', buscarDebounced);
        }

        // Bootstrap dispara 'shown.bs.tab' en el trigger (el <button data-bs-toggle="tab">)
        // cuando el usuario abre la pestaña por primera vez.
        if (tabCrecimientoBtn) {
            tabCrecimientoBtn.addEventListener('shown.bs.tab', initAnaliticaCrecimiento);
        }
    };

    // Punto de entrada explícito para la carga perezosa: se dispara solo al abrir
    // la pestaña (una vez) o al hacer clic en "Cargar Analítica". Nunca en DOMContentLoaded.
    const initAnaliticaCrecimiento = () => {
        if (yaCargadoInicial) return;
        yaCargadoInicial = true;
        cargarCrecimiento();
    };

    const getAuthHeaders = () => {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token') || urlParams.get('pwa_token') || localStorage.getItem('pwa_token') || localStorage.getItem('token') || sessionStorage.getItem('token') || '';
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        return { headers, token };
    };

    const getFiltros = () => {
        const anioActual = new Date().getFullYear();
        return {
            anioBase: document.getElementById('filter-anio-base')?.value || (anioActual - 1),
            anioComp: document.getElementById('filter-anio-comp')?.value || anioActual,
            zona: document.getElementById('filter-zona-crecimiento')?.value || ''
        };
    };

    const cargarCrecimiento = async () => {
        const { anioBase, anioComp, zona } = getFiltros();
        const switchYtd = document.getElementById('switch-ytd-crecimiento');
        mostrarEstadoCargando();

        try {
            const { headers, token } = getAuthHeaders();
            const params = new URLSearchParams({
                anio_base: anioBase,
                anio_comparacion: anioComp,
                zona,
                busqueda: terminoBusqueda,
                ytd: switchYtd ? switchYtd.checked : false,
                token
            });
            const response = await fetch(`/api/comercial/crecimiento-clientes?${params.toString()}`, { headers });
            const data = await response.json();

            if (!data.success) {
                console.error('Error al cargar crecimiento de clientes:', data.error);
                mostrarError(data.error || 'Error desconocido');
                return;
            }

            renderBadgeYtd(data.periodo);
            renderTablaCrecimiento(data.clientes || []);

        } catch (error) {
            console.error('Error en la llamada AJAX (crecimiento-clientes):', error);
            mostrarError('Fallo en la comunicación con el servidor');
        }
    };

    // Leyenda informativa: el backend decide si el corte YTD se aplicó (ya sea por
    // el switch o por el fallback automático de la ruta) — el frontend solo la pinta.
    const renderBadgeYtd = (periodo) => {
        const badge = document.getElementById('badge-ytd-info');
        if (!badge) return;

        if (periodo && periodo.ytd_aplicado) {
            badge.textContent = `Comparando del 01-01 al ${periodo.limite_mmdd} de cada año`;
            badge.classList.remove('d-none');
        } else {
            badge.textContent = '';
            badge.classList.add('d-none');
        }
    };

    // Formatea el % ya calculado por el backend: signo explícito y color por umbral en cero.
    const formatCrecimientoPct = (crecimientoPct) => {
        const valor = Number(crecimientoPct || 0);
        const signo = valor > 0 ? '+' : '';
        const claseColor = valor >= 0 ? 'text-success' : 'text-danger';
        const icono = valor >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
        return `<span class="fw-bold ${claseColor}"><i class="fas ${icono} me-1"></i>${signo}${valor.toFixed(1)}%</span>`;
    };

    // El backend ya resolvió la clasificación (NUEVO/REACTIVADO/SIN_VENTA_EN_VENTANA/ACTIVO);
    // el frontend solo elige el badge, cero lógica de negocio aquí.
    const renderEstadoCliente = (c) => {
        switch (c.clasificacion) {
            case 'NUEVO':
                return '<span class="badge bg-primary" title="Nunca había comprado antes de este año">NUEVO</span>';
            case 'REACTIVADO':
                return '<span class="badge bg-warning text-dark" title="Compraba antes, se saltó el año base">REACTIVADO</span>';
            case 'SIN_VENTA_EN_VENTANA':
                return '<span class="badge bg-secondary" title="Compró en el año base pero después del corte aplicado">SIN COMPRA EN VENTANA</span>';
            case 'ACTIVO':
            default:
                return formatCrecimientoPct(c.crecimiento_pct);
        }
    };

    const renderTablaCrecimiento = (clientes) => {
        const tbody = document.getElementById('tbody-crecimiento');
        if (!tbody) return;

        if (!clientes || clientes.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-3">No hay datos de crecimiento para el periodo/zona seleccionados.</td></tr>`;
            return;
        }

        tbody.innerHTML = clientes.map(c => `
            <tr>
                <td class="text-muted small">${c.cliente_nit || '—'}</td>
                <td class="fw-medium">${c.cliente_nombre}</td>
                <td><i class="fas fa-map-pin me-1 text-primary small"></i>${c.zona_region}</td>
                <td class="text-end text-muted">${currencyFormatter.format(c.venta_anio_base)}</td>
                <td class="text-end fw-bold">${currencyFormatter.format(c.venta_anio_comp)}</td>
                <td class="text-end ${c.variacion_cop >= 0 ? 'text-success' : 'text-danger'}">${currencyFormatter.format(c.variacion_cop)}</td>
                <td class="text-end">${renderEstadoCliente(c)}</td>
            </tr>
        `).join('');
    };

    const mostrarEstadoCargando = () => {
        const tbody = document.getElementById('tbody-crecimiento');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted"><i class="fas fa-spinner fa-spin me-2"></i>Calculando crecimiento interanual...</td></tr>`;
        }
    };

    const mostrarError = (mensaje) => {
        const tbody = document.getElementById('tbody-crecimiento');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-4"><i class="fas fa-exclamation-triangle me-2"></i>${mensaje}</td></tr>`;
        }
    };

    return { init };
})();
