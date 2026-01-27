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
            const datalist = document.getElementById('fac-productos-list');
            if (datalist) {
                datalist.innerHTML = '';
                window.AppState.sharedData.productos.forEach(p => {
                    const option = document.createElement('option');
                    option.value = p.codigo_sistema || p.codigo;
                    option.textContent = `${p.codigo_sistema || p.codigo} - ${p.descripcion}`;
                    datalist.appendChild(option);
                });
            }
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
                const val = item.nombre || item.id || item.codigo_sistema || item.codigo || '';
                const text = item.descripcion ? `${val} - ${item.descripcion}` : (item.nombre || item.id || val);
                option.value = val;
                option.textContent = text;
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
            codigo_producto: document.getElementById('producto-facturacion')?.value || '',
            cantidad_vendida: document.getElementById('cantidad-facturacion')?.value || '0',
            precio_unitario: document.getElementById('precio-facturacion')?.value || '0',
            orden_compra: document.getElementById('orden-compra-facturacion')?.value || '',
            fecha_inicio: document.getElementById('fecha-facturacion')?.value || new Date().toISOString().split('T')[0],
            observaciones: document.getElementById('observaciones-facturacion')?.value || ''
        };
        
        if (!datos.cliente || !datos.codigo_producto) {
            mostrarNotificacion('⚠️ Selecciona cliente y producto', 'error');
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
            document.getElementById('form-facturacion')?.reset();
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
 * Cálculo de total en tiempo real
 */
function actualizarTotalFacturacion() {
    const cantidad = parseFloat(document.getElementById('cantidad-facturacion')?.value) || 0;
    const precio = parseFloat(document.getElementById('precio-facturacion')?.value) || 0;
    const total = cantidad * precio;
    
    const displayTotal = document.getElementById('total-facturacion');
    if (displayTotal) {
        displayTotal.textContent = `$ ${formatNumber(total)}`;
    }
}

/**
 * Inicializar módulo
 */
function initFacturacion() {
    console.log('🔧 Inicializando módulo de Facturación...');
    cargarDatosFacturacion();
    
    document.getElementById('cantidad-facturacion')?.addEventListener('input', actualizarTotalFacturacion);
    document.getElementById('precio-facturacion')?.addEventListener('input', actualizarTotalFacturacion);
    
    // Si hay un formulario, prevenir el submit por defecto y usar nuestra función
    document.getElementById('form-facturacion')?.addEventListener('submit', (e) => {
        e.preventDefault();
        registrarFacturacion();
    });

    console.log('✅ Módulo de Facturación inicializado');
}

// Exportar
window.initFacturacion = initFacturacion;
window.ModuloFacturacion = { inicializar: initFacturacion };
