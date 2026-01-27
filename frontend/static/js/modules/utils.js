// utils.js - VERSIÓN REFACTORIZADA
// Protección contra carga múltiple
if (typeof window.UTILS_LOADED === 'undefined') {
    window.UTILS_LOADED = true;

// utils.js - VERSIÓN REFACTORIZADA
// Solo utilidades genéricas, sin lógica de negocio

// =========================================
// CONSTANTES
// =========================================
const PLACEHOLDER_THUMB = 'https://placehold.co/40x40/e9ecef/d1d5db?text=IMG';
const PLACEHOLDER_MODAL = 'https://placehold.co/300x200/e9ecef/6b7280?text=Sin+Imagen';

// =========================================
// SISTEMA DE NOTIFICACIONES
// =========================================
function mostrarNotificacion(mensaje, tipo = 'info', duracion = 4000) {

    
    let container = document.getElementById('notifications-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notifications-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 400px;
        `;
        document.body.appendChild(container);
    }

    const iconos = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    };

    const colores = {
        'success': 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        'error': 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
        'warning': 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        'info': 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)'
    };

    const notification = document.createElement('div');
    notification.style.cssText = `
        background: ${colores[tipo]};
        color: white;
        padding: 16px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        gap: 12px;
        animation: slideIn 0.3s ease;
        min-width: 300px;
        max-width: 400px;
        font-size: 14px;
        font-weight: 500;
    `;

    notification.innerHTML = `
        <i class="fas ${iconos[tipo]}"></i>
        <span>${mensaje}</span>
    `;

    container.appendChild(notification);

    if (duracion > 0) {
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, duracion);
    }
}

// =========================================
// FORMATEO
// =========================================
function formatNumber(num) {
    return new Intl.NumberFormat('es-ES').format(num);
}

function formatFecha(fechaISO) {
    if (!fechaISO) return '';
    const fecha = new Date(fechaISO);
    return fecha.toLocaleDateString('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

function limpiarCadena(str) {
    return String(str || '').trim().replace(/\s+/g, ' ');
}

// =========================================
// LOADING OVERLAY
// =========================================
function mostrarLoading(show) {
    let overlay = document.getElementById('loading-overlay');
    
    if (!overlay && show) {
        overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 99999;
        `;
        overlay.innerHTML = `
            <div style="text-align: center; color: white;">
                <i class="fas fa-spinner fa-spin" style="font-size: 48px;"></i>
                <p style="margin-top: 16px; font-size: 18px;">Cargando...</p>
            </div>
        `;
        document.body.appendChild(overlay);
    }
    
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}

// =========================================
// UTILIDADES DE IMAGEN
// =========================================
function normalizarImagenProducto(imagenRaw) {
    const PLACEHOLDER = 'https://placehold.co/300x200/e9ecef/6b7280?text=Sin+Imagen';
    if (!imagenRaw) return PLACEHOLDER;
    const val = String(imagenRaw).trim();
    return val || PLACEHOLDER;
}

// =========================================
// ESTADO DE STOCK
// =========================================
function getEstadoStock(total, minimo) {
    if (total <= 0) return 'agotado';
    if (total < minimo) return 'bajo';
    return 'ok';
}

// =========================================
// VALIDACIONES
// =========================================
function validarEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// =========================================
// GENERADORES
// =========================================
function generarIdSimple() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// =========================================
// PORTAPAPELES
// =========================================
async function copiarAlPortapapeles(texto) {
    try {
        await navigator.clipboard.writeText(texto);
        mostrarNotificacion('Texto copiado', 'success', 2000);
        return true;
    } catch (error) {
        console.error('Error copiando:', error);
        mostrarNotificacion('Error al copiar', 'error');
        return false;
    }
}

// CSS para animaciones (agregar una sola vez)
if (!document.getElementById('utils-animations')) {
    const style = document.createElement('style');
    style.id = 'utils-animations';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}

} else {
    console.warn('utils.js ya fue cargado, omitiendo...');
}
