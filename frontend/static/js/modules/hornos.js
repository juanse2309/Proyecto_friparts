// ============================================
// hornos.js - Subproceso de Ensamble: Hornos
// Formulario de un solo paso. Registro de temperatura de ingreso/salida y
// tiempo de curado por lote (solo existe un horno físico en planta).
// ============================================

const ModuloHornos = {
    controller: null,

    // Rango físico plausible de temperatura de horno industrial (°C).
    // Evita valores "ilógicos" (negativos absurdos o teclas mal presionadas).
    TEMP_MIN: -20,
    TEMP_MAX: 400,

    inicializar: function () {
        if (!this.controller) {
            this.controller = new SubprocesoEnsambleController({
                nombre: 'Registro de Horno',
                apiBase: '/api/hornos',
                idSesionKey: 'id_horno_registro',
                btnRegistrarId: 'btn-hornos-registrar',

                construirPayloadIniciar: () => ({
                    id_codigo: (document.getElementById('hornos-id-codigo')?.value || '').trim(),
                    cantidad: parseInt(document.getElementById('hornos-cantidad')?.value, 10) || 0,
                    temperatura_ingreso_c: parseFloat(document.getElementById('hornos-temp-ingreso')?.value),
                    op_numero: (document.getElementById('hornos-op')?.value || '').trim(),
                    hora_inicio: document.getElementById('hornos-hora-inicio')?.value || null,
                    responsable: this.controller.obtenerResponsable()
                }),

                // --- Guard Clauses: se ejecutan ANTES de cualquier fetch ---
                validarIniciar: (payload) => {
                    if (!payload.id_codigo) return 'Ingresa la referencia o código del lote.';
                    if (!Number.isFinite(payload.cantidad) || payload.cantidad <= 0) {
                        return 'La cantidad del lote debe ser mayor a cero.';
                    }
                    if (!Number.isFinite(payload.temperatura_ingreso_c)) {
                        return 'Ingresa la temperatura de ingreso.';
                    }
                    if (payload.temperatura_ingreso_c < this.TEMP_MIN || payload.temperatura_ingreso_c > this.TEMP_MAX) {
                        return `La temperatura de ingreso debe estar entre ${this.TEMP_MIN}°C y ${this.TEMP_MAX}°C.`;
                    }
                    if (!payload.responsable) return 'No se pudo identificar al responsable. Recarga la página.';
                    return null;
                },

                construirPayloadFinalizar: (idSesion) => ({
                    id_horno_registro: idSesion,
                    temperatura_salida_c: parseFloat(document.getElementById('hornos-temp-salida')?.value),
                    hora_fin: document.getElementById('hornos-hora-fin')?.value || null,
                    pnc_cantidad: parseInt(document.getElementById('hornos-pnc')?.value, 10) || 0,
                    observaciones: (document.getElementById('hornos-observaciones')?.value || '').trim(),
                    responsable: this.controller.obtenerResponsable()
                }),

                validarFinalizar: (payload) => {
                    if (!Number.isFinite(payload.temperatura_salida_c)) {
                        return 'Ingresa la temperatura de salida.';
                    }
                    if (payload.temperatura_salida_c < this.TEMP_MIN || payload.temperatura_salida_c > this.TEMP_MAX) {
                        return `La temperatura de salida debe estar entre ${this.TEMP_MIN}°C y ${this.TEMP_MAX}°C.`;
                    }
                    const horaInicio = document.getElementById('hornos-hora-inicio')?.value || null;
                    if (!SubprocesoEnsambleController.horaFinEsPosterior(horaInicio, payload.hora_fin)) {
                        return 'La Hora Fin debe ser posterior a la Hora Inicio.';
                    }
                    if (payload.pnc_cantidad < 0) {
                        return 'La merma (PNC) no puede ser negativa.';
                    }
                    const cantidadLote = parseInt(document.getElementById('hornos-cantidad')?.value, 10) || 0;
                    if (cantidadLote && payload.pnc_cantidad > cantidadLote) {
                        return 'La merma (PNC) no puede ser mayor que la cantidad del lote.';
                    }
                    return null;
                },

                limpiarCampos: () => this.limpiarFormulario()
            });
        }

        this.configurarEventos();
    },

    configurarEventos: function () {
        if (this._eventosConfigurados) return;
        this._eventosConfigurados = true;

        document.getElementById('btn-hornos-registrar')?.addEventListener('click', () => this.controller.registrar());
    },

    limpiarFormulario: function () {
        ['hornos-id-codigo', 'hornos-cantidad', 'hornos-temp-ingreso', 'hornos-op',
            'hornos-hora-inicio', 'hornos-temp-salida', 'hornos-hora-fin',
            'hornos-observaciones'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
        const pnc = document.getElementById('hornos-pnc');
        if (pnc) pnc.value = '0';
    }
};

window.ModuloHornos = ModuloHornos;
