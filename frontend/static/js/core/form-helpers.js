// ===========================
// FORM HELPERS - Funciones Compartidas para Formularios
// ===========================

/**
 * Módulo con funciones reutilizables para configuración de formularios.
 * Consolida lógica duplicada en múltiples módulos (inyección, pulido, ensamble).
 */
const FormHelpers = (() => {

    /**
     * Configura un datalist con la lista de productos disponibles.
     * 
     * Esta función crea o actualiza un elemento datalist para autocompletar
     * productos en un input. Obtiene los productos desde window.AppState.sharedData.
     * 
     * @param {string} inputId - ID del input que usará el datalist
     * @param {string} datalistId - ID del datalist a crear/actualizar
     * @returns {void}
     * 
     * @example
     * // Configurar datalist para el input de inyección
     * configurarDatalistProductos('codigo-producto-inyeccion', 'productos-list');
     */
    function configurarDatalistProductos(inputId, datalistId) {
        const input = document.getElementById(inputId);
        const { productos } = window.AppState?.sharedData || {};

        // Early return si no hay input o productos
        if (!input || !productos) {
            console.warn(`⚠️ No se pudo configurar datalist: input=${!!input}, productos=${!!productos}`);
            return;
        }

        // Crear o limpiar datalist
        let datalist = document.getElementById(datalistId);
        if (!datalist) {
            datalist = document.createElement('datalist');
            datalist.id = datalistId;
            input.parentElement.appendChild(datalist);
            input.setAttribute('list', datalistId);
        }

        // Poblar datalist con productos
        datalist.innerHTML = '';
        productos.forEach(p => {
            const option = document.createElement('option');
            option.value = p.codigo_sistema;
            option.textContent = `${p.codigo_sistema} - ${p.descripcion}`;
            datalist.appendChild(option);
        });

        console.log(`✅ Datalist configurado: ${productos.length} productos`);
    }

    /**
     * Configura un selector (select) con opciones dinámicas.
     * 
     * Limpia el selector y lo puebla con las opciones proporcionadas.
     * Agrega una opción placeholder al inicio.
     * 
     * @param {string} selectId - ID del elemento select
     * @param {Array<string>} opciones - Array de opciones a agregar
     * @param {string} [placeholder='Seleccionar...'] - Texto del placeholder
     * @returns {void}
     * 
     * @example
     * // Configurar selector de responsables
     * configurarSelector('responsable-inyeccion', ['Juan', 'María'], 'Seleccionar responsable...');
     */
    function configurarSelector(selectId, opciones, placeholder = 'Seleccionar...') {
        const select = document.getElementById(selectId);

        if (!select) {
            console.warn(`⚠️ Selector no encontrado: ${selectId}`);
            return;
        }

        if (!opciones || !Array.isArray(opciones)) {
            console.warn(`⚠️ Opciones inválidas para selector ${selectId}`);
            return;
        }

        // Limpiar y agregar placeholder
        select.innerHTML = `<option value="">${placeholder}</option>`;

        // Agregar opciones
        opciones.forEach(opcion => {
            const option = document.createElement('option');
            option.value = opcion;
            option.textContent = opcion;
            select.appendChild(option);
        });

        console.log(`✅ Selector configurado: ${selectId} con ${opciones.length} opciones`);
    }

    /**
     * Establece la fecha actual en un input de tipo date.
     * 
     * Solo establece la fecha si el input está vacío, para no sobrescribir
     * valores existentes.
     * 
     * @param {string} inputId - ID del input de fecha
     * @returns {void}
     * 
     * @example
     * establecerFechaActual('fecha-inyeccion');
     */
    function establecerFechaActual(inputId) {
        const fechaInput = document.getElementById(inputId);

        if (!fechaInput) {
            console.warn(`⚠️ Input de fecha no encontrado: ${inputId}`);
            return;
        }

        // Solo establecer si está vacío
        if (!fechaInput.value) {
            const hoy = new Date().toISOString().split('T')[0];
            fechaInput.value = hoy;
            console.log(`✅ Fecha establecida: ${hoy}`);
        }
    }

    /**
     * Configura listeners de input para cálculo automático.
     * 
     * Agrega event listeners a múltiples inputs para ejecutar una función
     * callback cuando cambian sus valores.
     * 
     * @param {Array<string>} inputIds - Array de IDs de inputs
     * @param {Function} callbackFn - Función a ejecutar cuando cambian los valores
     * @returns {void}
     * 
     * @example
     * // Configurar cálculo automático para producción
     * configurarCalculoAutomatico(
     *   ['cantidad-inyeccion', 'cavidades-inyeccion', 'pnc-inyeccion'],
     *   actualizarCalculoProduccion
     * );
     */
    function configurarCalculoAutomatico(inputIds, callbackFn) {
        if (!Array.isArray(inputIds) || typeof callbackFn !== 'function') {
            console.error('❌ Parámetros inválidos para configurarCalculoAutomatico');
            return;
        }

        let configurados = 0;
        inputIds.forEach(inputId => {
            const element = document.getElementById(inputId);
            if (element) {
                element.addEventListener('input', callbackFn);
                configurados++;
            } else {
                console.warn(`⚠️ Input no encontrado: ${inputId}`);
            }
        });

        console.log(`✅ Cálculo automático configurado: ${configurados}/${inputIds.length} inputs`);
    }

    /**
     * Configura el evento submit de un formulario.
     * 
     * Previene el comportamiento por defecto y ejecuta una función async.
     * 
     * @param {string} formId - ID del formulario
     * @param {Function} submitHandler - Función async a ejecutar en submit
     * @returns {void}
     * 
     * @example
     * configurarFormularioSubmit('form-inyeccion', registrarInyeccion);
     */
    function configurarFormularioSubmit(formId, submitHandler) {
        const form = document.getElementById(formId);

        if (!form) {
            console.error(`❌ Formulario no encontrado: ${formId}`);
            return;
        }

        if (typeof submitHandler !== 'function') {
            console.error('❌ submitHandler debe ser una función');
            return;
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await submitHandler();
        });

        console.log(`✅ Formulario configurado: ${formId}`);
    }

    /**
     * Configura el evento reset de un formulario.
     * 
     * @param {string} formId - ID del formulario
     * @param {Function} resetHandler - Función a ejecutar en reset
     * @returns {void}
     * 
     * @example
     * configurarFormularioReset('form-inyeccion', () => {
     *   defectosTemp = [];
     *   actualizarCalculoProduccion();
     * });
     */
    function configurarFormularioReset(formId, resetHandler) {
        const form = document.getElementById(formId);

        if (!form) {
            console.warn(`⚠️ Formulario no encontrado: ${formId}`);
            return;
        }

        if (typeof resetHandler !== 'function') {
            console.error('❌ resetHandler debe ser una función');
            return;
        }

        form.addEventListener('reset', resetHandler);
        console.log(`✅ Reset configurado: ${formId}`);
    }

    // Exportar funciones públicas
    return {
        configurarDatalistProductos,
        configurarSelector,
        establecerFechaActual,
        configurarCalculoAutomatico,
        configurarFormularioSubmit,
        configurarFormularioReset
    };
})();

// Exportar al scope global
window.FormHelpers = FormHelpers;

console.log('✅ FormHelpers cargado');
