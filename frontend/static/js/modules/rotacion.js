/**
 * ModuloRotacion.js
 * Gestión de rotación de inventario y prioridades de compra.
 */

window.ModuloRotacion = (function () {
    let datosOriginales = [];

    async function inicializar() {
        console.log('🔄 Inicializando Módulo de Rotación...');
        await cargarPrioridades();

        // Evento para limpiar búsqueda al cambiar de pestaña
        const subTabs = document.querySelectorAll('#rot-sub-tabs button');
        subTabs.forEach(tab => {
            tab.addEventListener('shown.bs.tab', () => {
                const search = document.getElementById('rot-search-global');
                if (search) {
                    search.value = '';
                    renderizarTablas(datosOriginales);
                }
            });
        });
    }

    async function cargarPrioridades() {
        try {
            mostrarLoading(true);
            const response = await fetch('/api/procura/rotacion/prioridades');
            const result = await response.json();

            if (result.status === 'success') {
                datosOriginales = result.data;
                renderizarDashboard(result.data);
                renderizarTablas(result.data);
                console.log('✅ Prioridades actualizadas');
            } else {
                console.error('Error al cargar prioridades:', result.message);
            }
        } catch (error) {
            console.error('Error fetch rotacion:', error);
        } finally {
            mostrarLoading(false);
        }
    }

    function renderizarDashboard(data) {
        const total = data.length;
        const criticos = data.filter(d => d.semaforo === 'ROJO').length;
        const precaucion = data.filter(d => d.semaforo === 'AMARILLO').length;
        const ok = data.filter(d => d.semaforo === 'VERDE').length;

        if (document.getElementById('rot-count-total')) {
            document.getElementById('rot-count-total').innerText = total;
            document.getElementById('rot-count-a').innerText = criticos;
            document.getElementById('rot-count-caution').innerText = precaucion;
            document.getElementById('rot-count-ok').innerText = ok;
        }

        const miniCounter = document.getElementById('mini-alert-count');
        if (miniCounter) {
            miniCounter.innerHTML = `<span class="text-danger fw-bold">${criticos} urgentes</span> detectados`;
        }
    }

    function renderizarTablas(data) {
        const tableA = document.getElementById('rot-table-a');
        const tableBC = document.getElementById('rot-table-bc');
        if (!tableA || !tableBC) return;

        const itemsA = data.filter(d => d.clase === 'A');
        const itemsBC = data.filter(d => d.clase !== 'A');

        tableA.innerHTML = itemsA.length > 0 ? itemsA.map(item => createRow(item, true)).join('') : '<tr><td colspan="7" class="text-center py-5 text-muted">No hay items Clase A críticos</td></tr>';
        tableBC.innerHTML = itemsBC.length > 0 ? itemsBC.map(item => createRow(item, false)).join('') : '<tr><td colspan="7" class="text-center py-5 text-muted">No hay items Clase B/C</td></tr>';
    }

    function createRow(item, isTop) {
        const colorMap = {
            'ROJO': { border: '#dc3545', bg: '#fff5f5' },
            'AMARILLO': { border: '#f59e0b', bg: '#fffbeb' },
            'VERDE': { border: '#10b981', bg: 'transparent' }
        };
        const colors = colorMap[item.semaforo] || { border: '#e2e8f0', bg: 'transparent' };

        const progressClass = item.semaforo === 'ROJO' ? 'bg-danger' : (item.semaforo === 'AMARILLO' ? 'bg-warning' : 'bg-success');

        const urgencyLabel = item.semaforo === 'ROJO' ? '<span class="badge bg-danger">URGENTE</span>' :
            (item.semaforo === 'AMARILLO' ? '<span class="badge bg-warning text-dark">ALERTA</span>' :
                '<span class="badge bg-success">ÓPTIMO</span>');

        return `
            <tr style="border-left: 5px solid ${colors.border}; background-color: ${colors.bg}; transition: all 0.2s;">
                <td class="ps-4"><span class="fw-bold text-dark">${item.codigo}</span></td>
                <td>
                    <div class="fw-medium">${item.descripcion}</div>
                    ${isTop ? '<small class="text-muted text-uppercase" style="font-size:0.65rem">Ítem Crítico de Producción</small>' : ''}
                </td>
                ${!isTop ? `<td class="text-center"><span class="badge bg-info bg-opacity-10 text-info border border-info border-opacity-25 px-2">${item.clase}</span></td>` : ''}
                <td class="text-center fw-bold ${item.semaforo === 'ROJO' ? 'text-danger' : ''}">${item.stock_actual}</td>
                ${isTop ? `<td class="text-center text-muted">${item.minimo}</td>` : ''}
                <td>
                    <div class="d-flex align-items-center justify-content-between mb-1">
                        ${urgencyLabel}
                        <span class="small fw-bold text-muted">${item.porcentaje}%</span>
                    </div>
                    <div class="progress" style="height: 6px; border-radius: 10px; background: rgba(0,0,0,0.05);">
                        <div class="progress-bar ${progressClass} progress-bar-striped progress-bar-animated" role="progressbar" style="width: ${Math.min(item.porcentaje, 100)}%"></div>
                    </div>
                </td>
                <td class="text-center">
                    <span class="fw-bold text-secondary" style="font-size: 1rem;">${item.contador_oc}</span>
                </td>
                <td class="pe-4 text-end">
                    <button class="btn btn-primary btn-sm rounded-pill px-3 shadow-sm hover-lift" 
                            onclick="ModuloRotacion.prepararCompra('${item.codigo}')" title="Comprar Ahora">
                        <i class="fas fa-shopping-cart me-1"></i> Comprar
                    </button>
                </td>
            </tr>
        `;
    }

    function filtrarGlobal() {
        const term = document.getElementById('rot-search-global').value.toUpperCase();
        // Detectar tabla activa
        const isClaseA = document.getElementById('tab-clase-a').classList.contains('active');

        const filtered = datosOriginales.filter(d => {
            const matchesTab = isClaseA ? d.clase === 'A' : d.clase !== 'A';
            const matchesTerm = (String(d.codigo).includes(term) || String(d.descripcion).toUpperCase().includes(term));
            return matchesTab && matchesTerm;
        });

        const targetTbody = isClaseA ? document.getElementById('rot-table-a') : document.getElementById('rot-table-bc');
        if (targetTbody) {
            targetTbody.innerHTML = filtered.length > 0 ? filtered.map(item => createRow(item, isClaseA)).join('') :
                `<tr><td colspan="7" class="text-center py-5 text-muted">No hay resultados para "${term}"</td></tr>`;
        }
    }

    function prepararCompra(codigo) {
        // 1. Cambiar a la pestaña de Órdenes de Compra
        const ordenesTab = document.getElementById('ordenes-tab');
        if (ordenesTab) {
            const tabTrigger = new bootstrap.Tab(ordenesTab);
            tabTrigger.show();
        }

        // 2. Esperar un poco a que la pestaña carge y ejecutar lógica de compra
        setTimeout(() => {
            const inputCodigo = document.getElementById('codigo-producto-oc');
            if (inputCodigo) {
                inputCodigo.value = codigo;
                inputCodigo.classList.add('is-valid');

                // Efecto de foco visual potente
                const card = inputCodigo.closest('.card');
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                card.style.boxShadow = '0 0 20px rgba(67, 97, 238, 0.3)';
                setTimeout(() => card.style.boxShadow = '', 2000);

                inputCodigo.focus();
                inputCodigo.dispatchEvent(new Event('input', { bubbles: true }));

                Swal.fire({
                    title: '¡Producto Seleccionado!',
                    text: `Se ha cargado ${codigo} en la nueva orden.`,
                    icon: 'success',
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 3000
                });
            }
        }, 400);
    }

    return {
        inicializar,
        cargarPrioridades,
        filtrarGlobal,
        prepararCompra
    };
})();
