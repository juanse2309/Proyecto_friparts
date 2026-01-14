// ============================================
// ensamble.js - Lógica de Ensamble ACTUALIZADO
// ============================================

/**
 * Cargar datos de Ensamble
 */
async function cargarDatosEnsamble() {
    try {
        console.log('🔧 Cargando datos de ensamble...');
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
        
        // Cargar criterios PNC
        await cargarCriteriosPNC('ensamble', 'criterio-pnc-ensamble');
        
        console.log('✅ Datos de ensamble cargados');
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
 * Registrar Ensamble - VERSIÓN COMPLETA
 */
async function registrarEnsamble() {
    try {
        mostrarLoading(true);
        
        // Obtener todos los campos
        const fecha = document.getElementById('fecha-ensamble')?.value;
        const responsable = document.getElementById('responsable-ensamble')?.value;
        const horaInicio = document.getElementById('hora-inicio-ensamble')?.value;
        const horaFin = document.getElementById('hora-fin-ensamble')?.value;
        const codigoProducto = document.getElementById('codigo-producto-ensamble')?.value;
        const lote = document.getElementById('lote-ensamble')?.value;
        const ordenProduccion = document.getElementById('orden-produccion-ensamble')?.value;
        const cantidadRecibida = document.getElementById('cantidad-recibida-ensamble')?.value;
        const cantidadReal = document.getElementById('cantidad-ensamble')?.value;
        const pnc = document.getElementById('pnc-ensamble')?.value || '0';
        const criterioPNC = document.getElementById('criterio-pnc-ensamble')?.value;
        const observaciones = document.getElementById('observaciones-ensamble')?.value;
        
        // Validaciones
        if (!fecha?.trim()) {
            mostrarNotificacion('❌ Selecciona fecha', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!responsable?.trim()) {
            mostrarNotificacion('❌ Selecciona responsable', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!horaInicio?.trim()) {
            mostrarNotificacion('❌ Ingresa hora de inicio', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!horaFin?.trim()) {
            mostrarNotificacion('❌ Ingresa hora de fin', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!codigoProducto?.trim()) {
            mostrarNotificacion('❌ Ingresa código del producto', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!cantidadRecibida || cantidadRecibida === '0') {
            mostrarNotificacion('❌ Ingresa cantidad recibida', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!cantidadReal || cantidadReal === '0') {
            mostrarNotificacion('❌ Ingresa cantidad real', 'error');
            mostrarLoading(false);
            return;
        }
        
        // Construir objeto de datos
        const datos = {
            fecha_inicio: fecha,
            responsable: responsable,
            hora_inicio: horaInicio,
            hora_fin: horaFin,
            codigo_producto: codigoProducto,
            lote: lote,
            orden_produccion: ordenProduccion,
            cantidad_recibida: parseInt(cantidadRecibida),
            cantidad_real: parseInt(cantidadReal),
            pnc: parseInt(pnc),
            criterio_pnc: criterioPNC,
            observaciones: observaciones
        };
        
        console.log('📤 Datos de ensamble:', datos);
        
        const response = await fetch('/api/ensamble', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        
        const resultado = await response.json();
        
        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');
            document.getElementById('form-ensamble')?.reset();
            setTimeout(() => cargarDatosEnsamble(), 1500);
        } else {
            const errores = resultado.errors 
                ? Object.values(resultado.errors).join(', ') 
                : resultado.error || 'Error desconocido';
            mostrarNotificacion(`❌ ${errores}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error registrando ensamble:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

// Asociar form submit
document.addEventListener('DOMContentLoaded', () => {
    const formEnsamble = document.getElementById('form-ensamble');
    if (formEnsamble) {
        formEnsamble.addEventListener('submit', async (e) => {
            e.preventDefault();
            await registrarEnsamble();
        });
    }
});