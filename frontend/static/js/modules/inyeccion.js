// ============================================
// inyeccion.js - Lógica de Inyección (VERSIÓN CORREGIDA)
// ============================================

/**
 * Cargar datos de inyección
 */
async function cargarDatosInyeccion() {
    try {
        console.log('📦 Cargando datos de inyección...');
        mostrarLoading(true);

        // Cargar responsables
        const responsables = await fetchData('/api/obtener_responsables');
        if (responsables) {
            actualizarSelectInyeccion('responsable-inyeccion', responsables);
        }

        // Usar productos del cache compartido (ya cargados en app.js)
        if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
            console.log('✅ Usando productos del cache compartido');
            const datalist = document.getElementById('productos-list');
            if (datalist) {
                datalist.innerHTML = '';
                window.AppState.sharedData.productos.forEach(p => {
                    const option = document.createElement('option');
                    option.value = p.codigo_sistema || p.codigo;
                    option.textContent = `${p.codigo_sistema || p.codigo} - ${p.descripcion}`;
                    datalist.appendChild(option);
                });
                console.log(`✅ ${window.AppState.sharedData.productos.length} productos agregados al datalist`);
            }
        } else {
            console.warn('⚠️ No hay productos en cache compartido');
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
    if (!select) {
        console.warn(`⚠️ Select no encontrado: ${selectId}`);
        return;
    }

    const currentValue = select.value;
    select.innerHTML = '<option value="">-- Seleccionar --</option>';

    if (datos && Array.isArray(datos)) {
        datos.forEach(item => {
            const option = document.createElement('option');

            // Si el item es un objeto (producto), usar codigo y descripcion
            if (typeof item === 'object' && item !== null) {
                option.value = item.codigo || item.PRODUCTO || item.descripcion || '';
                option.textContent = `${item.codigo || ''} - ${item.descripcion || item.PRODUCTO || ''}`;
            } else {
                // String simple (responsable, máquina)
                option.value = item;
                option.textContent = item;
            }

            select.appendChild(option);
        });
        console.log(`✅ ${datos.length} opciones agregadas a ${selectId}`);
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

        console.log('✅ [Inyección] Datos preparados:', datos);

        // VALIDACIÓN Juan Sebastian
        if (!datos.codigo_producto || datos.codigo_producto.trim() === '') {
            mostrarNotificacion('Por favor, ingresa el código del producto', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.cantidad_real || datos.cantidad_real <= 0) {
            mostrarNotificacion('Cantidad de disparos no válida', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.responsable || datos.responsable.trim() === '') {
            mostrarNotificacion('Selecciona un responsable', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.maquina || datos.maquina.trim() === '') {
            mostrarNotificacion('Selecciona la máquina utilizada', 'error');
            mostrarLoading(false);
            return;
        }

        console.log('🚀 [Inyección] Enviando solicitud...');

        // ENVIAR AL SERVIDOR
        const response = await fetch('/api/inyeccion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();
        console.log('📦 [Inyección] Respuesta:', resultado);

        if (response.ok && resultado.success) {
            mostrarNotificacion(resultado.mensaje || 'Registro completado con éxito', 'success');

            // Limpiar formulario
            document.getElementById('form-inyeccion').reset();

            // Restaurar valores por defecto
            document.getElementById('cavidades-inyeccion').value = 1;
            document.getElementById('pnc-inyeccion').value = 0;
            document.getElementById('produccion-calculada').textContent = '0';
            document.getElementById('formula-calc').textContent = 'Disparos: 0 x Cavidades: 1 = 0 piezas';

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
            mostrarNotificacion(errores, 'error');
        }
    } catch (error) {
        console.error('❌ [Inyección] Error crítico:', error);
        mostrarNotificacion(`Error del sistema: ${error.message}`, 'error');
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

    // Formula CORRECTA: Disparos x Cavidades = Cantidad Total
    const cantidadTotal = disparos * cavidades;
    const piezasBuenas = Math.max(0, cantidadTotal - pnc);

    // Mostrar TOTAL de piezas (numero grande)
    const produccionCalculada = document.getElementById('produccion-calculada');
    if (produccionCalculada) {
        produccionCalculada.textContent = formatNumber(cantidadTotal);
    }

    // Mostrar formula
    const formulaCalc = document.getElementById('formula-calc');
    if (formulaCalc) {
        formulaCalc.textContent = `Disparos: ${formatNumber(disparos)} x Cavidades: ${formatNumber(cavidades)} = ${formatNumber(cantidadTotal)} piezas`;
    }

    // Mostrar piezas buenas (linea verde)
    const piezasBuenasDisplay = document.getElementById('piezas-buenas');
    if (piezasBuenasDisplay) {
        piezasBuenasDisplay.textContent = `Total: ${formatNumber(cantidadTotal)} - PNC: ${formatNumber(pnc)} = ${formatNumber(piezasBuenas)} piezas buenas`;
    }

    // Validar que PNC no sea mayor que la produccion total
    if (pnc > cantidadTotal && cantidadTotal > 0) {
        mostrarNotificacion('PNC no puede ser mayor que la produccion total', 'warning', 3000);
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

        // Buscar información del producto Juan Sebastian
        const response = await fetch(`/api/inyeccion/ensamble_desde_producto?codigo=${encodeURIComponent(codigoProducto)}`);
        if (!response.ok) {
            console.warn('⚠️ [Inyección] No se pudo obtener ensamble para:', codigoProducto);
            return;
        }
        const data = await response.json();

        if (data.success && data.codigo_ensamble) {
            codigoEnsambleField.value = data.codigo_ensamble;
            console.log(`✅ [Inyección] Ensamble autocompletado: ${data.codigo_ensamble}`);
        } else {
            codigoEnsambleField.value = '';
        }

        codigoEnsambleField.classList.remove('loading');

    } catch (error) {
        console.error('❌ [Inyección] Error obteniendo código ensamble:', error);
        codigoEnsambleField.value = codigoProducto; // Fallback
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

    // Eventos para cálculo en tiempo real Juan Sebastian
    if (cantidadInput) {
        cantidadInput.addEventListener('input', actualizarCalculoProduccion);
    }

    if (cavidadesInput) {
        cavidadesInput.addEventListener('input', actualizarCalculoProduccion);
    }

    if (pncInput) {
        pncInput.addEventListener('input', actualizarCalculoProduccion);
    }

    // Evento para autocompletar c??digo de ensamble
    if (codigoProductoInput) {
        codigoProductoInput.addEventListener('change', autocompletarCodigoEnsamble);
    }

    // Evento para enviar formulario
    if (formInyeccion) {
        formInyeccion.addEventListener('submit', function (e) {
            e.preventDefault();
            console.log('🚀 [Inyección] Procesando formulario...');
            registrarInyeccion();
        });
    }

    // Inicializar cálculo al cargar Juan Sebastian
    setTimeout(() => {
        actualizarCalculoProduccion();
    }, 100);
}

/**
 * Inicializar módulo de inyección
 */
function initInyeccion() {
    console.log('🔧 [Inyección] Inicializando módulo...');

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

    console.log('🚀 [Inyección] Módulo listo');
}

// Exportar funciones si aplica Juan Sebastian
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initInyeccion,
        registrarInyeccion,
        actualizarCalculoProduccion
    };
}

// Inicializar cuando el DOM esté listo Juan Sebastian
document.addEventListener('DOMContentLoaded', function () {
    // Si estamos en la página de inyección, inicializar
    const inyeccionPage = document.getElementById('inyeccion-page');
    if (inyeccionPage && inyeccionPage.classList.contains('active')) {
        initInyeccion();
    }
});
// Exportar mÃ³dulos
window.ModuloInyeccion = { inicializar: initInyeccion };




