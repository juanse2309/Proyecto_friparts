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

            if (window.AppState.sharedData.maquinas) {
                this.poblarSelect('maquina-mezcla', window.AppState.sharedData.maquinas);
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
     * Calcular proporción en tiempo real
     */
    calcularProporcion: function () {
        const v = parseFloat(document.getElementById('virgen-mezcla')?.value) || 0;
        const m = parseFloat(document.getElementById('molido-mezcla')?.value) || 0;
        const total = v + m;

        const display = document.getElementById('info-proporcion');
        if (display && total > 0) {
            const pV = ((v / total) * 100).toFixed(1);
            const pM = ((m / total) * 100).toFixed(1);
            display.innerHTML = `
                <div style="display:flex; justify-content: space-between; font-size: 14px; font-weight: 600;">
                    <span style="color: #2563eb;">Virgen: ${pV}%</span>
                    <span style="color: #059669;">Molido: ${pM}%</span>
                    <span style="color: #1e293b;">Total: ${total.toFixed(2)} Kg</span>
                </div>
            `;
        }
    },

    limpiarProporcion: function () {
        const info = document.getElementById('info-proporcion');
        if (info) info.innerHTML = '<!-- Se llena vía JS -->';
    },

    /**
     * Inicializar módulo
     */
    inicializar: function () {
        console.log('🔧 [Mezcla] Inicializando...');
        this.cargarDatos();

        document.getElementById('virgen-mezcla')?.addEventListener('input', () => this.calcularProporcion());
        document.getElementById('molido-mezcla')?.addEventListener('input', () => this.calcularProporcion());

        const form = document.getElementById('form-mezcla');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.registrar();
            };
            form.onreset = () => this.limpiarProporcion();
        }
        console.log('✅ [Mezcla] Módulo inicializado');
    }
};

// Exportar
window.ModuloMezcla = ModuloMezcla;
window.initMezcla = () => ModuloMezcla.inicializar();
