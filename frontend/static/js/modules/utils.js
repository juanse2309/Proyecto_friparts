// ============================================
// utils.js - Funciones compartidas
// ============================================

/**
 * Mostrar notificación visual
 */
function mostrarNotificacion(mensaje, tipo = 'info') {
    const icon = {
        'success': '<i class="fas fa-check-circle me-2"></i>',
        'error': '<i class="fas fa-exclamation-circle me-2"></i>',
        'warning': '<i class="fas fa-exclamation-triangle me-2"></i>',
        'info': '<i class="fas fa-info-circle me-2"></i>'
    }[tipo] || '';

    const notificationDiv = document.createElement('div');
    notificationDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 10px;
        color: white;
        font-weight: 500;
        z-index: 10002;
        animation: slideInRight 0.3s ease;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        max-width: 400px;
        border-left: 5px solid rgba(0,0,0,0.2);
    `;

    switch (tipo) {
        case 'success': notificationDiv.style.backgroundColor = 'rgba(16, 185, 129, 0.9)'; break;
        case 'error': notificationDiv.style.backgroundColor = 'rgba(239, 68, 68, 0.9)'; break;
        case 'warning': notificationDiv.style.backgroundColor = 'rgba(245, 158, 11, 0.9)'; break;
        default: notificationDiv.style.backgroundColor = 'rgba(59, 130, 246, 0.9)';
    }

    notificationDiv.innerHTML = `${icon} <span>${mensaje}</span>`;
    document.body.appendChild(notificationDiv);

    if (!document.querySelector('style#notification-animations')) {
        const style = document.createElement('style');
        style.id = 'notification-animations';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes fadeOut {
                from { opacity: 1; opacity: 1; }
                to { transform: translateX(20px); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    // Tiempo visible: 3 segundos
    const timeout = 3000;

    setTimeout(() => {
        notificationDiv.style.animation = 'fadeOut 0.5s forwards';
        setTimeout(() => {
            if (notificationDiv.parentNode) {
                notificationDiv.parentNode.removeChild(notificationDiv);
            }
        }, 500);
    }, timeout);
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
