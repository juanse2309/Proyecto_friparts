// ============================================
// dashboard.js - Lógica del Dashboard
// ============================================

/**
 * Inicializar Dashboard
 */
async function inicializarDashboard() {
    try {
        console.log('🚀 Inicializando dashboard...');
        mostrarLoading(true);
        
        // Obtener datos del dashboard
        const dataReal = await fetchData('/api/dashboard/real');
        
        if (dataReal) {
            console.log('✅ Dashboard datos reales:', dataReal);
            actualizarDashboardUI(dataReal);
            console.log('✅ Dashboard actualizado');
        }
        
        mostrarLoading(false);
    } catch (error) {
        console.error('Error inicializando dashboard:', error);
        mostrarLoading(false);
    }
}

/**
 * Actualizar UI del Dashboard - Busca por TEXTO, no por ID
 */
function actualizarDashboardUI(data) {
    try {
        // Buscar todos los h3 (títulos de tarjetas)
        const titulos = document.querySelectorAll('h3');
        
        titulos.forEach(titulo => {
            const texto = titulo.textContent;
            const contenedor = titulo.closest('section') || titulo.closest('div[class*="card"]') || titulo.parentElement;
            
            if (!contenedor) return;
            
            // Obtener el primer span con número después del h3
            const obtenerPrimerSpan = () => {
                let elemento = titulo.nextElementSibling;
                while (elemento) {
                    const span = elemento.querySelector('span');
                    if (span && /^\d/.test(span.textContent.trim())) {
                        return span;
                    }
                    elemento = elemento.nextElementSibling;
                }
                return null;
            };
            
            // Producción Total
            if (texto.includes('Producción Total')) {
                const span = obtenerPrimerSpan();
                if (span) {
                    span.textContent = formatNumber(data.produccion_total || 0);
                    console.log('✅ Producción:', data.produccion_total);
                }
            }
            
            // Ventas Totales
            else if (texto.includes('Ventas Totales')) {
                const span = obtenerPrimerSpan();
                if (span) {
                    span.textContent = `$${formatNumber(data.ventas_totales || 0)}`;
                    console.log('✅ Ventas:', data.ventas_totales);
                }
            }
            
            // Eficiencia Global
            else if (texto.includes('Eficiencia Global')) {
                const span = obtenerPrimerSpan();
                if (span) {
                    span.textContent = `${(data.eficiencia_global || 0).toFixed(1)}%`;
                    console.log('✅ Eficiencia:', data.eficiencia_global);
                }
            }
            
            // Stock Crítico
            else if (texto.includes('Stock Crítico')) {
                const span = obtenerPrimerSpan();
                if (span) {
                    span.textContent = data.stock_critico || 0;
                    console.log('✅ Stock:', data.stock_critico);
                }
            }
            
            // Inyección - Producción
            else if (texto.includes('Inyección') && data.inyeccion) {
                const spans = contenedor.querySelectorAll('span');
                spans.forEach((span, idx) => {
                    if (span.textContent.includes('0') && span.parentElement.textContent.includes('Producción')) {
                        span.textContent = formatNumber(data.inyeccion.produccion || 0);
                    }
                    if (span.textContent.includes('0') && span.parentElement.textContent.includes('Eficiencia')) {
                        span.textContent = `${(data.inyeccion.eficiencia || 0).toFixed(1)}%`;
                    }
                    if (span.textContent.includes('0') && span.parentElement.textContent.includes('PNC')) {
                        span.textContent = formatNumber(data.inyeccion.pnc || 0);
                    }
                });
            }
            
            // Pulido - Eficiencia
            else if (texto.includes('Pulido') && !texto.includes('Por Pulir') && data.pulido) {
                const spans = contenedor.querySelectorAll('span');
                spans.forEach((span, idx) => {
                    if (span.textContent.includes('0') && span.parentElement.textContent.includes('Eficiencia')) {
                        span.textContent = `${(data.pulido.eficiencia || 0).toFixed(1)}%`;
                    }
                    if (span.textContent.includes('0') && span.parentElement.textContent.includes('PNC')) {
                        span.textContent = `${(data.pulido.pnc || 0).toFixed(1)}%`;
                    }
                });
            }
        });
        
    } catch (error) {
        console.error('Error actualizando UI:', error);
    }
}
