// ============================================
// inventario.js - LÃ³gica de Inventario con PaginaciÃ³n
// ============================================

// Configuración de paginación
const getItemsPerPage = () => window.innerWidth < 992 ? 20 : 50;
let paginaActual = 1;

// Placeholder premium de FriTech (SVG en base64 para evitar peticiones extra)
const PLACEHOLDER_SVG = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%23f8fafc;stop-opacity:1' /%3E%3Cstop offset='100%25' style='stop-color:%23e2e8f0;stop-opacity:1' /%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='100' height='100' fill='url(%23g)' rx='12'/%3E%3Cg opacity='0.4' transform='translate(0, -5)'%3E%3Cpath d='M30 40c0-2.2 1.8-4 4-4h32c2.2 0 4 1.8 4 4v25c0 2.2-1.8 4-4 4H34c-2.2 0-4-1.8-4-4V40z' fill='%2364748b'/%3E%3Ccircle cx='50' cy='52.5' r='7' fill='%23f1f5f9'/%3E%3Cpath d='M46 32h8l2 4h-12z' fill='%2364748b'/%3E%3C/g%3E%3Ctext x='50' y='82' text-anchor='middle' font-family='sans-serif' font-size='7' fill='%2394a3b8' font-weight='bold'%3EFriTech%3C/text%3E%3C/svg%3E`;

/**
 * Genera el HTML de la imagen con lógica de fallback multinivel (Súper Radar v3.0)
 * Orden: Imagen Pre-validada -> Local Original (.jpg) -> Local Limpio (.jpg) -> Local Limpio (.png) -> no-image.svg
 */
function obtenerHtmlImagen(p, esMovil = false) {
    const codigoOriginal = String(p.codigo || p.id_codigo || '').trim();
    const codigoLimpio = typeof limpiarCodigoJS === 'function' ? limpiarCodigoJS(codigoOriginal) : codigoOriginal;
    
    // Rutas de fallback
    const localImgOriginal = `/static/img/productos/${codigoOriginal}.jpg`;
    const localImgLimpio = `/static/img/productos/${codigoLimpio}.jpg`;
    const localImgPng = `/static/img/productos/${codigoLimpio}.png`;
    const cloudImg = p.imagen || '';
    
    // Si el backend ya validó una ruta, la usamos como punto de partida, si no, empezamos el radar
    const srcInicial = p.imagen_valida || localImgOriginal;
    
    // Estilos según vista
    const estilo = esMovil 
        ? 'width: 100%; height: 100%; object-fit: cover;' 
        : 'width: 40px; height: 40px; object-fit: cover; border-radius: 4px; cursor: pointer; background: white; border: 1px solid #eee;';
    
    const extraAttr = esMovil ? 'class="card-img"' : 'onclick="window.open(this.src, \'_blank\')" title="Click para ampliar"';

    return `
        <img src="${srcInicial}" 
             data-limpio-src="${localImgLimpio}"
             data-png-src="${localImgPng}"
             data-cloud-src="${cloudImg}"
             data-placeholder="${PLACEHOLDER_SVG}"
             data-attempt="0"
             style="${estilo}" 
             ${extraAttr} 
             onerror="
                const attempt = parseInt(this.dataset.attempt || '0');
                this.dataset.attempt = (attempt + 1).toString();
                
                if (attempt === 0) {
                    this.src = this.dataset.limpioSrc;
                } else if (attempt === 1) {
                    this.src = this.dataset.pngSrc;
                } else if (attempt === 2 && this.dataset.cloudSrc && this.dataset.cloudSrc.length > 10) {
                    this.src = this.dataset.cloudSrc;
                } else {
                    this.src = this.dataset.placeholder;
                    this.onerror = null;
                }
             ">
    `;
}

/**
 * Cargar productos para inventario
 */
