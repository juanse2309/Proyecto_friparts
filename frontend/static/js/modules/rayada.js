// ============================================
// rayada.js - Subproceso de Ensamble: Rayada
// Control de tiempos de proceso por referencia de carcaza (el tiempo lo
// calcula el backend a partir de los timestamps reales de iniciar/finalizar).
// ============================================

const ModuloRayada = {
    controller: null,

    inicializar: function () {
        if (!this.controller) {
            this.controller = new SubprocesoEnsambleController({
                nombre: 'Rayada',
                apiBase: '/api/rayada',
                idSesionKey: 'id_rayada',
                btnIniciarId: 'btn-rayada-iniciar',
                btnFinalizarId: 'btn-rayada-finalizar',

                construirPayloadIniciar: () => ({
                    id_codigo: (document.getElementById('rayada-id-codigo')?.value || '').trim(),
                    op_numero: (document.getElementById('rayada-op')?.value || '').trim(),
                    responsable: this.controller.obtenerResponsable()
                }),

                // --- Guard Clauses: se ejecutan ANTES de cualquier fetch ---
                validarIniciar: (payload) => {
                    if (!payload.id_codigo) return 'Ingresa la referencia de carcaza a rayar.';
                    if (!payload.responsable) return 'No se pudo identificar al responsable. Recarga la página.';
                    return null;
                },

                construirPayloadFinalizar: (idSesion) => ({
                    id_rayada: idSesion,
                    cantidad: parseInt(document.getElementById('rayada-cantidad')?.value, 10) || 0,
                    pnc_cantidad: parseInt(document.getElementById('rayada-pnc')?.value, 10) || 0,
                    observaciones: (document.getElementById('rayada-observaciones')?.value || '').trim(),
                    responsable: this.controller.obtenerResponsable()
                }),

                validarFinalizar: (payload) => {
                    if (!Number.isFinite(payload.cantidad) || payload.cantidad <= 0) {
                        return 'La cantidad rayada debe ser mayor a cero.';
                    }
                    if (payload.pnc_cantidad < 0) {
                        return 'La merma (PNC) no puede ser negativa.';
                    }
                    if (payload.pnc_cantidad > payload.cantidad) {
                        return 'La merma (PNC) no puede ser mayor que la cantidad rayada.';
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

        document.getElementById('btn-rayada-iniciar')?.addEventListener('click', () => this.controller.iniciar());
        document.getElementById('btn-rayada-finalizar')?.addEventListener('click', () => this.controller.finalizar());
    },

    actualizarUI: function (activa, sesion) {
        const cardIniciar = document.getElementById('rayada-card-iniciar');
        const cardFinalizar = document.getElementById('rayada-card-finalizar');
        const info = document.getElementById('rayada-session-info');

        if (cardIniciar) cardIniciar.style.display = activa ? 'none' : 'block';
        if (cardFinalizar) cardFinalizar.style.display = activa ? 'block' : 'none';

        if (info) {
            info.textContent = activa && sesion ? (sesion.id_codigo || '') : '';
        }
    },

    limpiarFormulario: function () {
        ['rayada-id-codigo', 'rayada-op', 'rayada-cantidad', 'rayada-observaciones'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        const pnc = document.getElementById('rayada-pnc');
        if (pnc) pnc.value = '0';
    }
};

window.ModuloRayada = ModuloRayada;
