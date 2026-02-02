// ============================================
// validation.js - Client-side Validation
// Previene errores 500 validando en el cliente
// ============================================

const FormValidator = {
    /**
     * Validar formulario completo
     */
    validateForm: function (formId) {
        const form = document.getElementById(formId);
        if (!form) {
            console.warn(`Formulario ${formId} no encontrado`);
            return false;
        }

        let isValid = true;
        const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');

        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        return isValid;
    },

    /**
     * Validar campo individual
     */
    validateField: function (input) {
        const value = input.value.trim();
        const type = input.type;
        const required = input.hasAttribute('required');

        // Limpiar estados previos
        this.clearFieldState(input);

        // Validar requerido
        if (required && !value) {
            this.setInvalid(input, 'Este campo es obligatorio');
            return false;
        }

        // Validar por tipo
        if (value) {
            switch (type) {
                case 'email':
                    if (!this.isValidEmail(value)) {
                        this.setInvalid(input, 'Email inválido');
                        return false;
                    }
                    break;
                case 'number':
                    if (!this.isValidNumber(value, input)) {
                        this.setInvalid(input, 'Número inválido');
                        return false;
                    }
                    break;
                case 'date':
                    if (!value) {
                        this.setInvalid(input, 'Fecha inválida');
                        return false;
                    }
                    break;
                case 'tel':
                    if (!this.isValidPhone(value)) {
                        this.setInvalid(input, 'Teléfono inválido');
                        return false;
                    }
                    break;
            }
        }

        // Si llegó aquí, es válido
        if (value) {
            this.setValid(input);
        }
        return true;
    },

    /**
     * Marcar campo como inválido
     */
    setInvalid: function (input, message) {
        input.classList.add('is-invalid');
        input.classList.remove('is-valid');

        // Crear o actualizar mensaje de error
        let feedback = input.nextElementSibling;
        if (!feedback || !feedback.classList.contains('invalid-feedback')) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            input.parentNode.insertBefore(feedback, input.nextSibling);
        }
        feedback.textContent = message;
        feedback.style.display = 'block';
    },

    /**
     * Marcar campo como válido
     */
    setValid: function (input) {
        input.classList.add('is-valid');
        input.classList.remove('is-invalid');

        // Ocultar mensaje de error
        const feedback = input.nextElementSibling;
        if (feedback && feedback.classList.contains('invalid-feedback')) {
            feedback.style.display = 'none';
        }
    },

    /**
     * Limpiar estado del campo
     */
    clearFieldState: function (input) {
        input.classList.remove('is-valid', 'is-invalid');
        const feedback = input.nextElementSibling;
        if (feedback && (feedback.classList.contains('invalid-feedback') || feedback.classList.contains('valid-feedback'))) {
            feedback.style.display = 'none';
        }
    },

    /**
     * Validar email
     */
    isValidEmail: function (email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },

    /**
     * Validar número
     */
    isValidNumber: function (value, input) {
        const num = parseFloat(value);
        if (isNaN(num)) return false;

        const min = input.getAttribute('min');
        const max = input.getAttribute('max');

        if (min !== null && num < parseFloat(min)) return false;
        if (max !== null && num > parseFloat(max)) return false;

        return true;
    },

    /**
     * Validar teléfono
     */
    isValidPhone: function (phone) {
        // Acepta formatos: 1234567890, 123-456-7890, (123) 456-7890
        const re = /^[\d\s\-\(\)]+$/;
        return re.test(phone) && phone.replace(/\D/g, '').length >= 7;
    },

    /**
     * Inicializar validación en tiempo real
     */
    initRealtimeValidation: function (formId) {
        const form = document.getElementById(formId);
        if (!form) {
            console.warn(`Formulario ${formId} no encontrado para validación`);
            return;
        }

        console.log(`✅ Validación en tiempo real activada para: ${formId}`);

        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            // Validar al perder foco
            input.addEventListener('blur', () => {
                if (input.value.trim() || input.hasAttribute('required')) {
                    this.validateField(input);
                }
            });

            // Limpiar error al escribir
            input.addEventListener('input', () => {
                if (input.classList.contains('is-invalid')) {
                    this.clearFieldState(input);
                }
            });
        });

        // Validar al enviar
        form.addEventListener('submit', (e) => {
            if (!this.validateForm(formId)) {
                e.preventDefault();
                e.stopPropagation();

                // Scroll al primer error
                const firstInvalid = form.querySelector('.is-invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstInvalid.focus();
                }

                if (window.mostrarNotificacion) {
                    mostrarNotificacion('Por favor completa todos los campos requeridos', 'error');
                }
            }
        });
    },

    /**
     * Validar select con productos
     */
    validateProductSelect: function (selectId) {
        const select = document.getElementById(selectId);
        if (!select) return false;

        if (!select.value || select.value === '') {
            this.setInvalid(select, 'Debes seleccionar un producto');
            return false;
        }

        this.setValid(select);
        return true;
    }
};

// Exportar
window.FormValidator = FormValidator;

console.log('📋 Módulo de validación cargado');