async function cargarProductos(forceRefresh = false) {
    try {
        console.log('📦 Cargando productos...');
        mostrarLoading(true);

        const isMetals = window.AppState.user?.division === 'FRIMETALS';
        let url = isMetals ? '/api/metals/productos/listar' : '/api/productos/listar';

        if (forceRefresh && !isMetals) {
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
        } else if (data.productos && Array.isArray(data.productos)) {
            listaFinal = data.productos;
        } else if (Array.isArray(data)) {
            listaFinal = data;
        }

        if (listaFinal.length > 0) {
            // Normalizar las claves para que coincidan con lo que espera el frontend (minúsculas)
            window.AppState.productosData = listaFinal.map(p => {
                const term = p.stock_terminado || p.TERMINADO || 0;
                const comp = p.stock_comprometido || 0;
                const min = p.stock_minimo || p.MINIMO || 10;
                const disp = term - comp;

                // Lógica de Semáforo (Fase 2: Frontend Visibility)
                let semaforo = { color: 'green', estado: 'STOCK OK' };
                if (disp <= 0) {
                    semaforo = { color: 'red', estado: 'AGOTADO' };
                } else if (disp < min) {
                    semaforo = { color: 'yellow', estado: 'POR PEDIR' };
                }

                return {
                    codigo: p.codigo || p.CODIGO || '',
                    descripcion: p.descripcion || p.DESCRIPCION || '',
                    precio: p.precio || p.PRECIO || 0,
                    stock_disponible: disp,
                    stock_terminado: term,
                    stock_comprometido: comp,
                    stock_bodega: p.stock_bodega || p.STOCK_BODEGA || 0,
                    en_zincado: p.en_zincado || 0,
                    en_granallado: p.en_granallado || 0,
                    stock_minimo: min,
                    semaforo: semaforo,
                    imagen_valida: p.imagen_valida // Juan Sebastian: Usar ruta pre-validada por backend
                };
            });
            paginaActual = 1; // Resetear a página 1
            renderizarTablaProductos(window.AppState.productosData);
            actualizarEstadisticasInventario(window.AppState.productosData);
            console.log('✅ Productos cargados y normalizados:', window.AppState.productosData.length);
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
            const localImageJpg = `/static/img/productos/${(p.codigo || '').trim()}.jpg`;
            const localImagePng = `/static/img/productos/${(p.codigo || '').trim()}.png`;

            tr.innerHTML = `
                <td class="mobile-card-cell">
                    <div class="mobile-product-card">
                        <div class="card-image-wrapper">
                            ${obtenerHtmlImagen(p, true)}
                            <span class="mobile-status-badge" style="background: ${getSemaforoColor(semaforoColor)}"></span>
                        </div>
                        
                        <div class="card-content">
                            <div class="card-header-flex">
                                <span class="card-code" onclick="event.preventDefault(); window.abrirModalHistorial('${p.codigo}');" style="text-decoration: underline; cursor: pointer; color: #0d6efd;">${p.codigo}</span>
                                <span class="card-status-text" style="color: ${getSemaforoColor(semaforoColor)}">${p.semaforo?.estado || ''}</span>
                            </div>
                            
                            <h6 class="card-title">${p.descripcion || 'Sin descripción'}</h6>
                            
                            <div class="card-stats-grid">
                                <div class="stat-item" title="Producto Terminado">
                                    <span class="stat-label">TERMINADO</span>
                                    <span class="stat-value success">${formatNumber(p.stock_terminado || 0)}</span>
                                </div>
                                <div class="stat-item" title="Unidades ya asignadas a pedidos">
                                    <span class="stat-label">COMPROM.</span>
                                    <span class="stat-value danger" style="color: #ef4444;">${formatNumber(p.stock_comprometido || 0)}</span>
                                </div>
                                <div class="stat-item" title="Calculado: TERMINADO - COMPROMETIDO">
                                    <span class="stat-label">DISPONIBLE</span>
                                    <span class="stat-value" style="color: ${(p.stock_terminado - p.stock_comprometido) < p.stock_minimo ? '#dc2626' : '#2563eb'}; font-weight: 800;">
                                        ${(p.stock_terminado - p.stock_comprometido) < p.stock_minimo ? '⚠️ ' : ''}
                                        ${formatNumber((p.stock_terminado || 0) - (p.stock_comprometido || 0))}
                                    </span>
                                </div>
                                <div class="stat-item" title="Materia Prima en Bodega">
                                    <span class="stat-label">BODEGA (MP)</span>
                                    <span class="stat-value" style="color: #f59e0b;">${formatNumber(p.stock_bodega || 0)}</span>
                                </div>
                                <div class="stat-item" title="Procesos Externos (Zincado/Granallado)">
                                    <span class="stat-label">TRÁNSITO</span>
                                    <span class="stat-value" style="color: #8b5cf6;">${formatNumber((p.en_zincado || 0) + (p.en_granallado || 0))}</span>
                                </div>
                                <div class="stat-item" title="Mínimo Requerido">
                                    <span class="stat-label">MIN</span>
                                    <span class="stat-value secondary">${formatNumber(p.stock_minimo || 0)}</span>
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
        productosPagina.forEach((p, idx) => {
            const tr = document.createElement('tr');
            tr.className = `animate-on-scroll delay-${(idx % 4) + 1}`; // Efecto cascada continuo
            tr.style.borderBottom = '1px solid #f0f0f0';

            // Obtener semáforo
            const semaforoColor = p.semaforo?.color || 'gray';
            const semaforoEstado = p.semaforo?.estado || '';

            // Cálculo de Disponible
            const stockTerminado = p.stock_terminado || 0;
            const stockComprometido = p.stock_comprometido || 0;
            const stockMinimo = p.stock_minimo || 0;
            const disponible = stockTerminado - stockComprometido;
            const bajoMinimo = disponible < stockMinimo;

            // ESTADO DE AUDITORÍA
            const tieneDiscrepancia = p.estado_auditoria === 'DISCREPANCIA';
            if (tieneDiscrepancia) {
                tr.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'; // Naranja/Rojo muy claro
                tr.style.borderLeft = '4px solid #ef4444';
            }

            tr.innerHTML = `
                <td style="padding: 10px; text-align: center;">${obtenerHtmlImagen(p, false)}</td>
                <td style="padding: 10px;"><a href="#" onclick="event.preventDefault(); window.abrirModalHistorial('${p.codigo}');" class="text-primary fw-bold text-decoration-underline" style="cursor: pointer;" title="Ver trazabilidad completa">${p.codigo || '-'}</a></td>
                <td style="padding: 10px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    ${p.descripcion || '-'}
                    ${tieneDiscrepancia ? '<br><span class="badge bg-danger" style="font-size: 10px;">DISCREPANCIA DETECTADA</span>' : ''}
                </td>
                <td style="padding: 10px; text-align: right; color: #64748b;">${formatNumber(stockTerminado)}</td>
                <td style="padding: 10px; text-align: right; color: #ef4444;">${formatNumber(stockComprometido)}</td>
                <td style="padding: 10px; text-align: right; font-weight: ${bajoMinimo ? 'bold' : '600'}; color: ${bajoMinimo ? '#dc2626' : '#2563eb'};">
                    ${bajoMinimo ? '<i class="fas fa-exclamation-triangle" title="Bajo el Mínimo!"></i> ' : ''}
                    ${formatNumber(disponible)}
                </td>
                <td style="padding: 10px; text-align: right; color: #f59e0b; font-weight: 500;">${formatNumber(p.stock_bodega || 0)}</td>
                <td style="padding: 10px; text-align: right; color: #8b5cf6; font-weight: 500;" title="Zincado: ${formatNumber(p.en_zincado || 0)} | Granallado: ${formatNumber(p.en_granallado || 0)}">${formatNumber((p.en_zincado || 0) + (p.en_granallado || 0))}</td>
                <td style="padding: 10px; text-align: center;">
                    ${tieneDiscrepancia 
                        ? `<button class="btn btn-danger btn-sm w-100 fw-bold" onclick="window.ModuloInventario.abrirModalConteo('${p.codigo}')" style="font-size: 11px;">
                             <i class="fas fa-gavel"></i> CONTEO 3 (ADMIN)
                           </button>`
                        : `<span style="background: ${getSemaforoColor(semaforoColor)}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 500;">
                             ${semaforoEstado}
                           </span>`
                    }
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

    // Actualizar elementos del HTML (Soporta IDs viejos y nuevos de Premium UI)
    const el_total = document.getElementById('val-total-prod') || document.getElementById('total-productos');
    const el_stockOk = document.getElementById('val-stock-ok') || document.getElementById('productos-stock-ok');
    const el_bajoStock = document.getElementById('val-bajo-stock') || document.getElementById('productos-bajo-stock');
    const el_agotados = document.getElementById('val-agotados') || document.getElementById('productos-agotados');

    if (el_total) el_total.textContent = formatNumber(totalProductos);
    if (el_stockOk) el_stockOk.textContent = formatNumber(stockOK);

    if (el_bajoStock) {
        el_bajoStock.textContent = formatNumber(porPedir || 0);
    }

    if (el_agotados) el_agotados.textContent = formatNumber(agotados);

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
                String(p.codigo || '').toLowerCase().includes(query) ||
                String(p.descripcion || '').toLowerCase().includes(query)
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
            cargarProductos(true);
        });
    }

    // Botón Conteo / Auditoría
    const btnConteo = document.getElementById('btn-conteo-inventario');
    if (btnConteo) {
        btnConteo.addEventListener('click', () => {
            abrirModalConteo();
        });
    }

    // Formulario de Conteo
    const formConteo = document.getElementById('form-conteo-inventario');
    if (formConteo) {
        formConteo.addEventListener('submit', (e) => {
            e.preventDefault();
            const inputAutocomplete = document.getElementById('conteo-producto-autocomplete');
            const hiddenCodigo = document.getElementById('conteo-producto-codigo');
            
            // Si el hidden no tiene valor, intentar parsear del input visual
            let codigoVal = hiddenCodigo.value;
            if (!codigoVal && inputAutocomplete.value.includes(' - ')) {
                codigoVal = inputAutocomplete.value.split(' - ')[0].trim();
            } else if (!codigoVal) {
                codigoVal = inputAutocomplete.value.trim();
            }

            if (!codigoVal) {
                Swal.fire('Error', 'Debe seleccionar un producto válido', 'warning');
                return;
            }

            const data = {
                codigo: codigoVal,
                cantidad: parseInt(document.getElementById('conteo-cantidad').value),
                tipo_stock: document.querySelector('input[name="tipo_stock"]:checked')?.value || 'principal',
                responsable: document.getElementById('conteo-responsable').value,
                observaciones: document.getElementById('conteo-observaciones').value
            };
            registrarConteo(data);
        });
    }

    // Inicializar Autocomplete para Auditoría
    inicializarAutocompleteAuditoria();
}

