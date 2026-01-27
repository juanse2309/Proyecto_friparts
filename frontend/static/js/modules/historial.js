// ============================================
// historial.js - Lógica de Historial Global
// ============================================

async function cargarHistorial() {
    try {
        console.log('📜 Cargando historial...');
        mostrarLoading(true);
        
        const proceso = document.getElementById('tipoProceso')?.value || '';
        const desde = document.getElementById('fechaDesde')?.value || '';
        const hasta = document.getElementById('fechaHasta')?.value || '';
        
        const url = `/api/historial?proceso=${proceso}&desde=${desde}&hasta=${hasta}`;
        const res = await fetchData(url);
        
        if (res && res.success) {
            renderizarTablaHistorial(res.data);
            const totalSpan = document.getElementById('total-registros-historial');
            if (totalSpan) totalSpan.textContent = res.data.length;
        }
        
    } catch (error) {
        console.error('Error cargando historial:', error);
    } finally {
        mostrarLoading(false);
    }
}

function renderizarTablaHistorial(datos) {
    const container = document.getElementById('historial-container');
    if (!container) return;
    
    if (!datos || datos.length === 0) {
        container.innerHTML = '<div class="text-center py-5 text-muted">No se encontraron registros</div>';
        return;
    }
    
    let html = `
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead class="bg-light">
                    <tr>
                        <th class="ps-4">Fecha</th>
                        <th>Tipo</th>
                        <th>Responsable</th>
                        <th>Producto</th>
                        <th>Detalle</th>
                        <th class="text-center">Cant.</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    datos.forEach(r => {
        const badgeClass = obtenerBadgeClass(r.proceso_tipo);
        html += `
            <tr>
                <td class="ps-4">${r.FECHA || r.fecha || '-'}</td>
                <td><span class="badge ${badgeClass}">${r.proceso_tipo}</span></td>
                <td>${r.RESPONSABLE || r.responsable || '-'}</td>
                <td><strong>${r.CODIGO || r.codigo_producto || '-'}</strong></td>
                <td><small class="text-muted">${r.OBSERVACIONES || r.observaciones || '-'}</small></td>
                <td class="text-center fw-bold">${r.CANTIDAD_REAL || r.ensambles || r.entrada || '-'}</td>
            </tr>
        `;
    });
    
    html += `</tbody></table></div>`;
    container.innerHTML = html;
}

function obtenerBadgeClass(tipo) {
    switch(tipo) {
        case 'INYECCION': return 'bg-primary';
        case 'PULIDO': return 'bg-info';
        case 'ENSAMBLE': return 'bg-success';
        case 'VENTA': return 'bg-warning text-dark';
        default: return 'bg-secondary';
    }
}

function initHistorial() {
    console.log('🔧 Inicializando módulo de historial...');
    
    // Configurar fechas por defecto (últimos 7 días)
    const hasta = new Date().toISOString().split('T')[0];
    const desdeDate = new Date();
    desdeDate.setDate(desdeDate.getDate() - 7);
    const desde = desdeDate.toISOString().split('T')[0];
    
    if (document.getElementById('fechaDesde')) document.getElementById('fechaDesde').value = desde;
    if (document.getElementById('fechaHasta')) document.getElementById('fechaHasta').value = hasta;
    
    cargarHistorial();
}

window.initHistorial = initHistorial;
window.filtrarHistorial = cargarHistorial;
window.ModuloHistorial = { inicializar: initHistorial };
