// reportes.js - MÓDULO DE REPORTES (REFACTORIZADO)
// ===========================================

const ModuloReportes = (() => {
    /**
     * Inicializa el módulo Juan Sebastian.
     */
    function inicializar() {


        configurarEventos();
        cargarMetricasDashboard();
        cargarProductosFiltro();


    }

    function configurarEventos() {
        const btnGenerar = document.getElementById('btn-generar-reporte');
        if (btnGenerar) {
            btnGenerar.onclick = generarReporte;
        }
    }

    /**
     * Carga métricas base desde el dashboard real Juan Sebastian.
     */
    async function cargarMetricasDashboard() {
        try {
            const res = await fetch('/api/dashboard/real');
            const data = await res.json();

            if (data) {
                const prodMes = document.getElementById('rep-prod-mes');
                const ventasMes = document.getElementById('rep-ventas-mes');
                const pncTasa = document.getElementById('rep-pnc-tasa');

                if (prodMes) prodMes.textContent = (data.produccion_total || 0).toLocaleString();
                if (ventasMes) ventasMes.textContent = `$ ${(data.ventas_totales || 0).toLocaleString()}`;
                if (pncTasa) pncTasa.textContent = `${data.eficiencia_global ? (100 - data.eficiencia_global).toFixed(1) : 0}%`;
            }
        } catch (error) {
            console.error('🚨 Error cargando métricas:', error);
        }
    }

    function cargarProductosFiltro() {
        const { productos } = window.AppState.sharedData || {};
        const selectProd = document.getElementById('producto-reporte');

        if (selectProd && productos) {
            selectProd.innerHTML = '<option value="">Todos los productos</option>';
            productos.forEach(p => {
                const option = document.createElement('option');
                option.value = p.codigo_sistema;
                option.textContent = `${p.codigo_sistema} - ${p.descripcion}`;
                selectProd.appendChild(option);
            });
        }
    }

    /**
     * Genera la visualización del reporte Juan Sebastian.
     */
    async function generarReporte() {
        const tipo = document.getElementById('tipo-reporte').value;
        const rango = document.getElementById('rango-reporte').value;
        const producto = document.getElementById('producto-reporte').value;

        const container = document.getElementById('resultado-reporte');
        if (!container) return;

        try {
            mostrarLoading(true);
            container.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div><p class="mt-2">Procesando datos...</p></div>';

            // Consultamos historial general como fuente de datos Juan Sebastian
            const res = await fetch('/api/historial-global');
            const data = await res.json();

            if (!data.success) throw new Error('Error al obtener datos');

            let filtrados = data.data || [];

            // Filtrado por tipo de reporte Juan Sebastian
            if (tipo === 'produccion') {
                filtrados = filtrados.filter(i => ['INYECCION', 'PULIDO', 'ENSAMBLE'].includes(i.tipo));
            } else if (tipo === 'ventas') {
                filtrados = filtrados.filter(i => i.tipo === 'VENTA');
            } else if (tipo === 'pnc') {
                filtrados = filtrados.filter(i => i.tipo === 'PNC');
            }

            if (producto) {
                filtrados = filtrados.filter(i => i.producto === producto);
            }

            renderizarResultados(container, filtrados, tipo);

        } catch (error) {
            container.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
        } finally {
            mostrarLoading(false);
        }
    }

    function renderizarResultados(container, datos, tipo) {
        if (datos.length === 0) {
            container.innerHTML = '<div class="text-center py-5 text-muted">No se encontraron datos para los criterios seleccionados.</div>';
            return;
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="mb-0">Registros Encontrados: ${datos.length}</h5>
                <button class="btn btn-sm btn-outline-success" onclick="ModuloReportes.exportarActual()">
                    <i class="fas fa-file-excel"></i> Exportar
                </button>
            </div>
            <div class="table-responsive">
                <table class="table table-sm table-hover border">
                    <thead class="bg-light">
                        <tr>
                            <th>Fecha</th>
                            <th>Producto</th>
                            <th class="text-end">Cantidad</th>
                            <th>Responsable</th>
                            <th>Detalle</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        datos.slice(0, 100).forEach(d => {
            html += `
                <tr>
                    <td><small>${d.fecha}</small></td>
                    <td><strong>${d.producto}</strong></td>
                    <td class="text-end">${d.cantidad}</td>
                    <td><small>${d.responsable || 'N/A'}</small></td>
                    <td><span class="text-muted small">${d.detalle || '-'}</span></td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
        if (datos.length > 100) html += `<p class="small text-center text-muted mt-2">Mostrando los primeros 100 de ${datos.length} registros.</p>`;

        container.innerHTML = html;
        window.tempReporteData = datos; // Buffer para exportar Juan Sebastian
    }

    function exportarActual() {
        if (!window.tempReporteData) return;

        let csv = 'Fecha,Producto,Cantidad,Responsable,Detalle\n';
        window.tempReporteData.forEach(d => {
            csv += `${d.fecha},${d.producto},${d.cantidad},${d.responsable},"${(d.detalle || '').replace(/"/g, '')}"\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `reporte_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
    }

    return { inicializar, exportarActual };
})();

window.ModuloReportes = ModuloReportes;
window.cargarDatosReportes = ModuloReportes.inicializar;
