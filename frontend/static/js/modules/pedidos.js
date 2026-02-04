
// pedidos.js - Módulo de Gestión de Pedidos

const ModuloPedidos = {
    listaProductos: [], // Array de productos: [{codigo, descripcion, cantidad, precio_unitario, stock_disponible}]
    clientesData: [],  // Cache de clientes
    productosData: [], // Cache de productos
    clienteSeleccionado: null, // {nombre, nit}

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

    buscarClientes: function (query, suggestionsDiv) {
        const resultados = this.clientesData.filter(cliente =>
            cliente.nombre.toLowerCase().includes(query.toLowerCase()) ||
            (cliente.nit && cliente.nit.includes(query))
        );

        if (resultados.length === 0) {
            suggestionsDiv.innerHTML = '<div class="suggestion-item">No se encontraron clientes</div>';
            suggestionsDiv.classList.add('active');
            return;
        }

        suggestionsDiv.innerHTML = resultados.map(cliente => `
            <div class="suggestion-item" data-nombre="${cliente.nombre}" data-nit="${cliente.nit || ''}">
                <strong>${cliente.nombre}</strong>
                ${cliente.nit ? `<br><small>NIT: ${cliente.nit}</small>` : ''}
            </div>
        `).join('');

        // Event listeners para selección
        suggestionsDiv.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                this.seleccionarCliente({
                    nombre: item.dataset.nombre,
                    nit: item.dataset.nit
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
        console.log("🔄 Cliente seleccionado:", cliente.nombre);
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
        const resultados = this.productosData.filter(prod =>
            prod.codigo_sistema.toLowerCase().includes(query.toLowerCase()) ||
            prod.descripcion.toLowerCase().includes(query.toLowerCase())
        );

        if (resultados.length === 0) {
            suggestionsDiv.innerHTML = '<div class="suggestion-item">No se encontraron productos</div>';
            suggestionsDiv.classList.add('active');
            return;
        }

        renderProductSuggestions(suggestionsDiv, resultados.slice(0, 10), (item) => {
            document.getElementById('ped-producto').value = `${item.codigo_sistema} - ${item.descripcion}`;
            document.getElementById('ped-precio').value = item.precio || 0;
            console.log("💰 Producto seleccionado:", item.codigo_sistema, "Stock:", item.stock_total);
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
        }
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
            stock_disponible: 'N/A'
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
            return;
        }

        tbody.innerHTML = this.listaProductos.map((item, index) => {
            const subtotal = item.cantidad * item.precio_unitario;
            return `
                <tr>
                    <td data-label="Código">${item.codigo}</td>
                    <td data-label="Descripción">${item.descripcion}</td>
                    <td data-label="Cantidad">${item.cantidad}</td>
                    <td data-label="Precio Unit.">$${formatNumber(item.precio_unitario)}</td>
                    <td data-label="Subtotal">$${formatNumber(subtotal)}</td>
                    <td data-label="Acciones">
                        <button type="button" class="btn btn-sm btn-danger" onclick="ModuloPedidos.eliminarItemDelCarrito(${index})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    },

    calcularTotalPedido: function () {
        const descuentoGlobal = parseFloat(document.getElementById('ped-descuento-global')?.value || 0);

        const subtotal = this.listaProductos.reduce((sum, item) => {
            return sum + (item.cantidad * item.precio_unitario);
        }, 0);

        const total = subtotal * (1 - descuentoGlobal / 100);

        document.getElementById('ped-total').textContent = `$ ${formatNumber(total)}`;
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
            const descuentoGlobal = parseFloat(document.getElementById('ped-descuento-global')?.value || 0);

            const pedidoData = {
                fecha: document.getElementById('ped-fecha').value,
                vendedor: document.getElementById('ped-vendedor').value,
                cliente: this.clienteSeleccionado.nombre,
                nit: this.clienteSeleccionado.nit || '',
                forma_pago: document.getElementById('ped-pago').value,
                descuento_global: descuentoGlobal,
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
                mostrarNotificacion(`✓ Pedido ${result.id_pedido} registrado con ${result.total_productos} productos`, 'success');

                // Limpiar formulario y lista SOLO después de éxito
                limpiarFormulario('form-pedidos');
                this.listaProductos = [];
                this.clienteSeleccionado = null;
                this.renderizarTablaItems();
                this.calcularTotalPedido();
                document.getElementById('ped-total').textContent = '$ 0.00';
                if (document.getElementById('ped-descuento-global')) {
                    document.getElementById('ped-descuento-global').value = '0';
                }
                this.actualizarVendedor();
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
