// historial.js - MÓDULO DE HISTORIAL GLOBAL (REFACTORIZADO)
// ===========================================

const ModuloHistorial = (() => {
    let historialData = [];
    let filteredData = [];
    let currentPage = 1;
    const recordsPerPage = 50;

    /**
     * Inicializa el módulo Juan Sebastian.
     */
    function inicializar() {

        configurarEventos();
        cargarFechasPorDefecto();


    }

    function configurarEventos() {
        const btnExportar = document.getElementById('btn-exportar-historial');
        if (btnExportar) {
            btnExportar.onclick = exportarHistorial;
        }

        // Búsqueda reactiva si existe el input Juan Sebastian
        const inputSearch = document.getElementById('searchHistorial');
        if (inputSearch) {
            inputSearch.onkeyup = (e) => searchInHistorial(e.target.value);
        }
    }

    function cargarFechasPorDefecto() {
        const hoy = new Date();
        const haceMes = new Date();
        haceMes.setMonth(hoy.getMonth() - 1);

        const dInput = document.getElementById('fechaDesde');
        const hInput = document.getElementById('fechaHasta');

        if (dInput && !dInput.value) dInput.value = haceMes.toISOString().split('T')[0];
        if (hInput && !hInput.value) hInput.value = hoy.toISOString().split('T')[0];
    }

    /**
     * Consulta al backend con filtros Juan Sebastian.
     */
    async function filtrarHistorial() {
        const desde = document.getElementById('fechaDesde').value;
        const hasta = document.getElementById('fechaHasta').value;
        const tipo = document.getElementById('tipoProceso').value;

        if (!desde || !hasta) {
            return mostrarNotificacion('Por favor selecciona un rango de fechas', 'warning');
        }

        try {
            mostrarLoading(true);

            const params = new URLSearchParams({ desde, hasta, tipo });
            const res = await fetch(`/api/historial-global?${params}`);
            const result = await res.json();

            if (result.success) {
                historialData = result.data || [];
                filteredData = [...historialData];

                currentPage = 1;
                renderizarTabla();
                actualizarPaginacion();

                const totalSpan = document.getElementById('total-registros-historial');
                if (totalSpan) totalSpan.textContent = filteredData.length;

                if (filteredData.length === 0) {
                    mostrarNotificacion('No hay registros en este rango', 'info');
                }
            } else {
                throw new Error(result.error || 'Error en servidor');
            }
        } catch (error) {
            console.error('🚨 Error en Historial:', error);
            mostrarNotificacion('Error al consultar historial', 'error');
        } finally {
            mostrarLoading(false);
        }
    }

    /**
     * Construye la tabla HTML Juan Sebastian.
     */
    function renderizarTabla() {
        const container = document.getElementById('historial-container');
        if (!container) return;

        if (filteredData.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="fas fa-history fa-3x mb-3" style="opacity: 0.2"></i>
                    <p>No se encontraron resultados para los filtros aplicados</p>
                </div>`;
            return;
        }

        const start = (currentPage - 1) * recordsPerPage;
        const end = start + recordsPerPage;
        const pagedData = filteredData.slice(start, end);

        let html = `
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th>FECHA</th>
                            <th>PROCESO</th>
                            <th>PRODUCTO</th>
                            <th class="text-end">CANT.</th>
                            <th>RESPONSABLE</th>
                            <th>DETALLES / OBSERVACIONES</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        pagedData.forEach(item => {
            const badgeClass = {
                'INYECCION': 'bg-primary',
                'PULIDO': 'bg-info text-dark',
                'ENSAMBLE': 'bg-warning text-dark',
                'PNC': 'bg-danger',
                'VENTA': 'bg-success'
            }[item.tipo] || 'bg-secondary';

            // Normalización de datos para visualización segura
            const fecha = item.fecha || 'S/F';
            const tipo = item.tipo || 'DESCONOCIDO';
            const producto = item.producto || 'S/C';
            const cantidad = (parseInt(item.cantidad) || 0).toLocaleString();
            const responsable = item.responsable || 'N/A';
            const detalle = item.detalle || item.observacion || '-';

            html += `
                <tr>
                    <td><small class="fw-bold">${fecha}</small></td>
                    <td><span class="badge ${badgeClass}">${tipo}</span></td>
                    <td><strong>${producto}</strong></td>
                    <td class="text-end fw-bold">${cantidad}</td>
                    <td><small>${responsable}</small></td>
                    <td><span class="text-muted small">${detalle}</span></td>
                </tr>
            `;
        });

        html += `</tbody></table></div>`;
        container.innerHTML = html;
    }

    function searchInHistorial(term) {
        term = term.toLowerCase();
        filteredData = historialData.filter(i =>
            i.producto.toLowerCase().includes(term) ||
            (i.responsable && i.responsable.toLowerCase().includes(term)) ||
            (i.detalle && i.detalle.toLowerCase().includes(term))
        );
        currentPage = 1;
        renderizarTabla();
        actualizarPaginacion();
    }

    function actualizarPaginacion() {
        const totalPages = Math.ceil(filteredData.length / recordsPerPage);
        const container = document.getElementById('pagination-container');
        if (!container) return;

        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        let html = '<ul class="pagination pagination-sm mb-0 justify-content-center">';
        for (let i = 1; i <= totalPages; i++) {
            if (i > 10) { // Limitar a 10 paginas visibles Juan Sebastian
                html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
                break;
            }
            html += `<li class="page-item ${i === currentPage ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="ModuloHistorial.cambiarPagina(${i}); return false;">${i}</a>
                    </li>`;
        }
        html += '</ul>';
        container.innerHTML = html;
    }

    async function exportarHistorial() {
        if (filteredData.length === 0) return alert('No hay datos para exportar');

        let csv = 'Fecha,Tipo,Producto,Cantidad,Responsable,Detalle\n';
        filteredData.forEach(i => {
            csv += `${i.fecha},${i.tipo},${i.producto},${i.cantidad},${i.responsable},"${(i.detalle || '').replace(/"/g, '')}"\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `historial_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
    }

    return {
        inicializar,
        filtrar: filtrarHistorial,
        cambiarPagina: (p) => { currentPage = p; renderizarTabla(); actualizarPaginacion(); }
    };
})();

// Scope global Juan Sebastian
window.ModuloHistorial = ModuloHistorial;
window.filtrarHistorial = ModuloHistorial.filtrar; // Alias compatible con HTML Juan Sebastian
