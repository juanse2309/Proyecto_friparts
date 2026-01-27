// dashboard.js - VERSIÓN REFACTORIZADA
// Usa apiClient en lugar de fetchData

async function inicializarDashboard() {

    await cargarDatosDashboard();
    configurarEventosDashboard();

}

async function cargarDatosDashboard() {
    try {
        mostrarLoading(true);
        
        // NUEVO: Usar apiClient en lugar de fetchData
        const datos = await apiClient.get('/dashboard');
        
        if (datos && datos.status === 'success') {
            actualizarDashboardUI(datos);
        } else {
            console.warn('No se recibieron datos del dashboard');
        }
    } catch (error) {
        console.error('Error cargando dashboard:', error);
        mostrarNotificacion('Error cargando datos del dashboard', 'error');
    } finally {
        mostrarLoading(false);
    }
}

function actualizarDashboardUI(datos) {

    
    // Actualizar métricas principales
    const produccionTotal = document.querySelector('#produccion-total');
    if (produccionTotal && datos.produccion) {
        produccionTotal.textContent = formatNumber(datos.produccion.total || 0);
    }
    
    const ventasTotal = document.querySelector('#ventas-total');
    if (ventasTotal && datos.ventas) {
        ventasTotal.textContent = formatNumber(datos.ventas.total || 0);
    }
    
    // Aquí agregar actualización de gráficos si existen
}

function configurarEventosDashboard() {
    const btnActualizar = document.getElementById('btn-actualizar-dashboard');
    if (btnActualizar) {
        btnActualizar.removeEventListener('click', cargarDatosDashboard);
        btnActualizar.addEventListener('click', cargarDatosDashboard);
    }
}

// Exportar para uso global (compatibilidad)
window.inicializarDashboard = inicializarDashboard;
window.actualizarDashboard = cargarDatosDashboard;

// Auto-inicializar si estamos en la página de dashboard
document.addEventListener('DOMContentLoaded', function() {
    const dashboardSection = document.querySelector('#dashboard-section, [data-module="dashboard"]');
    if (dashboardSection && dashboardSection.style.display !== 'none') {
        inicializarDashboard();
    }
});
