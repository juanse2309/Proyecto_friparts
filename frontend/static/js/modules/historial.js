// ============================================
// historial.js - Lógica de Historial Global
// ============================================

(function () {
    console.log('✅ Historial.js cargando...');

    // Variables de estado privadas al módulo
    let h_datos = [];
    let h_paginaActual = 1;
    const h_registrosPorPagina = 20;

    /**
     * Cargar datos desde la API
     */
    async function cargarHistorial() {
        try {
            console.log('📜 Cargando historial...');
            if (typeof mostrarLoading === 'function') mostrarLoading(true);

            const proceso = document.getElementById('tipoProceso')?.value || '';
            const desde = document.getElementById('fechaDesde')?.value || '';
            const hasta = document.getElementById('fechaHasta')?.value || '';

            const url = `/api/historial-global?tipo=${proceso}&desde=${desde}&hasta=${hasta}`;

            if (typeof fetchData !== 'function') {
                console.error('❌ Error: fetchData no está definida.');
                return;
            }

            const res = await fetchData(url);

            if (res && res.success) {
                h_datos = res.data || [];
                h_paginaActual = 1; // Reseteo imperativo a página 1

                // Debug para verificar llaves reales Juan Sebastian
                if (h_datos.length > 0) {
                    console.log('✅ Historial - Primer registro recibido:', h_datos[0]);
                } else {
                    console.log('⚠️ Historial - No se recibieron datos');
                }

                renderizarTablaHistorial();

                const totalSpan = document.getElementById('total-registros-historial');
                if (totalSpan) totalSpan.textContent = h_datos.length;
            }

        } catch (error) {
            console.error('❌ Error en cargarHistorial:', error);
        } finally {
            if (typeof mostrarLoading === 'function') mostrarLoading(false);
        }
    }

    /**
     * Renderizar la tabla con los datos actuales y paginación
     */
    function renderizarTablaHistorial() {
        const container = document.getElementById('historial-container');
        if (!container) return;

        if (!h_datos || h_datos.length === 0) {
            container.innerHTML = '<div class="text-center py-5 text-muted"><i class="fas fa-info-circle mb-2"></i> No se encontraron registros</div>';
            return;
        }

        // Calcular paginación
        const inicio = (h_paginaActual - 1) * h_registrosPorPagina;
        const fin = inicio + h_registrosPorPagina;
        const registrosVisibles = h_datos.slice(inicio, fin);
        const totalPaginas = Math.ceil(h_datos.length / h_registrosPorPagina);

        // Detectar modo vista (Móvil vs Escritorio)
        const esMovil = window.innerWidth < 992;

        let html = '';

        if (esMovil) {
            // VISTA DE TARJETAS (MOBILE)
            html += '<div class="d-flex flex-column gap-3 pb-5">';

            registrosVisibles.forEach(r => {
                const badgeClass = obtenerBadgeClass(r.Tipo);

                // Normalización de datos
                let responsable = r.Responsable;
                let cantidad = r.Cant;
                let orden = r.Orden;
                let maquina = r.Extra || '-';

                if (r.Tipo === 'INYECCION') {
                    responsable = r.RESPONSABLE || r.Responsable || r.OPERARIO || r.Usuario || '-';
                    cantidad = r['CANTIDAD REAL'] !== undefined ? r['CANTIDAD REAL'] : r.Cant;
                    orden = r['ORDEN PRODUCCION'] || r.Orden;
                    maquina = r.MAQUINA || r.Extra;
                } else if (r.Tipo === 'PULIDO') {
                    responsable = r.RESPONSABLE || r.Responsable || r.OPERARIO || r.Usuario || '-';
                    cantidad = r['CANTIDAD REAL'] !== undefined ? r['CANTIDAD REAL'] : r.Cant;
                    orden = r['ORDEN PRODUCCION'] || r.Orden;
                    maquina = 'N/A';
                } else if (r.Tipo === 'ENSAMBLE') {
                    responsable = r.RESPONSABLE || r.Responsable || r.OPERARIO || r.Usuario || '-';
                    cantidad = r['CANTIDAD'] !== undefined ? r['CANTIDAD'] : r.Cant;
                    orden = r['OP NUMERO'] || r.Orden;
                    maquina = 'N/A';
                }

                html += `
                    <div class="card shadow-sm border-0" style="border-radius: 12px; overflow: hidden;">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="badge ${badgeClass}">${r.Tipo}</span>
                                <small class="text-muted fw-bold">${r.Fecha}</small>
                            </div>
                            <h6 class="mb-1 fw-bold text-dark">${r.Producto || 'Sin Producto'}</h6>
                            <div class="text-muted small mb-3">
                                <i class="fas fa-user me-1"></i> ${responsable}
                            </div>
                            
                            <div class="d-flex justify-content-between align-items-center bg-light p-2 rounded">
                                <div class="text-center px-2">
                                    <small class="d-block text-muted" style="font-size: 10px;">CANTIDAD</small>
                                    <span class="fw-bold fs-5 text-primary">${cantidad ?? '-'}</span>
                                </div>
                                <div class="text-center px-2 border-start">
                                    <small class="d-block text-muted" style="font-size: 10px;">ORDEN</small>
                                    <span class="fw-medium">${orden || '-'}</span>
                                </div>
                                <div class="text-center px-2 border-start">
                                    <small class="d-block text-muted" style="font-size: 10px;">MAQ</small>
                                    <span class="fw-medium">${maquina || '-'}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';

        } else {
            // VISTA DE TABLA (DESKTOP)
            html += `
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0" style="min-width: 1000px;">
                        <thead class="ps-4 bg-light">
                            <tr>
                                <th class="ps-4" style="width: 100px;">Fecha</th>
                                <th style="width: 120px;">Tipo</th>
                                <th style="width: 150px;">Responsable</th>
                                <th style="width: 120px;">Producto</th>
                                <th style="width: 120px;">Orden Prod.</th>
                                <th style="width: 100px;">Máquina</th>
                                <th>Detalle</th>
                                <th class="text-center" style="width: 80px;">Cant.</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            registrosVisibles.forEach(r => {
                const badgeClass = obtenerBadgeClass(r.Tipo);

                // Valores por defecto (normalizados)
                let responsable = r.Responsable;
                let cantidad = r.Cant;
                let orden = r.Orden;
                let maquina = r.Extra || '-';

                // Manejo especial por proceso según requerimiento Juan Sebastian
                if (r.Tipo === 'INYECCION') {
                    responsable = r.RESPONSABLE || r.Responsable || r.OPERARIO || r.Usuario || '-';
                    cantidad = r['CANTIDAD REAL'] !== undefined ? r['CANTIDAD REAL'] : r.Cant;
                    orden = r['ORDEN PRODUCCION'] || r.Orden;
                    maquina = r.MAQUINA || r.Extra;
                } else if (r.Tipo === 'PULIDO') {
                    responsable = r.RESPONSABLE || r.Responsable || r.OPERARIO || r.Usuario || '-';
                    cantidad = r['CANTIDAD REAL'] !== undefined ? r['CANTIDAD REAL'] : r.Cant;
                    orden = r['ORDEN PRODUCCION'] || r.Orden;
                    maquina = '-'; // Pulido no tiene máquina
                } else if (r.Tipo === 'ENSAMBLE') {
                    responsable = r.RESPONSABLE || r.Responsable || r.OPERARIO || r.Usuario || '-';
                    cantidad = r['CANTIDAD'] !== undefined ? r['CANTIDAD'] : r.Cant;
                    orden = r['OP NUMERO'] || r.Orden;
                    maquina = '-';
                }

                html += `
                    <tr>
                        <td class="ps-4">${r.Fecha || '-'}</td>
                        <td><span class="badge ${badgeClass}">${r.Tipo || 'N/A'}</span></td>
                        <td>${responsable || '-'}</td>
                        <td><strong>${r.Producto || '-'}</strong></td>
                        <td><span class="text-primary fw-medium">${orden || '-'}</span></td>
                        <td><small>${maquina || '-'}</small></td>
                        <td><small class="text-muted">${r.Detalle || '-'}</small></td>
                        <td class="text-center fw-bold">${cantidad ?? '-'}</td>
                    </tr>
                `;
            });

            html += `</tbody></table></div>`;
        }

        // Controles de Paginación
        if (totalPaginas > 1) {
            html += `
                <div class="d-flex justify-content-between align-items-center p-3 bg-light border-top">
                    <div class="text-muted small">
                        Mostrando ${inicio + 1} a ${Math.min(fin, h_datos.length)} de ${h_datos.length} registros
                    </div>
                    <nav>
                        <ul class="pagination pagination-sm mb-0">
                            <li class="page-item ${h_paginaActual === 1 ? 'disabled' : ''}">
                                <button class="page-link" onclick="window.ModuloHistorial.cambiarPagina(${h_paginaActual - 1})">
                                    <i class="fas fa-chevron-left"></i> Anterior
                                </button>
                            </li>
                            <li class="page-item disabled">
                                <span class="page-link text-dark">Página ${h_paginaActual} de ${totalPaginas}</span>
                            </li>
                            <li class="page-item ${h_paginaActual === totalPaginas ? 'disabled' : ''}">
                                <button class="page-link" onclick="window.ModuloHistorial.cambiarPagina(${h_paginaActual + 1})">
                                    Siguiente <i class="fas fa-chevron-right"></i>
                                </button>
                            </li>
                        </ul>
                    </nav>
                </div>
            `;
        }

        container.innerHTML = html;
    }

    /**
     * Cambiar de página
     */
    function cambiarPagina(nuevaPagina) {
        h_paginaActual = nuevaPagina;
        renderizarTablaHistorial();
        const container = document.getElementById('historial-container');
        if (container) container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /**
     * Obtener clase de badge según tipo
     */
    function obtenerBadgeClass(tipo) {
        switch (tipo) {
            case 'INYECCION': return 'bg-primary';
            case 'PULIDO': return 'bg-info';
            case 'ENSAMBLE': return 'bg-success';
            case 'VENTA': return 'bg-warning text-dark';
            case 'PNC': return 'bg-danger';
            default: return 'bg-secondary';
        }
    }

    /**
     * Inicializar módulo
     */
    function initHistorial() {
        console.log('🔧 Inicializando módulo de historial...');
        try {
            const hInput = document.getElementById('fechaHasta');
            const dInput = document.getElementById('fechaDesde');
            if (hInput && !hInput.value) hInput.value = new Date().toISOString().split('T')[0];
            if (dInput && !dInput.value) {
                const d = new Date(); d.setDate(d.getDate() - 7);
                dInput.value = d.toISOString().split('T')[0];
            }
            cargarHistorial();
        } catch (e) {
            console.error('❌ Error en initHistorial:', e);
        }
    }

    // Registro Global indispensable para el onclick en HTML
    window.filtrarHistorial = cargarHistorial;
    window.ModuloHistorial = {
        inicializar: initHistorial,
        filtrar: cargarHistorial,
        cambiarPagina: cambiarPagina
    };

    console.log('🚀 Módulo Historial registrado y listo');
})();
