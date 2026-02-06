// ============================================
// inventario.js - LÃ³gica de Inventario con PaginaciÃ³n
// ============================================

// Configuración de paginación
const getItemsPerPage = () => window.innerWidth < 992 ? 10 : 50;
let paginaActual = 1;

// Placeholder premium de FriTech (SVG en base64 para evitar peticiones extra)
const PLACEHOLDER_SVG = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%23f8fafc;stop-opacity:1' /%3E%3Cstop offset='100%25' style='stop-color:%23e2e8f0;stop-opacity:1' /%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='100' height='100' fill='url(%23g)' rx='12'/%3E%3Cg opacity='0.4' transform='translate(0, -5)'%3E%3Cpath d='M30 40c0-2.2 1.8-4 4-4h32c2.2 0 4 1.8 4 4v25c0 2.2-1.8 4-4 4H34c-2.2 0-4-1.8-4-4V40z' fill='%2364748b'/%3E%3Ccircle cx='50' cy='52.5' r='7' fill='%23f1f5f9'/%3E%3Cpath d='M46 32h8l2 4h-12z' fill='%2364748b'/%3E%3C/g%3E%3Ctext x='50' y='82' text-anchor='middle' font-family='sans-serif' font-size='7' fill='%2394a3b8' font-weight='bold'%3EFriTech%3C/text%3E%3C/svg%3E`;

/**
 * Cargar productos para inventario
 */
