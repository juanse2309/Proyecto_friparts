// ============================================
// ensamble.js - L??gica de Ensamble
// ============================================

/**
 * Cargar datos de Ensamble
 */
async function cargarDatosEnsamble() {
    try {
        console.log('???? Cargando datos de ensamble...');
        mostrarLoading(true);
        
        // Cargar responsables
        const responsables = await fetchData('/api/obtener_responsables');
        if (responsables) {
            actualizarSelectEnsamble('responsable-ensamble', responsables);
        }
        
        // Cargar productos
        const productos = await fetchData('/api/obtener_productos');
        if (productos) {
            actualizarSelectEnsamble('codigo-producto-ensamble', productos);
        }
        
        console.log('??? Datos de ensamble cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos:', error);
        mostrarLoading(false);
    }
}

/**
 * Actualizar select en Ensamble
 */
function actualizarSelectEnsamble(selectId, datos) {
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
 * Registrar Ensamble
 */
async function registrarEnsamble() {
    try {
        mostrarLoading(true);
        
        const datos = {
            codigo_producto: document.getElementById('codigo-producto-ensamble')?.value || '',
            cantidad: document.getElementById('cantidad-ensamble')?.value || '0',
            pnc: document.getElementById('pnc-ensamble')?.value || '0',
            responsable: document.getElementById('responsable-ensamble')?.value || '',
            fecha_inicio: document.getElementById('fecha-inicio-ensamble')?.value || new Date().toISOString().split('T')[0],
            observaciones: document.getElementById('observaciones-ensamble')?.value || ''
        };
        
        console.log('???? Datos de ensamble:', datos);
        
        if (!datos.codigo_producto?.trim()) {
            mostrarNotificacion('??? Ingresa c??digo del producto', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.cantidad || datos.cantidad === '0') {
            mostrarNotificacion('??? Ingresa cantidad', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.responsable?.trim()) {
            mostrarNotificacion('??? Selecciona responsable', 'error');
            mostrarLoading(false);
            return;
        }
        
        const response = await fetch('/api/ensamble', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        
        const resultado = await response.json();
        
        if (response.ok && resultado.success) {
            mostrarNotificacion(`??? ${resultado.mensaje}`, 'success');
            limpiarFormulario('formulario-ensamble');
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
