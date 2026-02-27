// ============================================
// mezcla.js - Lógica de Mezcla Material - NAMESPACED
// ============================================

const ModuloMezcla = {
    /**
     * Cargar datos de Mezcla
     */
    cargarDatos: async function () {
        try {
            console.log('🧪 [Mezcla] Cargando datos...');
            mostrarLoading(true);

            // Cargar responsables y máquinas desde el cache compartido
            if (window.AppState.sharedData.responsables) {
                this.poblarSelect('responsable-mezcla', window.AppState.sharedData.responsables);
            }

            console.log('✅ [Mezcla] Datos cargados');
            mostrarLoading(false);
        } catch (error) {
            console.error('Error [Mezcla] cargarDatos:', error);
            mostrarLoading(false);
        }
    },

    poblarSelect: function (selectId, datos) {
        const select = document.getElementById(selectId);
        if (!select) return;

        select.innerHTML = '<option value="">-- Seleccionar --</option>';
        datos.forEach(item => {
            const option = document.createElement('option');
            const val = typeof item === 'object' ? (item.nombre || item.id) : item;
            option.value = val;
            option.textContent = val;
            select.appendChild(option);
        });

        // INTENTO DE AUTO-SELECCION (Fix Race Condition)
        this.intentarSeleccionarResponsable(select);
    },

    intentarSeleccionarResponsable: function (select) {
        let nombreUsuario = null;

        if (window.AppState?.user?.name) {
            nombreUsuario = window.AppState.user.name;
        } else if (window.AuthModule?.currentUser?.nombre) {
            nombreUsuario = window.AuthModule.currentUser.nombre;
        }

        if (nombreUsuario) {
            const options = Array.from(select.options);
            const matchingOption = options.find(opt => opt.value === nombreUsuario);
            if (matchingOption) {
                select.value = nombreUsuario;
                console.log(`✅ [Mezcla] Responsable auto-seleccionado: ${nombreUsuario}`);
            }
        } else {
            console.log('⏳ [Mezcla] Esperando usuario para auto-selección...');

            const handler = (e) => {
                console.log("👤 [Mezcla] Evento user-ready recibido");
                this.intentarSeleccionarResponsable(select);
                window.removeEventListener('user-ready', handler);
            };
            window.addEventListener('user-ready', handler);

            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                if (window.AppState?.user?.name) {
                    this.intentarSeleccionarResponsable(select);
                    clearInterval(interval);
                    window.removeEventListener('user-ready', handler);
                }
                if (attempts > 10) clearInterval(interval);
            }, 500);
        }
    },

    /**
     * Registrar Mezcla
     */
    registrar: async function () {
        try {
            mostrarLoading(true);

            const datos = {
                fecha: document.getElementById('fecha-mezcla')?.value || '',
                responsable: document.getElementById('responsable-mezcla')?.value || '',
                maquina: document.getElementById('maquina-mezcla')?.value || '',
                virgen: document.getElementById('virgen-mezcla')?.value || '0',
                molido: document.getElementById('molido-mezcla')?.value || '0',
                pigmento: document.getElementById('pigmento-mezcla')?.value || '0',
                observaciones: document.getElementById('observaciones-mezcla')?.value || ''
            };

            if (!datos.responsable || !datos.maquina) {
                mostrarNotificacion('⚠️ Selecciona responsable y equipo', 'warning');
                mostrarLoading(false);
                return;
            }

            console.log('📤 [Mezcla] ENVIANDO:', datos);

            const response = await fetch('/api/mezcla', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });

            const res = await response.json();
            if (res.success) {
                mostrarNotificacion('✅ Mezcla registrada!', 'success');
                document.getElementById('form-mezcla')?.reset();
                this.limpiarProporcion();
            } else {
                mostrarNotificacion(`❌ Error: ${res.error}`, 'error');
            }
        } catch (error) {
            console.error('Error [Mezcla] registrar:', error);
            mostrarNotificacion('Error de conexión', 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    /**
     * Calcular valores automáticamente basados en bultos
     */
    calcularPesosAutomaticos: function () {
        const bultos = parseFloat(document.getElementById('bultos-mezcla')?.value) || 0;

        const KG_VIRGEN_POR_BULTO = 25;
        const KG_MOLIDO_POR_BULTO = 3.39;
        const GR_PIGMENTO_POR_BULTO = 12.1;

        const v = (bultos * KG_VIRGEN_POR_BULTO);
        const m = (bultos * KG_MOLIDO_POR_BULTO);
        const p = (bultos * GR_PIGMENTO_POR_BULTO);

        const inputVirgen = document.getElementById('virgen-mezcla');
        const inputMolido = document.getElementById('molido-mezcla');
        const inputPigmento = document.getElementById('pigmento-mezcla');

        if (inputVirgen) inputVirgen.value = v.toFixed(2);
        if (inputMolido) inputMolido.value = m.toFixed(2);
        if (inputPigmento) inputPigmento.value = p.toFixed(1);

        this.calcularProporcion();
    },

    /**
     * Calcular proporción en tiempo real
     */
    calcularProporcion: function () {
        const v = parseFloat(document.getElementById('virgen-mezcla')?.value) || 0;
        const m = parseFloat(document.getElementById('molido-mezcla')?.value) || 0;
        const total = v + m;

        const display = document.getElementById('info-proporcion');
        if (!display) return;

        if (total > 0) {
            const pV = ((v / total) * 100).toFixed(1);
            const pM = ((m / total) * 100).toFixed(1);

            display.innerHTML = `
                <div style="display:flex; flex-direction: column; gap: 8px;">
                    <div style="display:flex; justify-content: space-between; align-items: baseline;">
                        <span style="color: #1e3a8a; font-weight: 800; font-size: 1.1rem;">\${pV}% VIRGEN</span>
                        <span style="color: #065f46; font-weight: 800; font-size: 1.1rem;">\${pM}% MOLIDO</span>
                    </div>
                    <div style="width: 100%; height: 12px; background: #e2e8f0; border-radius: 6px; overflow: hidden; display: flex;">
                        <div style="width: \${pV}%; background: #3b82f6; height: 100%;"></div>
                        <div style="width: \${pM}%; background: #10b981; height: 100%;"></div>
                    </div>
                    <div style="text-align: center; color: #1e293b; font-size: 0.9rem; font-weight: 600; margin-top: 4px;">
                        Material Total a Preparar: \${total.toFixed(2)} Kg
                    </div>
                </div>
            `;
        } else {
            display.innerHTML = '<div style="text-align: center; color: #64748b;">Ingrese cantidad de bultos para ver porcentajes</div>';
        }
    },

    limpiarProporcion: function () {
        const info = document.getElementById('info-proporcion');
        if (info) info.innerHTML = '<div style="text-align: center; color: #64748b;">Ingrese cantidad de bultos para ver porcentajes</div>';
    },

    /**
     * Inicializar módulo
     */
    inicializar: function () {
        console.log('🔧 [Mezcla] Inicializando...');
        this.cargarDatos();

        // Listener para bultos
        document.getElementById('bultos-mezcla')?.addEventListener('input', () => this.calcularPesosAutomaticos());

        const form = document.getElementById('form-mezcla');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.registrar();
            };
            form.onreset = () => {
                setTimeout(() => this.limpiarProporcion(), 10);
            };
        }

        this.limpiarProporcion();

        // Configurar Smart Enter
        if (window.ModuloUX && window.ModuloUX.setupSmartEnter) {
            window.ModuloUX.setupSmartEnter({
                inputIds: [
                    'fecha-mezcla', 'responsable-mezcla', 'maquina-mezcla',
                    'bultos-mezcla', 'virgen-mezcla', 'molido-mezcla',
                    'pigmento-mezcla', 'observaciones-mezcla'
                ],
                actionBtnId: 'form-mezcla'
            });
        }

        console.log('✅ [Mezcla] Módulo inicializado');
    }
};

// Exportar
window.ModuloMezcla = ModuloMezcla;
window.initMezcla = () => ModuloMezcla.inicializar();
