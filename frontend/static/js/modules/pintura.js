// ============================================
// pintura.js - Subproceso de Ensamble: Pintura
// Formulario de un solo paso: captura insumo (ml o L, convertido a ml antes
// de enviar) y calcula rendimiento por unidad en el backend.
// ============================================

const ModuloPintura = {
    controller: null,

    inicializar: function () {
        if (!this.controller) {
            this.controller = new SubprocesoEnsambleController({
                nombre: 'Pintura',
                apiBase: '/api/pintura',
                idSesionKey: 'id_pintura',
                btnRegistrarId: 'btn-pintura-registrar',

                construirPayloadIniciar: () => ({
                    id_codigo: (document.getElementById('pintura-id-codigo')?.value || '').trim(),
                    insumo_pintura: (document.getElementById('pintura-insumo')?.value || '').trim(),
                    op_numero: (document.getElementById('pintura-op')?.value || '').trim(),
                    hora_inicio: document.getElementById('pintura-hora-inicio')?.value || null,
                    responsable: this.controller.obtenerResponsable()
                }),

                // --- Guard Clauses: se ejecutan ANTES de cualquier fetch ---
                validarIniciar: (payload) => {
                    if (!payload.id_codigo) return 'Ingresa la referencia o código a pintar.';
                    if (!payload.insumo_pintura) return 'Indica qué insumo de pintura vas a usar.';
                    if (!payload.responsable) return 'No se pudo identificar al responsable. Recarga la página.';
                    return null;
                },

                construirPayloadFinalizar: (idSesion) => {
                    const cantidadInsumo = parseFloat(document.getElementById('pintura-ml-insumo')?.value) || 0;
                    const unidad = document.getElementById('pintura-unidad-insumo')?.value || 'ml';
                    return {
                        id_pintura: idSesion,
                        cantidad: parseInt(document.getElementById('pintura-cantidad')?.value, 10) || 0,
                        // Conversión a ml SIEMPRE antes de enviar -- el backend/columna
                        // ml_insumo_utilizado asume mililitros. 1 L = 1000 ml.
                        ml_insumo_utilizado: unidad === 'L' ? cantidadInsumo * 1000 : cantidadInsumo,
                        hora_fin: document.getElementById('pintura-hora-fin')?.value || null,
                        pnc_cantidad: parseInt(document.getElementById('pintura-pnc')?.value, 10) || 0,
                        observaciones: (document.getElementById('pintura-observaciones')?.value || '').trim(),
                        responsable: this.controller.obtenerResponsable()
                    };
                },

                validarFinalizar: (payload) => {
                    if (!Number.isFinite(payload.cantidad) || payload.cantidad <= 0) {
                        return 'La cantidad pintada debe ser mayor a cero.';
                    }
                    if (payload.ml_insumo_utilizado < 0) {
                        return 'La cantidad de insumo no puede ser negativa.';
                    }
                    const horaInicio = document.getElementById('pintura-hora-inicio')?.value || null;
                    if (!SubprocesoEnsambleController.horaFinEsPosterior(horaInicio, payload.hora_fin)) {
                        return 'La Hora Fin debe ser posterior a la Hora Inicio.';
                    }
                    if (payload.pnc_cantidad < 0) {
                        return 'La merma (PNC) no puede ser negativa.';
                    }
                    if (payload.pnc_cantidad > payload.cantidad) {
                        return 'La merma (PNC) no puede ser mayor que la cantidad pintada.';
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

        document.getElementById('btn-pintura-registrar')?.addEventListener('click', () => this.controller.registrar());
    },

    limpiarFormulario: function () {
        ['pintura-id-codigo', 'pintura-insumo', 'pintura-op', 'pintura-hora-inicio',
            'pintura-cantidad', 'pintura-ml-insumo', 'pintura-hora-fin',
            'pintura-observaciones'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
        const pnc = document.getElementById('pintura-pnc');
        if (pnc) pnc.value = '0';
        const unidad = document.getElementById('pintura-unidad-insumo');
        if (unidad) unidad.value = 'ml';
    }
};

window.ModuloPintura = ModuloPintura;
