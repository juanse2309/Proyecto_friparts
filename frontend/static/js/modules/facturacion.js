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
    /**
     * Iniciar proceso de exportación (V2 con Preview)
     */
    abrirPreviewWO: function () {
        const ids = Array.from(this.pedidosSeleccionados);

        if (ids.length === 0) {
            // Si no hay selección, preguntar si exportar todo
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    title: '¿Exportar todo?',
                    text: "No ha seleccionado pedidos específicos. ¿Desea exportar TODOS los pedidos pendientes?",
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonColor: '#3085d6',
                    cancelButtonColor: '#d33',
                    confirmButtonText: 'Sí, exportar todo'
                }).then((result) => {
                    if (result.isConfirmed) {
                        this.mostrarModalPreview([]); // Array vacío = Todo
                    }
                });
            } else {
                if (confirm("No ha seleccionado pedidos. ¿Desea exportar TODOS los pendientes?")) {
                    this.mostrarModalPreview([]);
                }
            }
        } else {
            this.mostrarModalPreview(ids);
        }
    },

    mostrarModalPreview: function (ids) {
        const modal = document.getElementById('modal-preview-wo');
        if (modal) {
            modal.style.display = 'flex'; // Usar FLEX para mantener el centrado
            this.cargarPreviewWO(ids);

            // Guardar IDs para la descarga final
            modal.dataset.idsToExport = JSON.stringify(ids);

            // Helpers para asignar eventos (evita cloneNode que puede fallar con referencias)
            // YA NO ES NECESARIO: Se asignó onclick directamente en HTML para mayor robustez
        }
    },

    cerrarPreviewWO: function () {
        const modal = document.getElementById('modal-preview-wo');
        if (modal) {
            modal.style.display = 'none';
            modal.dataset.idsToExport = ''; // Limpiar
            const tbody = document.querySelector('#tabla-preview-wo tbody');
            if (tbody) tbody.innerHTML = '';
        }
    },

    cargarPreviewWO: async function (ids) {
        const tbody = document.querySelector('#tabla-preview-wo tbody');
        const thead = document.querySelector('#tabla-preview-wo thead');

        if (!tbody || !thead) return;

        tbody.innerHTML = '<tr><td colspan="10" class="text-center"><i class="fas fa-spinner fa-spin"></i> Cargando vista previa...</td></tr>';

        try {
            const response = await fetch('/api/exportar/world-office/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids })
            });
            const result = await response.json();

            if (result.success && result.data.length > 0) {
                // Render Headers
                const firstRow = result.data[0];
                const columns = Object.keys(firstRow);
                thead.innerHTML = '<tr>' + columns.map(col => `<th>${col}</th>`).join('') + '</tr>';

                // Render Rows
                tbody.innerHTML = result.data.map(row => {
                    return '<tr>' + columns.map(col => `<td>${row[col] !== null ? row[col] : ''}</td>`).join('') + '</tr>';
                }).join('');

            } else {
                tbody.innerHTML = '<tr><td colspan="10" class="text-center text-warning"><i class="fas fa-exclamation-triangle"></i> No hay datos para exportar con los filtros seleccionados.</td></tr>';
            }
        } catch (error) {
            console.error("Error cargando preview:", error);
            tbody.innerHTML = `<tr><td colspan="10" class="text-center text-danger">Error: ${error.message}</td></tr>`;
        }
    },

    descargarExcelWO: function () {
        const modal = document.getElementById('modal-preview-wo');
        const ids = modal ? JSON.parse(modal.dataset.idsToExport || '[]') : [];

        const btn = document.getElementById('btn-confirmar-exportar-wo');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
        btn.disabled = true;

        fetch('/api/exportar/world-office', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids })
        })
            .then(response => {
                if (response.ok) return response.blob();
                return response.json().then(err => Promise.reject(err));
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `Export_WO_${new Date().toISOString().slice(0, 10)}.xlsx`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                if (typeof mostrarNotificacion === 'function') mostrarNotificacion('✅ Archivo generado correctamente.', 'success');
                else alert('Archivo generado');

                this.cerrarPreviewWO();
            })
            .catch(error => {
                console.error("Error descarga WO:", error);
                if (typeof Swal !== 'undefined') Swal.fire('Error', error.message || error.error, 'error');
                else alert('Error: ' + error.message);
            })
            .finally(() => {
                if (btn) {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            });
    }
};

// Exportar
window.ModuloFacturacion = ModuloFacturacion;
window.initFacturacion = () => ModuloFacturacion.inicializar();
