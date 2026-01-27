// ===========================
// DATA RELOAD HELPERS - Funciones para Recarga de Datos
// ===========================

/**
 * Módulo con funciones reutilizables para recargar datos compartidos.
 * Consolida la lógica de recarga de productos y otros datos del AppState.
 */
const DataReloadHelpers = (() => {

    /**
     * Recarga la lista de productos desde el servidor.
     * 
     * Actualiza window.AppState.sharedData.productos con los datos más recientes
     * desde el endpoint /api/productos/listar_v2. Esta función debe llamarse
     * después de operaciones que modifiquen el inventario.
     * 
     * @returns {Promise<void>}
     * @throws {Error} Si hay error en la comunicación con el servidor
     * 
     * @example
     * // Después de registrar una inyección
     * await recargarProductos();
     */
    async function recargarProductos() {
        try {
            console.log('🔄 Recargando productos...');

            // Usar apiClient si está disponible, sino fetch directo
            let productosRaw;
            if (typeof apiClient !== 'undefined' && apiClient.get) {
                productosRaw = await apiClient.get('/productos/listar_v2');
            } else {
                const response = await fetch('/api/productos/listar_v2');
                productosRaw = await response.json();
            }

            // Normalizar estructura de datos
            window.AppState.sharedData.productos = productosRaw.map(p => ({
                id_codigo: p.id_codigo || 0,
                codigo_sistema: p.codigo || '',
                descripcion: p.descripcion || '',
                imagen: p.imagen || '',
                stock_por_pulir: p.stock_por_pulir || 0,
                stock_terminado: p.stock_terminado || 0,
                stock_total: p.existencias_totales || 0,
                semaforo: p.semaforo || 'rojo',
                metricas: p.metricas || { min: 0, max: 0, reorden: 0 }
            }));

            console.log(`✅ Productos actualizados: ${window.AppState.sharedData.productos.length} productos`);

            // Notificar al módulo de inventario si existe
            if (window.ModuloInventario && window.ModuloInventario.inicializar) {
                console.log('🔄 Sincronizando interfaz de inventario...');
                window.ModuloInventario.inicializar();
            }

        } catch (error) {
            console.error('❌ Error recargando productos:', error);
            throw error; // Re-lanzar para que el llamador pueda manejarlo
        }
    }

    /**
     * Recarga todos los datos compartidos del AppState.
     * 
     * Actualiza productos, responsables, máquinas y otros datos compartidos.
     * Esta función es más completa que recargarProductos() y debe usarse
     * cuando se necesita actualizar todo el estado de la aplicación.
     * 
     * @returns {Promise<void>}
     * @throws {Error} Si hay error en la comunicación con el servidor
     * 
     * @example
     * // Al inicializar un módulo
     * await recargarDatosCompartidos();
     */
    async function recargarDatosCompartidos() {
        try {
            console.log('🔄 Recargando datos compartidos...');

            // Recargar productos
            await recargarProductos();

            // Recargar responsables si es necesario
            // (Por ahora solo productos, pero puede extenderse)

            console.log('✅ Datos compartidos actualizados');

        } catch (error) {
            console.error('❌ Error recargando datos compartidos:', error);
            // No re-lanzar aquí para evitar interrumpir el flujo
        }
    }

    /**
     * Recarga los responsables desde el servidor.
     * 
     * @returns {Promise<void>}
     * 
     * @example
     * await recargarResponsables();
     */
    async function recargarResponsables() {
        try {
            console.log('🔄 Recargando responsables...');

            const response = await fetch('/api/obtener_responsables');
            const responsables = await response.json();

            window.AppState.sharedData.responsables = responsables || [];

            console.log(`✅ Responsables actualizados: ${responsables.length} responsables`);

        } catch (error) {
            console.error('❌ Error recargando responsables:', error);
        }
    }

    /**
     * Recarga las máquinas desde el servidor.
     * 
     * @returns {Promise<void>}
     * 
     * @example
     * await recargarMaquinas();
     */
    async function recargarMaquinas() {
        try {
            console.log('🔄 Recargando máquinas...');

            const response = await fetch('/api/obtener_maquinas');
            const maquinas = await response.json();

            window.AppState.sharedData.maquinas = maquinas || [];

            console.log(`✅ Máquinas actualizadas: ${maquinas.length} máquinas`);

        } catch (error) {
            console.error('❌ Error recargando máquinas:', error);
        }
    }

    /**
     * Invalida el caché de productos en el servidor.
     * 
     * Fuerza al servidor a recargar los productos desde Google Sheets
     * en la próxima petición.
     * 
     * @returns {Promise<void>}
     * 
     * @example
     * await invalidarCacheProductos();
     * await recargarProductos(); // Obtendrá datos frescos
     */
    async function invalidarCacheProductos() {
        try {
            console.log('🔄 Invalidando caché de productos...');

            await fetch('/api/productos/invalidar_cache', { method: 'POST' });

            console.log('✅ Caché invalidado');

        } catch (error) {
            console.error('❌ Error invalidando caché:', error);
        }
    }

    // Exportar funciones públicas
    return {
        recargarProductos,
        recargarDatosCompartidos,
        recargarResponsables,
        recargarMaquinas,
        invalidarCacheProductos
    };
})();

// Exportar al scope global
window.DataReloadHelpers = DataReloadHelpers;

console.log('✅ DataReloadHelpers cargado');
