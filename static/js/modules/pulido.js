// ============================================
// pulido.js - Lógica de Pulido ACTUALIZADO
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

        // Cargar criterios PNC
        await cargarCriteriosPNC('pulido', 'criterio-pnc-pulido');

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
    select.innerHTML = '-- Seleccionar --';

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
* Registrar Pulido - VERSIÓN COMPLETA
*/
async function registrarPulido() {
    try {
        mostrarLoading(true);

        // Obtener todos los campos
        const fecha = document.getElementById('fecha-pulido')?.value;
        const responsable = document.getElementById('responsable-pulido')?.value;
        const horaInicio = document.getElementById('hora-inicio-pulido')?.value;
        const horaFin = document.getElementById('hora-fin-pulido')?.value;
        const codigoProducto = document.getElementById('codigo-producto-pulido')?.value?.trim(); // ✅ TRIM agregado
        const lote = document.getElementById('lote-pulido')?.value;
        const ordenProduccion = document.getElementById('orden-produccion-pulido')?.value;
        const cantidadRecibida = document.getElementById('cantidad-recibida-pulido')?.value;
        const cantidadReal = document.getElementById('cantidad-pulido')?.value;
        const pnc = document.getElementById('pnc-pulido')?.value || '0';
        const criterioPNC = document.getElementById('criterio-pnc-pulido')?.value;
        const observaciones = document.getElementById('observaciones-pulido')?.value;

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

        console.log('📤 Datos de pulido:', datos);

        const response = await fetch('/api/pulido', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();

        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');
            document.getElementById('form-pulido')?.reset();
            setTimeout(() => cargarDatosPulido(), 1500);
        } else {
            const errores = resultado.errors
                ? Object.values(resultado.errors).join(', ')
                : resultado.error || 'Error desconocido';
            mostrarNotificacion(`❌ ${errores}`, 'error');
        }

    } catch (error) {
        console.error('❌ Error registrando pulido:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

// Asociar form submit
document.addEventListener('DOMContentLoaded', () => {
    const formPulido = document.getElementById('form-pulido');
    if (formPulido) {
        formPulido.addEventListener('submit', async (e) => {
            e.preventDefault();
            await registrarPulido();
        });
    }
});