/**
 * Autocomplete avanzado para Auditoría
 */
function inicializarAutocompleteAuditoria() {
    const input = document.getElementById('conteo-producto-autocomplete');
    const suggestionsDiv = document.getElementById('conteo-producto-suggestions');
    const hiddenCodigo = document.getElementById('conteo-producto-codigo');

    if (!input || !suggestionsDiv) return;

    let debounceTimer;

    input.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        const query = e.target.value.trim();
        hiddenCodigo.value = ''; // Resetear al escribir

        if (query.length < 2) {
            suggestionsDiv.style.display = 'none';
            return;
        }

        debounceTimer = setTimeout(() => {
            const productos = window.AppState.productosData || [];
            const queryNorm = query.toLowerCase();
            
            const filtrados = productos.filter(p => {
                const code = String(p.codigo || '').toLowerCase();
                const desc = String(p.descripcion || '').toLowerCase();
                return code.includes(queryNorm) || desc.includes(queryNorm);
            });

            if (filtrados.length === 0) {
                suggestionsDiv.innerHTML = '<div class="suggestion-item text-muted">No se encontraron productos</div>';
                suggestionsDiv.style.display = 'block';
                return;
            }

            // Usar la utilidad global de renderizado si existe, o implementarla localmente
            if (typeof window.renderProductSuggestions === 'function') {
                window.renderProductSuggestions(suggestionsDiv, filtrados.slice(0, 15), (item) => {
                    input.value = `${item.codigo} - ${item.descripcion}`;
                    hiddenCodigo.value = item.codigo;
                    suggestionsDiv.style.display = 'none';
                    // Saltar a cantidad
                    document.getElementById('conteo-cantidad')?.focus();
                });
                suggestionsDiv.style.display = 'block';
            } else {
                // Fallback local
                suggestionsDiv.innerHTML = filtrados.slice(0, 15).map(p => `
                    <div class="suggestion-item p-2 border-bottom" style="cursor: pointer;" data-code="${p.codigo}">
                        <strong>${p.codigo}</strong> - ${p.descripcion}
                    </div>
                `).join('');
                suggestionsDiv.style.display = 'block';
                
                suggestionsDiv.querySelectorAll('.suggestion-item').forEach(el => {
                    el.onclick = () => {
                        const code = el.getAttribute('data-code');
                        const p = filtrados.find(x => x.codigo === code);
                        input.value = `${p.codigo} - ${p.descripcion}`;
                        hiddenCodigo.value = p.codigo;
                        suggestionsDiv.style.display = 'none';
                        document.getElementById('conteo-cantidad')?.focus();
                    };
                });
            }
        }, 300);
    });

    // Cerrar al click fuera
    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
            suggestionsDiv.style.display = 'none';
        }
    });

    // Configurar SmartEnter
    if (window.ModuloUX && window.ModuloUX.setupSmartEnter) {
        window.ModuloUX.setupSmartEnter({
            inputIds: ['conteo-producto-autocomplete', 'conteo-cantidad', 'conteo-responsable', 'conteo-observaciones'],
            actionBtnId: 'btn-registrar-conteo-submit', // Asegúrate de que el botón tenga este ID o usa el submit del form
            autocomplete: {
                inputId: 'conteo-producto-autocomplete',
                suggestionsId: 'conteo-producto-suggestions'
            }
        });
    }
}

