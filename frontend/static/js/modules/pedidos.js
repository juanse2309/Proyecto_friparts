
// pedidos.js - Módulo de Gestión de Pedidos

const ModuloPedidos = {
    init: function () {
        console.log("🛒 Inicializando Módulo Pedidos...");

        // 1. Listeners de cálculo
        const inputsCalculo = ['ped-cantidad', 'ped-precio', 'ped-descuento'];
        inputsCalculo.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', () => this.calcularTotal());
            }
        });

        // 2. Submit del formulario
        const form = document.getElementById('form-pedidos');
        if (form) {
            form.addEventListener('submit', (e) => this.registrarPedido(e));
        }

        // 3. Auto-fill NIT al seleccionar cliente
        const selectCliente = document.getElementById('ped-cliente');
        if (selectCliente) {
            selectCliente.addEventListener('change', () => this.autoFillNIT());
        }

        // 4. Auto-fill precio al seleccionar producto
        const inputProducto = document.getElementById('ped-producto');
        if (inputProducto) {
            inputProducto.addEventListener('change', () => this.autoFillPrecio());
        }

        // 5. Inicializar fecha
        const inputFecha = document.getElementById('ped-fecha');
        if (inputFecha) {
            inputFecha.valueAsDate = new Date();
        }
    },

    cargarDatosIniciales: async function () {
        console.log("📦 Cargando datos para Pedidos...");

        // Cargar Clientes desde AppState (ya cargados en app.js)
        try {
            const selectCliente = document.getElementById('ped-cliente');
            if (!selectCliente) return;

            // Usar datos compartidos si ya están cargados (ahora son objetos {nombre, nit})
            if (window.AppState && window.AppState.sharedData.clientes.length > 0) {
                selectCliente.innerHTML = '<option value="">Seleccione cliente...</option>';
                window.AppState.sharedData.clientes.forEach(cliente => {
                    const opt = document.createElement('option');
                    opt.value = cliente.nombre;
                    opt.textContent = cliente.nombre;
                    opt.dataset.nit = cliente.nit || ''; // Guardar NIT en dataset
                    selectCliente.appendChild(opt);
                });
                console.log("✅ Clientes cargados:", window.AppState.sharedData.clientes.length);
            } else {
                // Fallback: cargar directamente
                const response = await fetch('/api/obtener_clientes');
                const clientes = await response.json();
                selectCliente.innerHTML = '<option value="">Seleccione cliente...</option>';
                clientes.forEach(cliente => {
                    const opt = document.createElement('option');
                    opt.value = cliente.nombre;
                    opt.textContent = cliente.nombre;
                    opt.dataset.nit = cliente.nit || '';
                    selectCliente.appendChild(opt);
                });
            }
        } catch (e) {
            console.error("Error cargando clientes:", e);
        }

        // Cargar Productos (Datalist)
        try {
            const datalist = document.getElementById('ped-productos-list');
            if (!datalist) return;

            // Limpiar si ya tiene datos
            if (datalist.options.length > 0) return;

            // Usar datos compartidos
            if (window.AppState && window.AppState.sharedData.productos.length > 0) {
                window.AppState.sharedData.productos.forEach(prod => {
                    const opt = document.createElement('option');
                    opt.value = `${prod.codigo_sistema} - ${prod.descripcion}`;
                    datalist.appendChild(opt);
                });
                console.log("✅ Productos cargados:", window.AppState.sharedData.productos.length);
            } else {
                // Fallback: cargar directamente
                const response = await fetch('/api/productos/listar');
                const data = await response.json();
                const productos = data.items || data;

                productos.forEach(prod => {
                    const opt = document.createElement('option');
                    const codigo = prod.codigo || prod.codigo_sistema || prod['CODIGO SISTEMA'] || '';
                    const desc = prod.descripcion || prod['DESCRIPCION'] || '';
                    opt.value = `${codigo} - ${desc}`;
                    datalist.appendChild(opt);
                });
            }
        } catch (e) {
            console.error("Error cargando productos para pedidos:", e);
        }

        // Pre-fill vendedor
        this.actualizarVendedor();
    },

    autoFillNIT: function () {
        const selectCliente = document.getElementById('ped-cliente');
        const inputNIT = document.getElementById('ped-nit');

        if (!selectCliente || !inputNIT) return;

        const selectedOption = selectCliente.options[selectCliente.selectedIndex];
        if (selectedOption && selectedOption.dataset.nit) {
            inputNIT.value = selectedOption.dataset.nit;
            console.log("🔄 NIT auto-llenado:", selectedOption.dataset.nit);
        }
    },

    autoFillPrecio: function () {
        const inputProducto = document.getElementById('ped-producto');
        const inputPrecio = document.getElementById('ped-precio');

        if (!inputProducto || !inputPrecio) return;

        // Extraer código del producto (formato: "CODIGO - DESC")
        const valorProducto = inputProducto.value;
        if (!valorProducto.includes(' - ')) return;

        const codigo = valorProducto.split(' - ')[0].trim();

        // Buscar en AppState.sharedData.productos
        if (window.AppState && window.AppState.sharedData.productos.length > 0) {
            const producto = window.AppState.sharedData.productos.find(p =>
                p.codigo_sistema === codigo || p.id_codigo == codigo
            );

            if (producto && producto.precio) {
                inputPrecio.value = producto.precio;
                console.log("💰 Precio auto-llenado:", producto.precio);
                // Recalcular total
                this.calcularTotal();
            }
        }
    },

    actualizarVendedor: function () {
        const inputVendedor = document.getElementById('ped-vendedor');
        if (!inputVendedor) {
            console.warn('⚠️  Campo vendedor no encontrado en el DOM');
            return;
        }

        // Intentar múltiples fuentes para obtener el nombre del usuario
        let nombreVendedor = null;

        // Prioridad 1: window.AppState.user.name
        if (window.AppState && window.AppState.user && window.AppState.user.name) {
            nombreVendedor = window.AppState.user.name;
            console.log(`👤 Vendedor obtenido desde AppState: ${nombreVendedor}`);
        }
        // Prioridad 2: AuthModule.currentUser
        else if (window.AuthModule && window.AuthModule.currentUser && window.AuthModule.currentUser.nombre) {
            nombreVendedor = window.AuthModule.currentUser.nombre;
            console.log(`👤 Vendedor obtenido desde AuthModule: ${nombreVendedor}`);
        }
        // Prioridad 3: sessionStorage
        else {
            try {
                const storedUser = sessionStorage.getItem('friparts_user');
                if (storedUser) {
                    const userData = JSON.parse(storedUser);
                    nombreVendedor = userData.nombre;
                    console.log(`👤 Vendedor obtenido desde sessionStorage: ${nombreVendedor}`);
                }
            } catch (e) {
                console.error('Error parseando sessionStorage:', e);
            }
        }

        // Asignar el vendedor si se encontró
        if (nombreVendedor) {
            inputVendedor.value = nombreVendedor;
            inputVendedor.readOnly = true;
            console.log(`✅ Vendedor asignado al formulario: ${nombreVendedor}`);
        } else {
            // Silencioso: Si no hay usuario, probablemente aún no se ha logueado
            // No mostrar warning para evitar confusión
            console.log('ℹ️  Vendedor pendiente: esperando login de usuario');
        }
    },

    calcularTotal: function () {
        const cantidad = parseFloat(document.getElementById('ped-cantidad').value) || 0;
        const precio = parseFloat(document.getElementById('ped-precio').value) || 0;
        const descuento = parseFloat(document.getElementById('ped-descuento').value) || 0;

        let subtotal = cantidad * precio;
        let total = subtotal * (1 - (descuento / 100));

        document.getElementById('ped-total').textContent = `$ ${formatNumber(total)}`;
    },

    registrarPedido: async function (e) {
        e.preventDefault();

        if (!confirm("¿Confirma el registro del pedido?")) return;

        const btn = e.target.querySelector('button[type="submit"]');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';

        try {
            // Extraer ID del producto del input (Formato: "CODIGO - DESC")
            const valProducto = document.getElementById('ped-producto').value;
            const idCodigo = valProducto.split(' - ')[0].trim();
            const descripcion = valProducto.includes(' - ') ? valProducto.split(' - ')[1].trim() : '';

            const pedidoData = {
                fecha: document.getElementById('ped-fecha').value,
                vendedor: document.getElementById('ped-vendedor').value,
                cliente: document.getElementById('ped-cliente').value,
                nit: document.getElementById('ped-nit').value,
                id_codigo: idCodigo,
                descripcion: descripcion,
                cantidad: document.getElementById('ped-cantidad').value,
                precio_unitario: document.getElementById('ped-precio').value,
                descuento: document.getElementById('ped-descuento').value,
                forma_pago: document.getElementById('ped-pago').value
            };

            // LOG DE AUDITORÍA: Mostrar datos antes del envío
            console.log("📦 ===== DATOS DEL PEDIDO (PRE-ENVÍO) =====");
            console.table(pedidoData);
            console.log("Total de campos:", Object.keys(pedidoData).length);
            console.log("Vendedor capturado:", pedidoData.vendedor || "UNDEFINED ⚠️");

            const response = await fetch('/api/pedidos/registrar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pedidoData)
            });

            const result = await response.json();

            // LOG DE RESPUESTA
            console.log("🚀 ===== RESPUESTA DEL SERVIDOR =====");
            console.log("Status HTTP:", response.status);
            console.log("Response OK:", response.ok);
            console.log("Datos de respuesta:", result);

            if (result.success) {
                console.log("✅ Pedido registrado exitosamente:", result.id_pedido);
                mostrarNotificacion(`Pedido registrado: ${result.id_pedido}`, 'success');
                limpiarFormulario('form-pedidos');
                document.getElementById('ped-total').textContent = '$ 0.00';
                this.actualizarVendedor(); // Restaurar vendedor despues de limpiar
            } else {
                console.error("❌ Error del servidor:", result.error);
                mostrarNotificacion(result.error || "Error desconocido", 'error');
            }

        } catch (error) {
            console.error("❌ ERROR DE CONEXIÓN:", error);
            mostrarNotificacion("Error de conexión", 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
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

// Hook into Main App initialization if needed, or Listen loop
document.addEventListener('DOMContentLoaded', () => {
    // Wait for auth to be ready?
    // Listen for tab change to load data
    const menuLink = document.querySelector('.menu-item[data-page="pedidos"]');
    if (menuLink) {
        menuLink.addEventListener('click', () => {
            ModuloPedidos.cargarDatosIniciales();
            ModuloPedidos.actualizarVendedor();
        });
    }

    // Also init logic
    ModuloPedidos.init();
});
