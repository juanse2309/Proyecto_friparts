// ============================================
// inventario.js - Lógica de Inventario
// ============================================

/**
 * Cargar productos para inventario
 */
async function cargarProductos() {
    try {
        console.log('📦 Cargando productos...');
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
            console.log('✅ Productos cargados:', listaFinal.length);
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
 * Renderizar tabla de productos con optimización para 900 items
 */
function renderizarTablaProductos(productos) {
    const tbody = document.getElementById('tabla-productos-body');
    if (!tbody) {
        console.error('No se encontró tabla-productos-body');
        return;
    }

    if (!productos || productos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No hay productos</td></tr>';
        return;
    }

    // Usar DocumentFragment para renderizado eficiente
    const fragment = document.createDocumentFragment();

    productos.forEach(p => {
        const tr = document.createElement('tr');

        // Obtener semáforo color
        const semaforoColor = p.semaforo?.color || 'gray';
        const semaforoEstado = p.semaforo?.estado || 'NORMAL';

        tr.innerHTML = `
            <td>${p.codigo || '-'}</td>
            <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">${p.descripcion || '-'}</td>
            <td style="text-align: right;">${formatNumber(p.stock_por_pulir || 0)}</td>
            <td style="text-align: right;">${formatNumber(p.stock_terminado || 0)}</td>
            <td style="text-align: right; font-weight: bold;">${formatNumber(p.existencias_totales || 0)}</td>
            <td style="text-align: center;">
                <span class="semaforo-badge" style="background: ${getSemaforoColor(semaforoColor)}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;">
                    ${semaforoEstado}
                </span>
            </td>
        `;

        fragment.appendChild(tr);
    });

    // Limpiar y agregar todo de una vez
    tbody.innerHTML = '';
    tbody.appendChild(fragment);

    console.log(`✅ Tabla renderizada con ${productos.length} productos`);
}

/**
 * Obtener color de semáforo
 */
function getSemaforoColor(color) {
    const colores = {
        'green': '#28a745',
        'yellow': '#ffc107',
        'red': '#dc3545',
        'dark': '#6c757d',
        'gray': '#6c757d'
    };
    return colores[color] || '#6c757d';
}

/**
 * Actualizar estadísticas de inventario
 */
function actualizarEstadisticasInventario(productos) {
    const statsDiv = document.getElementById('estadisticas-inventario');
    if (!statsDiv) return;

    const totalProductos = productos.length;
    const stockPorPulir = productos.reduce((sum, p) => sum + (parseFloat(p.stock_por_pulir) || 0), 0);
    const stockTerminado = productos.reduce((sum, p) => sum + (parseFloat(p.stock_terminado) || 0), 0);
    const stockTotal = productos.reduce((sum, p) => sum + (parseFloat(p.existencias_totales) || 0), 0);

    statsDiv.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
            <div style="padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h4 style="margin: 0 0 10px 0; font-size: 14px; opacity: 0.9;">Total Productos</h4>
                <p style="margin: 0; font-size: 28px; font-weight: bold;">${totalProductos}</p>
            </div>
            <div style="padding: 15px; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h4 style="margin: 0 0 10px 0; font-size: 14px; opacity: 0.9;">Por Pulir</h4>
                <p style="margin: 0; font-size: 28px; font-weight: bold;">${formatNumber(stockPorPulir)}</p>
            </div>
            <div style="padding: 15px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h4 style="margin: 0 0 10px 0; font-size: 14px; opacity: 0.9;">Terminado</h4>
                <p style="margin: 0; font-size: 28px; font-weight: bold;">${formatNumber(stockTerminado)}</p>
            </div>
            <div style="padding: 15px; background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h4 style="margin: 0 0 10px 0; font-size: 14px; opacity: 0.9;">Stock Total</h4>
                <p style="margin: 0; font-size: 28px; font-weight: bold;">${formatNumber(stockTotal)}</p>
            </div>
        </div>
    `;
}

/**
 * Inicializar módulo de inventario
 */
function inicializarInventario() {
    console.log('🔧 Inicializando módulo de Inventario...');
    configurarEventosInventario();
    cargarProductos();
    console.log('✅ Módulo de Inventario inicializado');
}

/**
 * Configurar eventos de inventario
 */
function configurarEventosInventario() {
    // Buscar y filtrar productos
    const searchInput = document.getElementById('buscar-producto-inventario');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const filtrados = window.AppState.productosData.filter(p =>
                (p.codigo || '').toLowerCase().includes(query) ||
                (p.descripcion || '').toLowerCase().includes(query)
            );
            renderizarTablaProductos(filtrados);
        });
    }
}

// ============================================
// EXPORTAR MÓDULO
// ============================================
window.ModuloInventario = {
    inicializar: inicializarInventario
};
