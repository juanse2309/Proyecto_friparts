/**
 * Dashboard Tour — guía interactiva desacoplada del Dashboard IA.
 *
 * Reglas de arquitectura (aprobadas):
 * 1. Cero acoplamiento: solo LEE el DOM que dashboard.js pinta (selectores estructurales
 *    que existen en el HTML inicial). Nunca llama funciones internas de ModuloDashboard
 *    ni se engancha a cargarDatos()/renderizarTodo().
 * 2. Ligereza: usa exclusivamente bootstrap.Popover (ya cargado por bootstrap.bundle.min.js).
 *    Cero librerías nuevas.
 * 3. Persistencia local: el estado "tutorial visto" vive 100% en localStorage. El backend
 *    nunca se entera de esto.
 */
window.DashboardTour = (function () {
    'use strict';

    const STORAGE_KEY = 'frt_tour_dashboard_v1';

    const STEPS = [
        {
            selector: '#dashboard-icono-ayuda-ejemplo',
            title: '1/5 · Íconos de Ayuda',
            content: 'Cada tarjeta del dashboard tiene un ícono ⓘ junto a su título. Pasa el mouse por encima para ver la explicación directa de esa tarjeta específica.',
            placement: 'bottom'
        },
        {
            selector: '#dashboard-filtros-globales',
            title: '2/5 · Filtros Globales',
            content: 'Filtra la información de todo el tablero por rango de fechas.',
            placement: 'bottom'
        },
        {
            selector: '#dashboard-btn-refrescar',
            title: '3/5 · Actualizar Datos',
            content: 'Fuerza una lectura fresca de los datos en vivo sin perder el rango de fechas seleccionado.',
            placement: 'bottom'
        },
        {
            selector: '#dashboard-bot-container',
            title: '4/5 · Análisis Inteligente',
            content: 'El Bot de Planta cruza producción, calidad y ventas para generar insights ejecutivos automáticamente.',
            placement: 'bottom'
        },
        {
            selector: '#dashboard-toggle-unidades-dinero',
            title: '5/5 · Unidades vs. Dinero',
            content: 'Alterna la visualización de las tarjetas entre Unidades y Dinero para comparar el rendimiento desde ambas perspectivas.',
            placement: 'left'
        }
    ];

    // --- Estado interno del tour activo ---
    let activeSteps = [];
    let currentIndex = -1;
    let currentPopover = null;
    let currentTargetEl = null;
    let overlayEl = null;
    let resizeHandler = null;
    let keydownHandler = null;
    let clickHandler = null;
    let pendingTimeoutId = null;

    function esVisible(el) {
        return !!el && el.offsetParent !== null;
    }

    function crearOverlay() {
        if (overlayEl) return overlayEl;
        overlayEl = document.createElement('div');
        overlayEl.className = 'dtour-overlay';
        document.body.appendChild(overlayEl);
        return overlayEl;
    }

    function destruirOverlay() {
        if (overlayEl) {
            overlayEl.remove();
            overlayEl = null;
        }
    }

    // Mitigación de memory leaks: SIEMPRE se destruye la instancia previa de Popover
    // (bootstrap.Popover crea listeners/Popper internos que no se liberan solos si
    // solo se oculta el elemento; hay que llamar dispose() explícitamente).
    function limpiarPasoActual() {
        if (pendingTimeoutId) {
            clearTimeout(pendingTimeoutId);
            pendingTimeoutId = null;
        }
        if (currentPopover) {
            currentPopover.dispose();
            currentPopover = null;
        }
        if (currentTargetEl) {
            currentTargetEl.classList.remove('dtour-highlight');
            currentTargetEl = null;
        }
    }

    function construirContenidoHTML(index, total) {
        const esUltimo = index === total - 1;
        const botonAtras = index > 0
            ? '<button type="button" class="dtour-btn dtour-btn-secondary" data-dtour-action="anterior">Atrás</button>'
            : '';
        return `
            <div class="dtour-progress">Paso ${index + 1} de ${total}</div>
            <div class="dtour-nav">
                <button type="button" class="dtour-btn dtour-btn-link" data-dtour-action="cerrar">Saltar tour</button>
                <div class="d-flex gap-2">
                    ${botonAtras}
                    <button type="button" class="dtour-btn dtour-btn-primary" data-dtour-action="siguiente">${esUltimo ? 'Finalizar' : 'Siguiente'}</button>
                </div>
            </div>
        `;
    }

    function mostrarPaso(index) {
        limpiarPasoActual();

        if (index < 0 || index >= activeSteps.length) {
            cerrar();
            return;
        }

        const step = activeSteps[index];
        const el = document.querySelector(step.selector);

        if (!esVisible(el)) {
            // Selector inexistente u oculto por RBAC (data-role-access): saltar al siguiente paso
            mostrarPaso(index + 1);
            return;
        }

        currentIndex = index;
        currentTargetEl = el;
        el.classList.add('dtour-highlight');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Pequeño margen para que el scroll termine antes de posicionar el popover
        pendingTimeoutId = setTimeout(() => {
            pendingTimeoutId = null;
            // Si el usuario ya avanzó/cerró mientras esperábamos el scroll, no crear nada
            if (currentTargetEl !== el) return;

            currentPopover = new bootstrap.Popover(el, {
                container: 'body',
                trigger: 'manual',
                html: true,
                sanitize: false,
                placement: step.placement || 'auto',
                fallbackPlacements: ['top', 'bottom', 'right', 'left'],
                customClass: 'dtour-popover',
                title: `<div class="dtour-popover-title">${step.title}</div>`,
                content: `<div class="dtour-body-text">${step.content}</div>${construirContenidoHTML(index, activeSteps.length)}`
            });
            currentPopover.show();
        }, 300);
    }

    function siguiente() {
        mostrarPaso(currentIndex + 1);
    }

    function anterior() {
        mostrarPaso(currentIndex - 1);
    }

    function marcarComoVisto() {
        try {
            localStorage.setItem(STORAGE_KEY, '1');
        } catch (e) {
            console.warn('DashboardTour: no se pudo escribir en localStorage', e);
        }
    }

    function cerrar() {
        limpiarPasoActual();
        destruirOverlay();

        if (resizeHandler) {
            window.removeEventListener('resize', resizeHandler);
            resizeHandler = null;
        }
        if (keydownHandler) {
            document.removeEventListener('keydown', keydownHandler);
            keydownHandler = null;
        }
        if (clickHandler) {
            document.removeEventListener('click', clickHandler);
            clickHandler = null;
        }

        const habiaTourActivo = currentIndex !== -1;
        currentIndex = -1;
        activeSteps = [];

        if (habiaTourActivo) marcarComoVisto();
        document.dispatchEvent(new CustomEvent('dashboard:tour:end'));
    }

    function iniciar() {
        // Evitar doble arranque si ya hay un tour en curso
        if (currentIndex !== -1) return;

        activeSteps = STEPS.filter(step => esVisible(document.querySelector(step.selector)));
        if (activeSteps.length === 0) {
            console.warn('DashboardTour: no hay pasos visibles para este rol/vista, tour omitido.');
            return;
        }

        crearOverlay();

        clickHandler = (e) => {
            const btn = e.target.closest('[data-dtour-action]');
            if (!btn) return;
            const accion = btn.getAttribute('data-dtour-action');
            if (accion === 'siguiente') siguiente();
            else if (accion === 'anterior') anterior();
            else if (accion === 'cerrar') cerrar();
        };
        document.addEventListener('click', clickHandler);

        keydownHandler = (e) => {
            if (e.key === 'Escape') cerrar();
        };
        document.addEventListener('keydown', keydownHandler);

        resizeHandler = () => {
            if (currentPopover) currentPopover.update();
        };
        window.addEventListener('resize', resizeHandler);

        mostrarPaso(0);
    }

    // Señal puramente de DOM (sin llamar funciones internas de ModuloDashboard):
    // ni el loader de pantalla completa puede seguir visible, ni el bot puede seguir
    // mostrando su placeholder estático — ambos indican que los datos aún no llegaron.
    function pantallaListaParaTour() {
        const loader = document.getElementById('global-loader');
        if (esVisible(loader)) return false;

        const bot = document.getElementById('dashboard-bot-text');
        if (bot && bot.textContent.trim().startsWith('Analizando datos de la planta en tiempo real')) return false;

        return true;
    }

    function autoIniciarSiNoVisto() {
        let visto;
        try {
            visto = localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            console.warn('DashboardTour: localStorage no disponible', e);
            return;
        }
        if (visto !== null) return;

        // Espera a que el contenido real haya cargado (evita que el tour se dibuje
        // encima de placeholders/spinners); tope de seguridad por si el bot falla.
        const ESPERA_MAX_MS = 8000;
        const POLL_MS = 300;
        const inicioEspera = Date.now();

        const esperarCargaYArrancar = () => {
            if (pantallaListaParaTour() || Date.now() - inicioEspera >= ESPERA_MAX_MS) {
                setTimeout(iniciar, 300);
                return;
            }
            setTimeout(esperarCargaYArrancar, POLL_MS);
        };

        setTimeout(esperarCargaYArrancar, 600);
    }

    // --- Auto-arranque desacoplado ---
    // Observa la clase 'active' de #dashboard-page (mecanismo genérico ya usado por
    // app.js para mostrar/ocultar páginas) en vez de engancharse a la inicialización
    // de ModuloDashboard o a la lógica de enrutado en app.js.
    (function initAutoWatch() {
        const pageEl = document.getElementById('dashboard-page');
        if (!pageEl || typeof MutationObserver === 'undefined') return;

        let estabaActiva = pageEl.classList.contains('active');
        if (estabaActiva) autoIniciarSiNoVisto();

        const observer = new MutationObserver(() => {
            const activaAhora = pageEl.classList.contains('active');
            if (activaAhora && !estabaActiva) autoIniciarSiNoVisto();
            estabaActiva = activaAhora;
        });
        observer.observe(pageEl, { attributes: true, attributeFilter: ['class'] });
    })();

    return {
        iniciar,
        cerrar,
        autoIniciarSiNoVisto
    };
})();