/**
 * Lógica de Auditoría / Conteo
 */
function abrirModalConteo(codigoDefecto = null) {
    const modal = document.getElementById('modalConteoInventario');
    const inputAutocomplete = document.getElementById('conteo-producto-autocomplete');
    const hiddenCodigo = document.getElementById('conteo-producto-codigo');
    const selectResp = document.getElementById('conteo-responsable');

    if (!modal) return;

    // VALIDACIÓN DE PERMISOS PARA CONTEO 3 (DISCREPANCIAS)
    if (codigoDefecto) {
        const productos = window.AppState.productosData || [];
        const prod = productos.find(p => p.codigo === codigoDefecto);
        
        if (prod && prod.estado_auditoria === 'DISCREPANCIA') {
            const userRole = (window.AppState.user?.rol || '').toLowerCase();
            const esAutorizado = userRole.includes('admin') || userRole.includes('supervisor');
            
            if (!esAutorizado) {
                Swal.fire({
                    icon: 'lock',
                    title: 'Acceso Restringido',
                    text: 'Solo un Administrador o Supervisor puede resolver una discrepancia de inventario (Conteo 3).',
                    confirmButtonColor: '#ef4444'
                });
                return;
            }
        }
    }

    // Resetear campos
    if (inputAutocomplete) inputAutocomplete.value = '';
    if (hiddenCodigo) hiddenCodigo.value = '';
    
    // Resetear radio buttons a 'principal'
    const radioPrincipal = document.getElementById('tipo-stock-principal');
    if (radioPrincipal) radioPrincipal.checked = true;

    // Si viene un código por defecto (ej: desde el botón de la tabla), seleccionarlo
    if (codigoDefecto && inputAutocomplete) {
        const prod = (window.AppState.productosData || []).find(p => p.codigo === codigoDefecto);
        if (prod) {
            inputAutocomplete.value = `${prod.codigo} - ${prod.descripcion}`;
            hiddenCodigo.value = prod.codigo;
        } else {
            inputAutocomplete.value = codigoDefecto;
            hiddenCodigo.value = codigoDefecto;
        }
    }

    // Limpiar cantidad previa
    const inputCantidad = document.getElementById('conteo-cantidad');
    if (inputCantidad) inputCantidad.value = '';

    // Poblar responsables (Corregido: r es un objeto {nombre, departamento})
    if (selectResp && selectResp.options.length <= 1) {
        const responsables = window.AppState.sharedData?.responsables || [];
        console.log('👥 Poblando responsables en modal:', responsables);

        responsables.forEach(r => {
            const nombre = typeof r === 'object' ? r.nombre : r;
            const opt = document.createElement('option');
            opt.value = nombre;
            opt.textContent = nombre;
            selectResp.appendChild(opt);
        });
    }

    modal.style.display = 'flex';
    document.getElementById('form-conteo-inventario')?.reset();
}

