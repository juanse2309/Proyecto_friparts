// ============================================
// pulido.js - Módulo de Pulido (Versión DUAL FINAL - Satélite vs Planta)
// ============================================

const ModuloPulido = {
    productosData: [],
    responsablesData: [],
    
    // Pro Mode State
    sesionActiva: false,
    enPausa: false,
    pausaTime: null,
    totalPausaMs: 0,
    tiempoAcumuladoMs: 0, // NUEVO: Tiempo de segmentos anteriores
    timerInterval: null,
    sessionId: null,

    // Helper de Normalización
    normalizarCodigo: function(c) {
        if (!c) return "";
        return String(c).toUpperCase().replace(/FR-/gi, "").trim();
    },

    inicializar: async function () {
        console.log('🔧 [Pulido] Inicializando módulo DUAL FINAL...');
        this.configurarUI();
        await this.cargarDatosMaestros();
        this.initAutocompletes();
        this.cargarCacheUI();
        await this.verificarTrabajoActivo(); // Rehidratar desde SQL
        this.cargarEstadoLocal(); // Fallback/Sync local
        
        // Sync default mode state based on switch
        const switchEl = document.getElementById('toggle-pulido-mode');
        if (switchEl) {
            this.cambiarModo(switchEl.checked);
        }
    },

    guardarEstadoLocal: function() {
        const estado = {
            sesionActiva: this.sesionActiva,
            sessionId: this.sessionId,
            startTime: this.startTime ? this.startTime.getTime() : null,
            totalPausaMs: this.totalPausaMs,
            tiempoAcumuladoMs: this.tiempoAcumuladoMs,
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
        localStorage.setItem('pulido_state', JSON.stringify(estado));
    },

    cargarEstadoLocal: function() {
        const raw = localStorage.getItem('pulido_state');
        if (!raw) return;
        try {
            const estado = JSON.parse(raw);
            if (estado.sesionActiva) {
                // BLINDAJE OPERARIO: Solo rehidratar si el operario guardado
                // coincide con el operario actualmente logueado
                const operarioActual = document.getElementById('responsable-pulido-input')?.value?.trim()
                    || localStorage.getItem('pulido_last_responsable') || '';
                const operarioGuardado = (estado.responsable || estado.formData?.resp || '').trim();

                if (operarioActual && operarioGuardado && operarioActual.toUpperCase() !== operarioGuardado.toUpperCase()) {
                    console.log(`🚫 [Pulido] Estado local pertenece a '${operarioGuardado}' pero el operario actual es '${operarioActual}' — ignorando.`);
                    localStorage.removeItem('pulido_state');
                    return;
                }

                // BLINDAJE hora_inicio: No arrancar cronómetro con startTime nulo
                if (!estado.startTime) {
                    console.log('🚫 [Pulido] startTime nulo en estado local — descartando sesión corrupta.');
                    localStorage.removeItem('pulido_state');
                    return;
                }

                console.log("♻️ Rehidratando sesión activa de Pulido...");
                this.sesionActiva = true;
                this.sessionId = estado.sessionId;
                this.startTime = new Date(estado.startTime);
                this.totalPausaMs = estado.totalPausaMs;
                this.tiempoAcumuladoMs = estado.tiempoAcumuladoMs || 0;
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
            localStorage.removeItem('pulido_state');
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
        const resp = document.getElementById('responsable-pulido-input')?.value || localStorage.getItem('pulido_last_responsable');
        if (!resp) return;

        try {
            const res = await fetch(`/api/pulido/session_active?responsable=${encodeURIComponent(resp)}`);
            const data = await res.json();
            if (data.success && data.session) {
                // FIX Efecto Daniela: Solo cargar si el estado es genuinamente activo
                const estado = (data.session.estado || '').toUpperCase();
                if (!['EN_PROCESO', 'PAUSADO', 'PAUSADO_COLA', 'TRABAJANDO'].includes(estado)) {
                    console.log("🚫 [Pulido] Sesión encontrada pero estado='" + estado + "' — NO es activa, ignorando.");
                    return;
                }

                // BLINDAJE hora_inicio nula: No arrancar cronómetro sin hora válida
                if (!data.session.hora_inicio_dt) {
                    console.log('🚫 [Pulido] Sesión activa sin hora_inicio — cronómetro no arrancará.');
                    return;
                }

                console.log("📡 [Pulido] Sesión activa encontrada en SQL:", data.session);
                this.sesionActiva = true;
                this.sessionId = data.session.id_pulido;
                this.startTime = new Date(data.session.hora_inicio_dt);
                this.tiempoAcumuladoMs = (data.session.duracion_segundos || 0) * 1000;
                
                // Poblar UI con responsable verificado (mismo operario)
                const rInput = document.getElementById('responsable-pulido-input');
                if (rInput) rInput.value = resp; // Asegurar consistencia
                const p = document.getElementById('buscador-productos');
                const o = document.getElementById('orden-produccion-pulido');
                const l = document.getElementById('lote-pulido');
                if(p) p.value = data.session.codigo;
                if(o) o.value = data.session.orden_produccion;
                if(l) l.value = data.session.lote;

                this.continuarUIActiva();
            }
        } catch (e) {
            console.error("Error recuperando sesión SQL:", e);
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
        const totalElapsedMs = this.tiempoAcumuladoMs + segmentTime;

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
            tiempoAcumuladoMs: totalElapsedMs
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
        const now = new Date();
        
        // El tiempo total es la suma de lo acumulado (sesiones previas) + el segmento actual
        const msSegmentoActual = this.startTime ? (now - this.startTime - this.totalPausaMs) : 0;
        const msTotales = this.tiempoAcumuladoMs + msSegmentoActual;
        
        const totalMin = Math.floor(msTotales / 60000);
        const totalSec = Math.floor(msTotales / 1000);
        
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
        document.getElementById('modal-tiempo-efectivo').innerText = totalMin + ' min';
        
        // Reset inputs modal
        document.getElementById('cantidad-recibida-pro').value = 0;
        document.getElementById('pro-pnc-iny').value = 0;
        document.getElementById('pro-pnc-pul').value = 0;
        document.getElementById('resultado-buenas-pro').innerText = '0';
        
        document.getElementById('modal-reporte-final').style.display = 'flex';
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
        const brutoInput = document.getElementById('cantidad-recibida-pro');
        const pncInyInput = document.getElementById('pro-pnc-iny');
        const pncPulInput = document.getElementById('pro-pnc-pul');
        const display = document.getElementById('resultado-buenas-pro');
        
        if (!brutoInput) return;
        
        const recibida = parseInt(brutoInput.value, 10) || 0;
        const pncIny = parseInt(pncInyInput?.value, 10) || 0;
        const pncPul = parseInt(pncPulInput?.value, 10) || 0;
        
        const buenas = Math.max(0, recibida - pncIny - pncPul);
        
        console.log(`[Pulido PRO] Bruto: ${recibida}, PNC_Iny: ${pncIny}, PNC_Pul: ${pncPul} -> Total Buenos: ${buenas}`);
        
        if (display) display.innerText = buenas;
    },

    // ==========================================
    // GUARDADO DE DATOS
    // ==========================================

    guardarReportePro: async function () {
        const data = {
            id_pulido: this.sessionId,
            fecha_inicio: document.getElementById('fecha-pulido')?.value || new Date().toISOString().split('T')[0],
            hora_inicio: this.startTime ? (this.startTime.getHours() + ':' + String(this.startTime.getMinutes()).padStart(2, '0')) : '00:00',
            hora_fin: new Date().getHours() + ':' + String(new Date().getMinutes()).padStart(2, '0'),
            responsable: document.getElementById('responsable-pulido-input').value,
            codigo_producto: this.normalizarCodigo(document.getElementById('buscador-productos').value),
            cantidad_recibida: parseInt(document.getElementById('cantidad-recibida-pro').value, 10) || 0,
            pnc_inyeccion: parseInt(document.getElementById('pro-pnc-iny').value, 10) || 0,
            pnc_pulido: parseInt(document.getElementById('pro-pnc-pul').value, 10) || 0,
            criterio_pnc_inyeccion: document.getElementById('pro-criterio-iny').value,
            criterio_pnc_pulido: document.getElementById('pro-criterio-pul').value,
            cantidad_real: parseInt(document.getElementById('resultado-buenas-pro').innerText, 10) || 0,
            observaciones: document.getElementById('observaciones-pro')?.value || '',
            orden_produccion: document.getElementById('orden-produccion-pulido')?.value || '',
            lote: document.getElementById('lote-pulido')?.value || '',
            departamento: 'PULIDO',
            almacen_destino: 'P. TERMINADO',
            modo: 'PRO',
            tiempo_acumulado_ms: this.tiempoAcumuladoMs // Enviar el tiempo de segmentos previos
        };

        if (!data.responsable || !data.codigo_producto || !data.cantidad_recibida || data.cantidad_recibida <= 0) {
            Swal.fire('Atención', 'Faltan campos (Responsable, Producto o Cantidad bruta)', 'warning');
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
            Swal.showLoading();
            const response = await fetch('/api/pulido', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.success) {
                Swal.fire('¡Éxito!', 'Producción guardada correctamente.', 'success');
                // Limpieza total tras éxito
                this.terminarCiclo();
                this.limpiarSesionLocal(); 
                
                document.getElementById('modal-reporte-final').style.display = 'none';
                this.limpiarFormulario();
            } else {
                // Si el servidor rechaza la sesión (ej. ID no existe y falla recuperación)
                // Limpiamos localmente de todas formas para no bloquear al operario
                console.warn("Servidor rechazó el reporte:", result.error);
                Swal.fire({
                    title: 'Error de Sincronización',
                    text: (result.error || 'Error desconocido') + '. La sesión local se limpiará para evitar bloqueos.',
                    icon: 'warning',
                    confirmButtonText: 'Entendido'
                }).then(() => {
                    this.limpiarSesionLocal();
                    location.reload();
                });
            }
        } catch (error) {
            console.error("Error crítico al guardar:", error);
            Swal.fire({
                title: 'Fallo de Red',
                text: 'No hay comunicación con el servidor. La sesión local se limpiará para permitir nuevos registros.',
                icon: 'error',
                confirmButtonText: 'Limpiar y Reintentar'
            }).then(() => {
                this.limpiarSesionLocal();
                location.reload();
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
                this.productosData = prods?.productos || [];
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
                    localStorage.setItem('pulido_last_responsable', val);
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
                    suggestionsProd.classList.remove('active');
                    inputProd.dispatchEvent(new Event('input'));
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
            const val = typeof item === 'object' ? (item.nombre || item.codigo_sistema) : item;
            const desc = item.descripcion ? `<br><small class="text-muted">${item.descripcion}</small>` : '';
            return `<div class="suggestion-item p-2 border-bottom" style="cursor:pointer;">${val}${desc}</div>`;
        }).join('');
        
        container.querySelectorAll('.suggestion-item').forEach((div, idx) => {
            div.addEventListener('click', () => onSelect(items[idx]));
        });
        container.classList.add('active');
    },

    cargarCacheUI: function () {
        const lastResp = localStorage.getItem('pulido_last_responsable');
        if (lastResp) {
            const input = document.getElementById('responsable-pulido-input');
            if (input) input.value = lastResp;
        }
    },

    limpiarFormulario: function() {
        document.getElementById('form-pulido')?.reset();
        this.actualizarCalculoManual();
        this.actualizarCalculoPro();
    }
};

// Vinculación global
window.ModuloPulido = ModuloPulido;
window.initPulido = () => ModuloPulido.inicializar();
