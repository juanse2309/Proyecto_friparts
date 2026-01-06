// ============================================
// inyeccion.js - Lógica de Inyección
// ============================================

/**
 * Cargar datos de inyección
 */
async function cargarDatosInyeccion() {
    try {
        console.log('🔧 Cargando datos de inyección...');
        mostrarLoading(true);
        
        // Cargar responsables
        const responsables = await fetchData('/api/obtener_responsables');
        if (responsables) {
            actualizarSelectInyeccion('responsable-inyeccion', responsables);
        }
        
        // Cargar productos
        const productos = await fetchData('/api/obtener_productos');
        if (productos) {
            actualizarSelectInyeccion('codigo-producto-inyeccion', productos);
        }
        
        // Cargar máquinas
        const maquinas = await fetchData('/api/obtener_maquinas');
        if (maquinas) {
            actualizarSelectInyeccion('maquina-inyeccion', maquinas);
        }
        
        console.log('✅ Datos de inyección cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos:', error);
        mostrarLoading(false);
    }
}

/**
 * Actualizar select en inyección
 */
function actualizarSelectInyeccion(selectId, datos) {
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
 * REGISTRAR INYECCIÓN - FUNCIÓN PRINCIPAL
 */
async function registrarInyeccion() {
    try {
        mostrarLoading(true);
        
        // RECOPILAR DATOS
        const datos = {
            codigo_producto: document.getElementById('codigo-producto-inyeccion')?.value || '',
            cantidad_real: document.getElementById('cantidad-inyeccion')?.value || '0',
            pnc: document.getElementById('pnc-inyeccion')?.value || '0',
            responsable: document.getElementById('responsable-inyeccion')?.value || '',
            fecha_inicio: document.getElementById('fecha-inicio-inyeccion')?.value || new Date().toISOString().split('T')[0],
            fecha_fin: document.getElementById('fecha-fin-inyeccion')?.value || '',
            hora_inicio: document.getElementById('hora-inicio-inyeccion')?.value || '00:00',
            hora_fin: document.getElementById('hora-fin-inyeccion')?.value || '00:00',
            maquina: document.getElementById('maquina-inyeccion')?.value || '',
            no_cavidades: document.getElementById('cavidades-inyeccion')?.value || '1',
            contador_maquina: document.getElementById('contador-inyeccion')?.value || '',
            peso_vela_maquina: document.getElementById('peso-vela-inyeccion')?.value || '',
            peso_bujes: document.getElementById('peso-bujes-inyeccion')?.value || '',
            orden_produccion: document.getElementById('orden-produccion-inyeccion')?.value || '',
            observaciones: document.getElementById('observaciones-inyeccion')?.value || '',
            criterio_pnc: document.getElementById('criterio-pnc-inyeccion')?.value || ''
        };
        
        console.log('📤 Datos a enviar:', datos);
        
        // VALIDAR OBLIGATORIOS
        if (!datos.codigo_producto?.trim()) {
            mostrarNotificacion('❌ Ingresa código del producto', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.cantidad_real || datos.cantidad_real === '0') {
            mostrarNotificacion('❌ Ingresa cantidad producida', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.responsable?.trim()) {
            mostrarNotificacion('❌ Selecciona responsable', 'error');
            mostrarLoading(false);
            return;
        }
        
        // ENVIAR
        const response = await fetch('/api/inyeccion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        
        const resultado = await response.json();
        console.log('Respuesta del servidor:', resultado);
        
        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');
            limpiarFormulario('formulario-inyeccion');
            
            // Recargar tabla
            setTimeout(() => {
                location.reload();
            }, 1500);
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

/**
 * Actualizar cálculo de producción
 */
function actualizarCalculoProduccion() {
    const cantidadDisparos = parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0;
    const cavidades = parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1;
    const pnc = parseInt(document.getElementById('pnc-inyeccion')?.value) || 0;
    
    const piezasTotales = cantidadDisparos * cavidades;
    const piezasBuenas = Math.max(0, piezasTotales - pnc);
    
    const produccionCalculada = document.getElementById('produccion-calculada');
    if (produccionCalculada) {
        produccionCalculada.textContent = formatNumber(piezasBuenas);
        produccionCalculada.style.color = piezasBuenas > 0 ? '#10b981' : '#6b7280';
    }
    
    const formulaCalc = document.getElementById('formula-calc');
    if (formulaCalc) {
        formulaCalc.innerHTML = `
            Disparos (${cantidadDisparos}) × Cavidades (${cavidades}) = 
            ${piezasTotales} piezas - ${pnc} PNC = ${piezasBuenas} piezas buenas
        `;
    }
}

/**
 * Configurar eventos de inyección
 */
function configurarEventosInyeccion() {
    const cantidadInput = document.getElementById('cantidad-inyeccion');
    const cavidadesSelect = document.getElementById('cavidades-inyeccion');
    const pncInput = document.getElementById('pnc-inyeccion');
    
    if (cantidadInput) cantidadInput.addEventListener('input', actualizarCalculoProduccion);
    if (cavidadesSelect) cavidadesSelect.addEventListener('change', actualizarCalculoProduccion);
    if (pncInput) pncInput.addEventListener('input', actualizarCalculoProduccion);
}