function cerrarModalConteo() {
    const modal = document.getElementById('modalConteoInventario');
    if (modal) modal.style.display = 'none';
}

async function registrarConteo(data) {
    try {
        console.log('📤 Enviando conteo:', data);
        mostrarLoading(true);

        const response = await fetch('/api/conteo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            throw new Error('Respuesta no válida del servidor');
        }

        const result = await response.json();
        
        // CERRAR LOADER ANTES DE MOSTRAR ALERTAS (Crucial para evitar bloqueo)
        mostrarLoading(false);

        // --- SOLUCIÓN UX: CERRAR Y LIMPIAR MODAL DE INMEDIATO ---
        cerrarModalConteo();
        document.getElementById('form-conteo-inventario')?.reset(); 

        // Nueva lógica alineada con el Backend estandarizado
        const msg = result.mensaje || result.message || "Operación completada";

        if (result.status === 'discrepancy') {
            await Swal.fire({
                icon: 'warning',
                title: '¡ALERTA DE DISCREPANCIA!',
                text: msg,
                confirmButtonText: 'Entendido, llamar a Supervisor',
                confirmButtonColor: '#d33', // Rojo vibrante solicitado
                allowOutsideClick: false,
                allowEscapeKey: false
            });
        } else if (result.status === 'first_count') {
            await Swal.fire({
                icon: 'info',
                title: 'Primer Conteo Registrado',
                text: msg,
                timer: 2500,
                showConfirmButton: false
            });
        } else if (result.status === 'match' || result.success) {
            await Swal.fire({
                icon: 'success',
                title: 'Auditoría Exitosa',
                text: msg,
                timer: 2000,
                showConfirmButton: false
            });
        } else {
            Swal.fire('Error', result.error || msg || 'No se pudo guardar el conteo', 'error');
        }

        if (typeof cargarProductos === 'function') {
            cargarProductos(true); // Refrescar para ver estado de discrepancia en tabla
        }
    } catch (error) {
        mostrarLoading(false);
        console.error('Error:', error);
        Swal.fire('Error de Conexión', 'No se pudo comunicar con el servidor o la respuesta no es válida.', 'error');
    } finally {
        // Doble aseguramiento
        mostrarLoading(false);
    }
}

// ============================================
// EXPORTAR MÃ“DULO
// ============================================
window.ModuloInventario = {
    inicializar: inicializarInventario,
    cambiarPagina: cambiarPagina,
    cerrarModalConteo: cerrarModalConteo
};

/**
 * Función puente global para abrir el Modal de Historial.
 * Se invoca desde in-place en la tabla y llama al módulo Historial sin recargar.
 */
window.abrirModalHistorial = function(codigo) {
    if (window.ModuloHistorial && typeof window.ModuloHistorial.irAProducto === 'function') {
        window.ModuloHistorial.irAProducto(codigo);
    } else {
        console.error("Módulo de Trazabilidad/Historial no se encuentra disponible.");
        if (typeof Swal !== 'undefined') {
            Swal.fire('Atención', 'El módulo de trazabilidad no está disponible en esta vista.', 'info');
        } else {
            alert('El módulo de trazabilidad no está disponible.');
        }
    }
};
