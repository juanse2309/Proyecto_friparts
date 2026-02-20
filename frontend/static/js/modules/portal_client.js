
// portal_client.js - Lógica del Portal B2B para Clientes

const ModuloPortal = {
    productos: [],
    carrito: [],
    carrito: [],
    pedidos: [],
    pollingInterval: null,
    POLLING_DELAY: 15000, // 15 segundos

    init: async function () {
        console.log("🛒 Inicializando Portal de Clientes...");

        // 1. Cargar Productos
        await this.cargarCatalogo();

        // 2. Cargar Pedidos Históricos
        await this.cargarMisPedidos();

        // 3. Restaurar carrito
        this.cargarCarritoLocal();
        this.actualizarBadge();

        // 4. Renderizar Vista Inicial
        // (El loader se encargará de ocultarse al terminar cargarCatalogo)
        this.renderizarBotonFlotante();

        // 5. Listener Global para "Enter" (Navegación Rápida)
        document.addEventListener('keydown', (e) => {
            // Solo si estamos en el tab Catálogo y es un input numérico
            if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.type === 'number' && e.target.id.startsWith('qty-')) {
                e.preventDefault();

                // 1. Agregar al carrito
                const code = e.target.id.replace('qty-', '');
                if (code) {
                    this.agregarAlCarrito(code);
                }

                // 2. Mover foco al siguiente input visible
                // Buscamos todos los inputs visibles en la tabla
                const allInputs = Array.from(document.querySelectorAll('#product-grid input[type="number"]'));
                const currentIndex = allInputs.indexOf(e.target);

                if (currentIndex !== -1 && currentIndex < allInputs.length - 1) {
                    const nextInput = allInputs[currentIndex + 1];
                    nextInput.focus();
                    nextInput.select();
                    // Scroll suave si es necesario para mantenerlo visible
                    nextInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });

        console.log("✅ Portal Listo");
    },

    toggleLoader: function (show) {
        let loader = document.getElementById('portal-loader-overlay');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'portal-loader-overlay';
            loader.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.6); z-index: 9999;
                display: none; align-items: center; justify-content: center;
                backdrop-filter: blur(3px);
            `;
            loader.innerHTML = `
                <div class="text-center">
                    <div class="spinner-border text-light" style="width: 3rem; height: 3rem;" role="status"></div>
                    <div class="text-light mt-3 fw-bold">Cargando catálogo...</div>
                </div>
            `;
            document.body.appendChild(loader);
        }
        loader.style.display = show ? 'flex' : 'none';
    },

    renderizarBotonFlotante: function () {
        if (document.getElementById('floating-cart-btn')) return;

        const btn = document.createElement('button');
        btn.id = 'floating-cart-btn';
        btn.className = 'btn btn-primary rounded-circle shadow-lg d-flex align-items-center justify-content-center animate-bounce';
        btn.style.cssText = `
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 65px;
            height: 65px;
            z-index: 1050;
            border: 4px solid white;
            transition: transform 0.2s;
        `;
        btn.innerHTML = `
            <i class="fas fa-shopping-cart fa-lg"></i>
            <span id="floating-cart-count" class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger border border-light" style="font-size: 0.8rem; display: none;">
                0
            </span>
        `;
        btn.onclick = () => this.verCarrito();
        btn.onmouseover = () => btn.style.transform = 'scale(1.1)';
        btn.onmouseout = () => btn.style.transform = 'scale(1)';

        document.body.appendChild(btn);
        this.actualizarBadge();
    },

    // =================================================================
    // GESTIÓN DE PESTAÑAS
    // =================================================================
    // GESTIÓN DE PESTAÑAS
    switchTab: function (tabName) {
        // Update nav buttons
        const btnCatalogo = document.querySelector('#portal-tabs button[onclick*="catalogo"]');
        const btnPedidos = document.querySelector('#portal-tabs button[onclick*="mis-pedidos"]');

        // Reset styles (Outline by default)
        [btnCatalogo, btnPedidos].forEach(btn => {
            if (btn) {
                btn.className = 'btn btn-outline-primary rounded-pill px-4 fw-bold shadow-sm';
                btn.style.borderWidth = '2px';
            }
        });

        // Activate selected (Solid Blue)
        const activeBtn = tabName === 'catalogo' ? btnCatalogo : btnPedidos;
        if (activeBtn) {
            activeBtn.className = 'btn btn-primary rounded-pill px-4 fw-bold shadow';
        }

        // Update content visibility
        const contentCatalogo = document.getElementById('portal-tab-catalogo');
        const contentPedidos = document.getElementById('portal-tab-mis-pedidos');

        if (contentCatalogo) contentCatalogo.style.display = 'none';
        if (contentPedidos) contentPedidos.style.display = 'none';

        if (tabName === 'catalogo' && contentCatalogo) {
            contentCatalogo.style.display = 'block';
            // Scroll to top of catalog
            // contentCatalogo.scrollIntoView({ behavior: 'smooth' }); 
        }
        if (tabName === 'mis-pedidos' && contentPedidos) {
            contentPedidos.style.display = 'block';
            this.cargarMisPedidos(); // Reload data when switching
            this.startPolling(); // Iniciar auto-refresh
        } else {
            this.stopPolling(); // Detener si salimos del tab
        }
    },

    // =================================================================
    // CATÁLOGO
    // =================================================================

    cargarCatalogo: function () {
        return new Promise(async (resolve) => {
            try {
                this.toggleLoader(true); // Mostrar Loader

                // Usamos el endpoint oficial de productos
                const response = await fetch('/api/productos/listar');
                const data = await response.json();

                if (data.error) {
                    console.error("Error cargando catalogo:", data.error);
                    return;
                }

                // Normalizar respuesta (array vs objeto)
                let items = [];
                if (Array.isArray(data)) items = data;
                else if (data.items && Array.isArray(data.items)) items = data.items;
                else if (data.productos && Array.isArray(data.productos)) items = data.productos;

                this.productos = items.map(p => ({
                    id: p.id_codigo || p.ID_CODIGO || p.ID || 0,
                    codigo: p.codigo || p.codigo_sistema || p.CODIGO || '',
                    descripcion: p.descripcion || p.DESCRIPCION || '',
                    stock: p.stock_disponible ?? p.existencias_totales ?? p.stock_total ?? 0,
                    precio: p.precio || p.PRECIO || 0,
                    imagen: p.imagen || '/static/img/no-image.png'
                }));

                // Renderizar inmediatamente después de cargar
                this.renderizarProductos();

            } catch (e) {
                console.error("Error network catalogo:", e);
            } finally {
                // Ensure loader is hidden even if error
                setTimeout(() => this.toggleLoader(false), 300); // Pequeño delay para suavidad
                resolve();
            }
        });
    },

    // PAGINACIÓN
    currentPage: 1,
    itemsPerPage: 100,
    currentFilteredProducts: [], // Para mantener estado de busqueda + paginacion
    viewMode: 'list', // 'list' | 'grid'

    renderizarProductos: function (productos) {
        const grid = document.getElementById('product-grid');

        // Determinar lista base: si pasan productos (ej: filtro), usarlos. Si no, usar this.productos completos.
        // PERO: Si renderizarProductos se llama sin argumentos (reload), debemos ver si hay filtro activo o usar todo.
        // Simplificación: Si 'productos' es undefined, usamos this.productos.
        // Actualizamos 'currentFilteredProducts' solo si se pasa un array explicito (filtro o carga inicial).
        if (productos) {
            this.currentFilteredProducts = productos;
            this.currentPage = 1; // Reset a pagina 1 al cambiar datos
        } else if (this.currentFilteredProducts.length === 0 && this.productos.length > 0) {
            this.currentFilteredProducts = this.productos; // Init default
        }

        const listaTotal = this.currentFilteredProducts;

        if (!listaTotal || listaTotal.length === 0) {
            grid.innerHTML = '<div class="col-12 text-center text-muted py-5">No se encontraron productos.</div>';
            return;
        }

        // --- Paginación Slice ---
        const start = (this.currentPage - 1) * this.itemsPerPage;
        const end = start + this.itemsPerPage;
        const listaPagina = listaTotal.slice(start, end);
        const totalPages = Math.ceil(listaTotal.length / this.itemsPerPage);

        // Detectar viewport móvil
        const isMobile = window.innerWidth <= 768;

        if (isMobile) {
            this.renderizarProductosMobile(grid, listaPagina, totalPages);
        } else {
            if (this.viewMode === 'grid') {
                this.renderizarProductosGrid(grid, listaPagina, totalPages);
            } else {
                this.renderizarProductosDesktop(grid, listaPagina, totalPages, listaTotal, start, end);
            }
        }
    },

    setViewMode: function (mode) {
        this.viewMode = mode;
        const btnList = document.getElementById('btn-view-list');
        const btnGrid = document.getElementById('btn-view-grid');

        if (btnList) btnList.classList.toggle('active', mode === 'list');
        if (btnGrid) btnGrid.classList.toggle('active', mode === 'grid');

        this.renderizarProductos();
    },

    renderizarProductosGrid: function (grid, listaPagina, totalPages) {
        grid.style.display = 'grid';
        grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(220px, 1fr))';
        grid.style.gap = '20px';
        grid.className = '';

        const cards = listaPagina.map(p => {
            const localImage = `/static/img/productos/${p.codigo.trim()}.jpg`;
            const noImage = '/static/img/no-image.svg';

            return `
                <div class="card h-100 shadow-sm hover-lift border-0">
                    <div class="position-relative bg-white rounded-top" style="height: 180px; overflow: hidden; display: flex; align-items: center; justify-content: center;">
                        <img src="${localImage}" 
                             alt="${p.codigo}"
                             style="max-height: 100%; max-width: 100%; object-fit: contain; padding: 1rem;" 
                             onerror="if(this.src.endsWith('.jpg')){this.src=this.src.replace('.jpg','.png')}else{this.onerror=null;this.src='${noImage}'}"
                             onclick="window.open(this.src, '_blank')"
                             class="cursor-pointer">
                         <div class="position-absolute top-0 end-0 p-2">
                             ${this.getStockBadge(p.stock)}
                         </div>
                    </div>
                    <div class="card-body d-flex flex-column bg-light bg-opacity-10">
                        <h6 class="card-title fw-bold text-dark mb-1 text-truncate" title="${p.descripcion}" style="font-size: 0.95rem;">${p.descripcion}</h6>
                        <small class="text-muted mb-3 d-block font-monospace">${p.codigo}</small>
                        
                        <div class="mt-auto">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <span class="h5 mb-0 text-primary fw-bold">${p.precio > 0 ? '$' + p.precio.toLocaleString() : '<small>Consultar</small>'}</span>
                            </div>
                            <div class="d-flex gap-2">
                                <input type="number" id="qty-${p.codigo}" class="form-control text-center fw-bold" value="1" min="1" style="max-width: 60px;">
                                <button class="btn btn-primary flex-grow-1" onclick="ModuloPortal.agregarAlCarrito('${p.codigo}')">
                                    <i class="fas fa-cart-plus"></i> <span class="small">Agregar</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        const paginationControls = `
            <div class="col-12 mt-4">
                <div class="d-flex justify-content-center gap-2">
                    <button class="btn btn-outline-secondary btn-sm" 
                        ${this.currentPage <= 1 ? 'disabled' : ''} 
                        onclick="ModuloPortal.cambiarPagina(-1)">
                        <i class="fas fa-chevron-left"></i> Anterior
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" disabled>
                        ${this.currentPage} / ${totalPages}
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" 
                        ${this.currentPage >= totalPages ? 'disabled' : ''} 
                        onclick="ModuloPortal.cambiarPagina(1)">
                        Siguiente <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
            </div>
        `;

        grid.innerHTML = cards + paginationControls;
    },

    renderizarProductosMobile: function (grid, listaPagina, totalPages) {
        grid.className = 'w-100';
        grid.style.display = 'block';

        const cards = listaPagina.map(p => {
            const localImage = `/static/img/productos/${p.codigo.trim()}.jpg`;
            const noImage = '/static/img/no-image.svg';

            const stockBadge = p.stock > 50
                ? `<span class="badge bg-success text-white">Disponible (${p.stock})</span>`
                : p.stock > 0
                    ? `<span class="badge bg-warning text-dark">Pocas unidades (${p.stock})</span>`
                    : p.stock <= 0
                        ? `<span class="badge bg-secondary">Bajo Pedido</span>`
                        : `<span class="badge bg-danger">Agotado</span>`;

            return `
                <div class="product-card-mobile">
                    <img src="${localImage}" 
                         alt="${p.codigo}"
                         class="product-image"
                         onclick="window.open(this.src, '_blank')"
                         onerror="if(this.src.endsWith('.jpg')){this.src=this.src.replace('.jpg','.png')}else{this.onerror=null;this.src='${noImage}'}">
                    <div class="product-info">
                        <div class="product-name">${p.descripcion}</div>
                        <div class="product-code">${p.codigo}</div>
                        <div class="d-flex align-items-center gap-2 mt-1">
                            ${stockBadge}
                        </div>
                        <div class="product-price mt-2">
                            ${p.precio > 0 ? '$' + p.precio.toLocaleString() : '<span class="text-muted small">Consultar</span>'}
                        </div>
                        <div class="quantity-selector">
                            <button class="btn btn-outline-secondary" onclick="
                                const input = document.getElementById('qty-${p.codigo}');
                                if (input.value > 1) input.value = parseInt(input.value) - 1;
                            ">
                                <i class="fas fa-minus"></i>
                            </button>
                            <input type="number" id="qty-${p.codigo}" class="form-control" value="1" min="1">
                            <button class="btn btn-outline-secondary" onclick="
                                const input = document.getElementById('qty-${p.codigo}');
                                input.value = parseInt(input.value) + 1;
                            ">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                        <button class="btn btn-primary add-to-cart-btn" onclick="ModuloPortal.agregarAlCarrito('${p.codigo}')">
                            <i class="fas fa-shopping-cart me-2"></i>Agregar al Carrito
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        const paginationControls = totalPages > 1 ? `
            <div class="d-flex justify-content-center gap-2 mt-4 mb-3">
                <button class="btn btn-outline-secondary btn-sm" 
                    ${this.currentPage <= 1 ? 'disabled' : ''} 
                    onclick="ModuloPortal.cambiarPagina(-1)">
                    <i class="fas fa-chevron-left"></i> Anterior
                </button>
                <button class="btn btn-outline-secondary btn-sm" disabled>
                    ${this.currentPage} / ${totalPages}
                </button>
                <button class="btn btn-outline-secondary btn-sm" 
                    ${this.currentPage >= totalPages ? 'disabled' : ''} 
                    onclick="ModuloPortal.cambiarPagina(1)">
                    Siguiente <i class="fas fa-chevron-right"></i>
                </button>
            </div>
        ` : '';

        grid.innerHTML = cards + paginationControls;
    },

    renderizarProductosDesktop: function (grid, listaPagina, totalPages, listaTotal, start, end) {
        // VISTA LISTA (Tabla) - Desktop
        grid.className = 'w-100';
        grid.style.display = 'block';
        grid.style.gridTemplateColumns = 'none';
        grid.style.gap = '0';

        const tableHeader = `
            <div class="table-responsive">
                <table class="table table-hover align-middle shadow-sm rounded-3 overflow-hidden responsive-mobile" style="background: white;">
                    <thead class="bg-light text-secondary small text-uppercase">
                        <tr>
                            <th scope="col" class="ps-4" style="width: 80px;">Img</th>
                            <th scope="col" style="min-width: 200px;">Producto</th>
                            <th scope="col" class="text-center">Stock</th>
                            <th scope="col" class="text-end" style="min-width: 100px;">Precio</th>
                            <th scope="col" class="text-center" style="width: 180px;">Solicitar</th>
                        </tr>
                    </thead>
                    <tbody class="border-top-0">
        `;

        const tableBody = listaPagina.map(p => {
            const localImage = `/static/img/productos/${p.codigo.trim()}.jpg`;
            const noImage = '/static/img/no-image.svg';

            return `
            <tr>
                <td class="ps-4" data-label="Imagen">
                    <div class="position-relative bg-white rounded border d-flex align-items-center justify-content-center" style="width: 60px; height: 60px;">
                         <img src="${localImage}" 
                             alt="${p.codigo}"
                             class="rounded"
                             style="width: 100%; height: 100%; object-fit: contain; cursor: pointer;"
                             onclick="window.open(this.src, '_blank')"
                             onerror="if(this.src.endsWith('.jpg')){this.src=this.src.replace('.jpg','.png')}else{this.onerror=null;this.src='${noImage}'}">
                    </div>
                </td>
                <td data-label="Producto">
                    <div class="fw-bold text-dark mb-1" style="font-size: 0.95rem;">${p.descripcion}</div>
                    <div class="d-flex align-items-center">
                        <span class="badge bg-light text-secondary border fw-normal me-2">${p.codigo}</span>
                    </div>
                </td>
                <td class="text-center" data-label="Stock">
                   ${this.getStockBadge(p.stock)}
                </td>
                <td class="text-end fw-bold text-dark" data-label="Precio">
                    ${p.precio > 0 ? '$' + p.precio.toLocaleString() : '<span class="text-muted small">Consultar</span>'}
                </td>
                <td data-label="Solicitar">
                     <div class="d-flex align-items-center justify-content-end gap-2">
                        <input type="number" id="qty-${p.codigo}" class="form-control form-control-sm text-center fw-bold" value="1" min="1" style="width: 60px;">
                        <button class="btn btn-primary btn-sm px-3 fw-bold shadow-sm" onclick="ModuloPortal.agregarAlCarrito('${p.codigo}')">
                            <i class="fas fa-plus"></i> <span class="d-none d-md-inline ms-1">Agregar</span>
                        </button>
                    </div>
                </td>
            </tr>
            `;
        }).join('');

        const tableFooter = `
                    </tbody>
                </table>
            </div>
        `;

        // Controles de Paginación
        const paginationControls = `
            <div class="d-flex justify-content-between align-items-center py-3">
                <small class="text-muted">Mostrando ${start + 1}-${Math.min(end, listaTotal.length)} de ${listaTotal.length} productos</small>
                <div class="btn-group">
                    <button class="btn btn-outline-secondary btn-sm" 
                        ${this.currentPage === 1 ? 'disabled' : ''} 
                        onclick="ModuloPortal.cambiarPagina(-1)">
                        <i class="fas fa-chevron-left"></i> Anterior
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" disabled>
                        Página ${this.currentPage} de ${totalPages}
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" 
                        ${this.currentPage >= totalPages ? 'disabled' : ''} 
                        onclick="ModuloPortal.cambiarPagina(1)">
                        Siguiente <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
            </div>
        `;

        grid.innerHTML = tableHeader + tableBody + tableFooter + paginationControls;
    },

    cambiarPagina: function (delta) {
        this.currentPage += delta;
        // renderizarProductos sin args usa currentFilteredProducts y respeta currentPage
        this.renderizarProductos();
        // Scroll top suave
        document.getElementById('product-grid').scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    searchTimer: null,
    filtrarProductos: function () {
        clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => {
            const query = document.getElementById('portal-search').value.toLowerCase();
            const filtrados = this.productos.filter(p =>
                p.descripcion.toLowerCase().includes(query) ||
                p.codigo.toLowerCase().includes(query)
            );
            // Renderizar la lista filtrada (esto resetea page a 1)
            this.renderizarProductos(filtrados);
        }, 300); // Debounce 300ms
    },

    // =================================================================
    // CARRITO
    // =================================================================

    cargarCarritoLocal: function () {
        const stored = localStorage.getItem('friparts_cart');
        if (stored) this.carrito = JSON.parse(stored);
    },

    guardarCarritoLocal: function () {
        localStorage.setItem('friparts_cart', JSON.stringify(this.carrito));
        this.actualizarBadge();
    },

    agregarAlCarrito: function (codigo) {
        const prod = this.productos.find(p => p.codigo === codigo);
        if (!prod) return;

        // Obtener cantidad del input
        const inputQty = document.getElementById(`qty-${codigo}`);
        let cantidadAgregar = 1;
        if (inputQty) {
            cantidadAgregar = parseInt(inputQty.value) || 1;
            if (cantidadAgregar < 1) cantidadAgregar = 1;
        }

        const existente = this.carrito.find(item => item.codigo === codigo);
        if (existente) {
            existente.cantidad += cantidadAgregar;
        } else {
            this.carrito.push({
                codigo: prod.codigo,
                descripcion: prod.descripcion,
                cantidad: cantidadAgregar,
                precio: prod.precio
            });
        }

        this.guardarCarritoLocal();
        // Feedback visual
        if (window.AuthModule && typeof window.AuthModule.mostrarNotificacion === 'function') {
            window.AuthModule.mostrarNotificacion(`Agregado: ${cantidadAgregar}x ${prod.descripcion}`, 'success');
        }

        // Reset input to 1
        if (inputQty) inputQty.value = 1;

        const badge = document.getElementById('cart-badge');
        if (badge) {
            badge.classList.add('animate-bounce');
            setTimeout(() => badge.classList.remove('animate-bounce'), 500);
        }
    },

    getStockBadge: function (stock) {
        // Estilo sutil (Outline o Soft Backgrounds) para no "chillar"
        const styleBase = "font-size: 0.7rem; padding: 4px 10px; border-radius: 6px; font-weight: 600; letter-spacing: 0.3px;";

        if (stock > 50) return `<span class="badge text-success border border-success bg-white" style="${styleBase}"><i class="fas fa-check me-1"></i>Disponible</span>`;
        if (stock > 0) return `<span class="badge text-warning border border-warning bg-white" style="${styleBase}"><i class="fas fa-exclamation me-1"></i>Pocas Unidades</span>`;
        return `<span class="badge text-secondary border border-secondary bg-white" style="${styleBase}"><i class="fas fa-clock me-1"></i>Bajo Pedido</span>`;
    },

    actualizarBadge: function () {
        // CORRECCIÓN: Mostrar Referencias únicas (Items) en lugar de suma total de unidades
        const count = this.carrito.length;

        // 1. Badge Tradicional (Navbar)
        const badge = document.getElementById('cart-badge');
        if (badge) {
            badge.innerText = count;
            badge.style.display = count > 0 ? 'block' : 'none';
        }

        // 2. Badge Boton Flotante
        const floatBadge = document.getElementById('floating-cart-count');
        if (floatBadge) {
            floatBadge.innerText = count;
            floatBadge.style.display = count > 0 ? 'block' : 'none';
        }
    },

    verCarrito: function () {
        const totalItems = this.carrito.reduce((a, b) => a + b.cantidad, 0);
        const totalReferencias = this.carrito.length;
        let totalPrecio = 0;

        const cartHtml = this.carrito.map((item, idx) => {
            const prod = this.productos.find(p => p.codigo === item.codigo);
            // Fallback robusto de imagen (Igual que en renderizarProductos)
            const localImage = `/static/img/productos/${item.codigo.trim()}.jpg`;
            const fallbackImage = prod && prod.imagen && prod.imagen.length > 5 ? prod.imagen : '';
            const noImage = '/static/img/no-image.svg';

            const subtotal = item.cantidad * item.precio;
            totalPrecio += subtotal;

            const imgHtml = `
                <img src="${localImage}" 
                     class="rounded-3 border" 
                     style="width: 60px; height: 60px; object-fit: contain; background: #fff;" 
                     onerror="
                        if (this.src.includes('.jpg')) { 
                            this.src = this.src.replace('.jpg', '.png'); 
                        } else if (this.src.includes('.png') && '${fallbackImage}' !== '') { 
                            this.src = '${fallbackImage}'; 
                        } else { 
                            this.src = '${noImage}';
                        }
                     ">
            `;

            return `
            <div class="cart-item-row d-flex align-items-center border-bottom py-3">
                <div class="me-3 flex-shrink-0">
                    ${imgHtml}
                </div>
                
                <div class="flex-grow-1 min-width-0">
                    <h6 class="mb-1 fw-bold text-dark" style="font-size: 0.9rem; line-height: 1.2;">${item.descripcion}</h6>
                    <div class="d-flex align-items-center text-muted small mb-2">
                        <i class="fas fa-barcode me-1"></i> ${item.codigo}
                    </div>
                    <div class="text-primary fw-bold">
                        $${item.precio.toLocaleString()} <span class="text-muted fw-normal small">x un.</span>
                    </div>
                </div>

                <div class="d-flex flex-column align-items-end ms-3">
                    <div class="quantity-control d-flex align-items-center bg-white border rounded-pill px-1 mb-2 shadow-sm" style="height: 38px;">
                        <button class="btn btn-sm text-secondary border-0 p-0 px-3 h-100" onclick="ModuloPortal.cambiarCantidad(${idx}, -1)">
                            <i class="fas fa-minus small"></i>
                        </button>
                        <input type="text" class="form-control border-0 text-center p-0 fw-bold text-dark bg-transparent" value="${item.cantidad}" readonly style="width: 60px; height: 100%; font-size: 1rem;">
                        <button class="btn btn-sm text-primary border-0 p-0 px-3 h-100" onclick="ModuloPortal.cambiarCantidad(${idx}, 1)">
                            <i class="fas fa-plus small"></i>
                        </button>
                    </div>
                    <div class="fw-bold text-dark mb-1">$${subtotal.toLocaleString()}</div>
                    <button type="button" class="btn btn-link text-danger small text-decoration-none opacity-75 hover-opacity-100 p-0 border-0 bg-transparent" onclick="ModuloPortal.eliminarItem(${idx})">
                        Eliminar
                    </button>
                </div>
            </div>`;
        }).join('');

        const emptyHtml = `
            <div class="text-center py-5">
                <div class="mb-4 d-inline-block p-4 bg-primary bg-opacity-10 rounded-circle text-primary">
                    <i class="fas fa-shopping-cart fa-3x"></i>
                </div>
                <h4 class="fw-bold text-dark mb-2">Tu carrito está vacío</h4>
                <p class="text-muted mb-4">Explora nuestro catálogo y agrega los productos que necesitas.</p>
                <button class="btn btn-primary rounded-pill px-4 py-2 fw-medium" onclick="document.getElementById('portal-cart-modal').style.display='none'; ModuloPortal.switchTab('catalogo'); window.location.hash='portal-cliente';">
                    Ir al Catálogo
                </button>
            </div>
        `;

        const modalBody = this.carrito.length > 0 ? `
            <div class="cart-items-container px-3" style="max-height: 55vh; overflow-y: auto;">
                ${cartHtml}
            </div>
            <div class="cart-summary bg-light p-4 border-top mt-auto">
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-muted">Total Referencias</span>
                    <span class="fw-bold text-dark">${totalReferencias}</span>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <span class="h5 mb-0 text-dark fw-bold">Total Estimado</span>
                    <span class="h4 mb-0 text-primary fw-bold">$${totalPrecio.toLocaleString()}</span>
                </div>
                <div class="d-grid">
                    <button class="btn btn-primary py-3 rounded-3 shadow-sm fw-bold hover-scale" onclick="ModuloPortal.enviarPedido()">
                        Confirmar y Enviar Pedido <i class="fas fa-arrow-right ms-2"></i>
                    </button>
                </div>
            </div>
        ` : emptyHtml;

        let modal = document.getElementById('portal-cart-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'portal-cart-modal';
            modal.className = 'modal-custom';
            // Ensure centered flex layout for modal overlay
            modal.style.display = 'none'; // Hidden by default
            modal.style.alignItems = 'center'; // Center vertically
            modal.style.justifyContent = 'center'; // Center horizontally

            modal.innerHTML = `
                <div class="modal-content-custom bg-white shadow-lg animate-fade-in-up" 
                     style="width: 100%; max-width: 600px; border-radius: 20px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden;">
                    <div class="d-flex justify-content-between align-items-center p-3 px-4 border-bottom bg-white">
                        <div class="d-flex align-items-center gap-2">
                            <div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center" style="width: 32px; height: 32px;">
                                <i class="fas fa-shopping-bag small"></i>
                            </div>
                            <h5 class="mb-0 fw-bold">Mi Pedido</h5>
                        </div>
                        <button class="btn-close shadow-none" onclick="document.getElementById('portal-cart-modal').style.display='none'"></button>
                    </div>
                    <div id="cart-content" class="d-flex flex-column flex-grow-1" style="overflow: hidden;"></div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        document.getElementById('cart-content').innerHTML = modalBody;
        modal.style.display = 'flex';
    },

    cambiarCantidad: function (idx, delta) {
        let item = this.carrito[idx];
        let nuevaCant = item.cantidad + delta;
        if (nuevaCant <= 0) {
            if (confirm("¿Eliminar este producto del pedido?")) {
                this.eliminarItem(idx);
            }
        } else {
            item.cantidad = nuevaCant;
            this.guardarCarritoLocal();
            this.verCarrito();
        }
    },

    actualizarCantidad: function (idx, val) {
        val = parseInt(val);
        if (val <= 0) this.eliminarItem(idx);
        else {
            this.carrito[idx].cantidad = val;
            this.guardarCarritoLocal();
        }
    },

    eliminarItem: function (idx) {
        this.carrito.splice(idx, 1);
        this.guardarCarritoLocal();
        this.verCarrito(); // Re-render
    },

    enviarPedido: async function () {
        if (this.carrito.length === 0) return;

        // 1. Validar Usuario
        const user = window.AuthModule?.currentUser;
        if (!user) {
            alert("Error: No se ha identificado el usuario.");
            return;
        }

        // 2. Confirmar Intención
        const confirmar = await this.mostrarConfirmacion(
            '¿Confirmar Pedido?',
            `Estás a punto de enviar un pedido con ${this.carrito.length} referencias.`
        );
        if (!confirmar) return;

        // 3. Preparar Datos
        const fecha = new Date().toISOString().split('T')[0];
        const totalPrecio = this.carrito.reduce((a, b) => a + (b.cantidad * b.precio), 0);

        const pedidoData = {
            fecha: fecha,
            vendedor: 'Portal Web', // Marca especial
            cliente: user.nombre || 'Cliente Portal',
            nit: user.nit || '',
            forma_pago: 'Crédito', // Default para clientes portal
            descuento_global: 0,
            productos: this.carrito.map(item => ({
                codigo: item.codigo,
                descripcion: item.descripcion,
                cantidad: item.cantidad,
                precio_unitario: item.precio
            }))
        };

        // 4. Feedback Visual (Loading)
        this.toggleLoader(true);

        try {
            // 5. Enviar al Backend
            const response = await fetch('/api/pedidos/registrar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pedidoData)
            });

            const result = await response.json();

            if (result.success) {
                // EXITO
                if (window.AuthModule) window.AuthModule.mostrarNotificacion("¡Pedido enviado con éxito!", "success");

                // Limpiar
                this.carrito = [];
                this.guardarCarritoLocal();
                document.getElementById('portal-cart-modal').style.display = 'none';
                this.actualizarBadge();

                // 6. Ofrecer PDF (Delay para que cierre el modal anterior visualmente)
                setTimeout(async () => {
                    this.toggleLoader(false);

                    const descargar = await this.mostrarConfirmacion(
                        '¡Pedido Registrado!',
                        `Tu pedido <strong>${result.id_pedido}</strong> ha sido recibido.<br>¿Deseas descargar el comprobante PDF?`
                    );

                    if (descargar) {
                        // Preparar datos para PDF
                        const dataPDF = {
                            id_pedido: result.id_pedido,
                            fecha: fecha,
                            vendedor: 'Portal Web',
                            cliente: {
                                nombre: user.nombre,
                                nit: user.nit,
                                direccion: user.direccion || '',
                                telefonos: user.telefono || '',
                                ciudad: user.ciudad || ''
                            },
                            productos: pedidoData.productos,
                            total: `$ ${totalPrecio.toLocaleString()}`,
                            forma_pago: 'Crédito'
                        };
                        this.generarPDF(dataPDF);
                    }

                    // Ir a "Mis Pedidos"
                    this.switchTab('mis-pedidos');
                    this.cargarMisPedidos();

                }, 500);

            } else {
                this.toggleLoader(false);
                alert("Error al registrar pedido: " + (result.error || "Desconocido"));
            }

        } catch (e) {
            this.toggleLoader(false);
            console.error("Error enviando pedido:", e);
            alert("Error de conexión al enviar el pedido.");
        }
    },

    generarPDF: function (datos) {
        try {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF();

            // --- 1. ENCABEZADO Y LOGO ---
            const imgPath = '/static/img/logo_friparts_nuevo.jpg';

            const dibujar = (imgData) => {
                if (imgData) {
                    try { doc.addImage(imgData, 'JPEG', 14, 10, 60, 28); }
                    catch (e) { doc.addImage(imgData, 'PNG', 14, 10, 60, 28); }
                }

                doc.setFontSize(22);
                doc.setTextColor(30, 58, 138);
                doc.setFont(undefined, 'bold');
                doc.text("FRIPARTS S.A.S", 14, 45);

                doc.setFontSize(10);
                doc.setTextColor(100);
                doc.setFont(undefined, 'normal');

                doc.text(`Comprobante No: ${datos.id_pedido}`, 196, 20, { align: 'right' });
                doc.text(`Fecha: ${datos.fecha}`, 196, 26, { align: 'right' });

                // --- 2. INFO CLIENTE ---
                doc.setDrawColor(220);
                doc.setLineWidth(0.5);
                doc.line(14, 55, 196, 55);

                doc.setFontSize(11);
                doc.setTextColor(30, 58, 138);
                doc.setFont(undefined, 'bold');
                doc.text("CLIENTE:", 14, 65);

                doc.setFontSize(10);
                doc.setTextColor(40);
                doc.setFont(undefined, 'normal');
                const cliente = datos.cliente;
                doc.text(`Nombre: ${cliente.nombre}`, 14, 72);
                doc.text(`NIT: ${cliente.nit || 'N/A'}`, 14, 79);
                doc.text(`Ciudad: ${cliente.ciudad || 'N/A'}`, 14, 86);

                // Info Derecha
                const rightX = 135;
                doc.setFontSize(11);
                doc.setTextColor(30, 58, 138);
                doc.setFont(undefined, 'bold');
                doc.text("DETALLES:", rightX, 65);

                doc.setFontSize(10);
                doc.setTextColor(40);
                doc.setFont(undefined, 'normal');
                doc.text(`Origen: ${datos.vendedor}`, rightX, 72);
                doc.text(`Pago: ${datos.forma_pago}`, rightX, 79);
                doc.text(`Estado: RECIBIDO`, rightX, 86);

                // --- 3. TABLA ---
                const tablaData = datos.productos.map(item => [
                    item.codigo,
                    item.descripcion,
                    item.cantidad,
                    `$ ${item.precio_unitario.toLocaleString()}`,
                    `$ ${(item.cantidad * item.precio_unitario).toLocaleString()}`
                ]);

                doc.autoTable({
                    startY: 100,
                    head: [['Código', 'Descripción', 'Cant.', 'Unitario', 'Subtotal']],
                    body: tablaData,
                    theme: 'grid',
                    headStyles: { fillColor: [30, 58, 138], textColor: 255, halign: 'center' },
                    styles: { fontSize: 9, cellPadding: 3 },
                    columnStyles: {
                        0: { cellWidth: 30 },
                        2: { halign: 'center' },
                        3: { halign: 'right' },
                        4: { halign: 'right' }
                    }
                });

                // --- 4. TOTAL ---
                const finalY = doc.lastAutoTable.finalY + 15;
                doc.setDrawColor(30, 58, 138);
                doc.setLineWidth(1);
                doc.line(140, finalY - 5, 196, finalY - 5);

                doc.setFontSize(14);
                doc.setTextColor(30, 58, 138);
                doc.setFont(undefined, 'bold');
                doc.text(`TOTAL A PAGAR: ${datos.total}`, 196, finalY, { align: 'right' });

                // --- 5. FOOTER ---
                const footerY = 270;
                doc.setFontSize(8);
                doc.setTextColor(150);
                doc.text("Este documento es un comprobante de pedido web.", 105, footerY, { align: 'center' });
                doc.text("FRIPARTS S.A.S - www.friparts.com", 105, footerY + 5, { align: 'center' });

                doc.save(`Pedido_${datos.id_pedido}.pdf`);
                if (window.AuthModule) window.AuthModule.mostrarNotificacion("PDF descargado", "success");
            };

            const img = new Image();
            img.onload = function () { dibujar(this); };
            img.onerror = function () { dibujar(null); };
            img.src = imgPath;

        } catch (e) {
            console.error("Error PDF:", e);
            alert("No se pudo generar el PDF. Verifica que no haya bloqueadores de popups.");
        }
    },

    mostrarConfirmacion: function (titulo, mensaje) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            // Reutilizamos estilos del modal de pedidos (inline por seguridad)
            modal.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.5); z-index: 20000;
                display: flex; align-items: center; justify-content: center;
                backdrop-filter: blur(2px);
            `;
            modal.innerHTML = `
                <div class="modal-content animate-bounce bg-white shadow-lg" style="max-width: 400px; border-radius: 12px; overflow: hidden; margin: 20px;">
                    <div class="modal-header border-bottom p-3 bg-white">
                        <h5 class="mb-0 fw-bold text-dark"><i class="fas fa-question-circle text-primary me-2"></i> ${titulo}</h5>
                    </div>
                    <div class="modal-body p-4 text-secondary" style="font-size: 1rem;">
                        ${mensaje}
                    </div>
                    <div class="modal-footer border-top p-3 bg-light d-flex justify-content-end gap-2">
                        <button class="btn btn-light border" id="confirm-cancel">Cancelar</button>
                        <button class="btn btn-primary px-4 fw-bold" id="confirm-ok">Confirmar</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            const close = (val) => {
                modal.remove();
                resolve(val);
            };

            document.getElementById('confirm-ok').onclick = () => close(true);
            document.getElementById('confirm-cancel').onclick = () => close(false);
        });
    },


    // =================================================================
    // PEDIDOS / TRACKING
    // =================================================================

    cargarMisPedidos: async function (silent = false) {
        const container = document.getElementById('client-orders-container');
        if (!container) return;

        // Obtener usuario actual
        const user = window.AuthModule?.currentUser;
        if (!user || user.rol !== 'Cliente') return;

        if (!silent) {
            container.innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin"></i> Cargando historial...</div>';
        }

        try {
            // Fetch Real
            const res = await fetch(`/api/pedidos/cliente?nit=${user.nit}`);
            const data = await res.json();

            if (!data.success) throw new Error(data.message);

            this.pedidos = data.pedidos || [];

            if (this.pedidos.length === 0) {
                container.innerHTML = '<div class="text-center py-5 text-muted">No tienes pedidos registrados.</div>';
                return;
            }

            container.innerHTML = this.pedidos.map(p => {
                let badgeClass = 'bg-secondary';
                if (p.estado === 'En Proceso') badgeClass = 'bg-primary';
                if (p.estado === 'Entregado') badgeClass = 'bg-success';

                return `
                <div class="card mb-3 border-0 shadow-sm">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h5 class="card-title fw-bold text-primary mb-0">${p.id}</h5>
                            <span class="badge ${badgeClass} rounded-pill">${p.estado}</span>
                        </div>
                        <p class="text-muted small mb-3">📅 Fecha: ${p.fecha} &bull; 📦 Items: ${p.items}</p>
                        
                        <!-- Progress Bar -->
                        <div class="d-flex justify-content-between small fw-bold mb-1">
                            <span>Progreso</span>
                            <span>${p.progreso}%</span>
                        </div>
                        <div class="progress" style="height: 8px; border-radius: 4px;">
                            <div class="progress-bar ${badgeClass}" role="progressbar" style="width: ${p.progreso}%"></div>
                        </div>
                    </div>
                </div>
                `;
            }).join('');

        } catch (e) {
            console.error(e);
            container.innerHTML = '<div class="text-danger">Error cargando pedidos.</div>';
        }
    },

    // ===================================
    // AUTO-REFRESH (POLLING)
    // ===================================
    startPolling: function () {
        if (this.pollingInterval) return; // Ya está corriendo
        console.log('🔄 Iniciando auto-refresh de pedidos...');

        this.pollingInterval = setInterval(() => {
            // Solo si el tab es visible
            const contentPedidos = document.getElementById('portal-tab-mis-pedidos');
            if (contentPedidos && contentPedidos.style.display !== 'none') {
                console.log('🔄 Auto-refreshing pedidos...');
                this.cargarMisPedidos(true); // true = silent mode (sin spinner global si lo hubiera)
            } else {
                this.stopPolling();
            }
        }, this.POLLING_DELAY);
    },

    stopPolling: function () {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            console.log('⏹️ Auto-refresh detenido.');
        }
    },

    // =================================================================
    // EXPORTAR CATÁLOGO
    // =================================================================
    exportarCatalogo: function () {
        if (this.productos.length === 0) {
            alert('No hay productos para exportar');
            return;
        }

        // Crear CSV
        let csv = 'Código,Descripción,Stock Disponible,Precio\n';
        this.productos.forEach(p => {
            const stock = p.stock_terminado || 0;
            const precio = p.precio || 0;
            csv += `"${p.codigo}","${p.descripcion}",${stock},${precio}\n`;
        });

        // Descargar
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `catalogo_friparts_${new Date().toISOString().split('T')[0]}.csv`;
        link.click();

        if (window.AuthModule) {
            window.AuthModule.mostrarNotificacion('Catálogo exportado', 'success');
        }
    },

    // =================================================================
    // MÉTRICAS DEL CLIENTE
    // =================================================================
    mostrarMetricas: function () {
        const totalPedidos = this.pedidos.length;
        const pedidosPendientes = this.pedidos.filter(p => p.estado === 'PENDIENTE').length;
        const pedidosCompletados = this.pedidos.filter(p => p.estado === 'Entregado').length;

        const html = `
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center">
                            <i class="fas fa-shopping-cart fa-2x text-primary mb-2"></i>
                            <h3 class="fw-bold">${totalPedidos}</h3>
                            <p class="text-muted small mb-0">Total Pedidos</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center">
                            <i class="fas fa-clock fa-2x text-warning mb-2"></i>
                            <h3 class="fw-bold">${pedidosPendientes}</h3>
                            <p class="text-muted small mb-0">Pendientes</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center">
                            <i class="fas fa-check-circle fa-2x text-success mb-2"></i>
                            <h3 class="fw-bold">${pedidosCompletados}</h3>
                            <p class="text-muted small mb-0">Completados</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center">
                            <i class="fas fa-box fa-2x text-info mb-2"></i>
                            <h3 class="fw-bold">${this.productos.length}</h3>
                            <p class="text-muted small mb-0">Productos Disponibles</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Insertar antes del contenido de pedidos
        const container = document.getElementById('portal-tab-mis-pedidos');
        if (container) {
            const existingMetrics = container.querySelector('.row.mb-4');
            if (existingMetrics) {
                existingMetrics.outerHTML = html;
            } else {
                container.insertAdjacentHTML('afterbegin', html);
            }
        }
    },

    /**
     * Desactivar procesos del módulo al salir
     */
    desactivar: function () {
        console.log('🔌 [Portal] Deteniendo polling y procesos...');
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
};

window.ModuloPortal = ModuloPortal;
