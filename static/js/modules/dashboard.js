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
            
            // Actualizar tarjetas
            const elemProduccion = document.getElementById('produccion-total');
            if (elemProduccion) {
                elemProduccion.textContent = formatNumber(dataReal.produccion_total || 0);
            }
            
            const elemVentas = document.getElementById('ventas-totales');
            if (elemVentas) {
                elemVentas.textContent = `$${formatNumber(dataReal.ventas_totales || 0)}`;
            }
            
            const elemEficiencia = document.getElementById('eficiencia-global');
            if (elemEficiencia) {
                elemEficiencia.textContent = `${(dataReal.eficiencia_global || 0).toFixed(1)}%`;
            }
            
            const elemStock = document.getElementById('stock-critico');
            if (elemStock) {
                elemStock.textContent = dataReal.stock_critico || 0;
            }
            
            console.log('✅ Dashboard actualizado');
        }
        
        mostrarLoading(false);
    } catch (error) {
        console.error('Error inicializando dashboard:', error);
        mostrarLoading(false);
    }
}
