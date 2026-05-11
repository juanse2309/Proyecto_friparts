// ============================================
// ensamble.js - Sub-módulo de Programación y Reporte Flexible
// Versión RE-ESTABLECIDA: Captura Infalible de Usuario y Corrección de IDs
// ============================================

const ModuloEnsamble = {
    productosData: [],
    responsablesData: [],
    currentTab: 'programacion', 
    isManualMode: false,
    pncDetalles: '',

    inicializar: async function () {
        console.log('🔧 [Ensamble] Inicializando módulo con Captura Infalible...');
        this.configurarTabs();
        await this.cargarDatos();
        this.configurarEventos();
        
        // Autocompletes
        this.initAutocomplete('prog-producto', 'prog-producto-suggestions', true);
        this.initAutocomplete('reporte-producto-manual', 'reporte-producto-manual-suggestions', true);

        this.listarProgramacion();
        this.listarTareasPendientes();
        
        // Inicializar fecha hoy
        const hoy = new Date().toISOString().split('T')[0];
        if (document.getElementById('reporte-fecha')) document.getElementById('reporte-fecha').value = hoy;
        if (document.getElementById('prog-fecha')) document.getElementById('prog-fecha').value = hoy;

        this.intentarAutoSeleccionarResponsable();
    },

    configurarTabs: function() {
        document.querySelectorAll('#ensamble-tabs .nav-link').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.closest('.nav-link').dataset.tab);
            });
        });
    },

    switchTab: function(tabName) {
        this.currentTab = tabName;
        document.querySelectorAll('.ensamble-tab-content').forEach(el => el.style.display = 'none');
        document.getElementById(`ens-tab-${tabName}`).style.display = 'block';
        
        document.querySelectorAll('#ensamble-tabs .nav-link').forEach(el => el.classList.remove('active'));
        document.querySelector(`#ensamble-tabs .nav-link[data-tab="${tabName}"]`).classList.add('active');
        
        if (tabName === 'reporte') {
            this.listarTareasPendientes();
            this.resetFormulario(true);
        }
        if (tabName === 'programacion') this.listarProgramacion();
    },

    cargarDatos: async function () {
        try {
            mostrarLoading(true);
            if (window.AppState?.sharedData?.productos?.length > 0) {
                this.productosData = window.AppState.sharedData.productos;
            } else {
                const prods = await fetchData('/api/productos/listar');
                this.productosData = prods?.productos || prods?.items || (Array.isArray(prods) ? prods : []);
            }
            mostrarLoading(false);
        } catch (error) {
            console.error('Error cargando datos ensamble:', error);
            mostrarLoading(false);
        }
    },

    initAutocomplete: function(inputId, suggestionsId, isProduct) {
        const input = document.getElementById(inputId);
        const suggestionsDiv = document.getElementById(suggestionsId);
        if (!input || !suggestionsDiv) return;

        input.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            if (query.length < 1) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            const resultados = this.productosData.filter(p => 
                (p.codigo_sistema || '').toLowerCase().includes(query) || 
                (p.descripcion || '').toLowerCase().includes(query)
            ).slice(0, 15);
            
            renderProductSuggestions(suggestionsDiv, resultados, (item) => {
                input.value = item.codigo_sistema;
                suggestionsDiv.classList.remove('active');
                if (inputId === 'prog-producto') this.consultarBOMStock(item.codigo_sistema);
                if (inputId === 'reporte-producto-manual') this.seleccionarProductoManual(item);
            });
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    // --- VISTA NATHALIA ---
    consultarBOMStock: async function(idCodigo) {
        try {
            const res = await fetchData(`/api/ensamble/bom_stock/${idCodigo}`);
            const container = document.getElementById('prog-bom-container');
            const alertBox = document.getElementById('prog-stock-alert');
            
            if (!res || !res.success) {
                container.innerHTML = '<div class="alert alert-warning">Ficha técnica no encontrada.</div>';
                return;
            }

            const meta = parseInt(document.getElementById('prog-cantidad').value) || 0;
            let stockInsuficiente = false;

            let html = `
                <div class="table-responsive">
                    <table class="table align-middle border shadow-sm rounded-3 overflow-hidden">
                        <thead class="table-dark">
                            <tr>
                                <th class="py-3 px-3">Componente</th>
                                <th class="py-3 text-center">Stock Actual</th>
                                <th class="py-3 text-center">Capacidad Máxima</th>
                                <th class="py-3 text-center">Estado</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            res.componentes.forEach(c => {
                const isShort = c.alcanza_para < meta && meta > 0;
                if (isShort) stockInsuficiente = true;
                const rowClass = isShort ? 'table-warning bg-warning bg-opacity-25' : 'table-success bg-success bg-opacity-10';
                
                html += `
                    <tr class="${rowClass}">
                        <td class="fw-bold ps-3">${c.componente}<br><small class="text-muted">${c.codigo_inventario}</small></td>
                        <td class="text-center fw-bold fs-5 text-dark">${c.stock_almacen}</td>
                        <td class="text-center fw-bold fs-5 text-primary">${c.alcanza_para} und</td>
                        <td class="text-center">
                            <span class="badge ${isShort ? 'bg-warning text-dark' : 'bg-success'}">
                                ${isShort ? 'INSUFICIENTE' : 'OK'}
                            </span>
                        </td>
                    </tr>
                `;
            });

            html += '</tbody></table></div>';
            container.innerHTML = html;
            
            if (stockInsuficiente) {
                alertBox.innerHTML = `
                    <div class="alert border-warning bg-warning bg-opacity-10 mt-2 py-3 rounded-4">
                        <i class="fas fa-exclamation-triangle me-2"></i> Poka-Yoke: El stock resaltado no cubre la meta.
                    </div>
                `;
                alertBox.style.display = 'block';
            } else {
                alertBox.style.display = 'none';
            }
        } catch (e) { console.error(e); }
    },

    // --- FLUJO DE REPORTE ---
    renderBOMCheckboxes: async function(idCodigo, containerId) {
        try {
            const res = await fetchData(`/api/ensamble/bom_stock/${idCodigo}`);
            const container = document.getElementById(containerId);
            if (!res || !res.success) {
                container.innerHTML = '<div class="col-12 text-center text-muted">Sin BOM definido.</div>';
                return;
            }

            let html = '';
            res.componentes.forEach((c, index) => {
                html += `
                    <div class="col-md-4">
                        <div class="card border shadow-sm p-3 rounded-3 h-100">
                            <div class="form-check">
                                <input class="form-check-input bom-checkbox" type="checkbox" value="${c.codigo_inventario}" id="bom-check-${index}" checked style="width: 20px; height: 20px;">
                                <label class="form-check-label fw-bold ms-2" for="bom-check-${index}">
                                    ${c.componente}<br><small class="text-muted">${c.codigo_inventario}</small>
                                </label>
                            </div>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        } catch (e) { console.error(e); }
    },

    seleccionarTarea: function(tarea) {
        this.isManualMode = false;
        this.resetFormulario(false);
        
        document.getElementById('reporte-id-prog').value = tarea.id_prog;
        document.getElementById('reporte-producto-display').textContent = tarea.id_codigo;
        document.getElementById('reporte-producto-display').style.display = 'block';
        document.getElementById('reporte-producto-manual').value = tarea.id_codigo;
        document.getElementById('reporte-buje-origen').value = tarea.id_codigo;
        document.getElementById('reporte-cantidad').value = tarea.faltante;
        
        this.intentarAutoSeleccionarResponsable();
        this.renderBOMCheckboxes(tarea.id_codigo, 'reporte-bom-check-container');
        
        document.getElementById('form-reporte-ensamble-container').style.display = 'block';
        document.getElementById('form-reporte-ensamble-container').scrollIntoView({ behavior: 'smooth' });
    },

    seleccionarProductoManual: function(producto) {
        document.getElementById('reporte-id-prog').value = '';
        document.getElementById('reporte-producto-display').textContent = producto.codigo_sistema;
        document.getElementById('reporte-producto-display').style.display = 'block';
        document.getElementById('reporte-buje-origen').value = producto.codigo_sistema;
        
        this.intentarAutoSeleccionarResponsable();
        this.renderBOMCheckboxes(producto.codigo_sistema, 'reporte-bom-check-container');
    },

    toggleManualMode: function() {
        this.isManualMode = true;
        document.getElementById('form-reporte-ensamble-container').style.display = 'block';
        this.resetFormulario(true);
        this.intentarAutoSeleccionarResponsable();
        document.getElementById('form-reporte-ensamble-container').scrollIntoView({ behavior: 'smooth' });
    },

    reportarAvance: async function() {
        const idCodigo = document.getElementById('reporte-producto-manual').value;
        const cantidad = parseInt(document.getElementById('reporte-cantidad').value) || 0;
        const responsable = document.getElementById('responsable').value; 
        const pnc = parseInt(document.getElementById('reporte-pnc').value) || 0;
        const qty = parseFloat(document.getElementById('reporte-qty').value) || 1;

        if (!idCodigo || !cantidad || !responsable) {
            mostrarNotificacion('Faltan datos obligatorios', 'error');
            return;
        }

        if (pnc > 0 && !this.pncDetalles) {
            Swal.fire('Calidad Pendiente', 'Detalla el motivo del PNC.', 'warning');
            return;
        }

        const componentesADescontar = [];
        document.querySelectorAll('.bom-checkbox:checked').forEach(chk => {
            componentesADescontar.push(chk.value);
        });

        const payload = {
            id_prog: document.getElementById('reporte-id-prog').value || null,
            id_codigo: idCodigo,
            cantidad: cantidad,
            responsable: responsable,
            fecha: document.getElementById('reporte-fecha').value,
            hora_inicio: document.getElementById('reporte-hora-inicio').value,
            hora_fin: document.getElementById('reporte-hora-fin').value,
            buje_origen: document.getElementById('reporte-buje-origen').value,
            qty: qty,
            almacen_origen: document.getElementById('reporte-almacen-origen').value,
            almacen_destino: document.getElementById('reporte-almacen-destino').value,
            op_numero: document.getElementById('reporte-op').value,
            pnc: pnc,
            pnc_detalles: this.pncDetalles,
            observaciones: document.getElementById('reporte-observaciones').value,
            componentes_seleccionados: componentesADescontar
        };

        try {
            mostrarLoading(true);
            const res = await fetch('/api/ensamble/reportar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            mostrarLoading(false);

            if (data.success) {
                Swal.fire('¡Éxito!', 'Reporte procesado.', 'success');
                this.resetFormulario(true);
                this.listarTareasPendientes();
                this.listarProgramacion();
            } else {
                mostrarNotificacion(data.error, 'error');
            }
        } catch (e) { mostrarLoading(false); console.error(e); }
    },

    resetFormulario: function(fullReset = true) {
        if (fullReset) {
            document.getElementById('form-reporte-ensamble').reset();
            document.getElementById('reporte-id-prog').value = '';
            document.getElementById('reporte-producto-display').style.display = 'none';
            document.getElementById('reporte-bom-check-container').innerHTML = '<div class="col-12 text-center text-muted py-2">Selecciona un producto.</div>';
            this.pncDetalles = '';
            
            const hoy = new Date().toISOString().split('T')[0];
            if (document.getElementById('reporte-fecha')) document.getElementById('reporte-fecha').value = hoy;
            this.intentarAutoSeleccionarResponsable();
        }
        document.getElementById('form-reporte-ensamble-container').style.display = 'none';
    },

    abrirModalPNC: async function() {
        // 1. Cargar criterios dinámicos desde la base de datos
        await this.cargarCriteriosPNC();

        // 2. Abrir el modal global usando el destino ENSAMBLE
        if (typeof window.abrirModalInyeccion === 'function') {
            window.abrirModalInyeccion('ENSAMBLE');
        } else {
            console.error('Modal de PNC global no encontrado');
        }
    },

    cargarCriteriosPNC: async function() {
        try {
            const select = document.getElementById('crit-inyeccion');
            if (!select) return;

            // Fetch de criterios específicos de ENSAMBLE
            const response = await fetch('/api/obtener_criterios_pnc/ensamble');
            const criterios = await response.json();

            if (criterios && Array.isArray(criterios)) {
                select.innerHTML = '<option value="">Seleccionar Defecto...</option>';
                criterios.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.toUpperCase();
                    opt.textContent = c;
                    select.appendChild(opt);
                });
                console.log('✅ [Ensamble] Criterios PNC sincronizados con el servidor.');
            }
        } catch (e) {
            console.error('❌ Error cargando criterios PNC para ensamble:', e);
        }
    },

    listarTareasPendientes: async function() {
        try {
            const res = await fetchData('/api/ensamble/tareas_pendientes');
            const container = document.getElementById('tareas-pendientes-container');
            if (!res || !res.success) return;

            if (res.data.length === 0) {
                container.innerHTML = '<div class="text-center py-4 bg-light rounded-4">No hay tareas pendientes</div>';
                return;
            }

            let html = '<div class="row g-2">';
            res.data.forEach(t => {
                const porc = Math.round((t.cantidad_realizada / t.cantidad_objetivo) * 100);
                html += `
                    <div class="col-md-6 col-lg-4">
                        <div class="card shadow-sm border-0 rounded-4 hover-lift cursor-pointer bg-white" onclick="ModuloEnsamble.seleccionarTarea(${JSON.stringify(t).replace(/"/g, '&quot;')})">
                            <div class="card-body p-3">
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="badge bg-primary bg-opacity-10 text-primary rounded-pill">TAREA #${t.id_prog}</span>
                                    <small class="text-muted fw-bold">${porc}%</small>
                                </div>
                                <h5 class="fw-bold mb-1">${t.id_codigo}</h5>
                                <div class="progress mb-2" style="height: 5px;">
                                    <div class="progress-bar" style="width: ${porc}%"></div>
                                </div>
                                <p class="small text-muted mb-0">Faltan: <span class="text-danger fw-bold">${t.faltante}</span> / Objetivo: ${t.cantidad_objetivo}</p>
                            </div>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            container.innerHTML = html;
        } catch (e) { console.error(e); }
    },

    listarProgramacion: async function() {
        try {
            const res = await fetchData('/api/ensamble/programacion');
            const container = document.getElementById('prog-lista-container');
            if (!res || !res.success) return;

            let html = '<div class="p-3">';
            res.data.slice(0, 6).forEach(p => {
                const porc = Math.min(100, Math.round((p.cantidad_realizada / p.cantidad_objetivo) * 100));
                html += `
                    <div class="mb-2 p-2 border-bottom">
                        <div class="d-flex justify-content-between small">
                            <span>${p.id_codigo}</span>
                            <span>${p.cantidad_realizada}/${p.cantidad_objetivo}</span>
                        </div>
                        <div class="progress" style="height: 3px;">
                            <div class="progress-bar" style="width: ${porc}%"></div>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            container.innerHTML = html;
        } catch (e) { console.error(e); }
    },

    guardarProgramacion: async function() {
        const idCodigo = document.getElementById('prog-producto').value;
        const cantidad = document.getElementById('prog-cantidad').value;
        const fecha = document.getElementById('prog-fecha').value;
        if (!idCodigo || !cantidad || !fecha) return mostrarNotificacion('Faltan datos', 'error');

        try {
            mostrarLoading(true);
            const res = await fetch('/api/ensamble/programacion', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id_codigo: idCodigo, cantidad_objetivo: cantidad, fecha_programada: fecha })
            });
            const data = await res.json();
            mostrarLoading(false);
            if (data.success) {
                mostrarNotificacion('Meta programada', 'success');
                this.listarProgramacion();
                this.listarTareasPendientes();
            }
        } catch (e) { mostrarLoading(false); console.error(e); }
    },

    configurarEventos: function() {
        document.getElementById('btn-guardar-prog')?.addEventListener('click', () => this.guardarProgramacion());
        document.getElementById('btn-reportar-avance')?.addEventListener('click', () => this.reportarAvance());
        document.getElementById('btn-manual-mode')?.addEventListener('click', () => this.toggleManualMode());
        document.getElementById('btn-detalle-pnc')?.addEventListener('click', () => this.abrirModalPNC());
        document.getElementById('btn-cancelar-reporte')?.addEventListener('click', () => this.resetFormulario(true));
        
        document.getElementById('prog-cantidad')?.addEventListener('input', () => {
            const idCodigo = document.getElementById('prog-producto').value;
            if (idCodigo) this.consultarBOMStock(idCodigo);
        });
    },

    // --- CAPTURA INFALIBLE: Método del Input Oculto ---
    intentarAutoSeleccionarResponsable: function () {
        const input = document.getElementById('responsable'); // ID REAL corregido
        const inputDisplay = document.getElementById('responsable-display'); // Cabecera reporte
        const hiddenInput = document.getElementById('current_user_fullname'); // Fuente de verdad

        if (!input || !hiddenInput) return;

        const nombreCompleto = hiddenInput.value;

        if (nombreCompleto && nombreCompleto.trim().length > 2) {
            // Asignar al formulario
            input.value = nombreCompleto;
            input.readOnly = true;
            input.classList.add('bg-light');
            
            // Asignar a la cabecera visual (si existe)
            if (inputDisplay) {
                inputDisplay.value = nombreCompleto;
            }
            
            console.log('✅ [Ensamble] Usuario capturado infaliblemente:', nombreCompleto);
        }
    }
};

window.ModuloEnsamble = ModuloEnsamble;
window.initEnsamble = () => ModuloEnsamble.inicializar();
