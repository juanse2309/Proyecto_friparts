// ============================================
// inyeccion.js - Lógica de Inyección (VERSIÓN CORREGIDA)
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
 * REGISTRAR INYECCIÓN - FUNCIÓN PRINCIPAL COMPLETA (22 CAMPOS)
 */
async function registrarInyeccion() {
    try {
        mostrarLoading(true);

        // RECOPILAR TODOS LOS DATOS (22 CAMPOS)
        const datos = {
            fecha_inicio: document.getElementById('fecha-inyeccion')?.value || '',
            fecha_fin: document.getElementById('fecha-fin-inyeccion')?.value || '',
            maquina: document.getElementById('maquina-inyeccion')?.value || '',
            responsable: document.getElementById('responsable-inyeccion')?.value || '',
            codigo_producto: document.getElementById('codigo-producto-inyeccion')?.value || '',
            no_cavidades: parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1,
            hora_llegada: document.getElementById('hora-llegada-inyeccion')?.value || '',
            hora_inicio: document.getElementById('hora-inicio-inyeccion')?.value || '',
            hora_termina: document.getElementById('hora-termina-inyeccion')?.value || '',
            cantidad_real: parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0, // Disparos
            tomados_proceso: parseInt(document.getElementById('tomados-proceso-inyeccion')?.value) || 0,
            peso_tomadas: parseFloat(document.getElementById('peso-tomadas-inyeccion')?.value) || 0,
            almacen_destino: document.getElementById('almacen-destino-inyeccion')?.value || '',
            codigo_ensamble: document.getElementById('codigo-ensamble-inyeccion')?.value || '',
            orden_produccion: document.getElementById('orden-produccion-inyeccion')?.value || '',
            observaciones: document.getElementById('observaciones-inyeccion')?.value || '',
            peso_vela_maquina: parseFloat(document.getElementById('peso-vela-inyeccion')?.value) || 0,
            peso_bujes: parseFloat(document.getElementById('peso-bujes-inyeccion')?.value) || 0,
            pnc: parseInt(document.getElementById('pnc-inyeccion')?.value) || 0,
            criterio_pnc: document.getElementById('criterio-pnc-inyeccion')?.value || ''
        };

        console.log('📤 Datos a enviar (22 campos):', datos);

        // ✅ VALIDACIÓN
        if (!datos.codigo_producto || datos.codigo_producto.trim() === '') {
            mostrarNotificacion('❌ Ingresa código del producto', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.cantidad_real || datos.cantidad_real <= 0) {
            mostrarNotificacion('❌ Ingresa disparos válidos', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.responsable || datos.responsable.trim() === '') {
            mostrarNotificacion('❌ Selecciona responsable', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.maquina || datos.maquina.trim() === '') {
            mostrarNotificacion('❌ Selecciona máquina', 'error');
            mostrarLoading(false);
            return;
        }

        console.log('✅ Validación pasada, enviando...');

        // ENVIAR AL SERVIDOR
        const response = await fetch('/api/inyeccion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();
        console.log('Respuesta del servidor:', resultado);

        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');

            // Limpiar formulario
            document.getElementById('form-inyeccion').reset();

            // Restaurar valores por defecto
            document.getElementById('cavidades-inyeccion').value = 1;
            document.getElementById('pnc-inyeccion').value = 0;
            document.getElementById('produccion-calculada').textContent = '0';
            document.getElementById('formula-calc').textContent = 'Disparos: 0 × Cavidades: 1 = 0 piezas';
            
            // Restaurar fecha actual
            const fechaHoy = new Date().toISOString().split('T')[0];
            document.getElementById('fecha-inyeccion').value = fechaHoy;

            // Recargar dashboard
            if (window.actualizarDashboard) {
                window.actualizarDashboard();
            }
        } else {
            const errores = resultado.errors
                ? Object.values(resultado.errors).join(', ')
                : resultado.error || 'Error desconocido';
            mostrarNotificacion(`❌ ${errores}`, 'error');
        }
    } catch (error) {
        console.error('Error registrando inyección:', error);
        mostrarNotificacion(`❌ Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Actualizar cálculo de producción en tiempo real
 */
function actualizarCalculoProduccion() {
    const disparos = parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0;
    const cavidades = parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1;
    const pnc = parseInt(document.getElementById('pnc-inyeccion')?.value) || 0;
    
    // ✅ FÓRMULA CORRECTA: Disparos × Cavidades = Cantidad Total
    const cantidadTotal = disparos * cavidades;
    const piezasBuenas = Math.max(0, cantidadTotal - pnc);
    
    // Mostrar resultado de piezas buenas
    const produccionCalculada = document.getElementById('produccion-calculada');
    if (produccionCalculada) {
        produccionCalculada.textContent = formatNumber(piezasBuenas);
        produccionCalculada.style.color = piezasBuenas > 0 ? '#10b981' : '#6b7280';
    }
    
    // Mostrar fórmula explicativa
    const formulaCalc = document.getElementById('formula-calc');
    if (formulaCalc) {
        formulaCalc.innerHTML = `
            <strong>Disparos:</strong> ${formatNumber(disparos)} × 
            <strong>Cavidades:</strong> ${formatNumber(cavidades)} = 
            <strong style="color: #3b82f6;">${formatNumber(cantidadTotal)}</strong> piezas totales<br>
            <strong>Total:</strong> ${formatNumber(cantidadTotal)} - 
            <strong>PNC:</strong> ${formatNumber(pnc)} = 
            <strong style="color: #10b981;">${formatNumber(piezasBuenas)}</strong> piezas buenas
        `;
    }
    
    // Validar que PNC no sea mayor que la producción total
    if (pnc > cantidadTotal) {
        mostrarNotificacion('⚠️ PNC no puede ser mayor que la producción total', 'warning', 3000);
        document.getElementById('pnc-inyeccion').value = cantidadTotal;
    }
}

/**
 * Autocompletar código de ensamble cuando se selecciona producto
 */
async function autocompletarCodigoEnsamble() {
    const codigoProducto = document.getElementById('codigo-producto-inyeccion')?.value;
    const codigoEnsambleField = document.getElementById('codigo-ensamble-inyeccion');
    
    if (!codigoProducto || !codigoEnsambleField) return;
    
    try {
        // Mostrar loading en el campo
        codigoEnsambleField.value = 'Buscando...';
        codigoEnsambleField.classList.add('loading');
        
        // Buscar información del producto
        const productos = await fetchData('/api/obtener_productos_detalles');
        
        if (productos && Array.isArray(productos)) {
            const producto = productos.find(p => 
                p.codigo === codigoProducto || 
                p.descripcion?.includes(codigoProducto)
            );
            
            if (producto) {
                // Intentar obtener código de ensamble del producto
                codigoEnsambleField.value = producto.codigo_ensamble || 
                                           producto.codigo_ensamble_sistema || 
                                           producto.codigo_sistema || 
                                           '';
            } else {
                // Si no se encuentra, usar el mismo código
                codigoEnsambleField.value = codigoProducto;
            }
        } else {
            // Fallback al código del producto
            codigoEnsambleField.value = codigoProducto;
        }
        
    } catch (error) {
        console.error('Error obteniendo código ensamble:', error);
        codigoEnsambleField.value = codigoProducto; // Fallback al código del producto
    } finally {
        codigoEnsambleField.classList.remove('loading');
    }
}

/**
 * Formatear número con separadores de miles
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Configurar eventos para inyección
 */
function configurarEventosInyeccion() {
    // Elementos del formulario
    const cantidadInput = document.getElementById('cantidad-inyeccion');
    const cavidadesInput = document.getElementById('cavidades-inyeccion');
    const pncInput = document.getElementById('pnc-inyeccion');
    const codigoProductoInput = document.getElementById('codigo-producto-inyeccion');
    const formInyeccion = document.getElementById('form-inyeccion');
    
    // Eventos para cálculo en tiempo real
    if (cantidadInput) {
        cantidadInput.addEventListener('input', actualizarCalculoProduccion);
    }
    
    if (cavidadesInput) {
        cavidadesInput.addEventListener('input', actualizarCalculoProduccion);
    }
    
    if (pncInput) {
        pncInput.addEventListener('input', actualizarCalculoProduccion);
    }
    
    // Evento para autocompletar código de ensamble
    if (codigoProductoInput) {
        codigoProductoInput.addEventListener('change', autocompletarCodigoEnsamble);
    }
    
    // Evento para enviar formulario
    if (formInyeccion) {
        formInyeccion.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('📝 Enviando formulario de inyección...');
            registrarInyeccion();
        });
    }
    
    // Inicializar cálculo al cargar
    setTimeout(() => {
        actualizarCalculoProduccion();
    }, 100);
}

/**
 * Inicializar módulo de inyección
 */
function initInyeccion() {
    console.log('🔧 Inicializando módulo de inyección...');
    
    // Cargar datos
    cargarDatosInyeccion();
    
    // Configurar eventos
    configurarEventosInyeccion();
    
    // Establecer fecha actual
    const fechaHoy = new Date().toISOString().split('T')[0];
    const fechaInput = document.getElementById('fecha-inyeccion');
    if (fechaInput && !fechaInput.value) {
        fechaInput.value = fechaHoy;
    }
    
    console.log('✅ Módulo de inyección inicializado');
}

// Exportar funciones (si usas módulos ES6)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initInyeccion,
        registrarInyeccion,
        actualizarCalculoProduccion
    };
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Si estamos en la página de inyección, inicializar
    const inyeccionPage = document.getElementById('inyeccion-page');
    if (inyeccionPage && inyeccionPage.classList.contains('active')) {
        initInyeccion();
    }
});