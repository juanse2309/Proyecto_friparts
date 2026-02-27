/**
 * ModuloRotacion.js
 * Gestión de rotación de inventario y prioridades de compra.
 */

window.ModuloRotacion = (function () {
    let datosOriginales = [];

    async function inicializar() {
        console.log('🔄 Inicializando Módulo de Rotación...');
        await cargarPrioridades();
        configurarSidebarToggle();
    }

    function configurarSidebarToggle() {
        const btn = document.getElementById('toggle-sidebar-rotacion');
        if (btn) {
            btn.onclick = () => document.querySelector('.sidebar').classList.toggle('active');
        }
    }

    async function cargarPrioridades() {
        try {
            const response = await fetch('/api/rotacion/prioridades');
            const result = await response.json();

            if (result.status === 'success') {
                datosOriginales = result.data;
                renderizarDashboard(result.data);
                renderizarTablas(result.data);
            } else {
                console.error('Error al cargar prioridades:', result.message);
                alert('No se pudieron cargar las prioridades de rotación.');
            }
        } catch (error) {
            console.error('Error fetch rotacion:', error);
        }
    }

    function renderizarDashboard(data) {
        const total = data.length;
        const criticos = data.filter(d => d.clase === 'A' && d.semaforo === 'ROJO').length;
        const precaucion = data.filter(d => d.semaforo === 'AMARILLO').length;
        const ok = data.filter(d => d.semaforo === 'VERDE').length;

        document.getElementById('rot-count-total').innerText = total;
        document.getElementById('rot-count-a').innerText = criticos;
        document.getElementById('rot-count-caution').innerText = precaucion;
        document.getElementById('rot-count-ok').innerText = ok;
    }

    function renderizarTablas(data) {
        const tableA = document.getElementById('rot-table-a');
        const tableBC = document.getElementById('rot-table-bc');

        // Filtrar Clase A (Críticos y no críticos)
        const itemsA = data.filter(d => d.clase === 'A');
        // Filtrar Clase B y C
        const itemsBC = data.filter(d => d.clase !== 'A');

        tableA.innerHTML = itemsA.length > 0 ? itemsA.map(item => createRow(item, true)).join('') : '<tr><td colspan="6" class="text-center py-4">No hay items Clase A registrados</td></tr>';
        tableBC.innerHTML = itemsBC.length > 0 ? itemsBC.map(item => createRow(item, false)).join('') : '<tr><td colspan="6" class="text-center py-4">No hay items Clase B/C registrados</td></tr>';
    }

    function createRow(item, isTop) {
        const badgeClass = item.semaforo === 'ROJO' ? 'bg-danger' : (item.semaforo === 'AMARILLO' ? 'bg-warning text-dark' : 'bg-success');
        const progressClass = item.semaforo === 'ROJO' ? 'bg-danger' : (item.semaforo === 'AMARILLO' ? 'bg-warning' : 'bg-success');

        // Compact Progress Bar
        const progressBar = `
            <div class="d-flex align-items-center gap-2">
                <div class="progress flex-grow-1" style="height: 6px; background-color: #e9ecef;">
                    <div class="progress-bar ${progressClass}" role="progressbar" style="width: ${Math.min(item.porcentaje, 100)}%"></div>
                </div>
                <span class="small fw-bold ${item.semaforo === 'ROJO' ? 'text-danger' : 'text-muted'}" style="font-size: 0.75rem; min-width: 35px;">
                    ${item.porcentaje}%
                </span>
            </div>
        `;

        const urgencyLabel = item.semaforo === 'ROJO' ? '<span class="text-danger small fw-bold"><i class="fas fa-exclamation-circle"></i> CRÍTICO</span>' :
            (item.semaforo === 'AMARILLO' ? '<span class="text-warning small fw-bold">PRECAUCIÓN</span>' :
                '<span class="text-success small fw-bold">SALUDABLE</span>');

        return `
            <tr>
                <td><span class="fw-bold text-dark">${item.codigo}</span></td>
                <td><div class="text-truncate" style="max-width: 280px;" title="${item.descripcion}">${item.descripcion}</div></td>
                ${!isTop ? `<td class="text-center"><span class="badge bg-secondary opacity-75">${item.clase}</span></td>` : ''}
                <td class="text-center">${item.stock_actual}</td>
                <td class="text-center text-muted">${item.minimo}</td>
                <td>
                    <div class="mb-1">${urgencyLabel}</div>
                    ${progressBar}
                </td>
                <td class="text-center">
                    <span class="badge rounded-pill bg-light text-dark border fw-normal">
                        <i class="fas fa-shopping-cart me-1 text-primary" style="font-size:0.7rem;"></i> ${item.contador_oc}
                    </span>
                </td>
            </tr>
        `;
    }

    function filtrarBC() {
        const term = document.getElementById('rot-search-bc').value.toUpperCase();
        const filtered = datosOriginales.filter(d =>
            d.clase !== 'A' &&
            (d.codigo.includes(term) || d.descripcion.toUpperCase().includes(term))
        );

        const tableBC = document.getElementById('rot-table-bc');
        tableBC.innerHTML = filtered.length > 0 ? filtered.map(item => createRow(item, false)).join('') : '<tr><td colspan="6" class="text-center py-4">No se encontraron resultados</td></tr>';
    }

    return {
        inicializar,
        cargarPrioridades,
        filtrarBC
    };
})();
