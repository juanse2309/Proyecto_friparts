// ============================================
// rayada.js - Subproceso de Ensamble: Rayada
// Formulario de un solo paso. El tiempo de proceso lo calcula el backend a
// partir de hora_inicio/hora_fin capturadas en el mismo registro.
// ============================================

const ModuloRayada = {
    controller: null,

    inicializar: function () {
        if (!this.controller) {
            this.controller = new SubprocesoEnsambleController({
                nombre: 'Rayada',
                apiBase: '/api/rayada',
                idSesionKey: 'id_rayada',
                btnRegistrarId: 'btn-rayada-registrar',

                construirPayloadIniciar: () => ({
                    id_codigo: (document.getElementById('rayada-id-codigo')?.value || '').trim(),
                    hora_inicio: document.getElementById('rayada-hora-inicio')?.value || null,
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
                    hora_fin: document.getElementById('rayada-hora-fin')?.value || null,
                    pnc_cantidad: parseInt(document.getElementById('rayada-pnc')?.value, 10) || 0,
                    observaciones: (document.getElementById('rayada-observaciones')?.value || '').trim(),
                    responsable: this.controller.obtenerResponsable()
                }),

                validarFinalizar: (payload) => {
                    if (!Number.isFinite(payload.cantidad) || payload.cantidad <= 0) {
                        return 'La cantidad rayada debe ser mayor a cero.';
                    }
                    const horaInicio = document.getElementById('rayada-hora-inicio')?.value || null;
                    if (!SubprocesoEnsambleController.horaFinEsPosterior(horaInicio, payload.hora_fin)) {
                        return 'La Hora Fin debe ser posterior a la Hora Inicio.';
                    }
                    if (payload.pnc_cantidad < 0) {
                        return 'La merma (PNC) no puede ser negativa.';
                    }
                    if (payload.pnc_cantidad > payload.cantidad) {
                        return 'La merma (PNC) no puede ser mayor que la cantidad rayada.';
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

        document.getElementById('btn-rayada-registrar')?.addEventListener('click', () => this.controller.registrar());
    },

    limpiarFormulario: function () {
        ['rayada-id-codigo', 'rayada-hora-inicio', 'rayada-cantidad', 'rayada-hora-fin',
            'rayada-observaciones'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        const pnc = document.getElementById('rayada-pnc');
        if (pnc) pnc.value = '0';
    }
};

window.ModuloRayada = ModuloRayada;
