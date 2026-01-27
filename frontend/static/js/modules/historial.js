

/**
 * Inicializar módulo de historial
 */
function initHistorial() {
    console.log('🔧 Inicializando módulo de historial...');
    if (typeof cargarHistorial === 'function') {
        cargarHistorial();
    }
    console.log('✅ Módulo de historial inicializado');
}

// ============================================
// EXPORTAR MÓDULO
// ============================================
window.initHistorial = initHistorial;
window.ModuloHistorial = { inicializar: initHistorial };
