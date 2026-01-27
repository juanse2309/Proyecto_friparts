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
            throw new Error(`HTTP ${response.statusCode}`);
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
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 20px;">No hay productos</td></tr>';
        return;
    }

    // Usar DocumentFragment para renderizado eficiente
    const fragment = document.createDocumentFragment();

    productos.forEach(p => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #f0f0f0';

        // Obtener semáforo
        const semaforoColor = p.semaforo?.color || 'gray';
        const semaforoEstado = p.semaforo?.estado || 'NORMAL';

        tr.innerHTML = `
            <td style="padding: 10px;">${p.codigo || '-'}</td>
            <td style="padding: 10px; max-width: 350px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${p.descripcion || '-'}</td>
            <td style="padding: 10px; text-align: right;">${formatNumber(p.stock_por_pulir || 0)}</td>
            <td style="padding: 10px; text-align: right;">${formatNumber(p.stock_terminado || 0)}</td>
            <td style="padding: 10px; text-align: right; font-weight: bold;">${formatNumber(p.existencias_totales || 0)}</td>
            <td style="padding: 10px; text-align: center;">
                <span style="background: ${getSemaforoColor(semaforoColor)}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 500;">
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
    if (!productos || productos.length === 0) return;

    const totalProductos = productos.length;

    // Contar productos por estado de semáforo
    const stockOK = productos.filter(p => p.semaforo?.color === 'green').length;
    const bajoStock = productos.filter(p => p.semaforo?.color === 'yellow').length;
    const agotados = productos.filter(p => p.semaforo?.estado === 'AGOTADO').length;

    // Actualizar elementos del HTML
    const el_total = document.getElementById('total-productos');
    const el_stockOk = document.getElementById('productos-stock-ok');
    const el_bajoStock = document.getElementById('productos-bajo-stock');
    const el_agotados = document.getElementById('productos-agotados');

    if (el_total) el_total.textContent = totalProductos;
    if (el_stockOk) el_stockOk.textContent = stockOK;
    if (el_bajoStock) el_bajoStock.textContent = bajoStock;
    if (el_agotados) el_agotados.textContent = agotados;

    console.log(`📊 Estadísticas: Total=${totalProductos}, OK=${stockOK}, Bajo=${bajoStock}, Agotados=${agotados}`);
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
    const searchInput = document.getElementById('buscar-producto');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            if (!window.AppState.productosData) return;

            const filtrados = window.AppState.productosData.filter(p =>
                (p.codigo || '').toLowerCase().includes(query) ||
                (p.descripcion || '').toLowerCase().includes(query)
            );
            renderizarTablaProductos(filtrados);
            console.log(`🔍 Búsqueda: "${query}" → ${filtrados.length} resultados`);
        });
    }

    // Botón actualizar
    const btnActualizar = document.getElementById('btn-actualizar-productos');
    if (btnActualizar) {
        btnActualizar.addEventListener('click', () => {
            cargarProductos();
        });
    }
}

// ============================================
// EXPORTAR MÓDULO
// ============================================
window.ModuloInventario = {
    inicializar: inicializarInventario
};
