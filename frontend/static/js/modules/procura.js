// ============================================
// procura.js - Módulo de Gestión de Procura
// ============================================

const ModuloProcura = {
    parametrosData: [],
    proveedoresData: [],
    itemsOC: [],

    initAutocompleteProveedor: function () {
        const input = document.getElementById('proveedor-oc');
        const suggestionsDiv = document.getElementById('procura-proveedor-suggestions');
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
                const resultados = this.proveedoresData.filter(p =>
                    (p.nombre || '').toLowerCase().includes(query)
                ).slice(0, 10);

                if (resultados.length > 0) {
                    suggestionsDiv.innerHTML = resultados.map(p => `
                        <div class="suggestion-item p-2 border-bottom" style="cursor:pointer">
                            <strong>${p.nombre}</strong><br>
                            <small class="text-muted">${p.nit || ''}</small>
                        </div>
                    `).join('');

                    suggestionsDiv.querySelectorAll('.suggestion-item').forEach((div, idx) => {
                        div.onclick = () => {
                            input.value = resultados[idx].nombre;
                            suggestionsDiv.classList.remove('active');
                        };
                    });
                    suggestionsDiv.classList.add('active');
                } else {
                    suggestionsDiv.classList.remove('active');
                }
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    inicializar: async function () {
        console.log('📦 [Procura] Inicializando módulo...');
        await Promise.all([this.cargarParametros(), this.cargarProveedores()]);

        this.configurarEventos();
        this.initAutocompleteProducto();
        this.initAutocompleteProveedor();

        if (window.ModuloUX && window.ModuloUX.setupSmartEnter) {
            // Cabecera principal
            window.ModuloUX.setupSmartEnter({
                inputIds: ['fecha-solicitud-oc', 'n-oc', 'proveedor-oc', 'codigo-producto-oc'],
                autocomplete: {
                    inputId: 'proveedor-oc',
                    suggestionsId: 'procura-proveedor-suggestions'
                }
            });

            // Formulario de items recurrentes
            window.ModuloUX.setupSmartEnter({
                inputIds: ['codigo-producto-oc', 'cantidad-oc'],
                actionBtnId: 'btn-agregar-oc',
                autocomplete: {
                    inputId: 'codigo-producto-oc',
                    suggestionsId: 'procura-producto-suggestions'
                }
            });
        }

        // Inicializar ventana limpia de nueva orden
        this.nuevaOrden(false);

        // Cargar prioridades de rotación consolidadas
        if (window.ModuloRotacion && window.ModuloRotacion.cargarPrioridades) {
            window.ModuloRotacion.cargarPrioridades();
        }
    },

    cargarParametros: async function () {
        try {
            mostrarLoading(true);
            const response = await fetch('/api/procura/listar_parametros');
            const data = await response.json();

            if (data.status === 'success') {
                this.parametrosData = data.data;
                console.log(`[Procura] Parametros cargados: ${this.parametrosData.length} items`);
            } else {
                console.warn('⚠️ [Procura] Error cargando parámetros:', data.message);
                Swal.fire('Error', 'No se pudieron cargar los parámetros de inventario', 'error');
            }
        } catch (error) {
            console.error('Error [Procura] fetching parametros:', error);
            Swal.fire('Error de conexión', 'No se pudo contactar al servidor', 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    cargarProveedores: async function () {
        try {
            const response = await fetch('/api/procura/listar_proveedores');
            const data = await response.json();
            if (data.status === 'success') {
                this.proveedoresData = data.data;
                console.log(`✅ [Procura] Proveedores cargados: ${this.proveedoresData.length}`);
                this.renderDirectorioProveedores(this.proveedoresData);
            }
        } catch (error) {
            console.error('Error [Procura] fetching proveedores:', error);
        }
    },

    renderDirectorioProveedores: function (proveedores) {
        const grid = document.getElementById('proveedores-grid');
        const counter = document.getElementById('counter-proveedores');
        if (!grid) return;

        if (counter) counter.textContent = `${proveedores.length} Proveedores`;

        if (proveedores.length === 0) {
            grid.innerHTML = `
                <div class="col-12 text-center py-5">
                    <div class="p-4 bg-white rounded shadow-sm border">
                        <i class="fas fa-search-minus fa-3x text-muted mb-3"></i>
                        <h5>No se encontraron proveedores</h5>
                        <p class="text-muted">Prueba con otros términos de búsqueda.</p>
                    </div>
                </div>
            `;
            return;
        }

        grid.innerHTML = proveedores.map(p => {
            // Lógica de color para evaluación
            let evalColor = 'bg-secondary';
            const score = parseInt(p.evaluacion) || 0;
            if (score >= 90) evalColor = 'bg-success';
            else if (score >= 70) evalColor = 'bg-primary';
            else if (score >= 50) evalColor = 'bg-warning text-dark';
            else if (score > 0) evalColor = 'bg-danger';

            return `
                <div class="col-12 col-md-6 col-lg-4 col-xl-3">
                    <div class="supplier-card shadow-sm border h-100">
                        <div class="supplier-header d-flex justify-content-between align-items-start">
                            <div>
                                <h6 class="supplier-name" title="${p.nombre}">${p.nombre}</h6>
                                <small class="text-muted" style="font-size: 0.75rem;">NIT: ${p.nit || 'N/A'}</small>
                            </div>
                            <span class="badge ${evalColor} eval-badge rounded-pill shadow-sm">${p.evaluacion || 'N/E'}</span>
                        </div>
                        <div class="supplier-body">
                            <div class="mb-3">
                                <span class="supplier-badge proceso-tag d-inline-block mb-2" title="Proceso Principal">
                                    <i class="fas fa-microchip me-1"></i> ${p.proceso || 'No especificado'}
                                </span>
                            </div>
                            <div class="supplier-info-item">
                                <i class="fas fa-user-tie"></i>
                                <span class="text-truncate" title="${p.contacto}">${p.contacto || 'Sin contacto'}</span>
                            </div>
                            <div class="supplier-info-item">
                                <i class="fas fa-phone-alt"></i>
                                <span>${p.telefono || 'Sin teléfono'}</span>
                            </div>
                            <div class="supplier-info-item">
                                <i class="fas fa-envelope"></i>
                                <span class="text-truncate" title="${p.correo}">${p.correo || 'Sin correo'}</span>
                            </div>
                            <div class="supplier-info-item mt-2 pt-2 border-top">
                                <i class="fas fa-credit-card"></i>
                                <small class="text-muted">${p.forma_pago || 'Pago: N/D'}</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    },

    filtrarDirectorio: function (query) {
        const q = query.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();

        const filtrados = this.proveedoresData.filter(p => {
            const nombre = (p.nombre || '').toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
            const proceso = (p.proceso || '').toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
            const contacto = (p.contacto || '').toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

            return nombre.includes(q) || proceso.includes(q) || contacto.includes(q);
        });

        this.renderDirectorioProveedores(filtrados);
    },

    initAutocompleteProducto: function () {
        const input = document.getElementById('codigo-producto-oc');
        const suggestionsDiv = document.getElementById('procura-producto-suggestions');

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
                // Normalizando la query igual que en Python (sin espacios ni guiones)
                const queryNormalizada = query.replace(/[-\s]/g, "");

                const resultados = this.parametrosData.filter(prod => {
                    const descMatch = String(prod.descripcion || '').toLowerCase().includes(query);
                    const codMatch = String(prod.codigo_normalizado || '').toLowerCase().includes(queryNormalizada);
                    return descMatch || codMatch;
                }).slice(0, 15);

                this.renderProductSuggestions(suggestionsDiv, resultados, (item) => {
                    input.value = item.codigo;
                    // Guardamos la info extra del item en hidden si se ocupa
                    suggestionsDiv.classList.remove('active');
                });
            }, 300);
        });

        // El manejo de teclas (Enter y Flechas) ahora lo realiza setupSmartEnter


        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    renderProductSuggestions: function (container, items, onSelect) {
        if (items.length === 0) {
            container.innerHTML = '<div class="suggestion-item text-muted">No se encontraron componentes en maestro</div>';
            container.classList.add('active');
            return;
        }

        container.innerHTML = items.map(item => `
            <div class="suggestion-item d-flex justify-content-between align-items-center">
                <div>
                    <strong class="text-primary">${item.codigo}</strong><br>
                    <small class="text-muted text-wrap">${item.descripcion}</small>
                </div>
                <div>
                    <span class="badge bg-secondary ms-2" title="Mínimo Ideal">Min: ${item.existencia_minima}</span>
                </div>
            </div>
        `).join('');

        container.querySelectorAll('.suggestion-item').forEach((div, index) => {
            div.addEventListener('click', () => {
                onSelect(items[index]);
            });
        });

        container.classList.add('active');
    },



    configurarEventos: function () {
        const formOC = document.getElementById('form-oc');
        if (formOC) {
            formOC.onsubmit = (e) => {
                e.preventDefault();
                this.registrarOC();
            };
        }

        const btnAgregar = document.getElementById('btn-agregar-oc');
        if (btnAgregar) {
            btnAgregar.onclick = () => this.agregarItemOC();
        }
    },

    agregarItemOC: function () {
        const producto = document.getElementById('codigo-producto-oc')?.value?.trim();
        const cantidadSolicitada = parseInt(document.getElementById('cantidad-oc')?.value) || 0;
        const cantidadEnviada = parseInt(document.getElementById('cantidad-enviada-oc')?.value) || 0;

        if (!producto || (cantidadSolicitada <= 0 && cantidadEnviada <= 0)) {
            Swal.fire('Atención', 'Debes ingresar un producto válido y una cantidad (solicitada o enviada) mayor a 0', 'warning');
            return;
        }

        // Cargar datos contextuales del producto si existe en maestro para display
        const maestroMatches = this.parametrosData.filter(p => p.codigo === producto || p.codigo_normalizado === producto.replace(/[-\s]/g, "").toUpperCase());
        const descInfo = maestroMatches.length > 0 ? maestroMatches[0].descripcion : "Producto sin descripción en maestro";
        const codeFormal = maestroMatches.length > 0 ? maestroMatches[0].codigo : producto;

        const nuevoItem = {
            id_temporal: Date.now().toString(),
            fecha_solicitud: this.formatearFechaParaBD(document.getElementById('fecha-solicitud-oc')?.value),
            n_oc: document.getElementById('n-oc')?.value?.replace(/OC-/gi, "")?.trim() || '',
            proveedor: document.getElementById('proveedor-oc')?.value?.trim() || '',
            producto: codeFormal,
            descripcion: descInfo,
            cantidad: cantidadSolicitada,
            cantidad_enviada: cantidadEnviada,
            // Campos de recepción en 0 para UI por defecto
            fecha_factura: '',
            n_factura: '',
            cantidad_fact: 0,
            fecha_llegada: '',
            cantidad_recibida: 0,
            observaciones: '',
            estado_proceso: 'Normal'
        };

        if (!nuevoItem.n_oc || !nuevoItem.proveedor) {
            Swal.fire('Atención', 'El Número de O.C. y el Proveedor son obligatorios', 'warning');
            return;
        }

        // Si la OC ya tiene Items, el nuevo item DEBE coincidir en cabeceras o advertir al user
        if (this.itemsOC.length > 0) {
            const currentOCInfo = { oc: this.itemsOC[0].n_oc, prov: this.itemsOC[0].proveedor };
            if (nuevoItem.n_oc !== currentOCInfo.oc || nuevoItem.proveedor !== currentOCInfo.prov) {
                Swal.fire('Error', 'Todos los ítems de esta orden deben tener el mismo N° OC y Proveedor en esta sesión de captura.', 'error');
                return;
            }
        }

        this.itemsOC.push(nuevoItem);
        this.renderTablaOC();
        this.limpiarFormularioProductoOC();

        Swal.fire({
            title: 'Agregado',
            text: 'Componente agregado a la Orden',
            icon: 'success',
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 1500
        });
    },

    removerItemOC: function (index) {
        this.itemsOC.splice(index, 1);
        this.renderTablaOC();
    },

    limpiarFormularioProductoOC: function () {
        document.getElementById('codigo-producto-oc').value = '';
        document.getElementById('cantidad-oc').value = '';
        document.getElementById('cantidad-enviada-oc').value = '';
        document.getElementById('codigo-producto-oc').focus();
    },

    formatearFechaParaInput: function (fecha) {
        if (!fecha) return '';
        if (String(fecha).includes('-')) return fecha;
        const parts = String(fecha).split('/');
        if (parts.length === 3) {
            const day = parts[0].padStart(2, '0');
            const month = parts[1].padStart(2, '0');
            const year = parts[2].trim().split(' ')[0]; // In case there's time trailing
            return `${year}-${month}-${day}`;
        }
        return '';
    },

    formatearFechaParaBD: function (fecha) {
        if (!fecha) return '';
        if (String(fecha).includes('/')) return fecha;
        const parts = String(fecha).split('-');
        if (parts.length === 3) {
            const year = parts[0];
            const month = parts[1].padStart(2, '0');
            const day = parts[2].padStart(2, '0');
            return `${day}/${month}/${year}`;
        }
        return fecha;
    },

    renderTablaOC: function () {
        const container = document.getElementById('lista-oc-container');
        if (!container) return;

        if (this.itemsOC.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5 border rounded bg-white shadow-sm">
                    <i class="fas fa-box-open mb-3" style="font-size: 2.5rem; color: #cbd5e1;"></i>
                    <h6 class="mb-1">Sin componentes</h6>
                    <p class="mb-0 small">Agrega ítems o busca una Orden de Compra.</p>
                </div>
            `;
            return;
        }

        let tableHTML = `
        <div class="table-responsive bg-white rounded shadow-sm border mt-3" style="overflow-x: auto;">
            <table class="table table-hover table-bordered align-middle mb-0" style="min-width: 1400px; font-size: 0.85rem;">
                <thead class="bg-light">
                    <tr>
                        <th class="text-center" style="width: 40px;"><i class="fas fa-trash"></i></th>
                        <th style="min-width: 130px;">FECHA DE SOLICITUD</th>
                        <th style="min-width: 100px;">N° OC</th>
                        <th style="min-width: 120px;">PROVEEDOR</th>
                        <th style="min-width: 250px;">PRODUCTO</th>
                        <th style="min-width: 80px;" class="text-center">CANTIDAD PEDIDA</th>
                        <th style="min-width: 120px;">FECHA FACTURA</th>
                        <th style="min-width: 100px;">N° FACTURA</th>
                        <th style="min-width: 90px;" class="text-center">CANTIDAD FACTURADA</th>
                        <th style="min-width: 120px;">FECHA LLEGADA</th>
                        <th style="min-width: 90px;" class="text-center">CANTIDAD RECIBIDA</th>
                        <th style="min-width: 90px;" class="text-center">DIFERENCIA</th>
                        <th style="min-width: 200px;">OBSERVACIONES</th>
                        <th style="min-width: 100px;" class="text-center">CANT. ENVIADA (WIP)</th>
                        <th style="min-width: 220px;">ESTADO PROGRESO</th>
                    </tr>
                </thead>
                <tbody>
        `;

        tableHTML += this.itemsOC.map((item, index) => {
            const diferencia = (item.cantidad || 0) - (item.cantidad_recibida || 0);
            const diffClass = diferencia > 0 ? 'text-danger fw-bold' : (diferencia < 0 ? 'text-warning fw-bold' : 'text-success fw-bold');

            // Checkbox logic for Estado Progreso
            const estadosArr = (item.estado_proceso || 'Normal').split(',').map(s => s.trim());
            const buildCheckbox = (val, label) => {
                const isChecked = estadosArr.includes(val) ? 'checked' : '';
                return `
                    <div class="form-check form-check-inline m-0 me-2 mb-1" style="min-width: 80px;">
                        <input class="form-check-input shadow-sm" type="checkbox" id="est-${val}-${index}" value="${val}" ${isChecked} 
                               onchange="ModuloProcura.toggleEstado(${index}, '${val}', this.checked)" style="cursor: pointer;">
                        <label class="form-check-label small" for="est-${val}-${index}" style="cursor: pointer;">${label}</label>
                    </div>
                `;
            };

            return `
            <tr>
                <td class="text-center">
                    <button type="button" class="btn btn-sm btn-outline-danger shadow-sm rounded-circle" 
                            onclick="ModuloProcura.removerItemOC(${index})" title="Eliminar ítem" style="width:28px; height:28px; padding:0;">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
                <td>
                    <input type="date" class="form-control form-control-sm shadow-sm" style="border-radius: 4px;"
                           value="${ModuloProcura.formatearFechaParaInput(item.fecha_solicitud)}" 
                           onchange="ModuloProcura.updateItem(${index}, 'fecha_solicitud', this.value)">
                </td>
                <td class="fw-bold text-primary align-middle">${item.n_oc}</td>
                <td class="align-middle">${item.proveedor}</td>
                <td style="white-space: normal; word-wrap: break-word;">
                    <strong class="text-primary">${item.producto}</strong><br>
                    <small class="text-muted" style="display:block; max-width: 300px;">${item.descripcion}</small>
                </td>
                <td class="text-center fw-bold bg-primary bg-opacity-10 align-middle fs-6 text-primary">${item.cantidad || 0}</td>
                
                <!-- Recepción / Facturación -->
                <td>
                    <input type="date" class="form-control form-control-sm shadow-sm" style="border-radius: 4px;"
                           value="${ModuloProcura.formatearFechaParaInput(item.fecha_factura)}" 
                           onchange="ModuloProcura.updateItem(${index}, 'fecha_factura', this.value)">
                </td>
                <td>
                    <input type="text" class="form-control form-control-sm shadow-sm" style="border-radius: 4px;" placeholder="Opcional"
                           value="${item.n_factura || ''}" 
                           onchange="ModuloProcura.updateItem(${index}, 'n_factura', this.value)">
                </td>
                <td>
                    <input type="number" class="form-control form-control-sm shadow-sm text-center" style="border-radius: 4px;"
                           value="${item.cantidad_fact || 0}" 
                           onchange="ModuloProcura.updateItem(${index}, 'cantidad_fact', this.value)">
                </td>
                <td>
                    <input type="date" class="form-control form-control-sm shadow-sm border-success bg-success bg-opacity-10" style="border-radius: 4px;"
                           value="${ModuloProcura.formatearFechaParaInput(item.fecha_llegada)}" 
                           onchange="ModuloProcura.updateItem(${index}, 'fecha_llegada', this.value)">
                </td>
                <td>
                    <input type="number" class="form-control form-control-sm shadow-sm text-center fw-bold text-success border-success" style="border-radius: 4px; font-size:1.05rem;"
                           value="${item.cantidad_recibida || 0}" 
                           onchange="ModuloProcura.updateItem(${index}, 'cantidad_recibida', this.value)">
                </td>
                <td class="text-center align-middle bg-light" style="font-size:1.05rem;">
                    <span id="dif-text-${index}" class="${diffClass}">${diferencia}</span>
                </td>
                <td>
                    <textarea class="form-control form-control-sm shadow-sm" style="border-radius: 4px; resize: vertical;" rows="2" placeholder="Notas..."
                              onchange="ModuloProcura.updateItem(${index}, 'observaciones', this.value)">${item.observaciones || ''}</textarea>
                </td>
                <td>
                    <input type="number" class="form-control form-control-sm shadow-sm text-center fw-bold text-primary border-primary" style="border-radius: 4px;"
                           value="${item.cantidad_enviada || 0}" 
                           onchange="ModuloProcura.updateItem(${index}, 'cantidad_enviada', this.value)">
                </td>
                <td class="bg-light p-2">
                    <div class="d-flex flex-wrap">
                        ${buildCheckbox('Normal', 'Normal')}
                        ${buildCheckbox('Zincado', 'Zincado')}
                        ${buildCheckbox('Granallado', 'Granallado')}
                    </div>
                </td>
            </tr>
            `;
        }).join('');

        tableHTML += `
                </tbody>
            </table>
        </div>`;

        container.innerHTML = tableHTML;
    },

    toggleEstado: function (index, valor, isChecked) {
        if (!this.itemsOC[index]) return;

        let estadosArr = (this.itemsOC[index].estado_proceso || '').split(',').map(s => s.trim()).filter(s => s !== '');

        if (isChecked) {
            if (!estadosArr.includes(valor)) estadosArr.push(valor);
        } else {
            estadosArr = estadosArr.filter(s => s !== valor);
        }

        // Si se desselecciona todo, por defecto ponemos Normal
        if (estadosArr.length === 0) estadosArr.push('Normal');

        this.itemsOC[index].estado_proceso = estadosArr.join(', ');
    },

    updateItem: function (index, field, value) {
        if (this.itemsOC[index]) {
            let val = value;
            if (field === 'cantidad' || field === 'cantidad_recibida' || field === 'cantidad_fact' || field === 'cantidad_enviada') {
                val = parseInt(value) || 0;
            } else if (field.includes('fecha')) {
                val = this.formatearFechaParaBD(value);
            }
            this.itemsOC[index][field] = val;

            if (field === 'cantidad' || field === 'cantidad_recibida') {
                const diffSpan = document.getElementById(`dif-text-${index}`);
                if (diffSpan) {
                    const dif = (this.itemsOC[index].cantidad || 0) - (this.itemsOC[index].cantidad_recibida || 0);
                    diffSpan.textContent = dif;
                    diffSpan.className = dif > 0 ? 'text-danger fw-bold' : (dif < 0 ? 'text-warning fw-bold' : 'text-success fw-bold');
                }
            }
        }
    },

    nuevaOrden: async function (showToast = true) {
        this.itemsOC = [];
        this.renderTablaOC();

        // Asignar fecha de hoy
        const hoy = new Date().toISOString().split('T')[0];
        document.getElementById('fecha-solicitud-oc').value = hoy;

        document.getElementById('n-oc').value = 'Cargando...';
        document.getElementById('proveedor-oc').value = '';

        const buscador = document.getElementById('buscar-oc-input');
        if (buscador) buscador.value = '';

        // Obtener siguiente OC
        try {
            const resp = await fetch('/api/procura/siguiente_oc');
            const data = await resp.json();
            if (data.success) {
                document.getElementById('n-oc').value = data.siguiente_oc;
            } else {
                document.getElementById('n-oc').value = '';
            }
        } catch (e) {
            console.error(e);
            document.getElementById('n-oc').value = '';
        }

        if (showToast !== false) {
            Swal.fire({
                title: 'Nueva Orden',
                text: 'Formulario limpiado para crear una Orden de Compra.',
                icon: 'info',
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 2000
            });
        }
    },

    buscarOC: async function () {
        const inputBuscador = document.getElementById('buscar-oc-input');
        const noc = inputBuscador?.value?.trim();

        if (!noc) {
            Swal.fire('Atención', 'Ingrese un N° de Orden de Compra para buscar.', 'warning');
            return;
        }

        try {
            mostrarLoading(true);
            const response = await fetch(`/api/procura/buscar_oc/${noc}`);
            const data = await response.json();

            if (data.success && data.data.items.length > 0) {
                const items = data.data.items;
                this.itemsOC = items;

                // Rellenar cabecera con el primer item
                const primero = items[0];
                document.getElementById('fecha-solicitud-oc').value = ModuloProcura.formatearFechaParaInput(primero.fecha_solicitud) || '';
                document.getElementById('n-oc').value = primero.n_oc || '';
                document.getElementById('proveedor-oc').value = primero.proveedor || '';

                this.renderTablaOC();

                Swal.fire({
                    title: 'Encontrada',
                    text: `La Orden ${noc} se ha cargado con ${items.length} items. Puedes continuar editándola.`,
                    icon: 'success',
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 2000
                });

            } else {
                Swal.fire('No se encontró OC', data.error || 'Verifica el número ingresado.', 'info');
            }
        } catch (e) {
            console.error(e);
            Swal.fire('Error', 'Fallo al realizar la búsqueda en el servidor.', 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    registrarOC: async function () {
        if (this.itemsOC.length === 0) {
            Swal.fire('Advertencia', 'Debes agregar al menos un componente a la Orden de Compra', 'warning');
            return;
        }

        const btn = document.querySelector('#form-oc button[type="submit"]');

        try {
            if (window.TouchFeedback && btn) TouchFeedback.setButtonLoading(btn, true);
            mostrarLoading(true);

            console.log('📤 [Procura] ENVIANDO ORDEN:', this.itemsOC);

            const payload = { items: this.itemsOC };

            const response = await fetch('/api/procura/registrar_oc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const resultado = await response.json();

            if (response.ok && resultado.success) {
                Swal.fire({
                    title: '¡Orden de Compra Guardada!',
                    text: resultado.message,
                    icon: 'success',
                    timer: 2000,
                    showConfirmButton: false
                });

                // Reiniciar todo
                this.itemsOC = [];
                this.renderTablaOC();

                // Limpiar cabeceras
                document.getElementById('n-oc').value = '';
                // document.getElementById('proveedor-oc').value = ''; // Opcional mantener proveedor si compra mas al msmo
                this.limpiarFormularioProductoOC();

                // 🔄 Recargar prioridades de rotación para actualizar semáforos
                if (window.ModuloRotacion && window.ModuloRotacion.cargarPrioridades) {
                    window.ModuloRotacion.cargarPrioridades();
                }
            } else {
                Swal.fire('Error', resultado.error || 'Error procesando Orden de Compra', 'error');
            }

        } catch (e) {
            console.error('Error [Procura] registrar OC:', e);
            Swal.fire('Error', 'Fallo de Conexión al intentar guardar', 'error');
        } finally {
            mostrarLoading(false);
            if (window.TouchFeedback && btn) TouchFeedback.setButtonLoading(btn, false);
        }
    },

};

window.ModuloProcura = ModuloProcura;
window.initProcura = () => {
    ModuloProcura.inicializar();
};
