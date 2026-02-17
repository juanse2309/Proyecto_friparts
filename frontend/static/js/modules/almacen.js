/**
 * Módulo de Gestión de Almacén (Alistamiento)
 * Desarrollado para FriParts por Antigravity
 * Soporta alistamiento parcial por cantidad.
 */

const AlmacenModule = {
    pedidosPendientes: [],
    pedidoActual: null,
    tvInterval: null,
    autoRefreshInterval: null,
    scrollInterval: null,
    scrollTimeout: null, // Timeout para el delay del scroll
    isTVMode: false,

    /**
     * Inicializar módulo
     */
    inicializar: function () {
        console.log('🔧 [Almacen] Inicializando módulo...');
        console.log('🔧 [Almacen] Estado actual:', {
            pedidosPendientes: this.pedidosPendientes.length,
            user: window.AppState?.user,
            tvMode: this.isTVMode
        });

        this.cargarPedidos();
        this.iniciarAutoRefresco();

        // Listener para refrescar automáticamente al entrar a la página
        document.querySelector('[data-page="almacen"]')?.addEventListener('click', () => {
            console.log('🔧 [Almacen] Click en menú detectado, recargando...');
            this.cargarPedidos();
        });

        console.log('✅ [Almacen] Módulo inicializado correctamente');
    },

    /**
     * Cargar pedidos pendientes desde la API
     */
    cargarPedidos: async function (showLoading = true) {
        console.log('📦 [Almacen] cargarPedidos() iniciado, showLoading:', showLoading);
        try {
            if (showLoading) mostrarLoading(true);

            // CRÍTICO: Si window.AppState.user no está listo, intentar recuperarlo de AuthModule o SessionStorage
            let user = window.AppState?.user;
            console.log('📦 [Almacen] Usuario inicial:', user);
            if (!user || (!user.name && !user.nombre)) {
                const sessionUser = sessionStorage.getItem('friparts_user');
                console.log('📦 [Almacen] Recuperando usuario de sesión:', sessionUser);
                if (sessionUser) {
                    const parsed = JSON.parse(sessionUser);
                    user = {
                        name: parsed.nombre,
                        nombre: parsed.nombre,
                        rol: parsed.rol
                    };
                    console.log('📦 [Almacen] Usuario recuperado de sesión:', user.name);
                }
            }

            const url = new URL('/api/pedidos/pendientes', window.location.origin);
            if (user) {
                const isAdmin = user.rol === 'Administración' ||
                    (user.name && (user.name.toUpperCase().includes('ANDRES') || user.name.toUpperCase().includes('ANDRÉS')));

                // Si es admin o Andres, pasamos el rol Administración para que el backend devuelva todo
                url.searchParams.append('usuario', user.name || user.nombre || 'N/A');
                url.searchParams.append('rol', isAdmin ? 'Administración' : (user.rol || 'N/A'));
            }

            // CRÍTICO: Cache buster para evitar que el navegador guarde la respuesta
            url.searchParams.append('_t', Date.now());

            console.log('📦 [Almacen] Haciendo fetch a:', url.toString());
            const response = await fetch(url, {
                cache: 'no-store', // Forzar al navegador a no usar cache
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            });
            console.log('📦 [Almacen] Response status:', response.status);

            const data = await response.json();
            console.log('📦 [Almacen] Datos recibidos:', {
                success: data.success,
                pedidosCount: data.pedidos?.length || 0
            });

            if (data.success) {
                // TV MODE: Detectar nuevos pedidos para sonido
                if (this.isTVMode && this.pedidosPendientes.length > 0) {
                    const nuevosCount = data.pedidos.length;
                    const anterioresCount = this.pedidosPendientes.length;

                    if (nuevosCount > anterioresCount) {
                        try {
                            if (window.ModuloUX && window.ModuloUX.playSound) {
                                window.ModuloUX.playSound('new_order');
                            }
                        } catch (e) {
                            console.warn('Error reproduciendo sonido TV', e);
                        }
                    }
                }

                this.pedidosPendientes = data.pedidos;
                console.log('📦 [Almacen] Pedidos asignados, llamando renderizarTarjetas()...');
                this.renderizarTarjetas();
                console.log('✅ [Almacen] renderizarTarjetas() completado');
            } else {
                console.error('Error al cargar pedidos:', data.error);
                if (showLoading) mostrarNotificacion('Error al cargar pedidos pendientes', 'error');
            }
        } catch (error) {
            console.error('❌ [Almacen] Error fetch pedidos:', error);
            if (showLoading) mostrarNotificacion('Error de conexión con el servidor', 'error');
        } finally {
            if (showLoading) mostrarLoading(false);
            console.log('📦 [Almacen] cargarPedidos() finalizado');

            // Si está en modo TV, reiniciar el scroll después de cargar nuevos datos
            if (this.isTVMode) {
                this.iniciarAutoScroll();
            }
        }
    },

    /**
     * Renderizar tarjetas de pedidos en el contenedor
     */
    renderizarTarjetas: function () {
        const container = document.getElementById('almacen-container');
        if (!container) return;

        if (this.pedidosPendientes.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted empty-state-almacen">
                    <i class="fas fa-clipboard-check fa-3x mb-3" style="opacity: 0.2; color: #10b981;"></i>
                    <p>¡Buen trabajo! No hay pedidos pendientes</p>
                </div>
            `;
            return;
        }

        let html = '<div class="row g-3">';
        // Filtrar pedidos completados (100% Alistado y 100% Enviado)
        const pendientesReales = this.pedidosPendientes.filter(p => {
            const alistado = parseInt(p.progreso) || 0;
            const enviado = parseInt(p.progreso_despacho) || 0;
            return !(alistado === 100 && enviado === 100);
        });

        if (pendientesReales.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted empty-state-almacen">
                     <i class="fas fa-check-circle fa-3x mb-3" style="opacity: 0.2; color: #10b981;"></i>
                    <p>¡Todo al día! No hay pedidos pendientes de gestión.</p>
                </div>
            `;
            return;
        }

        pendientesReales.forEach(pedido => {
            // Validación robusta: Omitir pedidos "fantasma" sin datos mínimos
            if (!pedido || !pedido.id_pedido || !pedido.cliente || pedido.cliente === 'undefined') {
                console.warn('⚠️ [Almacen] Omitiendo pedido inválido/vacío:', pedido);
                return;
            }

            const progresoAlisado = parseInt(pedido.progreso) || 0;
            const progresoEnviado = parseInt(pedido.progreso_despacho) || 0;

            // Colores sugeridos por el usuario
            const colorStatus = this.getColorPorEstadoProporcional(progresoAlisado, progresoEnviado);

            const currentUser = window.AppState?.user;
            // Natalia y Rol Administración pueden DELEGAR
            const puedeDelegar = (currentUser?.name && (
                currentUser.name.toUpperCase().includes('NATALIA') ||
                currentUser.name.toUpperCase().includes('NATHALIA')
            )) || currentUser?.rol === 'Administración';
            const esParaMi = pedido.delegado_a === currentUser?.name;

            html += `
                <div class="col-md-6 col-lg-4">
                    <div class="card h-100 shadow-sm border-0 almacen-card-pro"
                        style="transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); border-radius: 12px; overflow: hidden; border-left: 5px solid ${colorStatus} !important; background: #fff; min-height: 280px; display: flex; flex-direction: column;">
                        <div style="background: #f8fafc; padding: 12px 15px; border-bottom: 1px solid #edf2f7; cursor: pointer;" onclick="AlmacenModule.abrirModal('${pedido.id_pedido}')">
                            <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
                                <span class="fw-bold text-primary order-id-ref" style="font-size: 1.4rem; white-space: nowrap; letter-spacing: -0.3px; font-weight: 800;">${pedido.id_pedido}</span>
                                <div class="d-flex flex-wrap gap-1 align-items-center justify-content-end" style="flex: 1;">
                                    ${esParaMi ? '<span class="badge bg-info" style="font-size: 0.6rem; padding: 4px 6px; font-weight: 700; border-radius: 4px;"><i class="fas fa-user-check me-1"></i>MÍO</span>' : ''}
                                    <span class="badge" style="background: ${colorStatus}; font-size: 0.6rem; padding: 4px 6px; text-transform: uppercase; font-weight: 700; border-radius: 4px;">${pedido.estado}</span>
                                </div>
                            </div>
                        </div>
                        <div class="card-body" style="padding: 15px; flex: 1; display: flex; flex-direction: column;">
                            <h6 class="card-title fw-bold mb-1" style="color: #1e293b; cursor: pointer; font-size: 0.85rem; line-height: 1.3; margin-bottom: 4px !important;" onclick="AlmacenModule.abrirModal('${pedido.id_pedido}')">${pedido.cliente}</h6>
                            <p class="text-muted mb-1" style="font-size: 0.7rem; margin-bottom: 4px !important;"><i class="fas fa-map-marker-alt me-1"></i> ${pedido.direccion || 'S/D'} - ${pedido.ciudad || 'S/C'}</p>
                            <p class="text-muted mb-3" style="font-size: 0.7rem; margin-bottom: 12px !important;"><i class="fas fa-calendar-alt me-1"></i> ${pedido.fecha} | <i class="fas fa-user me-1"></i> ${pedido.vendedor}</p>
                            
                            <!-- Barra Doble de Progreso -->
                            <div class="mt-auto" style="cursor: pointer; margin-bottom: 10px;" onclick="AlmacenModule.abrirModal('${pedido.id_pedido}')">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small fw-bold text-muted" style="font-size: 0.65rem;"><i class="fas fa-box me-1"></i> Alistado</span>
                                    <span class="small fw-bold" style="color: #6366f1; font-size: 0.7rem;">${progresoAlisado}%</span>
                                </div>
                                <div class="progress progress-modern" style="height: 6px; border-radius: 10px; background: #f1f5f9; margin-bottom: 10px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated progress-bar-shimmer ${progresoAlisado > 0 ? 'progress-glow-indigo' : ''}" role="progressbar" style="width: ${progresoAlisado}%; background: linear-gradient(90deg, #6366f1, #818cf8);" 
                                        aria-valuenow="${progresoAlisado}" aria-valuemin="0" aria-valuemax="100"></div>
                                </div>

                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small fw-bold text-muted" style="font-size: 0.65rem;"><i class="fas fa-truck me-1"></i> Despachado</span>
                                    <span class="small fw-bold" style="color: #10b981; font-size: 0.7rem;">${progresoEnviado}%</span>
                                </div>
                                <div class="progress progress-modern" style="height: 6px; border-radius: 10px; background: #f1f5f9;">
                                    <div class="progress-bar progress-bar-shimmer ${progresoEnviado > 0 ? 'progress-glow-emerald' : ''}" role="progressbar" style="width: ${progresoEnviado}%; background: linear-gradient(90deg, #10b981, #34d399);" 
                                        aria-valuenow="${progresoEnviado}" aria-valuemin="0" aria-valuemax="100"></div>
                                </div>
                            </div>

                            <div class="mt-3 pt-3 border-top delegation-section" style="border-top: 1px dashed #e2e8f0 !important; ${pedido.delegado_a || puedeDelegar ? '' : 'display:none;'}">
                                <label class="small fw-bold text-muted mb-2 d-block text-uppercase delegate-label" style="letter-spacing: 0.5px; font-size: 0.6rem; opacity: 0.7;">
                                    ${pedido.delegado_a ? 'Alistador Asignado' : 'Delegar Alistamiento'}
                                </label>
                                
                                <!-- Nombre visible solo en TV Mode -->
                                <div class="alistador-tv-display" style="display: none; font-weight: 800; color: #6366f1; text-transform: uppercase;">
                                    ${pedido.delegado_a || 'Sin asignar'}
                                </div>

                                <div class="delegation-controls">
                                    ${puedeDelegar ? `
                                    <div class="input-group input-group-sm">
                                        <select class="form-select select-delegar" id="select-delegar-${pedido.id_pedido}" style="border-radius: 6px 0 0 6px; font-size: 0.75rem; border-color: #e2e8f0; background-color: #f8fafc;">
                                            <option value="">Sin asignar</option>
                                            ${(window.AppState.sharedData.responsables || [])
                        .filter(r => {
                            const depto = (typeof r === 'object' ? r.departamento : '').toUpperCase();
                            return depto.includes('ALISTAMIENTO');
                        })
                        .map(r => {
                            const nome = typeof r === 'object' ? r.nombre : r;
                            return `<option value="${nome}" ${pedido.delegado_a === nome ? 'selected' : ''}>${nome}</option>`;
                        }).join('')}
                                        </select>
                                        <button class="btn btn-primary" onclick="AlmacenModule.delegarPedido('${pedido.id_pedido}')" style="border-radius: 0 6px 6px 0; padding: 0 12px; background: #4f46e5; border: none;">
                                            <i class="fas fa-user-plus" style="font-size: 0.8rem;"></i>
                                        </button>
                                    </div>
                                    ` : `
                                    <div class="text-muted" style="font-size: 0.75rem;">
                                        <i class="fas fa-user-circle me-1"></i> ${pedido.delegado_a || 'Sin asignar'}
                                    </div>
                                    `}
                                </div>
                            </div>
                            
                            <!-- Mensaje Solo Lectura para Comercial -->
                            ${currentUser?.rol === 'Comercial' ? '<div class="mt-2 text-center"><span class="badge bg-secondary text-white small" style="opacity:0.8"><i class="fas fa-eye"></i> Solo Lectura</span></div>' : ''}
                        </div>
                    </div>
                </div>
    `;
        });
        html += '</div>';
        container.innerHTML = html;
    },

    /**
     * Lógica de colores intuitivos según solicitud
     */
    getColorPorEstadoProporcional: function (alisado, enviado) {
        if (enviado === 100) return '#10b981'; // Verde: Todo enviado
        if (enviado > 0) return '#facc15';     // Amarillo: Envío parcial
        if (alisado === 100) return '#6366f1'; // Azul: Listo para enviar
        return '#f97316';                      // Naranja: Pendiente/Faltante
    },

    /**
     * Determina el color del badge según el estado
     */
    getColorEstado: function (estado) {
        switch (estado.toUpperCase()) {
            case 'PENDIENTE': return '#64748b';
            case 'EN ALISTAMIENTO': return '#6366f1';
            case 'COMPLETADO': return '#10b981';
            default: return '#94a3b8';
        }
    },

    /**
     * Abrir modal de checklist para un pedido específico
     */
    abrirModal: function (id_pedido) {
        const pedido = this.pedidosPendientes.find(p => p.id_pedido === id_pedido);
        if (!pedido) return;

        this.pedidoActual = JSON.parse(JSON.stringify(pedido)); // Clonar para no afectar el original
        // Reiniciar estado de visualización de ocultos
        this.mostrarOcultos = false;
        const toggle = document.getElementById('toggle-ver-ocultos');
        if (toggle) toggle.checked = false;

        document.getElementById('modal-alistamiento-titulo').innerText = `Alistamiento: ${pedido.id_pedido}`;
        document.getElementById('modal-alistamiento-cliente').innerText = `Cliente: ${pedido.cliente} `;

        this.renderizarProductosChecklist();
        this.actualizarProgresoVisual();

        document.getElementById('modalAlistamiento').style.display = 'flex';

        // MODO LECTURA: Si es Comercial, deshabilitar TODO dentro del modal
        const user = window.AppState?.user;
        const isReadOnly = user?.rol === 'Comercial';

        const modalContainer = document.getElementById('modalAlistamiento');
        const inputs = modalContainer.querySelectorAll('input, button:not(.btn-close):not(#btn-cerrar-modal)');

        if (isReadOnly) {
            // Deshabilitar controles de edición
            inputs.forEach(el => {
                // Permitir cerrar y escrolear, bloquear acciones
                if (!el.classList.contains('close') && el.id !== 'modal-cancelar') {
                    el.disabled = true;
                    el.style.opacity = '0.6';
                    el.style.pointerEvents = 'none';
                }
            });
            // Ocultar botón Guardar si existe y mostrar aviso
            const btnGuardar = document.getElementById('btn-guardar-alistamiento');
            if (btnGuardar) btnGuardar.style.display = 'none';
        } else {
            // Restaurar si se reutiliza el modal
            const btnGuardar = document.getElementById('btn-guardar-alistamiento');
            if (btnGuardar) btnGuardar.style.display = 'block';
        }
    },

    /**
     * Renderizar lista de productos con inputs de cantidad
     */
    renderizarProductosChecklist: function () {
        const container = document.getElementById('lista-productos-alistamiento');
        if (!container) return;

        let html = '';
        let itemsVisibles = 0;

        this.pedidoActual.productos.forEach((prod, index) => {
            if (prod.cant_lista === undefined) prod.cant_lista = 0;
            // Asegurar booleano
            if (prod.despachado === undefined) prod.despachado = false;

            // Lógica de Filtrado:
            // - Normal: Ocultar si está 100% alistado y despachado.
            // - Recuperación (mostrarOcultos): Mostrar todo
            const estaCompletamenteDespachado = prod.cant_lista >= prod.cantidad && prod.despachado;

            if (estaCompletamenteDespachado && !this.mostrarOcultos) {
                return; // Ocultar en modo normal
            }

            itemsVisibles++;
            const isCompletoAlisado = prod.cant_lista >= prod.cantidad;

            // Lógica de Estado Visual (Tri-estado)
            const isReadyToDispatch = isCompletoAlisado && !prod.despachado;

            // Colores Dinámicos
            let bgClass = '#f8fafc'; // Gris (Default/Disabled)
            let borderClass = '#e2e8f0';
            let iconHtml = '<i class="far fa-circle"></i> PENDIENTE';
            let labelStyle = 'color: #94a3b8;'; // Gray 400

            if (prod.despachado) {
                bgClass = '#dcfce7'; // Green 100
                borderClass = '#22c55e'; // Green 500
                iconHtml = '<i class="fas fa-check-circle"></i> DESPACHADO';
                labelStyle = 'color: #15803d;'; // Green 700
            } else if (isReadyToDispatch) {
                bgClass = '#fff7ed'; // Orange 50
                borderClass = '#fdba74'; // Orange 300
                iconHtml = '<i class="far fa-clock"></i> LISTO PARA ENVIAR';
                labelStyle = 'color: #ea580c;'; // Orange 600
            }

            // ID único para el checkbox
            const checkId = `check-despacho-${index}`;

            // Progress width for visual feedback within the card background or border
            const progress = (prod.cant_lista / prod.cantidad) * 100;
            const progressColor = progress >= 100 ? '#10b981' : '#6366f1';

            // Verificar permisos para eliminar (solo Andrés y Admins)
            const currentUser = window.AppState?.user;
            const puedeEliminar = (currentUser?.rol === 'Administración') ||
                (currentUser?.name && (
                    currentUser.name.toUpperCase().includes('ANDRES') ||
                    currentUser.name.toUpperCase().includes('ANDRÉS')
                ));

            html += `
            <div class="product-row-item p-4 mb-4 bg-white shadow-sm border-0 rounded-4 position-relative overflow-hidden" id="row-prod-${index}" 
                 style="transition: all 0.4s ease; transform: scale(1);">
                 
                <!-- Visual Progress Bar at Bottom -->
                <div style="position: absolute; bottom: 0; left: 0; height: 6px; width: ${progress}%; background: ${progressColor}; transition: width 0.3s ease;"></div>

                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div style="max-width: 60%;">
                        <span class="badge bg-light text-dark border fw-bold mb-1" style="font-size: 0.8rem; letter-spacing: 1px;">CÓDIGO: ${prod.codigo}</span>
                        <h6 class="text-muted mb-0 fw-normal" style="font-size: 0.8rem; line-height: 1.2;">${prod.descripcion}</h6>
                    </div>
                    <div class="d-flex align-items-start gap-2">
                        <div class="text-end">
                            <small class="text-uppercase text-muted fw-bold" style="font-size: 0.7rem; letter-spacing: 1px;">Solicitado</small>
                            <div class="fw-bold text-primary" style="font-size: 2.5rem; line-height: 1; letter-spacing: -1px;">${prod.cantidad}</div>
                        </div>
                        ${puedeEliminar && !prod.despachado ? `
                        <button class="btn btn-sm btn-outline-danger rounded-circle btn-eliminar-producto" 
                                onclick="event.stopPropagation(); AlmacenModule.eliminarProducto(${index})"
                                title="Eliminar producto del pedido"
                                style="width: 36px; height: 36px; padding: 0; display: flex; align-items: center; justify-content: center; z-index: 10; position: relative; background: white;">
                            <i class="fas fa-trash" style="font-size: 0.9rem;"></i>
                        </button>
                        ` : ''}
                    </div>
                </div>

                <!-- Big Input Control Area -->
                <div class="d-flex align-items-center justify-content-between bg-light rounded-4 p-2 mb-4 border inner-shadow">
                    <button class="btn btn-white shadow-sm rounded-circle d-flex align-items-center justify-content-center border-0" 
                        onclick="AlmacenModule.ajustarCantidad(${index}, -1, 'cant_lista')"
                        style="width: 60px; height: 60px; font-size: 1.5rem; color: #ef4444; transition: transform 0.1s;"
                        onmousedown="this.style.transform='scale(0.95)'" onmouseup="this.style.transform='scale(1)'">
                        <i class="fas fa-minus"></i>
                    </button>
                    
                    <div class="flex-grow-1 px-3 text-center">
                        <small class="text-uppercase text-muted fw-bold d-block mb-1" style="font-size: 0.65rem; letter-spacing: 0.5px;">Empacado</small>
                        <input type="number" class="form-control border-0 bg-transparent text-center fw-bold p-0" 
                            value="${prod.cant_lista}" 
                            onchange="AlmacenModule.cambiarCantidad(${index}, this.value, 'cant_lista')"
                            style="font-size: 2.5rem; color: #1e293b; height: auto; box-shadow: none;">
                    </div>

                    <button class="btn btn-white shadow-sm rounded-circle d-flex align-items-center justify-content-center border-0" 
                         onclick="AlmacenModule.ajustarCantidad(${index}, 1, 'cant_lista')"
                         style="width: 60px; height: 60px; font-size: 1.5rem; color: #10b981; transition: transform 0.1s;"
                         onmousedown="this.style.transform='scale(0.95)'" onmouseup="this.style.transform='scale(1)'">
                        <i class="fas fa-plus"></i>
                    </button>
                </div>

                <!-- Status Toggle Actions -->
                <div class="d-flex align-items-center justify-content-end gap-3 border-top pt-3">
                    <span class="text-muted small fw-bold ${isReadyToDispatch ? 'text-orange-500' : ''}" style="transition: color 0.3s; ${isReadyToDispatch ? 'color: #f97316;' : ''}">
                         ${isReadyToDispatch ? '<i class="fas fa-exclamation-circle me-1"></i> LISTO PARA CERRAR' : (prod.despachado ? '<i class="fas fa-check-circle me-1"></i> DESPACHADO' : 'PENDIENTE')}
                    </span>
                    
                    <div class="form-check form-switch custom-switch-lg">
                        <input class="form-check-input" type="checkbox" role="switch" id="${checkId}"
                            ${prod.despachado ? 'checked' : ''}
                            ${!isCompletoAlisado ? 'disabled' : ''}
                            onchange="AlmacenModule.toggleDespacho(${index}, this.checked)"
                            style="width: 3.5rem; height: 2rem; cursor: pointer;">
                    </div>
                </div>
            </div>`;
        });

        if (itemsVisibles === 0) {
            html = `
                <div class="text-center py-5">
                    <i class="fas fa-check-double fa-3x text-success mb-3"></i>
                    <h5 class="text-muted">¡Todo alistado y despachado!</h5>
                    <p class="small text-muted">Este pedido se cerrará automáticamente.</p>
                </div>
            `;
        }

        container.innerHTML = html;
    },

    /**
     * Alternar estado de despacho y guardar automáticamente
     * Si está completo (alistado=cantidad) y se despacha, iniciar fade-out
     */
    toggleDespacho: function (index, checked) {
        this.pedidoActual.productos[index].despachado = checked;

        // Efecto Sonoro/Háptico
        if (window.HapticFeedback) window.HapticFeedback.light();

        this.actualizarProgresoVisual();

        // Si se marca como despachado y estaba completamente alistado...
        const prod = this.pedidoActual.productos[index];
        if (checked && prod.cant_lista >= prod.cantidad) {
            // Si estamos viendo ocultos, NO ocultar (para permitir gestión), solo actualizar estado visual
            if (this.mostrarOcultos) {
                this.renderizarProductosChecklist();
            } else {
                // Modo normal: fade-out y desaparecer
                setTimeout(() => {
                    const row = document.getElementById(`row-prod-${index}`);
                    if (row) {
                        row.style.transform = 'translateX(50px)';
                        row.style.opacity = '0';
                        setTimeout(() => {
                            this.renderizarProductosChecklist();
                        }, 500);
                    } else {
                        this.renderizarProductosChecklist();
                    }
                }, 500);
            }
        } else {
            this.renderizarProductosChecklist();
        }
    },

    toggleOcultos: function (checked) {
        this.mostrarOcultos = checked;
        this.renderizarProductosChecklist();
    },

    /**
     * Ajustar cantidad con botones +/- genérico
     */
    ajustarCantidad: function (index, delta, campo) {
        if (campo === 'cant_enviada') return; // Deprecado, usar toggleDespacho

        let val = parseInt(this.pedidoActual.productos[index][campo]) || 0;
        let max = this.pedidoActual.productos[index].cantidad;

        val = Math.max(0, Math.min(max, val + delta));
        this.cambiarCantidad(index, val, campo);
    },

    /**
     * Cambiar cantidad manualmente genérico
     */
    cambiarCantidad: function (index, valor, campo) {
        if (campo === 'cant_enviada') return; // Deprecado

        let max = this.pedidoActual.productos[index].cantidad;
        let num = parseInt(valor) || 0;

        if (num < 0) num = 0;
        if (num > max) num = max;

        this.pedidoActual.productos[index][campo] = num;

        this.renderizarProductosChecklist();
        this.actualizarProgresoVisual();

        if (window.HapticFeedback) window.HapticFeedback.light();
    },

    /**
     * Calcular y actualizar barra de progreso visual en el modal
     */
    actualizarProgresoVisual: function () {
        let totalRequerido = 0;
        let totalListo = 0;
        let totalUnidadesDespachadas = 0;

        this.pedidoActual.productos.forEach(p => {
            const cantidad = parseFloat(p.cantidad) || 0;
            totalRequerido += cantidad;
            totalListo += parseInt(p.cant_lista) || 0;

            if (p.despachado) {
                totalUnidadesDespachadas += cantidad;
            }
        });

        const pctAlisado = totalRequerido > 0 ? Math.round((totalListo / totalRequerido) * 100) : 0;
        // AHORA: El progreso enviado se basa en VOLUMEN (unidades) igual que el alistado
        const pctEnviado = totalRequerido > 0 ? Math.round((totalUnidadesDespachadas / totalRequerido) * 100) : 0;

        // Actualizar barras en el modal
        const barAlisado = document.getElementById('modal-alisado-progress');
        const barEnviado = document.getElementById('modal-enviado-progress');

        if (barAlisado) {
            barAlisado.style.width = `${pctAlisado}% `;
            barAlisado.innerText = `Alistado: ${pctAlisado}% `;
            // ... efectos ...
            barAlisado.parentElement.classList.add('progress-modern');
            barAlisado.classList.add('progress-bar-shimmer');
            if (pctAlisado > 0) barAlisado.classList.add('progress-glow-indigo');
            else barAlisado.classList.remove('progress-glow-indigo');
        }
        if (barEnviado) {
            barEnviado.style.width = `${pctEnviado}% `;
            barEnviado.innerText = `Despachado: ${pctEnviado}% `;
            // ... efectos ...
            barEnviado.parentElement.classList.add('progress-modern');
            barEnviado.classList.add('progress-bar-shimmer');
            if (pctEnviado > 0) barEnviado.classList.add('progress-glow-emerald');
            else barEnviado.classList.remove('progress-glow-emerald');
        }
    },

    /**
     * Cerrar modal
     */
    cerrarModal: function () {
        document.getElementById('modalAlistamiento').style.display = 'none';
        this.pedidoActual = null;
    },

    /**
     * Guardar progreso en el backend y persistir en Sheets
     */
    guardarAlistamiento: async function () {
        if (!this.pedidoActual) return;

        let totalReq = 0;
        let totalLis = 0;
        let totalUnidadesDesp = 0;

        this.pedidoActual.productos.forEach(p => {
            const cantidad = parseFloat(p.cantidad) || 0;
            totalReq += cantidad;
            totalLis += parseInt(p.cant_lista) || 0;

            if (p.despachado) {
                totalUnidadesDesp += cantidad;
            }
        });

        const pctLis = totalReq > 0 ? Math.round((totalLis / totalReq) * 100) : 0;
        // Calculo basado en volumen
        const pctEnv = totalReq > 0 ? Math.round((totalUnidadesDesp / totalReq) * 100) : 0;

        // Determinar estado final para la UI
        let estado = 'EN ALISTAMIENTO';
        if (pctEnv === 100 && pctLis === 100) estado = 'DESPACHADO'; // Todo alistado y todo check despachado
        else if (pctEnv > 0) estado = 'DESPACHO PARCIAL';
        else if (pctLis === 100) estado = 'ALISTADO';
        else if (pctLis === 0) estado = 'PENDIENTE';

        const detalles = this.pedidoActual.productos.map(p => ({
            codigo: p.codigo,
            cant_lista: p.cant_lista,
            despachado: p.despachado // Enviamos el booleano
        }));

        try {
            mostrarLoading(true);
            const response = await fetch('/api/pedidos/actualizar-alistamiento', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_pedido: this.pedidoActual.id_pedido,
                    progreso: `${pctLis}% `,
                    progreso_despacho: `${pctEnv}% `,
                    estado: estado,
                    detalles: detalles
                })
            });

            const data = await response.json();
            if (data.success) {
                mostrarNotificacion('¡Seguimiento actualizado!', 'success');
                this.cerrarModal();
                this.cargarPedidos();
            } else {
                mostrarNotificacion(data.error || 'Error al actualizar', 'error');
            }
        } catch (error) {
            console.error('Error guardando:', error);
            mostrarNotificacion('Error de conexión', 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    /**
     * Eliminar un producto del pedido
     */
    eliminarProducto: async function (index) {
        console.log(`🗑️ Intentando eliminar producto en índice: ${index}`);
        if (!this.pedidoActual) {
            console.error('❌ No hay pedido actual');
            return;
        }

        const producto = this.pedidoActual.productos[index];
        if (!producto) {
            console.error('❌ Producto no encontrado en índice:', index);
            return;
        }

        // Verificar si ya fue despachado
        if (producto.despachado) {
            mostrarNotificacion('No se puede eliminar un producto que ya fue despachado', 'error');
            return;
        }

        // Confirmación
        const confirmar = await this.mostrarConfirmacion(
            'Eliminar Producto',
            `¿Estás seguro de eliminar <b>${producto.codigo} - ${producto.descripcion}</b> del pedido?<br><br>` +
            `<small class="text-muted">La cantidad (${producto.cantidad}) se devolverá automáticamente al inventario.</small>`
        );

        if (!confirmar) return;

        try {
            mostrarLoading(true);
            const response = await fetch('/api/pedidos/eliminar-producto', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_pedido: this.pedidoActual.id_pedido,
                    codigo: producto.codigo
                })
            });

            const data = await response.json();

            if (data.success) {
                mostrarNotificacion(data.message, 'success');

                // Si el pedido quedó vacío, cerrar modal y recargar
                if (data.pedido_vacio) {
                    this.cerrarModal();
                    this.cargarPedidos();
                } else {
                    // Eliminar del array local y re-renderizar
                    this.pedidoActual.productos.splice(index, 1);
                    this.renderizarProductosChecklist();
                    this.actualizarProgresoVisual();
                }
            } else {
                mostrarNotificacion(data.error || 'Error al eliminar producto', 'error');
            }
        } catch (error) {
            console.error('Error eliminando producto:', error);
            mostrarNotificacion('Error de conexión', 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    /**
     * Alternar el Modo TV (Pantalla completa, Fuentes grandes, Auto-refresco)
     */
    toggleModoTV: function () {
        this.isTVMode = !this.isTVMode;

        if (this.isTVMode) {
            console.log('📺 [Almacen] Activando Modo TV...');
            document.body.classList.add('tv-mode');

            // Salir con ESCAPE
            this._escHandler = (e) => {
                if (e.key === 'Escape' && this.isTVMode) {
                    this.toggleModoTV();
                }
            };
            window.addEventListener('keydown', this._escHandler);

            // Intentar poner en pantalla completa si el navegador lo permite
            try {
                if (document.documentElement.requestFullscreen) {
                    document.documentElement.requestFullscreen();
                }
            } catch (e) {
                console.warn('Pantalla completa no soportada o bloqueada:', e);
            }

            // Agregar botón de salida flotante si no existe
            if (!document.querySelector('.btn-exit-tv')) {
                const btnExit = document.createElement('button');
                btnExit.className = 'btn-exit-tv';
                btnExit.innerHTML = '<i class="fas fa-times"></i> Salir de Modo TV';
                btnExit.onclick = () => this.toggleModoTV();
                document.body.appendChild(btnExit);
            }

            // Iniciar intervalo de refresco automático (cada 30 segundos)
            this.tvInterval = setInterval(() => {
                // Solo refrescar si NO hay un modal abierto (para evitar interrumpir al usuario)
                const modal = document.getElementById('modalAlistamiento');
                if (modal && modal.style.display !== 'flex' && modal.style.display !== 'block') {
                    console.log('📺 [Almacen] Refresco automático de Modo TV...');
                    this.cargarPedidos(false);
                }
            }, 30000);

            mostrarNotificacion('Modo TV Activado: Auto-refresco cada 30s', 'info');

            // Iniciar auto-scroll
            this.iniciarAutoScroll();
        } else {
            console.log('📺 [Almacen] Desactivando Modo TV...');
            document.body.classList.remove('tv-mode');

            // Remover listener de ESC
            if (this._escHandler) {
                window.removeEventListener('keydown', this._escHandler);
            }

            // Salir de pantalla completa
            try {
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                }
            } catch (e) { }

            // Limpiar botón de salida
            document.querySelector('.btn-exit-tv')?.remove();

            // Detener el auto-refresco
            if (this.tvInterval) {
                clearInterval(this.tvInterval);
                this.tvInterval = null;
            }

            // Detener auto-scroll
            this.detenerAutoScroll();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    },

    /**
     * Lógica de Auto-Scroll para Modo TV (Airport Effect)
     */
    iniciarAutoScroll: function () {
        this.detenerAutoScroll();
        if (!this.isTVMode) return;

        console.log('📜 [Almacen] Configurando Auto-Scroll continuo...');

        // Variables de control
        let lastPausePosition = 0;
        const pixelsPerPause = 960; // ~3 filas de tarjetas (320px cada una)
        const scrollSpeed = 5; // Pixels por frame (más rápido que antes)
        const pauseDuration = 8000; // 8 segundos de pausa

        // Guardar el timeout para poder cancelarlo
        this.scrollTimeout = setTimeout(() => {
            this.scrollInterval = setInterval(() => {
                const modalAbierto = document.getElementById('modalAlistamiento')?.style.display === 'flex' ||
                    document.getElementById('modalAlistamiento')?.style.display === 'block';

                if (modalAbierto || !this.isTVMode) return;

                const currentScroll = window.pageYOffset || document.documentElement.scrollTop;
                const maxScroll = document.documentElement.scrollHeight - window.innerHeight;

                if (maxScroll <= 10) return;

                // Verificar si hemos scrolleado suficiente para hacer una pausa
                if (currentScroll - lastPausePosition >= pixelsPerPause && currentScroll < maxScroll - 5) {
                    console.log('📜 [Almacen] Pausa para leer (8s)...');
                    lastPausePosition = currentScroll;
                    this.detenerAutoScroll();

                    // Pausar 8 segundos y luego continuar
                    this.scrollTimeout = setTimeout(() => {
                        if (this.isTVMode) this.iniciarAutoScroll();
                    }, pauseDuration);
                    return;
                }

                // Si llegamos al final, volver arriba
                if (currentScroll >= maxScroll - 5) {
                    console.log('📜 [Almacen] Fin alcanzado, volviendo arriba...');
                    this.detenerAutoScroll();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                    lastPausePosition = 0;

                    this.scrollTimeout = setTimeout(() => {
                        if (this.isTVMode) this.iniciarAutoScroll();
                    }, pauseDuration);
                    return;
                }

                // Scroll continuo suave
                window.scrollBy(0, scrollSpeed);
            }, 30); // 30ms entre frames
        }, 2000);
    },

    /**
     * Detener el auto-scroll
     */
    detenerAutoScroll: function () {
        if (this.scrollInterval) {
            clearInterval(this.scrollInterval);
            this.scrollInterval = null;
        }
        if (this.scrollTimeout) {
            clearTimeout(this.scrollTimeout);
            this.scrollTimeout = null;
        }
    },

    /**
     * Desactivar procesos del módulo al salir de la página
     */
    desactivar: function () {
        console.log('🔌 [Almacen] Desactivando procesos de fondo...');
        if (this.isTVMode) {
            this.toggleModoTV(); // Apaga el modo TV limpiamente
        }
        this.detenerAutoRefresco();
        this.detenerAutoScroll();
    },

    /**
     * Delegar un pedido a una colaboradora
     */
    delegarPedido: async function (id_pedido) {
        const select = document.getElementById(`select-delegar-${id_pedido}`);
        if (!select) return;

        const colaboradora = select.value;
        const title = colaboradora ? 'Confirmar Asignación' : 'Quitar Asignación';
        const confirmMsg = colaboradora
            ? `¿Deseas asignar el pedido <b>${id_pedido}</b> a <b>${colaboradora}</b>?`
            : `¿Deseas quitar la asignación del pedido <b>${id_pedido}</b>?`;

        const confirmar = await this.mostrarConfirmacion(title, confirmMsg);
        if (!confirmar) return;

        try {
            mostrarLoading(true);
            const response = await fetch('/api/pedidos/delegar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_pedido: id_pedido,
                    colaboradora: colaboradora
                })
            });

            const data = await response.json();
            if (data.success) {
                mostrarNotificacion(`Pedido ${id_pedido} actualizado`, 'success');
                this.cargarPedidos();
            } else {
                mostrarNotificacion(data.error || 'Error al delegar', 'error');
            }
        } catch (error) {
            console.error('Error delegando:', error);
            mostrarNotificacion('Error de conexión', 'error');
        } finally {
            mostrarLoading(false);
        }
    },

    /**
     * Mostrar confirmación personalizada estilo Pedidos
     */
    mostrarConfirmacion: function (titulo, mensaje) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.style.zIndex = '10001';
            modal.innerHTML = `
    <div class="modal-content confirmation-modal-pro" style = "max-width: 420px; border: none; overflow: hidden; background-color: #ffffff; border-radius: 12px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);">
                    <div class="modal-header" style="background: white; border-bottom: 1px solid #e5e7eb; padding: 20px 25px;">
                        <h3 style="color: #111827; margin: 0; font-size: 1.15rem; font-weight: 700;">
                            <i class="fas fa-question-circle" style="color: #6366f1; margin-right: 12px;"></i> ${titulo}
                        </h3>
                    </div>
                    <div class="modal-body" style="padding: 25px; color: #4b5563; font-size: 0.95rem; line-height: 1.5; background-color: #ffffff;">
                        <p style="margin: 0;">${mensaje}</p>
                    </div>
                    <div class="modal-footer" style="background: #f9fafb; padding: 15px 25px; border-top: 1px solid #e5e7eb; display: flex; gap: 10px; justify-content: flex-end;">
                        <button class="btn btn-sm btn-secondary" id="modal-cancelar" style="background: white; border: 1px solid #d1d5db; color: #4b5563; padding: 7px 15px; font-weight: 600; border-radius: 8px;">
                            Cancelar
                        </button>
                        <button class="btn btn-sm btn-primary" id="modal-confirmar" style="background: #4f46e5; color: white; border: none; padding: 7px 20px; font-weight: 600; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.4);">
                            Confirmar
                        </button>
                    </div>
                </div>
    `;

            document.body.appendChild(modal);

            document.getElementById('modal-confirmar').addEventListener('click', () => {
                document.body.removeChild(modal);
                resolve(true);
            });

            document.getElementById('modal-cancelar').addEventListener('click', () => {
                document.body.removeChild(modal);
                resolve(false);
            });

            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    document.body.removeChild(modal);
                    resolve(false);
                }
            });
        });
    },

    /**
     * Iniciar refresco automático cada 60 segundos si la pestaña está activa
     */
    iniciarAutoRefresco: function () {
        if (this.autoRefreshInterval) return;

        console.log('⏱️ [Almacen] Iniciando poll background (15s)...');
        this.autoRefreshInterval = setInterval(() => {
            const paginaActual = window.AppState?.paginaActual;
            const modalAbierto = document.getElementById('modalAlistamiento')?.style.display === 'flex';

            // Verificación robusta: página actual O existencia del contenedor
            const esPaginaAlmacen = paginaActual === 'almacen' || !!document.getElementById('almacen-container');

            if (esPaginaAlmacen && !this.isTVMode && !modalAbierto) {
                console.log('🔄 [Almacen] Auto-refresco de fondo...');
                this.cargarPedidos(false);
            }
        }, 15000); // 15s poll
    },

    /**
     * Detener el refresco automático
     */
    detenerAutoRefresco: function () {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }
};

// Exportación global para app.js
window.AlmacenModule = AlmacenModule;
window.initAlmacen = () => AlmacenModule.inicializar();
