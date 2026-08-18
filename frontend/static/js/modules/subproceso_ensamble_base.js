// ============================================
// subproceso_ensamble_base.js
// Clase base reutilizable para los subprocesos de Ensamble (Pintura, Rayada,
// Hornos): todos comparten el mismo ciclo de vida iniciar -> finalizar contra
// un backend con la forma POST /api/<modulo>/iniciar | /finalizar +
// GET /api/<modulo>/session_active. Se centraliza aquí el manejo de estado,
// el bloqueo de doble-submit y el feedback de error/éxito para no repetir
// la misma lógica 3 veces (Pintura/Rayada/Hornos).
// ============================================

class SubprocesoEnsambleController {
    /**
     * @param {Object} config
     * @param {string} config.nombre - Nombre legible del subproceso (ej. 'Pintura').
     * @param {string} config.apiBase - Prefijo de API (ej. '/api/pintura').
     * @param {string} config.idSesionKey - Clave del identificador de sesión en las respuestas del backend (ej. 'id_pintura').
     * @param {string} config.btnIniciarId - ID del botón de Iniciar.
     * @param {string} config.btnFinalizarId - ID del botón de Finalizar.
     * @param {Function} config.construirPayloadIniciar - () => Object payload para /iniciar.
     * @param {Function} config.validarIniciar - (payload) => string|null (mensaje de error o null si válido).
     * @param {Function} config.construirPayloadFinalizar - (idSesion, sesionInfo) => Object payload para /finalizar.
     * @param {Function} config.validarFinalizar - (payload) => string|null.
     * @param {Function} config.onSesionCambia - (activa:boolean, sesion:Object|null) => void. Actualiza la UI (mostrar/ocultar cards).
     * @param {Function} [config.limpiarCampos] - () => void. Limpia los inputs tras un finalizar exitoso.
     */
    constructor(config) {
        this.nombre = config.nombre;
        this.apiBase = config.apiBase;
        this.idSesionKey = config.idSesionKey;
        this.btnIniciarId = config.btnIniciarId;
        this.btnFinalizarId = config.btnFinalizarId;
        this.construirPayloadIniciar = config.construirPayloadIniciar;
        this.validarIniciar = config.validarIniciar;
        this.construirPayloadFinalizar = config.construirPayloadFinalizar;
        this.validarFinalizar = config.validarFinalizar;
        this.onSesionCambia = config.onSesionCambia || (() => {});
        this.limpiarCampos = config.limpiarCampos || (() => {});

        this.sesion = null; // Objeto de sesión activa (o null)

        // Dispara la carga del catálogo compartido (idempotente: un solo fetch
        // real sin importar cuántas instancias de este controller se creen).
        this.constructor.cargarCatalogoReferencias();
    }

    // ============================================
    // CATÁLOGO COMPARTIDO DE REFERENCIAS (Pintura/Rayada/Hornos)
    // Single fetch + caché en memoria + <datalist> compartido. Vive a nivel
    // de CLASE (no de instancia) para que los 3 submódulos consuman el mismo
    // catálogo sin triplicar la petición ni la lógica.
    // ============================================
    static _catalogoPromise = null;
    static _referenciasValidas = new Set();

    static cargarCatalogoReferencias() {
        if (!SubprocesoEnsambleController._catalogoPromise) {
            SubprocesoEnsambleController._catalogoPromise = (async () => {
                try {
                    const res = await fetch('/api/productos/listar');
                    const data = await res.json();
                    const items = Array.isArray(data) ? data : (data.items || []);

                    const datalist = document.getElementById('lista-referencias-ensamble');
                    const frag = document.createDocumentFragment();

                    items.forEach(p => {
                        const codigo = p.id_codigo || p.codigo_sistema || p.codigo;
                        if (!codigo) return;

                        SubprocesoEnsambleController._referenciasValidas.add(String(codigo).trim().toUpperCase());

                        if (datalist) {
                            const opt = document.createElement('option');
                            opt.value = codigo;
                            frag.appendChild(opt);
                        }
                    });

                    if (datalist) datalist.appendChild(frag);
                } catch (e) {
                    console.error('[SubprocesoEnsamble] Error cargando catálogo de referencias:', e);
                }
            })();
        }
        return SubprocesoEnsambleController._catalogoPromise;
    }

    static esReferenciaValida(codigo) {
        if (!codigo) return false;
        return SubprocesoEnsambleController._referenciasValidas.has(String(codigo).trim().toUpperCase());
    }

    /**
     * Valida que hora_fin sea posterior a hora_inicio cuando ambas son
     * comparables directamente (formato "HH:MM", como llega recién tecleado
     * en la misma sesión de navegador). Si hora_inicio viene de una sesión
     * recuperada tras recargar la página (timestamp ISO), no se puede
     * comparar de forma confiable aquí y se omite -- el backend sigue siendo
     * la fuente de verdad para el cálculo real de duración.
     */
    static horaFinEsPosterior(horaInicioStr, horaFinStr) {
        if (!horaInicioStr || !horaFinStr) return true;
        if (!/^\d{2}:\d{2}$/.test(horaInicioStr)) return true;
        return horaFinStr > horaInicioStr;
    }

