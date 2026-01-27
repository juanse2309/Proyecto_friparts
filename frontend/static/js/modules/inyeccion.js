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

        console.log('???? Datos a enviar (22 campos):', datos);

        // ??? VALIDACI??N
        if (!datos.codigo_producto || datos.codigo_producto.trim() === '') {
            mostrarNotificacion('??? Ingresa c??digo del producto', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.cantidad_real || datos.cantidad_real <= 0) {
            mostrarNotificacion('??? Ingresa disparos v??lidos', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.responsable || datos.responsable.trim() === '') {
            mostrarNotificacion('??? Selecciona responsable', 'error');
            mostrarLoading(false);
            return;
        }

        if (!datos.maquina || datos.maquina.trim() === '') {
            mostrarNotificacion('??? Selecciona m??quina', 'error');
            mostrarLoading(false);
            return;
        }

        console.log('??? Validaci??n pasada, enviando...');

        // ENVIAR AL SERVIDOR
        const response = await fetch('/api/inyeccion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();
        console.log('Respuesta del servidor:', resultado);

        if (response.ok && resultado.success) {
            mostrarNotificacion(`??? ${resultado.mensaje}`, 'success');

            // Limpiar formulario
            document.getElementById('form-inyeccion').reset();

            // Restaurar valores por defecto
            document.getElementById('cavidades-inyeccion').value = 1;
            document.getElementById('pnc-inyeccion').value = 0;
            document.getElementById('produccion-calculada').textContent = '0';
            document.getElementById('formula-calc').textContent = 'Disparos: 0 ?? Cavidades: 1 = 0 piezas';

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
            mostrarNotificacion(`??? ${errores}`, 'error');
        }
    } catch (error) {
        console.error('Error registrando inyecci??n:', error);
        mostrarNotificacion(`??? Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Actualizar c??lculo de producci??n en tiempo real
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
 * Autocompletar c??digo de ensamble cuando se selecciona producto
 */
async function autocompletarCodigoEnsamble() {
    const codigoProducto = document.getElementById('codigo-producto-inyeccion')?.value;
    const codigoEnsambleField = document.getElementById('codigo-ensamble-inyeccion');

    if (!codigoProducto || !codigoEnsambleField) return;

    try {
        // Mostrar loading en el campo
        codigoEnsambleField.value = 'Buscando...';
        codigoEnsambleField.classList.add('loading');

        // Buscar informaci??n del producto
        // Usar endpoint correcto para obtener ensamble
        const response = await fetch(`/api/inyeccion/ensamble_desde_producto?codigo=${encodeURIComponent(codigoProducto)}`);
        if (!response.ok) {
            console.warn('⚠️ No se pudo obtener ensamble para:', codigoProducto);
            return;
        }
        const data = await response.json();

        if (data.success && data.codigo_ensamble) {
            codigoEnsambleField.value = data.codigo_ensamble;
            console.log(`✅ Ensamble autocompletado: ${data.codigo_ensamble}`);
        } else {
            codigoEnsambleField.value = '';
        }

        codigoEnsambleField.classList.remove('loading');

    } catch (error) {
        console.error('Error obteniendo c??digo ensamble:', error);
        codigoEnsambleField.value = codigoProducto; // Fallback al c??digo del producto
    } finally {
        codigoEnsambleField.classList.remove('loading');
    }
}

/**
 * Formatear n??mero con separadores de miles
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Configurar eventos para inyecci??n
 */
function configurarEventosInyeccion() {
    // Elementos del formulario
    const cantidadInput = document.getElementById('cantidad-inyeccion');
    const cavidadesInput = document.getElementById('cavidades-inyeccion');
    const pncInput = document.getElementById('pnc-inyeccion');
    const codigoProductoInput = document.getElementById('codigo-producto-inyeccion');
    const formInyeccion = document.getElementById('form-inyeccion');

    // Eventos para c??lculo en tiempo real
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
            console.log('???? Enviando formulario de inyecci??n...');
            registrarInyeccion();
        });
    }

    // Inicializar c??lculo al cargar
    setTimeout(() => {
        actualizarCalculoProduccion();
    }, 100);
}

/**
 * Inicializar m??dulo de inyecci??n
 */
function initInyeccion() {
    console.log('???? Inicializando m??dulo de inyecci??n...');

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

    console.log('??? M??dulo de inyecci??n inicializado');
}

// Exportar funciones (si usas m??dulos ES6)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initInyeccion,
        registrarInyeccion,
        actualizarCalculoProduccion
    };
}

// Inicializar cuando el DOM est?? listo
document.addEventListener('DOMContentLoaded', function () {
    // Si estamos en la p??gina de inyecci??n, inicializar
    const inyeccionPage = document.getElementById('inyeccion-page');
    if (inyeccionPage && inyeccionPage.classList.contains('active')) {
        initInyeccion();
    }
});
// Exportar mÃ³dulos
window.ModuloInyeccion = { inicializar: initInyeccion };




