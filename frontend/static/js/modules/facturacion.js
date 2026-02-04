// ============================================
// facturacion.js - Lógica de Facturación - NAMESPACED
// ============================================

const ModuloFacturacion = {
    clientesData: [],

    /**
     * Cargar datos de Facturación
     */
    cargarDatos: async function () {
        try {
            console.log('📦 [Facturación] Cargando datos...');
            mostrarLoading(true);

            // 1. Cargar clientes (desde API o AppState)
            let clientes = [];
            if (window.AppState && window.AppState.sharedData && Array.isArray(window.AppState.sharedData.clientes) && window.AppState.sharedData.clientes.length > 0) {
                clientes = window.AppState.sharedData.clientes;
            } else {
                clientes = await fetchData('/api/obtener_clientes');
            }

            this.clientesData = clientes;

            // 2. Poblar datalist de productos (Cache Compartido)
            if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
                console.log('✅ [Facturación] Usando productos del cache compartido');
                const datalist = document.getElementById('fac-productos-list');
                if (datalist) {
                    datalist.innerHTML = '';
                    window.AppState.sharedData.productos.forEach(p => {
                        const option = document.createElement('option');
                        const code = p.codigo_sistema || p.codigo;
                        option.value = code;
                        option.textContent = `${code} - ${p.descripcion}`;
                        datalist.appendChild(option);
                    });
                }
            }

            console.log('✅ [Facturación] Datos cargados');
            mostrarLoading(false);
        } catch (error) {
            console.error('Error [Facturación] cargarDatos:', error);
            mostrarLoading(false);
        }
    },

    /**
     * Autocomplete Producto (Local a Facturación)
     */
    initAutocompleteProducto: function () {
        const input = document.getElementById('producto-facturacion');
        const suggestionsDiv = document.getElementById('facturacion-producto-suggestions');

        if (!input || !suggestionsDiv) return;

        let debounceTimer;

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim().toLowerCase();

            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            debounceTimer = setTimeout(() => {
                const products = window.AppState.sharedData.productos || [];
                const resultados = products.filter(prod => {
                    const cod = String(prod.codigo_sistema || prod.codigo || '').toLowerCase();
                    const desc = String(prod.descripcion || '').toLowerCase();
                    return cod.includes(query) || desc.includes(query);
                }).slice(0, 15);

                this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                    input.value = item.codigo_sistema || item.codigo;
                    suggestionsDiv.classList.remove('active');
                });
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    /**
     * Autocomplete Cliente (Local a Facturación)
     */
    initAutocompleteCliente: function () {
        const input = document.getElementById('cliente-facturacion');
        const suggestionsDiv = document.getElementById('facturacion-cliente-suggestions');

        if (!input || !suggestionsDiv) return;

        let debounceTimer;

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim().toLowerCase();

            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            debounceTimer = setTimeout(() => {
                const resultados = this.clientesData.filter(c =>
                    (c.nombre || '').toLowerCase().includes(query) ||
                    (c.id || '').toString().includes(query)
                ).slice(0, 15);

                this.renderSuggestionsCliente(suggestionsDiv, resultados, (item) => {
                    input.value = item.nombre;
                    suggestionsDiv.classList.remove('active');
                });
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    /**
     * Renderizador Sugerencias Universal del Módulo
     */
    renderSuggestions: function (container, items, onSelect) {
        renderProductSuggestions(container, items, onSelect);
    },

    renderSuggestionsCliente: function (container, items, onSelect) {
        if (!container) return;
        if (items.length === 0) {
            container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
        } else {
            container.innerHTML = items.map(item => `
                <div class="suggestion-item" data-val="${item.id}">
                    <strong>${item.nombre}</strong><br>
                    <small>ID: ${item.id}</small>
                </div>
            `).join('');

            container.querySelectorAll('.suggestion-item').forEach((div, index) => {
                div.addEventListener('click', () => onSelect(items[index]));
            });
        }
        container.classList.add('active');
    },

    /**
     * Registrar Facturación
     */
    registrar: async function () {
        try {
            mostrarLoading(true);

            const datos = {
                cliente: document.getElementById('cliente-facturacion')?.value || '',
                codigo_producto: document.getElementById('producto-facturacion')?.value || '',
                cantidad_vendida: document.getElementById('cantidad-facturacion')?.value || '0',
                precio_unitario: document.getElementById('precio-facturacion')?.value || '0',
                orden_compra: document.getElementById('orden-compra-facturacion')?.value || '',
                fecha_inicio: document.getElementById('fecha-facturacion')?.value || new Date().toISOString().split('T')[0],
                observaciones: document.getElementById('observaciones-facturacion')?.value || ''
            };

            if (!datos.cliente || !datos.codigo_producto) {
                mostrarNotificacion('⚠️ Selecciona cliente y producto', 'error');
                mostrarLoading(false);
                return;
            }

            console.log('📤 [Facturación] ENVIANDO:', datos);

            const response = await fetch('/api/facturacion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });

            const resultado = await response.json();

            if (response.ok && resultado.success) {
                mostrarNotificacion(`✅ ${resultado.mensaje || 'Venta registrada'}`, 'success');
                document.getElementById('form-facturacion')?.reset();
                this.actualizarTotal();
                this.cargarDatos();
            } else {
                mostrarNotificacion(`❌ Error: ${resultado.error || 'Falla en registro'}`, 'error');
            }
        } catch (error) {
            console.error('Error [Facturación] registrar:', error);
            mostrarNotificacion(`Error: ${error.message}`, 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    /**
     * Cálculo de total
     */
    actualizarTotal: function () {
        const cantidad = parseFloat(document.getElementById('cantidad-facturacion')?.value) || 0;
        const precio = parseFloat(document.getElementById('precio-facturacion')?.value) || 0;
        const total = cantidad * precio;

        const displayTotal = document.getElementById('total-facturacion');
        if (displayTotal) {
            displayTotal.textContent = `$ ${formatNumber(total)}`;
        }
    },

    /**
     * Inicializar módulo
     */
    inicializar: function () {
        console.log('🔧 [Facturación] Inicializando...');
        this.cargarDatos();
        this.initAutocompleteProducto();
        this.initAutocompleteCliente();

        document.getElementById('cantidad-facturacion')?.addEventListener('input', () => this.actualizarTotal());
        document.getElementById('precio-facturacion')?.addEventListener('input', () => this.actualizarTotal());

        const form = document.getElementById('form-facturacion');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.registrar();
            };
        }

        console.log('✅ [Facturación] Módulo inicializado');
    }
};

// Exportar
window.ModuloFacturacion = ModuloFacturacion;
window.initFacturacion = () => ModuloFacturacion.inicializar();
