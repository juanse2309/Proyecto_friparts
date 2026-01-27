// ============================================
// facturacion.js - Lógica de Facturación
// ============================================

/**
 * Cargar datos de Facturación
 */
async function cargarDatosFacturacion() {
    try {
        console.log('📦 Cargando datos de Facturación...');
        mostrarLoading(true);
        
        // Cargar clientes
        const clientes = await fetchData('/api/obtener_clientes');
        if (clientes && Array.isArray(clientes)) {
            actualizarSelectFacturacion('cliente-facturacion', clientes);
        }
        
        // Usar productos del cache compartido
        if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
            console.log('✅ Usando productos del cache compartido en Facturación');
            actualizarSelectFacturacion('codigo-producto-facturacion', window.AppState.sharedData.productos);
        } else {
            console.warn('⚠️ No hay productos en cache compartido para Facturación');
        }
        
        console.log('✅ Datos de Facturación cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos:', error);
        mostrarLoading(false);
    }
}

/**
 * Actualizar select en Facturación
 */
function actualizarSelectFacturacion(selectId, datos) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    const currentValue = select.value;
    select.innerHTML = '<option value="">-- Seleccionar --</option>';
    
    if (datos && Array.isArray(datos)) {
        datos.forEach(item => {
            const option = document.createElement('option');
            if (typeof item === 'object') {
                option.value = item.codigo_sistema || item.codigo || item.id || item.nombre || '';
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
 * Registrar Facturación
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
        
        if (!datos.cliente) {
            mostrarNotificacion('⚠️ Selecciona un cliente', 'error');
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
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');
            document.getElementById('formulario-facturacion')?.reset();
            setTimeout(() => location.reload(), 1500);
        } else {
            mostrarNotificacion(`❌ ${resultado.error || 'Error'}`, 'error');
        }
    } catch (error) {
        console.error('Error register:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Inicializar módulo
 */
function initFacturacion() {
    console.log('🔧 Inicializando módulo de Facturación...');
    cargarDatosFacturacion();
    console.log('✅ Módulo de Facturación inicializado');
}

// Exportar
window.initFacturacion = initFacturacion;
window.ModuloFacturacion = { inicializar: initFacturacion };
