// ============================================
// inventario.js - Lógica de Inventario con Paginación
// ============================================

// Estado de paginación
let paginaActual = 1;
const productosPorPagina = 50;

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
            paginaActual = 1; // Resetear a página 1
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
 * Renderizar tabla de productos con paginación
 */
function renderizarTablaProductos(productos, resetearPagina = false) {
    const tbody = document.getElementById('tabla-productos-body');
    if (!tbody) {
        console.error('No se encontró tabla-productos-body');
        return;
    }

    if (!productos || productos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 20px;">No hay productos</td></tr>';
        const paginationDiv = document.getElementById('pagination-container');
        if (paginationDiv) paginationDiv.innerHTML = '';
        return;
    }

    // Resetear página si es necesario (por filtros)
    if (resetearPagina) paginaActual = 1;

    // Calcular índices de paginación
    const totalProductos = productos.length;
    const totalPaginas = Math.ceil(totalProductos / productosPorPagina);
    const inicio = (paginaActual - 1) * productosPorPagina;
    const fin = Math.min(inicio + productosPorPagina, totalProductos);
    const productosPagina = productos.slice(inicio, fin);

    // Usar DocumentFragment para renderizado eficiente
    const fragment = document.createDocumentFragment();

    productosPagina.forEach(p => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #f0f0f0';

        // Obtener semáforo
        const semaforoColor = p.semaforo?.color || 'gray';
        const semaforoEstado = p.semaforo?.estado || 'NORMAL';

        // Imagen del producto (thumbnail)
        const imagenUrl = p.imagen || '';
        const imagenHtml = imagenUrl
            ? `<img src="${imagenUrl}" alt="${p.codigo}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px; cursor: pointer;" onclick="window.open('${imagenUrl}', '_blank')" title="Click para ampliar">`
            : '<div style="width: 40px; height: 40px; background: #f0f0f0; border-radius: 4px; display: flex; align-items: center; justify-content: center;"><i class="fas fa-image" style="color: #ccc;"></i></div>';

        tr.innerHTML = `
            <td style="padding: 10px; text-align: center;">${imagenHtml}</td>
            <td style="padding: 10px;">${p.codigo || '-'}</td>
            <td style="padding: 10px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${p.descripcion || '-'}</td>
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

    // Renderizar controles de paginación
    renderizarPaginacion(totalProductos, totalPaginas, productos);

    console.log(`✅ Página ${paginaActual}/${totalPaginas}: Mostrando ${productosPagina.length} de ${totalProductos} productos`);
}

/**
 * Renderizar controles de paginación
 */
function renderizarPaginacion(totalProductos, totalPaginas, productos) {
    const paginationDiv = document.getElementById('pagination-container');
    if (!paginationDiv) return;

    if (totalPaginas <= 1) {
        paginationDiv.innerHTML = '';
        return;
    }

    const inicio = (paginaActual - 1) * productosPorPagina + 1;
    const fin = Math.min(paginaActual * productosPorPagina, totalProductos);

    let html = `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px 0;">
            <div style="color: #666; font-size: 14px;">
                Mostrando <strong>${inicio}-${fin}</strong> de <strong>${totalProductos}</strong> productos
            </div>
            <div style="display: flex; gap: 5px;">
    `;

    // Botón anterior
    html += `
        <button 
            onclick="window.ModuloInventario.cambiarPagina(${paginaActual - 1})" 
            ${paginaActual === 1 ? 'disabled' : ''}
            style="padding: 8px 12px; border: 1px solid #ddd; background: ${paginaActual === 1 ? '#f5f5f5' : 'white'}; border-radius: 4px; cursor: ${paginaActual === 1 ? 'not-allowed' : 'pointer'}; color: ${paginaActual === 1 ? '#ccc' : '#333'};"
        >
            <i class="fas fa-chevron-left"></i> Anterior
        </button>
    `;

    // Números de página (máximo 7 botones)
    const maxBotones = 7;
    let inicioPaginas = Math.max(1, paginaActual - Math.floor(maxBotones / 2));
    let finPaginas = Math.min(totalPaginas, inicioPaginas + maxBotones - 1);

    if (finPaginas - inicioPaginas < maxBotones - 1) {
        inicioPaginas = Math.max(1, finPaginas - maxBotones + 1);
    }

    if (inicioPaginas > 1) {
        html += `<button onclick="window.ModuloInventario.cambiarPagina(1)" style="padding: 8px 12px; border: 1px solid #ddd; background: white; border-radius: 4px; cursor: pointer;">1</button>`;
        if (inicioPaginas > 2) html += `<span style="padding: 8px;">...</span>`;
    }

    for (let i = inicioPaginas; i <= finPaginas; i++) {
        const esActiva = i === paginaActual;
        html += `
            <button 
                onclick="window.ModuloInventario.cambiarPagina(${i})" 
                style="padding: 8px 12px; border: 1px solid ${esActiva ? '#007bff' : '#ddd'}; background: ${esActiva ? '#007bff' : 'white'}; color: ${esActiva ? 'white' : '#333'}; border-radius: 4px; cursor: pointer; font-weight: ${esActiva ? 'bold' : 'normal'};"
            >
                ${i}
            </button>
        `;
    }

    if (finPaginas < totalPaginas) {
        if (finPaginas < totalPaginas - 1) html += `<span style="padding: 8px;">...</span>`;
        html += `<button onclick="window.ModuloInventario.cambiarPagina(${totalPaginas})" style="padding: 8px 12px; border: 1px solid #ddd; background: white; border-radius: 4px; cursor: pointer;">${totalPaginas}</button>`;
    }

    // Botón siguiente
    html += `
        <button 
            onclick="window.ModuloInventario.cambiarPagina(${paginaActual + 1})" 
            ${paginaActual === totalPaginas ? 'disabled' : ''}
            style="padding: 8px 12px; border: 1px solid #ddd; background: ${paginaActual === totalPaginas ? '#f5f5f5' : 'white'}; border-radius: 4px; cursor: ${paginaActual === totalPaginas ? 'not-allowed' : 'pointer'}; color: ${paginaActual === totalPaginas ? '#ccc' : '#333'};"
        >
            Siguiente <i class="fas fa-chevron-right"></i>
        </button>
    `;

    html += `</div></div>`;
    paginationDiv.innerHTML = html;
}

/**
 * Cambiar página
 */
function cambiarPagina(nuevaPagina) {
    const productosActuales = window.AppState.productosFiltrados || window.AppState.productosData || [];
    const totalPaginas = Math.ceil(productosActuales.length / productosPorPagina);

    if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;

    paginaActual = nuevaPagina;
    renderizarTablaProductos(productosActuales, false);

    // Scroll hacia arriba
    const tableContainer = document.querySelector('.table-container');
    if (tableContainer) tableContainer.scrollTop = 0;
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
            window.AppState.productosFiltrados = filtrados;
            renderizarTablaProductos(filtrados, true);
            console.log(`🔍 Búsqueda: "${query}" → ${filtrados.length} resultados`);
        });
    }

    // Botones de filtro por estado de semáforo
    const botonesFiltro = document.querySelectorAll('#filtros-inventario button');
    botonesFiltro.forEach((btn, index) => {
        btn.addEventListener('click', () => {
            // Quitar 'active' de todos los botones
            botonesFiltro.forEach(b => b.classList.remove('active'));
            // Marcar este botón como activo
            btn.classList.add('active');

            if (!window.AppState.productosData) return;

            let productosFiltrados = [];
            const textoBtn = btn.textContent.trim().toLowerCase();

            // Filtrar según el botón clicado
            if (textoBtn.includes('todos')) {
                productosFiltrados = window.AppState.productosData;
            } else if (textoBtn.includes('críticos')) {
                productosFiltrados = window.AppState.productosData.filter(p =>
                    p.semaforo?.color === 'red'
                );
            } else if (textoBtn.includes('por pedir') || textoBtn.includes('pedir')) {
                productosFiltrados = window.AppState.productosData.filter(p =>
                    p.semaforo?.color === 'yellow'
                );
            } else if (textoBtn.includes('stock ok')) {
                productosFiltrados = window.AppState.productosData.filter(p =>
                    p.semaforo?.color === 'green'
                );
            } else if (textoBtn.includes('agotados')) {
                productosFiltrados = window.AppState.productosData.filter(p =>
                    p.semaforo?.estado === 'AGOTADO' || p.semaforo?.color === 'dark'
                );
            }

            window.AppState.productosFiltrados = productosFiltrados;
            renderizarTablaProductos(productosFiltrados, true);
            console.log(`🔘 Filtro: "${textoBtn}" → ${productosFiltrados.length} productos`);
        });
    });

    // Botón actualizar
    const btnActualizar = document.getElementById('btn-actualizar-productos');
    if (btnActualizar) {
        btnActualizar.addEventListener('click', () => {
            console.log('🔄 Recargando productos...');
            cargarProductos();
        });
    }
}

// ============================================
// EXPORTAR MÓDULO
// ============================================
window.ModuloInventario = {
    inicializar: inicializarInventario,
    cambiarPagina: cambiarPagina
};
