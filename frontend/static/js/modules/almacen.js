/**
 * Módulo de Gestión de Almacén (Alistamiento)
 * Desarrollado para FriParts por Antigravity
 * Soporta alistamiento parcial por cantidad.
 */

const AlmacenModule = {
    pedidosPendientes: [],
    pedidoActual: null,
    tvInterval: null,
    isTVMode: false,

    /**
     * Inicializar módulo
     */
    inicializar: function () {
        console.log('🔧 [Almacen] Inicializando módulo...');
        this.cargarPedidos();

        // Listener para refrescar automáticamente al entrar a la página
        document.querySelector('[data-page="almacen"]')?.addEventListener('click', () => {
            this.cargarPedidos();
        });
    },

    /**
     * Cargar pedidos pendientes desde la API
     */
    cargarPedidos: async function () {
        try {
            mostrarLoading(true);
            const response = await fetch('/api/pedidos/pendientes');
            const data = await response.json();

            if (data.success) {
                this.pedidosPendientes = data.pedidos;
                this.renderizarTarjetas();
            } else {
                console.error('Error al cargar pedidos:', data.error);
                mostrarNotificacion('Error al cargar pedidos pendientes', 'error');
            }
        } catch (error) {
            console.error('Error fetch pedidos:', error);
            mostrarNotificacion('Error de conexión con el servidor', 'error');
        } finally {
            mostrarLoading(false);
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

            html += `
                <div class="col-md-6 col-lg-4">
                    <div class="card h-100 shadow-sm border-0" onclick="AlmacenModule.abrirModal('${pedido.id_pedido}')" 
                        style="cursor: pointer; transition: transform 0.2s; border-radius: 12px; overflow: hidden; border-left: 5px solid ${colorStatus} !important;">
                        <div style="background: #f8fafc; padding: 15px; border-bottom: 1px solid #edf2f7;">
                            <div class="d-flex justify-content-between align-items-center">
                                <span class="fw-bold text-primary" style="font-size: 1.1rem;">${pedido.id_pedido}</span>
                                <span class="badge" style="background: ${colorStatus}; font-size: 0.75rem;">${pedido.estado}</span>
                            </div>
                        </div>
                        <div class="card-body" style="padding: 15px;">
                            <h6 class="card-title fw-bold mb-1" style="color: #1e293b;">${pedido.cliente}</h6>
                            <p class="text-muted small mb-3"><i class="fas fa-calendar-alt me-1"></i> ${pedido.fecha} | <i class="fas fa-user me-1"></i> ${pedido.vendedor}</p>
                            
                            <!-- Barra Doble de Progreso -->
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small fw-bold text-muted"><i class="fas fa-box me-1"></i> Alistado</span>
                                    <span class="small fw-bold" style="color: #6366f1;">${progresoAlisado}%</span>
                                </div>
                                <div class="progress" style="height: 6px; border-radius: 3px; background: #e2e8f0; margin-bottom: 8px;">
                                    <div class="progress-bar" role="progressbar" style="width: ${progresoAlisado}%; background: #6366f1;" 
                                        aria-valuenow="${progresoAlisado}" aria-valuemin="0" aria-valuemax="100"></div>
                                </div>

                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small fw-bold text-muted"><i class="fas fa-truck me-1"></i> Despachado</span>
                                    <span class="small fw-bold" style="color: #10b981;">${progresoEnviado}%</span>
                                </div>
                                <div class="progress" style="height: 6px; border-radius: 3px; background: #e2e8f0;">
                                    <div class="progress-bar" role="progressbar" style="width: ${progresoEnviado}%; background: #10b981;" 
                                        aria-valuenow="${progresoEnviado}" aria-valuemin="0" aria-valuemax="100"></div>
                                </div>
                            </div>
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

        document.getElementById('modal-alistamiento-titulo').innerText = `Alistamiento: ${pedido.id_pedido}`;
        document.getElementById('modal-alistamiento-cliente').innerText = `Cliente: ${pedido.cliente}`;

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
     * Marcar un item como completamente listo
     */
    marcarCompleto: function (index) {
        this.cambiarCantidad(index, this.pedidoActual.productos[index].cantidad);
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
            barAlisado.style.width = `${pctAlisado}%`;
            barAlisado.innerText = `Alistado: ${pctAlisado}%`;
        }
        if (barEnviado) {
            barEnviado.style.width = `${pctEnviado}%`;
            barEnviado.innerText = `Enviado: ${pctEnviado}%`;
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
                    progreso: `${pctLis}%`,
                    progreso_despacho: `${pctEnv}%`,
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
                    this.cargarPedidos();
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
    }
};

// Auto-inicializar cuando el script cargue
document.addEventListener('DOMContentLoaded', () => {
    // Solo inicializar si estamos en la app principal
    if (typeof AppState !== 'undefined') {
        AlmacenModule.inicializar();
    }
});
