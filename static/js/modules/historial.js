// Historial Global - Auditoría completa de movimientos
let historialData = [];
let filteredData = [];
let currentPage = 1;
const recordsPerPage = 50;

async function loadHistorialGlobal() {
    try {
        showLoading('Cargando historial de movimientos...');
        
        const response = await fetch('/api/historial-global');
        const result = await response.json();
        
        if (result.success) {
            historialData = result.data;
            filteredData = [...historialData];
            
            console.log(`✅ Historial cargado: ${historialData.length} registros`);
            
            currentPage = 1;
            renderHistorial();
            updatePagination();
        } else {
            showError('Error al cargar el historial: ' + result.error);
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error de conexión al cargar historial');
    } finally {
        hideLoading();
    }
}

function renderHistorial() {
    const container = document.getElementById('historial-container');
    
    if (filteredData.length === 0) {
        container.innerHTML = `
            <div class="empty-state text-center py-5">
                <i class="fas fa-inbox fa-3x mb-3 text-muted"></i>
                <p class="text-muted">No se encontraron movimientos en el rango seleccionado</p>
            </div>
        `;
        document.getElementById('pagination-container').innerHTML = '';
        return;
    }
    
    // Calcular registros a mostrar
    const startIndex = (currentPage - 1) * recordsPerPage;
    const endIndex = Math.min(startIndex + recordsPerPage, filteredData.length);
    const pageData = filteredData.slice(startIndex, endIndex);
    
    let html = `
        <div class="table-header mb-3">
            <div class="row align-items-center">
                <div class="col-md-6">
                    <h5 class="mb-0">
                        <i class="fas fa-list-alt text-primary"></i>
                        Mostrando ${startIndex + 1} - ${endIndex} de ${filteredData.length} registros
                    </h5>
                    ${filteredData.length !== historialData.length ? 
                        `<small class="text-muted">(${historialData.length} registros totales)</small>` : ''}
                </div>
                <div class="col-md-6">
                    <div class="input-group input-group-sm">
                        <span class="input-group-text">
                            <i class="fas fa-search"></i>
                        </span>
                        <input type="text" 
                               id="searchHistorial" 
                               class="form-control" 
                               placeholder="Buscar en tabla..."
                               onkeyup="searchInHistorial(this.value)">
                    </div>
                </div>
            </div>
        </div>
        
        <div class="table-responsive">
            <table class="table table-hover table-striped table-sm">
                <thead class="table-dark">
                    <tr>
                        <th style="width: 10%">
                            <i class="fas fa-calendar"></i> Fecha
                        </th>
                        <th style="width: 12%">
                            <i class="fas fa-tasks"></i> Tipo Proceso
                        </th>
                        <th style="width: 15%">
                            <i class="fas fa-box"></i> Producto / Ref
                        </th>
                        <th style="width: 10%" class="text-center">
                            <i class="fas fa-sort-numeric-up"></i> Cantidad
                        </th>
                        <th style="width: 18%">
                            <i class="fas fa-user"></i> Responsable
                        </th>
                        <th style="width: 35%">
                            <i class="fas fa-info-circle"></i> Detalle / Observación
                        </th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    pageData.forEach((item, index) => {
        const tipoClass = getTipoClass(item.tipo);
        const cantidad = parseInt(item.cantidad) || 0;
        const detalle = item.detalle || item.observacion || '-';
        
        html += `
            <tr>
                <td class="text-nowrap">
                    <small>${formatDate(item.fecha)}</small>
                </td>
                <td>
                    <span class="badge ${tipoClass}">
                        ${item.tipo}
                    </span>
                </td>
                <td>
                    <strong>${item.producto}</strong>
                </td>
                <td class="text-center">
                    <span class="badge bg-info text-dark">
                        ${cantidad.toLocaleString()}
                    </span>
                </td>
                <td>
                    <small>${item.responsable || 'N/A'}</small>
                </td>
                <td>
                    <small class="text-muted">${detalle}</small>
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    container.innerHTML = html;
}

function getTipoClass(tipo) {
    const classes = {
        'INYECCION': 'bg-primary',
        'PULIDO': 'bg-success',
        'ENSAMBLE': 'bg-warning text-dark',
        'PNC': 'bg-danger',
        'VENTA': 'bg-info text-dark',
        'FACTURACION': 'bg-secondary'
    };
    return classes[tipo] || 'bg-secondary';
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    
    try {
        // Si viene en formato DD/MM/YYYY
        const parts = dateStr.split('/');
        if (parts.length === 3) {
            return `${parts[0]}/${parts[1]}/${parts[2]}`;
        }
        return dateStr;
    } catch (e) {
        return dateStr;
    }
}

function searchInHistorial(searchTerm) {
    searchTerm = searchTerm.toLowerCase().trim();
    
    if (!searchTerm) {
        filteredData = [...historialData];
    } else {
        filteredData = historialData.filter(item => {
            return (
                (item.fecha && item.fecha.toLowerCase().includes(searchTerm)) ||
                (item.tipo && item.tipo.toLowerCase().includes(searchTerm)) ||
                (item.producto && item.producto.toLowerCase().includes(searchTerm)) ||
                (item.responsable && item.responsable.toLowerCase().includes(searchTerm)) ||
                (item.detalle && item.detalle.toLowerCase().includes(searchTerm)) ||
                (item.observacion && item.observacion.toLowerCase().includes(searchTerm))
            );
        });
    }
    
    currentPage = 1;
    renderHistorial();
    updatePagination();
}

function updatePagination() {
    const totalPages = Math.ceil(filteredData.length / recordsPerPage);
    const paginationContainer = document.getElementById('pagination-container');
    
    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }
    
    let html = `
        <nav aria-label="Paginación de historial" class="mt-3">
            <ul class="pagination pagination-sm justify-content-center mb-0">
    `;
    
    // Botón anterior
    html += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="changePage(${currentPage - 1}); return false;">
                <i class="fas fa-chevron-left"></i> Anterior
            </a>
        </li>
    `;
    
    // Números de página
    const maxButtons = 7;
    let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    
    if (endPage - startPage + 1 < maxButtons) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }
    
    if (startPage > 1) {
        html += `<li class="page-item"><a class="page-link" href="#" onclick="changePage(1); return false;">1</a></li>`;
        if (startPage > 2) {
            html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="#" onclick="changePage(${i}); return false;">
                    ${i}
                </a>
            </li>
        `;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
        html += `<li class="page-item"><a class="page-link" href="#" onclick="changePage(${totalPages}); return false;">${totalPages}</a></li>`;
    }
    
    // Botón siguiente
    html += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="changePage(${currentPage + 1}); return false;">
                Siguiente <i class="fas fa-chevron-right"></i>
            </a>
        </li>
    `;
    
    html += `
            </ul>
        </nav>
    `;
    
    paginationContainer.innerHTML = html;
}

function changePage(page) {
    const totalPages = Math.ceil(filteredData.length / recordsPerPage);
    
    if (page < 1 || page > totalPages) return;
    
    currentPage = page;
    renderHistorial();
    updatePagination();
    
    // Scroll suave al inicio de la tabla
    document.getElementById('historial-container').scrollIntoView({ 
        behavior: 'smooth', 
        block: 'start' 
    });
}

async function filtrarHistorial() {
    const desde = document.getElementById('fechaDesde').value;
    const hasta = document.getElementById('fechaHasta').value;
    const tipo = document.getElementById('tipoProceso').value;
    
    if (!desde || !hasta) {
        alert('Por favor selecciona ambas fechas');
        return;
    }
    
    try {
        showLoading('Buscando registros...');
        
        const params = new URLSearchParams({
            desde: desde,
            hasta: hasta,
            tipo: tipo
        });
        
        const response = await fetch(`/api/historial-global?${params}`);
        const result = await response.json();
        
        if (result.success) {
            historialData = result.data;
            filteredData = [...historialData];
            
            console.log(`✅ Filtro aplicado: ${historialData.length} registros encontrados`);
            
            currentPage = 1;
            renderHistorial();
            updatePagination();
        } else {
            showError('Error al filtrar: ' + result.error);
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error de conexión al filtrar');
    } finally {
        hideLoading();
    }
}

async function exportarHistorial() {
    try {
        showLoading('Preparando exportación...');
        
        // Usar los datos filtrados actuales
        const dataToExport = filteredData.map(item => ({
            Fecha: item.fecha,
            'Tipo Proceso': item.tipo,
            'Producto/Ref': item.producto,
            Cantidad: item.cantidad,
            Responsable: item.responsable || 'N/A',
            'Detalle/Observación': item.detalle || item.observacion || '-'
        }));
        
        // Crear CSV
        const headers = Object.keys(dataToExport[0]);
        let csv = headers.join(',') + '\n';
        
        dataToExport.forEach(row => {
            const values = headers.map(header => {
                const value = row[header] || '';
                return `"${value}"`;
            });
            csv += values.join(',') + '\n';
        });
        
        // Descargar
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        link.setAttribute('href', url);
        link.setAttribute('download', `historial_global_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        alert(`✅ Exportados ${dataToExport.length} registros`);
    } catch (error) {
        console.error('Error:', error);
        alert('Error al exportar datos');
    } finally {
        hideLoading();
    }
}

// Funciones de utilidad
function showLoading(message = 'Cargando...') {
    const container = document.getElementById('historial-container');
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Cargando...</span>
            </div>
            <p class="mt-3 text-muted">${message}</p>
        </div>
    `;
}

function hideLoading() {
    // La función render se encarga de limpiar el loading
}

function showError(message) {
    const container = document.getElementById('historial-container');
    container.innerHTML = `
        <div class="alert alert-danger" role="alert">
            <i class="fas fa-exclamation-triangle"></i> ${message}
        </div>
    `;
}
