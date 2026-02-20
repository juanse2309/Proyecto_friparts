// ============================================
// inyeccion.js - Lógica de Inyección (SMART SEARCH) - NAMESPACED
// ============================================

const ModuloInyeccion = {
    productosData: [],
    responsablesData: [],

    init: async function () {
        console.log('🔧 [Inyeccion] Inicializando módulo Smart...');
        await this.cargarDatos();
        this.configurarEventos();
        this.initAutocompleteProducto();
        this.initAutocompleteResponsable();
        this.intentarAutoSeleccionarResponsable();

        // Inicializar fecha
        const fechaHoy = new Date().toISOString().split('T')[0];
        const fechaInput = document.getElementById('fecha-inyeccion');
        if (fechaInput && !fechaInput.value) fechaInput.value = fechaHoy;
    },

    cargarDatos: async function () {
        try {
            console.log('📦 [Inyeccion] Cargando datos...');
            mostrarLoading(true);

            // 1. Cargar Responsables
            const responsables = await fetchData('/api/obtener_responsables');
            if (responsables) {
                // Mapear de objetos a strings para mantener compatibilidad con el buscador
                this.responsablesData = responsables.map(r => typeof r === 'object' ? r.nombre : r);
            }

            // 2. Cargar Productos (Cache Compartido)
            if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
                this.productosData = window.AppState.sharedData.productos;
                console.log('✅ [Inyeccion] Usando productos del cache compartido:', this.productosData.length);
            } else {
                console.warn('⚠️ [Inyeccion] Cache vacío, intentando fetch...');
                const prods = await fetchData('/api/productos/listar');
                this.productosData = prods?.productos || prods?.items || (Array.isArray(prods) ? prods : []);
            }

            // 3. Cargar Máquinas
            const maquinas = await fetchData('/api/obtener_maquinas');
            this.actualizarSelect('maquina-inyeccion', maquinas);

            mostrarLoading(false);
        } catch (error) {
            console.error('Error [Inyeccion] cargarDatos:', error);
            mostrarLoading(false);
        }
    },

    actualizarSelect: function (id, datos) {
        const select = document.getElementById(id);
        if (!select) return;
        select.innerHTML = '<option value="">-- Seleccionar --</option>';
        if (datos) {
            datos.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item;
                opt.textContent = item;
                select.appendChild(opt);
            });
        }
    },

    intentarAutoSeleccionarResponsable: function () {
        const input = document.getElementById('responsable-inyeccion');
        if (!input) return;

        let nombreUsuario = null;

        if (window.AppState?.user?.name) {
            nombreUsuario = window.AppState.user.name;
        } else if (window.AuthModule?.currentUser?.nombre) {
            nombreUsuario = window.AuthModule.currentUser.nombre;
        }

        if (nombreUsuario) {
            input.value = nombreUsuario;
            console.log(`✅ [Inyeccion] Responsable auto-asignado: ${nombreUsuario}`);
        } else {
            console.log('⏳ [Inyeccion] Esperando usuario para auto-asignación...');
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
        const input = document.getElementById('codigo-producto-inyeccion');
        const suggestionsDiv = document.getElementById('inyeccion-producto-suggestions');

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
                    this.autocompletarCodigoEnsamble(input.value);
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
        const input = document.getElementById('responsable-inyeccion');
        const suggestionsDiv = document.getElementById('inyeccion-responsable-suggestions');

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

    autocompletarCodigoEnsamble: async function (codigoProducto) {
        const codigoEnsambleField = document.getElementById('codigo-ensamble-inyeccion');
        if (!codigoProducto || !codigoEnsambleField) return;

        try {
            codigoEnsambleField.value = 'Buscando...';
            codigoEnsambleField.classList.add('loading');

            const response = await fetch(`/api/inyeccion/ensamble_desde_producto?codigo=${encodeURIComponent(codigoProducto)}`);
            const data = await response.json();

            if (data.success && data.codigo_ensamble) {
                codigoEnsambleField.value = data.codigo_ensamble;
            } else {
                codigoEnsambleField.value = '';
            }
        } catch (error) {
            console.error('Error [Inyeccion] buscando ensamble:', error);
            codigoEnsambleField.value = codigoProducto;
        } finally {
            codigoEnsambleField.classList.remove('loading');
        }
    },

    configurarEventos: function () {
        const form = document.getElementById('form-inyeccion');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.registrar();
            };
        }

        const btnDefectos = document.getElementById('btn-defectos-inyeccion');
        if (btnDefectos) {
            btnDefectos.replaceWith(btnDefectos.cloneNode(true));
            const newBtn = document.getElementById('btn-defectos-inyeccion');
            newBtn.onclick = () => {
                if (typeof window.abrirModalInyeccion === 'function') {
                    window.abrirModalInyeccion();
                }
            };
        }

        ['cantidad-inyeccion', 'cavidades-inyeccion', 'pnc-inyeccion', 'cantidad-real-inyeccion'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => this.calculos());
        });
    },

    calculos: function () {
        const disparos = parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0;
        const cavidades = parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1;
        const pnc = parseInt(document.getElementById('pnc-inyeccion')?.value) || 0;
        const manualReal = parseInt(document.getElementById('cantidad-real-inyeccion')?.value) || 0;

        const produccionTeorica = disparos * cavidades;

        // Si hay manual, esa es la "Real Reportada". Si no, es la teorica.
        const produccionFinal = manualReal > 0 ? manualReal : produccionTeorica;
        const piezasBuenas = Math.max(0, produccionFinal - pnc);

        const displayProduccion = document.getElementById('produccion-calculada');
        const displayFormula = document.getElementById('formula-calc');
        const displayBuenas = document.getElementById('piezas-buenas');

        if (displayProduccion) {
            displayProduccion.textContent = piezasBuenas.toLocaleString();
        }

        if (displayFormula) {
            if (manualReal > 0) {
                const diff = manualReal - produccionTeorica;
                const sign = diff >= 0 ? '+' : '';
                const color = diff >= 0 ? '#4ade80' : '#f87171'; // Green or Red
                displayFormula.innerHTML = `
                    Teórica: <b>${produccionTeorica}</b> | 
                    Real: <b>${manualReal}</b>
                    <span style="color: ${color}; font-weight: bold; margin-left:8px;">(${sign}${diff})</span>
                `;
            } else {
                displayFormula.textContent = `Disparos: ${disparos} × Cavidades: ${cavidades} = ${produccionTeorica} (Teórica)`;
            }
        }

        if (displayBuenas) {
            if (pnc > 0) {
                displayBuenas.textContent = `${produccionFinal} (Bruto) - PNC: ${pnc} = ${piezasBuenas} piezas buenas`;
                displayBuenas.style.display = 'block';
            } else {
                // Si no hay PNC, mostramos mensaje confirmando que todas son buenas
                displayBuenas.textContent = `${piezasBuenas} piezas buenas`;
                displayBuenas.style.display = 'block';
            }
        }
    },

    registrar: async function () {
        const btn = document.querySelector('#form-inyeccion button[type="submit"]');

        try {
            if (window.TouchFeedback && btn) TouchFeedback.setButtonLoading(btn, true);
            mostrarLoading(true);

            const disparos = parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0;
            const cavidades = parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1;
            const pnc = parseInt(document.getElementById('pnc-inyeccion')?.value) || 0;
            const manualReal = parseInt(document.getElementById('cantidad-real-inyeccion')?.value) || 0;

            const produccionTeorica = disparos * cavidades;
            // Si hay input manual > 0, es la verdad. Si no, usamos la teorica.
            const cantidadRealBruta = manualReal > 0 ? manualReal : produccionTeorica;

            // Cantidad Real REPORTADA al backend (para stock y reporte) es la bruta
            // El backend resta el PNC para "piezas buenas" si es necesario, O nosotros mandamos bruto.
            // Segun backend: piezas_buenas = max(0, cantidad_final_reportada - pnc)
            // Asi que mandamos la bruta.

            const datos = {
                fecha_inicio: document.getElementById('fecha-inyeccion')?.value || '',
                maquina: document.getElementById('maquina-inyeccion')?.value || '',
                responsable: document.getElementById('responsable-inyeccion')?.value || '',
                codigo_producto: document.getElementById('codigo-producto-inyeccion')?.value || '',
                no_cavidades: cavidades,
                disparos: disparos,
                hora_llegada: document.getElementById('hora-llegada-inyeccion')?.value || '',
                hora_inicio: document.getElementById('hora-inicio-inyeccion')?.value || '',
                hora_termina: document.getElementById('hora-termina-inyeccion')?.value || '',
                cantidad_real: cantidadRealBruta, // ENVIO LA MANUAL O LA TEORICA
                almacen_destino: document.getElementById('almacen-destino-inyeccion')?.value || '',
                codigo_ensamble: document.getElementById('codigo-ensamble-inyeccion')?.value || '',
                orden_produccion: document.getElementById('orden-produccion-inyeccion')?.value || '',
                observaciones: document.getElementById('observaciones-inyeccion')?.value || '',
                peso_vela_maquina: parseFloat(document.getElementById('peso-vela-inyeccion')?.value) || 0,
                peso_bujes: parseFloat(document.getElementById('peso-bujes-inyeccion')?.value) || 0,
                pnc: pnc,
                criterio_pnc: document.getElementById('criterio-pnc-hidden-inyeccion')?.value || ''
            };

            if (!datos.codigo_producto) {
                mostrarNotificacion('⚠️ Falta código de producto', 'error');
                mostrarLoading(false);
                return;
            }

            console.log('📤 [Inyeccion] ENVIANDO:', datos);

            const response = await fetch('/api/inyeccion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });

            const resultado = await response.json();

            if (response.ok && resultado.success) {
                // Preparar datos para restauración en caso de Undo
                const datosRestaurar = { ...datos };
                const metaConCallback = {
                    ...resultado.undo_meta,
                    restoreCallback: () => {
                        // Restaurar valores PRINCIPALES
                        document.getElementById('fecha-inyeccion').value = datosRestaurar.fecha_inicio;
                        document.getElementById('responsable-inyeccion').value = datosRestaurar.responsable;
                        document.getElementById('maquina-inyeccion').value = datosRestaurar.maquina; // Restaurar Maquina

                        // Horarios
                        document.getElementById('hora-llegada-inyeccion').value = datosRestaurar.hora_llegada; // Restaurar Llegada
                        document.getElementById('hora-inicio-inyeccion').value = datosRestaurar.hora_inicio;
                        document.getElementById('hora-termina-inyeccion').value = datosRestaurar.hora_termina;

                        // Producto y Producción
                        document.getElementById('codigo-producto-inyeccion').value = datosRestaurar.codigo_producto;
                        document.getElementById('cavidades-inyeccion').value = datosRestaurar.no_cavidades;
                        document.getElementById('cantidad-inyeccion').value = datosRestaurar.disparos;
                        document.getElementById('cantidad-real-inyeccion').value = datosRestaurar.cantidad_real;

                        // PNC
                        document.getElementById('pnc-inyeccion').value = datosRestaurar.pnc;
                        document.getElementById('criterio-pnc-hidden-inyeccion').value = datosRestaurar.criterio_pnc;

                        // Logística (Almacén, OP, Ensamble)
                        document.getElementById('almacen-destino-inyeccion').value = datosRestaurar.almacen_destino;
                        document.getElementById('codigo-ensamble-inyeccion').value = datosRestaurar.codigo_ensamble;
                        document.getElementById('orden-produccion-inyeccion').value = datosRestaurar.orden_produccion;

                        // Pesos
                        document.getElementById('peso-vela-inyeccion').value = datosRestaurar.peso_vela_maquina;
                        document.getElementById('peso-bujes-inyeccion').value = datosRestaurar.peso_bujes;
                        document.getElementById('observaciones-inyeccion').value = datosRestaurar.observaciones;

                        // Re-calcular
                        if (ModuloInyeccion.calculos) ModuloInyeccion.calculos();
                        mostrarNotificacion('Formulario completo restaurado', 'info');
                    }
                };

                mostrarNotificacion('Registro exitoso', 'success', metaConCallback);
                document.getElementById('form-inyeccion').reset();
                document.getElementById('cavidades-inyeccion').value = 1;
                document.getElementById('pnc-inyeccion').value = 0;
                document.getElementById('cantidad-real-inyeccion').value = ''; // Reset Manual Input
                this.calculos();
            } else {
                mostrarNotificacion(resultado.error || 'Error', 'error');
            }

        } catch (e) {
            console.error('Error [Inyeccion] registrar:', e);
            mostrarNotificacion(e.message, 'error');
        } finally {
            mostrarLoading(false);
            if (window.TouchFeedback && btn) TouchFeedback.setButtonLoading(btn, false);
        }
    },

    // Alias para compatibilidad
    inicializar: function () {
        return this.init();
    }
};

// Exportación global
window.ModuloInyeccion = ModuloInyeccion;
window.initInyeccion = () => ModuloInyeccion.init();