async function cargarProductos(forceRefresh = false) {
    try {
        console.log('📦 Cargando productos...');
        mostrarLoading(true);

        let url = '/api/productos/listar';
        if (forceRefresh) {
            url += '?refresh=true';
        }
        const response = await fetch(url);
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
            paginaActual = 1; // Resetear a pÃ¡gina 1
            renderizarTablaProductos(listaFinal);
            actualizarEstadisticasInventario(listaFinal);
            console.log('âœ… Productos cargados:', listaFinal.length);
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
 * Renderizar tabla de productos con paginaciÃ³n
 */
function renderizarTablaProductos(productos, resetearPagina = false) {
    const tbody = document.getElementById('tabla-productos-body');
    if (!tbody) {
        console.error('No se encontrÃ³ tabla-productos-body');
        return;
    }

    if (!productos || productos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 20px;">No hay productos</td></tr>';
        const paginationDiv = document.getElementById('pagination-container');
        if (paginationDiv) paginationDiv.innerHTML = '';
        return;
    }

    // Resetear pÃ¡gina si es necesario (por filtros)
    if (resetearPagina) paginaActual = 1;

    // Calcular Ã­ndices de paginaciÃ³n
    const itemsPerPage = getItemsPerPage();
    const totalProductos = productos.length;
    const totalPaginas = Math.ceil(totalProductos / itemsPerPage);
    const inicio = (paginaActual - 1) * itemsPerPage;
    const fin = Math.min(inicio + itemsPerPage, totalProductos);
    const productosPagina = productos.slice(inicio, fin);

    // Usar DocumentFragment para renderizado eficiente
    const fragment = document.createDocumentFragment();

    // Detectar modo móvil
    const esMovil = window.innerWidth < 992;

    // Si es móvil, limpiar estilos de tabla para usar grid/flex si es necesario, 
    // pero aquí mantendremos el tbody y usaremos celdas block o cambiaremos el contenedor.
    // ESTRATEGIA: Si es móvil, no inyectamos TRs, inyectamos un solo TR con un TD que contiene el Grid de Cards.
    // O mejor, manipulamos el DOM para ocultar la tabla y mostrar un div de cards.
    // SIMPLIFICACION: Generar HTML de cards dentro del tbody (un tr por card con display block) o reemplazar contenido.

    // MEJOR OPCION: Detectar y renderizar Cards
    // const fragment = document.createDocumentFragment(); // YA DECLARADO ARRIBA

    if (esMovil) {
        // MODO MÓVIL: CARDS MODERNAS (PWA Style)
        productosPagina.forEach(p => {
            const tr = document.createElement('tr');
            tr.className = 'mobile-product-card-row'; // Usar clase en lugar de estilos inline pesados

            const semaforoColor = p.semaforo?.color || 'gray';
            const imagenUrl = p.imagen || '';
            const localImage = `/static/img/productos/${(p.codigo || '').trim()}.jpg`;

            tr.innerHTML = `
                <td class="mobile-card-cell">
                    <div class="mobile-product-card">
                        <div class="card-image-wrapper">
                            <img src="${localImage}" 
                                 class="card-img" 
                                 onerror="
                                    // Fallback: JPG -> PNG -> URL -> Placeholder
                                    if (this.src.match(/\.jpg$/)) { 
                                        this.src = this.src.replace('.jpg', '.png'); 
                                    } else if (this.src.match(/\.png$/) && '${imagenUrl}' !== '') { 
                                        this.src = '${imagenUrl}'; 
                                    } else { 
                                        this.src = '${PLACEHOLDER_SVG}';
                                        this.onerror = null; 
                                    }
                                 ">
                            <span class="mobile-status-badge" style="background: ${getSemaforoColor(semaforoColor)}"></span>
                        </div>
                        
                        <div class="card-content">
                            <div class="card-header-flex">
                                <span class="card-code">${p.codigo}</span>
                                <span class="card-status-text" style="color: ${getSemaforoColor(semaforoColor)}">${p.semaforo?.estado || ''}</span>
                            </div>
                            
                            <h6 class="card-title">${p.descripcion || 'Sin descripción'}</h6>
                            
                            <div class="card-stats-grid">
                                <div class="stat-item">
                                    <span class="stat-label">TOTAL</span>
                                    <span class="stat-value">${formatNumber(p.existencias_totales || 0)}</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-label">PULIR</span>
                                    <span class="stat-value secondary">${formatNumber(p.stock_por_pulir || 0)}</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-label">OK</span>
                                    <span class="stat-value success">${formatNumber(p.stock_terminado || 0)}</span>
                                </div>
                            </div>
                        </div>
                        <div class="card-arrow">
                            <i class="fas fa-chevron-right"></i>
                        </div>
                    </div>
                </td>
            `;
            fragment.appendChild(tr);
        });

    } else {
        // MODO DESKTOP: TABLA NORMAL
        productosPagina.forEach(p => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid #f0f0f0';

            // Obtener semáforo
            const semaforoColor = p.semaforo?.color || 'gray';
            const semaforoEstado = p.semaforo?.estado || '';

            // Imagen del producto (thumbnail)
            const imagenUrl = p.imagen || '';
            const localImage = `/static/img/productos/${(p.codigo || '').trim()}.jpg`;

            // Lógica de fallback en HTML string
            const imagenHtml = `
                <img src="${localImage}" 
                     style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px; cursor: pointer; background: white;" 
                     onclick="window.open(this.src, '_blank')" 
                     title="Click para ampliar"
                     onerror="
                        if (this.src.match(/\.jpg$/)) { 
                            this.src = this.src.replace('.jpg', '.png'); 
                        } else if (this.src.match(/\.png$/) && '${imagenUrl}' !== '') { 
                            this.src = '${imagenUrl}'; 
                        } else { 
                            this.src = '${PLACEHOLDER_SVG}';
                            this.style.opacity = '0.5';
                            this.onerror = null; 
                        }
                     ">`;

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
    }

    // Limpiar y agregar todo de una vez
    tbody.innerHTML = '';
    tbody.appendChild(fragment);

    // Renderizar controles de paginaciÃ³n
    renderizarPaginacion(totalProductos, totalPaginas, productos);

    console.log(`âœ… PÃ¡gina ${paginaActual}/${totalPaginas}: Mostrando ${productosPagina.length} de ${totalProductos} productos`);
}

/**
 * Renderizar controles de paginaciÃ³n
 */
function renderizarPaginacion(totalProductos, totalPaginas, productos) {
    const paginationDiv = document.getElementById('pagination-container');
    if (!paginationDiv) return;

    if (totalPaginas <= 1) {
        paginationDiv.innerHTML = '';
        return;
    }

    const itemsPerPage = getItemsPerPage();
    const inicio = (paginaActual - 1) * itemsPerPage + 1;
    const fin = Math.min(paginaActual * itemsPerPage, totalProductos);

    let html = `
        <div class="pagination-container" style="display: flex; justify-content: space-between; align-items: center; padding: 15px 0;">
            <div class="pagination-info" style="color: #666; font-size: 14px;">
                Mostrando <strong>${inicio}-${fin}</strong> de <strong>${totalProductos}</strong> productos
            </div>
            <div class="pagination-buttons" style="display: flex; gap: 5px;">
    `;

    // BotÃ³n anterior
    html += `
        <button 
            onclick="window.ModuloInventario.cambiarPagina(${paginaActual - 1})" 
            ${paginaActual === 1 ? 'disabled' : ''}
            class="pagination-btn"
            style="padding: 8px 12px; border: 1px solid #ddd; background: ${paginaActual === 1 ? '#f5f5f5' : 'white'}; border-radius: 4px; cursor: ${paginaActual === 1 ? 'not-allowed' : 'pointer'}; color: ${paginaActual === 1 ? '#ccc' : '#333'};"
        >
            <i class="fas fa-chevron-left"></i> <span class="btn-text">Anterior</span>
        </button>
    `;

    // NÃºmeros de pÃ¡gina (mÃ¡ximo 7 botones)
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
                class="pagination-btn"
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

    // BotÃ³n siguiente
    html += `
        <button 
            onclick="window.ModuloInventario.cambiarPagina(${paginaActual + 1})" 
            ${paginaActual === totalPaginas ? 'disabled' : ''}
            class="pagination-btn"
            style="padding: 8px 12px; border: 1px solid #ddd; background: ${paginaActual === totalPaginas ? '#f5f5f5' : 'white'}; border-radius: 4px; cursor: ${paginaActual === totalPaginas ? 'not-allowed' : 'pointer'}; color: ${paginaActual === totalPaginas ? '#ccc' : '#333'};"
        >
            <span class="btn-text">Siguiente</span> <i class="fas fa-chevron-right"></i>
        </button>
    `;

    html += `</div></div>`;
    paginationDiv.innerHTML = html;
}

/**
 * Cambiar pÃ¡gina
 */
function cambiarPagina(nuevaPagina) {
    const itemsPerPage = getItemsPerPage();
    const productosActuales = window.AppState.productosFiltrados || window.AppState.productosData || [];
    const totalPaginas = Math.ceil(productosActuales.length / itemsPerPage);

    if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;

    paginaActual = nuevaPagina;
    renderizarTablaProductos(productosActuales, false);

    // Scroll hacia arriba
    const tableContainer = document.querySelector('.table-container');
    if (tableContainer) tableContainer.scrollTop = 0;
}

/**
 * Obtener color de semÃ¡foro
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
 * Actualizar estadÃ­sticas de inventario
 */
function actualizarEstadisticasInventario(productos) {
    if (!productos || productos.length === 0) return;

    const totalProductos = productos.length;

    // Contar productos por estado de semáforo (Saneado Juan Sebastian)
    const stockOK = productos.filter(p => p.semaforo?.color === 'green').length;
    const porPedir = productos.filter(p => p.semaforo?.color === 'yellow').length; // Antes bajoStock
    // Agotados: Incluye 'red' (Critico) y 'dark' (Agotado <= 0)
    const agotados = productos.filter(p => p.semaforo?.color === 'red' || p.semaforo?.color === 'dark' || p.semaforo?.estado === 'AGOTADO').length;

    // Actualizar elementos del HTML
    const el_total = document.getElementById('total-productos');
    const el_stockOk = document.getElementById('productos-stock-ok');
    const el_bajoStock = document.getElementById('productos-bajo-stock');
    const el_agotados = document.getElementById('productos-agotados');

    if (el_total) el_total.textContent = totalProductos;
    if (el_stockOk) el_stockOk.textContent = stockOK;

    if (el_bajoStock) {
        el_bajoStock.textContent = porPedir;
        // Actualizar etiqueta si es necesario
        const label = el_bajoStock.nextElementSibling;
        if (label) label.textContent = 'Por Pedir';
    }

    if (el_agotados) el_agotados.textContent = agotados;

    console.log(`📊 Estadísticas: Total=${totalProductos}, OK=${stockOK}, PorPedir=${porPedir}, Agotados=${agotados}`);
}

/**
 * Inicializar módulo de inventario
 */
function inicializarInventario() {
    console.log('🔧 Inicializando módulo de Inventario...');
    configurarEventosInventario();
    cargarProductos();

    // Re-renderizar al redimensionar (Debounce)
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (window.AppState.productosData) {
                const prods = window.AppState.productosFiltrados || window.AppState.productosData;
                renderizarTablaProductos(prods, false);
            }
        }, 200);
    });

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
            console.log(`ðŸ” BÃºsqueda: "${query}" â†’ ${filtrados.length} resultados`);
        });
    }

    // Botones de filtro por estado de semÃ¡foro
    const botonesFiltro = document.querySelectorAll('#filtros-inventario button');
    botonesFiltro.forEach((btn, index) => {
        btn.addEventListener('click', () => {
            // Quitar 'active' de todos los botones
            botonesFiltro.forEach(b => b.classList.remove('active'));
            // Marcar este botÃ³n como activo
            btn.classList.add('active');

            if (!window.AppState.productosData) return;

            let productosFiltrados = [];
            const textoBtn = btn.textContent.trim().toLowerCase();

            // Filtrar segÃºn el botÃ³n clicado
            // Filtrar SEGÚN SEMÁFORO (CORREGIDO Juan Sebastian)
            if (textoBtn.includes('todos')) {
                productosFiltrados = window.AppState.productosData;
            } else if (textoBtn.includes('por pedir') || textoBtn.includes('pedir')) {
                // AMARILLO: Stock <= Reorden y > 0
                productosFiltrados = window.AppState.productosData.filter(p => p.semaforo?.color === 'yellow');
            } else if (textoBtn.includes('stock ok')) {
                // VERDE: Stock > Reorden
                productosFiltrados = window.AppState.productosData.filter(p => p.semaforo?.color === 'green');
            } else if (textoBtn.includes('agotados')) {
                // ROJO: Stock <= 0
                productosFiltrados = window.AppState.productosData.filter(p =>
                    p.semaforo?.estado === 'AGOTADO' || p.semaforo?.color === 'red' || p.semaforo?.color === 'dark'
                );
            }

            window.AppState.productosFiltrados = productosFiltrados;
            renderizarTablaProductos(productosFiltrados, true);
            console.log(`ðŸ”˜ Filtro: "${textoBtn}" â†’ ${productosFiltrados.length} productos`);
        });
    });

    // Botón actualizar
    const btnActualizar = document.getElementById('btn-actualizar-productos');
    if (btnActualizar) {
        btnActualizar.addEventListener('click', () => {
            console.log('🔄 Recargando productos (Forzando actualización)...');
            mostrarNotificacion('Actualizando inventario desde la nube...', 'info');
            cargarProductos(true); // Pasar true para forzar refresh
        });
    }
}

// ============================================
// EXPORTAR MÃ“DULO
// ============================================
window.ModuloInventario = {
    inicializar: inicializarInventario,
    cambiarPagina: cambiarPagina
};




