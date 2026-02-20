
// pedidos.js - Módulo de Gestión de Pedidos

const ModuloPedidos = {
    listaProductos: [], // Array de productos: [{codigo, descripcion, cantidad, precio_unitario, stock_disponible}]
    clientesData: [],  // Cache de clientes
    productosData: [], // Cache de productos
    clienteSeleccionado: null, // {nombre, nit}
    ultimoIdRegistrado: null, // ID generado por el servidor
    idPedidoEdicion: null,   // ID del pedido que se está editando


    init: function () {
        console.log("🛒 Inicializando Módulo Pedidos...");

        // 1. Inicializar autocomplete
        this.inicializarAutocompleteCliente();
        this.inicializarAutocompleteProducto();

        // 2. Botón añadir item
        const btnAgregar = document.getElementById('btn-agregar-item');
        if (btnAgregar) {
            btnAgregar.addEventListener('click', () => this.agregarItemAlCarrito());
        }

        // 3. Submit del formulario
        const form = document.getElementById('form-pedidos');
        if (form) {
            form.addEventListener('submit', (e) => this.registrarPedido(e));
        }

        // 4. Listener para descuento global
        const descuentoGlobal = document.getElementById('ped-descuento-global');
        if (descuentoGlobal) {
            descuentoGlobal.addEventListener('input', () => this.calcularTotalPedido());
        }

        // 5. Inicializar fecha
        const inputFecha = document.getElementById('ped-fecha');
        if (inputFecha) {
            inputFecha.valueAsDate = new Date();
        }

        // 6. Configurar gestión de Enter
        this.configurarManejoEnter();
    },

    cargarDatosIniciales: async function () {
        console.log("📦 Cargando datos para Pedidos...");

        // Cargar Clientes
        try {
            if (window.AppState && window.AppState.sharedData.clientes.length > 0) {
                this.clientesData = window.AppState.sharedData.clientes;
            } else {
                const response = await fetch('/api/obtener_clientes');
                this.clientesData = await response.json();
            }
            console.log("✅ Clientes cargados:", this.clientesData.length);
        } catch (e) {
            console.error("Error cargando clientes:", e);
        }

        // Cargar Productos
        try {
            if (window.AppState && window.AppState.sharedData.productos.length > 0) {
                this.productosData = window.AppState.sharedData.productos;
            } else {
                const response = await fetch('/api/productos/listar');
                const data = await response.json();
                this.productosData = data.items || data;
            }
            console.log("✅ Productos cargados:", this.productosData.length);
        } catch (e) {
            console.error("Error cargando productos:", e);
        }

        // Pre-fill vendedor
        this.actualizarVendedor();
    },

    inicializarAutocompleteCliente: function () {
        const input = document.getElementById('ped-cliente');
        const suggestionsDiv = document.getElementById('ped-cliente-suggestions');

        if (!input || !suggestionsDiv) return;

        let debounceTimer;

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();

            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            debounceTimer = setTimeout(() => {
                this.buscarClientes(query, suggestionsDiv);
            }, 300);
        });

        // Cerrar sugerencias al hacer clic fuera
        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    // Helper para normalizar texto (quitar tildes y minusculas)
    normalizeString: function (str) {
        return String(str || '').normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    },

    buscarClientes: function (query, suggestionsDiv) {
        const queryNorm = this.normalizeString(query);

        const resultados = this.clientesData.filter(cliente => {
            const nombreNorm = this.normalizeString(cliente.nombre);
            return nombreNorm.includes(queryNorm) ||
                (cliente.nit && cliente.nit.includes(query));
        });

        if (resultados.length === 0) {
            suggestionsDiv.innerHTML = '<div class="suggestion-item">No se encontraron clientes</div>';
            suggestionsDiv.classList.add('active');
            return;
        }

        suggestionsDiv.innerHTML = resultados.map(cliente => `
            <div class="suggestion-item" 
                data-nombre="${cliente.nombre}" 
                data-nit="${cliente.nit || ''}"
                data-direccion="${cliente.direccion || ''}"
                data-telefonos="${cliente.telefonos || ''}"
                data-ciudad="${cliente.ciudad || ''}">
                <strong>${cliente.nombre}</strong>
                ${cliente.nit ? `<br><small>NIT: ${cliente.nit}</small>` : ''}
                <br><small style="color: #6b7280;"><i class="fas fa-map-marker-alt"></i> ${cliente.direccion || 'Sin dirección'} - ${cliente.ciudad || 'Sin ciudad'}</small>
            </div>
        `).join('');

        // Event listeners para selección
        suggestionsDiv.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                this.seleccionarCliente({
                    nombre: item.dataset.nombre,
                    nit: item.dataset.nit,
                    direccion: item.dataset.direccion,
                    telefonos: item.dataset.telefonos,
                    ciudad: item.dataset.ciudad
                });
                suggestionsDiv.classList.remove('active');
            });
        });

        suggestionsDiv.classList.add('active');
    },

    seleccionarCliente: function (cliente) {
        this.clienteSeleccionado = cliente;
        document.getElementById('ped-cliente').value = cliente.nombre;
        document.getElementById('ped-nit').value = cliente.nit || '';
        document.getElementById('ped-direccion').value = cliente.direccion || '';
        document.getElementById('ped-ciudad').value = cliente.ciudad || '';
        console.log("🔄 Cliente seleccionado con sede:", cliente);
    },

    inicializarAutocompleteProducto: function () {
        const input = document.getElementById('ped-producto');
        const suggestionsDiv = document.getElementById('ped-producto-suggestions');

        if (!input || !suggestionsDiv) return;

        let debounceTimer;

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();

            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            debounceTimer = setTimeout(() => {
                this.buscarProductos(query, suggestionsDiv);
            }, 300);
        });

        // Cerrar sugerencias al hacer clic fuera
        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    buscarProductos: function (query, suggestionsDiv) {
        const queryNorm = this.normalizeString(query);
        const resultados = this.productosData.filter(prod => {
            const codigoNorm = this.normalizeString(prod.codigo_sistema);
            const descNorm = this.normalizeString(prod.descripcion);
            return codigoNorm.includes(queryNorm) || descNorm.includes(queryNorm);
        });

        if (resultados.length === 0) {
            suggestionsDiv.innerHTML = '<div class="suggestion-item">No se encontraron productos</div>';
            suggestionsDiv.classList.add('active');
            return;
        }

        renderProductSuggestions(suggestionsDiv, resultados.slice(0, 10), (item) => {
            document.getElementById('ped-producto').value = `${item.codigo_sistema} - ${item.descripcion}`;
            document.getElementById('ped-precio').value = item.precio || 0;
            this.productoSeleccionado = item; // Guardar el objeto completo
            console.log("💰 Producto seleccionado:", item.codigo_sistema, "Stock Disponible:", item.stock_disponible);
        });
    },

    actualizarVendedor: function () {
        const inputVendedor = document.getElementById('ped-vendedor');
        if (!inputVendedor) {
            console.warn('⚠️  Campo vendedor no encontrado en el DOM');
            return;
        }

        let nombreVendedor = null;

        if (window.AppState && window.AppState.user && window.AppState.user.name) {
            nombreVendedor = window.AppState.user.name;
        } else if (window.AuthModule && window.AuthModule.currentUser && window.AuthModule.currentUser.nombre) {
            nombreVendedor = window.AuthModule.currentUser.nombre;
        } else {
            try {
                const storedUser = sessionStorage.getItem('friparts_user');
                if (storedUser) {
                    const userData = JSON.parse(storedUser);
                    nombreVendedor = userData.nombre;
                }
            } catch (e) {
                console.error('Error parseando sessionStorage:', e);
            }
        }

        if (nombreVendedor) {
            inputVendedor.value = nombreVendedor;
            inputVendedor.readOnly = true;
            console.log(`✅ Vendedor asignado: ${nombreVendedor}`);
        } else {
            console.log('ℹ️  Vendedor pendiente: esperando login de usuario');

            // Retry on event
            window.addEventListener('user-ready', (e) => {
                console.log("👤 Evento user-ready recibido en Pedidos");
                this.actualizarVendedor();
            });

            // Polling fallback (max 5 seconds)
            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                if (window.AppState?.user?.name) {
                    this.actualizarVendedor();
                    clearInterval(interval);
                }
                if (attempts > 10) clearInterval(interval);
            }, 500);
        }
    },

    configurarManejoEnter: function () {
        const form = document.getElementById('form-pedidos');
        if (!form) return;

        // Lista de IDs de inputs que deben pasar al siguiente con Enter
        const inputsSecuencia = [
            'ped-fecha',
            'ped-cliente',
            'ped-pago',
            'ped-descuento-global',
            'ped-producto',
            'ped-cantidad',
            'ped-precio'
        ];

        form.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const targetId = e.target.id;

                // Prevenir envío accidental del formulario
                if (e.target.type !== 'textarea' && e.target.type !== 'submit' && e.target.id !== 'ped-load-id') {
                    e.preventDefault();
                }

                // Lógica especial para el buscador de pedidos
                if (targetId === 'ped-load-id') {
                    e.preventDefault();
                    this.cargarPedidoPorId();
                    return;
                }

                // Lógica específica para campos de producto
                if (targetId === 'ped-cantidad' || targetId === 'ped-precio') {
                    this.agregarItemAlCarrito();
                    document.getElementById('ped-producto').focus();
                    return;
                }

                // Lógica de salto de foco
                const currentIndex = inputsSecuencia.indexOf(targetId);
                if (currentIndex !== -1 && currentIndex < inputsSecuencia.length - 1) {
                    const nextInput = document.getElementById(inputsSecuencia[currentIndex + 1]);
                    if (nextInput) {
                        nextInput.focus();
                        if (nextInput.tagName === 'INPUT') nextInput.select();
                    }
                }
            }
        });
    },

    cargarPedidoPorId: async function () {
        const inputId = document.getElementById('ped-load-id');
        const id = inputId.value.trim().toUpperCase();

        if (!id) {
            mostrarNotificacion('Ingrese un ID de pedido', 'warning');
            return;
        }

        try {
            console.log(`🔍 Buscando pedido: ${id}...`);
            const response = await fetch(`/api/pedidos/detalle/${id}`);
            const result = await response.json();

            if (result.success) {
                this.poblarFormularioConPedido(result.pedido);
                inputId.value = '';
                mostrarNotificacion(`Pedido ${id} cargado correctamente`, 'success');
            } else {
                mostrarNotificacion(result.error || 'Pedido no encontrado', 'error');
            }
        } catch (error) {
            console.error('Error cargando pedido:', error);
            mostrarNotificacion('Error de conexión al cargar pedido', 'error');
        }
    },

    poblarFormularioConPedido: function (pedido) {
        console.log("📄 Poblando formulario con:", pedido);

        // 1. Limpiar estado actual
        this.listaProductos = [];
        this.idPedidoEdicion = pedido.id_pedido;

        // 2. Poblar cabecera
        document.getElementById('ped-fecha').value = pedido.fecha;
        document.getElementById('ped-vendedor').value = pedido.vendedor;
        document.getElementById('ped-cliente').value = pedido.cliente;
        document.getElementById('ped-nit').value = pedido.nit || '';
        document.getElementById('ped-direccion').value = pedido.direccion || '';
        document.getElementById('ped-ciudad').value = pedido.ciudad || '';
        document.getElementById('ped-pago').value = pedido.forma_pago || 'Contado';
        document.getElementById('ped-descuento-global').value = pedido.descuento_global || 0;
        document.getElementById('ped-observaciones').value = pedido.observaciones || '';

        // Establecer cliente seleccionado para las validaciones
        this.clienteSeleccionado = {
            nombre: pedido.cliente,
            nit: pedido.nit,
            direccion: pedido.direccion,
            ciudad: pedido.ciudad
        };

        // 3. Cargar productos (conviertiendo de la estructura del backend)
        this.listaProductos = pedido.productos.map(p => ({
            codigo: p.codigo,
            descripcion: p.descripcion,
            cantidad: p.cantidad,
            precio_unitario: p.precio_unitario,
            stock_disponible: 0
        }));

        // 4. Actualizar UI
        this.renderizarTablaItems();
        this.calcularTotalPedido();

        // 5. Mostrar indicador de edición
        const indicator = document.getElementById('edit-mode-indicator');
        const spanId = document.getElementById('active-edit-id');
        if (indicator && spanId) {
            indicator.style.display = 'block';
            spanId.textContent = pedido.id_pedido;
        }

        // 6. Cambiar texto del botón de registro
        const btnSubmit = document.querySelector('#form-pedidos button[type="submit"]');
        if (btnSubmit) {
            btnSubmit.innerHTML = '<i class="fas fa-save"></i> Actualizar Pedido';
            btnSubmit.style.background = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    cancelarEdicion: function () {
        this.idPedidoEdicion = null;
        limpiarFormulario('form-pedidos');
        this.listaProductos = [];
        this.clienteSeleccionado = null;
        this.renderizarTablaItems();
        this.calcularTotalPedido();

        document.getElementById('edit-mode-indicator').style.display = 'none';

        const btnSubmit = document.querySelector('#form-pedidos button[type="submit"]');
        if (btnSubmit) {
            btnSubmit.innerHTML = '<i class="fas fa-paper-plane"></i> Registrar Pedido';
            btnSubmit.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
        }

        document.getElementById('ped-total').textContent = '$ 0.00';
        this.actualizarVendedor();
        mostrarNotificacion('Edición cancelada', 'info');
    },


    agregarItemAlCarrito: function () {
        console.log('🛒 agregarItemAlCarrito llamado');

        const productoInput = document.getElementById('ped-producto').value;
        const cantidad = parseInt(document.getElementById('ped-cantidad').value);
        const precioUnitario = parseFloat(document.getElementById('ped-precio').value);

        console.log('📦 Datos del formulario:', { productoInput, cantidad, precioUnitario });

        // Validaciones básicas SOLO de campos vacíos
        if (!productoInput || !cantidad || !precioUnitario) {
            console.warn('⚠️ Campos incompletos');
            mostrarNotificacion('Complete todos los campos del producto', 'warning');
            return;
        }

        if (cantidad <= 0 || precioUnitario <= 0) {
            console.warn('⚠️ Valores inválidos');
            mostrarNotificacion('Cantidad y precio deben ser mayores a 0', 'warning');
            return;
        }

        // Extraer código y descripción del input
        let codigo = productoInput;
        let descripcion = '';

        if (productoInput.includes(' - ')) {
            const partes = productoInput.split(' - ');
            codigo = partes[0].trim();
            descripcion = partes.slice(1).join(' - ').trim();
        }

        console.log('✅ Producto a agregar:', { codigo, descripcion, cantidad, precioUnitario });

        // ========================================
        // AGREGAR DIRECTAMENTE SIN VALIDACIONES
        // ========================================

        this.listaProductos.push({
            codigo: codigo,
            descripcion: descripcion || 'Sin descripción',
            cantidad: cantidad,
            precio_unitario: precioUnitario,
            stock_disponible: (this.productoSeleccionado && this.productoSeleccionado.codigo_sistema === codigo)
                ? this.productoSeleccionado.stock_disponible
                : 0
        });

        console.log(`✅ Producto ${codigo} agregado a la lista. Total items: ${this.listaProductos.length}`);
        console.log('📋 Lista completa:', this.listaProductos);

        // Limpiar campos de producto
        document.getElementById('ped-producto').value = '';
        document.getElementById('ped-cantidad').value = '';
        document.getElementById('ped-precio').value = '';

        // Renderizar tabla y calcular total
        this.renderizarTablaItems();
        this.calcularTotalPedido();

        mostrarNotificacion(`✓ ${codigo} agregado (${cantidad} unidades)`, 'success');
    },


    eliminarItemDelCarrito: function (index) {
        this.listaProductos.splice(index, 1);
        this.renderizarTablaItems();
        this.calcularTotalPedido();
        this.actualizarEstadoBotonPDF();
    },

    renderizarTablaItems: function () {
        const tbody = document.getElementById('items-pedido-body');

        if (this.listaProductos.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-state">
                    <td colspan="6" style="text-align: center; color: #999; padding: 20px; border: 1px solid #dee2e6;">
                        No hay productos agregados
                    </td>
                </tr>
            `;
            this.actualizarEstadoBotonPDF();
            return;
        }

        tbody.innerHTML = this.listaProductos.map((item, index) => {
            const subtotal = item.cantidad * item.precio_unitario;
            return `
                <tr>
                    <td data-label="Código" style="padding: 10px; border: 1px solid #dee2e6;">${item.codigo}</td>
                    <td data-label="Descripción" style="padding: 10px; border: 1px solid #dee2e6;">${item.descripcion}</td>
                    <td data-label="Cantidad" style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">${item.cantidad}</td>
                    <td data-label="Precio Unit." style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">${formatearMoneda(item.precio_unitario)}</td>
                    <td data-label="Subtotal" style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">${formatearMoneda(subtotal)}</td>
                    <td data-label="Acciones" style="padding: 10px; border: 1px solid #dee2e6; text-align: center;">
                        <div class="d-flex justify-content-center gap-1">
                            <button type="button" class="btn btn-sm btn-outline-primary" style="padding: 4px 8px; font-size: 0.8rem;" title="Editar Cantidad" onclick="ModuloPedidos.editarItemDelCarrito(${index})">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-danger" style="padding: 4px 8px; font-size: 0.8rem;" title="Eliminar" onclick="ModuloPedidos.eliminarItemDelCarrito(${index})">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
        this.actualizarEstadoBotonPDF();
    },

    editarItemDelCarrito: function (index) {
        const item = this.listaProductos[index];
        if (!item) return;

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:20000;';
        modal.innerHTML = `
            <div style="background:#fff; border-radius:16px; max-width:400px; width:90%; overflow:hidden; box-shadow:0 20px 60px rgba(0,0,0,0.3); animation: slideInRight 0.3s ease;">
                <div style="background:linear-gradient(135deg,#6366f1,#4f46e5); padding:18px 24px; color:#fff;">
                    <h4 style="margin:0; font-size:1.1rem; font-weight:600;"><i class="fas fa-edit me-2"></i>Editar Cantidad</h4>
                </div>
                <div style="padding:24px;">
                    <p style="margin:0 0 6px; font-size:0.85rem; color:#64748b;">Producto:</p>
                    <p style="margin:0 0 16px; font-weight:600; color:#1e293b; font-size:0.95rem;">${item.codigo} — ${item.descripcion}</p>
                    <label style="font-size:0.8rem; color:#64748b; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Nueva Cantidad</label>
                    <input type="number" id="modal-edit-cantidad" value="${item.cantidad}" min="1" 
                           style="width:100%; padding:12px 16px; font-size:1.8rem; font-weight:700; text-align:center; border:2px solid #e2e8f0; border-radius:12px; margin-top:8px; outline:none; transition:border 0.2s;"
                           onfocus="this.style.borderColor='#6366f1'" onblur="this.style.borderColor='#e2e8f0'">
                </div>
                <div style="padding:16px 24px; background:#f8fafc; border-top:1px solid #e5e7eb; display:flex; gap:12px; justify-content:flex-end;">
                    <button id="modal-edit-cancelar" style="padding:10px 20px; border:1px solid #d1d5db; background:#fff; color:#374151; border-radius:10px; font-weight:500; cursor:pointer; font-size:0.9rem;">
                        Cancelar
                    </button>
                    <button id="modal-edit-confirmar" style="padding:10px 24px; background:linear-gradient(135deg,#6366f1,#4f46e5); color:#fff; border:none; border-radius:10px; font-weight:600; cursor:pointer; font-size:0.9rem;">
                        <i class="fas fa-check me-1"></i> Guardar
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const inputCant = document.getElementById('modal-edit-cantidad');
        inputCant.focus();
        inputCant.select();

        // Enter key support
        inputCant.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') document.getElementById('modal-edit-confirmar').click();
            if (e.key === 'Escape') document.getElementById('modal-edit-cancelar').click();
        });

        document.getElementById('modal-edit-confirmar').addEventListener('click', () => {
            const cantNum = parseInt(inputCant.value);
            if (isNaN(cantNum) || cantNum <= 0) {
                mostrarNotificacion('La cantidad debe ser un número mayor a 0', 'warning');
                return;
            }
            item.cantidad = cantNum;
            this.renderizarTablaItems();
            this.calcularTotalPedido();
            document.body.removeChild(modal);
            mostrarNotificacion('Cantidad actualizada', 'success');
        });

        document.getElementById('modal-edit-cancelar').addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) document.body.removeChild(modal);
        });
    },

    actualizarEstadoBotonPDF: function () {
        const btnPdf = document.getElementById('btn-pdf-pedido');
        if (btnPdf) {
            btnPdf.disabled = this.listaProductos.length === 0;
        }
    },

    calcularTotalPedido: function () {
        const descuentoGlobal = parseFloat(document.getElementById('ped-descuento-global')?.value || 0);

        const subtotalBruto = this.listaProductos.reduce((sum, item) => {
            return sum + (item.cantidad * item.precio_unitario);
        }, 0);

        const valorDescuento = subtotalBruto * (descuentoGlobal / 100);
        const subtotalNeto = subtotalBruto - valorDescuento;
        const iva = subtotalNeto * 0.19;
        const total = subtotalNeto + iva;

        // Actualizar UI
        const pedSubtotal = document.getElementById('ped-subtotal');
        const pedIva = document.getElementById('ped-iva');
        const pedTotal = document.getElementById('ped-total');

        if (pedSubtotal) pedSubtotal.textContent = formatearMoneda(subtotalBruto);
        if (pedIva) pedIva.textContent = formatearMoneda(iva);
        if (pedTotal) pedTotal.textContent = formatearMoneda(total);

        // Habilitar botón PDF si hay items
        const btnPdf = document.getElementById('btn-pdf-pedido');
        if (btnPdf) btnPdf.disabled = this.listaProductos.length === 0;
    },

    registrarPedido: async function (e) {
        e.preventDefault();

        // Validar que haya productos en la lista
        if (this.listaProductos.length === 0) {
            mostrarNotificacion('Debe agregar al menos un producto al pedido', 'warning');
            return;
        }

        if (!this.clienteSeleccionado) {
            mostrarNotificacion('Debe seleccionar un cliente', 'warning');
            return;
        }

        // Mostrar modal de confirmación en lugar de confirm()
        const confirmar = await this.mostrarConfirmacion(
            '¿Confirmar Registro?',
            `Se registrará el pedido con ${this.listaProductos.length} producto(s)`
        );

        if (!confirmar) return;

        const btn = e.target.querySelector('button[type="submit"]');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';

        try {
            const totalStr = document.getElementById('ped-total').textContent;
            const descuentoGlobal = parseFloat(document.getElementById('ped-descuento-global')?.value || 0);

            const pedidoData = {
                id_pedido: this.idPedidoEdicion, // Incluir si estamos editando
                fecha: document.getElementById('ped-fecha').value || new Date().toISOString().split('T')[0],
                vendedor: document.getElementById('ped-vendedor').value,
                cliente: this.clienteSeleccionado.nombre,
                nit: this.clienteSeleccionado.nit || '',
                direccion: this.clienteSeleccionado.direccion || '',
                ciudad: this.clienteSeleccionado.ciudad || '',
                forma_pago: document.getElementById('ped-pago').value,
                descuento_global: descuentoGlobal,
                observaciones: document.getElementById('ped-observaciones').value || '',
                productos: this.listaProductos.map(item => ({
                    codigo: item.codigo,
                    descripcion: item.descripcion,
                    cantidad: item.cantidad,
                    precio_unitario: item.precio_unitario
                }))
            };

            // LOG DE AUDITORÍA
            console.log("📦 ===== DATOS DEL PEDIDO =====");
            console.table(pedidoData);
            console.log("Total de productos:", pedidoData.productos.length);
            console.log("Descuento global:", descuentoGlobal + "%");

            const response = await fetch('/api/pedidos/registrar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pedidoData)
            });

            const result = await response.json();

            // LOG DE RESPUESTA
            console.log("🚀 ===== RESPUESTA DEL SERVIDOR =====");
            console.log("Status HTTP:", response.status);
            console.log("Datos de respuesta:", result);

            if (result.success) {
                console.log("✅ Pedido registrado exitosamente:", result.id_pedido);
                this.ultimoIdRegistrado = result.id_pedido;
                mostrarNotificacion(`✓ Pedido ${result.id_pedido} registrado con ${result.total_productos} productos`, 'success');

                // Limpiar formulario y lista SOLO después de éxito
                limpiarFormulario('form-pedidos');
                this.listaProductos = [];
                this.clienteSeleccionado = null;
                this.idPedidoEdicion = null;
                if (document.getElementById('edit-mode-indicator')) {
                    document.getElementById('edit-mode-indicator').style.display = 'none';
                }
                const btnSubmit = document.querySelector('#form-pedidos button[type="submit"]');
                if (btnSubmit) {
                    btnSubmit.innerHTML = '<i class="fas fa-paper-plane"></i> Registrar Pedido';
                    btnSubmit.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
                }
                this.renderizarTablaItems();
                this.calcularTotalPedido();
                document.getElementById('ped-total').textContent = '$ 0.00';
                if (document.getElementById('ped-descuento-global')) {
                    document.getElementById('ped-descuento-global').value = '0';
                }
                this.actualizarVendedor();

                // --- Preguntar por PDF tras registro ---
                // Capturamos datos antes de la confirmación porque es async y el estado podría cambiar
                const dataParaPDF = {
                    id_pedido: result.id_pedido,
                    fecha: pedidoData.fecha,
                    vendedor: pedidoData.vendedor,
                    cliente: {
                        nombre: pedidoData.cliente,
                        nit: pedidoData.nit,
                        direccion: '', city: '', telefonos: '' // Datos básicos
                    },
                    productos: JSON.parse(JSON.stringify(pedidoData.productos)),
                    total: totalStr, // Usar el string capturado arriba
                    forma_pago: pedidoData.forma_pago
                };

                setTimeout(async () => {
                    const descargar = await this.mostrarConfirmacion(
                        '¡Pedido Registrado!',
                        '¿Desea descargar el comprobante PDF del pedido ahora?'
                    );
                    if (descargar) {
                        this.generarPDF(dataParaPDF);
                    }
                }, 500);

            } else {
                console.error("❌ Error del servidor:", result.error);
                mostrarNotificacion(result.error || "Error desconocido", 'error');
            }

        } catch (error) {
            console.error("❌ ERROR DE CONEXIÓN:", error);
            mostrarNotificacion("Error de conexión con el servidor", 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    },

    generarPDF: function (datosManuales = null) {
        try {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF();

            // Si vienen datos manuales (ej: justo después de registrar), usarlos. 
            // Si no, leer del DOM (flujo normal).
            const fechaRaw = datosManuales ? datosManuales.fecha : document.getElementById('ped-fecha').value;
            const fecha = fechaRaw || new Date().toLocaleDateString();
            const vendedor = datosManuales ? datosManuales.vendedor : document.getElementById('ped-vendedor').value;
            const cliente = datosManuales ? datosManuales.cliente : (this.clienteSeleccionado || {
                nombre: document.getElementById('ped-cliente').value,
                nit: document.getElementById('ped-nit').value,
                direccion: '',
                telefonos: '',
                ciudad: ''
            });
            const totalStr = datosManuales ? datosManuales.total : document.getElementById('ped-total').textContent;
            const formaPago = datosManuales ? datosManuales.forma_pago : document.getElementById('ped-pago').value;
            const listaProductos = datosManuales ? datosManuales.productos : this.listaProductos;
            const idMostrar = datosManuales ? datosManuales.id_pedido : (this.ultimoIdRegistrado || `Ped-TEMP`);

            // --- 1. ENCABEZADO Y LOGO ---
            const imgPath = '/static/img/logo_friparts_nuevo.jpg';

            // Función interna para dibujar el contenido (con o sin logo)
            const dibujarContenido = (imgData = null) => {
                if (imgData) {
                    // El logo es un JPEG, intentamos con JPEG y si no PNG como fallback por compatibilidad de jsPDF
                    try {
                        doc.addImage(imgData, 'JPEG', 14, 10, 60, 28);
                    } catch (e) {
                        doc.addImage(imgData, 'PNG', 14, 10, 60, 28);
                    }
                }

                // Nombre de la empresa DEBAJO del logo (alineado a la izquierda)
                doc.setFontSize(22);
                doc.setTextColor(30, 58, 138); // Azul corporativo
                doc.setFont(undefined, 'bold');
                doc.text("FRIPARTS S.A.S", 14, 45);

                doc.setFontSize(10);
                doc.setTextColor(100);
                doc.setFont(undefined, 'normal');
                // SE ELIMINA EL ESLOGAN "Soluciones Integrales..." SOLICITADO POR EL USUARIO

                doc.text(`Comprobante No: ${idMostrar}`, 196, 20, { align: 'right' });
                doc.text(`Fecha: ${fecha}`, 196, 26, { align: 'right' });

                // --- 2. BLOQUE DE INFORMACIÓN (Grid de 2 columnas) ---
                doc.setDrawColor(220);
                doc.setLineWidth(0.5);
                doc.line(14, 55, 196, 55);

                // Columna Izquierda: Cliente (Ancho máx 100)
                doc.setFontSize(11);
                doc.setTextColor(30, 58, 138);
                doc.setFont(undefined, 'bold');
                doc.text("CLIENTE:", 14, 65);

                doc.setFontSize(10);
                doc.setTextColor(40);
                doc.setFont(undefined, 'normal');
                const splitNombre = doc.splitTextToSize(`Nombre: ${cliente.nombre}`, 110);
                doc.text(splitNombre, 14, 72);

                const nextY = 72 + (splitNombre.length * 5);
                doc.text(`NIT/ID: ${cliente.nit || 'N/A'}`, 14, nextY);
                doc.text(`Dirección: ${cliente.direccion || 'N/A'}`, 14, nextY + 7);
                doc.text(`Ciudad: ${cliente.ciudad || 'N/A'}`, 14, nextY + 14);
                doc.text(`Teléfonos: ${cliente.telefonos || 'N/A'}`, 14, nextY + 21);

                // Columna Derecha: Venta (Movida más a la derecha para evitar choques)
                const rightX = 135;
                doc.setFontSize(11);
                doc.setTextColor(30, 58, 138);
                doc.setFont(undefined, 'bold');
                doc.text("DETALLES DE VENTA:", rightX, 65);

                doc.setFontSize(10);
                doc.setTextColor(40);
                doc.setFont(undefined, 'normal');
                doc.text(`Vendedor: ${vendedor}`, rightX, 72);
                doc.text(`Forma de Pago: ${formaPago}`, rightX, 79);
                doc.text(`Estado: REGISTRADO`, rightX, 86);

                // --- 3. TABLA DE PRODUCTOS ---
                const tablaData = listaProductos.map(item => [
                    item.codigo,
                    item.descripcion,
                    item.cantidad,
                    formatearMoneda(item.precio_unitario),
                    formatearMoneda(item.cantidad * item.precio_unitario)
                ]);

                doc.autoTable({
                    startY: 115,
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

                // --- 4. TOTALES ---
                const finalY = doc.lastAutoTable.finalY + 10;
                const totalX = 196;

                // Cálculos para el PDF
                const subtotalBruto = listaProductos.reduce((acc, p) => acc + (p.cantidad * p.precio_unitario), 0);
                const valorDescuento = subtotalBruto * (descuentoGlobal / 100);
                const subtotalNeto = subtotalBruto - valorDescuento;
                const iva = subtotalNeto * 0.19;
                const totalFinal = subtotalNeto + iva;

                doc.setFontSize(10);
                doc.setTextColor(100);
                doc.setFont(undefined, 'normal');

                // Subtotal
                doc.text(`Subtotal:`, totalX - 45, finalY);
                doc.text(formatearMoneda(subtotalBruto), totalX, finalY, { align: 'right' });

                // Descuento (si existe)
                let currentY = finalY;
                if (descuentoGlobal > 0) {
                    currentY += 6;
                    doc.text(`Descuento (${descuentoGlobal}%):`, totalX - 45, currentY);
                    doc.text(`- ${formatearMoneda(valorDescuento)}`, totalX, currentY, { align: 'right' });
                }

                // IVA
                currentY += 6;
                doc.text(`IVA (19%):`, totalX - 45, currentY);
                doc.text(formatearMoneda(iva), totalX, currentY, { align: 'right' });

                // Línea de total
                currentY += 4;
                doc.setDrawColor(30, 58, 138);
                doc.setLineWidth(0.5);
                doc.line(totalX - 55, currentY, totalX, currentY);

                // Total Final
                currentY += 10;
                doc.setFontSize(15);
                doc.setTextColor(30, 58, 138);
                doc.setFont(undefined, 'bold');
                doc.text(`TOTAL A PAGAR: ${formatearMoneda(totalFinal)}`, totalX, currentY, { align: 'right' });

                // --- 5. FIRMAS Y PIE ---
                const footerY = 270;

                // Línea separadora final
                doc.setDrawColor(200);
                doc.setLineWidth(0.2);
                doc.line(14, footerY - 10, 196, footerY - 10);

                doc.setFontSize(8);
                doc.setTextColor(150);
                doc.text("Este documento es un comprobante interno de pedido y no constituye factura legal.", 105, footerY, { align: 'center' });
                doc.text("FRIPARTS S.A.S - Carrera 29 #78-40 - www.friparts.com", 105, footerY + 5, { align: 'center' });

                doc.setFontSize(9);
                doc.setTextColor(100);
                doc.setFont(undefined, 'normal');
                doc.text("Instagram: @friparts_bujes", 105, footerY + 11, { align: 'center' });

                // Guardar
                const fileName = `Pedido_${cliente.nombre.replace(/\s+/g, '_')}_${fecha}.pdf`;
                doc.save(fileName);
                mostrarNotificacion("PDF generado correctamente", "success");
            };

            // Intentar cargar logo antes de dibujar
            const img = new Image();
            img.onload = function () {
                dibujarContenido(this);
            };
            img.onerror = function () {
                console.warn("Logo no encontrado en /static/img/logo_friparts.png - Generando sin logo");
                dibujarContenido(null);
            };
            img.src = imgPath;

        } catch (error) {
            console.error("Error generando PDF:", error);
            mostrarNotificacion("No se pudo generar el PDF", "error");
        }
    },

    // Función para mostrar confirmación personalizada
    mostrarConfirmacion: function (titulo, mensaje) {
        return new Promise((resolve) => {
            // Crear modal de confirmación
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content confirmation-modal-pro" style="max-width: 420px; border: none; overflow: hidden; background-color: #ffffff;">
                    <div class="modal-header" style="background: white; border-bottom: 1px solid #e5e7eb; padding: 20px 25px;">
                        <h3 style="color: #111827; margin: 0; font-size: 1.25rem; font-weight: 600;"><i class="fas fa-question-circle" style="color: #3b82f6; margin-right: 12px;"></i> ${titulo}</h3>
                    </div>
                    <div class="modal-body" style="padding: 30px 25px; color: #374151; font-size: 1.05rem; line-height: 1.6; background-color: #ffffff;">
                        <p>${mensaje}</p>
                    </div>
                    <div class="modal-footer" style="background: #f9fafb; padding: 15px 25px; border-top: 1px solid #e5e7eb; display: flex; gap: 12px; justify-content: flex-end;">
                        <button class="btn btn-secondary" id="modal-cancelar" style="background: white; border: 1px solid #d1d5db; color: #374151; padding: 8px 16px; font-weight: 500; border-radius: 6px;">
                            Cancelar
                        </button>
                        <button class="btn btn-primary" id="modal-confirmar" style="background: #2563eb; color: white; border: 1px solid #2563eb; padding: 8px 20px; font-weight: 500; border-radius: 6px;">
                            Confirmar
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            // Event listeners
            document.getElementById('modal-confirmar').addEventListener('click', () => {
                document.body.removeChild(modal);
                resolve(true);
            });

            document.getElementById('modal-cancelar').addEventListener('click', () => {
                document.body.removeChild(modal);
                resolve(false);
            });

            // Cerrar al hacer clic fuera
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    document.body.removeChild(modal);
                    resolve(false);
                }
            });
        });
    },

    // Nueva función Toast Profesional
    showToast: function (mensaje, tipo = 'info') {
        // Colores de barra lateral según tipo
        const colores = {
            'success': '#10b981', // Verde
            'error': '#ef4444',   // Rojo
            'warning': '#f59e0b', // Naranja
            'info': '#3b82f6'     // Azul
        };

        const color = colores[tipo] || colores['info'];
        const icono = tipo === 'success' ? 'fa-check-circle' :
            tipo === 'error' ? 'fa-exclamation-triangle' :
                'fa-info-circle';

        const toast = document.createElement('div');
        toast.className = 'toast-notification';
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background-color: #ffffff;
            color: #333;
            padding: 16px 24px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 15px;
            z-index: 10000;
            min-width: 320px;
            border-left: 6px solid ${color};
            font-family: 'Segoe UI', system-ui, sans-serif;
            font-weight: 500;
            opacity: 0;
            transition: all 0.4s cubic-bezier(0.68, -0.55, 0.27, 1.55);
        `;

        toast.innerHTML = `
            <i class="fas ${icono}" style="color: ${color}; font-size: 1.2rem;"></i>
            <span style="flex: 1;">${mensaje}</span>
        `;

        document.body.appendChild(toast);

        // Animación de entrada
        requestAnimationFrame(() => {
            toast.style.top = '40px';
            toast.style.opacity = '1';
        });

        // Auto-eliminar
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.top = '0px';
            setTimeout(() => toast.remove(), 400);
        }, 3000);
    },

    // Método para integración con app.js
    inicializar: function () {
        console.log("🔧 Inicializando módulo Pedidos (desde app.js)");
        this.cargarDatosIniciales();
        this.actualizarVendedor();
    },

    // --- Lógica Exportación World Office ---
    abrirPreviewWO: function () {
        const modal = document.getElementById('modal-preview-wo');
        if (modal) {
            modal.style.display = 'block';
            this.cargarPreviewWO();
        }
    },

    cerrarPreviewWO: function () {
        const modal = document.getElementById('modal-preview-wo');
        if (modal) {
            modal.style.display = 'none';
            // Limpiar tabla
            const tbody = document.querySelector('#tabla-preview-wo tbody');
            if (tbody) tbody.innerHTML = '';
        }
    },

    cargarPreviewWO: async function () {
        const tbody = document.querySelector('#tabla-preview-wo tbody');
        const thead = document.querySelector('#tabla-preview-wo thead');

        if (!tbody || !thead) return;

        tbody.innerHTML = '<tr><td colspan="10" class="text-center"><i class="fas fa-spinner fa-spin"></i> Cargando vista previa...</td></tr>';

        try {
            const response = await fetch('/api/exportar/world-office/preview');
            const result = await response.json();

            if (result.success && result.data.length > 0) {
                // Render Headers
                const firstRow = result.data[0];
                const columns = Object.keys(firstRow);
                thead.innerHTML = '<tr>' + columns.map(col => `<th>${col}</th>`).join('') + '</tr>';

                // Render Rows
                tbody.innerHTML = result.data.map(row => {
                    return '<tr>' + columns.map(col => `<td>${row[col] !== null ? row[col] : ''}</td>`).join('') + '</tr>';
                }).join('');

            } else {
                tbody.innerHTML = '<tr><td colspan="10" class="text-center text-warning"><i class="fas fa-exclamation-triangle"></i> No hay pedidos pendientes para exportar.</td></tr>';
            }
        } catch (error) {
            console.error("Error cargando preview:", error);
            tbody.innerHTML = `<tr><td colspan="10" class="text-center text-danger">Error: ${error.message}</td></tr>`;
        }
    },

    descargarExcelWO: function () {
        const btn = document.getElementById('btn-confirmar-exportar-wo');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
        btn.disabled = true;

        fetch('/api/exportar/world-office', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}) // No params needed for v2 logic
        })
            .then(response => {
                if (response.ok) return response.blob();
                return response.json().then(err => Promise.reject(err));
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `Export_WO_${new Date().toISOString().slice(0, 10)}.xlsx`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                this.showToast('✅ Archivo generado correctamente.', 'success');
                this.cerrarPreviewWO();
            })
            .catch(error => {
                console.error("Error descarga WO:", error);
                this.showToast(`Error: ${error.error || error.message}`, 'error');
            })
            .finally(() => {
                btn.innerHTML = originalText;
                btn.disabled = false;
            });
    }
};

// Export global
window.ModuloPedidos = ModuloPedidos;

// Hook into Main App initialization
document.addEventListener('DOMContentLoaded', () => {
    const menuLink = document.querySelector('.menu-item[data-page="pedidos"]');
    if (menuLink) {
        menuLink.addEventListener('click', () => {
            ModuloPedidos.cargarDatosIniciales();
            ModuloPedidos.actualizarVendedor();
        });
    }

    ModuloPedidos.init();
});
