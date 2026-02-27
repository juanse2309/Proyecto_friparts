/**
 * metals.js - Módulos de Producción FRIMETALS
 * Selector de procesos + formularios específicos por máquina
 */

const ModuloMetals = {
    productosData: [],
    procesoActual: null,
    graficoTiempos: null,
    graficoDefectos: null,
    graficoOk: null,
    graficoTendencia: null,
    graficoOperarios: null,

    // ----------------------------------------------------------------
    // Mapa de procesos → máquinas + campos específicos
    // ----------------------------------------------------------------
    PAGE_MAP: {
        'metals-torno': 'TORNO',
        'metals-laser': 'CORTADORA_LASER',
        'metals-soldadura': 'SOLDADURA',
        'metals-marcadora': 'MARCADORA_LASER',
        'metals-taladro': 'TALADRO',
        'metals-dobladora': 'DOBLADORA',
        'metals-pintura': 'PINTURA',
        'metals-zincado': 'ZINCADO',
        'metals-horno': 'HORNO',
        'metals-pulido-m': 'PULIDO'
    },

    PROCESOS: {
        'TORNO': {
            label: 'Torno',
            icon: 'fa-circle-notch',
            color: '#3b82f6',
            maquinas: ['TORNO-1', 'TORNO-2', 'TORNO-3', 'TORNO-4'],
            extraFields: ''
        },
        'CORTADORA_LASER': {
            label: 'Cortadora Laser',
            icon: 'fa-bolt',
            color: '#ef4444',
            maquinas: ['CORTADORA LASER'],
            extraFields: ''
        },
        'SOLDADURA': {
            label: 'Soldadura',
            icon: 'fa-fire',
            color: '#f59e0b',
            maquinas: ['SOLDADORA-1', 'SOLDADORA-2'],
            extraFields: ''
        },
        'MARCADORA_LASER': {
            label: 'Marcadora Laser',
            icon: 'fa-crosshairs',
            color: '#8b5cf6',
            maquinas: ['MARCADORA LASER'],
            extraFields: ''
        },
        'TALADRO': {
            label: 'Taladro',
            icon: 'fa-circle',
            color: '#10b981',
            maquinas: ['TALADRO-1', 'TALADRO-2'],
            extraFields: ''
        },
        'DOBLADORA': {
            label: 'Dobladora',
            icon: 'fa-angle-left',
            color: '#06b6d4',
            maquinas: ['DOBLADORA'],
            extraFields: ''
        },
        'PINTURA': {
            label: 'Pintura',
            icon: 'fa-paint-roller',
            color: '#ec4899',
            maquinas: ['CABINA PINTURA'],
            extraFields: ''
        },
        'ZINCADO': {
            label: 'Zincado',
            icon: 'fa-shield-alt',
            color: '#64748b',
            maquinas: ['CUBA ZINCADO'],
            extraFields: `
                <div class="form-group-metals">
                    <label class="label-metals"><i class="fas fa-truck"></i> Estado de Zincado</label>
                    <select id="extra-estado-zincado" class="input-metals">
                        <option value="ENVIADO_A_PROVEEDOR">Enviado a Proveedor</option>
                        <option value="RECIBIDO_DE_PROVEEDOR">Recibido de Proveedor</option>
                    </select>
                </div>
                <div class="form-group-metals">
                    <label class="label-metals"><i class="fas fa-file-invoice"></i> N° Remisión / Guía</label>
                    <input type="text" id="extra-remision" class="input-metals" placeholder="Ej: RM-0012">
                </div>`
        },
        'HORNO': {
            label: 'Horno',
            icon: 'fa-fire-alt',
            color: '#dc2626',
            maquinas: ['HORNO-1'],
            extraFields: ''
        },
        'PULIDO': {
            label: 'Pulido',
            icon: 'fa-certificate',
            color: '#7c3aed',
            maquinas: ['PULIDORA-1'],
            extraFields: ''
        }
    },

    // ----------------------------------------------------------------
    // Inicializar
    // ----------------------------------------------------------------
    inicializar: async function () {
        console.log('🏭 [Metals] Inicializando módulo de producción...');

        // 1. Cargar productos si no están en AppState
        if (!window.AppState.sharedData.productosMetals) {
            await this.cargarProductos();
        } else {
            this.productosData = window.AppState.sharedData.productosMetals;
        }

        // 2. Detectar qué proceso mostrar según la página actual
        const paginaActual = window.AppState.paginaActual;
        console.log(`🏭 [Metals] Página actual: ${paginaActual}`);

        if (paginaActual === 'metals-dashboard') {
            this.cargarDashboard();
            return;
        }

        if (paginaActual === 'metals-produccion') {
            this.mostrarSelectorProcesos();
            return;
        }

        const procesoKey = this.PAGE_MAP[paginaActual];
        if (procesoKey) {
            this.abrirFormulario(procesoKey);
        } else {
            console.warn(`⚠️ [Metals] No hay proceso mapeado para la página: ${paginaActual}`);
            this.mostrarSelectorProcesos(); // Fallback
        }
    },

    desactivar: function () {
        // Resetear estado al salir
        this.procesoActual = null;
    },

    // ----------------------------------------------------------------
    // Selector de procesos (vista principal)
    // ----------------------------------------------------------------
    mostrarSelectorProcesos: function () {
        const contenedor = document.getElementById('metals-contenido');
        if (!contenedor) return;

        this.procesoActual = null;

        const tarjetas = Object.entries(this.PROCESOS).map(([key, proc]) => `
            <div class="metals-process-card" onclick="ModuloMetals.abrirFormulario('${key}')"
                style="border-top: 4px solid ${proc.color};">
                <div class="metals-card-icon" style="background: ${proc.color}20; color: ${proc.color};">
                    <i class="fas ${proc.icon} fa-2x"></i>
                </div>
                <div class="metals-card-label">${proc.label}</div>
                <div class="metals-card-machines">${proc.maquinas.join(' · ')}</div>
            </div>
        `).join('');

        contenedor.innerHTML = `
            <div class="metals-selector-header">
                <h2><i class="fas fa-hammer me-2"></i>Registro de Producción</h2>
                <p class="text-muted">Selecciona el proceso que realizaste</p>
            </div>
            <div class="metals-process-grid">
                ${tarjetas}
            </div>
        `;
    },

    // ----------------------------------------------------------------
    // Formulario por proceso
    // ----------------------------------------------------------------
    abrirFormulario: function (procesoKey) {
        const proc = this.PROCESOS[procesoKey];
        if (!proc) return;

        this.procesoActual = procesoKey;
        const contenedor = document.getElementById('metals-contenido');
        if (!contenedor) return;

        const maquinasOptions = proc.maquinas.map(m => `<option value="${m}">${m}</option>`).join('');
        const hoy = new Date().toISOString().split('T')[0];
        const responsable = window.AppState?.user?.name || '';

        contenedor.innerHTML = `
            <div class="metals-form-header" style="border-left: 5px solid ${proc.color}; padding-left: 16px; margin-bottom: 24px;">
                <button class="btn-back-metals" onclick="ModuloMetals.mostrarSelectorProcesos()">
                    <i class="fas fa-arrow-left me-2"></i>Volver
                </button>
                <h3 style="color: ${proc.color}; margin: 8px 0 4px;">
                    <i class="fas ${proc.icon} me-2"></i>${proc.label}
                </h3>
                <p class="text-muted small mb-0">Registrar actividad de producción</p>
            </div>

            <form id="form-metals" class="metals-form">
                <!-- Fila 1: Fecha + Responsable -->
                <div class="metals-form-grid">
                    <div class="form-group-metals">
                        <label class="label-metals"><i class="fas fa-calendar"></i> Fecha</label>
                        <input type="date" id="metals-fecha" class="input-metals" value="${hoy}" required>
                    </div>
                    <div class="form-group-metals">
                        <label class="label-metals"><i class="fas fa-user"></i> Operario</label>
                        <input type="text" id="metals-responsable" class="input-metals" value="${responsable}" readonly
                            style="background: #f1f5f9; color: #64748b; font-weight: 700;">
                    </div>
                </div>

                <!-- Fila 2: Máquina + Producto -->
                <div class="metals-form-grid">
                    <div class="form-group-metals">
                        <label class="label-metals"><i class="fas fa-cog"></i> Máquina</label>
                        <select id="metals-maquina" class="input-metals" required>
                            <option value="">-- Seleccionar --</option>
                            ${maquinasOptions}
                        </select>
                    </div>
                    <div class="form-group-metals" style="position: relative;">
                        <label class="label-metals"><i class="fas fa-box"></i> Producto (Código / Descripción)</label>
                        <input type="text" id="metals-producto" class="input-metals" autocomplete="off"
                            placeholder="Buscar código o descripción..." required>
                        <div id="metals-sugerencias" class="autocomplete-suggestions"></div>
                    </div>
                </div>

                <!-- Fila 3: Horas -->
                <div class="metals-form-grid">
                    <div class="form-group-metals">
                        <label class="label-metals"><i class="fas fa-clock"></i> Hora Inicio</label>
                        <div style="display: flex; gap: 8px;">
                            <input type="time" id="metals-hora-inicio" class="input-metals" style="flex: 1;">
                            <button type="button" class="btn-hora-metals" onclick="ModuloMetals.marcarHora('inicio')" title="Marcar ahora">
                                <i class="fas fa-stopwatch"></i>
                            </button>
                        </div>
                    </div>
                    <div class="form-group-metals">
                        <label class="label-metals"><i class="fas fa-clock"></i> Hora Fin</label>
                        <div style="display: flex; gap: 8px;">
                            <input type="time" id="metals-hora-fin" class="input-metals" style="flex: 1;">
                            <button type="button" class="btn-hora-metals" onclick="ModuloMetals.marcarHora('fin')" title="Marcar ahora">
                                <i class="fas fa-flag-checkered"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Fila 4: Cantidad OK + PNC -->
                <div class="metals-form-grid">
                    <div class="form-group-metals">
                        <label class="label-metals"><i class="fas fa-check-circle" style="color: #10b981;"></i> Cantidad OK</label>
                        <input type="number" id="metals-cant-ok" class="input-metals" min="0" placeholder="0" required>
                    </div>
                    <div class="form-group-metals">
                        <label class="label-metals"><i class="fas fa-times-circle" style="color: #ef4444;"></i> PNC / Defectos</label>
                        <input type="number" id="metals-pnc" class="input-metals" min="0" placeholder="0" value="0">
                    </div>
                </div>

                <!-- Campos específicos del proceso -->
                <div class="metals-form-grid" id="metals-campos-extra">
                    ${proc.extraFields}
                </div>

                <!-- Observaciones -->
                <div class="form-group-metals" style="grid-column: 1 / -1;">
                    <label class="label-metals"><i class="fas fa-comment"></i> Observaciones</label>
                    <textarea id="metals-observaciones" class="input-metals" rows="2"
                        placeholder="Notas adicionales del proceso..."></textarea>
                </div>

                <!-- Botones -->
                <div class="metals-form-actions">
                    <button type="submit" class="btn-guardar-metals"
                        style="background: ${proc.color};">
                        <i class="fas fa-save me-2"></i>Guardar Registro
                    </button>
                    <button type="button" class="btn-limpiar-metals"
                        onclick="document.getElementById('form-metals').reset(); ModuloMetals.abrirFormulario('${procesoKey}')">
                        <i class="fas fa-redo me-1"></i>Limpiar
                    </button>
                </div>
            </form>
        `;

        // Inicializar autocomplete y eventos
        this.initAutocompleteProducto();
        document.getElementById('form-metals').addEventListener('submit', (e) => this.handleSubmit(e));

        // Auto-seleccionar máquina si solo hay una
        if (proc.maquinas.length === 1) {
            document.getElementById('metals-maquina').value = proc.maquinas[0];
        }
    },

    // ----------------------------------------------------------------
    // Autocomplete de productos
    // ----------------------------------------------------------------
    initAutocompleteProducto: function () {
        const input = document.getElementById('metals-producto');
        const suggestionsDiv = document.getElementById('metals-sugerencias');
        if (!input || !suggestionsDiv) return;

        input.addEventListener('input', () => {
            const query = input.value.trim().toLowerCase();
            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }
            const resultados = this.productosData.filter(p =>
                String(p.CODIGO || '').toLowerCase().includes(query) ||
                String(p.DESCRIPCION || '').toLowerCase().includes(query)
            ).slice(0, 10);

            if (resultados.length === 0) {
                suggestionsDiv.innerHTML = '<div class="suggestion-item text-muted">Sin resultados</div>';
            } else {
                suggestionsDiv.innerHTML = resultados.map(p => `
                    <div class="suggestion-item" data-cod="${p.CODIGO}" data-desc="${p.DESCRIPCION}">
                        <strong>${p.CODIGO}</strong> — ${p.DESCRIPCION}
                    </div>
                `).join('');
                suggestionsDiv.querySelectorAll('.suggestion-item').forEach(div => {
                    div.addEventListener('click', () => {
                        input.value = `${div.dataset.cod} — ${div.dataset.desc}`;
                        input.dataset.codigo = div.dataset.cod;
                        input.dataset.descripcion = div.dataset.desc;
                        suggestionsDiv.classList.remove('active');
                    });
                });
            }
            suggestionsDiv.classList.add('active');
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    // ----------------------------------------------------------------
    // Helpers
    // ----------------------------------------------------------------
    marcarHora: function (tipo) {
        const ahora = new Date();
        const hh = String(ahora.getHours()).padStart(2, '0');
        const mm = String(ahora.getMinutes()).padStart(2, '0');
        const idInput = tipo === 'inicio' ? 'metals-hora-inicio' : 'metals-hora-fin';
        const el = document.getElementById(idInput);
        if (el) el.value = `${hh}:${mm}`;
    },

    cargarProductos: async function () {
        try {
            const res = await fetch('/api/metals/productos/listar');
            const data = await res.json();
            this.productosData = data.productos || [];
            window.AppState.sharedData.productosMetals = this.productosData; // Cache global
            console.log(`✅ [Metals] ${this.productosData.length} productos cargados.`);
        } catch (e) {
            console.error('Error cargando productos metals:', e);
        }
    },

    cargarDashboard: async function () {
        console.log('📊 [Metals] Cargando Dashboard...');
        const historyBody = document.getElementById('metals-dashboard-history');
        if (!historyBody) return;

        try {
            const res = await fetch('/api/metals/produccion/historial?limite=10');
            const data = await res.json();

            if (data.success && data.registros) {
                // Actualizar KPIs
                const stats = data.stats || { hoy: 0, mes: 0, pnc: 0, procesos: 0 };
                document.getElementById('metals-kpi-hoy').textContent = stats.hoy || 0;
                document.getElementById('metals-kpi-mes').textContent = stats.mes || 0;
                document.getElementById('metals-kpi-pnc').textContent = stats.pnc || 0;
                document.getElementById('metals-kpi-procesos').textContent = stats.procesos || 0;

                // Preparar datos para gráficos
                const tiemposPorMaquina = {};
                const pncPorProceso = {};
                const okPorMaquina = {};
                const tendenciaDiaria = {};
                const trabajosPorOperario = {};

                data.registros.forEach(r => {
                    const maq = r.MAQUINA || r.LOTE || 'Otro';
                    const proc = r.PROCESO || 'Otro';
                    const fecha = r.FECHA || 'N/A';

                    const mins = r.TIEMPO_TOTAL ? ModuloMetals.parseTiempoAMinutos(r.TIEMPO_TOTAL) : 0;
                    if (mins > 0) tiemposPorMaquina[maq] = (tiemposPorMaquina[maq] || 0) + mins;

                    const pnc = parseInt(r.PNC) || 0;
                    if (pnc > 0) pncPorProceso[proc] = (pncPorProceso[proc] || 0) + pnc;

                    const ok = parseInt(r.CANTIDAD_OK) || 0;
                    if (ok > 0) okPorMaquina[maq] = (okPorMaquina[maq] || 0) + ok;

                    if (fecha !== 'N/A') {
                        tendenciaDiaria[fecha] = (tendenciaDiaria[fecha] || 0) + ok;
                    }

                    const resp = r.RESPONSABLE || 'N/A';
                    if (resp !== 'N/A') {
                        trabajosPorOperario[resp] = (trabajosPorOperario[resp] || 0) + 1;
                    }
                });

                ModuloMetals.renderizarGraficos(tiemposPorMaquina, pncPorProceso, okPorMaquina, tendenciaDiaria, trabajosPorOperario);

                // Renderizar tabla
                historyBody.innerHTML = data.registros.map(r => {
                    const tiempoStr = r.TIEMPO_TOTAL ? r.TIEMPO_TOTAL : 'N/A';
                    return `
                    <tr>
                        <td class="text-secondary fw-bold small"><i class="fas fa-barcode me-1"></i>${r.ID_REGISTRO || 'N/A'}</td>
                        <td>${r.FECHA}</td>
                        <td><span class="badge" style="background: #64748b;">${r.MAQUINA || r.LOTE || 'N/A'}</span></td>
                        <td class="small fw-bold">${r.CODIGO_PRODUCTO}<br><span class="text-muted fw-normal">${r.DESCRIPCION_PRODUCTO}</span></td>
                        <td>${r.PROCESO}</td>
                        <td>${r.RESPONSABLE}</td>
                        <td class="text-center fw-bold text-success">${r.CANTIDAD_OK}</td>
                        <td class="text-center text-primary fw-bold"><i class="fas fa-clock me-1" style="opacity: 0.5;"></i>${tiempoStr}</td>
                        <td class="text-center fw-bold text-danger">${r.PNC}</td>
                    </tr>
                `;
                }).join('') || '<tr><td colspan="8" class="text-center p-3 text-muted">No hay registros recientes</td></tr>';
            }
        } catch (e) {
            console.error('Error cargando dashboard metals:', e);
            historyBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Error al cargar datos</td></tr>';
        }
    },

    // ----------------------------------------------------------------
    // Recolectar campos extra del proceso actual
    // ----------------------------------------------------------------
    getExtraData: function () {
        const extras = {};
        const extraEl = document.getElementById('metals-campos-extra');
        if (!extraEl) return extras;

        extraEl.querySelectorAll('input, select').forEach(el => {
            if (el.id && el.value) {
                const key = el.id.replace('extra-', '').replace(/-/g, '_');
                extras[key] = el.value;
            }
        });
        return extras;
    },

    // ----------------------------------------------------------------
    // Submit
    // ----------------------------------------------------------------
    handleSubmit: async function (e) {
        e.preventDefault();

        const productoInput = document.getElementById('metals-producto');
        const codigo = productoInput?.dataset?.codigo;
        const descripcion = productoInput?.dataset?.descripcion || productoInput?.value || '';

        if (!codigo) {
            mostrarNotificacion('⚠️ Selecciona un producto del buscador', 'warning');
            productoInput.focus();
            return;
        }

        const horaInicio = document.getElementById('metals-hora-inicio')?.value;
        const horaFin = document.getElementById('metals-hora-fin')?.value;

        // Calcular tiempo en minutos
        let tiempoMin = null;
        if (horaInicio && horaFin) {
            const [h1, m1] = horaInicio.split(':').map(Number);
            const [h2, m2] = horaFin.split(':').map(Number);
            tiempoMin = (h2 * 60 + m2) - (h1 * 60 + m1);
            if (tiempoMin < 0) tiempoMin += 1440; // cruce de medianoche
        }

        const proc = this.PROCESOS[this.procesoActual];

        const payload = {
            proceso: this.procesoActual,
            proceso_label: proc?.label || this.procesoActual,
            maquina: document.getElementById('metals-maquina')?.value,
            fecha: document.getElementById('metals-fecha')?.value,
            responsable: document.getElementById('metals-responsable')?.value,
            codigo_producto: codigo,
            descripcion_producto: descripcion,
            hora_inicio: horaInicio,
            hora_fin: horaFin,
            tiempo_min: tiempoMin,
            cantidad_ok: document.getElementById('metals-cant-ok')?.value,
            pnc: document.getElementById('metals-pnc')?.value || '0',
            observaciones: document.getElementById('metals-observaciones')?.value || '',
            campos_extra: this.getExtraData()
        };

        try {
            mostrarLoading(true);
            const response = await fetch('/api/metals/produccion/registrar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const res = await response.json();
            mostrarLoading(false);

            if (res.success) {
                mostrarNotificacion(`✅ Registro guardado — ${proc?.label}`, 'success');
                // Limpiar formulario o recargar
                setTimeout(() => this.inicializar(), 1200);
            } else {
                mostrarNotificacion(`❌ Error: ${res.message}`, 'error');
            }
        } catch (err) {
            mostrarLoading(false);
            console.error('Error submit metals:', err);
            mostrarNotificacion('Error de conexión', 'error');
        }
    },

    // ----------------------------------------------------------------
    // Gráficos y Análisis
    // ----------------------------------------------------------------
    parseTiempoAMinutos: function (tiempoStr) {
        if (!tiempoStr) return 0;
        let mins = 0;
        const hMatch = tiempoStr.match(/(\d+)h/);
        if (hMatch) mins += parseInt(hMatch[1]) * 60;
        const mMatch = tiempoStr.match(/(\d+)m/);
        if (mMatch) mins += parseInt(mMatch[1]);
        return mins;
    },

    renderizarGraficos: function (tiempos, defectos, ok, tendencia, operarios) {
        // Tiempos por Máquina (Doughnut)
        const ctxTiempos = document.getElementById('metals-chart-tiempos');
        if (ctxTiempos && window.Chart) {
            if (this.graficoTiempos) this.graficoTiempos.destroy();
            const bgColorsTpl = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#64748b'];

            const labelsTiempos = Object.keys(tiempos).length > 0 ? Object.keys(tiempos) : ['Sin datos'];
            const dataTiempos = Object.keys(tiempos).length > 0 ? Object.values(tiempos) : [1];
            const colorsT = Object.keys(tiempos).length > 0 ? bgColorsTpl : ['#e2e8f0'];

            this.graficoTiempos = new Chart(ctxTiempos, {
                type: 'doughnut',
                data: {
                    labels: labelsTiempos.map(l => l.length > 15 ? l.substring(0, 15) + '...' : l),
                    datasets: [{
                        data: dataTiempos,
                        backgroundColor: colorsT,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    if (Object.keys(tiempos).length === 0) return ' Sin registros';
                                    return ` ${ctx.label}: ${Math.floor(ctx.raw / 60)}h ${ctx.raw % 60}m`;
                                }
                            }
                        }
                    },
                    cutout: '65%'
                }
            });
        }

        // Defectos por Proceso (Bar)
        const ctxDefectos = document.getElementById('metals-chart-defectos');
        if (ctxDefectos && window.Chart) {
            if (this.graficoDefectos) this.graficoDefectos.destroy();

            const labelsDefectos = Object.keys(defectos).length > 0 ? Object.keys(defectos) : ['Sin defectos reportados'];
            const dataDefectos = Object.keys(defectos).length > 0 ? Object.values(defectos) : [0];

            this.graficoDefectos = new Chart(ctxDefectos, {
                type: 'bar',
                data: {
                    labels: labelsDefectos.map(l => l.length > 15 ? l.substring(0, 15) + '...' : l),
                    datasets: [{
                        label: 'Unidades Defectuosas (PNC)',
                        data: dataDefectos,
                        backgroundColor: '#ef4444',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            max: Object.keys(defectos).length > 0 ? undefined : 5
                        }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // Producción OK por Máquina (Pie)
        const ctxOk = document.getElementById('metals-chart-ok');
        if (ctxOk && window.Chart) {
            if (this.graficoOk) this.graficoOk.destroy();
            const bgColorsTpl = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#64748b', '#ef4444'];

            const labelsOk = Object.keys(ok).length > 0 ? Object.keys(ok) : ['Sin datos'];
            const dataOk = Object.keys(ok).length > 0 ? Object.values(ok) : [1];
            const colorsO = Object.keys(ok).length > 0 ? bgColorsTpl : ['#e2e8f0'];

            this.graficoOk = new Chart(ctxOk, {
                type: 'pie',
                data: {
                    labels: labelsOk.map(l => l.length > 15 ? l.substring(0, 15) + '...' : l),
                    datasets: [{
                        data: dataOk,
                        backgroundColor: colorsO,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    if (Object.keys(ok).length === 0) return ' Sin registros';
                                    return ` ${ctx.label}: ${ctx.raw} unidades OK`;
                                }
                            }
                        }
                    }
                }
            });
        }

        // Rendimiento Diario (Line)
        const ctxTendencia = document.getElementById('metals-chart-tendencia');
        if (ctxTendencia && window.Chart) {
            if (this.graficoTendencia) this.graficoTendencia.destroy();

            // Ordenar fechas cronológicamente
            const fechas = Object.keys(tendencia).sort((a, b) => {
                const partsA = a.split('/');
                const partsB = b.split('/');
                return new Date(partsA[2], partsA[1] - 1, partsA[0]) - new Date(partsB[2], partsB[1] - 1, partsB[0]);
            });

            // Tomar los últimos 7 días como máximo
            const fechasRecientes = fechas.slice(-7);
            const dataTendenciaStr = fechasRecientes.map(f => tendencia[f]);

            const labelsTendencia = fechasRecientes.length > 0 ? fechasRecientes : ['Sin datos'];
            const dataTendencia = fechasRecientes.length > 0 ? dataTendenciaStr : [0];

            this.graficoTendencia = new Chart(ctxTendencia, {
                type: 'line',
                data: {
                    labels: labelsTendencia,
                    datasets: [{
                        label: 'Unidades OK Producidas',
                        data: dataTendencia,
                        borderColor: '#0dcaf0',
                        backgroundColor: 'rgba(13, 202, 240, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: '#0dcaf0',
                        pointRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            max: fechasRecientes.length > 0 ? undefined : 10
                        }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // Trabajos por Operario (Horizontal Bar)
        const ctxOperarios = document.getElementById('metals-chart-operarios');
        if (ctxOperarios && window.Chart) {
            if (this.graficoOperarios) this.graficoOperarios.destroy();

            // Ordenar operarios de mayor a menor cantidad de trabajos
            const operariosOrdenados = Object.keys(operarios).sort((a, b) => operarios[b] - operarios[a]);

            const labelsOperarios = operariosOrdenados.length > 0 ? operariosOrdenados : ['Sin datos'];
            const dataOperarios = operariosOrdenados.length > 0 ? operariosOrdenados.map(o => operarios[o]) : [0];

            this.graficoOperarios = new Chart(ctxOperarios, {
                type: 'bar',
                data: {
                    labels: labelsOperarios.map(l => l.length > 20 ? l.substring(0, 20) + '...' : l),
                    datasets: [{
                        label: 'Número de Trabajos Realizados',
                        data: dataOperarios,
                        backgroundColor: '#f59e0b',
                        borderRadius: 4
                    }]
                },
                options: {
                    indexAxis: 'y', // Hace que las barras sean horizontales
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            max: operariosOrdenados.length > 0 ? undefined : 5
                        }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    }
};

window.ModuloMetals = ModuloMetals;
