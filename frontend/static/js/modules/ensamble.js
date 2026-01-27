// ============================================
// ensamble.js - Lógica de Ensamble
// ============================================

/**
 * Cargar datos de Ensamble
 */
async function cargarDatosEnsamble() {
    try {
        console.log('📦 Cargando datos de ensamble...');
        mostrarLoading(true);
        
        // Cargar responsables
        const responsables = await fetchData('/api/obtener_responsables');
        if (responsables && Array.isArray(responsables)) {
            actualizarSelectEnsamble('responsable-ensamble', responsables);
        }
        
        // Usar productos del cache compartido
        if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
            console.log('✅ Usando productos del cache compartido en Ensamble');
            actualizarSelectEnsamble('ens-id-codigo', window.AppState.sharedData.productos);
        } else {
            console.warn('⚠️ No hay productos en cache compartido para Ensamble');
        }
        
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
            if (typeof item === 'object') {
                option.value = item.codigo_sistema || item.codigo || item.nombre || item.id || '';
                option.textContent = item.descripcion ? `${item.codigo_sistema || item.codigo} - ${item.descripcion}` : (item.nombre || item.id);
            } else {
                option.value = item;
                option.textContent = item;
            }
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
            fecha: document.getElementById('fecha-ensamble')?.value || '',
            responsable: document.getElementById('responsable-ensamble')?.value || '',
            hora_inicio: document.getElementById('hora-inicio-ensamble')?.value || '',
            hora_fin: document.getElementById('hora-fin-ensamble')?.value || '',
            codigo_producto: document.getElementById('ens-id-codigo')?.value || '',
            qty_per_ensamble: document.getElementById('ens-qty-bujes')?.value || '1',
            cantidad: document.getElementById('cantidad-ensamble')?.value || '0',
            almacen_origen: document.getElementById('almacen-origen-ensamble')?.value || '',
            almacen_destino: document.getElementById('almacen-destino-ensamble')?.value || '',
            op: document.getElementById('op-ensamble')?.value || '',
            pnc: document.getElementById('pnc-ensamble')?.value || '0',
            observaciones: document.getElementById('observaciones-ensamble')?.value || ''
        };
        
        if (!datos.codigo_producto) {
            mostrarNotificacion('⚠️ Selecciona un producto', 'error');
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
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');
            document.getElementById('form-ensamble')?.reset();
            setTimeout(() => location.reload(), 1500);
        } else {
            mostrarNotificacion(`❌ ${resultado.error || 'Error'}`, 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Actualizar cálculo de ensamble en tiempo real
 */
function actualizarCalculoEnsamble() {
    const cantidad = parseInt(document.getElementById('cantidad-ensamble')?.value) || 0;
    const pnc = parseInt(document.getElementById('pnc-ensamble')?.value) || 0;
    const qtyPerEnsamble = parseInt(document.getElementById('ens-qty-bujes')?.value) || 1;
    
    const ensamblesBuenos = Math.max(0, cantidad - pnc);
    const bujesConsumidos = cantidad * qtyPerEnsamble;
    
    // UI Elements
    const displaySalida = document.getElementById('produccion-calculada-ensamble');
    const formulaCalc = document.getElementById('formula-calc-ensamble');
    const piezasBuenasDisplay = document.getElementById('piezas-buenas-ensamble');
    
    if (displaySalida) displaySalida.textContent = formatNumber(ensamblesBuenos);
    if (formulaCalc) {
        formulaCalc.textContent = `Ensambles: ${formatNumber(cantidad)} - PNC: ${formatNumber(pnc)} = ${formatNumber(ensamblesBuenos)} finales`;
    }
    if (piezasBuenasDisplay) {
        piezasBuenasDisplay.textContent = `Bujes consumidos: ${formatNumber(bujesConsumidos)}`;
    }
}

/**
 * Inicializar módulo
 */
function initEnsamble() {
    console.log('🔧 Inicializando módulo de Ensamble...');
    cargarDatosEnsamble();
    
    // Listeners
    document.getElementById('cantidad-ensamble')?.addEventListener('input', actualizarCalculoEnsamble);
    document.getElementById('pnc-ensamble')?.addEventListener('input', actualizarCalculoEnsamble);
    document.getElementById('ens-qty-bujes')?.addEventListener('input', actualizarCalculoEnsamble);
    
    console.log('✅ Módulo de Ensamble inicializado');
}

// Exportar
window.initEnsamble = initEnsamble;
window.ModuloEnsamble = { inicializar: initEnsamble };
