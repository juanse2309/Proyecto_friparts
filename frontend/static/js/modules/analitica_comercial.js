/**
 * Módulo JavaScript: Crecimiento Interanual (YoY) por Cliente y Zona
 * REGLA INFLEXIBLE: CERO cálculos matemáticos en cliente.
 * Solo recibe el JSON ya calculado por el backend (venta_anio_base, venta_anio_comp,
 * variacion_cop, crecimiento_pct, es_nuevo) y lo renderiza en el DOM.
 *
 * Estructura HTML esperada en la plantilla que use este módulo:
 *   - <select id="filter-anio-base">     (año de comparación base)
 *   - <select id="filter-anio-comp">     (año a comparar)
 *   - <select id="filter-zona-crecimiento"> (opciones = claves de MAPEO_ZONAS + "Todas")
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
        const inputSearch = document.getElementById('input-search-crecimiento');
        const tabCrecimientoBtn = document.getElementById('tab-crecimiento-btn');

        if (btnRefresh) btnRefresh.addEventListener('click', cargarCrecimiento);
        if (anioBaseSelect) anioBaseSelect.addEventListener('change', cargarCrecimiento);
        if (anioCompSelect) anioCompSelect.addEventListener('change', cargarCrecimiento);
        if (zonaSelect) zonaSelect.addEventListener('change', cargarCrecimiento);

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
        mostrarEstadoCargando();

        try {
            const { headers, token } = getAuthHeaders();
            const params = new URLSearchParams({
                anio_base: anioBase,
                anio_comparacion: anioComp,
                zona,
                busqueda: terminoBusqueda,
                token
            });
            const response = await fetch(`/api/comercial/crecimiento-clientes?${params.toString()}`, { headers });
            const data = await response.json();

            if (!data.success) {
                console.error('Error al cargar crecimiento de clientes:', data.error);
                mostrarError(data.error || 'Error desconocido');
                return;
            }

            renderTablaCrecimiento(data.clientes || []);

        } catch (error) {
            console.error('Error en la llamada AJAX (crecimiento-clientes):', error);
            mostrarError('Fallo en la comunicación con el servidor');
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
                <td class="text-end">${c.es_nuevo ? '<span class="badge bg-info">NUEVO</span>' : formatCrecimientoPct(c.crecimiento_pct)}</td>
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
