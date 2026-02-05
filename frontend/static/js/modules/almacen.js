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
    isTVMode: false,

    /**
     * Inicializar módulo
     */
    inicializar: function () {
        console.log('🔧 [Almacen] Inicializando módulo...');
        this.cargarPedidos();
        this.iniciarAutoRefresco();

        // Listener para refrescar automáticamente al entrar a la página
        document.querySelector('[data-page="almacen"]')?.addEventListener('click', () => {
            this.cargarPedidos();
        });
    },

    /**
     * Cargar pedidos pendientes desde la API
     */
    cargarPedidos: async function (showLoading = true) {
        try {
            if (showLoading) mostrarLoading(true);

            // CRÍTICO: Si window.AppState.user no está listo, intentar recuperarlo de AuthModule o SessionStorage
            let user = window.AppState?.user;
            if (!user || (!user.name && !user.nombre)) {
                const sessionUser = sessionStorage.getItem('friparts_user');
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

            const response = await fetch(url, {
                cache: 'no-store', // Forzar al navegador a no usar cache
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            });
            const data = await response.json();

            if (data.success) {
                this.pedidosPendientes = data.pedidos;
                this.renderizarTarjetas();
            } else {
                console.error('Error al cargar pedidos:', data.error);
                if (showLoading) mostrarNotificacion('Error al cargar pedidos pendientes', 'error');
            }
        } catch (error) {
            console.error('Error fetch pedidos:', error);
            if (showLoading) mostrarNotificacion('Error de conexión con el servidor', 'error');
        } finally {
            if (showLoading) mostrarLoading(false);
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
        this.pedidosPendientes.forEach(pedido => {
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
                                <span class="fw-bold text-primary" style="font-size: 0.9rem; white-space: nowrap; letter-spacing: -0.5px; overflow: hidden; text-overflow: ellipsis; max-width: 120px;">${pedido.id_pedido}</span>
                                <div class="d-flex flex-wrap gap-1 align-items-center justify-content-end" style="flex: 1;">
                                    ${esParaMi ? '<span class="badge bg-info" style="font-size: 0.6rem; padding: 4px 6px; font-weight: 700; border-radius: 4px;"><i class="fas fa-user-check me-1"></i>MÍO</span>' : ''}
                                    <span class="badge" style="background: ${colorStatus}; font-size: 0.6rem; padding: 4px 6px; text-transform: uppercase; font-weight: 700; border-radius: 4px;">${pedido.estado}</span>
                                </div>
                            </div>
                        </div>
                        <div class="card-body" style="padding: 15px; flex: 1; display: flex; flex-direction: column;">
                            <h6 class="card-title fw-bold mb-1" style="color: #1e293b; cursor: pointer; font-size: 0.85rem; line-height: 1.3; margin-bottom: 8px !important;" onclick="AlmacenModule.abrirModal('${pedido.id_pedido}')">${pedido.cliente}</h6>
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

                            ${puedeDelegar ? `
                            <div class="mt-3 pt-3 border-top" style="border-top: 1px dashed #e2e8f0 !important;">
                                <label class="small fw-bold text-muted mb-2 d-block text-uppercase" style="letter-spacing: 0.5px; font-size: 0.6rem; opacity: 0.7;">Delegar Alistamiento</label>
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
                            </div>
                            ` : ''}
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

        this.pedidoActual = JSON.parse(JSON.stringify(pedido)); // Clonar para no afectar el original hasta guardar

        document.getElementById('modal-alistamiento-titulo').innerText = `Alistamiento: ${pedido.id_pedido} `;
        document.getElementById('modal-alistamiento-cliente').innerText = `Cliente: ${pedido.cliente} `;

        this.renderizarProductosChecklist();
        this.actualizarProgresoVisual();

        document.getElementById('modalAlistamiento').style.display = 'flex';
    },

    /**
     * Renderizar lista de productos con inputs de cantidad
     */
    renderizarProductosChecklist: function () {
        const container = document.getElementById('lista-productos-alistamiento');
        if (!container) return;

        let html = '';
        this.pedidoActual.productos.forEach((prod, index) => {
            if (prod.cant_lista === undefined) prod.cant_lista = 0;
            if (prod.cant_enviada === undefined) prod.cant_enviada = 0;

            const isCompletoAlisado = prod.cant_lista == prod.cantidad;
            const isCompletoEnviado = prod.cant_enviada == prod.cantidad;

            html += `
    <div class="p-3 mb-3 bg-white border rounded shadow-sm">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <div>
                            <div class="fw-bold" style="color: #1e293b; font-size: 1.1rem;">${prod.codigo}</div>
                            <div class="text-muted small">${prod.descripcion}</div>
                        </div>
                        <div class="text-end">
                            <span class="badge" style="font-size: 1.1rem; background-color: #fef08a; color: #854d0e; border: 1px solid #fde047; padding: 5px 12px; border-radius: 8px;">
                                <i class="fas fa-list-ol me-1"></i> Cantidad: ${prod.cantidad}
                            </span>
                        </div>
                    </div>
                    
                    <div class="row g-2">
                        <!-- Control de Alistamiento (Caja) -->
                        <div class="col-6">
                            <div class="p-2 rounded" style="background: #f0f7ff; border: 1px solid #dbeafe;">
                                <label class="small fw-bold text-primary mb-1 d-block"><i class="fas fa-box"></i> Alistado</label>
                                <div class="input-group input-group-sm">
                                    <button class="btn btn-white border" type="button" onclick="AlmacenModule.ajustarCantidad(${index}, -1, 'cant_lista')">-</button>
                                    <input type="number" class="form-control text-center fw-bold" 
                                        value="${prod.cant_lista}" 
                                        onchange="AlmacenModule.cambiarCantidad(${index}, this.value, 'cant_lista')"
                                        style="font-size: 1rem; border-color: #6366f1;">
                                    <button class="btn btn-white border" type="button" onclick="AlmacenModule.ajustarCantidad(${index}, 1, 'cant_lista')">+</button>
                                </div>
                            </div>
                        </div>

                        <!-- Control de Despacho (Camion) -->
                        <div class="col-6">
                            <div class="p-2 rounded ${prod.cant_lista === 0 ? 'opacity-50' : ''}" 
                                style="background: #f0fdf4; border: 1px solid #dcfce7; transition: opacity 0.3s;">
                                <label class="small fw-bold text-success mb-1 d-block"><i class="fas fa-truck"></i> Enviado</label>
                                <div class="input-group input-group-sm">
                                    <button class="btn btn-white border" type="button" 
                                        ${prod.cant_lista === 0 ? 'disabled' : ''}
                                        onclick="AlmacenModule.ajustarCantidad(${index}, -1, 'cant_enviada')">-</button>
                                    <input type="number" class="form-control text-center fw-bold" 
                                        value="${prod.cant_enviada}" 
                                        ${prod.cant_lista === 0 ? 'disabled' : ''}
                                        onchange="AlmacenModule.cambiarCantidad(${index}, this.value, 'cant_enviada')"
                                        style="font-size: 1rem; border-color: #10b981;">
                                    <button class="btn btn-white border" type="button" 
                                        ${prod.cant_lista === 0 ? 'disabled' : ''}
                                        onclick="AlmacenModule.ajustarCantidad(${index}, 1, 'cant_enviada')">+</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
    `;
        });
        container.innerHTML = html;
    },

    /**
     * Ajustar cantidad con botones +/- genérico para ambos estados
     */
    ajustarCantidad: function (index, delta, campo) {
        let val = parseInt(this.pedidoActual.productos[index][campo]) || 0;
        let max = this.pedidoActual.productos[index].cantidad;

        // Validación: Despacho no puede superar al Alistamiento
        if (campo === 'cant_enviada') {
            max = this.pedidoActual.productos[index].cant_lista;
        }

        val = Math.max(0, Math.min(max, val + delta));
        this.cambiarCantidad(index, val, campo);
    },

    /**
     * Cambiar cantidad manualmente genérico
     */
    cambiarCantidad: function (index, valor, campo) {
        let max = this.pedidoActual.productos[index].cantidad;

        // Validación: Despacho no puede superar al Alistamiento
        if (campo === 'cant_enviada') {
            max = this.pedidoActual.productos[index].cant_lista;
        }

        let num = parseInt(valor) || 0;
        if (num < 0) num = 0;
        if (num > max) num = max;

        this.pedidoActual.productos[index][campo] = num;

        // Si bajamos el alistamiento por debajo del despacho, bajamos el despacho automáticamente
        if (campo === 'cant_lista' && this.pedidoActual.productos[index].cant_enviada > num) {
            this.pedidoActual.productos[index].cant_enviada = num;
        }

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
        let totalEnviado = 0;

        this.pedidoActual.productos.forEach(p => {
            totalRequerido += parseFloat(p.cantidad) || 0;
            totalListo += parseInt(p.cant_lista) || 0;
            totalEnviado += parseInt(p.cant_enviada) || 0;
        });

        const pctAlisado = totalRequerido > 0 ? Math.round((totalListo / totalRequerido) * 100) : 0;
        const pctEnviado = totalRequerido > 0 ? Math.round((totalEnviado / totalRequerido) * 100) : 0;

        // Actualizar barras en el modal
        const barAlisado = document.getElementById('modal-alisado-progress');
        const barEnviado = document.getElementById('modal-enviado-progress');

        if (barAlisado) {
            barAlisado.style.width = `${pctAlisado}% `;
            barAlisado.innerText = `Alistado: ${pctAlisado}% `;

            // Añadir efectos dinámicos
            barAlisado.parentElement.classList.add('progress-modern');
            barAlisado.classList.add('progress-bar-shimmer');
            if (pctAlisado > 0) barAlisado.classList.add('progress-glow-indigo');
            else barAlisado.classList.remove('progress-glow-indigo');
        }
        if (barEnviado) {
            barEnviado.style.width = `${pctEnviado}% `;
            barEnviado.innerText = `Enviado: ${pctEnviado}% `;

            // Añadir efectos dinámicos
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
        let totalEnv = 0;

        this.pedidoActual.productos.forEach(p => {
            totalReq += parseFloat(p.cantidad) || 0;
            totalLis += parseInt(p.cant_lista) || 0;
            totalEnv += parseInt(p.cant_enviada) || 0;
        });

        const pctLis = totalReq > 0 ? Math.round((totalLis / totalReq) * 100) : 0;
        const pctEnv = totalReq > 0 ? Math.round((totalEnv / totalReq) * 100) : 0;

        // Determinar estado final para la UI
        let estado = 'EN ALISTAMIENTO';
        if (pctEnv === 100) estado = 'DESPACHADO';
        else if (pctEnv > 0) estado = 'DESPACHO PARCIAL';
        else if (pctLis === 100) estado = 'ALISTADO';
        else if (pctLis === 0) estado = 'PENDIENTE';

        const detalles = this.pedidoActual.productos.map(p => ({
            codigo: p.codigo,
            cant_lista: p.cant_lista,
            cant_enviada: p.cant_enviada
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
     * Alternar el Modo TV (Pantalla completa, Fuentes grandes, Auto-refresco)
     */
    toggleModoTV: function () {
        this.isTVMode = !this.isTVMode;

        if (this.isTVMode) {
            console.log('📺 [Almacen] Activando Modo TV...');
            document.body.classList.add('tv-mode');

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
        } else {
            console.log('📺 [Almacen] Desactivando Modo TV...');
            document.body.classList.remove('tv-mode');

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
        }
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

            if (paginaActual === 'almacen' && !this.isTVMode && !modalAbierto) {
                console.log('🔄 [Almacen] Auto-refresco de fondo...');
                this.cargarPedidos(false);
            }
        }, 15000);
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
