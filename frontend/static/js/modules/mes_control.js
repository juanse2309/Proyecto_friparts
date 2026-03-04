// ============================================
// mes_control.js - Módulo de Control de Producción (MES)
// ============================================

window.ModuloMes = {
    maquinas: [],
    productos: [],
    programacionesActivas: [],
    maquinaSeleccionada: localStorage.getItem('mes_maquina_ref') || '',
    trabajoActivo: null,
    tempProductList: [], // Lista para multi-producto (un montaje, varios códigos)

    init: async function () {
        console.log('🚀 [MES] Inicializando Módulo de Control de Producción...');

        // Registrar persistencia Juan Sebastian Request
        if (window.FormHelpers) {
            window.FormHelpers.registrarPersistencia('form-mes-programar');
        }

        this.configurarEventos();
        await this.cargarDatos();
        this.initAutocomplete();

        // Cargar máquina desde localStorage si existe
        if (this.maquinaSeleccionada) {
            const select = document.getElementById('mes-op-maquina-sel');
            if (select) {
                select.value = this.maquinaSeleccionada;
                this.cambiarMaquina(this.maquinaSeleccionada);
            }
        }
    },

    cargarDatos: async function () {
        try {
            // 1. Cargar Máquinas
            const maqData = await fetchData('/api/obtener_maquinas');
            this.maquinas = maqData || [];
            this.actualizarSelect('mes-prog-maquina', this.maquinas);

            // 2. Cargar Productos (desde cache o API)
            if (window.AppState && window.AppState.sharedData && window.AppState.sharedData.productos) {
                this.productos = window.AppState.sharedData.productos;
            } else {
                const res = await fetchData('/api/productos/listar');
                this.productos = res?.productos || [];
            }

            // 3. Cargar estado del dashboard de máquinas
            await this.cargarDashboard();

            // 4. Cargar la cola de programación (Vista 1)
            await this.actualizarColaProgramacion();

        } catch (error) {
            console.error('[MES] Error cargando datos:', error);
        }
    },

    /**
     * Carga el dashboard de 4 máquinas desde /api/mes/dashboard
     * y renderiza las tarjetas en la Vista 2.
     */
    cargarDashboard: async function () {
        try {
            const data = await fetchData('/api/mes/dashboard');
            if (data && data.maquinas) {
                this.dashboardData = data.maquinas;
                this.renderDashboardMaquinas(data.maquinas);
            }
        } catch (error) {
            console.error('[MES] Error cargando dashboard:', error);
        }
    },

    getColorEstadoMaquina: function (estado) {
        if (estado === 'EN_PROCESO') return { header: 'bg-primary text-white', badge: 'bg-white text-primary' };
        if (estado === 'PROGRAMADO') return { header: 'bg-warning text-dark', badge: 'bg-dark text-white' };
        return { header: 'bg-light text-muted', badge: 'bg-secondary text-white' };
    },

    renderDashboardMaquinas: function (maquinas) {
        const grid = document.getElementById('mes-dashboard-grid');
        if (!grid) return;

        if (!maquinas || maquinas.length === 0) {
            grid.innerHTML = `<div class="col-12 text-center py-5 opacity-50">
                <i class="fas fa-industry fa-3x mb-3"></i>
                <p>No hay m\u00e1quinas configuradas.</p>
            </div>`;
            return;
        }

        // ── Ordenar siempre por n\u00famero de m\u00e1quina ──────────────────
        const sorted = [...maquinas].sort((a, b) => {
            const num = s => parseInt((s.nombre || '').replace(/\D/g, '')) || 0;
            return num(a) - num(b);
        });

        // Paleta por estado
        const palette = {
            EN_PROCESO: { border: '#2563eb', bg: '#eff6ff', badge: '#2563eb', label: '\u25B6 EN PROCESO', btnCls: 'btn-warning' },
            PROGRAMADO: { border: '#16a34a', bg: '#f0fdf4', badge: '#16a34a', label: '\u23F3 PROGRAMADO', btnCls: 'btn-success' },
            LIBRE: { border: '#cbd5e1', bg: '#f8fafc', badge: '#94a3b8', label: '\u2713 LIBRE', btnCls: '' },
        };

        grid.innerHTML = sorted.map(m => {
            const pal = palette[m.estado] || palette.LIBRE;
            const activo = m.trabajo_activo;
            const cola = m.cola || [];

            // ── Card LIBRE ─────────────────────────────────────────────
            if (m.estado === 'LIBRE') {
                return `
                <div class="col-md-6 col-xl-3">
                    <div class="card border-0 h-100" style="border-radius:16px;border-left:4px solid ${pal.border} !important;
                        box-shadow:0 2px 10px rgba(0,0,0,.07);background:${pal.bg}">
                        <div class="card-body d-flex flex-column align-items-center justify-content-center text-center p-4">
                            <div class="fw-bold text-muted" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase">${m.nombre}</div>
                            <div class="mt-2" style="color:${pal.badge};font-size:.75rem;font-weight:600">${pal.label}</div>
                            <div class="text-muted mt-1" style="font-size:.75rem">Sin trabajos en cola</div>
                        </div>
                    </div>
                </div>`;
            }

            // ── Datos clave del trabajo ─────────────────────────────────
            const molde = activo?.molde || cola[0]?.molde || 'N/A';
            const horaInicio = (m.estado === 'EN_PROCESO' && activo?.hora_inicio)
                ? `<small class="text-muted"><i class="fas fa-clock me-1"></i>Inicio: ${activo.hora_inicio}</small>` : '';

            // Lista de SKUs del molde (desde la cola del dashboard)
            const skuList = cola.length > 0
                ? cola.map(c => `
                    <div class="d-flex justify-content-between align-items-center py-1"
                        style="border-bottom:1px solid #f1f5f9;font-size:.78rem">
                        <span class="fw-bold" style="color:#1e293b">${c.codigo_producto || '-'}</span>
                        <span class="badge" style="background:${pal.border}22;color:${pal.border};font-size:.65rem">${c.cavidades} cav.</span>
                    </div>`).join('')
                : `<div class="text-muted" style="font-size:.75rem">Sin productos en cola.</div>`;

            // Botón principal
            const btn = m.estado === 'EN_PROCESO'
                ? `<button class="btn btn-warning fw-bold w-100 py-2"
                       onclick="ModuloMes.clickFinalizarDesdeCard('${activo?.id_inyeccion}', ${activo?.cavidades || 1})">
                       <i class="fas fa-stop-circle me-1"></i> Finalizar Turno
                   </button>`
                : `<button class="btn btn-success fw-bold w-100 py-2"
                       onclick="ModuloMes.clickIniciarDesdeCard('${cola[0]?.id_programacion}')">
                       <i class="fas fa-play me-1"></i> Iniciar Trabajo
                   </button>`;

            // Botón liberar (solo PROGRAMADO)
            const btnLiberar = (m.estado === 'PROGRAMADO' && cola.length > 0)
                ? `<button class="btn btn-outline-danger btn-sm w-100 mt-2"
                       onclick="ModuloMes.cancelarBatch('${m.nombre}')">
                       <i class="fas fa-ban me-1"></i> Liberar M\u00e1quina
                   </button>` : '';

            return `
            <div class="col-md-6 col-xl-3">
                <div class="card border-0 h-100" style="border-radius:16px;overflow:hidden;
                    border-left:4px solid ${pal.border} !important;
                    box-shadow:0 4px 16px rgba(0,0,0,.09);">

                    <!-- Cabecera: Máquina + Estado -->
                    <div style="background:${pal.bg};padding:12px 16px 8px;border-bottom:1px solid #f1f5f9">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span style="font-size:.62rem;font-weight:700;letter-spacing:.1em;
                                text-transform:uppercase;color:#64748b">${m.nombre}</span>
                            <span style="font-size:.62rem;font-weight:700;color:${pal.badge};
                                background:${pal.badge}18;padding:2px 8px;border-radius:20px">${pal.label}</span>
                        </div>
                        <!-- MOLDE como Héroe -->
                        <div style="font-size:1.35rem;font-weight:900;color:#0f172a;line-height:1.1">
                            ${molde}
                        </div>
                        ${horaInicio}
                    </div>

                    <!-- Lista de SKUs del molde -->
                    <div style="padding:10px 14px;flex-grow:1">
                        <div style="font-size:.6rem;font-weight:700;text-transform:uppercase;color:#94a3b8;margin-bottom:6px">
                            <i class="fas fa-boxes me-1"></i> Productos del Molde
                        </div>
                        ${skuList}
                    </div>

                    <!-- Acciones -->
                    <div style="padding:10px 14px 14px">
                        ${btn}
                        ${btnLiberar}
                    </div>
                </div>
            </div>`;
        }).join('');
    },


    /**
     * Iniciar trabajo desde el botón de la tarjeta de máquina.
     */
    clickIniciarDesdeCard: async function (idProg) {
        if (!idProg) return;
        const operario = window.AuthModule?.currentUser?.nombre || 'OPERARIO';

        const result = await Swal.fire({
            title: '¿Iniciar Trabajo?',
            text: `Se registrará la Hora de Inicio ahora. Operador: ${operario}`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, iniciar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                mostrarLoading(true);
                const res = await fetchData('/api/mes/iniciar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_programacion: idProg, operario })
                });
                mostrarLoading(false);
                if (res?.success) {
                    await this.cargarDashboard(); // Refrescar tarjetas
                } else {
                    Swal.fire('Error', res?.error || 'No se pudo iniciar', 'error');
                }
            } catch (e) {
                mostrarLoading(false);
                console.error('[MES] Error iniciando:', e);
            }
        }
    },

    /**
     * Finalizar turno desde el botón de la tarjeta de máquina.
     */
    clickFinalizarDesdeCard: async function (idInyeccion, cavidades) {
        if (!idInyeccion) return;

        // Obtener la hora actual en formato HH:MM para sugerir como Hora Fin
        const now = new Date();
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        const horaSugerida = `${hh}:${mm}`;

        const { value: formValues } = await Swal.fire({
            title: '\u00bfFinalizar Turno?',
            html: `
                <div class="text-start fs-6 mb-3 text-muted">Ingresa los cierres totales y revisa los tiempos del turno:</div>
                
                <div class="mb-3 text-start px-2">
                    <label class="form-label fw-bold small text-uppercase text-muted mb-1">Cierres del Contador</label>
                    <input type="number" id="swal-cierres" class="form-control form-control-lg text-center fw-bold" placeholder="0" min="1">
                </div>
                
                <div class="row text-start px-2 g-3">
                    <div class="col-6">
                        <label class="form-label fw-bold small text-uppercase text-muted mb-1">Hora Inicio Real</label>
                        <input type="time" id="swal-hora-inicio" class="form-control" value="06:00">
                    </div>
                    <div class="col-6">
                        <label class="form-label fw-bold small text-uppercase text-muted mb-1">Hora Fin Real</label>
                        <input type="time" id="swal-hora-fin" class="form-control" value="${horaSugerida}">
                    </div>
                </div>
                <div class="mt-3 small text-muted text-start ps-2"><i class="fas fa-info-circle me-1"></i>La hora de llegada se registrar\u00e1 como 6:00 AM autom\u00e1ticamente.</div>
            `,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonText: '<i class="fas fa-check-circle me-1"></i> Reportar y Finalizar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#16a34a',
            preConfirm: () => {
                const cierres = document.getElementById('swal-cierres').value;
                const hi = document.getElementById('swal-hora-inicio').value;
                const hf = document.getElementById('swal-hora-fin').value;

                if (!cierres || parseInt(cierres) <= 0) {
                    Swal.showValidationMessage('Ingresa un n\u00famero v\u00e1lido de cierres');
                    return false;
                }
                if (!hi || !hf) {
                    Swal.showValidationMessage('Ambas horas son obligatorias');
                    return false;
                }
                return { cierres: parseInt(cierres), hora_inicio: hi, hora_fin: hf };
            }
        });

        if (formValues) {
            try {
                mostrarLoading(true);
                const res = await fetchData('/api/mes/reportar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_inyeccion: idInyeccion,
                        cierres: formValues.cierres,
                        hora_inicio: formValues.hora_inicio,
                        hora_fin: formValues.hora_fin
                    })
                });
                mostrarLoading(false);
                if (res?.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Turno Reportado',
                        text: `Producci\u00f3n te\u00f3rica: ${res.teorica?.toLocaleString()} piezas. Pasa a Control de Calidad.`,
                        timer: 3500, showConfirmButton: false
                    });
                    await this.cargarDashboard();
                    await this.actualizarPendientesCalidad();
                } else {
                    Swal.fire('Error', res?.error || 'No se pudo reportar', 'error');
                }
            } catch (e) {
                mostrarLoading(false);
                console.error('[MES] Error finalizando:', e);
            }
        }
    },

    configurarEventos: function () {
        // Tab Events - Refresh data on tab change
        const tabs = document.querySelectorAll('#mes-tabs button');
        tabs.forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                const targetId = e.target.getAttribute('data-bs-target');
                if (targetId === '#panel-programacion') this.actualizarColaProgramacion();
                if (targetId === '#panel-calidad') this.actualizarPendientesCalidad();
                if (targetId === '#panel-operacion') this.cargarDashboard(); // <-- Llama dashboard unificado
                if (targetId === '#panel-legacy') {
                    if (window.ModuloInyeccion && typeof window.ModuloInyeccion.init === 'function') {
                        window.ModuloInyeccion.init();
                    }
                }
            });
        });

        // Form Programar
        const formProg = document.getElementById('form-mes-programar');
        if (formProg) {
            formProg.addEventListener('submit', (e) => {
                e.preventDefault();
                this.crearProgramacion();
            });
        }

        // Selección de Máquina (Operario)
        const selectMaq = document.getElementById('mes-op-maquina-sel');
        if (selectMaq) {
            selectMaq.addEventListener('change', (e) => {
                this.cambiarMaquina(e.target.value);
            });
        }

        // Botones de Acción Operario
        const btnIniciar = document.getElementById('btn-mes-iniciar-trabajo');
        if (btnIniciar) {
            btnIniciar.addEventListener('click', () => this.iniciarTrabajo());
        }

        const btnFinalizar = document.getElementById('btn-mes-finalizar-trabajo');
        if (btnFinalizar) {
            btnFinalizar.addEventListener('click', () => this.finalizarTrabajo());
        }

        // Refresh buttons
        document.getElementById('btn-refresh-prog')?.addEventListener('click', () => this.actualizarColaProgramacion());
        document.getElementById('btn-refresh-operacion')?.addEventListener('click', () => this.cargarDashboard());


        // --- MEJORA: Búsqueda automática y Autocompletado ---
        const productInput = document.getElementById('mes-prog-producto');
        const btnAddProd = document.getElementById('btn-mes-add-prod-list');

        if (productInput) {
            // Autocompletado mientras escribe
            productInput.addEventListener('input', (e) => this.filtrarProductos(e.target.value));

            productInput.addEventListener('blur', () => {
                // Pequeño delay para permitir click en sugerencias
                setTimeout(() => {
                    const suggestions = document.getElementById('mes-prog-prod-suggestions');
                    if (suggestions) suggestions.classList.remove('active');
                }, 200);
            });

            // Re-escuchar cambio/blur para detalles técnicos
            productInput.addEventListener('blur', () => this.buscarDetallesProducto(productInput.value));
            productInput.addEventListener('change', () => this.buscarDetallesProducto(productInput.value));

            // Permitir 'Enter' para añadir a la lista
            productInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.agregarProductoATemp();
                }
            });
        }

        if (btnAddProd) {
            btnAddProd.addEventListener('click', () => this.agregarProductoATemp());
        }
    },

    filtrarProductos: function (query) {
        const suggestions = document.getElementById('mes-prog-prod-suggestions');
        if (!suggestions) return;

        if (!query || query.length < 2) {
            suggestions.classList.remove('active');
            return;
        }

        const q = query.toLowerCase();
        // Filtrar del cache de productos
        const filtrados = (this.productos || []).filter(p =>
            (p.codigo && p.codigo.toLowerCase().includes(q)) ||
            (p.descripcion && p.descripcion.toLowerCase().includes(q))
        ).slice(0, 8);

        if (filtrados.length > 0) {
            suggestions.innerHTML = filtrados.map(p => `
                <div class="suggestion-item p-2 border-bottom pointer" onclick="ModuloMes.seleccionarProducto('${p.codigo}')">
                    <div class="fw-bold">${p.codigo}</div>
                    <div class="text-xs text-muted text-truncate">${p.descripcion}</div>
                </div>
            `).join('');
            suggestions.classList.add('active');
        } else {
            suggestions.classList.remove('active');
        }
    },

    seleccionarProducto: function (codigo) {
        const input = document.getElementById('mes-prog-producto');
        if (input) {
            input.value = codigo;
            this.filtrarProductos(''); // Cerrar
            this.buscarDetallesProducto(codigo);
        }
    },

    /**
     * Añade el producto actual del input a la lista temporal del molde
     */
    agregarProductoATemp: function () {
        const input = document.getElementById('mes-prog-producto');
        const moldeInput = document.getElementById('mes-prog-molde');
        const cavInput = document.getElementById('mes-prog-cavidades');

        const codigo = input.value.trim();
        const cavidades = parseInt(cavInput.value) || 1;

        if (!codigo) return;

        // Verificar si ya está en la lista
        if (this.tempProductList.some(p => p.codigo === codigo)) {
            Swal.fire('Atención', 'Este producto ya está en la lista', 'warning');
            return;
        }

        this.tempProductList.push({
            codigo: codigo,
            cavidades: cavidades,
            molde: moldeInput.value.trim()
        });

        // Limpiar para el siguiente
        input.value = '';
        input.focus();
        this.filtrarProductos(''); // Limpiar sugerencias

        this.renderTempList();
        console.log('➕ [MES] Producto añadido a lote:', codigo);

        // Feedback visual en el input
        input.style.borderColor = '#10b981';
        setTimeout(() => input.style.borderColor = '', 500);
    },

    quitarProductoATemp: function (codigo) {
        this.tempProductList = this.tempProductList.filter(p => p.codigo !== codigo);
        this.renderTempList();
    },

    renderTempList: function () {
        const container = document.getElementById('mes-prog-temp-list');
        const totalCavBadge = document.getElementById('mes-prog-total-cav');

        if (!container) return;

        if (this.tempProductList.length === 0) {
            container.innerHTML = '<tr><td class="text-center text-muted py-2 small">Añade productos para empezar</td></tr>';
            if (totalCavBadge) totalCavBadge.innerText = '0 Cav';
            return;
        }

        let totalCav = 0;
        container.innerHTML = this.tempProductList.map(p => {
            totalCav += p.cavidades;
            return `
                <tr>
                    <td class="fw-bold">${p.codigo}</td>
                    <td class="text-center">${p.cavidades}</td>
                    <td class="text-end">
                        <button type="button" class="btn btn-sm btn-link text-danger p-0" onclick="ModuloMes.quitarProductoATemp('${p.codigo}')">
                            <i class="fas fa-times"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        if (totalCavBadge) totalCavBadge.innerText = `${totalCav} Cav`;
    },

    /**
     * Busca los detalles técnicos de un producto (molde/cavidades) para autocompletar el form.
     */
    buscarDetallesProducto: async function (codigo) {
        if (!codigo || codigo.length < 3) return;

        try {
            console.log(`🔍 [MES] Buscando detalles técnicos para: ${codigo}`);
            const res = await fetchData(`/api/productos/detalle/${codigo}`);

            if (res && res.status === 'success' && res.producto) {
                const p = res.producto;
                console.log('✅ [MES] Detalles encontrados:', p);

                const moldeInput = document.getElementById('mes-prog-molde');
                const cavInput = document.getElementById('mes-prog-cavidades');

                if (moldeInput && p.moldes) {
                    moldeInput.value = p.moldes;
                    moldeInput.classList.add('is-valid');
                    setTimeout(() => moldeInput.classList.remove('is-valid'), 2000);
                }

                if (cavInput && p.cavidades) {
                    cavInput.value = p.cavidades;
                    cavInput.classList.add('is-valid');
                    setTimeout(() => cavInput.classList.remove('is-valid'), 2000);
                }
            }
        } catch (error) {
            console.warn('[MES] No se pudieron obtener detalles para auto-completar:', error);
        }
    },

    initAutocomplete: function () {
        if (window.ModuloUX && window.ModuloUX.setupSmartEnter) {
            window.ModuloUX.setupSmartEnter({
                inputIds: ['mes-prog-producto', 'mes-prog-molde', 'mes-prog-cavidades'],
                actionBtnId: 'btn-mes-add-prod-list',
                autocomplete: {
                    inputId: 'mes-prog-producto',
                    suggestionsId: 'mes-prog-prod-suggestions'
                }
            });
        }
    },

    // --- LÓGICA DE PROGRAMACIÓN (Fase 1) ---

    actualizarColaProgramacion: async function () {
        try {
            console.log('🔄 [MES] Actualizando cola de programación...');
            const data = await fetchData('/api/mes/programaciones/TODAS');
            this.programacionesActivas = data || [];
            this.renderCardsProgramacion();
        } catch (error) {
            console.error('[MES] Error actualizando cola:', error);
        }
    },

    renderCardsProgramacion: function () {
        const container = document.getElementById('mes-cards-container');
        if (!container) return;

        if (!this.programacionesActivas || this.programacionesActivas.length === 0) {
            container.innerHTML = `
                <div class="col-12 text-center py-5 opacity-50">
                    <i class="fas fa-calendar-check fa-3x mb-3"></i>
                    <p>No hay programaciones activas en este momento.</p>
                </div>`;
            return;
        }

        // Agrupar por Máquina — usando Maquina (campo del nuevo formato agrupado)
        const porMaquina = {};
        this.maquinas.forEach(m => porMaquina[m] = []);

        this.programacionesActivas.forEach(p => {
            const maq = p.Maquina || p.MAQUINA || '';
            if (porMaquina[maq] !== undefined) {
                porMaquina[maq].push(p);
            } else {
                porMaquina[maq] = [p];
            }
        });

        // Unión de máquinas conocidas + máquinas con trabajo
        const todasMaquinas = [...new Set([...this.maquinas, ...Object.keys(porMaquina).filter(k => k)])];

        // Paleta de colores por máquina (gradientes) — cíclica
        const paletas = [
            { grad: 'linear-gradient(135deg,#1d4ed8,#3b82f6)', light: '#eff6ff', accent: '#1d4ed8' },
            { grad: 'linear-gradient(135deg,#6d28d9,#8b5cf6)', light: '#f5f3ff', accent: '#6d28d9' },
            { grad: 'linear-gradient(135deg,#0f766e,#14b8a6)', light: '#f0fdfa', accent: '#0f766e' },
            { grad: 'linear-gradient(135deg,#c2410c,#f97316)', light: '#fff7ed', accent: '#c2410c' },
        ];

        container.innerHTML = todasMaquinas.map((m, idx) => {
            const progs = porMaquina[m] || [];
            const tieneTrabajo = progs.length > 0;
            const pal = paletas[idx % paletas.length];

            // --- Card libre ---
            if (!tieneTrabajo) {
                return `
                <div class="col-md-6 col-xl-3 mb-3">
                    <div class="card border-0 h-100" style="border-radius:18px;background:#f8fafc;box-shadow:0 2px 8px rgba(0,0,0,.06)">
                        <div class="card-body d-flex flex-column align-items-center justify-content-center text-center p-4" style="min-height:170px">
                            <div class="rounded-circle d-flex align-items-center justify-content-center mb-3"
                                style="width:52px;height:52px;background:#e2e8f0">
                                <i class="fas fa-microchip text-muted" style="font-size:1.4rem"></i>
                            </div>
                            <div class="fw-bold text-muted" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase">${m}</div>
                            <div class="text-muted mt-1" style="font-size:.78rem">Disponible</div>
                        </div>
                    </div>
                </div>`;
            }

            // --- Card activa ---
            // El backend ahora devuelve 1 objeto por molde con un sub-array `productos`
            const moldeGrupo = progs[0]; // primer (y único) grupo por molde
            const moldePrincipal = moldeGrupo.Molde || moldeGrupo.MOLDE || 'Sin nombre';
            // Aplanar los productos de todos los grupos de esta máquina
            const todosProductos = progs.flatMap(g => g.productos || []);
            const totalCav = todosProductos.reduce((sum, p) => sum + (parseInt(p.cavidades) || 0), 0);

            return `
            <div class="col-md-6 col-xl-3 mb-3">
                <div class="card border-0 h-100" style="border-radius:18px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,.13)">
                    <!-- Header gradiente -->
                    <div style="background:${pal.grad};padding:18px 20px 16px">
                        <div class="d-flex justify-content-between align-items-start">
                            <div style="max-width:65%">
                                <div style="color:rgba(255,255,255,.6);font-size:.6rem;letter-spacing:.12em;text-transform:uppercase;font-weight:700">${m}</div>
                                <div style="color:#fff;font-size:1.1rem;font-weight:800;line-height:1.25;margin-top:4px;word-break:break-word">${moldePrincipal}</div>
                            </div>
                            <div class="text-center" style="min-width:52px">
                                <div style="color:#fff;font-size:2.4rem;font-weight:900;line-height:1">${totalCav}</div>
                                <div style="color:rgba(255,255,255,.55);font-size:.6rem;letter-spacing:.06em">CAV.</div>
                            </div>
                        </div>
                        <div class="d-flex align-items-center gap-2 mt-3">
                            <span style="width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.75);display:inline-block;
                                animation:mes-pulse 1.8s ease-in-out infinite"></span>
                            <span style="color:rgba(255,255,255,.65);font-size:.68rem;font-weight:600">
                                EN COLA &middot; ${todosProductos.length} PRODUCTO${todosProductos.length !== 1 ? 'S' : ''}
                            </span>
                        </div>
                    </div>
                    <!-- Body: lista de SKUs -->
                    <div style="background:#fff;padding:14px 16px 16px">
                        <div style="margin-bottom:12px">
                            ${todosProductos.map((p, i) => `
                                <div style="display:flex;justify-content:space-between;align-items:center;
                                    padding:9px 12px;
                                    background:${i % 2 === 0 ? pal.light : '#fff'};
                                    border-radius:8px;margin-bottom:3px">
                                    <span style="font-size:1.15rem;font-weight:900;color:${pal.accent}">
                                        ${p.codigo || '-'}
                                    </span>
                                    <span style="font-size:1.15rem;font-weight:700;color:#374151">
                                        x${p.cavidades || 0}
                                    </span>
                                </div>`).join('')}
                        </div>
                        <button onclick="ModuloMes.cancelarBatch('${m}')"
                            style="width:100%;padding:7px;border:none;border-radius:10px;
                            background:#fee2e2;color:#b91c1c;font-size:.78rem;font-weight:600;cursor:pointer">
                            <i class="fas fa-times-circle me-1"></i> Liberar Máquina
                        </button>
                    </div>
                </div>
            </div>`;
        }).join('');
    },


    crearProgramacion: async function () {
        const maquina = document.getElementById('mes-prog-maquina').value;
        const observaciones = document.getElementById('mes-prog-obs').value;

        if (!maquina) {
            Swal.fire('Error', 'Debes seleccionar una máquina', 'error');
            return;
        }

        // Si hay productos en la lista temporal, usamos la lista. 
        // Si no, verificamos si hay algo en el input individual (para caso simple)
        let productosParaEnviar = [...this.tempProductList];

        const codigoInput = document.getElementById('mes-prog-producto').value.trim();
        if (codigoInput && productosParaEnviar.length === 0) {
            productosParaEnviar.push({
                codigo: codigoInput,
                cavidades: parseInt(document.getElementById('mes-prog-cavidades').value) || 1,
                molde: document.getElementById('mes-prog-molde').value.trim()
            });
        }

        if (productosParaEnviar.length === 0) {
            Swal.fire('Error', 'Añade al menos un producto a la lista', 'error');
            return;
        }

        const payload = {
            maquina: maquina,
            productos: productosParaEnviar,
            observaciones: observaciones,
            responsable_planta: window.AuthModule?.currentUser?.nombre || 'ADMIN'
        };

        try {
            mostrarLoading(true);
            const res = await fetchData('/api/mes/programar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            mostrarLoading(false);

            if (res && res.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Programado!',
                    text: `Se han programado ${res.count} items en la ${maquina}`,
                    timer: 2000,
                    showConfirmButton: false
                });

                this.tempProductList = [];
                this.renderTempList();
                document.getElementById('form-mes-programar').reset();
                if (window.FormHelpers) window.FormHelpers.limpiarPersistencia('form-mes-programar');
                // Refrescar tanto la tabla de cola como las tarjetas de máquinas
                await this.actualizarColaProgramacion();
                await this.cargarDashboard();   // ← actualiza las cards a estado PROGRAMADO
            } else {
                Swal.fire('Error', res?.error || 'No se pudo programar', 'error');
            }
        } catch (error) {
            mostrarLoading(false);
            console.error('[MES] Error al programar:', error);
            Swal.fire('Error', 'Error de red al intentar programar', 'error');
        }
    },

    cancelarBatch: async function (maquina) {
        const result = await Swal.fire({
            title: '¿Liberar Máquina?',
            text: `Se cancelarán todas las programaciones pendientes para ${maquina}.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            confirmButtonText: 'Sí, liberar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                mostrarLoading(true);

                // Leer la cola de la máquina directamente del dashboard en memoria
                const maquinaData = (this.dashboardData || []).find(m => m.nombre === maquina);
                const cola = maquinaData?.cola || [];

                if (cola.length === 0) {
                    mostrarLoading(false);
                    Swal.fire('Aviso', 'No hay programaciones activas para esta máquina.', 'info');
                    return;
                }

                // Obtener IDs únicos (Multi-SKU: varios SKUs comparten un mismo id_programacion)
                const idsUnicos = [...new Set(cola.map(p => p.id_programacion).filter(Boolean))];

                for (const id of idsUnicos) {
                    await fetchData(`/api/mes/cancelar/${id}`, { method: 'POST' });
                }

                mostrarLoading(false);
                await this.cargarDashboard();
                await this.actualizarColaProgramacion();
                Swal.fire('Liberada', `La máquina ${maquina} ya no tiene trabajos pendientes.`, 'success');
            } catch (error) {
                mostrarLoading(false);
                console.error('[MES] Error liberando máquina:', error);
                Swal.fire('Error', 'No se pudieron cancelar todos los trabajos', 'error');
            }
        }
    },

    // --- LÓGICA DE OPERACIÓN (Fase 2) ---

    cambiarMaquina: function (idMaquina) {
        this.maquinaSeleccionada = idMaquina;
        localStorage.setItem('mes_maquina_ref', idMaquina);
        this.actualizarEstadoMaquina();
    },

    actualizarEstadoMaquina: async function () {
        if (!this.maquinaSeleccionada) return;

        try {
            // Usamos el nuevo endpoint de status
            const data = await fetchData(`/api/mes/status/${this.maquinaSeleccionada}`);
            this.trabajoActivo = (data && data.estado !== 'LIBRE') ? data : null;
            this.renderOperacion();
        } catch (error) {
            console.error('[MES] Error cargando estado máquina:', error);
        }
    },

    renderOperacion: function () {
        const card = document.getElementById('mes-operacion-card');
        const empty = document.getElementById('mes-empty-operacion');
        const statusBadge = document.getElementById('mes-status-maquina');

        if (!this.trabajoActivo) {
            if (card) card.style.display = 'none';
            if (empty) empty.style.display = 'block';
            if (statusBadge) {
                statusBadge.className = 'badge bg-secondary p-3 fs-6 rounded-pill';
                statusBadge.innerText = 'Máquina Sin Programación';
            }
            return;
        }

        if (card) card.style.display = 'block';
        if (empty) empty.style.display = 'none';

        // Info Superior
        const infoDiv = document.getElementById('mes-info-trabajo');
        if (infoDiv) {
            infoDiv.innerHTML = `
                <div class="d-flex justify-content-between">
                    <div>
                        <h4 class="fw-bold mb-1">${this.trabajoActivo.producto}</h4>
                        <span class="text-muted small">Estado: ${this.trabajoActivo.estado}</span>
                    </div>
                    <div class="text-end">
                        <div class="fw-bold">Molde: ${this.trabajoActivo.molde || 'N/A'}</div>
                        <div class="text-muted small">${this.trabajoActivo.cavidades} Cavidades</div>
                    </div>
                </div>
            `;
        }

        // Indicadores Laterales
        const txtTeorica = document.getElementById('mes-txt-teorica');
        if (txtTeorica) txtTeorica.innerText = this.trabajoActivo.teorica || '--';

        const txtMolde = document.getElementById('mes-txt-molde');
        if (txtMolde) txtMolde.innerText = this.trabajoActivo.molde || 'N/A';

        const txtCav = document.getElementById('mes-txt-cavidades');
        if (txtCav) txtCav.innerText = `${this.trabajoActivo.cavidades} cavidades`;

        const txtInicio = document.getElementById('mes-txt-hora-inicio');
        if (txtInicio) txtInicio.innerText = this.trabajoActivo.inicio || '--:--';

        // Switch de pasos
        const stepIniciar = document.getElementById('mes-step-iniciar');
        const stepReportar = document.getElementById('mes-step-reportar');

        if (this.trabajoActivo.estado === 'PROGRAMADO') {
            if (statusBadge) {
                statusBadge.className = 'badge bg-primary p-3 fs-6 rounded-pill animate__animated animate__pulse animate__infinite';
                statusBadge.innerText = 'TRABAJO PENDIENTE';
            }
            if (stepIniciar) stepIniciar.style.display = 'block';
            if (stepReportar) stepReportar.style.display = 'none';
        } else if (this.trabajoActivo.estado === 'EN_PROCESO') {
            if (statusBadge) {
                statusBadge.className = 'badge bg-success p-3 fs-6 rounded-pill animate__animated animate__flash animate__slow animate__infinite';
                statusBadge.innerText = '▶ TRABAJANDO...';
            }
            if (stepIniciar) stepIniciar.style.display = 'none';
            if (stepReportar) stepReportar.style.display = 'block';
        }
    },

    iniciarTrabajo: async function () {
        if (!this.trabajoActivo) return;

        const operario = window.AuthModule?.currentUser?.nombre || 'OPERARIO_MES';

        const result = await Swal.fire({
            title: '¿Confirmar Inicio?',
            text: `Vas a iniciar la producción de ${this.trabajoActivo.producto} en la ${this.maquinaSeleccionada}. Operador: ${operario}`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, iniciar'
        });

        if (result.isConfirmed) {
            try {
                mostrarLoading(true);
                const res = await fetchData('/api/mes/iniciar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_programacion: this.trabajoActivo.id_programacion,
                        operario: operario
                    })
                });
                mostrarLoading(false);
                if (res && res.success) {
                    this.actualizarEstadoMaquina();
                } else {
                    Swal.fire('Error', res?.error || 'No se pudo iniciar', 'error');
                }
            } catch (error) {
                mostrarLoading(false);
                console.error('[MES] Error iniciando:', error);
            }
        }
    },

    finalizarTrabajo: async function () {
        const cierres = parseInt(document.getElementById('mes-op-cierres').value);
        if (!cierres || cierres <= 0) {
            Swal.fire('Atenci\u00f3n', 'Debe reportar el n\u00famero de cierres del contador', 'warning');
            return;
        }

        // Obtener la hora actual en formato HH:MM para sugerir como Hora Fin
        const now = new Date();
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        const horaSugerida = `${hh}:${mm}`;

        const { value: formValues } = await Swal.fire({
            title: '\u00bfFinalizar Turno?',
            html: `
                <div class="text-start fs-6 mb-3 text-muted">Se reportar\u00e1n <b>${cierres} cierres</b> de molde. Revisa los tiempos del turno:</div>
                <div class="row text-start p-2 g-3">
                    <div class="col-6">
                        <label class="form-label fw-bold small text-uppercase text-muted mb-1">Hora Inicio Real</label>
                        <input type="time" id="swal-hora-inicio" class="form-control" value="06:00">
                    </div>
                    <div class="col-6">
                        <label class="form-label fw-bold small text-uppercase text-muted mb-1">Hora Fin Real</label>
                        <input type="time" id="swal-hora-fin" class="form-control" value="${horaSugerida}">
                    </div>
                </div>
                <div class="mt-2 small text-muted text-start ps-2"><i class="fas fa-info-circle me-1"></i>La hora de llegada se registrar\u00e1 como 6:00 AM autom\u00e1ticamente.</div>
            `,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonText: '<i class="fas fa-check-circle me-1"></i> Finalizar y Reportar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#16a34a',
            preConfirm: () => {
                const hi = document.getElementById('swal-hora-inicio').value;
                const hf = document.getElementById('swal-hora-fin').value;
                if (!hi || !hf) {
                    Swal.showValidationMessage('Ambas horas son obligatorias');
                    return false;
                }
                return { hora_inicio: hi, hora_fin: hf };
            }
        });

        if (formValues) {
            try {
                mostrarLoading(true);
                const res = await fetchData('/api/mes/reportar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_inyeccion: this.trabajoActivo.id_inyeccion,
                        cierres: cierres,
                        hora_inicio: formValues.hora_inicio,
                        hora_fin: formValues.hora_fin
                    })
                });
                mostrarLoading(false);
                if (res && res.success) {
                    Swal.fire('Reportado', 'El trabajo ha finalizado y pasado a Validación de Paola', 'success');
                    document.getElementById('mes-op-cierres').value = '';
                    await this.actualizarEstadoMaquina();
                    await this.cargarDashboard(); // Refrescar tarjetas de la izquierda
                } else {
                    Swal.fire('Error', res?.error || 'No se pudo reportar', 'error');
                }
            } catch (error) {
                mostrarLoading(false);
                console.error('[MES] Error reportando:', error);
                Swal.fire('Error', 'Error de red al reportar', 'error');
            }
        }
    },





    // --- UTILS ---

    getColorEstado: function (estado) {
        switch (estado) {
            case 'PROGRAMADO': return 'bg-info text-white';
            case 'EN_PROCESO': return 'bg-success text-white';
            case 'PENDIENTE_CALIDAD': return 'bg-warning text-dark';
            case 'FINALIZADO': return 'bg-secondary text-white';
            default: return 'bg-light text-dark';
        }
    },

    actualizarSelect: function (id, datos) {
        const select = document.getElementById(id);
        if (!select) return;
        select.innerHTML = '<option value="">-- Seleccionar --</option>';
        if (datos && Array.isArray(datos)) {
            datos.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item;
                opt.textContent = item;
                select.appendChild(opt);
            });
        }
    }
};

// Auto-inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('inyeccion-page')) {
        ModuloMes.init();
    }
});
