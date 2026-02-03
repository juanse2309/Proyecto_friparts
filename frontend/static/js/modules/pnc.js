// ============================================
// pnc.js - Lógica de PNC (Producto No Conforme) - NAMESPACED
// ============================================

const ModuloPNC = {
    /**
     * Cargar datos de PNC
     */
    cargarDatos: async function () {
        try {
            console.log('📦 [PNC] Cargando datos...');
            mostrarLoading(true);

            // Fecha actual
            const hoy = new Date().toISOString().split('T')[0];
            const fechaInput = document.getElementById('pnc-manual-fecha');
            if (fechaInput) fechaInput.value = hoy;

            console.log('✅ [PNC] Datos cargados');
            mostrarLoading(false);
        } catch (error) {
            console.error('Error [PNC] cargarDatos:', error);
            mostrarLoading(false);
        }
    },

    /**
     * Autocomplete de Producto (Aislado)
     */
    initAutocompleteProducto: function () {
        const input = document.getElementById('pnc-manual-producto');
        const suggestionsDiv = document.getElementById('pnc-manual-producto-suggestions');

        console.log('🔍 [PNC] initAutocomplete - Context:', { input: !!input, suggestions: !!suggestionsDiv });

        if (!input || !suggestionsDiv) return;

        let debounceTimer;

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim().toLowerCase();

            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                suggestionsDiv.style.display = 'none';
                return;
            }

            debounceTimer = setTimeout(() => {
                let products = [];
                if (window.AppState && window.AppState.sharedData && Array.isArray(window.AppState.sharedData.productos)) {
                    products = window.AppState.sharedData.productos;
                }

                console.log(`🔍 [PNC] Buscando "${query}" en ${products.length} productos`);

                const resultados = products.filter(prod => {
                    const cod = String(prod.codigo_sistema || prod.codigo || '').toLowerCase();
                    const desc = String(prod.descripcion || '').toLowerCase();
                    return cod.includes(query) || desc.includes(query);
                }).slice(0, 15);

                this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                    input.value = item.codigo_sistema || item.codigo || '';
                    suggestionsDiv.classList.remove('active');
                    suggestionsDiv.style.display = 'none';
                    console.log('✅ [PNC] Seleccionado:', input.value);
                });
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
                suggestionsDiv.style.display = 'none';
            }
        });
    },

    /**
     * Renderizador de sugerencias local
     */
    renderSuggestions: function (container, items, onSelect) {
        if (!container) return;

        if (items.length === 0) {
            container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
        } else {
            container.innerHTML = items.map(item => `
                <div class="suggestion-item" data-val="${item.codigo_sistema || item.codigo || ''}">
                    <strong>${item.codigo_sistema || item.codigo || ''}</strong><br>
                    <small>${item.descripcion || ''}</small>
                </div>
            `).join('');

            container.querySelectorAll('.suggestion-item').forEach((div, index) => {
                div.addEventListener('click', () => onSelect(items[index]));
            });
        }

        container.classList.add('active');
        container.style.display = 'block';
    },

    /**
     * Registrar PNC
     */
    registrar: async function () {
        try {
            mostrarLoading(true);

            const datos = {
                fecha: document.getElementById('pnc-manual-fecha')?.value || '',
                codigo_producto: document.getElementById('pnc-manual-producto')?.value || '',
                cantidad: document.getElementById('pnc-manual-cantidad')?.value || '0',
                criterio: document.getElementById('pnc-manual-criterio')?.value || '',
                notas: document.getElementById('pnc-manual-ensamble')?.value || ''
            };

            console.log('📤 [PNC] ENVIANDO:', datos);

            if (!datos.codigo_producto?.trim()) {
                mostrarNotificacion('⚠️ Ingresa código del producto', 'error');
                mostrarLoading(false);
                return;
            }

            const response = await fetch('/api/pnc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });

            const resultado = await response.json();

            if (response.ok && resultado.success) {
                mostrarNotificacion(`✅ ${resultado.mensaje || 'PNC registrado'}`, 'success');
                document.getElementById('form-manual-pnc')?.reset();
                this.cargarDatos();
            } else {
                mostrarNotificacion(`❌ ${resultado.error || 'Error'}`, 'error');
            }
        } catch (error) {
            console.error('Error [PNC] registrar:', error);
            mostrarNotificacion(`Error: ${error.message}`, 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    /**
     * Inicialización del módulo
     */
    inicializar: function () {
        console.log('🔧 [PNC] Inicializando...');
        this.cargarDatos();
        this.initAutocompleteProducto();

        const form = document.getElementById('form-manual-pnc');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.registrar();
            };
        }
        console.log('✅ [PNC] Módulo inicializado');
    }
};

// Exportación global
window.ModuloPNC = ModuloPNC;
window.initPnc = () => ModuloPNC.inicializar();
