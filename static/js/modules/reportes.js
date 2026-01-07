// ============================================
// reportes.js - Lógica de Reportes
// ============================================

/**
 * Cargar datos de Reportes
 */
async function cargarDatosReportes() {
    try {
        console.log('📊 Cargando reportes...');
        mostrarLoading(true);
        
        // Obtener estadísticas básicas
        const estadisticas = await fetchData('/api/estadisticas');
        if (estadisticas) {
            mostrarEstadisticasReportes(estadisticas);
        }
        
        console.log('✅ Reportes cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando reportes:', error);
        mostrarLoading(false);
    }
}

/**
 * Mostrar estadísticas en reportes
 */
function mostrarEstadisticasReportes(stats) {
    const container = document.getElementById('reportes-container') || document.querySelector('.page');
    if (!container) return;
    
    const html = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px;">
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                <h4 style="margin: 0 0 10px 0;">Producción Total</h4>
                <p style="margin: 0; font-size: 28px; font-weight: bold; color: #1f2937;">
                    ${formatNumber(stats.produccion_total || 0)} piezas
                </p>
            </div>
            
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; border-left: 4px solid #10b981;">
                <h4 style="margin: 0 0 10px 0;">Ventas Totales</h4>
                <p style="margin: 0; font-size: 28px; font-weight: bold; color: #1f2937;">
                    $${formatNumber(stats.ventas_totales || 0)}
                </p>
            </div>
            
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                <h4 style="margin: 0 0 10px 0;">Eficiencia Global</h4>
                <p style="margin: 0; font-size: 28px; font-weight: bold; color: #1f2937;">
                    ${(stats.eficiencia_global || 0).toFixed(1)}%
                </p>
            </div>
            
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; border-left: 4px solid #ef4444;">
                <h4 style="margin: 0 0 10px 0;">Stock Crítico</h4>
                <p style="margin: 0; font-size: 28px; font-weight: bold; color: #1f2937;">
                    ${stats.stock_critico || 0} productos
                </p>
            </div>
        </div>
    `;
    
    const div = document.createElement('div');
    div.innerHTML = html;
    container.appendChild(div);
}

/**
 * Exportar reporte a CSV
 */
function exportarReporte() {
    mostrarNotificacion('✅ Descargando reporte...', 'info');
    // Aquí iría la lógica real de descarga
}
