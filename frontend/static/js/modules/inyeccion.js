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

        // Configurar Smart Enter
        if (window.ModuloUX && window.ModuloUX.setupSmartEnter) {
            window.ModuloUX.setupSmartEnter({
                inputIds: [
                    'fecha-inyeccion', 'maquina-inyeccion', 'responsable-inyeccion',
                    'hora-llegada-inyeccion', 'hora-inicio-inyeccion', 'hora-termina-inyeccion',
                    'peso-vela-inyeccion', 'orden-produccion-inyeccion',
                    'codigo-producto-inyeccion', 'cavidades-inyeccion', 'cantidad-inyeccion',
                    'cantidad-real-inyeccion', 'pnc-inyeccion', 'peso-bujes-inyeccion', 'observaciones-inyeccion'
                ],
                actionBtnId: 'btn-agregar-inyeccion',
                autocomplete: {
                    inputId: 'codigo-producto-inyeccion',
                    suggestionsId: 'inyeccion-producto-suggestions'
                }
            });

            // Autocomplete para responsable
            window.ModuloUX.setupSmartEnter({
                inputIds: ['responsable-inyeccion'],
                autocomplete: {
                    inputId: 'responsable-inyeccion',
                    suggestionsId: 'inyeccion-responsable-suggestions'
                }
            });
        }

        // Registrar persistencia de formulario Juan Sebastian Request
        if (window.FormHelpers) {
            window.FormHelpers.registrarPersistencia('form-inyeccion');
        }
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

            // 1.5 Cargar pendientes de validacion
            await this.cargarPendientesValidacion();

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

    pendientesData: [], // Store the raw data from backend

    formatearFechaParaInput: function (fechaStr) {
        if (!fechaStr) return '';
        // DD/MM/YYYY -> YYYY-MM-DD
        const parts = fechaStr.split('/');
        if (parts.length === 3) {
            return `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
        }
        return fechaStr;
    },

    formatearHoraParaInput: function (horaStr) {
        if (!horaStr) return '';
        // H:mm -> HH:mm
        const parts = horaStr.split(':');
        if (parts.length === 2) {
            return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
        }
        return horaStr;
    },

    cargarPendientesValidacion: async function () {
        try {
            const select = document.getElementById('select-validar-lote');
            if (!select) return;

            select.innerHTML = '<option value="">Cargando...</option>';
            const res = await fetchData('/api/mes/pendientes_validacion');

            select.innerHTML = '<option value="">-- Seleccionar lote a validar (o dejar vacío para registro manual) --</option>';

            if (res && res.success && res.data) {
                this.pendientesData = res.data;
                console.log(`📋 [Inyeccion] ${res.data.length} pendientes cargados:`, res.data);
                res.data.forEach(lote => {
                    // Mapeo robusto a ID (Backend usa "ID INYECCION", frontend a veces "ID_INYECCION")
                    const id = lote['ID INYECCION'] || lote['ID_INYECCION'];
                    const maquina = lote['MAQUINA'] || 'S/M';
                    const producto = lote['ID CODIGO'] || lote['CODIGO_PRODUCTO'] || lote['ID_PRODUCTO_SISTEMA'] || 'VARIOS';
                    const qty = lote['CANTIDAD REAL'] || lote['CANTIDAD_REAL_FINAL'] || lote['CANTIDAD_REAL'] || 0;

                    const opt = document.createElement('option');
                    opt.value = id;
                    opt.textContent = `[${maquina}] ${producto} - ${qty} pzs (${id})`;
                    select.appendChild(opt);
                });
            }
        } catch (err) {
            console.error("Error cargando pendientes validacion:", err);
            const select = document.getElementById('select-validar-lote');
            if (select) select.innerHTML = '<option value="">Error cargando pendientes</option>';
        }
    },

    seleccionarLoteValidacion: async function () {
        const select = document.getElementById('select-validar-lote');
        const idValidacion = select ? select.value : '';
        console.log(`🎯 [Inyeccion] Lote seleccionado ID: "${idValidacion}"`);

        if (!idValidacion) {
            console.log('🧹 [Inyeccion] No hay ID, limpiando foormulario.');
            this.limpiarFormularioValidacion();
            return;
        }

        // Búsqueda robusta del lote
        const lote = this.pendientesData.find(l => (l['ID INYECCION'] || l['ID_INYECCION']) === idValidacion);
        console.log('📦 [Inyeccion] Datos encontrados del lote:', lote);

        if (!lote) {
            console.error('❌ [Inyeccion] No se encontró el objeto de datos para este ID.');
            return;
        }

        // Extraer id_programacion para traer los SKUs (columna 24 de inyeccion es ID_PROG)
        const idProg = lote['ID_PROG'] || lote['ID_PROGRAMACION_MES'] || lote['ID_PROGRAMACION'] || lote['ID_PROGRAMACION (MES)'];
        console.log(`🔗 [Inyeccion] ID PROGRAMACION detectado: "${idProg}"`);

        if (!idProg) {
            Swal.fire('Error', 'Este lote no tiene ID de Programación asociado', 'error');
            return;
        }

        if (idProg && document.getElementById('legacy-id-programacion')) {
            document.getElementById('legacy-id-programacion').value = idProg;
        }

        // Ocultar sección de agregar producto para enfoque en validación
        const container = document.getElementById('contenedor-agregar-producto-inyeccion');
        if (container) container.classList.add('d-none');

        this.limpiarFormularioValidacion(false); // Limpiar pero no el select

        // 1. Llenar la Cabecera (Turno) - MAPEOS ROBUSTOS (Espacios vs Underscores)
        const fechaRaw = (lote['FECHA INICIA'] || lote['FECHA_INICIO'] || '').split(' ')[0];
        const fechaISO = this.formatearFechaParaInput(fechaRaw);
        console.log(`📅 [Inyeccion] Mapeando cabecera - Fecha Orig: ${fechaRaw}, ISO: ${fechaISO}`);

        if (fechaISO && document.getElementById('fecha-inyeccion')) {
            document.getElementById('fecha-inyeccion').value = fechaISO;
        }

        if (document.getElementById('maquina-inyeccion')) document.getElementById('maquina-inyeccion').value = lote['MAQUINA'] || '';
        if (document.getElementById('responsable-inyeccion')) document.getElementById('responsable-inyeccion').value = lote['RESPONSABLE'] || '';

        if (document.getElementById('hora-llegada-inyeccion')) {
            const h = lote['HORA LLEGADA'] || lote['HORA_LLEGADA'] || '';
            document.getElementById('hora-llegada-inyeccion').value = this.formatearHoraParaInput(h);
        }
        if (document.getElementById('hora-inicio-inyeccion')) {
            const h = lote['HORA INICIO'] || lote['HORA_INICIO'] || '';
            document.getElementById('hora-inicio-inyeccion').value = this.formatearHoraParaInput(h);
        }
        if (document.getElementById('hora-termina-inyeccion')) {
            const h = lote['HORA TERMINA'] || lote['HORA_TERMINA'] || '';
            document.getElementById('hora-termina-inyeccion').value = this.formatearHoraParaInput(h);
        }

        if (document.getElementById('orden-produccion-inyeccion')) document.getElementById('orden-produccion-inyeccion').value = lote['ORDEN PRODUCCION'] || lote['ORDEN_PRODUCCION'] || lote['OP'] || '';
        if (document.getElementById('peso-vela-inyeccion')) document.getElementById('peso-vela-inyeccion').value = lote['PESO VELA MAQUINA'] || lote['PESO_VELA_MAQUINA'] || 0;

        // Los cierres reportados por el operario
        const disparosBase = parseInt(lote['CONTADOR MAQ.'] || lote['CONTADOR MAQ'] || lote['DISPAROS'] || 0);
        console.log(`🔢 [Inyeccion] Disparos base detectados: ${disparosBase}`);

        // 2. Fetch de los SKUs asociados a esta Programación
        try {
            console.log(`🌐 [Inyeccion] Fetching productos para programacion: ${idProg}`);
            const dataProd = await fetchData(`/api/mes/programacion/${idProg}/productos`);
            console.log('📦 [Inyeccion] Respuesta productos:', dataProd);

            if (dataProd && dataProd.success && dataProd.productos?.length > 0) {

                // 3. Poblar la lista de agregar (simulando que Paola los agregó manually)
                for (let i = 0; i < dataProd.productos.length; i++) {
                    const p = dataProd.productos[i];

                    const cavs = parseInt(p.cavidades || 1);
                    const teorica = disparosBase * cavs;

                    // El primero hereda el ID de la cabecera para Upsert. El resto nace nuevo.
                    const idAsignado = (i === 0) ? idValidacion : undefined;

                    const nuevoItem = {
                        codigo_producto: p.codigo,
                        no_cavidades: cavs,
                        disparos: disparosBase,
                        cantidad_real: teorica, // Iniciar con la teórica para facilitar el trabajo de Paola
                        piezasBuenas: teorica,
                        manual_buenas: null,
                        pnc: 0,
                        peso_bujes: 0,
                        codigo_ensamble: '',
                        criterio_pnc: '',
                        observaciones: p.molde || '',
                        id_inyeccion: idAsignado
                    };

                    this.items.push(nuevoItem);
                }

                this.renderTablaItems();

                Swal.fire({
                    title: 'Familia de Productos Cargada',
                    text: `Se han precargado ${dataProd.productos.length} productos del ${lote['MAQUINA']}. Por favor ingrese las Buenas (Real), PNC y Peso para cada uno en la tabla y presione Guardar.`,
                    icon: 'info',
                    toast: true,
                    position: 'top-end',
                    timer: 6000,
                    showConfirmButton: false
                });

            } else {
                Swal.fire('Advertencia', 'No se encontraron productos programados para este lote.', 'warning');
            }
        } catch (error) {
            console.error('[MES] Error fetching productos asociados:', error);
            Swal.fire('Error', 'No se pudo obtener la lista de productos de este molde', 'error');
        }
    },

    limpiarFormularioValidacion: function (limpiarSelect = true) {
        if (limpiarSelect) {
            const select = document.getElementById('select-validar-lote');
            if (select) select.value = '';

            // Mostrar sección de agregar producto si es manual/limpieza
            const container = document.getElementById('contenedor-agregar-producto-inyeccion');
            if (container) container.classList.remove('d-none');
        }

        if (document.getElementById('legacy-id-inyeccion')) {
            document.getElementById('legacy-id-inyeccion').value = '';
        }
        if (document.getElementById('legacy-id-programacion')) {
            document.getElementById('legacy-id-programacion').value = '';
        }

        this.items = [];
        this.renderTablaItems();
        this.limpiarFormularioProducto();
        document.getElementById('hora-llegada-inyeccion').value = '';
        document.getElementById('hora-inicio-inyeccion').value = '';
        document.getElementById('hora-termina-inyeccion').value = '';
        document.getElementById('orden-produccion-inyeccion').value = '';
        document.getElementById('peso-vela-inyeccion').value = 0;
        this.intentarAutoSeleccionarResponsable();
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

        const legacyId = document.getElementById('legacy-id-inyeccion')?.value || '';

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
            piezasBuenas, // Solo para visualizacion
            id_inyeccion: legacyId ? legacyId : undefined // <-- INYECTAR ID AQUÍ
        };

        this.items.push(nuevoItem);
        this.renderTablaItems();
        this.limpiarFormularioProducto();

        // Limpiar el legacy ID luego de agregarlo para evitar duplicados en el mismo turno manual
        document.getElementById('legacy-id-inyeccion').value = '';

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
                    <input type="number" min="1" class="form-control form-control-sm text-center mx-auto" style="width: 60px;" value="${item.no_cavidades}" onchange="ModuloInyeccion.editarItem(${index}, 'no_cavidades', this.value)">
                </td>
                <td class="text-center align-middle">
                    <input type="number" min="1" class="form-control form-control-sm text-center mx-auto" style="width: 70px;" value="${item.disparos}" onchange="ModuloInyeccion.editarItem(${index}, 'disparos', this.value)">
                </td>
                <td class="text-center align-middle">
                    <div class="d-flex flex-column align-items-center">
                        <small class="text-muted" style="font-size: 0.65rem;">Buenas</small>
                        <input type="number" min="0" class="form-control form-control-sm text-center mx-auto fw-bold text-success border-success" style="width: 85px;" value="${item.manual_buenas !== null ? item.manual_buenas : item.piezasBuenas}" onchange="ModuloInyeccion.editarItem(${index}, 'manual_buenas', this.value)">
                    </div>
                </td>
                <td class="text-center align-middle">
                    <div class="d-flex flex-column align-items-center">
                        <small class="text-muted" style="font-size: 0.65rem;">PNC</small>
                        <div class="d-flex justify-content-center align-items-center gap-1">
                            <input type="number" min="0" class="form-control form-control-sm text-center text-danger fw-bold border-danger" style="width: 65px;" value="${item.pnc}" onchange="ModuloInyeccion.editarItem(${index}, 'pnc', this.value)">
                            <button type="button" class="btn btn-sm btn-outline-danger px-2 py-1" onclick="ModuloInyeccion.editarPNCLista(${index})"><i class="fas fa-list-ul"></i></button>
                        </div>
                    </div>
                </td>
                <td class="text-center align-middle">
                    <div class="d-flex flex-column align-items-center">
                        <small class="text-muted" style="font-size: 0.65rem;">Peso (kg)</small>
                        <input type="number" step="0.01" min="0" class="form-control form-control-sm text-center mx-auto border-primary" style="width: 80px;" value="${item.peso_bujes || 0}" onchange="ModuloInyeccion.editarItem(${index}, 'peso_bujes', this.value)">
                    </div>
                </td>
                <td class="text-center align-middle">
                    <span class="badge bg-secondary fs-6">${item.cantidad_real.toLocaleString()}</span>
                </td>
                <td class="text-center align-middle">
                    <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="ModuloInyeccion.removerItem(${index})" title="Eliminar">
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
                id_programacion: document.getElementById('legacy-id-programacion')?.value || '',
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
                document.getElementById('form-inyeccion')?.reset();
                if (window.FormHelpers) window.FormHelpers.limpiarPersistencia('form-inyeccion');
                this.intentarAutoSeleccionarResponsable();

                // Limpiar turno parcialmente (mantener maquina, fecha, responsable si se desea)
                // Usualmente se deja responsable y maquina, quizas limpiar hora.
                document.getElementById('hora-llegada-inyeccion').value = '';
                document.getElementById('peso-vela-inyeccion').value = 0;
                // document.getElementById('orden-produccion-inyeccion').value = '';  // Opcional

                this.limpiarFormularioValidacion(true);
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
