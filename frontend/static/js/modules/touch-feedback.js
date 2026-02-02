// ============================================
// touch-feedback.js - Touch Feedback Enhancement
// Mejora el feedback táctil en botones y elementos
// ============================================

const TouchFeedback = {
    /**
     * Añadir loading state a botón
     */
    setButtonLoading: function (button, loading = true) {
        if (!button) return;

        if (loading) {
            button.classList.add('btn-loading');
            button.disabled = true;
            button.dataset.originalText = button.innerHTML;
        } else {
            button.classList.remove('btn-loading');
            button.disabled = false;
            if (button.dataset.originalText) {
                button.innerHTML = button.dataset.originalText;
                delete button.dataset.originalText;
            }
        }
    },

    /**
     * Añadir ripple effect
     */
    addRippleEffect: function (element, event) {
        const ripple = document.createElement('span');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = event.clientX - rect.left - size / 2;
        const y = event.clientY - rect.top - size / 2;

        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = x + 'px';
        ripple.style.top = y + 'px';
        ripple.className = 'ripple';

        element.appendChild(ripple);

        setTimeout(() => ripple.remove(), 600);
    },

    /**
     * Inicializar feedback táctil
     */
    init: function () {
        console.log('👆 Inicializando feedback táctil...');

        // Añadir ripple a todos los botones
        document.querySelectorAll('.btn, button:not(.btn-icon)').forEach(btn => {
            // Asegurar que el botón tenga position relative
            const position = window.getComputedStyle(btn).position;
            if (position === 'static') {
                btn.style.position = 'relative';
            }
            btn.style.overflow = 'hidden';

            btn.addEventListener('click', (e) => {
                this.addRippleEffect(btn, e);
            });
        });

        // Añadir feedback visual a enlaces del menú
        document.querySelectorAll('.menu-item a').forEach(link => {
            link.addEventListener('touchstart', () => {
                link.style.transform = 'scale(0.98)';
            });

            link.addEventListener('touchend', () => {
                setTimeout(() => {
                    link.style.transform = '';
                }, 100);
            });
        });

        // Añadir feedback a botones de iconos
        document.querySelectorAll('.btn-icon').forEach(btn => {
            btn.addEventListener('touchstart', () => {
                btn.style.opacity = '0.7';
            });

            btn.addEventListener('touchend', () => {
                setTimeout(() => {
                    btn.style.opacity = '';
                }, 100);
            });
        });

        console.log('✅ Feedback táctil activado');
    },

    /**
     * Añadir overlay de sidebar para móvil
     */
    initSidebarOverlay: function () {
        // Crear overlay si no existe
        let overlay = document.querySelector('.sidebar-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'sidebar-overlay';
            document.body.appendChild(overlay);
        }

        const sidebar = document.querySelector('.sidebar');
        const toggleBtn = document.querySelector('.btn-icon.d-lg-none');

        if (!sidebar || !toggleBtn) return;

        // Toggle sidebar
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('active');
            overlay.classList.toggle('active');
        });

        // Cerrar al hacer click en overlay
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
        });

        console.log('✅ Sidebar overlay configurado');
    }
};

// Inicializar al cargar el DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        TouchFeedback.init();
        TouchFeedback.initSidebarOverlay();
    });
} else {
    TouchFeedback.init();
    TouchFeedback.initSidebarOverlay();
}

// Exportar
window.TouchFeedback = TouchFeedback;

console.log('👆 Módulo de feedback táctil cargado');
