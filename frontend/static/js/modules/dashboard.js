// ============================================
// dashboard.js - Dashboard Simple y Funcional
// ============================================

/**
 * Inicializar Dashboard
 */
async function inicializarDashboard() {
    try {
        console.log('???? Inicializando dashboard...');
        mostrarLoading(true);
        
        // Obtener datos del dashboard
        const dataReal = await fetchData('/api/dashboard/real');
        
        if (dataReal) {
            console.log('??? Dashboard datos reales:', dataReal);
            actualizarDashboardUI(dataReal);
            console.log('??? Dashboard actualizado');
        }
        
        mostrarLoading(false);
    } catch (error) {
        console.error('Error inicializando dashboard:', error);
        mostrarLoading(false);
    }
}

/**
 * Actualizar UI del Dashboard - VERSI??N FINAL LIMPIA
 */
function actualizarDashboardUI(data) {
    try {
        // Buscar todos los h3 en la p??gina
        const titulos = document.querySelectorAll('h3');
        
        titulos.forEach(titulo => {
            const texto = titulo.textContent.trim();
            
            // Encontrar el primer span/div con n??mero despu??s del h3
            let elemento = titulo.nextElementSibling;
            let spanEncontrado = null;
            let intentos = 0;
            
            while (elemento && !spanEncontrado && intentos < 5) {
                const span = elemento.querySelector('span');
                if (span && /^\d|^\$/.test(span.textContent.trim())) {
                    spanEncontrado = span;
                    break;
                }
                elemento = elemento.nextElementSibling;
                intentos++;
            }
            
            // Actualizar seg??n el t??tulo
            if (texto.includes('Producci??n Total') && spanEncontrado) {
                spanEncontrado.textContent = formatNumber(data.produccion_total || 0);
                console.log('??? Producci??n:', data.produccion_total);
            }
            else if (texto.includes('Ventas Totales') && spanEncontrado) {
                spanEncontrado.textContent = `$${formatNumber(data.ventas_totales || 0)}`;
                console.log('??? Ventas:', data.ventas_totales);
            }
            else if (texto.includes('Eficiencia Global') && spanEncontrado) {
                spanEncontrado.textContent = `${(data.eficiencia_global || 0).toFixed(1)}%`;
                console.log('??? Eficiencia:', data.eficiencia_global);
            }
            else if (texto.includes('Stock Cr??tico') && spanEncontrado) {
                spanEncontrado.textContent = data.stock_critico || 0;
                console.log('??? Stock:', data.stock_critico);
            }
        });
        
        console.log('??? Dashboard UI actualizado completamente');
    } catch (error) {
        console.error('Error actualizando UI:', error);
    }
}