    obtenerResponsable() {
        return (document.getElementById('current_user_fullname')?.value
            || document.getElementById('responsable')?.value
            || '').trim();
    }

    async verificarSesionActiva() {
        const responsable = this.obtenerResponsable();
        if (!responsable) return;

        try {
            const res = await fetch(`${this.apiBase}/session_active?responsable=${encodeURIComponent(responsable)}`);
            const data = await res.json();
            const session = data?.data?.session || null;

            if (data && data.success && session) {
                this.sesion = session;
                this.onSesionCambia(true, session);
            } else {
                this.sesion = null;
                this.onSesionCambia(false, null);
            }
        } catch (e) {
            console.error(`[${this.nombre}] Error verificando sesión activa:`, e);
        }
    }

    /**
     * Ejecuta un POST bloqueando el botón (spinner + disabled) durante la
     * llamada y garantizando su reactivación en finally, pase lo que pase.
     */
    async _ejecutarConBloqueo(btnId, url, payload, onSuccess) {
        const btn = document.getElementById(btnId);
        const textoOriginal = btn ? btn.innerHTML : '';

        try {
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Cargando...';
            }

            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (data && data.success) {
                await onSuccess(data);
            } else {
                const mensaje = (data && data.error) || 'El servidor rechazó la operación.';
                if (window.Swal) {
                    Swal.fire('No se pudo procesar', mensaje, 'error');
                } else {
                    mostrarNotificacion(mensaje, 'error');
                }
            }
        } catch (e) {
            console.error(`[${this.nombre}] Error de red en ${url}:`, e);
            const mensaje = 'No se pudo contactar al servidor. Verifica tu conexión e intenta de nuevo.';
            if (window.Swal) {
                Swal.fire('Error de conexión', mensaje, 'error');
            } else {
                mostrarNotificacion(mensaje, 'error');
            }
        } finally {
            // Reactivación GARANTIZADA del botón, haya éxito, error de negocio o error de red.
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = textoOriginal;
            }
        }
    }

    async iniciar() {
        const payload = this.construirPayloadIniciar();

        // --- Guard Clause: no se dispara el fetch si la validación falla ---
        const errorValidacion = this.validarIniciar(payload);
        if (errorValidacion) {
            if (window.Swal) {
                Swal.fire('Datos incompletos', errorValidacion, 'warning');
            } else {
                mostrarNotificacion(errorValidacion, 'warning');
            }
            return;
        }

        // --- Guard de Integridad (Strict Match): la referencia debe existir
        // TAL CUAL en el catálogo cargado de /api/productos/listar. Se espera
        // a que el catálogo termine de cargar (normalmente ya está resuelto
        // para cuando el operario alcanza a llenar el formulario). ---
        await this.constructor.cargarCatalogoReferencias();
        if (!this.constructor.esReferenciaValida(payload.id_codigo)) {
            const mensaje = `"${payload.id_codigo}" no existe en el catálogo de productos. Selecciónala de la lista.`;
            if (window.Swal) {
                Swal.fire('Referencia inválida', 'Referencia inválida o no existe en el catálogo.', 'error');
            } else {
                mostrarNotificacion(mensaje, 'error');
            }
            return;
        }

        await this._ejecutarConBloqueo(this.btnIniciarId, `${this.apiBase}/iniciar`, payload, async (data) => {
            const idSesion = data.data?.[this.idSesionKey];
            this.sesion = { [this.idSesionKey]: idSesion, ...payload };
            this.onSesionCambia(true, this.sesion);
            mostrarNotificacion(data.message || `${this.nombre} iniciada correctamente.`, 'success');
        });
    }

    async finalizar() {
        if (!this.sesion || !this.sesion[this.idSesionKey]) {
            if (window.Swal) {
                Swal.fire('Sin sesión activa', `No hay un registro de ${this.nombre} iniciado para finalizar.`, 'warning');
            } else {
                mostrarNotificacion(`No hay un registro de ${this.nombre} activo.`, 'warning');
            }
            return;
        }

        const idSesion = this.sesion[this.idSesionKey];
        const payload = this.construirPayloadFinalizar(idSesion, this.sesion);

        // --- Guard Clause: no se dispara el fetch si la validación falla ---
        const errorValidacion = this.validarFinalizar(payload);
        if (errorValidacion) {
            if (window.Swal) {
                Swal.fire('Datos incompletos', errorValidacion, 'warning');
            } else {
                mostrarNotificacion(errorValidacion, 'warning');
            }
            return;
        }

        await this._ejecutarConBloqueo(this.btnFinalizarId, `${this.apiBase}/finalizar`, payload, async (data) => {
            this.sesion = null;
            this.onSesionCambia(false, null);
            this.limpiarCampos();

            if (window.Swal) {
                Swal.fire({
                    icon: 'success',
                    title: `¡${this.nombre} finalizada!`,
                    timer: 2000,
                    showConfirmButton: false
                });
            } else {
                mostrarNotificacion(`${this.nombre} finalizada correctamente.`, 'success');
            }
        });
    }
}

window.SubprocesoEnsambleController = SubprocesoEnsambleController;
