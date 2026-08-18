// ============================================
// pintura.js - Subproceso de Ensamble: Pintura
// Captura insumo (ml) y calcula rendimiento por unidad en el backend.
// ============================================

const ModuloPintura = {
    controller: null,

    inicializar: function () {
        if (!this.controller) {
            this.controller = new SubprocesoEnsambleController({
                nombre: 'Pintura',
                apiBase: '/api/pintura',
                idSesionKey: 'id_pintura',
                btnIniciarId: 'btn-pintura-iniciar',
                btnFinalizarId: 'btn-pintura-finalizar',

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

                construirPayloadFinalizar: (idSesion) => ({
                    id_pintura: idSesion,
                    cantidad: parseInt(document.getElementById('pintura-cantidad')?.value, 10) || 0,
                    ml_insumo_utilizado: parseFloat(document.getElementById('pintura-ml-insumo')?.value) || 0,
                    hora_fin: document.getElementById('pintura-hora-fin')?.value || null,
                    pnc_cantidad: parseInt(document.getElementById('pintura-pnc')?.value, 10) || 0,
                    observaciones: (document.getElementById('pintura-observaciones')?.value || '').trim(),
                    responsable: this.controller.obtenerResponsable()
                }),

                validarFinalizar: (payload) => {
                    if (!Number.isFinite(payload.cantidad) || payload.cantidad <= 0) {
                        return 'La cantidad pintada debe ser mayor a cero.';
                    }
                    if (payload.ml_insumo_utilizado < 0) {
                        return 'Los ML de insumo no pueden ser negativos.';
                    }
                    if (!SubprocesoEnsambleController.horaFinEsPosterior(this.controller.sesion?.hora_inicio, payload.hora_fin)) {
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

                onSesionCambia: (activa, sesion) => this.actualizarUI(activa, sesion),
                limpiarCampos: () => this.limpiarFormulario()
            });
        }

        this.controller.verificarSesionActiva();
        this.configurarEventos();
    },

    configurarEventos: function () {
        if (this._eventosConfigurados) return;
        this._eventosConfigurados = true;

        document.getElementById('btn-pintura-iniciar')?.addEventListener('click', () => this.controller.iniciar());
        document.getElementById('btn-pintura-finalizar')?.addEventListener('click', () => this.controller.finalizar());
    },

    actualizarUI: function (activa, sesion) {
        const cardIniciar = document.getElementById('pintura-card-iniciar');
        const cardFinalizar = document.getElementById('pintura-card-finalizar');
        const info = document.getElementById('pintura-session-info');

        if (cardIniciar) cardIniciar.style.display = activa ? 'none' : 'block';
        if (cardFinalizar) cardFinalizar.style.display = activa ? 'block' : 'none';

        if (info) {
            info.textContent = activa && sesion
                ? `${sesion.id_codigo || ''} · ${sesion.insumo_pintura || ''}`.trim()
                : '';
        }
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
    }
};

window.ModuloPintura = ModuloPintura;
