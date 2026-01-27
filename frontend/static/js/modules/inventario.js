// ============================================
// inventario.js - L??gica de Inventario
// ============================================

/**
 * Cargar productos para inventario
 */
async function cargarProductos() {
    try {
        console.log('???? Cargando productos...');
        mostrarLoading(true);
        
        const response = await fetch('/api/productos/listar');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Datos recibidos:', data);
        
        let listaFinal = [];
        if (data.items && Array.isArray(data.items)) {
            listaFinal = data.items;
        } else if (Array.isArray(data)) {
            listaFinal = data;
        }
        
        if (listaFinal.length > 0) {
            window.AppState.productosData = listaFinal;
            renderizarTablaProductos(listaFinal);
            actualizarEstadisticasInventario(listaFinal);
            console.log('??? Productos cargados:', listaFinal.length);
        } else {
            mostrarNotificacion('No hay productos para mostrar', 'warning');
        }
        
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando productos:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
        mostrarLoading(false);
    }
}

/**
 * Renderizar tabla de productos
 */
function renderizarTablaProductos(productos) {
    const tbody = document.getElementById('tabla-productos-body');
    if (!tbody) {
        console.error('No se encontr?? tabla-productos-body');
        return;
    }
    
    if (!productos || productos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay productos</td></tr>';
        return;
    }
    
    tbody.innerHTML = productos.map(p => `
        <tr>
            <td>${p.codigo || '-'}</td>
            <td>${p.nombre || '-'}</td>
            <td>${formatNumber(p.stock || 0)}</td>
            <td>${p.estado || '-'}</td>
            <td>${p.precio || '$0'}</td>
        </tr>
    `).join('');
}

/**
 * Actualizar estad??sticas de inventario
 */
function actualizarEstadisticasInventario(productos) {
    const statsDiv = document.getElementById('estadisticas-inventario');
    if (!statsDiv) return;
    
    const totalProductos = productos.length;
    const stockTotal = productos.reduce((sum, p) => sum + (parseFloat(p.stock) || 0), 0);
    
    statsDiv.innerHTML = `
        <div style="display: flex; gap: 20px; margin-bottom: 20px;">
            <div style="flex: 1; padding: 15px; background: #f0f0f0; border-radius: 8px;">
                <h4 style="margin: 0 0 10px 0;">Total Productos</h4>
                <p style="margin: 0; font-size: 24px; font-weight: bold;">${totalProductos}</p>
            </div>
            <div style="flex: 1; padding: 15px; background: #f0f0f0; border-radius: 8px;">
                <h4 style="margin: 0 0 10px 0;">Stock Total</h4>
                <p style="margin: 0; font-size: 24px; font-weight: bold;">${formatNumber(stockTotal)}</p>
            </div>
        </div>
    `;
}

/**
 * Configurar eventos de inventario
 */
function configurarEventosInventario() {
    console.log('Configurando eventos de inventario...');
    // Aqu?? ir??an event listeners si hay filtros, b??squeda, etc
}
