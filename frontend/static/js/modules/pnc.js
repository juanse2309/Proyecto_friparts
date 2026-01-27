// pnc.js - MÓDULO DE PRODUCTOS NO CONFORMES (REFACTORIZADO)
// ===========================================

const ModuloPNC = (() => {
    let registrosPNC = [];
    let filtroActual = 'todos';

    /**
     * Inicializa el módulo y carga datos Juan Sebastian.
     */
    async function inicializar() {


        configurarEventos();

        // Configurar datalist de productos
        FormHelpers.configurarDatalistProductos('pnc-manual-producto', 'pnc-productos-list');

        // Ya no cargamos datos aquí porque la tabla fue eliminada a favor del Historial Global
        // await cargarDatosPNC();


    }

    /**
     * Listeners para filtros y exportación.
     */
    function configurarEventos() {
        // Formulario Manual Juan Sebastian 
        const formManual = document.getElementById('form-manual-pnc');
        if (formManual) {
            formManual.onsubmit = async (e) => {
                e.preventDefault();
                await registrarPNCManual();
            };

            // Buscar ensamble automáticamente
            const inputProd = document.getElementById('pnc-manual-producto');
            if (inputProd) {
                inputProd.onblur = async () => {
                    const cod = inputProd.value.trim();
                    if (cod) {
                        try {
                            const res = await fetch(`/api/inyeccion/ensamble_desde_producto?codigo=${cod}`);
                            const data = await res.json();
                            if (data.success) {
                                document.getElementById('pnc-manual-ensamble').value = data.codigo_ensamble || '';
                            }
                        } catch (e) { console.warn('No se pudo autocompletar ensamble'); }
                    }
                };
            }

            // Fecha hoy por defecto Juan Sebastian
            const inputFecha = document.getElementById('pnc-manual-fecha');
            if (inputFecha) inputFecha.value = new Date().toISOString().split('T')[0];
        }

        // Filtros por proceso
        document.querySelectorAll('.btn-filtro-pnc').forEach(btn => {
            btn.addEventListener('click', function () {
                const proceso = this.dataset.proceso;
                filtrarPNC(proceso);
            });
        });

        // Botón exportar
        const btnExportar = document.getElementById('btn-exportar-pnc');
        if (btnExportar) {
            btnExportar.onclick = exportarPNC;
        }

        // Cerrar modal detalle
        document.querySelectorAll('#modal-detalle-pnc .close').forEach(btn => {
            btn.onclick = () => {
                document.getElementById('modal-detalle-pnc').style.display = 'none';
            };
        });
    }

    /**
     * Consulta el consolidado al backend Juan Sebastian.
     */
    async function cargarDatosPNC() {
        try {
            mostrarLoading(true);
            const res = await fetch('/api/obtener_pnc');
            const data = await res.json();

            registrosPNC = data || [];
            renderizarTabla();

            const contador = document.getElementById('contador-pnc');
            if (contador) contador.textContent = `${registrosPNC.length} registros`;

        } catch (error) {
            mostrarNotificacion('Error al cargar datos de PNC', 'error');
        } finally {
            mostrarLoading(false);
        }
    }

    /**
     * Renderiza la tabla con los datos actuales Juan Sebastian.
     */
    function renderizarTabla() {
        const tbody = document.getElementById('tabla-pnc-body');
        if (!tbody) return;

        tbody.innerHTML = '';

        let filtrados = registrosPNC;
        if (filtroActual !== 'todos') {
            filtrados = registrosPNC.filter(r => r.proceso === filtroActual);
        }

        if (filtrados.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">No hay registros para mostrar</td></tr>';
            return;
        }

        filtrados.forEach(reg => {
            const tr = document.createElement('tr');

            // Clase de badge según proceso Juan Sebastian
            const badgeClass = {
                'inyeccion': 'bg-primary',
                'pulido': 'bg-info text-dark',
                'ensamble': 'bg-secondary'
            }[reg.proceso] || 'bg-dark';

            tr.innerHTML = `
                <td><small>${reg.fecha}</small></td>
                <td><span class="badge ${badgeClass}">${reg.proceso.toUpperCase()}</span></td>
                <td><strong>${reg.codigo_producto}</strong></td>
                <td>${reg.responsable}</td>
                <td class="text-end fw-bold">${reg.cantidad}</td>
                <td><span class="text-truncate d-inline-block" style="max-width: 150px;">${reg.criterio_pnc}</span></td>
                <td><span class="badge bg-warning text-dark">${reg.estado}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="ModuloPNC.verDetalle('${reg.id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    /**
     * Cambia el filtro actual Juan Sebastian.
     */
    function filtrarPNC(proceso) {
        filtroActual = proceso;
        renderizarTabla();

        // Actualizar UI botones Juan Sebastian
        document.querySelectorAll('.btn-filtro-pnc').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.proceso === proceso);
            btn.classList.toggle('btn-primary', btn.dataset.proceso === proceso);
            btn.classList.toggle('btn-light', btn.dataset.proceso !== proceso);
        });
    }

    /**
     * Muestra el modal con la info completa Juan Sebastian.
     */
    function verDetalle(id) {
        const reg = registrosPNC.find(r => r.id === id);
        if (!reg) return;

        const container = document.getElementById('detalle-pnc-contenido');
        if (!container) return;

        container.innerHTML = `
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="text-muted small d-block">ID de Registro</label>
                    <p class="fw-bold">${reg.id}</p>
                    <label class="text-muted small d-block">Proceso de Origen</label>
                    <p><span class="badge bg-dark">${reg.proceso.toUpperCase()}</span></p>
                </div>
                <div class="col-md-6">
                    <label class="text-muted small d-block">Fecha Reporte</label>
                    <p>${reg.fecha}</p>
                    <label class="text-muted small d-block">Código Producto</label>
                    <p class="text-primary fw-bold">${reg.codigo_producto}</p>
                </div>
                <hr>
                <div class="col-12">
                    <label class="text-muted small d-block">Criterio de Rechazo / Defecto</label>
                    <p class="alert alert-danger p-2 h5">${reg.criterio_pnc}</p>
                </div>
                <div class="col-md-6 text-center">
                    <label class="text-muted small d-block">Cantidad Afectada</label>
                    <div class="h2 text-danger fw-bold">${reg.cantidad}</div>
                </div>
                <div class="col-md-6">
                    <label class="text-muted small d-block">Info Adicional / Ensamble</label>
                    <p>${reg.observaciones || 'Sin datos extra'}</p>
                </div>
            </div>
        `;

        document.getElementById('modal-detalle-pnc').style.display = 'block';
    }

    /**
     * Exporta los datos a CSV Juan Sebastian.
     */
    function exportarPNC() {
        if (registrosPNC.length === 0) return mostrarNotificacion('Nada que exportar', 'warning');

        let csv = 'Fecha,Proceso,Producto,Cantidad,Criterio,Estado\n';
        registrosPNC.forEach(r => {
            csv += `${r.fecha},${r.proceso},${r.codigo_producto},${r.cantidad},"${r.criterio_pnc}",${r.estado}\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `pnc_global_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
    }

    async function registrarPNCManual() {
        const data = {
            fecha: document.getElementById('pnc-manual-fecha').value,
            codigo_producto: document.getElementById('pnc-manual-producto').value,
            cantidad: document.getElementById('pnc-manual-cantidad').value,
            criterio: document.getElementById('pnc-manual-criterio').value,
            codigo_ensamble: document.getElementById('pnc-manual-ensamble').value
        };

        try {
            mostrarLoading(true);
            const res = await fetch('/api/pnc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await res.json();
            if (result.success) {
                mostrarNotificacion('✅ PNC registrado correctamente Juan Sebastian', 'success');
                document.getElementById('form-manual-pnc').reset();
                const inputFecha = document.getElementById('pnc-manual-fecha');
                if (inputFecha) inputFecha.value = new Date().toISOString().split('T')[0];
                await cargarDatosPNC();
            } else {
                mostrarNotificacion(result.error || 'Error al registrar', 'error');
            }
        } catch (error) {
            console.error('🚨 Error registro manual PNC:', error);
            mostrarNotificacion('Error de conexión', 'error');
        } finally {
            mostrarLoading(false);
        }
    }

    return {
        inicializar,
        verDetalle,
        recargar: cargarDatosPNC
    };
})();

// Exportar objeto global Juan Sebastian
window.ModuloPNC = ModuloPNC;
window.initPNC = ModuloPNC.inicializar;
