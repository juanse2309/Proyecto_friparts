// =========================================================
// gerencia.js - Módulo de Tablero Gerencial (Torre de Control)
// =========================================================

const ModuloGerencia = {
    // Referencia al contenedor principal de la vista
    contenedorId: 'vista-gerencia-container',

    /**
     * Inicializar módulo
     */
    inicializar: async function () {
        console.log('📊 [Gerencia] Inicializando Tablero Gerencial...');
        // Mostrar vista gerencia y asegurar navegación correcta
        const vistaGer = document.getElementById('vista-gerencia');
        if (vistaGer) {
            vistaGer.classList.remove('d-none');
        }
        
        await this.cargarTrazabilidad();
    },

    /**
     * Alias por compatibilidad con llamadas externas
     */
    init: function () {
        cargarPagina('gerencia');
    },

    /**
     * Consulta el endpoint de trazabilidad y renderiza el tablero
     */
    cargarTrazabilidad: async function () {
        const contenedor = document.getElementById(this.contenedorId);
        if (!contenedor) return;

        try {
            contenedor.innerHTML = `
                <div class="text-center py-5">
                    <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <h5 class="mt-3 text-muted fw-bold">Consolidando datos de producción en tiempo real...</h5>
                </div>
            `;

            const response = await fetch('/api/gerencia/trazabilidad');
            const result = await response.json();

            if (!result.success) {
                contenedor.innerHTML = `
                    <div class="alert alert-danger shadow-sm border-0 d-flex align-items-center" role="alert">
                        <i class="fas fa-exclamation-circle fa-2x me-3"></i>
                        <div>
                            <h5 class="alert-heading fw-bold mb-1">Error al consolidar trazabilidad</h5>
                            <p class="mb-0">${result.error || 'Ocurrió un error en el servidor.'}</p>
                        </div>
                    </div>
                `;
                return;
            }

            const pedidos = result.data || [];
            if (pedidos.length === 0) {
                contenedor.innerHTML = `
                    <div class="text-center py-5 bg-white rounded-4 shadow-sm border border-dashed">
                        <i class="fas fa-folder-open fa-4x text-muted mb-3" style="opacity: 0.5;"></i>
                        <h4 class="fw-bold text-dark mb-2">No hay pedidos programados</h4>
                        <p class="text-muted">Las cubetas de prioridad se mostrarán una vez que se programen pedidos en la tarde.</p>
                    </div>
                `;
                return;
            }

            // Renderizar las tarjetas gerenciales
            let html = '<div class="row g-4">';
            
            pedidos.forEach(pedido => {
                const colorSemaf = this.obtenerColorSemaforo(pedido.estado_global);
                
                html += `
                    <div class="col-12">
                        <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-3 hover-shadow" style="transition: all 0.3s ease; border-left: 6px solid ${colorSemaf.border} !important;">
                            <!-- Header de la tarjeta del pedido -->
                            <div class="card-header border-0 bg-light py-3 px-4 d-flex justify-content-between align-items-center flex-wrap gap-2" style="background-color: #f8fafc !important;">
                                <div class="d-flex align-items-center gap-3">
                                    <div class="rounded-3 p-2 d-flex align-items-center justify-content-center" style="background-color: ${colorSemaf.bgLight}; color: ${colorSemaf.border};">
                                        <i class="fas fa-clipboard-list fa-lg"></i>
                                    </div>
                                    <div>
                                        <h5 class="mb-0 fw-bold text-dark">PEDIDO: ${pedido.id_pedido}</h5>
                                        <span class="text-muted small fw-semibold">
                                            <i class="fas fa-user me-1 text-secondary"></i> ${pedido.cliente}
                                        </span>
                                    </div>
                                </div>
                                <div class="d-flex align-items-center gap-3">
                                    <div class="text-end">
                                        <div class="text-muted small fw-bold text-uppercase" style="font-size: 0.65rem;">Fecha Prometida</div>
                                        <div class="fw-bold text-dark small"><i class="fas fa-calendar-alt me-1 text-primary"></i> ${pedido.fecha_prometida}</div>
                                    </div>
                                    <span class="badge px-3 py-2 rounded-pill font-monospace fw-bold" style="background-color: ${colorSemaf.bg}; color: ${colorSemaf.color}; font-size: 0.8rem; letter-spacing: 0.5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                                        ${pedido.estado_global}
                                    </span>
                                </div>
                            </div>
                            
                            <!-- Body con el desglose de productos -->
                            <div class="card-body p-4 bg-white">
                                <div class="d-flex flex-column gap-4">
                `;

                pedido.productos.forEach(prod => {
                    // Buscar la descripción del producto localmente en el cache de AppState
                    const cacheProd = window.AppState?.sharedData?.productos?.find(p => p.codigo_sistema === prod.codigo);
                    const descProducto = cacheProd ? cacheProd.descripcion : "Pieza / Buje de Inyección";

                    html += `
                        <div class="p-3 rounded-3 border bg-light-subtle" style="background-color: #fbfcfd; border: 1px solid #eef2f6 !important;">
                            <!-- Info del Producto -->
                            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2 border-bottom pb-2 border-light">
                                <div class="d-flex align-items-center gap-2">
                                    <span class="badge bg-dark px-2.5 py-1.5 rounded text-white font-monospace fw-bold">${prod.codigo}</span>
                                    <span class="text-secondary fw-semibold small">${descProducto}</span>
                                </div>
                                <div class="d-flex align-items-center gap-3">
                                    <span class="text-muted small">Vía: <strong class="text-dark font-monospace">${prod.op}</strong></span>
                                    <span class="badge bg-secondary-subtle text-secondary fw-bold px-2.5 py-1">Prioridad: ${prod.cant_requerida} u</span>
                                </div>
                            </div>
                            
                            <!-- Grilla de las 4 etapas de trazabilidad -->
                            <div class="row g-3">
                                <!-- 1. Inyección -->
                                <div class="col-md-3 col-sm-6">
                                    <div class="d-flex flex-column gap-1.5 p-2 rounded bg-white border border-light">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <span class="fw-bold small text-dark d-flex align-items-center gap-1.5">
                                                <i class="fas fa-industry text-primary" style="font-size: 0.85rem;"></i> Inyección
                                            </span>
                                            <span class="fw-bold text-primary" style="font-size: 0.8rem;">${prod.inyectado.porcentaje}%</span>
                                        </div>
                                        <div class="progress rounded-pill bg-light" style="height: 8px;">
                                            <div class="progress-bar rounded-pill ${this.obtenerColorBarra(prod.inyectado.porcentaje)}" 
                                                 role="progressbar" 
                                                 style="width: ${prod.inyectado.porcentaje}%" 
                                                 aria-valuenow="${prod.inyectado.porcentaje}" 
                                                 aria-valuemin="0" 
                                                 aria-valuemax="100">
                                            </div>
                                        </div>
                                        <div class="text-muted small d-flex justify-content-between" style="font-size: 0.72rem;">
                                            <span>Inyectado:</span>
                                            <span class="fw-semibold text-dark">${prod.inyectado.cantidad} / ${prod.cant_requerida}</span>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- 2. Pulido -->
                                <div class="col-md-3 col-sm-6">
                                    <div class="d-flex flex-column gap-1.5 p-2 rounded bg-white border border-light">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <span class="fw-bold small text-dark d-flex align-items-center gap-1.5">
                                                <i class="fas fa-sparkles text-warning" style="font-size: 0.85rem;"></i> Pulido
                                            </span>
                                            <span class="fw-bold text-warning" style="font-size: 0.8rem;">${prod.pulido.porcentaje}%</span>
                                        </div>
                                        <div class="progress rounded-pill bg-light" style="height: 8px;">
                                            <div class="progress-bar rounded-pill ${this.obtenerColorBarra(prod.pulido.porcentaje)}" 
                                                 role="progressbar" 
                                                 style="width: ${prod.pulido.porcentaje}%" 
                                                 aria-valuenow="${prod.pulido.porcentaje}" 
                                                 aria-valuemin="0" 
                                                 aria-valuemax="100">
                                            </div>
                                        </div>
                                        <div class="text-muted small d-flex justify-content-between" style="font-size: 0.72rem;">
                                            <span>Pulido:</span>
                                            <span class="fw-semibold text-dark">${prod.pulido.cantidad} / ${prod.cant_requerida}</span>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- 3. Ensamble -->
                                <div class="col-md-3 col-sm-6">
                                    <div class="d-flex flex-column gap-1.5 p-2 rounded bg-white border border-light h-100 justify-content-center">
                                        ${prod.ensamble.requiere ? `
                                            <div class="d-flex justify-content-between align-items-center">
                                                <span class="fw-bold small text-dark d-flex align-items-center gap-1.5">
                                                    <i class="fas fa-puzzle-piece text-info" style="font-size: 0.85rem;"></i> Ensamble
                                                </span>
                                                <span class="fw-bold text-info" style="font-size: 0.8rem;">${prod.ensamble.porcentaje}%</span>
                                            </div>
                                            <div class="progress rounded-pill bg-light" style="height: 8px;">
                                                <div class="progress-bar rounded-pill ${this.obtenerColorBarra(prod.ensamble.porcentaje)}" 
                                                     role="progressbar" 
                                                     style="width: ${prod.ensamble.porcentaje}%" 
                                                     aria-valuenow="${prod.ensamble.porcentaje}" 
                                                     aria-valuemin="0" 
                                                     aria-valuemax="100">
                                                </div>
                                            </div>
                                            <div class="text-muted small d-flex justify-content-between" style="font-size: 0.72rem;">
                                                <span>Ensamblado:</span>
                                                <span class="fw-semibold text-dark">${prod.ensamble.cantidad} / ${prod.cant_requerida}</span>
                                            </div>
                                        ` : `
                                            <div class="text-center py-2">
                                                <span class="badge bg-secondary-subtle text-secondary px-3 py-1.5 rounded-pill fw-bold text-uppercase" style="font-size: 0.68rem; letter-spacing: 0.3px;">
                                                    <i class="fas fa-ban me-1"></i> No requiere ensamble
                                                </span>
                                            </div>
                                        `}
                                    </div>
                                </div>
                                
                                <!-- 4. Empaque / Almacén -->
                                <div class="col-md-3 col-sm-6">
                                    <div class="d-flex flex-column gap-1.5 p-2 rounded bg-white border border-light">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <span class="fw-bold small text-dark d-flex align-items-center gap-1.5">
                                                <i class="fas fa-box text-success" style="font-size: 0.85rem;"></i> Empaque
                                            </span>
                                            <span class="fw-bold text-success" style="font-size: 0.8rem;">${prod.empaque.porcentaje}%</span>
                                        </div>
                                        <div class="progress rounded-pill bg-light" style="height: 8px;">
                                            <div class="progress-bar rounded-pill ${this.obtenerColorBarra(prod.empaque.porcentaje)}" 
                                                 role="progressbar" 
                                                 style="width: ${prod.empaque.porcentaje}%" 
                                                 aria-valuenow="${prod.empaque.porcentaje}" 
                                                 aria-valuemin="0" 
                                                 aria-valuemax="100">
                                            </div>
                                        </div>
                                        <div class="text-muted small d-flex justify-content-between" style="font-size: 0.72rem;">
                                            <span>Alistado:</span>
                                            <span class="fw-semibold text-dark">${prod.empaque.cantidad} / ${prod.cant_requerida}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });

                html += `
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';
            contenedor.innerHTML = html;

        } catch (error) {
            console.error('❌ Error [Gerencia] cargarTrazabilidad:', error);
            contenedor.innerHTML = `
                <div class="alert alert-danger shadow-sm border-0 d-flex align-items-center" role="alert">
                    <i class="fas fa-exclamation-triangle fa-2x me-3"></i>
                    <div>
                        <h5 class="alert-heading fw-bold mb-1">Error de conexión</h5>
                        <p class="mb-0">No se pudo conectar con el servidor para consolidar la trazabilidad.</p>
                    </div>
                </div>
            `;
        }
    },

    /**
     * Retorna clases de color de bootstrap para las barras de progreso
     */
    obtenerColorBarra: function (porcentaje) {
        if (porcentaje >= 100) return 'bg-success';
        if (porcentaje > 0) return 'bg-warning';
        return 'bg-secondary';
    },

    /**
     * Mapea el estado global a un esquema cromático premium HSL
     */
    obtenerColorSemaforo: function (estado) {
        switch (estado) {
            case 'RETENIDO EN PLANTA':
                return {
                    border: '#ef4444', // Rojo Coral
                    bg: '#fee2e2',
                    bgLight: '#fef2f2',
                    color: '#991b1b'
                };
            case 'LISTO PARA DESPACHO':
                return {
                    border: '#10b981', // Verde Esmeralda
                    bg: '#d1fae5',
                    bgLight: '#ecfdf5',
                    color: '#065f46'
                };
            case 'EN PROCESO':
            default:
                return {
                    border: '#f59e0b', // Amarillo Ámbar
                    bg: '#fef3c7',
                    bgLight: '#fffbeb',
                    color: '#92400e'
                };
        }
    },

    desactivar: function () {
        console.log('🔌 [Gerencia] Módulo desactivado');
    }
};

// Exportar globalmente
window.ModuloGerencia = ModuloGerencia;
