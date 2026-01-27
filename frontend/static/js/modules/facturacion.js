// facturacion.js - MÓDULO DE FACTURACIÓN
// ===========================================

const ModuloFacturacion = (() => {
    // Variable privada para evitar envíos dobles
    let isSubmitting = false;

    /**
     * Inicializa el módulo, configura eventos y carga datos.
     */
    function inicializar() {

        cargarSelectores();
        configurarEventos();
        establecerFechaActual();


    }

    /**
     * Carga clientes y productos desde AppState.sharedData.
     */
    function cargarSelectores() {
        const { clientes } = window.AppState.sharedData || {};

        // Poblar Clientes
        const selectCliente = document.getElementById('cliente-facturacion');
        if (selectCliente && clientes) {
            selectCliente.innerHTML = '<option value="">-- Seleccionar Cliente --</option>';
            clientes.forEach(c => {
                const option = document.createElement('option');
                option.value = c;
                option.textContent = c;
                selectCliente.appendChild(option);
            });
        }

        // Configurar datalist de productos (Nuevo sistema con búsqueda)
        FormHelpers.configurarDatalistProductos('producto-facturacion', 'fac-productos-list');
    }

    /**
     * Configura listeners de eventos del formulario.
     */
    function configurarEventos() {
        const form = document.getElementById('form-facturacion');
        if (form) {
            form.removeEventListener('submit', registrarVenta);
            form.addEventListener('submit', registrarVenta);
        }

        // Suscribirse a cambios en cantidad y precio para el Total
        const cantInput = document.getElementById('cantidad-facturacion');
        const precioInput = document.getElementById('precio-facturacion');

        if (cantInput && precioInput) {
            [cantInput, precioInput].forEach(input => {
                input.addEventListener('input', actualizarTotal);
            });
        }
    }

    /**
     * Calcula y muestra el total en tiempo real.
     */
    function actualizarTotal() {
        const cant = parseInt(document.getElementById('cantidad-facturacion').value) || 0;
        const precio = parseFloat(document.getElementById('precio-facturacion').value) || 0;
        const total = cant * precio;

        const totalSpan = document.getElementById('total-facturacion');
        if (totalSpan) {
            totalSpan.textContent = `$ ${total.toLocaleString('es-CO', { minimumFractionDigits: 2 })}`;
        }
    }

    /**
     * Establece la fecha de hoy por defecto.
     */
    function establecerFechaActual() {
        const input = document.getElementById('fecha-facturacion');
        if (input && !input.value) {
            input.value = new Date().toISOString().split('T')[0];
        }
    }

    /**
     * Envía los datos al backend para registro en Sheets.
     */
    async function registrarVenta(e) {
        if (e) e.preventDefault();
        if (isSubmitting) return;

        const data = {
            fecha_inicio: document.getElementById('fecha-facturacion').value,
            cliente: document.getElementById('cliente-facturacion').value,
            codigo_producto: document.getElementById('producto-facturacion').value,
            cantidad_vendida: document.getElementById('cantidad-facturacion').value,
            precio_unitario: document.getElementById('precio-facturacion').value,
            orden_compra: document.getElementById('orden-compra-facturacion').value,
            total_venta: (parseInt(document.getElementById('cantidad-facturacion').value) || 0) *
                (parseFloat(document.getElementById('precio-facturacion').value) || 0)
        };

        // Validación extra Jonathan
        if (!data.cliente || !data.codigo_producto || !data.cantidad_vendida) {
            mostrarNotificacion('Por favor completa los campos obligatorios', 'warning');
            return;
        }

        try {
            isSubmitting = true;
            mostrarLoading(true);

            const res = await fetch('/api/facturacion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await res.json();

            if (res.ok && (result.status === 'success' || result.success)) {
                mostrarNotificacion(result.message || 'Venta registrada con éxito', 'success');
                document.getElementById('form-facturacion').reset();
                actualizarTotal();
                establecerFechaActual();

                // Invalidad cache global de productos si fue exitoso
                if (window.invalidarCacheProductos) window.invalidarCacheProductos();
            } else {
                throw new Error(result.message || result.error || 'Error al registrar');
            }

        } catch (error) {
            console.error('🚨 Error en Facturación:', error);
            mostrarNotificacion(error.message, 'error');
        } finally {
            isSubmitting = false;
            mostrarLoading(false);
        }
    }

    // Exportar interfaz Jonathan
    return {
        inicializar,
        recargarSelectores: cargarSelectores // Por si AppState cambia
    };
})();

// Asignar al scope global
window.ModuloFacturacion = ModuloFacturacion;
window.registrarFacturacion = ModuloFacturacion.inicializar; // Alias compatible
