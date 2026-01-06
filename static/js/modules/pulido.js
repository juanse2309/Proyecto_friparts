// ============================================
// pulido.js - Lógica de Pulido
// ============================================

/**
 * Cargar datos de Pulido
 */
async function cargarDatosPulido() {
    try {
        console.log('🔧 Cargando datos de pulido...');
        mostrarLoading(true);
        
        // Cargar responsables
        const responsables = await fetchData('/api/obtener_responsables');
        if (responsables) {
            actualizarSelectPulido('responsable-pulido', responsables);
        }
        
        // Cargar productos
        const productos = await fetchData('/api/obtener_productos');
        if (productos) {
            actualizarSelectPulido('codigo-producto-pulido', productos);
        }
        
        console.log('✅ Datos de pulido cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos:', error);
        mostrarLoading(false);
    }
}

/**
 * Actualizar select en Pulido
 */
function actualizarSelectPulido(selectId, datos) {
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
 * Registrar Pulido
 */
async function registrarPulido() {
    try {
        mostrarLoading(true);
        
        const datos = {
            codigo_producto: document.getElementById('codigo-producto-pulido')?.value || '',
            cantidad_recibida: document.getElementById('cantidad-pulido')?.value || '0',
            pnc: document.getElementById('pnc-pulido')?.value || '0',
            responsable: document.getElementById('responsable-pulido')?.value || '',
            fecha_inicio: document.getElementById('fecha-inicio-pulido')?.value || new Date().toISOString().split('T')[0],
            observaciones: document.getElementById('observaciones-pulido')?.value || ''
        };
        
        console.log('📤 Datos de pulido:', datos);
        
        if (!datos.codigo_producto?.trim()) {
            mostrarNotificacion('❌ Ingresa código del producto', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.cantidad_recibida || datos.cantidad_recibida === '0') {
            mostrarNotificacion('❌ Ingresa cantidad recibida', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.responsable?.trim()) {
            mostrarNotificacion('❌ Selecciona responsable', 'error');
            mostrarLoading(false);
            return;
        }
        
        const response = await fetch('/api/pulido', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        
        const resultado = await response.json();
        
        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');
            limpiarFormulario('formulario-pulido');
            setTimeout(() => location.reload(), 1500);
        } else {
            const errores = resultado.errors 
                ? Object.values(resultado.errors).join(', ') 
                : resultado.error || 'Error desconocido';
            mostrarNotificacion(`❌ ${errores}`, 'error');
        }
    } catch (error) {
        console.error('Error registrando:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}
