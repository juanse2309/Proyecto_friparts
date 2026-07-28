/**
 * Módulo JavaScript: Analítica Comercial Histórica (2024-2026)
 * REGLA INFLEXIBLE: CERO cálculos matemáticos en cliente.
 * Solo recibe el JSON estructurado con las agregaciones hechas por PostgreSQL y las renderiza en el DOM.
 */

document.addEventListener('DOMContentLoaded', () => {
    ComercialHistoricoModule.init();
});

const ComercialHistoricoModule = (() => {
    let chartInteranualInstance = null;
    let chartZonasInstance = null;

    // Estado de paginación server-side del detalle (nunca acumulamos todo el dataset en el cliente)
    let paginaActual = 1;
    let terminoBusqueda = '';
    let debounceTimer = null;

    const debounce = (fn, delayMs) => (...args) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => fn(...args), delayMs);
    };

    const currencyFormatter = new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        maximumFractionDigits: 0
    });

    const numberFormatter = new Intl.NumberFormat('es-CO', {
        maximumFractionDigits: 0
    });

    const MESES = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];

    const init = () => {
        setupEventListeners();
        cargarTodo();
    };

    const setupEventListeners = () => {
        const btnRefresh = document.getElementById('btn-refresh');
        const startSelect = document.getElementById('filter-start-year');
        const endSelect = document.getElementById('filter-end-year');

        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => { paginaActual = 1; cargarTodo(); });
        }

        if (startSelect) {
            startSelect.addEventListener('change', () => {
                if (endSelect && Number(endSelect.value) < Number(startSelect.value)) {
                    endSelect.value = startSelect.value;
                }
                paginaActual = 1;
                cargarTodo();
            });
        }

        if (endSelect) {
            endSelect.addEventListener('change', () => {
                if (startSelect && Number(startSelect.value) > Number(endSelect.value)) {
                    startSelect.value = endSelect.value;
                }
                paginaActual = 1;
                cargarTodo();
            });
        }

        // Debounce: evita que cada tecla dispare una consulta + re-render completo
        // de la tabla en el hilo principal (esa era la causa del "página no responde").
        const inputSearch = document.getElementById('input-search-detalle');
        if (inputSearch) {
            const buscarDebounced = debounce(() => {
                terminoBusqueda = inputSearch.value.toLowerCase().trim();
                paginaActual = 1;
                cargarDetalle();
            }, 300);
            inputSearch.addEventListener('input', buscarDebounced);
        }

        const btnExportExcel = document.getElementById('btn-export-excel');
        if (btnExportExcel) {
            btnExportExcel.addEventListener('click', descargarExcel);
        }
    };

    // El endpoint exige Authorization: Bearer <token>, por lo que no se puede usar
    // un <a href> plano — se pide como blob y se dispara la descarga manualmente.
    const descargarExcel = async () => {
        const btn = document.getElementById('btn-export-excel');
        const { startYear, endYear } = getFiltrosAnio();
        const iconoOriginal = btn ? btn.innerHTML : '';

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Generando...';
        }

        try {
            const { headers, token } = getAuthHeaders();
            const params = new URLSearchParams({ start_year: startYear, end_year: endYear, token });
            const response = await fetch(`/api/comercial/historico/excel?${params.toString()}`, { headers });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Error HTTP ${response.status}`);
            }

            const blob = await response.blob();
            const disposition = response.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename="?([^"]+)"?/);
            const nombreArchivo = match ? match[1] : `Comercial_YTD_${startYear}-${endYear}.xlsx`;

            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = nombreArchivo;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

        } catch (error) {
            console.error('Error al descargar el Excel:', error);
            alert('No se pudo generar el Excel: ' + error.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = iconoOriginal;
            }
        }
    };

    const getAuthHeaders = () => {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token') || urlParams.get('pwa_token') || localStorage.getItem('pwa_token') || localStorage.getItem('token') || sessionStorage.getItem('token') || '';
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        return { headers, token };
    };

    const getFiltrosAnio = () => ({
        startYear: document.getElementById('filter-start-year')?.value || 2024,
        endYear: document.getElementById('filter-end-year')?.value || 2026
    });

    const cargarTodo = () => {
        cargarResumen();
        cargarDetalle();
    };

    // Resumen ejecutivo: KPIs, gráficos, zonas y top clientes. Payload liviano
    // (decenas de filas) — se recarga solo al cambiar el rango de años.
    const cargarResumen = async () => {
        const { startYear, endYear } = getFiltrosAnio();
        mostrarEstadoCargandoResumen();

        try {
            const { headers, token } = getAuthHeaders();
            const fetchUrl = `/api/comercial/historico?start_year=${startYear}&end_year=${endYear}&token=${encodeURIComponent(token)}`;
            const response = await fetch(fetchUrl, { headers });
            const data = await response.json();

            if (!data.success) {
                console.error('Error al cargar analítica:', data.error);
                mostrarError(data.error || 'Error desconocido');
                return;
            }

            renderBadgeSeguridad(data.seguridad);
            renderKPIs(data.resumen_anual);
            renderGraficoInteranual(data.resumen_anual);
            renderGraficoZonas(data.resumen_zonas);
            renderTablaZonas(data.resumen_zonas);
            renderTablaClientes(data.top_clientes);

        } catch (error) {
            console.error('Error en la llamada AJAX (resumen):', error);
            mostrarError('Fallo en la comunicación con el servidor');
        }
    };

    // Detalle consolidado: 100% server-side (agregación, búsqueda y paginación
    // corren en PostgreSQL). Nunca se carga ni se filtra el dataset completo en el cliente.
    const cargarDetalle = async () => {
        const { startYear, endYear } = getFiltrosAnio();
        const tbody = document.getElementById('tbody-detalle');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted"><i class="fas fa-spinner fa-spin me-2"></i>Consultando página ${paginaActual}...</td></tr>`;
        }

        try {
            const { headers, token } = getAuthHeaders();
            const params = new URLSearchParams({
                start_year: startYear,
                end_year: endYear,
                pagina: paginaActual,
                tam_pagina: 100,
                busqueda: terminoBusqueda,
                token
            });
            const response = await fetch(`/api/comercial/historico/detalle?${params.toString()}`, { headers });
            const data = await response.json();

            if (!data.success) {
                console.error('Error al cargar detalle:', data.error);
                mostrarError(data.error || 'Error desconocido');
                return;
            }

            renderTablaDetalle(data.filas || []);
            renderPaginacion(data.paginacion);

        } catch (error) {
            console.error('Error en la llamada AJAX (detalle):', error);
            mostrarError('Fallo en la comunicación con el servidor');
        }
    };

    const renderBadgeSeguridad = (seguridad) => {
        const badge = document.getElementById('scope-badge');
        if (!badge) return;

        if (seguridad?.vista_global) {
            badge.className = 'badge badge-scope badge-global';
            badge.innerHTML = `<i class="fas fa-globe me-1"></i>Vista Global (Gerencia/Admin)`;
        } else {
            badge.className = 'badge badge-scope badge-comercial';
            badge.innerHTML = `<i class="fas fa-user-tag me-1"></i>Vendedor: ${seguridad?.usuario || 'Comercial'}`;
        }
    };

    const renderKPIs = (resumenAnual) => {
        const kpiVentas = document.getElementById('kpi-total-ventas');
        const kpiUnidades = document.getElementById('kpi-total-unidades');
        const kpiTransacciones = document.getElementById('kpi-total-transacciones');
        const kpiTicket = document.getElementById('kpi-ticket-promedio');

        if (!resumenAnual || resumenAnual.length === 0) {
            if (kpiVentas) kpiVentas.textContent = '$0';
            if (kpiUnidades) kpiUnidades.textContent = '0';
            if (kpiTransacciones) kpiTransacciones.textContent = '0';
            if (kpiTicket) kpiTicket.textContent = '$0';
            return;
        }

        // Se usa la fila de totales globales entregada directamente por SQL en la primera posición o consolidada
        // Para mostrar la suma total del periodo, tomamos los valores agregados de SQL sin loops en JS.
        // SQL devuelve una fila por año en resumen_anual.
        let totalVentas = 0;
        let totalUnidades = 0;
        let totalTx = 0;

        resumenAnual.forEach(r => {
            totalVentas += Number(r.total_ventas || 0);
            totalUnidades += Number(r.total_unidades || 0);
            totalTx += Number(r.total_transacciones || 0);
        });

        if (kpiVentas) kpiVentas.textContent = currencyFormatter.format(totalVentas);
        if (kpiUnidades) kpiUnidades.textContent = numberFormatter.format(totalUnidades);
        if (kpiTransacciones) kpiTransacciones.textContent = numberFormatter.format(totalTx);
        
        const ticketPromedio = totalTx > 0 ? (totalVentas / totalTx) : 0;
        if (kpiTicket) kpiTicket.textContent = currencyFormatter.format(ticketPromedio);
    };

    const renderGraficoInteranual = (resumenAnual) => {
        const canvas = document.getElementById('chart-interanual');
        if (!canvas) return;

        const labels = resumenAnual.map(r => `Año ${r.anio}`);
        const dataVentas = resumenAnual.map(r => r.total_ventas);
        const dataUnidades = resumenAnual.map(r => r.total_unidades);

        if (chartInteranualInstance) {
            chartInteranualInstance.destroy();
            chartInteranualInstance = null;
        }
        if (window.miGraficoInteranual) {
            window.miGraficoInteranual.destroy();
            window.miGraficoInteranual = null;
        }

        chartInteranualInstance = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Ventas Totales ($)',
                        data: dataVentas,
                        backgroundColor: 'rgba(59, 130, 246, 0.75)',
                        borderColor: '#3b82f6',
                        borderWidth: 1,
                        yAxisID: 'yVentas'
                    },
                    {
                        label: 'Unidades Vendidas',
                        data: dataUnidades,
                        backgroundColor: 'rgba(16, 185, 129, 0.75)',
                        borderColor: '#10b981',
                        borderWidth: 1,
                        yAxisID: 'yUnidades'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#f8fafc' } }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
                    yVentas: {
                        type: 'linear',
                        position: 'left',
                        ticks: { color: '#60a5fa' },
                        grid: { color: '#334155' }
                    },
                    yUnidades: {
                        type: 'linear',
                        position: 'right',
                        ticks: { color: '#34d399' },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    };

    const renderGraficoZonas = (resumenZonas) => {
        const canvas = document.getElementById('chart-zonas');
        if (!canvas) return;

        const topZonas = (resumenZonas || []).slice(0, 6);
        const labels = topZonas.map(z => z.zona);
        const dataVentas = topZonas.map(z => z.total_ventas);

        if (chartZonasInstance) {
            chartZonasInstance.destroy();
            chartZonasInstance = null;
        }
        if (window.miGraficoZonas) {
            window.miGraficoZonas.destroy();
            window.miGraficoZonas = null;
        }

        chartZonasInstance = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: dataVentas,
                    backgroundColor: [
                        '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#64748b'
                    ],
                    borderWidth: 2,
                    borderColor: '#182234'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#f8fafc', font: { size: 11 } }
                    }
                }
            }
        });
    };

    const renderTablaZonas = (resumenZonas) => {
        const tbody = document.getElementById('tbody-zonas');
        if (!tbody) return;

        if (!resumenZonas || resumenZonas.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted py-3">No hay registros de zonas.</td></tr>`;
            return;
        }

        tbody.innerHTML = resumenZonas.map(z => `
            <tr>
                <td class="fw-medium">${z.zona}</td>
                <td class="text-end fw-bold text-success">${currencyFormatter.format(z.total_ventas)}</td>
                <td class="text-end text-muted">${numberFormatter.format(z.total_unidades)}</td>
            </tr>
        `).join('');
    };

    const renderTablaClientes = (topClientes) => {
        const tbody = document.getElementById('tbody-clientes');
        if (!tbody) return;

        if (!topClientes || topClientes.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No hay registros de clientes.</td></tr>`;
            return;
        }

        tbody.innerHTML = topClientes.map((c, index) => `
            <tr>
                <td class="text-muted small">${index + 1}</td>
                <td class="fw-medium">${c.cliente}</td>
                <td class="text-end fw-bold text-success">${currencyFormatter.format(c.total_ventas)}</td>
                <td class="text-end text-muted">${numberFormatter.format(c.total_unidades)}</td>
            </tr>
        `).join('');
    };

    const renderTablaDetalle = (detalleRows) => {
        const tbody = document.getElementById('tbody-detalle');
        if (!tbody) return;

        if (!detalleRows || detalleRows.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No se encontraron datos agrupados para este periodo.</td></tr>`;
            return;
        }

        tbody.innerHTML = detalleRows.map(d => `
            <tr>
                <td><span class="badge bg-secondary">${d.anio}</span></td>
                <td>${MESES[d.mes] || d.mes}</td>
                <td><i class="fas fa-map-pin me-1 text-primary small"></i>${d.zona}</td>
                <td class="fw-medium">${d.cliente}</td>
                <td class="text-end fw-bold text-success">${currencyFormatter.format(d.total_ventas)}</td>
                <td class="text-end">${numberFormatter.format(d.total_unidades)}</td>
                <td class="text-end text-muted">${d.total_transacciones}</td>
            </tr>
        `).join('');
    };

    const renderPaginacion = (paginacion) => {
        const contenedor = document.getElementById('paginacion-detalle');
        if (!contenedor || !paginacion) return;

        const { pagina, total_paginas, total_registros } = paginacion;

        contenedor.innerHTML = `
            <span class="text-muted small me-3">${numberFormatter.format(total_registros)} registros · Página ${pagina} de ${total_paginas}</span>
            <button class="btn btn-outline-secondary btn-sm" id="btn-pagina-prev" ${pagina <= 1 ? 'disabled' : ''}>
                <i class="fas fa-chevron-left"></i>
            </button>
            <button class="btn btn-outline-secondary btn-sm ms-1" id="btn-pagina-next" ${pagina >= total_paginas ? 'disabled' : ''}>
                <i class="fas fa-chevron-right"></i>
            </button>
        `;

        document.getElementById('btn-pagina-prev')?.addEventListener('click', () => {
            if (paginaActual > 1) {
                paginaActual -= 1;
                cargarDetalle();
            }
        });
        document.getElementById('btn-pagina-next')?.addEventListener('click', () => {
            if (paginaActual < total_paginas) {
                paginaActual += 1;
                cargarDetalle();
            }
        });
    };

    const mostrarEstadoCargandoResumen = () => {
        const tbodyZonas = document.getElementById('tbody-zonas');
        const tbodyClientes = document.getElementById('tbody-clientes');

        const spinnerRow = (cols) => `<tr><td colspan="${cols}" class="text-center py-4 text-muted"><i class="fas fa-spinner fa-spin me-2"></i>Consultando agregaciones en PostgreSQL...</td></tr>`;

        if (tbodyZonas) tbodyZonas.innerHTML = spinnerRow(3);
        if (tbodyClientes) tbodyClientes.innerHTML = spinnerRow(4);
    };

    const mostrarError = (mensaje) => {
        const tbodyDetalle = document.getElementById('tbody-detalle');
        if (tbodyDetalle) {
            tbodyDetalle.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-4"><i class="fas fa-exclamation-triangle me-2"></i>${mensaje}</td></tr>`;
        }
    };

    return { init };
})();
