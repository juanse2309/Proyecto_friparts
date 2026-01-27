// ============================================
// facturacion.js - L??gica de Facturaci??n
// ============================================

/**
 * Cargar datos de Facturaci??n
 */
async function cargarDatosFacturacion() {
    try {
        console.log('???? Cargando datos de facturaci??n...');
        mostrarLoading(true);
        
        // Cargar clientes
        const clientes = await fetchData('/api/obtener_clientes');
        if (clientes) {
            actualizarSelectFacturacion('cliente-facturacion', clientes);
        }
        
        // Cargar productos
        const productos = await fetchData('/api/obtener_productos');
        if (productos) {
            actualizarSelectFacturacion('codigo-producto-facturacion', productos);
        }
        
        console.log('??? Datos de facturaci??n cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos:', error);
        mostrarLoading(false);
    }
}

/**
 * Actualizar select en Facturaci??n
 */
function actualizarSelectFacturacion(selectId, datos) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    const currentValue = select.value;
    select.innerHTML = '<option value="">-- Seleccionar --</option>';
    
    if (datos && Array.isArray(datos)) {
        datos.forEach(item => {
            const option = document.createElement('option');
            option.value = item;
            option.textContent = item;
            select.appendChild(option);
        });
    }
    
    if (currentValue) select.value = currentValue;
}

/**
 * Registrar Facturaci??n
 */
async function registrarFacturacion() {
    try {
        mostrarLoading(true);
        
        const datos = {
            cliente: document.getElementById('cliente-facturacion')?.value || '',
            codigo_producto: document.getElementById('codigo-producto-facturacion')?.value || '',
            cantidad_vendida: document.getElementById('cantidad-facturacion')?.value || '0',
            total_venta: document.getElementById('total-facturacion')?.value || '0',
            fecha_inicio: document.getElementById('fecha-facturacion')?.value || new Date().toISOString().split('T')[0],
            observaciones: document.getElementById('observaciones-facturacion')?.value || ''
        };
        
        console.log('???? Datos de facturaci??n:', datos);
        
        if (!datos.cliente?.trim()) {
            mostrarNotificacion('??? Selecciona un cliente', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.codigo_producto?.trim()) {
            mostrarNotificacion('??? Ingresa c??digo del producto', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.cantidad_vendida || datos.cantidad_vendida === '0') {
            mostrarNotificacion('??? Ingresa cantidad vendida', 'error');
            mostrarLoading(false);
            return;
        }
        
        const response = await fetch('/api/facturacion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        
        const resultado = await response.json();
        
        if (response.ok && resultado.success) {
            mostrarNotificacion(`??? ${resultado.mensaje}`, 'success');
            limpiarFormulario('formulario-facturacion');
            setTimeout(() => location.reload(), 1500);
        } else {
            const errores = resultado.errors 
                ? Object.values(resultado.errors).join(', ') 
                : resultado.error || 'Error desconocido';
            mostrarNotificacion(`??? ${errores}`, 'error');
        }
    } catch (error) {
        console.error('Error registrando:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}
window.ModuloFacturacion = { inicializar: inicializarFacturacion };
