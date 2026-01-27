// ===========================
// VALIDATION HELPERS - Funciones de Validación Compartidas
// ===========================

/**
 * Módulo con funciones reutilizables para validación de formularios.
 * Proporciona validaciones consistentes y mensajes de error estandarizados.
 */
const ValidationHelpers = (() => {

    /**
     * Valida un formulario usando validación HTML5.
     * 
     * Verifica que todos los campos requeridos estén completos y sean válidos
     * según las reglas HTML5 (required, pattern, type, etc.).
     * 
     * @param {string} formId - ID del formulario a validar
     * @returns {boolean} - true si el formulario es válido, false si no
     * 
     * @example
     * if (!validarFormulario('form-inyeccion')) {
     *   return; // Detener el proceso si hay errores
     * }
     */
    function validarFormulario(formId) {
        const form = document.getElementById(formId);

        if (!form) {
            console.error(`❌ Formulario no encontrado: ${formId}`);
            return false;
        }

        // Usar validación HTML5 nativa
        if (!form.checkValidity()) {
            form.reportValidity(); // Mostrar mensajes de error nativos
            return false;
        }

        return true;
    }

    /**
     * Valida que se haya seleccionado un producto.
     * 
     * Verifica que el código del producto no esté vacío y muestra un mensaje
     * de error si es necesario.
     * 
     * @param {string} codigoProducto - Código del producto a validar
     * @param {string} [mensajePersonalizado] - Mensaje de error personalizado
     * @returns {boolean} - true si es válido, false si no
     * 
     * @example
     * if (!validarProductoSeleccionado(formData.codigo_producto)) {
     *   return; // Detener el proceso
     * }
     */
    function validarProductoSeleccionado(codigoProducto, mensajePersonalizado) {
        if (!codigoProducto || codigoProducto.trim() === '') {
            const mensaje = mensajePersonalizado || 'Por favor selecciona un producto';
            mostrarErrorValidacion(mensaje);
            return false;
        }
        return true;
    }

    /**
     * Valida que una cantidad sea un número positivo.
     * 
     * Verifica que el valor sea un número mayor a cero y muestra un mensaje
     * de error descriptivo si no lo es.
     * 
     * @param {number|string} cantidad - Cantidad a validar
     * @param {string} nombreCampo - Nombre del campo para el mensaje de error
     * @returns {boolean} - true si es válido, false si no
     * 
     * @example
     * if (!validarCantidadPositiva(formData.cantidad_recibida, 'cantidad recibida')) {
     *   return; // Detener el proceso
     * }
     */
    function validarCantidadPositiva(cantidad, nombreCampo) {
        const num = typeof cantidad === 'string' ? parseFloat(cantidad) : cantidad;

        if (isNaN(num) || num <= 0) {
            const mensaje = `La ${nombreCampo} debe ser mayor a 0`;
            mostrarErrorValidacion(mensaje);
            return false;
        }
        return true;
    }

    /**
     * Valida que una cantidad no sea negativa (puede ser cero).
     * 
     * @param {number|string} cantidad - Cantidad a validar
     * @param {string} nombreCampo - Nombre del campo para el mensaje de error
     * @returns {boolean} - true si es válido, false si no
     * 
     * @example
     * if (!validarCantidadNoNegativa(formData.pnc, 'cantidad de PNC')) {
     *   return;
     * }
     */
    function validarCantidadNoNegativa(cantidad, nombreCampo) {
        const num = typeof cantidad === 'string' ? parseFloat(cantidad) : cantidad;

        if (isNaN(num) || num < 0) {
            const mensaje = `La ${nombreCampo} no puede ser negativa`;
            mostrarErrorValidacion(mensaje);
            return false;
        }
        return true;
    }

    /**
     * Valida que un campo de texto no esté vacío.
     * 
     * @param {string} valor - Valor a validar
     * @param {string} nombreCampo - Nombre del campo para el mensaje de error
     * @returns {boolean} - true si es válido, false si no
     * 
     * @example
     * if (!validarCampoRequerido(formData.responsable, 'responsable')) {
     *   return;
     * }
     */
    function validarCampoRequerido(valor, nombreCampo) {
        if (!valor || valor.trim() === '') {
            const mensaje = `El campo ${nombreCampo} es requerido`;
            mostrarErrorValidacion(mensaje);
            return false;
        }
        return true;
    }

    /**
     * Valida un rango de valores numéricos.
     * 
     * @param {number} valor - Valor a validar
     * @param {number} min - Valor mínimo permitido
     * @param {number} max - Valor máximo permitido
     * @param {string} nombreCampo - Nombre del campo para el mensaje de error
     * @returns {boolean} - true si es válido, false si no
     * 
     * @example
     * if (!validarRango(cavidades, 1, 32, 'número de cavidades')) {
     *   return;
     * }
     */
    function validarRango(valor, min, max, nombreCampo) {
        const num = typeof valor === 'string' ? parseFloat(valor) : valor;

        if (isNaN(num) || num < min || num > max) {
            const mensaje = `${nombreCampo} debe estar entre ${min} y ${max}`;
            mostrarErrorValidacion(mensaje);
            return false;
        }
        return true;
    }

    /**
     * Muestra un mensaje de error de validación al usuario.
     * 
     * Usa alert por defecto, pero puede ser extendido para usar
     * un sistema de notificaciones más sofisticado.
     * 
     * @param {string} mensaje - Mensaje de error a mostrar
     * @returns {void}
     * 
     * @example
     * mostrarErrorValidacion('El código de producto es inválido');
     */
    function mostrarErrorValidacion(mensaje) {
        // Usar la función global de notificaciones si existe
        if (typeof window.mostrarNotificacion === 'function') {
            window.mostrarNotificacion(mensaje, 'error');
        } else {
            // Fallback a alert
            alert(`⚠️ ${mensaje}`);
        }
    }

    /**
     * Valida múltiples campos requeridos a la vez.
     * 
     * @param {Object} data - Objeto con los datos a validar
     * @param {Array<string>} campos - Array de nombres de campos requeridos
     * @returns {boolean} - true si todos son válidos, false si alguno falla
     * 
     * @example
     * const esValido = validarCamposRequeridos(formData, [
     *   'responsable', 'maquina', 'codigo_producto'
     * ]);
     */
    function validarCamposRequeridos(data, campos) {
        for (const campo of campos) {
            if (!data[campo] || (typeof data[campo] === 'string' && data[campo].trim() === '')) {
                mostrarErrorValidacion(`El campo ${campo.replace('_', ' ')} es requerido`);
                return false;
            }
        }
        return true;
    }

    // Exportar funciones públicas
    return {
        validarFormulario,
        validarProductoSeleccionado,
        validarCantidadPositiva,
        validarCantidadNoNegativa,
        validarCampoRequerido,
        validarRango,
        validarCamposRequeridos,
        mostrarErrorValidacion
    };
})();

// Exportar al scope global
window.ValidationHelpers = ValidationHelpers;

console.log('✅ ValidationHelpers cargado');
