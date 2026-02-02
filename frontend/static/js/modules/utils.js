// ============================================
// utils.js - Funciones compartidas
// ============================================

/**
 * Mostrar notificación visual
 */
function mostrarNotificacion(mensaje, tipo = 'info') {
    // Definir colores de borde según tipo
    const colors = {
        'success': '#10b981', // Green
        'error': '#ef4444',   // Red
        'warning': '#f59e0b', // Amber
        'info': '#3b82f6'     // Blue
    };

    const iconColor = colors[tipo] || colors['info'];

    const icon = {
        'success': `<i class="fas fa-check-circle" style="color: ${iconColor}; font-size: 1.2rem;"></i>`,
        'error': `<i class="fas fa-times-circle" style="color: ${iconColor}; font-size: 1.2rem;"></i>`,
        'warning': `<i class="fas fa-exclamation-triangle" style="color: ${iconColor}; font-size: 1.2rem;"></i>`,
        'info': `<i class="fas fa-info-circle" style="color: ${iconColor}; font-size: 1.2rem;"></i>`
    }[tipo] || '';

    const notificationDiv = document.createElement('div');

    // Estilos profesionales: Fondo blanco, sombra, centrado top
    notificationDiv.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%); /* Centrado horizontal */
        background-color: #ffffff;
        color: #333333;
        padding: 16px 24px;
        border-radius: 12px;
        font-weight: 500;
        font-size: 0.95rem;
        z-index: 10005; /* Encima de todo */
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1); /* Sombra suave pero visible */
        display: flex;
        align-items: center;
        gap: 15px;
        max-width: 90%;
        width: 400px;
        border-left: 6px solid ${iconColor};
        animation: slideInDown 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    `;

    notificationDiv.innerHTML = `
        <div style="flex-shrink: 0;">${icon}</div>
        <span style="flex-grow: 1; line-height: 1.4;">${mensaje}</span>
        <i class="fas fa-times" style="color: #9ca3af; cursor: pointer; font-size: 0.9rem;" onclick="this.parentElement.remove()"></i>
    `;

    document.body.appendChild(notificationDiv);

    // Animaciones
    if (!document.querySelector('style#notification-animations')) {
        const style = document.createElement('style');
        style.id = 'notification-animations';
        style.textContent = `
            @keyframes slideInDown {
                from { transform: translate(-50%, -100%); opacity: 0; }
                to { transform: translate(-50%, 0); opacity: 1; }
            }
            @keyframes fadeOutUp {
                from { opacity: 1; transform: translate(-50%, 0); }
                to { opacity: 0; transform: translate(-50%, -20px); }
            }
        `;
        document.head.appendChild(style);
    }

    // Auto eliminar
    setTimeout(() => {
        if (notificationDiv.parentNode) {
            notificationDiv.style.animation = 'fadeOutUp 0.5s forwards';
            setTimeout(() => {
                if (notificationDiv.parentNode) notificationDiv.remove();
            }, 500);
        }
    }, 4000); // 4 segundos
}

/**
 * Mostrar/ocultar loading
 */
function mostrarLoading(mostrar) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = mostrar ? 'flex' : 'none';
    }
}

/**
 * Fetch con manejo de errores
 */
async function fetchData(url, options = {}) {
    try {
        console.log(`Fetching: ${url}`);
        const response = await fetch(url, options);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log(`✅ [API Success] ${url}`); // Log profesional Juan Sebastian
        return data;
    } catch (error) {
        console.error(`❌ [API Error] ${url}:`, error);
        mostrarNotificacion(`Error en la solicitud: ${error.message}`, 'error');
        return null;
    }
}

/**
 * Formatear números
 */
function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    return parseFloat(num).toLocaleString('es-CO');
}

/**
 * Formatear fecha corta
 */
function formatDateShort(fecha) {
    if (!fecha) return '';
    const date = new Date(fecha);
    return date.toLocaleDateString('es-CO');
}

/**
 * Formatear hora
 */
function formatTime(hora) {
    if (!hora) return '00:00';
    if (typeof hora === 'string' && hora.includes('T')) {
        return hora.split('T')[1].substring(0, 5);
    }
    return hora;
}

/**
 * Validar email
 */
function validarEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Obtener estado de stock
 */
function getEstadoStock(stockActual, stockMinimo) {
    stockActual = parseFloat(stockActual || 0);
    stockMinimo = parseFloat(stockMinimo || 0);

    if (stockActual <= 0) {
        return { estado: 'AGOTADO', clase: 'bg-danger' };
    } else if (stockActual < stockMinimo) {
        return { estado: 'BAJO STOCK', clase: 'bg-warning' };
    } else {
        return { estado: 'STOCK OK', clase: 'bg-success' };
    }
}

/**
 * Limpiar formulario
 */
function limpiarFormulario(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.reset();
        // Restaurar usuario logueado
        if (window.AuthModule) {
            window.AuthModule.autoFillForms();
        }
    }
}
