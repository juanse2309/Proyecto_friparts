
// portal_client.js - Lógica del Portal B2B para Clientes

const ModuloPortal = {
    productos: [],
    carrito: [],
    pedidos: [],

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
    switchTab: function (tabName) {
        // Update nav
        document.querySelectorAll('#portal-tabs .nav-link').forEach(btn => btn.classList.remove('active'));
        const btn = document.querySelector(`#portal-tabs button[onclick*="${tabName}"]`);
        if (btn) btn.classList.add('active');

        // Update content
        document.getElementById('portal-tab-catalogo').style.display = 'none';
        document.getElementById('portal-tab-mis-pedidos').style.display = 'none';

        document.getElementById(`portal-tab-${tabName}`).style.display = 'block';
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

                // Mapeo robusto
                this.productos = items.map(p => ({
                    id: p.id_codigo || p.ID_CODIGO || p.ID || 0,
                    codigo: p.codigo || p.codigo_sistema || p.CODIGO || '',
                    descripcion: p.descripcion || p.DESCRIPCION || '',
                    stock: p.existencias_totales || p.EXISTENCIAS || p.stock_total || 0,
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
    itemsPerPage: 50,
    currentFilteredProducts: [], // Para mantener estado de busqueda + paginacion

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

        // VISTA LISTA (Tabla)
        grid.className = 'w-100';
        grid.style.display = 'block';
        grid.style.gridTemplateColumns = 'none';
        grid.style.gap = '0';

        const tableHeader = `
            <div class="table-responsive">
                <table class="table table-hover align-middle shadow-sm rounded-3 overflow-hidden" style="background: white;">
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
            const fallbackImage = p.imagen && p.imagen.length > 5 ? p.imagen : '';
            const noImage = '/static/img/no-image.png';

            return `
            <tr>
                <td class="ps-4">
                    <div class="position-relative bg-white rounded border d-flex align-items-center justify-content-center" style="width: 60px; height: 60px;">
                        <img src="${localImage}" 
                             alt="${p.codigo}"
                             class="rounded"
                             style="width: 100%; height: 100%; object-fit: contain; cursor: pointer;"
                             onclick="window.open(this.src, '_blank')"
                             onerror="
                                if (this.src.endsWith('.jpg')) { 
                                    this.src = this.src.replace('.jpg', '.png'); 
                                } else if (this.src.endsWith('.png') && '${fallbackImage}' !== '') { 
                                    this.src = '${fallbackImage}'; 
                                } else { 
                                    this.src = '${noImage}';
                                }
                             ">
                    </div>
                </td>
                <td>
                    <div class="fw-bold text-dark mb-1" style="font-size: 0.95rem;">${p.descripcion}</div>
                    <div class="d-flex align-items-center">
                        <span class="badge bg-light text-secondary border fw-normal me-2">${p.codigo}</span>
                    </div>
                </td>
                <td class="text-center">
                   ${this.getStockBadge(p.stock)}
                </td>
                <td class="text-end fw-bold text-dark">
                    ${p.precio > 0 ? '$' + p.precio.toLocaleString() : '<span class="text-muted small">Consultar</span>'}
                </td>
                <td>
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
            const noImage = '/static/img/no-image.png';

            const subtotal = item.cantidad * item.precio;
            totalPrecio += subtotal;

            const imgHtml = `
                <img src="${localImage}" 
                     class="rounded-3 border" 
                     style="width: 60px; height: 60px; object-fit: contain; background: #fff;" 
                     onerror="
                        if (this.src.endsWith('.jpg')) { 
                            this.src = this.src.replace('.jpg', '.png'); 
                        } else if (this.src.endsWith('.png') && '${fallbackImage}' !== '') { 
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

    cargarMisPedidos: async function () {
        const container = document.getElementById('client-orders-container');
        if (!container) return;

        // Obtener usuario actual
        const user = window.AuthModule?.currentUser;
        if (!user || user.rol !== 'Cliente') return;

        container.innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin"></i> Cargando historial...</div>';

        try {
            // Simulamos datos o fetch real si existiera endpoint
            // const res = await fetch(`/api/pedidos/cliente?nit=${user.nit}`); 

            // Mock Data
            const pedidosMock = [
                { id: 'PED-1001', fecha: '2023-10-01', estado: 'En Proceso', items: 5, progreso: 60 },
                { id: 'PED-0988', fecha: '2023-09-20', estado: 'Entregado', items: 12, progreso: 100 },
            ];

            this.pedidos = pedidosMock;

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
    }
};

window.ModuloPortal = ModuloPortal;
