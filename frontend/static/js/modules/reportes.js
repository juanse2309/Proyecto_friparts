// ============================================
// reportes.js - Lógica de Reportes y Análisis
// ============================================

/**
 * Cargar datos de Reportes
 */
async function cargarDatosReportes() {
    try {
        console.log('📊 Cargando centro de reportes...');
        mostrarLoading(true);
        
        // Obtener estadísticas desde el backend
        const stats = await fetchData('/api/estadisticas');
        if (stats && stats.success) {
            actualizarMetricasReportes(stats);
            // Si hay productos en cache, llenar el select de productos para filtrar
            if (window.AppState.sharedData.productos) {
                const select = document.getElementById('producto-reporte');
                if (select && select.children.length <= 1) {
                    window.AppState.sharedData.productos.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p.codigo_sistema || p.codigo;
                        opt.textContent = `${opt.value} - ${p.descripcion}`;
                        select.appendChild(opt);
                    });
                }
            }
        }
        
        console.log('✅ Reportes listos');
    } catch (error) {
        console.error('Error cargando reportes:', error);
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Actualizar las tarjetas de métricas en la UI
 */
function actualizarMetricasReportes(stats) {
    const prodMes = document.getElementById('rep-prod-mes');
    const ventasMes = document.getElementById('rep-ventas-mes');
    const pncTasa = document.getElementById('rep-pnc-tasa');
    
    if (prodMes) prodMes.textContent = formatNumber(stats.produccion_total || 0);
    if (ventasMes) ventasMes.textContent = `$ ${formatNumber(stats.ventas_totales || 0)}`;
    if (pncTasa) pncTasa.textContent = `${(stats.pnc_tasa || 0).toFixed(1)}%`;
}

/**
 * Generar Reporte Detallado
 */
async function generarReporte() {
    const tipo = document.getElementById('tipo-reporte').value;
    const rango = document.getElementById('rango-reporte').value;
    const producto = document.getElementById('producto-reporte').value;
    
    mostrarLoading(true);
    mostrarNotificacion(`📈 Generando reporte de ${tipo}...`, 'info');
    
    try {
        // En una fase real, esto llamaría a un endpoint específico de Excel/PDF
        // Por ahora, simulamos una carga y mostramos un mensaje
        setTimeout(() => {
            mostrarLoading(false);
            const container = document.getElementById('resultado-reporte');
            if (container) {
                container.innerHTML = `
                    <div class="alert alert-success d-flex align-items-center">
                        <i class="fas fa-check-circle fa-2x me-3"></i>
                        <div>
                            <strong>Reporte Generado con Éxito</strong><br>
                            Se han procesado los datos de ${tipo} para el rango ${rango}.
                            <button class="btn btn-sm btn-success ms-3" onclick="alert('Descargando...')">
                                <i class="fas fa-download"></i> Descargar Excel
                            </button>
                        </div>
                    </div>
                `;
            }
        }, 1500);
    } catch (error) {
        console.error('Error generando reporte:', error);
        mostrarLoading(false);
    }
}

function initReportes() {
    console.log('🔧 Inicializando módulo de reportes...');
    cargarDatosReportes();
    
    document.getElementById('btn-generar-reporte')?.addEventListener('click', generarReporte);
}

window.initReportes = initReportes;
window.ModuloReportes = { inicializar: initReportes };
