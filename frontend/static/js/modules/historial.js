// ============================================
// historial.js - Lógica de Historial Global
// ============================================

(function () {
    console.log('✅ Historial.js cargando...');

    // Variables de estado privadas al módulo
    let h_datos = [];
    let h_paginaActual = 1;
    const getHRegistrosPorPagina = () => window.innerWidth < 992 ? 10 : 20;

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
        const h_registrosPorPagina = getHRegistrosPorPagina();
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
                    // FIX: Mostrar Cantidad Recibida (Total) en lugar de Real (Buenos)
                    cantidad = r.Cant !== undefined ? r.Cant : (r['CANTIDAD RECIBIDA'] || r['CANTIDAD REAL']);
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
                                <div class="d-flex align-items-center gap-2">
                                    <small class="text-muted fw-bold">${r.Fecha}</small>
                                    ${(window.AppState?.user?.nombre?.toUpperCase().includes('PAOLA') || window.AppState?.user?.nombre?.toUpperCase().includes('ZOENIA') || window.AppState?.user?.name?.toUpperCase().includes('PAOLA') || window.AppState?.user?.name?.toUpperCase().includes('ZOENIA') || window.AppState?.user?.rol === 'Administración') ?
                        `<button class="btn btn-sm btn-outline-primary p-1" onclick="window.ModuloHistorial.editarRegistro(${h_datos.indexOf(r)})" style="line-height: 1;">
                                            <i class="fas fa-pencil-alt" style="font-size: 0.8rem;"></i>
                                        </button>` : ''}
                                </div>
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
                                ${(window.AppState?.user?.nombre?.toUpperCase().includes('PAOLA') || window.AppState?.user?.name?.toUpperCase().includes('PAOLA') || window.AppState?.user?.rol === 'Administración') ? '<th class="text-center" style="width: 50px;"></th>' : ''}
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
                    // FIX: Mostrar Cantidad Recibida (Total) en lugar de Real (Buenos)
                    cantidad = r.Cant !== undefined ? r.Cant : (r['CANTIDAD RECIBIDA'] || r['CANTIDAD REAL']);
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
                        ${(window.AppState?.user?.nombre?.toUpperCase().includes('PAOLA') || window.AppState?.user?.nombre?.toUpperCase().includes('ZOENIA') || window.AppState?.user?.name?.toUpperCase().includes('PAOLA') || window.AppState?.user?.name?.toUpperCase().includes('ZOENIA') || window.AppState?.user?.rol === 'Administración') ?
                        `<td class="text-center">
                                <button class="btn btn-sm btn-link text-primary p-0" onclick="window.ModuloHistorial.editarRegistro(${h_datos.indexOf(r)})">
                                    <i class="fas fa-pencil-alt"></i>
                                </button>
                            </td>` : ''}
                    </tr>
                `;
            });

            html += `</tbody></table></div>`;
        }

        // Controles de Paginación
        if (totalPaginas > 1) {
            const h_registrosPorPagina = getHRegistrosPorPagina();
            const inicio_real = (h_paginaActual - 1) * h_registrosPorPagina + 1;
            const fin_real = Math.min(h_paginaActual * h_registrosPorPagina, h_datos.length);

            html += `
                <div class="pagination-container d-flex justify-content-between align-items-center p-3 bg-light border-top">
                    <div class="pagination-info text-muted small">
                        Mostrando ${inicio_real} a ${fin_real} de ${h_datos.length} registros
                    </div>
                    <nav>
                        <ul class="pagination-buttons pagination pagination-sm mb-0" style="display: flex; gap: 5px; list-style: none; padding: 0;">
                            <li class="page-item ${h_paginaActual === 1 ? 'disabled' : ''}">
                                <button class="pagination-btn page-link" onclick="window.ModuloHistorial.cambiarPagina(${h_paginaActual - 1})" ${h_paginaActual === 1 ? 'disabled' : ''}>
                                    <i class="fas fa-chevron-left"></i> <span class="btn-text">Anterior</span>
                                </button>
                            </li>
                            <li class="page-item disabled">
                                <span class="page-link text-dark">Página ${h_paginaActual} de ${totalPaginas}</span>
                            </li>
                            <li class="page-item ${h_paginaActual === totalPaginas ? 'disabled' : ''}">
                                <button class="pagination-btn page-link" onclick="window.ModuloHistorial.cambiarPagina(${h_paginaActual + 1})" ${h_paginaActual === totalPaginas ? 'disabled' : ''}>
                                    <span class="btn-text">Siguiente</span> <i class="fas fa-chevron-right"></i>
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
        const h_registrosPorPagina = getHRegistrosPorPagina();
        const totalPaginas = Math.ceil(h_datos.length / h_registrosPorPagina);
        if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
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

            // Re-renderizar al cambiar tamaño de ventana (Debounce simple)
            let resizeTimer;
            window.addEventListener('resize', () => {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(() => {
                    renderizarTablaHistorial();
                }, 200);
            });

        } catch (e) {
            console.error('❌ Error en initHistorial:', e);
        }
    }

    // Registro Global indispensable para el onclick en HTML
    /**
     * Abrir modal de edición (Sólo Paola)
     */
    function editarRegistro(index) {
        const r = h_datos[index];
        if (!r || !r.hoja || !r.fila) {
            mostrarNotificacion('No se puede editar este registro (Faltan metadatos)', 'error');
            return;
        }

        const modal = document.getElementById('modalEditarHistorial');
        const container = document.getElementById('campos-edicion-dinamicos');
        document.getElementById('edit-hoja').value = r.hoja;
        document.getElementById('edit-fila').value = r.fila;

        let html = '';

        if (r.Tipo === 'INYECCION') {
            html += `
                <div class="edit-section mb-4">
                    <h6 class="section-title"><i class="fas fa-info-circle me-2"></i> Información General</h6>
                    <div class="row g-3">
                        <div class="col-md-6">${crearCampoEdicion('Responsable', r.Responsable, 'text', 'RESPONSABLE')}</div>
                        <div class="col-md-6">${crearCampoEdicion('Departamento', r.DEPARTAMENTO, 'text', 'DEPARTAMENTO')}</div>
                        <div class="col-md-6">${crearCampoEdicion('Máquina', r.Extra, 'text', 'MAQUINA')}</div>
                        <div class="col-md-6">${crearCampoEdicion('Orden Producción', r.Orden, 'text', 'ORDEN PRODUCCION')}</div>
                        <div class="col-md-6">${crearCampoEdicion('ID Código', r.Producto, 'text', 'ID CODIGO')}</div>
                        <div class="col-md-6">${crearCampoEdicion('Cod. Ensamble', r.CODIGO_ENSAMBLE, 'text', 'CODIGO ENSAMBLE')}</div>
                    </div>
                </div>

                <div class="edit-section mb-4">
                    <h6 class="section-title"><i class="fas fa-clock me-2"></i> Tiempos y Fechas</h6>
                    <div class="row g-3">
                        <div class="col-md-12">${crearCampoEdicion('Fecha Inicia', r.FECHA_INICIA, 'text', 'FECHA INICIA')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Hora Llegada', r.HORA_LLEGADA, 'text', 'HORA LLEGADA')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Hora Inicio', r.HORA_INICIO, 'text', 'HORA INICIO')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Hora Termina', r.HORA_TERMINA, 'text', 'HORA TERMINA')}</div>
                    </div>
                </div>

                <div class="edit-section mb-4">
                    <h6 class="section-title"><i class="fas fa-microchip me-2"></i> Producción y Contadores</h6>
                    <div class="row g-3">
                        <div class="col-md-4">${crearCampoEdicion('No. Cavidades', r.N_CAVIDADES, 'number', 'No. CAVIDADES')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Contador Maq.', r.CONTADOR_MAQ, 'number', 'CONTADOR MAQ.')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Cant. Contador', r.CANT_CONTADOR, 'number', 'CANT. CONTADOR')}</div>
                        <div class="col-md-6">${crearCampoEdicion('Tomados Proceso', r.TOMADOS_PROCESO, 'number', 'TOMADOS EN PROCESO')}</div>
                        <div class="col-md-6">${crearCampoEdicion('Cantidad REAL', r.Cant, 'number', 'CANTIDAD REAL')}</div>
                        <div class="col-md-12">${crearCampoEdicion('Almacén Destino', r.ALMACEN_DESTINO, 'text', 'ALMACEN DESTINO')}</div>
                    </div>
                </div>

                <div class="edit-section mb-4">
                    <h6 class="section-title"><i class="fas fa-weight-hanging me-2"></i> Pesos (g)</h6>
                    <div class="row g-3">
                        <div class="col-md-6">${crearCampoEdicion('Peso Tomadas (g)', r.PESO_TOMADOS_PROCESO, 'number', 'PESO TOMADAS EN PROCESO')}</div>
                        <div class="col-md-6">${crearCampoEdicion('Peso Vela (g)', r.PESO_VELA, 'number', 'PESO VELA MAQUINA')}</div>
                        <div class="col-md-12">${crearCampoEdicion('Peso Bujes (g)', r.PESO_BUJES, 'number', 'PESO BUJES')}</div>
                    </div>
                </div>

                <div class="edit-section mb-3">
                    <h6 class="section-title"><i class="fas fa-comment-alt me-2"></i> Observaciones del Registro</h6>
                    <textarea class="form-control edit-input" data-col="OBSERVACIONES" rows="2" 
                        style="border-radius: 10px; border: 1px solid #e2e8f0; padding: 10px; font-size: 0.9rem;">${r.Detalle || ''}</textarea>
                </div>
            `;
        } else if (r.Tipo === 'PULIDO') {
            html += `
                <div class="edit-section mb-4">
                    <h6 class="section-title"><i class="fas fa-id-badge me-2"></i> Datos de Pulido</h6>
                    <div class="row g-3">
                        <div class="col-md-12">${crearCampoEdicion('Responsable', r.Responsable, 'text', 'RESPONSABLE')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Recibidos', r.RECIBIDOS, 'number', 'CANTIDAD RECIBIDA')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Buenos', r.BUENOS, 'number', 'BUJES BUENOS')}</div>
                        <div class="col-md-4">${crearCampoEdicion('PNC', r.PNC, 'number', 'PNC')}</div>
                    </div>
                </div>
            `;
        } else if (r.Tipo === 'ENSAMBLE') {
            html += `
                <div class="edit-section mb-4">
                    <h6 class="section-title"><i class="fas fa-puzzle-piece me-2"></i> Datos de Ensamble</h6>
                    <div class="row g-3">
                        <div class="col-md-12">${crearCampoEdicion('Responsable', r.Responsable, 'text', 'RESPONSABLE')}</div>
                        <div class="col-md-12">${crearCampoEdicion('Cantidad', r.Cant, 'number', 'CANTIDAD')}</div>
                    </div>
                </div>
            `;
        } else if (r.Tipo === 'MEZCLA') {
            html += `
                <div class="edit-section mb-4">
                    <h6 class="section-title"><i class="fas fa-blender me-2"></i> Datos de Mezcla</h6>
                    <div class="row g-3">
                        <div class="col-md-6">${crearCampoEdicion('Responsable', r.Responsable, 'text', 'RESPONSABLE')}</div>
                        <div class="col-md-6">${crearCampoEdicion('Máquina', r.Extra, 'text', 'MAQUINA')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Virgen (Kg)', r.VIRGEN, 'number', 'VIRGEN (Kg)')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Molido (Kg)', r.MOLIDO, 'number', 'MOLIDO (Kg)')}</div>
                        <div class="col-md-4">${crearCampoEdicion('Pigmento (Kg)', r.PIGMENTO, 'number', 'PIGMENTO (Kg)')}</div>
                    </div>
                </div>
            `;
        }

        // Siempre permitir editar observaciones
        html += `
            <div class="edit-section mb-3">
                <h6 class="section-title text-primary"><i class="fas fa-comment-dots me-2"></i> Motivo de la Corrección</h6>
                <textarea class="form-control" id="edit-motivo" rows="3" 
                    placeholder="Describa brevemente por qué realiza este cambio..."
                    style="border-radius: 12px; border: 1px solid #cbd5e1; padding: 12px; font-size: 0.95rem;"></textarea>
            </div>`;

        container.innerHTML = html;
        modal.style.display = 'flex';
    }

    function crearCampoEdicion(label, valor, tipo, colName) {
        return `
            <div class="form-group mb-1">
                <label class="small fw-bold text-secondary text-uppercase mb-1 d-block" style="font-size: 0.7rem; letter-spacing: 0.5px;">${label}</label>
                <input type="${tipo}" class="form-control edit-input" data-col="${colName}" value="${valor || ''}" 
                    style="border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; font-size: 0.95rem; background: #ffffff; transition: all 0.2s ease;">
            </div>
        `;
    }

    /**
     * Guardar cambios en el backend
     */
    async function guardarCambios() {
        const hoja = document.getElementById('edit-hoja').value;
        const fila = document.getElementById('edit-fila').value;
        const motivo = document.getElementById('edit-motivo').value;

        const inputs = document.querySelectorAll('.edit-input');
        const datos = {};
        inputs.forEach(input => {
            datos[input.dataset.col] = input.value;
        });

        // Añadir motivo a las observaciones si se proporcionó (Concatenar si ya existe en datos)
        if (motivo) {
            if (datos['OBSERVACIONES']) {
                datos['OBSERVACIONES'] = datos['OBSERVACIONES'] + " | Motivo: " + motivo;
            } else {
                datos['OBSERVACIONES'] = motivo;
            }
        }

        try {
            mostrarLoading(true);
            const res = await fetch('/api/historial/actualizar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    hoja: hoja,
                    fila: fila,
                    datos: datos,
                    usuario: window.AppState.user.nombre
                })
            });

            const data = await res.json();
            if (data.success) {
                mostrarNotificacion('Registro corregido correctamente', 'success');
                cerrarModalEdicion();
                cargarHistorial(); // Refrescar lista
            } else {
                mostrarNotificacion(data.error || 'Error al actualizar', 'error');
            }
        } catch (error) {
            console.error('Error guardando edicion:', error);
            mostrarNotificacion('Error de conexión', 'error');
        } finally {
            mostrarLoading(false);
        }
    }

    function cerrarModalEdicion() {
        document.getElementById('modalEditarHistorial').style.display = 'none';
    }

    window.filtrarHistorial = cargarHistorial;
    window.ModuloHistorial = {
        inicializar: initHistorial,
        filtrar: cargarHistorial,
        cambiarPagina: cambiarPagina,
        editarRegistro: editarRegistro,
        guardarCambios: guardarCambios,
        cerrarModalEdicion: cerrarModalEdicion
    };

    console.log('🚀 Módulo Historial registrado y listo');
})();
