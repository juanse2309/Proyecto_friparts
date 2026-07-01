/**
 * Módulo reutilizable de Autoguardado de Formularios (Form Auto-Save)
 * Diseñado con medidas estrictas de aislamiento de sesión y prevención de OOM/obsolescencia.
 */
class FormAutoSave {
    /**
     * @param {HTMLFormElement} form - Elemento de formulario de tipo HTMLFormElement.
     * @param {string} formId - Identificador único para el formulario.
     * @param {Object} options - Opciones de configuración adicionales.
     * @param {number} options.debounceDelay - Retraso del debouncer en ms (default: 500).
     * @param {number} options.maxAgeHours - Tiempo de vida máximo del borrador en horas (default: 12).
     */
    constructor(form, formId, options = {}) {
        if (!form || !(form instanceof HTMLFormElement)) {
            throw new Error("FormAutoSave requiere un elemento <form> válido.");
        }
        if (!formId || typeof formId !== 'string') {
            throw new Error("FormAutoSave requiere un identificador (formId) de tipo string.");
        }

        this.form = form;
        this.formId = formId;
        this.debounceDelay = options.debounceDelay || 500;
        this.maxAgeMs = (options.maxAgeHours || 12) * 60 * 60 * 1000; // 12 Horas por defecto
        
        this.init();
    }

    /**
     * Obtiene el objeto de usuario actual.
     * @returns {Object|null}
     */
    _getCurrentUser() {
        return window.AppState?.user || (typeof AuthModule !== 'undefined' ? AuthModule.currentUser : null);
    }

    /**
     * Obtiene el identificador único del usuario logueado en la sesión.
     * @returns {string} Identificador formateado del usuario.
     */
    _getSessionUserKey() {
        const user = this._getCurrentUser();
        const username = user?.name || user?.nombre || 'anonymous';
        // Sanitizar el nombre del usuario para usarlo como parte de la llave de localStorage
        return encodeURIComponent(username.toLowerCase().trim().replace(/\s+/g, '_'));
    }

    /**
     * Obtiene la clave de almacenamiento exclusiva para el usuario y formulario actuales.
     * @returns {string}
     */
    _getStorageKey() {
        const userKey = this._getSessionUserKey();
        return `autosave_${userKey}_${this.formId}`;
    }

    /**
     * Inicializa los escuchadores de eventos y maneja la resolución asíncrona del usuario.
     */
    init() {
        // 1. Crear debouncer para guardar cambios
        const debouncedSave = this._debounce(() => this.saveDraft(), this.debounceDelay);

        // 2. Escuchar cambios de forma delegada para guardar borrador
        this.form.addEventListener('input', debouncedSave);
        this.form.addEventListener('change', debouncedSave);

        // 3. Resolver la condición de carrera antes de restaurar
        this._resolveUserAndRestore();
    }

    /**
     * Espera a que el usuario esté autenticado para intentar restaurar el borrador.
     * Si no se resuelve o es 'anonymous', aborta silenciosamente.
     */
    _resolveUserAndRestore() {
        const isUserValid = () => {
            const user = this._getCurrentUser();
            const username = user?.name || user?.nombre;
            return username && username.toLowerCase() !== 'anonymous';
        };

        // Si ya está cargado el usuario, restaurar inmediatamente
        if (isUserValid()) {
            this.restoreDraft();
            return;
        }

        // Si no está listo, registrar listeners del evento nativo
        const handleUserReady = () => {
            if (isUserValid()) {
                this.restoreDraft();
                cleanup();
            }
        };

        // Polling de seguridad (máximo 3 segundos)
        let pollCount = 0;
        const interval = setInterval(() => {
            pollCount++;
            if (isUserValid()) {
                this.restoreDraft();
                cleanup();
            } else if (pollCount > 30) { // 3 segundos (30 * 100ms)
                console.warn(`[AutoSave] Abortando restauración para ${this.formId}: Usuario no autenticado o anonymous.`);
                cleanup();
            }
        }, 100);

        const cleanup = () => {
            clearInterval(interval);
            window.removeEventListener('user-ready', handleUserReady);
            document.removeEventListener('user-ready', handleUserReady);
        };

        window.addEventListener('user-ready', handleUserReady);
        document.addEventListener('user-ready', handleUserReady);
    }

    /**
     * Serializa los campos del formulario excluyendo contraseñas y archivos.
     * @returns {Object}
     */
    _serializeForm() {
        const data = {};
        const elements = this.form.querySelectorAll('input, select, textarea');
        const excludeTypes = ['password', 'file', 'submit', 'button'];

        elements.forEach(el => {
            const key = el.name || el.id;
            if (!key || excludeTypes.includes(el.type)) return;

            if (el.type === 'checkbox') {
                data[key] = el.checked;
            } else if (el.type === 'radio') {
                if (el.checked) {
                    data[key] = el.value;
                }
            } else {
                data[key] = el.value;
            }
        });

        return data;
    }

