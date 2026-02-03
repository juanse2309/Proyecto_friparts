// ============================================
// pulido.js - Lógica de Pulido (SMART SEARCH) - NAMESPACED
// ============================================

const ModuloPulido = {
    productosData: [],
    responsablesData: [],

    init: async function () {
        console.log('🔧 [Pulido] Inicializando módulo Smart...');
        await this.cargarDatos();
        this.configurarEventos();
        this.initAutocompleteProducto();
        this.initAutocompleteResponsable();

        // Inicializar Lote con fecha de hoy
        const loteInput = document.getElementById('lote-pulido');
        if (loteInput && !loteInput.value) {
            loteInput.value = new Date().toISOString().split('T')[0];
        }

        console.log('✅ [Pulido] Módulo inicializado');
    },

    cargarDatos: async function () {
        try {
            console.log('📦 [Pulido] Cargando datos...');
            mostrarLoading(true);

            // 1. Cargar Responsables
            const responsables = await fetchData('/api/obtener_responsables');
            if (responsables) {
                this.responsablesData = responsables;
            }

            // 2. Cargar Productos (Cache Compartido)
            if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
                this.productosData = window.AppState.sharedData.productos;
            } else {
                const prods = await fetchData('/api/productos/listar');
                this.productosData = prods.items || prods;
            }

            mostrarLoading(false);
        } catch (error) {
            console.error('Error [Pulido] cargarDatos:', error);
            mostrarLoading(false);
        }
    },

    initAutocompleteProducto: function () {
        const input = document.getElementById('codigo-producto-pulido');
        const suggestionsDiv = document.getElementById('pulido-producto-suggestions');

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
                const resultados = this.productosData.filter(prod =>
                    (prod.codigo_sistema || '').toLowerCase().includes(query) ||
                    (prod.descripcion || '').toLowerCase().includes(query)
                ).slice(0, 15);

                this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                    input.value = item.codigo_sistema || item.codigo;
                    suggestionsDiv.classList.remove('active');
                }, true);
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    initAutocompleteResponsable: function () {
        const input = document.getElementById('responsable-pulido');
        const suggestionsDiv = document.getElementById('pulido-responsable-suggestions');

        if (!input || !suggestionsDiv) return;

        input.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            if (query.length < 1) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            const resultados = this.responsablesData.filter(resp =>
                resp.toLowerCase().includes(query)
            );

            this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                input.value = item;
                suggestionsDiv.classList.remove('active');
            }, false);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    renderSuggestions: function (container, items, onSelect, isProduct) {
        if (items.length === 0) {
            container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
            container.classList.add('active');
            return;
        }

        container.innerHTML = items.map(item => {
            if (isProduct) {
                return `
                <div class="suggestion-item" data-val="${item.codigo_sistema || item.codigo}">
                    <strong>${item.codigo_sistema || item.codigo}</strong><br>
                    <small>${item.descripcion}</small>
                </div>`;
            } else {
                return `<div class="suggestion-item" data-val="${item}">${item}</div>`;
            }
        }).join('');

        container.querySelectorAll('.suggestion-item').forEach((div, index) => {
            div.addEventListener('click', () => {
                onSelect(items[index]);
            });
        });

        container.classList.add('active');
    },

    configurarEventos: function () {
        const form = document.getElementById('form-pulido');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.registrar();
            };
        }

        const entradaInput = document.getElementById('entrada-pulido');
        const pncInput = document.getElementById('pnc-pulido');

        if (entradaInput) entradaInput.oninput = () => this.actualizarCalculo();
        if (pncInput) pncInput.oninput = () => this.actualizarCalculo();
    },

    actualizarCalculo: function () {
        const entradaInput = document.getElementById('entrada-pulido');
        const pncInput = document.getElementById('pnc-pulido');
        const buenosInput = document.getElementById('bujes-buenos-pulido');

        let entrada = Number(entradaInput?.value) || 0;
        let pnc = Number(pncInput?.value) || 0;

        if (pnc > entrada) {
            mostrarNotificacion('⚠️ PNC no puede ser mayor que la cantidad recibida', 'warning');
            pnc = entrada;
            if (pncInput) pncInput.value = pnc;
        }

        const totalReal = Math.max(0, entrada - pnc);
        const displaySalida = document.getElementById('salida-calculada');
        const formulaCalc = document.getElementById('formula-calc-pulido');
        const piezasBuenasDisplay = document.getElementById('piezas-buenas-pulido');

        if (displaySalida) displaySalida.textContent = formatNumber(totalReal);
        if (formulaCalc) formulaCalc.textContent = `Recibida: ${formatNumber(entrada)} - PNC: ${formatNumber(pnc)} = ${formatNumber(totalReal)} piezas pulidas`;
        if (piezasBuenasDisplay) piezasBuenasDisplay.textContent = `Total: ${formatNumber(totalReal)} piezas buenas`;
        if (buenosInput) buenosInput.value = totalReal;
    },

    registrar: async function () {
        try {
            const datos = {
                fecha_inicio: document.getElementById('fecha-pulido')?.value || '',
                responsable: document.getElementById('responsable-pulido')?.value || '',
                hora_inicio: document.getElementById('hora-inicio-pulido')?.value || '',
                hora_fin: document.getElementById('hora-fin-pulido')?.value || '',
                codigo_producto: document.getElementById('codigo-producto-pulido')?.value || '',
                lote: document.getElementById('lote-pulido')?.value || '',
                orden_produccion: document.getElementById('orden-produccion-pulido')?.value || '',
                cantidad_recibida: document.getElementById('entrada-pulido')?.value || '0',
                cantidad_real: document.getElementById('bujes-buenos-pulido')?.value || '0',
                pnc: document.getElementById('pnc-pulido')?.value || '0',
                criterio_pnc: document.getElementById('criterio-pnc-hidden')?.value || '',
                observaciones: document.getElementById('observaciones-pulido')?.value || ''
            };

            const entrada = Number(datos.cantidad_recibida) || 0;
            const pnc = Number(datos.pnc) || 0;
            datos.cantidad_real = Math.max(0, entrada - pnc).toString();

            if (!datos.codigo_producto?.trim()) {
                mostrarNotificacion('⚠️ Ingresa código del producto', 'error');
                return;
            }

            if (!(await new Promise(resolve => resolve(window.confirm(`¿Confirmar registro de Pulido?\n\nProducto: ${datos.codigo_producto}\nEntrada: ${datos.cantidad_recibida}\nBuenas: ${datos.cantidad_real}`))))) return;

            mostrarLoading(true);

            const response = await fetch('/api/pulido', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });

            const resultado = await response.json();
            if (response.ok && resultado.success) {
                mostrarNotificacion('✅ Registro exitoso', 'success');
                document.getElementById('form-pulido')?.reset();
                window.tmpDefectosPulido = [];
                this.actualizarCalculo();
                const loteInput = document.getElementById('lote-pulido');
                if (loteInput) loteInput.value = new Date().toISOString().split('T')[0];
            } else {
                mostrarNotificacion(`❌ Error: ${resultado.error || 'Falla'}`, 'error');
            }
        } catch (error) {
            console.error('Error [Pulido] registrar:', error);
            mostrarNotificacion('Error de conexión', 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    inicializar: function () { return this.init(); }
};

// Exportación global
window.ModuloPulido = ModuloPulido;
window.initPulido = () => ModuloPulido.init();
window.actualizarCalculoPulido = () => ModuloPulido.actualizarCalculo();
