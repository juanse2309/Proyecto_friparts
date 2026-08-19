// ============================================
// subproceso_ensamble_base.js
// Clase base reutilizable para los subprocesos de Ensamble (Pintura, Rayada,
// Hornos). De cara al operario es UN SOLO formulario con UN SOLO botón
// ("Registrar"): por debajo, esa acción encadena POST /api/<modulo>/iniciar
// seguido de POST /api/<modulo>/finalizar contra el mismo id de sesión, sin
// exponer el ciclo de dos fases del backend. Se centraliza aquí el manejo de
// estado, la validación previa (para no dejar registros huérfanos en
// EN_PROCESO por datos inválidos), el bloqueo de doble-submit y el feedback
// de error/éxito, para no repetir la misma lógica 3 veces.
// ============================================

class SubprocesoEnsambleController {
    /**
     * @param {Object} config
     * @param {string} config.nombre - Nombre legible del subproceso (ej. 'Pintura').
     * @param {string} config.apiBase - Prefijo de API (ej. '/api/pintura').
     * @param {string} config.idSesionKey - Clave del identificador de sesión en las respuestas del backend (ej. 'id_pintura').
     * @param {string} config.btnRegistrarId - ID del botón único de Registrar.
     * @param {Function} config.construirPayloadIniciar - () => Object payload para /iniciar.
     * @param {Function} config.validarIniciar - (payload) => string|null (mensaje de error o null si válido).
     * @param {Function} config.construirPayloadFinalizar - (idSesion) => Object payload para /finalizar.
     * @param {Function} config.validarFinalizar - (payload) => string|null.
     * @param {Function} [config.limpiarCampos] - () => void. Limpia los inputs tras un registro exitoso.
     */
    constructor(config) {
        this.nombre = config.nombre;
        this.apiBase = config.apiBase;
        this.idSesionKey = config.idSesionKey;
        this.btnRegistrarId = config.btnRegistrarId;
        this.construirPayloadIniciar = config.construirPayloadIniciar;
        this.validarIniciar = config.validarIniciar;
        this.construirPayloadFinalizar = config.construirPayloadFinalizar;
        this.validarFinalizar = config.validarFinalizar;
        this.limpiarCampos = config.limpiarCampos || (() => {});

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
                        // codigo_sistema es la columna única/canónica de db_productos
                        // (ver sql_models.py) -- es la que se muestra en el resto de
                        // la app (ej. autocomplete de Ensamble). id_codigo es un campo
                        // secundario que a veces coincide y a veces no (ej. FR-9380 vs
                        // 9380 sin prefijo): si solo se acepta uno de los dos, el
                        // operario que escribe la referencia "de siempre" (con
                        // prefijo) se topa con "Referencia inválida" aunque el
                        // producto exista. Se registran AMBAS formas como válidas.
                        const codigoPrincipal = p.codigo_sistema || p.id_codigo || p.codigo;
                        if (!codigoPrincipal) return;

                        [p.codigo_sistema, p.id_codigo, p.codigo].forEach(c => {
                            if (c) SubprocesoEnsambleController._referenciasValidas.add(String(c).trim().toUpperCase());
                        });

                        if (datalist) {
                            const opt = document.createElement('option');
                            opt.value = codigoPrincipal;
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
     * Valida que hora_fin sea posterior a hora_inicio. Ambas vienen del mismo
     * formulario (mismo formato "HH:MM"), así que la comparación siempre es
     * directa -- ya no hay dos pasos separados en el tiempo.
     */
    static horaFinEsPosterior(horaInicioStr, horaFinStr) {
        if (!horaInicioStr || !horaFinStr) return true;
        return horaFinStr > horaInicioStr;
    }

    obtenerResponsable() {
        return (document.getElementById('current_user_fullname')?.value
            || document.getElementById('responsable')?.value
            || '').trim();
    }

    async _postJson(ruta, payload) {
        const res = await fetch(`${this.apiBase}${ruta}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return res.json();
    }

    /**
     * Único punto de entrada de cara al operario: "Registrar". Valida TODO el
     * formulario (inicio + fin) antes de tocar la red -- si algo es inválido,
     * jamás se llega a crear un registro EN_PROCESO huérfano en el backend --
     * y luego encadena iniciar -> finalizar como una sola operación bloqueando
     * el botón (spinner) durante ambas llamadas, con reactivación garantizada
     * en el finally pase lo que pase.
     */
    async registrar() {
        const payloadIniciar = this.construirPayloadIniciar();

        // --- Guard Clauses: se ejecutan ANTES de cualquier fetch ---
        const errorIniciar = this.validarIniciar(payloadIniciar);
        if (errorIniciar) {
            this._mostrarError('Datos incompletos', errorIniciar, 'warning');
            return;
        }

        // --- Guard de Integridad (Strict Match) sobre el catálogo ---
        await this.constructor.cargarCatalogoReferencias();
        if (!this.constructor.esReferenciaValida(payloadIniciar.id_codigo)) {
            this._mostrarError('Referencia inválida', 'Referencia inválida o no existe en el catálogo.', 'error');
            return;
        }

        // Payload de cierre pre-armado (sin id de sesión aún) solo para
        // validar los campos de finalización en el mismo paso.
        const payloadFinalizarPreview = this.construirPayloadFinalizar(null);
        const errorFinalizar = this.validarFinalizar(payloadFinalizarPreview);
        if (errorFinalizar) {
            this._mostrarError('Datos incompletos', errorFinalizar, 'warning');
            return;
        }

        const btn = document.getElementById(this.btnRegistrarId);
        const textoOriginal = btn ? btn.innerHTML : '';

        try {
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Guardando...';
            }

            const dataIni = await this._postJson('/iniciar', payloadIniciar);
            if (!dataIni || !dataIni.success) {
                throw new Error((dataIni && dataIni.error) || 'No se pudo registrar el inicio.');
            }

            const idSesion = dataIni.data?.[this.idSesionKey];
            const payloadFinal = this.construirPayloadFinalizar(idSesion);

            const dataFin = await this._postJson('/finalizar', payloadFinal);
            if (!dataFin || !dataFin.success) {
                throw new Error((dataFin && dataFin.error) || 'No se pudo completar el registro.');
            }

            this.limpiarCampos();

            if (window.Swal) {
                Swal.fire({
                    icon: 'success',
                    title: `¡${this.nombre} registrada!`,
                    timer: 2000,
                    showConfirmButton: false
                });
            } else {
                mostrarNotificacion(`${this.nombre} registrada correctamente.`, 'success');
            }
        } catch (e) {
            console.error(`[${this.nombre}] Error al registrar:`, e);
            this._mostrarError('No se pudo procesar', e.message || 'No se pudo contactar al servidor. Intenta de nuevo.', 'error');
        } finally {
            // Reactivación GARANTIZADA del botón, haya éxito o error.
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = textoOriginal;
            }
        }
    }

    _mostrarError(titulo, mensaje, tipo) {
        if (window.Swal) {
            Swal.fire(titulo, mensaje, tipo);
        } else {
            mostrarNotificacion(mensaje, tipo);
        }
    }
}

window.SubprocesoEnsambleController = SubprocesoEnsambleController;
