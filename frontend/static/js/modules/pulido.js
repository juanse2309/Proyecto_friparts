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
        this.intentarAutoSeleccionarResponsable();

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
                // Mapear de objetos a strings para el buscador
                this.responsablesData = responsables.map(r => typeof r === 'object' ? r.nombre : r);
            }

            // 2. Cargar Productos (Cache Compartido)
            if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
                this.productosData = window.AppState.sharedData.productos;
            } else {
                const prods = await fetchData('/api/productos/listar');
                this.productosData = prods?.productos || prods?.items || (Array.isArray(prods) ? prods : []);
            }

            mostrarLoading(false);
        } catch (error) {
            console.error('Error [Pulido] cargarDatos:', error);
            mostrarLoading(false);
        }
    },

    intentarAutoSeleccionarResponsable: function () {
        const input = document.getElementById('responsable-pulido');
        if (!input) return;

        let nombreUsuario = null;

        if (window.AppState?.user?.name) {
            nombreUsuario = window.AppState.user.name;
        } else if (window.AuthModule?.currentUser?.nombre) {
            nombreUsuario = window.AuthModule.currentUser.nombre;
        }

        if (nombreUsuario) {
            input.value = nombreUsuario;
            console.log(`✅ [Pulido] Responsable auto-asignado: ${nombreUsuario}`);
        } else {
            console.log('⏳ [Pulido] Esperando usuario para auto-asignación...');
            const handler = () => {
                this.intentarAutoSeleccionarResponsable();
                window.removeEventListener('user-ready', handler);
            };
            window.addEventListener('user-ready', handler);

            // Polling fallback
            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                if (window.AppState?.user?.name) {
                    this.intentarAutoSeleccionarResponsable();
                    clearInterval(interval);
                    window.removeEventListener('user-ready', handler);
                }
                if (attempts > 10) clearInterval(interval);
            }, 500);
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
                    String(prod.codigo_sistema || '').toLowerCase().includes(query) ||
                    String(prod.descripcion || '').toLowerCase().includes(query)
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
        if (isProduct) {
            renderProductSuggestions(container, items, onSelect);
        } else {
            if (items.length === 0) {
                container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
                container.classList.add('active');
                return;
            }

            container.innerHTML = items.map(item => `<div class="suggestion-item" data-val="${item}">${item}</div>`).join('');

            container.querySelectorAll('.suggestion-item').forEach((div, index) => {
                div.addEventListener('click', () => {
                    onSelect(items[index]);
                });
            });

            container.classList.add('active');
        }
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
        const bujesInput = document.getElementById('bujes-buenos-pulido');

        if (bujesInput) bujesInput.oninput = () => this.actualizarCalculo();
        if (pncInput) pncInput.oninput = () => this.actualizarCalculo();
    },

    actualizarCalculo: function () {
        const entradaInput = document.getElementById('entrada-pulido');
        const pncInput = document.getElementById('pnc-pulido');
        const buenosInput = document.getElementById('bujes-buenos-pulido');

        let buenos = Number(buenosInput?.value) || 0;
        let pnc = Number(pncInput?.value) || 0;

        // Nueva Lógica: Total Entrada = Buenos + PNC
        const totalEntrada = buenos + pnc;

        const displaySalida = document.getElementById('salida-calculada');
        const formulaCalc = document.getElementById('formula-calc-pulido');
        const piezasBuenasDisplay = document.getElementById('piezas-buenas-pulido');

        // Actualizar el campo readonly de Entrada (Total)
        if (entradaInput) entradaInput.value = totalEntrada;

        if (displaySalida) displaySalida.textContent = formatNumber(buenos);
        if (formulaCalc) formulaCalc.textContent = `Buenas: ${formatNumber(buenos)} + PNC: ${formatNumber(pnc)} = ${formatNumber(totalEntrada)} Total Procesado`;
        if (piezasBuenasDisplay) piezasBuenasDisplay.textContent = `Total a descontar: ${formatNumber(totalEntrada)}`;
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
                cantidad_recibida: document.getElementById('entrada-pulido')?.value || '0', // Este es el Total Calculado
                cantidad_real: document.getElementById('bujes-buenos-pulido')?.value || '0', // Estas son las Buenas
                pnc: document.getElementById('pnc-pulido')?.value || '0',
                criterio_pnc: document.getElementById('criterio-pnc-hidden')?.value || '',
                observaciones: document.getElementById('observaciones-pulido')?.value || ''
            };

            // Asegurar integridad de datos
            const buenos = Number(datos.cantidad_real) || 0;
            const pnc = Number(datos.pnc) || 0;
            // Recalcular por seguridad
            datos.cantidad_recibida = (buenos + pnc).toString();

            if (!datos.codigo_producto?.trim()) {
                mostrarNotificacion('⚠️ Ingresa código del producto', 'error');
                return;
            }

            // Confirmación Pro
            const confirmar = await this.mostrarConfirmacion(
                '¿Confirmar Registro?',
                `Producto: ${datos.codigo_producto}<br>Entrada: ${datos.cantidad_recibida}<br>Buenas: ${datos.cantidad_real}`
            );

            if (!confirmar) return;

            mostrarLoading(true);

            const response = await fetch('/api/pulido', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });

            const resultado = await response.json();
            if (response.ok && resultado.success) {
                // Preparar datos para restauración
                const datosRestaurar = { ...datos };
                const metaConCallback = {
                    ...resultado.undo_meta,
                    restoreCallback: () => {
                        // Restaurar valores Pulido
                        document.getElementById('fecha-pulido').value = datosRestaurar.fecha_inicio;
                        document.getElementById('responsable-pulido').value = datosRestaurar.responsable;
                        document.getElementById('hora-inicio-pulido').value = datosRestaurar.hora_inicio;
                        document.getElementById('hora-fin-pulido').value = datosRestaurar.hora_fin;
                        document.getElementById('codigo-producto-pulido').value = datosRestaurar.codigo_producto;
                        document.getElementById('lote-pulido').value = datosRestaurar.lote;
                        document.getElementById('orden-produccion-pulido').value = datosRestaurar.orden_produccion;

                        // Restaurar cantidades y calcular
                        document.getElementById('bujes-buenos-pulido').value = datosRestaurar.cantidad_real;
                        document.getElementById('pnc-pulido').value = datosRestaurar.pnc;
                        document.getElementById('criterio-pnc-hidden').value = datosRestaurar.criterio_pnc;
                        document.getElementById('observaciones-pulido').value = datosRestaurar.observaciones;

                        // Re-calcular
                        if (ModuloPulido.actualizarCalculo) ModuloPulido.actualizarCalculo();
                        mostrarNotificacion('Formulario restaurado', 'info');
                    }
                };
                mostrarNotificacion('✅ Registro exitoso', 'success', metaConCallback);
                document.getElementById('form-pulido')?.reset();
                this.intentarAutoSeleccionarResponsable();
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

    mostrarConfirmacion: function (titulo, mensaje) {
        return new Promise((resolve) => {
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
                        <button class="btn btn-secondary" id="modal-cancelar-pulido" style="background: white; border: 1px solid #d1d5db; color: #374151; padding: 8px 16px; font-weight: 500; border-radius: 6px;">
                            Cancelar
                        </button>
                        <button class="btn btn-primary" id="modal-confirmar-pulido" style="background: #2563eb; color: white; border: 1px solid #2563eb; padding: 8px 20px; font-weight: 500; border-radius: 6px;">
                            Confirmar
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            document.getElementById('modal-confirmar-pulido').addEventListener('click', () => {
                document.body.removeChild(modal);
                resolve(true);
            });

            document.getElementById('modal-cancelar-pulido').addEventListener('click', () => {
                document.body.removeChild(modal);
                resolve(false);
            });

            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    document.body.removeChild(modal);
                    resolve(false);
                }
            });
        });
    },

    inicializar: function () { return this.init(); }
};

// Exportación global
window.ModuloPulido = ModuloPulido;
window.initPulido = () => ModuloPulido.init();
window.actualizarCalculoPulido = () => ModuloPulido.actualizarCalculo();
