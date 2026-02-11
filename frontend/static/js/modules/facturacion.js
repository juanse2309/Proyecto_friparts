// ============================================
// facturacion.js - Lógica de Exportación World Office - NAMESPACED
// ============================================

const ModuloFacturacion = {

    // Estado local
    pedidosPendientes: [],
    pedidosSeleccionados: new Set(),

    /**
     * Inicializar módulo
     */
    inicializar: function () {
        console.log('🔧 [Exportación WO] Inicializando...');
        this.cargarPedidosPendientes();
        console.log('✅ [Exportación WO] Módulo inicializado');
    },

    /**
     * Cargar pedidos pendientes desde el backend
     */
    cargarPedidosPendientes: async function () {
        try {
            const tbody = document.getElementById('tbody-pedidos-exportar');
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center py-5 text-muted"><i class="fas fa-spinner fa-spin fa-2x mb-2"></i><br>Cargando pedidos pendientes...</td></tr>';

            const response = await fetch('/api/facturacion/pedidos-pendientes');
            const data = await response.json();

            if (data.success) {
                this.pedidosPendientes = data.pedidos;
                this.pedidosSeleccionados.clear();
                this.actualizarContadorSeleccion();
                this.renderizarTablaExportar();

                // Actualizar check all
                const checkAll = document.getElementById('check-all-wo');
                if (checkAll) checkAll.checked = false;

                if (this.pedidosPendientes.length === 0) {
                    mostrarNotificacion('No hay pedidos pendientes', 'info');
                }
            } else {
                if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Error: ${data.error}</td></tr>`;
            }
        } catch (error) {
            console.error('Error cargando pedidos pendientes:', error);
            const tbody = document.getElementById('tbody-pedidos-exportar');
            if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Error de conexión</td></tr>`;
        }
    },

    /**
     * Renderizar tabla de pedidos
     */
    renderizarTablaExportar: function () {
        const tbody = document.getElementById('tbody-pedidos-exportar');
        if (!tbody) return;

        if (this.pedidosPendientes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-5 text-muted"><i class="fas fa-inbox fa-3x mb-3 text-light"></i><br>No hay pedidos en estado PENDIENTE</td></tr>';
            return;
        }

        tbody.innerHTML = this.pedidosPendientes.map(p => `
            <tr onclick="ModuloFacturacion.toggleRowClick('${p.id}', event)" style="cursor: pointer;">
                <td class="text-center">
                    <div class="form-check d-flex justify-content-center">
                        <input class="form-check-input check-pedido-wo" type="checkbox" value="${p.id}" 
                               ${this.pedidosSeleccionados.has(p.id) ? 'checked' : ''}
                               onchange="ModuloFacturacion.togglePedido('${p.id}'); event.stopPropagation();">
                    </div>
                </td>
                <td>
                    <span class="fw-bold text-primary">${p.id}</span>
                </td>
                <td>
                    <div class="fw-bold text-dark">${p.cliente}</div>
                    <small class="text-muted"><i class="fas fa-id-card me-1"></i>${p.nit || 'Sin NIT'}</small>
                </td>
                <td>${p.fecha}</td>
                <td>${p.vendedor}</td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border rounded-pill px-3">${p.items_count}</span>
                </td>
                <td class="text-end fw-bold text-success pe-4">$ ${formatNumber(p.total)}</td>
            </tr>
        `).join('');
    },

    /**
     * Manejar click en la fila para seleccionar
     */
    toggleRowClick: function (id, event) {
        // Evitar doble toggle si se hace click en el checkbox directamente (ya manejado por stopPropagation)
        const checkbox = document.querySelector(`.check-pedido-wo[value="${id}"]`);
        if (checkbox) {
            checkbox.checked = !checkbox.checked;
            this.togglePedido(id);
        }
    },

    /**
     * Toggle selección individual
     */
    togglePedido: function (id) {
        if (this.pedidosSeleccionados.has(id)) {
            this.pedidosSeleccionados.delete(id);
        } else {
            this.pedidosSeleccionados.add(id);
        }
        this.actualizarCheckAll();
        this.actualizarContadorSeleccion();
    },

    /**
     * Seleccionar/Deseleccionar todos
     */
    toggleSelectAll: function (checkbox) {
        const checkboxes = document.querySelectorAll('.check-pedido-wo');
        checkboxes.forEach(cb => {
            cb.checked = checkbox.checked;
            if (checkbox.checked) {
                this.pedidosSeleccionados.add(cb.value);
            } else {
                this.pedidosSeleccionados.delete(cb.value);
            }
        });
        this.actualizarContadorSeleccion();
    },

    /**
     * Actualizar estado del checkbox maestro
     */
    actualizarCheckAll: function () {
        const checkAll = document.getElementById('check-all-wo');
        const checkboxes = document.querySelectorAll('.check-pedido-wo');
        if (checkAll) {
            checkAll.checked = checkboxes.length > 0 && checkboxes.length === this.pedidosSeleccionados.size;
        }
    },

    /**
     * Actualizar contador visual de selección
     */
    actualizarContadorSeleccion: function () {
        const countDiv = document.getElementById('wo-selection-count');
        const countSpan = document.getElementById('wo-count-val');

        if (countDiv && countSpan) {
            const count = this.pedidosSeleccionados.size;
            countSpan.textContent = count;
            countDiv.style.display = count > 0 ? 'block' : 'none';
        }
    },

    /**
     * Iniciar proceso de exportación
     */
    iniciarExportacion: async function () {
        if (this.pedidosSeleccionados.size === 0) {
            // Usar SweetAlert si está disponible, sino alert nativo
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Sin selección',
                    text: 'Seleccione al menos un pedido para exportar',
                    confirmButtonColor: '#3085d6'
                });
            } else {
                alert('Seleccione al menos un pedido para exportar');
            }
            return;
        }

        // Verificar SweetAlert
        if (typeof Swal === 'undefined') {
            alert('Error: SweetAlert2 no está cargado. Recargue la página.');
            return;
        }

        const { value: consecutivo } = await Swal.fire({
            title: 'Exportar a World Office',
            text: 'Ingrese el número de documento inicial (Consecutivo):',
            input: 'number',
            inputValue: 9430,
            showCancelButton: true,
            confirmButtonText: 'Generar Excel',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#10b981',
            cancelButtonColor: '#d33',
            showLoaderOnConfirm: true,
            preConfirm: (consecutivo) => {
                if (!consecutivo) {
                    Swal.showValidationMessage('El consecutivo es requerido');
                }
                return consecutivo;
            }
        });

        if (consecutivo) {
            try {
                mostrarLoading(true);

                // Convertir Set a Array
                const pedidosArray = Array.from(this.pedidosSeleccionados);

                const response = await fetch('/api/exportar/world-office', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        consecutivo: consecutivo,
                        pedidos: pedidosArray
                    })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `Export_WO_${new Date().toISOString().slice(0, 10)}.xlsx`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);

                    Swal.fire({
                        icon: 'success',
                        title: '¡Archivo Generado!',
                        text: 'La descarga comenzará automáticamente.',
                        timer: 2000,
                        showConfirmButton: false
                    });
                } else {
                    const data = await response.json();
                    throw new Error(data.error || 'Error al generar archivo');
                }
            } catch (error) {
                console.error('Error exportación:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: error.message
                });
            } finally {
                mostrarLoading(false);
            }
        }
    }
};

// Exportar
window.ModuloFacturacion = ModuloFacturacion;
window.initFacturacion = () => ModuloFacturacion.inicializar();
