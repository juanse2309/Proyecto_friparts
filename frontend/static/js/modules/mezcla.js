

/**
 * Inicializar módulo de mezcla
 */
function initMezcla() {
    console.log('🔧 Inicializando módulo de mezcla...');
    if (typeof cargarDatosMezcla === 'function') {
        cargarDatosMezcla();
    }
    console.log('✅ Módulo de mezcla inicializado');
}

// ============================================
// EXPORTAR MÓDULO
// ============================================
window.initMezcla = initMezcla;
window.ModuloMezcla = { inicializar: initMezcla };
