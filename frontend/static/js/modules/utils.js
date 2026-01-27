// ============================================
// utils.js - Funciones compartidas
// ============================================

/**
 * Mostrar notificaci??n visual
 */
function mostrarNotificacion(mensaje, tipo = 'info') {
    console.log(`[${tipo.toUpperCase()}] ${mensaje}`);
    
    const notificationDiv = document.createElement('div');
    notificationDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10002;
        animation: slideInRight 0.3s ease;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        max-width: 400px;
    `;
    
    switch(tipo) {
        case 'success': notificationDiv.style.backgroundColor = '#10b981'; break;
        case 'error': notificationDiv.style.backgroundColor = '#ef4444'; break;
        case 'warning': notificationDiv.style.backgroundColor = '#f59e0b'; break;
        default: notificationDiv.style.backgroundColor = '#6366f1';
    }
    
    notificationDiv.textContent = mensaje;
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
                from { opacity: 1; }
                to { opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    setTimeout(() => {
        notificationDiv.style.animation = 'fadeOut 0.5s ease';
        setTimeout(() => {
            if (notificationDiv.parentNode) {
                notificationDiv.parentNode.removeChild(notificationDiv);
            }
        }, 500);
    }, 5000);
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
        console.log(`??? Data from ${url}:`, data);
        return data;
    } catch (error) {
        console.error(`??? Error fetching ${url}:`, error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
        return null;
    }
}

/**
 * Formatear n??meros
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
    }
}