    /**
     * Guarda el estado actual en el localStorage con un timestamp.
     */
    saveDraft() {
        const user = this._getCurrentUser();
        const username = user?.name || user?.nombre;

        // Abortar si no hay usuario real autenticado
        if (!username || username.toLowerCase() === 'anonymous') {
            console.debug(`[AutoSave] Ignorando autoguardado para ${this.formId}: usuario es anonymous o no autenticado.`);
            return;
        }

        try {
            const data = this._serializeForm();
            // Evitar guardar borradores vacíos
            if (Object.keys(data).length === 0) return;

            const payload = {
                timestamp: Date.now(),
                data: data
            };

            const key = this._getStorageKey();
            localStorage.setItem(key, JSON.stringify(payload));
            console.debug(`[AutoSave] Guardado borrador para ${key}`);
        } catch (e) {
            console.error("[AutoSave] Error guardando borrador en localStorage", e);
        }
    }

    /**
     * Restaura los datos del borrador si cumple con las validaciones de obsolescencia.
     */
    restoreDraft() {
        const key = this._getStorageKey();
        const rawPayload = localStorage.getItem(key);
        if (!rawPayload) return;

        try {
            const payload = JSON.parse(rawPayload);
            const now = Date.now();

            // Validación de Obsolescencia: más de 12 horas
            if (now - payload.timestamp > this.maxAgeMs) {
                console.warn(`[AutoSave] Borrador de ${this.formId} expirado (> 12h). Limpiando silenciosamente.`);
                this.clearDraft();
                return;
            }

            const data = payload.data || {};
            const elements = this.form.querySelectorAll('input, select, textarea');
            const elementsToNotify = [];

            elements.forEach(el => {
                const nameOrId = el.name || el.id;
                if (!nameOrId || !(nameOrId in data)) return;

                let hasChanged = false;

                if (el.type === 'checkbox') {
                    const newValue = !!data[nameOrId];
                    if (el.checked !== newValue) {
                        el.checked = newValue;
                        hasChanged = true;
                    }
                } else if (el.type === 'radio') {
                    const newValue = (el.value === data[nameOrId]);
                    if (el.checked !== newValue) {
                        el.checked = newValue;
                        hasChanged = true;
                    }
                } else {
                    const newValue = data[nameOrId];
                    if (el.value !== newValue) {
                        el.value = newValue;
                        hasChanged = true;
                    }
                }

                // Si realmente cambió, encolamos para disparar eventos
                if (hasChanged) {
                    elementsToNotify.push(el);
                }
            });

            // Mitigación de Avalancha de Eventos: procesamiento asíncrono escalonado
            if (elementsToNotify.length > 0) {
                let index = 0;
                const dispatchBatch = () => {
                    const batchSize = 5; // Procesar en bloques pequeños
                    const end = Math.min(index + batchSize, elementsToNotify.length);
                    
                    for (let i = index; i < end; i++) {
                        const el = elementsToNotify[i];
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                    
                    index = end;
                    if (index < elementsToNotify.length) {
                        requestAnimationFrame(dispatchBatch);
                    }
                };
                requestAnimationFrame(dispatchBatch);
            }

            console.log(`[AutoSave] Borrador restaurado con éxito para formulario: ${this.formId}`);
            
            // Inyectar botón de descarte (Escape Hatch UI)
            this._injectDiscardButton();

        } catch (e) {
            console.error("[AutoSave] Error parseando o aplicando borrador", e);
            this.clearDraft();
        }
    }

    /**
     * Inyecta dinámicamente un botón para descartar el borrador.
     */
    _injectDiscardButton() {
        // Evitar duplicados
        if (this.form.querySelector('.autosave-discard-btn')) return;

        const submitBtn = this.form.querySelector('button[type="submit"], input[type="submit"]');
        const discardBtn = document.createElement('button');
        discardBtn.type = 'button';
        discardBtn.className = 'btn btn-sm btn-outline-danger ms-2 autosave-discard-btn';
        discardBtn.textContent = 'Descartar Borrador';
        discardBtn.style.fontSize = '0.8rem';
        discardBtn.style.padding = '0.25rem 0.5rem';
        discardBtn.style.borderRadius = '20px';
        discardBtn.style.transition = 'all 0.2s ease';

        discardBtn.addEventListener('click', () => {
            this.clearDraft();
            this.form.reset();
            discardBtn.remove();
        });

        if (submitBtn) {
            submitBtn.parentNode.insertBefore(discardBtn, submitBtn.nextSibling);
        } else {
            this.form.appendChild(discardBtn);
        }
    }

    /**
     * Elimina el borrador asociado a este formulario de localStorage.
     */
    clearDraft() {
        const key = this._getStorageKey();
        localStorage.removeItem(key);
        console.log(`[AutoSave] Borrador eliminado para: ${key}`);

        // Limpiar el botón de UI si existe
        const discardBtn = this.form.querySelector('.autosave-discard-btn');
        if (discardBtn) {
            discardBtn.remove();
        }
    }

    /**
     * Helper de debouncing clásico.
     */
    _debounce(func, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    }
}

// Exponer la clase globalmente en el scope window
window.FormAutoSave = FormAutoSave;
