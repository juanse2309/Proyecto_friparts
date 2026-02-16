// ============================================
// utils.js - Funciones compartidas
// ============================================

/**
 * Placeholder SVG para productos sin imagen
 */
const PLACEHOLDER_SVG_PRODUCTO = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%23f8fafc;stop-opacity:1' /%3E%3Cstop offset='100%25' style='stop-color:%23e2e8f0;stop-opacity:1' /%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='100' height='100' fill='url(%23g)' rx='12'/%3E%3Cg opacity='0.4' transform='translate(0, -5)'%3E%3Cpath d='M30 40c0-2.2 1.8-4 4-4h32c2.2 0 4 1.8 4 4v25c0 2.2-1.8 4-4 4H34c-2.2 0-4-1.8-4-4V40z' fill='%2364748b'/%3E%3Ccircle cx='50' cy='52.5' r='7' fill='%23f1f5f9'/%3E%3Cpath d='M46 32h8l2 4h-12z' fill='%2364748b'/%3E%3C/g%3E%3Ctext x='50' y='82' text-anchor='middle' font-family='sans-serif' font-size='7' fill='%2394a3b8' font-weight='bold'%3EFriTech%3C/text%3E%3C/svg%3E`;

/**
 * Renderiza sugerencias de productos con imagen (Estandarizado)
 * @param {HTMLElement} container - El div de sugerencias
 * @param {Array} items - Lista de productos filtrados
 * @param {Function} onSelect - Callback al seleccionar un item
 */
function renderProductSuggestions(container, items, onSelect) {
    if (!container) return;

    if (items.length === 0) {
        container.innerHTML = '<div class="suggestion-item">No se encontraron productos</div>';
        container.classList.add('active');
        return;
    }

    container.innerHTML = items.map(prod => {
        const imgUrl = prod.imagen || PLACEHOLDER_SVG_PRODUCTO;
        const codigo = prod.codigo_sistema || prod.codigo || 'N/A';
        const descripcion = prod.descripcion || 'Sin descripción';
        const precio = prod.precio || 0;
        const stock = prod.stock_disponible ?? prod.stock_total ?? prod.stock ?? 0;

        return `
            <div class="suggestion-item product-suggestion-pro" 
                 style="display: flex; align-items: center; gap: 12px; padding: 10px; cursor: pointer; border-bottom: 1px solid #f0f0f0;"
                 data-codigo="${codigo}">
                
                <img src="${imgUrl}" 
                     onerror="this.src='${PLACEHOLDER_SVG_PRODUCTO}';this.onerror=null;"
                     style="width: 42px; height: 42px; object-fit: cover; border-radius: 8px; background: #f8fafc; border: 1px solid #e2e8f0;">
                
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: baseline; gap: 8px;">
                        <strong style="color: #1e293b; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${codigo}</strong>
                        <span style="color: #64748b; font-size: 0.75rem; font-weight: 600;">Stock: ${stock}</span>
                    </div>
                    <div style="color: #475569; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${descripcion}</div>
                    ${precio > 0 ? `<div style="color: #0891b2; font-size: 0.8rem; font-weight: 600; margin-top: 2px;">$ ${formatNumber(precio)}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');

    // Event listeners para selección
    container.querySelectorAll('.suggestion-item').forEach((item, index) => {
        item.addEventListener('click', () => {
            onSelect(items[index]);
            container.classList.remove('active');
            container.style.display = 'none'; // Asegurar que se oculte
        });
    });

    container.classList.add('active');
    container.style.display = 'block';
}

/**
 * Mostrar notificación visual
 */
function mostrarNotificacion(mensaje, tipo = 'info', undoData = null) {
    // 1. Reproducir sonido (Gamificación v1.3)
    if (window.ModuloUX && window.ModuloUX.playSound) {
        window.ModuloUX.playSound(tipo);
    }

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

    // Estilos profesionales
    notificationDiv.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background-color: #ffffff;
        color: #333333;
        padding: 16px 24px;
        border-radius: 12px;
        font-weight: 500;
        font-size: 0.95rem;
        z-index: 10005;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        display: flex;
        align-items: center;
        gap: 15px;
        max-width: 90%;
        width: git 420px;
        border-left: 6px solid ${iconColor};
        animation: slideInDown 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    `;

    // Botón Undo (si hay datos)
    let undoHtml = '';
    if (undoData && undoData.hoja && undoData.fila) {
        undoHtml = `
            <button id="btn-undo-action" class="btn btn-sm btn-outline-danger ms-auto" 
                style="border-radius: 20px; padding: 2px 10px; font-size: 0.8rem; white-space: nowrap;">
                <i class="fas fa-undo"></i> DESHACER
            </button>
        `;
    }

    notificationDiv.innerHTML = `
        <div style="flex-shrink: 0;">${icon}</div>
        <span style="flex-grow: 1; line-height: 1.4;">${mensaje}</span>
        ${undoHtml}
        <i class="fas fa-times" style="color: #9ca3af; cursor: pointer; font-size: 0.9rem; margin-left: 10px;" onclick="this.parentElement.remove()"></i>
    `;

    document.body.appendChild(notificationDiv);

    // Handler para Undo
    if (undoData) {
        const btnUndo = notificationDiv.querySelector('#btn-undo-action');
        if (btnUndo) {
            btnUndo.addEventListener('click', async () => {
                // Feedback inmediato
                btnUndo.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ...';
                btnUndo.disabled = true;

                try {
                    const res = await fetch('/api/undo', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(undoData)
                    });
                    const data = await res.json();

                    if (data.success) {
                        notificationDiv.remove();
                        mostrarNotificacion('Acción deshecha correctamente. Verifica el stock si es necesario.', 'warning');

                        // Callback de restauración de datos
                        if (undoData && typeof undoData.restoreCallback === 'function') {
                            undoData.restoreCallback();
                        }

                        // Opcional: Recargar módulo actual
                        const pagina = window.AppState.paginaActual;
                        if (window[`Modulo${pagina.charAt(0).toUpperCase() + pagina.slice(1)}`]?.cargarDatos) {
                            window[`Modulo${pagina.charAt(0).toUpperCase() + pagina.slice(1)}`].cargarDatos();
                        }
                    } else {
                        mostrarNotificacion('No se pudo deshacer: ' + data.error, 'error');
                    }
                } catch (e) {
                    mostrarNotificacion('Error de conexión al deshacer', 'error');
                }
            });
        }
    }

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

    // Auto eliminar (5s para dar tiempo al Undo)
    setTimeout(() => {
        if (notificationDiv.parentNode) {
            notificationDiv.style.animation = 'fadeOutUp 0.5s forwards';
            setTimeout(() => {
                if (notificationDiv.parentNode) notificationDiv.remove();
            }, 500);
        }
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
