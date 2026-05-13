// ============================================
// pulido.js - Módulo de Pulido (Versión DUAL FINAL - Satélite vs Planta)
// ============================================

const ModuloPulido = {
    productosData: [],
    responsablesData: [],
    selectedProduct: null,
    
    // Pro Mode State
    sesionActiva: false,
    enPausa: false,
    pausaTime: null,
    totalPausaMs: 0,
    tiempoAcumuladoMs: 0, // NUEVO: Tiempo de segmentos anteriores
    timerInterval: null,
    sessionId: null,
    // Descuentos automáticos por pausas programadas (ms)
    descuentoProgramadoMs: 0,

    // PNC Dynamic State
    pncRows: [],
    revueltosRows: [],
    catalogosPnc: {
        'INYECCION': ['RECHUPE', 'FALTA DE MATERIAL', 'QUEMADO', 'REBABA', 'MANCHA', 'BURBUJA'],
        'PULIDO': ['MAL CORTE', 'EXCESO DE PULIDO', 'RAYADO', 'MAL ACABADO', 'GOLPEADO', 'FISURA']
    },

    // Helper de Normalización
    normalizarCodigo: function(c) {
        if (!c) return "";
        return String(c).toUpperCase().replace(/FR-/gi, "").trim();
    },

    // ==========================================================
    // STORAGE NAMESPACING (evita colisiones en tablet compartida)
    // ==========================================================
    getOperarioActual: function () {
        // Prioridad: sesión autenticada -> input -> fallback
        const u = window.AuthModule?.currentUser?.nombre
            || window.AppState?.user?.nombre
            || window.AppState?.user?.name;
        const input = document.getElementById('responsable-pulido-input')?.value;
        const raw = (u || input || '').toString().trim();
        return raw;
    },

    storageKey: function (baseKey) {
        const operario = (this.getOperarioActual() || 'ANON').toString().trim().toUpperCase();
        return `${baseKey}::${operario}`;
    },

    getLastResponsableKey: function () {
        return this.storageKey('pulido_last_responsable');
    },

    getStateKey: function () {
        return this.storageKey('pulido_state');
    },

    // Limpia posibles keys antiguas globales (migración suave)
    limpiarLegacyStorageKeys: function () {
        try {
            if (localStorage.getItem('pulido_state') && !localStorage.getItem(this.getStateKey())) {
                // No migramos: solo evitamos que afecte a otro operario
                localStorage.removeItem('pulido_state');
            }
            if (localStorage.getItem('pulido_last_responsable') && !localStorage.getItem(this.getLastResponsableKey())) {
                localStorage.removeItem('pulido_last_responsable');
            }
        } catch (e) {
            console.warn('[Pulido] No se pudo limpiar legacy keys:', e);
        }
    },

    inicializar: async function () {
        console.log('🔧 [Pulido] Inicializando módulo DUAL FINAL...');
        this.configurarUI();
        await this.cargarDatosMaestros();
        this.initAutocompletes();
        this.limpiarLegacyStorageKeys();
        this.cargarCacheUI();
        await this.verificarTrabajoActivo(); // Rehidratar desde SQL
        this.cargarEstadoLocal(); // Fallback/Sync local
        
        // Verificación de reportes pendientes por fallo de red previo
        this.verificarReportesPendientes();

        // Keep-Alive: Ping al servidor cada 5 min para evitar que Render se duerma
        this.iniciarPingServidor();

        // Sync default mode state based on switch
        const switchEl = document.getElementById('toggle-pulido-mode');
        if (switchEl) {
            this.cambiarModo(switchEl.checked);
        }

        // Si cambia el usuario en el mismo navegador (tablet compartida),
        // cortar intervalos y cargar estado del nuevo operario.
        const onUserReady = () => {
            if (this.timerInterval) clearInterval(this.timerInterval);
            this.timerInterval = null;
            this.cargarCacheUI();
            this.verificarTrabajoActivo().then(() => this.cargarEstadoLocal());
        };
        document.addEventListener('user-ready', onUserReady);
    },

    iniciarPingServidor: function() {
        console.log("📡 [Pulido] Iniciando Keep-Alive (ping cada 5 min)...");
        setInterval(async () => {
            try {
                // Ping silencioso al endpoint de sesión para mantener el servidor despierto
                await fetch('/api/pulido/session_active?ping=true');
            } catch (e) {
                console.warn("[Keep-Alive] Fallo de ping:", e);
            }
        }, 5 * 60 * 1000); // 5 minutos
    },

    verificarReportesPendientes: function() {
        const backup = localStorage.getItem('pulido_failed_report');
        if (backup) {
            Swal.fire({
                title: 'Reporte Pendiente',
                text: 'Se detectó un reporte que no se pudo enviar anteriormente por fallo de red. ¿Deseas intentar enviarlo de nuevo?',
                icon: 'info',
                showCancelButton: true,
                confirmButtonText: 'Sí, reintentar envío',
                cancelButtonText: 'Descartar',
                confirmButtonColor: '#3b82f6'
            }).then(async (result) => {
                if (result.isConfirmed) {
                    const data = JSON.parse(backup);
                    await this.enviarAServidor(data);
                } else if (result.dismiss === Swal.DismissReason.cancel) {
                    localStorage.removeItem('pulido_failed_report');
                }
            });
        }
    },

    guardarEstadoLocal: function() {
        const estado = {
            sesionActiva: this.sesionActiva,
            sessionId: this.sessionId,
            startTime: this.startTime ? this.startTime.getTime() : null,
            totalPausaMs: this.totalPausaMs,
            tiempoAcumuladoMs: this.tiempoAcumuladoMs,
            descuentoProgramadoMs: this.descuentoProgramadoMs || 0,
            enPausa: this.enPausa,
            pausaTime: this.pausaTime ? this.pausaTime.getTime() : null,
            sesionesEnPausa: this.sesionesEnPausa,
            // Guardar quién es el operario para validar al rehidratar
            responsable: document.getElementById('responsable-pulido-input')?.value || '',
            formData: {
                resp: document.getElementById('responsable-pulido-input')?.value,
                prod: document.getElementById('buscador-productos')?.value,
                op: document.getElementById('orden-produccion-pulido')?.value,
                lote: document.getElementById('lote-pulido')?.value
            }
        };
        localStorage.setItem(this.getStateKey(), JSON.stringify(estado));
    },

    cargarEstadoLocal: function() {
        const raw = localStorage.getItem(this.getStateKey());
        if (!raw) return;
        try {
            const estado = JSON.parse(raw);
            if (estado.sesionActiva) {
                // BLINDAJE OPERARIO: Solo rehidratar si el operario guardado
                // coincide con el operario actualmente logueado
                const operarioActual = document.getElementById('responsable-pulido-input')?.value?.trim()
                    || localStorage.getItem(this.getLastResponsableKey()) || '';
                const operarioGuardado = (estado.responsable || estado.formData?.resp || '').trim();

                if (operarioActual && operarioGuardado && operarioActual.toUpperCase() !== operarioGuardado.toUpperCase()) {
                    console.log(`🚫 [Pulido] Estado local pertenece a '${operarioGuardado}' pero el operario actual es '${operarioActual}' — ignorando.`);
                    localStorage.removeItem(this.getStateKey());
                    return;
                }

                // BLINDAJE hora_inicio: No arrancar cronómetro con startTime nulo
                if (!estado.startTime) {
                    console.log('🚫 [Pulido] startTime nulo en estado local — descartando sesión corrupta.');
                    localStorage.removeItem(this.getStateKey());
                    return;
                }

                console.log("♻️ Rehidratando sesión activa de Pulido...");
                this.sesionActiva = true;
                this.sessionId = estado.sessionId;
                this.startTime = new Date(estado.startTime);
                this.totalPausaMs = estado.totalPausaMs;
                this.tiempoAcumuladoMs = estado.tiempoAcumuladoMs || 0;
                this.descuentoProgramadoMs = estado.descuentoProgramadoMs || 0;
                this.enPausa = estado.enPausa;
                if (estado.pausaTime) this.pausaTime = new Date(estado.pausaTime);

                // Restaurar formulario
                if (estado.formData) {
                    const r = document.getElementById('responsable-pulido-input');
                    const p = document.getElementById('buscador-productos');
                    const o = document.getElementById('orden-produccion-pulido');
                    const l = document.getElementById('lote-pulido');
                    if(r) r.value = estado.formData.resp || '';
                    if(p) p.value = estado.formData.prod || '';
                    if(o) o.value = estado.formData.op || '';
                    if(l) l.value = estado.formData.lote || '';
                }

                // UI
                document.getElementById('pulido-idle-msg').style.display = 'none';
                document.getElementById('pulido-active-msg').style.display = 'block';
                document.getElementById('pulido-session-id-display').innerText = this.sessionId;
                
                ['fecha-pulido', 'responsable-pulido-input', 'buscador-productos', 'orden-produccion-pulido', 'lote-pulido'].forEach(id => {
                    const el = document.getElementById(id);
                    if(el) el.disabled = true;
                });

                document.getElementById('btn-iniciar-pulido').disabled = true;
                document.getElementById('btn-pausar-pulido').disabled = false;
                document.getElementById('btn-terminar-pulido').disabled = false;
                document.getElementById('btn-cambiar-ref-pulido').style.display = 'block';

                if (this.enPausa) {
                    const btn = document.getElementById('btn-pausar-pulido');
                    btn.innerHTML = '<i class="fas fa-play me-2"></i> Reanudar';
                    btn.className = 'btn btn-info btn-lg p-3 shadow';
                    document.getElementById('pulido-pausa-msg').style.display = 'block';
                }
                this.timerInterval = setInterval(() => this.actualizarTimer(), 1000);
            }
            if (estado.sesionesEnPausa && estado.sesionesEnPausa.length > 0) {
                this.sesionesEnPausa = estado.sesionesEnPausa;
                this.renderCola();
            }
        } catch (e) {
            console.error("Error rehidratando:", e);
            localStorage.removeItem(this.getStateKey());
        }
    },

    sesionesEnPausa: [],

    configurarUI: function () {
        // Set fecha de hoy por defecto y sincronizar Lote
        const fechaInput = document.getElementById('fecha-pulido');
        const loteInput = document.getElementById('lote-pulido');

        if (fechaInput) {
            fechaInput.value = new Date().toISOString().split('T')[0];
        }
        if (loteInput && !loteInput.value) {
            loteInput.value = new Date().toISOString().split('T')[0];
        }
        
        // Reset manual display
        this.actualizarCalculoManual();

        // Sincronizar encabezado "Trabajando en" en tiempo real
        const actualizarHeader = () => {
            const prodRaw = document.getElementById('buscador-productos')?.value || '---';
            const prod = this.normalizarCodigo(prodRaw) || '---';
            const lote = document.getElementById('lote-pulido')?.value || '---';
            const display = document.getElementById('current-pulido-job');
            if (display && this.sesionActiva) {
                display.innerText = `${prod} | Lote: ${lote}`;
            }
        };

        ['responsable-pulido-input', 'buscador-productos', 'lote-pulido'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', () => {
                    actualizarHeader();
                    this.validarBotonInicioPro();
                });
                el.addEventListener('change', () => {
                    actualizarHeader();
                    this.validarBotonInicioPro();
                });
            }
        });

        this.validarBotonInicioPro();
        this.renderCola();
    },

    validarBotonInicioPro: function() {
        const resp = document.getElementById('responsable-pulido-input')?.value?.trim();
        const prod = document.getElementById('buscador-productos')?.value?.trim();
        const lote = document.getElementById('lote-pulido')?.value?.trim();
        const btn = document.getElementById('btn-iniciar-pulido');
        
        if (btn) {
            if (resp && prod && lote && !this.sesionActiva) {
                btn.disabled = false;
            } else {
                btn.disabled = true;
            }
        }
    },

    cambiarModo: function (isPro) {
        console.log("🔄 Cambiando a Modo:", isPro ? "PRO (Planta)" : "MANUAL (Satélite)");
        const panelManual = document.getElementById('panel-pulido-manual');
        const panelPro = document.getElementById('panel-pulido-pro');
        
        if (isPro) {
            panelManual.style.display = 'none';
            panelPro.style.display = 'block';
        } else {
            panelManual.style.display = 'block';
            panelPro.style.display = 'none';
        }
    },

    verificarTrabajoActivo: async function() {
        const resp = document.getElementById('responsable-pulido-input')?.value || localStorage.getItem(this.getLastResponsableKey());
        if (!resp) return;

        try {
            console.log(`📡 [Pulido] Validando estado de sesión en servidor para: ${resp}...`);
            const res = await fetch(`/api/pulido/session_active?responsable=${encodeURIComponent(resp)}`);
            const data = await res.json();
            
            if (data.success && data.session) {
                // FIX Efecto Daniela: Solo cargar si el estado es genuinamente activo
                const estado = (data.session.estado || '').toUpperCase();
                if (!['EN_PROCESO', 'PAUSADO', 'PAUSADO_COLA', 'TRABAJANDO'].includes(estado)) {
                    console.log("🚫 [Pulido] Sesión encontrada pero estado='" + estado + "' — NO es activa, ignorando.");
                    this.limpiarGhostState(resp);
                    return;
                }

                // BLINDAJE hora_inicio nula: No arrancar cronómetro sin hora válida
                if (!data.session.hora_inicio_dt) {
                    console.log('🚫 [Pulido] Sesión activa sin hora_inicio — cronómetro no arrancará.');
                    return;
                }

                console.log("✅ [Pulido] Sesión activa confirmada en SQL:", data.session);
                this.sesionActiva = true;
                this.sessionId = data.session.id_pulido;
                this.startTime = new Date(data.session.hora_inicio_dt);
                this.tiempoAcumuladoMs = (data.session.duracion_segundos || 0) * 1000;
                
                // Poblar UI
                const rInput = document.getElementById('responsable-pulido-input');
                if (rInput) rInput.value = resp;
                const p = document.getElementById('buscador-productos');
                const o = document.getElementById('orden-produccion-pulido');
                const l = document.getElementById('lote-pulido');
                if(p) p.value = data.session.codigo;
                if(o) o.value = data.session.orden_produccion;
                if(l) l.value = data.session.lote;

                this.continuarUIActiva();
            } else {
                // SINCRONIZACIÓN ESTRICTA: El backend dice que no hay nada activo
                console.log(`🧹 [Pulido] Sincronización: No hay trabajos activos para '${resp}' en DB. Limpiando caché local.`);
                this.limpiarGhostState(resp);
            }
        } catch (e) {
            console.error("Error recuperando sesión SQL:", e);
        }
    },

    limpiarGhostState: function(operario) {
        const key = this.getStateKey();
        if (localStorage.getItem(key)) {
            console.warn(`[Pulido] Eliminando Ghost State detectado para: ${operario}`);
            localStorage.removeItem(key);
            // Si la UI estaba activa por un error de flujo previo, resetearla
            if (this.sesionActiva) {
                this.limpiarSesionLocal();
            }
        }
    },

    continuarUIActiva: function() {
        document.getElementById('pulido-idle-msg').style.display = 'none';
        document.getElementById('pulido-active-msg').style.display = 'block';
        document.getElementById('pulido-session-id-display').innerText = this.sessionId;
        
        ['fecha-pulido', 'responsable-pulido-input', 'buscador-productos', 'orden-produccion-pulido', 'lote-pulido'].forEach(id => {
            const el = document.getElementById(id);
            if(el) el.disabled = true;
        });

        document.getElementById('btn-iniciar-pulido').disabled = true;
        document.getElementById('btn-pausar-pulido').disabled = false;
        document.getElementById('btn-terminar-pulido').disabled = false;
        document.getElementById('btn-cambiar-ref-pulido').style.display = 'block';

        if (this.timerInterval) clearInterval(this.timerInterval);
        this.timerInterval = setInterval(() => this.actualizarTimer(), 1000);
        this.guardarEstadoLocal();
        this.mostrarFotoProducto();
    },

    // ==========================================
    // LÓGICA MODO PRO (PLANTA)
    // ==========================================
    
    iniciarCiclo: function () {
        const respInput = document.getElementById('responsable-pulido-input');
        const prodInput = document.getElementById('buscador-productos');
        const loteInput = document.getElementById('lote-pulido');
        
        const resp = respInput?.value?.trim();
        const prodRaw = prodInput?.value?.trim();
        const prod = this.normalizarCodigo(prodRaw);
        const lote = loteInput?.value?.trim();
        
        if (!resp || !prod || !lote) {
            Swal.fire({
                title: 'Campos Incompletos',
                text: 'Por favor, selecciona Responsable, Referencia y Lote antes de iniciar el cronómetro de planta.',
                icon: 'warning',
                confirmButtonColor: '#3b82f6'
            });
            return;
        }

        // Bloquear campos compartidos
        ['fecha-pulido', 'responsable-pulido-input', 'buscador-productos', 'orden-produccion-pulido', 'lote-pulido'].forEach(id => {
            const el = document.getElementById(id);
            if(el) el.disabled = true;
        });

        this.sesionActiva = true;
        this.enPausa = false;
        
        // Si no hay startTime, es una sesión nueva
        if (!this.startTime) {
            this.startTime = new Date();
            this.totalPausaMs = 0;
            this.tiempoAcumuladoMs = 0;
        }

        // Mostrar Foto (NUEVO)
        this.mostrarFotoProducto();
        
        if (!this.sessionId) this.sessionId = 'PUL-' + Math.random().toString(36).substr(2, 9).toUpperCase();
        
        document.getElementById('pulido-idle-msg').style.display = 'none';
        document.getElementById('pulido-active-msg').style.display = 'block';
        document.getElementById('current-pulido-job').innerText = `${prod} | Lote: ${lote}`;
        document.getElementById('pulido-session-id-display').innerText = this.sessionId;
        
        document.getElementById('btn-iniciar-pulido').disabled = true;
        document.getElementById('btn-pausar-pulido').disabled = false;
        document.getElementById('btn-terminar-pulido').disabled = false;
        
        const btnUrgencia = document.getElementById('btn-cambiar-ref-pulido');
        if (btnUrgencia) btnUrgencia.style.display = 'block';

        if (this.timerInterval) clearInterval(this.timerInterval);
        this.timerInterval = setInterval(() => this.actualizarTimer(), 1000);
        
        // PERSISTENCIA INMEDIATA EN SQL
        this.persistirInicioSQL(resp, prod, lote, document.getElementById('orden-produccion-pulido')?.value);
        
        this.guardarEstadoLocal();
    },

    persistirInicioSQL: async function(resp, prod, lote, op) {
        const data = {
            id_pulido: this.sessionId,
            responsable: resp,
            codigo_producto: prod,
            lote: lote,
            orden_produccion: op || 'SIN OP',
            estado: 'TRABAJANDO',
            hora_inicio: this.startTime.getHours() + ':' + String(this.startTime.getMinutes()).padStart(2, '0'),
            fecha_inicio: this.startTime.toISOString().split('T')[0]
        };

        try {
            await fetch('/api/pulido', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            console.log("✅ [Pulido] Inicio persistido en SQL inmediatamente.");
        } catch (e) {
            console.error("Error persistencia inmediata:", e);
        }
    },

    actualizarTimer: function () {
        if (this.enPausa) return;

        // BLINDAJE: Si startTime es nulo/inválido, mostrar 00:00:00 estático
        if (!this.startTime || isNaN(this.startTime.getTime())) {
            document.getElementById('pulido-main-timer').innerText = '00:00:00';
            return;
        }
        
        const now = new Date();
        const diffMs = (now - this.startTime - (this.totalPausaMs || 0)) + (this.tiempoAcumuladoMs || 0);
        
        // Protección contra valores negativos (por drift de reloj)
        const safeDiff = Math.max(0, diffMs);
        const hrs = String(Math.floor(safeDiff / 3600000)).padStart(2, '0');
        const mins = String(Math.floor((safeDiff % 3600000) / 60000)).padStart(2, '0');
        const secs = String(Math.floor((safeDiff % 60000) / 1000)).padStart(2, '0');
        
        document.getElementById('pulido-main-timer').innerText = `${hrs}:${mins}:${secs}`;
    },

    pausarCiclo: function () {
        const btn = document.getElementById('btn-pausar-pulido');
        if (!this.enPausa) {
            this.enPausa = true;
            this.pausaTime = new Date();
            btn.innerHTML = '<i class="fas fa-play me-2"></i> Reanudar';
            btn.className = 'btn btn-info btn-lg p-3 shadow';
            document.getElementById('pulido-pausa-msg').style.display = 'block';
        } else {
            this.enPausa = false;
            this.totalPausaMs += (new Date() - this.pausaTime);
            btn.innerHTML = '<i class="fas fa-pause me-2"></i> Pausar';
            btn.className = 'btn btn-warning btn-lg p-3 shadow';
            document.getElementById('pulido-pausa-msg').style.display = 'none';
        }
        this.guardarEstadoLocal();
    },

    habilitarCambioReferencia: function() {
        Swal.fire({
            title: 'Multitarea / Urgencia',
            text: '¿Qué deseas hacer con el trabajo actual?',
            icon: 'question',
            showCancelButton: true,
            showDenyButton: true,
            confirmButtonColor: '#10b981',
            denyButtonColor: '#3b82f6',
            cancelButtonColor: '#6b7280',
            confirmButtonText: 'Reportar y Terminar',
            denyButtonText: 'Pausar y Enviar a Cola',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                this.prepararReporteFinal();
            } else if (result.isDenied) {
                this.enviarACola();
            }
        });
    },

    enviarACola: async function() {
        if (this.timerInterval) clearInterval(this.timerInterval);
        
        const now = new Date();
        const segmentTime = now - this.startTime - this.totalPausaMs;
        const descuentoSegmento = this.calcularDescuentoProgramadoMs(this.startTime, now);
        const totalElapsedMs = this.tiempoAcumuladoMs + segmentTime;
        const totalDescuentoProgramadoMs = (this.descuentoProgramadoMs || 0) + descuentoSegmento;

        const prodRaw = document.getElementById('buscador-productos').value;
        const prod = this.normalizarCodigo(prodRaw);
        const op = document.getElementById('orden-produccion-pulido').value;
        const lote = document.getElementById('lote-pulido').value;
        const resp = document.getElementById('responsable-pulido-input').value;

        const sessionToPause = {
            sessionId: this.sessionId,
            prod,
            op,
            lote,
            resp,
            tiempoAcumuladoMs: totalElapsedMs,
            descuentoProgramadoMs: totalDescuentoProgramadoMs
        };

        // Guardado preventivo en DB
        const dataPreventiva = {
            id_pulido: this.sessionId,
            codigo_producto: prod,
            responsable: resp,
            orden_produccion: op,
            lote: lote,
            estado: 'PAUSADO_COLA',
            cantidad_real: 0,
            hora_inicio: this.startTime.getHours() + ':' + String(this.startTime.getMinutes()).padStart(2, '0')
        };

        mostrarLoading(true, 'Enviando trabajo a la cola...');
        await this.enviarAServidor(dataPreventiva);
        mostrarLoading(false);

        this.sesionesEnPausa.push(sessionToPause);
        
        // Reset local para nueva urgencia
        this.limpiarSesionLocal();
        this.descuentoProgramadoMs = totalDescuentoProgramadoMs; // conservar acumulado para el operario
        this.renderCola();
        this.guardarEstadoLocal();

        Swal.fire({
            title: 'Trabajo en Cola',
            text: `El trabajo ${prod} se ha pausado. Ahora puedes iniciar la urgencia.`,
            icon: 'info',
            timer: 3000,
            toast: true,
            position: 'top-end',
            showConfirmButton: false
        });
    },

    renderCola: function() {
        const container = document.getElementById('pulido-queue-container');
        const list = document.getElementById('pulido-queue-list');
        
        if (this.sesionesEnPausa.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';
        list.innerHTML = this.sesionesEnPausa.map((s, index) => `
            <div class="card border-start border-primary border-4 shadow-sm mb-2">
                <div class="card-body p-2 d-flex justify-content-between align-items-center">
                    <div>
                        <div class="fw-bold text-dark" style="font-size: 0.85rem;">${s.prod}</div>
                        <div class="text-muted" style="font-size: 0.7rem;">OP: ${s.op || 'N/A'} | Lote: ${s.lote}</div>
                    </div>
                    <button class="btn btn-sm btn-outline-primary" onclick="ModuloPulido.retomarSesion(${index})">
                        <i class="fas fa-undo me-1"></i> Retomar
                    </button>
                </div>
            </div>
        `).join('');
    },

    retomarSesion: function(index) {
        if (this.sesionActiva) {
            Swal.fire('Atención', 'Debes terminar o pausar el trabajo actual antes de retomar uno de la cola.', 'warning');
            return;
        }

        const s = this.sesionesEnPausa[index];
        
        // Restaurar datos
        document.getElementById('buscador-productos').value = s.prod;
        document.getElementById('orden-produccion-pulido').value = s.op;
        document.getElementById('lote-pulido').value = s.lote;
        document.getElementById('responsable-pulido-input').value = s.resp;
        
        this.sessionId = s.sessionId;
        this.tiempoAcumuladoMs = s.tiempoAcumuladoMs;
        this.descuentoProgramadoMs = s.descuentoProgramadoMs || 0;
        this.startTime = new Date(); // El nuevo segmento empieza AHORA
        this.totalPausaMs = 0; // Reset pausas del nuevo segmento
        
        // Quitar de la cola
        this.sesionesEnPausa.splice(index, 1);
        this.renderCola();
        
        // Iniciar ciclo con datos restaurados
        this.iniciarCiclo();
        this.guardarEstadoLocal();
    },

    limpiarSesionLocal: function() {
        clearInterval(this.timerInterval);
        this.sesionActiva = false;
        this.sessionId = null;
        this.startTime = null;
        this.totalPausaMs = 0;
        this.tiempoAcumuladoMs = 0;
        // NOTA: descuentoProgramadoMs se conserva por operario para sesiones multi-segmento
        this.enPausa = false;

        document.getElementById('pulido-idle-msg').style.display = 'block';
        document.getElementById('pulido-active-msg').style.display = 'none';
        document.getElementById('pulido-main-timer').innerText = '00:00:00';
        document.getElementById('btn-iniciar-pulido').disabled = true;
        
        // Limpiar campos para nueva entrada
        document.getElementById('buscador-productos').value = '';
        document.getElementById('orden-produccion-pulido').value = '';
        
        // Desbloquear campos
        ['responsable-pulido-input', 'buscador-productos', 'orden-produccion-pulido', 'lote-pulido'].forEach(id => {
            const el = document.getElementById(id);
            if(el) el.disabled = false;
        });
    },



    prepararReporteFinal: function () {
        // DETENER CRONÓMETRO INMEDIATAMENTE PARA EXACTITUD (Bug Fix)
        if (this.sesionActiva && !this.enPausa) {
            console.log("⏱️ [Pulido] Deteniendo cronómetro para reporte final...");
            this.pausarCiclo();
        }

        const now = new Date();
        
        // El tiempo total es la suma de lo acumulado (sesiones previas) + el segmento actual
        const msSegmentoActual = this.startTime ? (now - this.startTime - this.totalPausaMs) : 0;
        const msTotales = this.tiempoAcumuladoMs + msSegmentoActual;
        const descuentoSegmento = (this.startTime ? this.calcularDescuentoProgramadoMs(this.startTime, now) : 0);
        const descuentoTotal = (this.descuentoProgramadoMs || 0) + descuentoSegmento;
        const msEfectivos = Math.max(0, msTotales - descuentoTotal);
        
        const totalMin = Math.floor(msTotales / 60000);
        const totalSec = Math.floor(msTotales / 1000);
        const efectivoMin = Math.floor(msEfectivos / 60000);
        const efectivoSec = Math.floor(msEfectivos / 1000);
        
        // Validación flexible: 30 segundos para urgencias/retomados, 1 min para nuevos
        const umbralSegundos = (this.tiempoAcumuladoMs > 0) ? 10 : 30; 

        if (totalSec < umbralSegundos) {
            Swal.fire({
                title: 'Tiempo Insuficiente',
                text: `La sesión debe durar al menos ${umbralSegundos} segundos. Tiempo actual: ${totalSec}s`,
                icon: 'error',
                confirmButtonColor: '#d33'
            });
            return;
        }

        document.getElementById('modal-tiempo-total').innerText = totalMin + ' min ' + (totalSec % 60) + 's';
        document.getElementById('modal-tiempo-efectivo').innerText =
            `${efectivoMin} min ${(efectivoSec % 60)}s`;

        // Mostrar descuento programado si aplica (sin depender de HTML preexistente)
        const descuentoMin = Math.floor(descuentoTotal / 60000);
        const descuentoSec = Math.floor(descuentoTotal / 1000);
        this._renderDescuentoProgramadoUI(descuentoTotal, descuentoMin, descuentoSec);
        
        // Reset inputs modal
        document.getElementById('cantidad-recibida-pro').value = 0;
        this.pncRows = []; // Reiniciar PNC dinámico
        this.renderPncRows();
        document.getElementById('resultado-buenas-pro').innerText = '0';
        
        document.getElementById('modal-reporte-final').style.display = 'flex';
    },

    // ==========================================
    // GESTIÓN DE PNC DINÁMICO
    // ==========================================

    agregarFilaPnc: function() {
        // Validar que la última fila tenga datos antes de añadir otra (opcional, pero ayuda a la limpieza)
        if (this.pncRows.length > 0) {
            const lastRow = this.pncRows[this.pncRows.length - 1];
            if (!lastRow.cantidad || lastRow.cantidad <= 0 || !lastRow.criterio) {
                Swal.fire({
                    title: 'Fila incompleta',
                    text: 'Por favor complete la información de la fila de PNC actual antes de añadir una nueva.',
                    icon: 'warning',
                    toast: true,
                    position: 'top-end',
                    timer: 3000,
                    showConfirmButton: false
                });
                return;
            }
        }

        this.pncRows.push({
            proceso: 'PULIDO',
            cantidad: 0,
            criterio: ''
        });
        this.renderPncRows();
    },

    eliminarFilaPnc: function(index) {
        this.pncRows.splice(index, 1);
        this.renderPncRows();
        this.actualizarCalculoPro();
    },

    renderPncRows: function() {
        const container = document.getElementById('pnc-dynamic-container');
        if (!container) return;

        if (this.pncRows.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-2 small" id="pnc-empty-msg">No hay PNC reportado</div>';
            return;
        }

        container.innerHTML = this.pncRows.map((row, index) => `
            <div class="d-flex gap-1 align-items-center p-2 border-bottom bg-white rounded shadow-sm animate__animated animate__fadeInIn">
                <select class="form-select form-select-sm" style="width: 30%;" onchange="ModuloPulido.updateRow(${index}, 'proceso', this.value)">
                    <option value="PULIDO" ${row.proceso === 'PULIDO' ? 'selected' : ''}>Pulido</option>
                    <option value="INYECCION" ${row.proceso === 'INYECCION' ? 'selected' : ''}>Inyección</option>
                </select>
                <input type="number" class="form-control form-control-sm text-center fw-bold" style="width: 20%;" 
                    value="${row.cantidad}" min="1" placeholder="Cant"
                    oninput="ModuloPulido.updateRow(${index}, 'cantidad', this.value)">
                <select class="form-select form-select-sm" style="width: 40%;" onchange="ModuloPulido.updateRow(${index}, 'criterio', this.value)">
                    <option value="">- Motivo -</option>
                    ${(this.catalogosPnc[row.proceso] || []).map(c => `
                        <option value="${c}" ${row.criterio === c ? 'selected' : ''}>${c}</option>
                    `).join('')}
                </select>
                <button type="button" class="btn btn-sm btn-link text-danger p-0" style="width: 10%;" onclick="ModuloPulido.eliminarFilaPnc(${index})">
                    <i class="fas fa-times-circle"></i>
                </button>
            </div>
        `).join('');
    },

    updateRow: function(index, field, value) {
        if (field === 'cantidad') {
            const val = parseInt(value, 10);
            if (val < 0) {
                Swal.fire('Cantidad inválida', 'No se permiten cantidades negativas en PNC', 'error');
                this.pncRows[index].cantidad = 0;
            } else {
                this.pncRows[index].cantidad = val || 0;
            }
        } else {
            this.pncRows[index][field] = value;
        }
        
        // Si cambió el proceso, resetear el criterio para que coincida con el nuevo catálogo
        if (field === 'proceso') {
            this.pncRows[index].criterio = '';
            this.renderPncRows();
        }
        
        this.actualizarCalculoPro();
    },

    // ==========================================
    // CÁLCULOS EN TIEMPO REAL (REQUISITO)
    // ==========================================
    
    actualizarCalculoManual: function() {
        const brutoInput = document.getElementById('cantidad-recibida-pulido');
        const pncInyInput = document.getElementById('manual-pnc-iny');
        const pncPulInput = document.getElementById('manual-pnc-pul');
        const display = document.getElementById('manual-bujes-buenos');
        
        if (!brutoInput) return;
        
        const recibida = parseInt(brutoInput.value, 10) || 0;
        const pncIny = parseInt(pncInyInput?.value, 10) || 0;
        const pncPul = parseInt(pncPulInput?.value, 10) || 0;
        
        const buenas = Math.max(0, recibida - pncIny - pncPul);
        
        console.log(`[Pulido Manual] Bruto: ${recibida}, PNC_Iny: ${pncIny}, PNC_Pul: ${pncPul} -> Total Buenos: ${buenas}`);
        
        if (display) display.innerText = buenas;
    },

    actualizarCalculoPro: function() {
        const display = document.getElementById('resultado-buenas-pro');
        const buenosInput = document.getElementById('cantidad-recibida-pro');
        if (!buenosInput) return;
        
        const buenos = parseFloat(buenosInput.value) || 0;
        
        // Sincronizar pncRows desde el DOM y calcular total
        let totalPnc = 0;
        this.pncRows.forEach(row => {
            const input = document.getElementById(`pnc-cant-${row.id}`);
            if (input) {
                row.cantidad = parseFloat(input.value) || 0;
                totalPnc += row.cantidad;
            }
        });
        
        const totalBruto = buenos + totalPnc;
        
        if (display) display.innerText = totalBruto;
    },

    // ==========================================
    // GUARDADO DE DATOS
    // ==========================================

    guardarReportePro: async function () {
        const now = new Date();
        const descuentoSegmento = (this.startTime ? this.calcularDescuentoProgramadoMs(this.startTime, now) : 0);
        const descuentoTotal = (this.descuentoProgramadoMs || 0) + descuentoSegmento;
        const detalleDescuento = this.generarDetalleDescuentoProgramado(this.startTime, now);

        // Agrupar PNC por proceso para compatibilidad con DB
        const pncData = this.pncRows.map(row => ({
            proceso: document.getElementById(`pnc-proc-${row.id}`)?.value,
            cantidad: parseFloat(document.getElementById(`pnc-cant-${row.id}`)?.value || 0),
            criterio: document.getElementById(`pnc-crit-${row.id}`)?.value
        })).filter(p => p.cantidad > 0);

        // Bujes Revueltos (NUEVO)
        const revueltosData = this.revueltosRows.map(row => ({
            id_codigo: document.getElementById(`rev-cod-${row.id}`)?.value,
            cantidad: parseFloat(document.getElementById(`rev-cant-${row.id}`)?.value || 0)
        })).filter(r => r.cantidad > 0 && r.id_codigo);

        const data = {
            id_pulido: this.sessionId,
            fecha_inicio: document.getElementById('fecha-pulido')?.value || new Date().toISOString().split('T')[0],
            hora_inicio: this.startTime ? (this.startTime.getHours() + ':' + String(this.startTime.getMinutes()).padStart(2, '0')) : '00:00',
            hora_fin: new Date().getHours() + ':' + String(new Date().getMinutes()).padStart(2, '0'),
            responsable: document.getElementById('responsable-pulido-input').value,
            codigo_producto: this.normalizarCodigo(document.getElementById('buscador-productos').value),
            
            // NUEVA LÓGICA: cantidad_real son las buenas, cantidad_recibida es el total (bruto)
            cantidad_real: parseFloat(document.getElementById('cantidad-recibida-pro')?.value || 0),
            cantidad_recibida: parseFloat(document.getElementById('resultado-buenas-pro')?.innerText || 0),
            
            pnc_inyeccion: pncData.filter(p => p.proceso === 'INYECCION').reduce((a, b) => a + b.cantidad, 0),
            pnc_pulido: pncData.filter(p => p.proceso === 'PULIDO').reduce((a, b) => a + b.cantidad, 0),
            criterio_pnc_inyeccion: pncData.filter(p => p.proceso === 'INYECCION').map(p => `${p.criterio} (${p.cantidad})`).join(', '),
            criterio_pnc_pulido: pncData.filter(p => p.proceso === 'PULIDO').map(p => `${p.criterio} (${p.cantidad})`).join(', '),
            
            observaciones: (document.getElementById('observaciones-pro')?.value || ''),
            
            orden_produccion: document.getElementById('orden-produccion-pulido')?.value || '',
            lote: document.getElementById('lote-pulido')?.value || '',
            departamento: 'PULIDO',
            almacen_destino: 'P. TERMINADO',
            modo: 'PRO',
            tiempo_acumulado_ms: this.tiempoAcumuladoMs,
            descuento_programado_ms: descuentoTotal,
            detalle_descuento_programado: detalleDescuento,
            pnc_detail: pncData,
            revueltos: revueltosData
        };

        // Validación de filas completas
        if (pncData.some(r => !r.cantidad || r.cantidad <= 0 || !r.criterio)) {
            Swal.fire('PNC Incompleto', 'Todas las filas de PNC deben tener cantidad y motivo seleccionado.', 'warning');
            return;
        }

        // Validación de consistencia
        const totalCalculado = data.cantidad_real + pncData.reduce((s, r) => s + r.cantidad, 0);
        
        if (totalCalculado !== data.cantidad_recibida) {
            Swal.fire('Error de Consistencia', 'La suma de piezas buenas y PNC no coincide con el total. Por favor revise los datos.', 'error');
            return;
        }

        if (!data.responsable || !data.codigo_producto || data.cantidad_real < 0) {
            Swal.fire('Atención', 'Faltan campos obligatorios o hay valores negativos', 'warning');
            return;
        }

        await this.enviarAServidor(data);
    },

    registrarPulidoTradicional: async function () {
        const horaInicio = document.getElementById('hora-inicio-pulido')?.value || '00:00';
        const horaFin = document.getElementById('hora-fin-pulido')?.value || '00:00';

        if (horaFin <= horaInicio) {
            Swal.fire({
                title: 'Error de Tiempos',
                text: 'La Hora de Fin debe ser estrictamente posterior a la Hora de Inicio.',
                icon: 'error',
                confirmButtonColor: '#d33'
            });
            return;
        }

        const data = {
            fecha_inicio: document.getElementById('fecha-pulido')?.value || new Date().toISOString().split('T')[0],
            responsable: document.getElementById('responsable-pulido-input').value,
            hora_inicio: document.getElementById('hora-inicio-pulido')?.value || '00:00',
            hora_fin: document.getElementById('hora-fin-pulido')?.value || '00:00',
            codigo_producto: this.normalizarCodigo(document.getElementById('buscador-productos').value),
            orden_produccion: document.getElementById('orden-produccion-pulido')?.value || '',
            lote: document.getElementById('lote-pulido')?.value || '',
            departamento: 'PULIDO',
            almacen_destino: 'P. TERMINADO',
            cantidad_recibida: parseInt(document.getElementById('cantidad-recibida-pulido').value, 10) || 0,
            pnc_inyeccion: parseInt(document.getElementById('manual-pnc-iny').value, 10) || 0,
            pnc_pulido: parseInt(document.getElementById('manual-pnc-pul').value, 10) || 0,
            criterio_pnc_inyeccion: document.getElementById('manual-criterio-iny').value,
            criterio_pnc_pulido: document.getElementById('manual-criterio-pul').value,
            cantidad_real: parseInt(document.getElementById('manual-bujes-buenos').innerText, 10) || 0,
            observaciones: document.getElementById('observaciones-pulido').value,
            modo: 'MANUAL'
        };

        if (!data.responsable || !data.codigo_producto || !data.cantidad_recibida || data.cantidad_recibida <= 0) {
            Swal.fire('Atención', 'Faltan campos obligatorios', 'warning');
            return;
        }

        await this.enviarAServidor(data);
    },

    enviarAServidor: async function (data) {
        try {
            if (!navigator.onLine) {
                throw new Error("No hay conexión a internet (Modo Offline)");
            }

            Swal.showLoading();
            // Usar el apiClient robusto que ya implementa 3 reintentos
            const result = await window.apiClient.post('/pulido', data);

            if (result.success) {
                Swal.fire('¡Éxito!', 'Producción guardada correctamente.', 'success');
                localStorage.removeItem('pulido_failed_report'); // Limpiar backup si existía
                
                this.terminarCiclo();
                this.limpiarSesionLocal(); 
                
                const modal = document.getElementById('modal-reporte-final');
                if (modal) modal.style.display = 'none';
                this.limpiarFormulario();
            } else {
                console.warn("Servidor rechazó el reporte:", result.error);
                throw new Error(result.error || 'Error desconocido del servidor');
            }
        } catch (error) {
            console.error("Error crítico al guardar:", error);
            
            // Persistencia Local (LocalStorage) ante fallos
            localStorage.setItem('pulido_failed_report', JSON.stringify(data));

            const isServerError = error.message.includes('HTTP');
            const errorMsg = isServerError ? error.message : 'No se pudo contactar al servidor tras varios intentos.';

            Swal.fire({
                title: isServerError ? 'Error del Servidor' : 'Fallo de Conexión',
                text: `${errorMsg} El reporte se guardó LOCALMENTE en la tablet. Puedes reintentar ahora o cerrar para intentarlo más tarde.`,
                icon: 'error',
                showCancelButton: true,
                confirmButtonText: 'Reintentar Ahora',
                cancelButtonText: 'Guardar y Cerrar',
                confirmButtonColor: '#3b82f6'
            }).then((result) => {
                if (result.isConfirmed) {
                    this.enviarAServidor(data);
                } else {
                    // Si deciden cerrar, limpiamos la UI pero el reporte queda en 'pulido_failed_report'
                    this.limpiarSesionLocal();
                    const modal = document.getElementById('modal-reporte-final');
                    if (modal) modal.style.display = 'none';
                    location.reload();
                }
            });
        }
    },

    terminarCiclo: function() {
        if (this.timerInterval) clearInterval(this.timerInterval);
        this.sesionActiva = false;
        this.sessionId = null;
        this.startTime = null;
        this.totalPausaMs = 0;
        this.tiempoAcumuladoMs = 0;
        this.enPausa = false;

        document.getElementById('pulido-active-msg').style.display = 'none';
        document.getElementById('pulido-idle-msg').style.display = 'block';
        document.getElementById('btn-iniciar-pulido').disabled = false;
        document.getElementById('btn-pausar-pulido').disabled = true;
        document.getElementById('btn-terminar-pulido').disabled = true;
        document.getElementById('pulido-main-timer').innerText = '00:00:00';
        
        // Desbloquear campos compartidos
        ['fecha-pulido', 'responsable-pulido-input', 'buscador-productos', 'orden-produccion-pulido', 'lote-pulido'].forEach(id => {
            const el = document.getElementById(id);
            if(el) el.disabled = false;
        });

        const btnUrgencia = document.getElementById('btn-cambiar-ref-pulido');
        if (btnUrgencia) btnUrgencia.style.display = 'none';

        this.validarBotonInicioPro();
        this.guardarEstadoLocal();

        // Ocultar Foto (NUEVO)
        const photoContainer = document.getElementById('pulido-product-photo-container');
        if (photoContainer) photoContainer.style.display = 'none';

        // Preguntar por trabajos en cola
        if (this.sesionesEnPausa.length > 0) {
            const proxima = this.sesionesEnPausa[0];
            Swal.fire({
                title: '¿Retomar pendiente?',
                text: `Tienes un trabajo en cola: ${proxima.prod}. ¿Deseas retomarlo ahora?`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Sí, retomar',
                cancelButtonText: 'No, después'
            }).then(r => {
                if (r.isConfirmed) {
                    this.retomarSesion(0);
                }
            });
        }
    },

    // ==========================================
    // HELPERS
    // ==========================================

    cargarDatosMaestros: async function () {
        try {
            // Responsables
            const resp = await fetch('/api/obtener_responsables').then(r => r.json());
            this.responsablesData = resp || [];
            
            // Productos (Usa AppState si existe, sino fetch)
            if (window.AppState?.sharedData?.productos?.length > 0) {
                this.productosData = window.AppState.sharedData.productos;
            } else {
                const prods = await fetch('/api/productos/listar').then(r => r.json());
                this.productosData = prods?.items || prods?.productos || [];
            }
        } catch (e) { console.error("Error maestros:", e); }
    },

    initAutocompletes: function () {
        const inputResp = document.getElementById('responsable-pulido-input');
        const suggestionsResp = document.getElementById('pulido-responsable-suggestions');
        
        if (inputResp && suggestionsResp) {
            inputResp.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase();
                if (!query) { suggestionsResp.classList.remove('active'); return; }
                const resultados = this.responsablesData.filter(resp => 
                    (typeof resp === 'string' ? resp : (resp.nombre || '')).toLowerCase().includes(query)
                ).slice(0, 5);
                this.renderSuggestions(suggestionsResp, resultados, (item) => {
                    const val = typeof item === 'object' ? item.nombre : item;
                    inputResp.value = val;
                    localStorage.setItem(this.getLastResponsableKey(), val);
                    suggestionsResp.classList.remove('active');
                    inputResp.dispatchEvent(new Event('input'));
                });
            });
        }

        const inputProd = document.getElementById('buscador-productos');
        const suggestionsProd = document.getElementById('pulido-producto-suggestions');
        if (inputProd && suggestionsProd) {
            inputProd.addEventListener('input', (e) => {
                const query = e.target.value.trim().toLowerCase();
                if (query.length < 2) { suggestionsProd.classList.remove('active'); return; }
                const resultados = this.productosData.filter(p => 
                    String(p.codigo_sistema || '').toLowerCase().includes(query) || 
                    String(p.descripcion || '').toLowerCase().includes(query)
                ).slice(0, 10);
                this.renderSuggestions(suggestionsProd, resultados, (p) => {
                    inputProd.value = p.codigo_sistema;
                    this.selectedProduct = p; // Guardar para el cronómetro
                    suggestionsProd.classList.remove('active');
                    inputProd.dispatchEvent(new Event('input'));
                    
                    // Si ya está en modo PRO y la sesión no ha iniciado, 
                    // tal vez quiera ver la foto antes de empezar (opcional)
                });
            });
        }

        // Click outside suggestions
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.autocomplete-suggestions')) {
                document.querySelectorAll('.autocomplete-suggestions').forEach(el => el.classList.remove('active'));
            }
        });
    },

    renderSuggestions: function (container, items, onSelect) {
        if (items.length === 0) { container.classList.remove('active'); return; }
        container.innerHTML = items.map(item => {
            const isProd = typeof item === 'object' && item.codigo_sistema;
            const val = isProd ? item.codigo_sistema : (item.nombre || item);
            const desc = item.descripcion ? `<br><small class="text-muted" style="font-size: 0.75rem;">${item.descripcion}</small>` : '';
            
            if (isProd) {
                let imgSrc = item.imagen || '';
                if (imgSrc && !imgSrc.startsWith('/') && !imgSrc.startsWith('http') && !imgSrc.startsWith('data:')) {
                    imgSrc = `/static/img/productos/${imgSrc}`;
                }
                const img = imgSrc ? `<img src="${imgSrc}" style="width: 45px; height: 45px; object-fit: contain; margin-right: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;" onerror="this.src='/static/img/no-image.svg'">` : '';
                return `
                    <div class="suggestion-item p-2 border-bottom d-flex align-items-center" style="cursor:pointer; transition: background 0.2s;">
                        ${img}
                        <div style="line-height: 1.2;">
                            <span class="fw-bold text-dark">${val}</span>
                            ${desc}
                        </div>
                    </div>`;
            }
            
            return `<div class="suggestion-item p-2 border-bottom" style="cursor:pointer;">${val}${desc}</div>`;
        }).join('');
        
        container.querySelectorAll('.suggestion-item').forEach((div, idx) => {
            div.addEventListener('click', () => onSelect(items[idx]));
        });
        container.classList.add('active');
    },

    cargarCacheUI: function () {
        const lastResp = localStorage.getItem(this.getLastResponsableKey());
        if (lastResp) {
            const input = document.getElementById('responsable-pulido-input');
            if (input) input.value = lastResp;
        }
    },

    // ==========================================================
    // PAUSAS PROGRAMADAS (descuento automático)
    // ==========================================================
    getVentanasPausasProgramadas: function () {
        // Ventanas fijas locales (Bogotá) por turno estándar
        return [
            { tipo: 'MICROBREAK', inicio: '07:00', fin: '07:05' },
            { tipo: 'DESAYUNO',   inicio: '09:00', fin: '09:20' },
            { tipo: 'MICROBREAK', inicio: '11:00', fin: '11:05' },
            { tipo: 'ALMUERZO',   inicio: '13:00', fin: '13:40' },
            { tipo: 'MICROBREAK', inicio: '15:00', fin: '15:05' }
        ];
    },

    _toDateTimeSameDay: function (baseDate, hhmm) {
        const [h, m] = hhmm.split(':').map(n => parseInt(n, 10));
        const d = new Date(baseDate);
        d.setHours(h, m, 0, 0);
        return d;
    },

    _overlapMs: function (aStart, aEnd, bStart, bEnd) {
        const start = Math.max(aStart.getTime(), bStart.getTime());
        const end = Math.min(aEnd.getTime(), bEnd.getTime());
        return Math.max(0, end - start);
    },

    calcularDescuentoProgramadoMs: function (inicio, fin) {
        if (!inicio || !fin) return 0;
        const aStart = new Date(inicio);
        const aEnd = new Date(fin);
        if (isNaN(aStart.getTime()) || isNaN(aEnd.getTime()) || aEnd <= aStart) return 0;

        // Soportar cruces de medianoche (muy raro). Si cruza, limitamos a mismo día para evitar descuento erróneo.
        const sameDay = aStart.toDateString() === aEnd.toDateString();
        if (!sameDay) return 0;

        let total = 0;
        for (const v of this.getVentanasPausasProgramadas()) {
            const bStart = this._toDateTimeSameDay(aStart, v.inicio);
            const bEnd = this._toDateTimeSameDay(aStart, v.fin);
            total += this._overlapMs(aStart, aEnd, bStart, bEnd);
        }
        return total;
    },

    generarDetalleDescuentoProgramado: function (inicio, fin) {
        if (!inicio || !fin) return [];
        const aStart = new Date(inicio);
        const aEnd = new Date(fin);
        const sameDay = aStart.toDateString() === aEnd.toDateString();
        if (!sameDay) return [];

        const detalle = [];
        for (const v of this.getVentanasPausasProgramadas()) {
            const bStart = this._toDateTimeSameDay(aStart, v.inicio);
            const bEnd = this._toDateTimeSameDay(aStart, v.fin);
            const ms = this._overlapMs(aStart, aEnd, bStart, bEnd);
            if (ms > 0) {
                detalle.push({
                    tipo: v.tipo,
                    inicio: v.inicio,
                    fin: v.fin,
                    minutos: Math.round(ms / 60000)
                });
            }
        }
        return detalle;
    },

    _renderDescuentoProgramadoUI: function (descuentoTotalMs, descuentoMin, descuentoSec) {
        const modal = document.getElementById('modal-reporte-final');
        if (!modal) return;

        let el = document.getElementById('modal-descuento-programado');
        if (!el) {
            el = document.createElement('div');
            el.id = 'modal-descuento-programado';
            el.style.marginTop = '6px';
            el.style.fontSize = '0.9rem';
            el.style.color = '#0f172a';
            // Insertar cerca de los totales si existen
            const anchor = document.getElementById('modal-tiempo-efectivo')?.parentElement || modal;
            anchor.appendChild(el);
        }

        if (!descuentoTotalMs || descuentoTotalMs <= 0) {
            el.innerHTML = '';
            return;
        }

        const detalle = this.generarDetalleDescuentoProgramado(this.startTime, new Date());
        const breakdown = detalle.length
            ? `<div class="text-muted" style="font-size:0.8rem;">${detalle.map(d => `${d.tipo} ${d.inicio}-${d.fin} (${d.minutos}m)`).join(' · ')}</div>`
            : '';
        el.innerHTML = `
            <div><strong>Descuento automático:</strong> ${descuentoMin} min ${(descuentoSec % 60)}s (pausas programadas)</div>
            ${breakdown}
        `;
    },

    limpiarFormulario: function() {
        document.getElementById('form-pulido')?.reset();
        this.selectedProduct = null;
        this.pncRows = [];
        this.revueltosRows = [];
        this.renderFilasPnc();
        this.renderFilasRevuelto();
        this.actualizarCalculoManual();
        this.actualizarCalculoPro();
    },

    // ==========================================
    // GESTIÓN DE FILAS DINÁMICAS (PNC Y REVUELTOS)
    // ==========================================
    
    agregarFilaPnc: function() {
        const id = Date.now();
        this.pncRows.push({ id, proceso: 'PULIDO', cantidad: 0, criterio: '' });
        this.renderFilasPnc();
    },

    eliminarFilaPnc: function(id) {
        this.pncRows = this.pncRows.filter(r => r.id !== id);
        this.renderFilasPnc();
        this.actualizarCalculoPro();
    },

    renderFilasPnc: function() {
        const container = document.getElementById('pnc-dynamic-container');
        const emptyMsg = document.getElementById('pnc-empty-msg');
        if (!container) return;

        if (this.pncRows.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-2 small" id="pnc-empty-msg">No hay PNC reportado</div>';
            return;
        }

        container.innerHTML = this.pncRows.map(row => `
            <div class="pnc-row d-flex gap-2 align-items-center bg-white p-2 rounded border shadow-sm">
                <select id="pnc-proc-${row.id}" class="form-select form-select-sm" style="width: 110px;">
                    <option value="PULIDO" ${row.proceso === 'PULIDO' ? 'selected' : ''}>PULIDO</option>
                    <option value="INYECCION" ${row.proceso === 'INYECCION' ? 'selected' : ''}>INYECCIÓN</option>
                    <option value="ENSAMBLE" ${row.proceso === 'ENSAMBLE' ? 'selected' : ''}>ENSAMBLE</option>
                </select>
                <input type="number" id="pnc-cant-${row.id}" class="form-control form-control-sm" placeholder="Cant" style="width: 70px;" value="${row.cantidad}" oninput="ModuloPulido.actualizarCalculoPro()">
                <select id="pnc-crit-${row.id}" class="form-select form-select-sm flex-grow-1">
                    <option value="">Seleccionar motivo...</option>
                    ${(this.catalogosPnc[row.proceso] || []).map(c => `<option value="${c}" ${row.criterio === c ? 'selected' : ''}>${c}</option>`).join('')}
                    <option value="OTRO">OTRO</option>
                </select>
                <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="ModuloPulido.eliminarFilaPnc(${row.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');

        // Re-vincular eventos de cambio de proceso para actualizar criterios
        this.pncRows.forEach(row => {
            const selectProc = document.getElementById(`pnc-proc-${row.id}`);
            if (selectProc) {
                selectProc.addEventListener('change', (e) => {
                    const newProc = e.target.value;
                    const rowIdx = this.pncRows.findIndex(r => r.id === row.id);
                    if (rowIdx !== -1) {
                        this.pncRows[rowIdx].proceso = newProc;
                        this.renderFilasPnc();
                    }
                });
            }
        });
    },

    // --- NUEVA SECCIÓN: BUJES REVUELTOS ---
    
    agregarFilaRevuelto: function() {
        const id = Date.now();
        this.revueltosRows.push({ id, id_codigo: '', cantidad: 0 });
        this.renderFilasRevuelto();
        this.initRevueltosAutocomplete(id);
    },

    eliminarFilaRevuelto: function(id) {
        this.revueltosRows = this.revueltosRows.filter(r => r.id !== id);
        this.renderFilasRevuelto();
    },

    renderFilasRevuelto: function() {
        const container = document.getElementById('revueltos-dynamic-container');
        if (!container) return;

        if (this.revueltosRows.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-2 small" id="revueltos-empty-msg">No hay bujes revueltos</div>';
            return;
        }

        container.innerHTML = this.revueltosRows.map(row => `
            <div class="revueltos-row d-flex gap-2 align-items-center bg-white p-2 rounded border shadow-sm position-relative">
                <div class="flex-grow-1 position-relative">
                    <input type="text" id="rev-cod-${row.id}" class="form-control form-control-sm" placeholder="Referencia..." value="${row.id_codigo}" autocomplete="off" oninput="ModuloPulido.updateRevState(${row.id})">
                    <div id="rev-sugg-${row.id}" class="autocomplete-suggestions" style="top: 100%; left: 0; width: 100%; z-index: 1000;"></div>
                </div>
                <input type="number" id="rev-cant-${row.id}" class="form-control form-control-sm" placeholder="Cant" style="width: 80px;" value="${row.cantidad}" oninput="ModuloPulido.updateRevState(${row.id})">
                <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="ModuloPulido.eliminarFilaRevuelto(${row.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');

        this.revueltosRows.forEach(row => {
            this.initRevueltosAutocomplete(row.id);
        });
    },

    updateRevState: function(id) {
        const row = this.revueltosRows.find(r => r.id === id);
        if (row) {
            row.id_codigo = document.getElementById(`rev-cod-${id}`)?.value || '';
            row.cantidad = parseFloat(document.getElementById(`rev-cant-${id}`)?.value) || 0;
        }
    },

    initRevueltosAutocomplete: function(rowId) {
        const input = document.getElementById(`rev-cod-${rowId}`);
        const suggestions = document.getElementById(`rev-sugg-${rowId}`);
        if (!input || !suggestions) return;

        input.addEventListener('input', (e) => {
            const query = e.target.value.trim().toUpperCase();
            if (query.length < 2) {
                suggestions.classList.remove('active');
                return;
            }

            const resultados = this.productosData.filter(p => 
                (p.codigo_sistema || '').toUpperCase().includes(query) || 
                (p.descripcion || '').toUpperCase().includes(query)
            ).slice(0, 5);

            this.renderSuggestions(suggestions, resultados, (p) => {
                input.value = p.codigo_sistema;
                const rowIdx = this.revueltosRows.findIndex(r => r.id === rowId);
                if (rowIdx !== -1) this.revueltosRows[rowIdx].id_codigo = p.codigo_sistema;
                suggestions.classList.remove('active');
            });
        });
    },

    mostrarFotoProducto: function() {
        const container = document.getElementById('pulido-product-photo-container');
        const img = document.getElementById('pulido-product-photo');
        if (!container || !img) return;

        let url = "";
        if (this.selectedProduct && this.selectedProduct.imagen) {
            url = this.selectedProduct.imagen;
        } else {
            // Si no tenemos selectedProduct (ej. tras recargar), buscamos en la data
            const codigo = this.normalizarCodigo(document.getElementById('buscador-productos')?.value);
            const prod = this.productosData.find(p => this.normalizarCodigo(p.codigo_sistema) === codigo);
            if (prod) {
                url = prod.imagen;
            }
        }

        if (url) {
            // FIX: Si la URL es relativa (ej: 'No-disponible.jpg'), apuntar a la carpeta de productos
            if (!url.startsWith('/') && !url.startsWith('http') && !url.startsWith('data:')) {
                url = `/static/img/productos/${url}`;
            }
            img.src = url;
            container.style.display = 'block';
        } else {
            container.style.display = 'none';
        }
    }
};

// Vinculación global
window.ModuloPulido = ModuloPulido;
window.initPulido = () => ModuloPulido.inicializar();
