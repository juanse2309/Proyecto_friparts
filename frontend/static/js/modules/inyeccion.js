// ============================================
// inyeccion.js - Lógica de Inyección (SMART SEARCH) - NAMESPACED
// ============================================

const ModuloInyeccion = {
    productosData: [],
    responsablesData: [],
    items: [],

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

        const btnAgregar = document.getElementById('btn-agregar-inyeccion');
        if (btnAgregar) {
            btnAgregar.onclick = () => this.agregarItem();
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

        // Limpiar peso vela si cambia la maquina
        const selectMaquina = document.getElementById('maquina-inyeccion');
        if (selectMaquina) {
            selectMaquina.addEventListener('change', () => {
                const pesoVela = document.getElementById('peso-vela-inyeccion');
                if (pesoVela && this.items.length === 0) {
                    pesoVela.value = 0;
                }
            });
        }

        ['cantidad-inyeccion', 'cavidades-inyeccion', 'pnc-inyeccion', 'cantidad-real-inyeccion'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => this.calculos());
        });
    },

    calculos: function () {
        const disparos = parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0;
        const cavidades = parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1;
        const pnc = parseInt(document.getElementById('pnc-inyeccion')?.value) || 0;
        const inputReal = document.getElementById('cantidad-real-inyeccion');
        const manualBuenas = parseInt(inputReal?.value) || 0;
        const isManual = inputReal?.value !== '';

        const produccionTeorica = disparos * cavidades;
        const piezasBuenas = isManual ? manualBuenas : Math.max(0, produccionTeorica - pnc);
        const produccionBrutaReal = isManual ? (manualBuenas + pnc) : produccionTeorica;

        const displayProduccion = document.getElementById('produccion-calculada');
        const displayFormula = document.getElementById('formula-calc');
        const displayBuenas = document.getElementById('piezas-buenas');

        if (displayProduccion) {
            displayProduccion.textContent = piezasBuenas.toLocaleString();
        }

        if (displayFormula) {
            if (isManual) {
                const diff = produccionBrutaReal - produccionTeorica;
                const sign = diff >= 0 ? '+' : '';
                const color = diff >= 0 ? '#4ade80' : '#f87171';
                displayFormula.innerHTML = `Teórica: <b>${produccionTeorica}</b> | Bruto (Buenas+PNC): <b>${produccionBrutaReal}</b> <span style="color: ${color}; font-weight: bold; margin-left:8px;">(${sign}${diff})</span>`;
            } else {
                displayFormula.textContent = `Disparos: ${disparos} × Cavidades: ${cavidades} = ${produccionTeorica} (Teórica)`;
            }
        }

        if (displayBuenas) {
            displayBuenas.textContent = `Buenas: ${piezasBuenas} | PNC: ${pnc}`;
        }
    },

    agregarItem: function () {
        const codigo_producto = document.getElementById('codigo-producto-inyeccion')?.value || '';
        const cavidades = parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1;
        const disparos = parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0;
        const inputReal = document.getElementById('cantidad-real-inyeccion');
        const manualBuenas = parseInt(inputReal?.value) || 0;
        const isManual = inputReal?.value !== '';

        if (!codigo_producto) {
            Swal.fire('Atención', 'Ingresa un código de producto', 'warning');
            return;
        }
        if (disparos <= 0) {
            Swal.fire('Atención', 'Los disparos deben ser mayor a 0', 'warning');
            return;
        }

        const pnc = parseInt(document.getElementById('pnc-inyeccion')?.value) || 0;
        const criterio_pnc = document.getElementById('criterio-pnc-hidden-inyeccion')?.value || '';

        const codigo_ensamble = document.getElementById('codigo-ensamble-inyeccion')?.value || '';
        const peso_bujes = parseFloat(document.getElementById('peso-bujes-inyeccion')?.value) || 0;
        const observaciones = document.getElementById('observaciones-inyeccion')?.value || '';

        const produccionTeorica = disparos * cavidades;
        const piezasBuenas = isManual ? manualBuenas : Math.max(0, produccionTeorica - pnc);
        const cantidadRealBruta = isManual ? (manualBuenas + pnc) : produccionTeorica;

        const nuevoItem = {
            id_item: Date.now().toString() + Math.random().toString(36).substr(2, 5),
            codigo_producto,
            no_cavidades: cavidades,
            disparos,
            cantidad_real: cantidadRealBruta,
            manual_buenas: isManual ? manualBuenas : null,
            pnc,
            criterio_pnc,
            codigo_ensamble,
            peso_bujes,
            observaciones,
            piezasBuenas // Solo para visualizacion
        };

        this.items.push(nuevoItem);
        this.renderTablaItems();
        this.limpiarFormularioProducto();
        Swal.fire({
            title: 'Agregado',
            text: 'Producto agregado a la lista',
            icon: 'success',
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 2000
        });
    },

    removerItem: function (index) {
        Swal.fire({
            title: '¿Eliminar producto?',
            text: "Se quitará de la lista actual.",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                this.items.splice(index, 1);
                this.renderTablaItems();
            }
        });
    },

    editarItem: function (index, campo, valor) {
        const item = this.items[index];
        if (!item) return;

        let val = parseFloat(valor);
        if (isNaN(val) || val < 0) val = 0;

        if (campo === 'manual_buenas') {
            item.manual_buenas = valor === '' ? null : val;
        } else {
            item[campo] = val;
        }

        const produccionTeorica = item.disparos * item.no_cavidades;

        if (item.manual_buenas !== null) {
            item.piezasBuenas = item.manual_buenas;
            item.cantidad_real = item.manual_buenas + item.pnc;
        } else {
            item.cantidad_real = produccionTeorica;
            item.piezasBuenas = Math.max(0, produccionTeorica - item.pnc);
        }

        this.renderTablaItems();
    },

    editarPNCLista: async function (index) {
        const item = this.items[index];

        const { value: formValues } = await Swal.fire({
            title: 'Reportar PNC',
            html: `
                <div class="mb-3 text-start">
                    <label class="form-label fw-bold">Cantidad PNC</label>
                    <input type="number" id="swal-pnc-qty" class="form-control" min="0" value="${item.pnc}">
                </div>
                <div class="text-start">
                    <label class="form-label fw-bold">Criterio (Opcional)</label>
                    <select id="swal-pnc-crit" class="form-select">
                        <option value="">Selecciona un motivo...</option>
                        <option value="Manchas" ${item.criterio_pnc === 'Manchas' ? 'selected' : ''}>Manchas</option>
                        <option value="Incompleta" ${item.criterio_pnc === 'Incompleta' ? 'selected' : ''}>Incompleta</option>
                        <option value="Rebaba" ${item.criterio_pnc === 'Rebaba' ? 'selected' : ''}>Rebaba</option>
                        <option value="Quemada" ${item.criterio_pnc === 'Quemada' ? 'selected' : ''}>Quemada</option>
                        <option value="Hundimiento" ${item.criterio_pnc === 'Hundimiento' ? 'selected' : ''}>Hundimiento</option>
                        <option value="Chupon" ${item.criterio_pnc === 'Chupon' ? 'selected' : ''}>Chupón</option>
                        <option value="Retenida" ${item.criterio_pnc === 'Retenida' ? 'selected' : ''}>Retenida en Molde</option>
                        <option value="Contaminacion" ${item.criterio_pnc === 'Contaminacion' ? 'selected' : ''}>Contaminación</option>
                        <option value="Troquelado" ${item.criterio_pnc === 'Troquelado' ? 'selected' : ''}>Mal Troquelado</option>
                        <option value="Color" ${item.criterio_pnc === 'Color' ? 'selected' : ''}>Problema Color</option>
                        <option value="Otro" ${item.criterio_pnc === 'Otro' ? 'selected' : ''}>Otro</option>
                    </select>
                </div>
            `,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonText: 'Guardar PNC',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                return {
                    qty: parseInt(document.getElementById('swal-pnc-qty').value) || 0,
                    crit: document.getElementById('swal-pnc-crit').value
                }
            }
        });

        if (formValues) {
            item.pnc = formValues.qty;
            item.criterio_pnc = formValues.crit;
            // Forzar actualización
            this.editarItem(index, 'pnc', formValues.qty);
        }
    },

    limpiarFormularioProducto: function () {
        document.getElementById('codigo-producto-inyeccion').value = '';
        document.getElementById('cavidades-inyeccion').value = 1;
        // document.getElementById('cantidad-inyeccion').value = ''; // No limpiar, se mantiene por máquina
        document.getElementById('cantidad-real-inyeccion').value = '';
        document.getElementById('pnc-inyeccion').value = 0;
        document.getElementById('criterio-pnc-hidden-inyeccion').value = '';
        document.getElementById('codigo-ensamble-inyeccion').value = '';
        document.getElementById('peso-bujes-inyeccion').value = 0;
        document.getElementById('observaciones-inyeccion').value = '';
        this.calculos();
        document.getElementById('codigo-producto-inyeccion').focus();
    },

    renderTablaItems: function () {
        const tbody = document.getElementById('lista-inyeccion-body');
        const tfoot = document.getElementById('inyeccion-tfoot');

        if (!tbody) return;

        if (this.items.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted py-5">
                        <i class="fas fa-box-open mb-3" style="font-size: 2rem; color: #cbd5e1;"></i>
                        <p class="mb-0">No hay productos en la lista.</p>
                        <small>Llena la sección de Agregar Producto y presiona "+ Agregar Producto".</small>
                    </td>
                </tr>
            `;
            if (tfoot) tfoot.style.display = 'none';
            return;
        }

        let totalBuenas = 0;
        let totalPNC = 0;
        let totalBruto = 0;

        tbody.innerHTML = this.items.map((item, index) => {
            totalBuenas += item.piezasBuenas;
            totalPNC += item.pnc;
            totalBruto += item.cantidad_real;

            return `
            <tr>
                <td class="fw-bold align-middle">${item.codigo_producto}</td>
                <td class="text-center align-middle">
                    <input type="number" min="1" class="form-control form-control-sm text-center mx-auto" style="width: 70px;" value="${item.no_cavidades}" onchange="ModuloInyeccion.editarItem(${index}, 'no_cavidades', this.value)">
                </td>
                <td class="text-center align-middle">
                    <input type="number" min="1" class="form-control form-control-sm text-center mx-auto" style="width: 90px;" value="${item.disparos}" onchange="ModuloInyeccion.editarItem(${index}, 'disparos', this.value)">
                </td>
                <td class="text-center align-middle">
                    <input type="number" min="0" class="form-control form-control-sm text-center mx-auto fw-bold text-success" style="width: 90px;" value="${item.manual_buenas !== null ? item.manual_buenas : ''}" onchange="ModuloInyeccion.editarItem(${index}, 'manual_buenas', this.value)" placeholder="Teórica">
                </td>
                <td class="text-center align-middle">
                    <div class="d-flex justify-content-center align-items-center gap-1">
                        <input type="number" min="0" class="form-control form-control-sm text-center text-light fw-bold bg-danger border-0" style="width: 60px; cursor: pointer;" value="${item.pnc}" readonly onclick="ModuloInyeccion.editarPNCLista(${index})">
                        <button type="button" class="btn btn-sm btn-outline-danger px-2 py-1" onclick="ModuloInyeccion.editarPNCLista(${index})"><i class="fas fa-list-ul"></i></button>
                    </div>
                </td>
                <td class="text-center align-middle">
                    <span class="badge bg-secondary fs-6">${item.cantidad_real.toLocaleString()}</span>
                </td>
                <td class="text-center align-middle">
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="ModuloInyeccion.removerItem(${index})" title="Eliminar">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
            `;
        }).join('');

        if (tfoot) {
            tfoot.style.display = 'table-footer-group';
            document.getElementById('inyeccion-total-buenas').textContent = totalBuenas.toLocaleString();
            document.getElementById('inyeccion-total-pnc').textContent = totalPNC.toLocaleString();
            const brutoFooter = document.getElementById('inyeccion-total-bruto');
            if (brutoFooter) brutoFooter.textContent = totalBruto.toLocaleString();
        }
    },

    registrar: async function () {
        if (this.items.length === 0) {
            Swal.fire('Advertencia', 'Agrega al menos un producto a la lista', 'warning');
            return;
        }

        const btn = document.querySelector('#form-inyeccion button[type="submit"]');

        try {
            if (window.TouchFeedback && btn) TouchFeedback.setButtonLoading(btn, true);
            mostrarLoading(true);

            // Datos comunes de turno
            const datosTurno = {
                fecha_inicio: document.getElementById('fecha-inyeccion')?.value || '',
                maquina: document.getElementById('maquina-inyeccion')?.value || '',
                responsable: document.getElementById('responsable-inyeccion')?.value || '',
                hora_llegada: document.getElementById('hora-llegada-inyeccion')?.value || '',
                hora_inicio: document.getElementById('hora-inicio-inyeccion')?.value || '',
                hora_termina: document.getElementById('hora-termina-inyeccion')?.value || '',
                orden_produccion: document.getElementById('orden-produccion-inyeccion')?.value || '',
                peso_vela_maquina: parseFloat(document.getElementById('peso-vela-inyeccion')?.value) || 0,
                almacen_destino: 'POR PULIR' // Hardcoded as requested
            };

            if (!datosTurno.maquina || !datosTurno.responsable) {
                Swal.fire('Atención', 'Faltan datos del turno (Responsable o Máquina)', 'warning');
                mostrarLoading(false);
                return;
            }

            // Unir datos de turno con cada item iterado
            const payload = {
                turno: datosTurno,
                items: this.items
            };

            console.log('📤 [Inyeccion] ENVIANDO LOTE:', payload);

            const response = await fetch('/api/inyeccion/lote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const resultado = await response.json();

            if (response.ok && resultado.success) {
                Swal.fire({
                    title: '¡Registrado!',
                    text: `Lote de ${this.items.length} productos procesado correctamente`,
                    icon: 'success',
                    timer: 2000,
                    showConfirmButton: false
                });

                // Reiniciar todo
                this.items = [];
                this.renderTablaItems();

                // Limpiar turno parcialmente (mantener maquina, fecha, responsable si se desea)
                // Usualmente se deja responsable y maquina, quizas limpiar hora.
                document.getElementById('hora-llegada-inyeccion').value = '';
                document.getElementById('hora-inicio-inyeccion').value = '';
                document.getElementById('hora-termina-inyeccion').value = '';
                document.getElementById('peso-vela-inyeccion').value = 0;
                // document.getElementById('orden-produccion-inyeccion').value = '';  // Opcional

                this.limpiarFormularioProducto();
                this.intentarAutoSeleccionarResponsable();
            } else {
                Swal.fire('Error', resultado.error || 'Error procesando lote', 'error');
            }

        } catch (e) {
            console.error('Error [Inyeccion] registrar lote:', e);
            Swal.fire('Error de Conexión', e.message, 'error');
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
