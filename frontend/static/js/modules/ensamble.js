// ============================================
// ensamble.js - Lógica de Ensamble (Refactorizada)
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

        // Usar productos del cache compartido para el BUJE COMPONENTE
        if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
            console.log('✅ Usando productos del cache compartido en Ensamble (Bujes)');
            // Poblamos el select de BUJE COMPONENTE (ens-buje-componente)
            actualizarSelectEnsamble('ens-buje-componente', window.AppState.sharedData.productos);
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
                // Para el buje componente, usamos el codigo de sistema o codigo base
                option.value = item.codigo_sistema || item.codigo || '';
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
        console.log('🚀 [Ensamble] Intentando registrar...');
        mostrarLoading(true);

        const cantidadTotal = parseInt(document.getElementById('cantidad-ensamble')?.value) || 0;
        const pnc = parseInt(document.getElementById('pnc-ensamble')?.value) || 0;
        const cantidadReal = Math.max(0, cantidadTotal - pnc);

        // Mapeo exacto esperado por app.py Juan Sebastian
        const datos = {
            fecha_inicio: document.getElementById('fecha-ensamble')?.value || '',
            responsable: document.getElementById('responsable-ensamble')?.value || '',
            hora_inicio: document.getElementById('hora-inicio-ensamble')?.value || '',
            hora_fin: document.getElementById('hora-fin-ensamble')?.value || '',
            codigo_producto: document.getElementById('ens-id-codigo')?.value || '',
            buje_componente: document.getElementById('ens-buje-componente')?.value || '',
            qty_unitaria: document.getElementById('ens-qty-bujes')?.value || '1',
            cantidad_recibida: cantidadTotal,
            cantidad_real: cantidadReal,
            almacen_origen: document.getElementById('almacen-origen-ensamble')?.value || 'P. TERMINADO',
            almacen_destino: document.getElementById('almacen-destino-ensamble')?.value || 'PRODUCTO ENSAMBLADO',
            orden_produccion: document.getElementById('op-ensamble')?.value || '',
            pnc: pnc,
            observaciones: document.getElementById('observaciones-ensamble')?.value || ''
        };

        console.log('📦 [Ensamble] Datos preparados:', datos);

        if (!datos.codigo_producto || datos.codigo_producto === 'NO DEFINIDO') {
            mostrarNotificacion('⚠️ Selecciona un buje componente válido que genere un ensamble', 'error');
            mostrarLoading(false);
            return;
        }

        const response = await fetch('/api/ensamble', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();
        console.log('📥 [Ensamble] Respuesta:', resultado);

        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje || 'Ensamble registrado correctamente'}`, 'success');

            // Limpiar formulario sin recargar
            document.getElementById('form-ensamble')?.reset();
            actualizarCalculoEnsamble(); // Resetear resumen visual

            // Si el dashboard está abierto abajo, actualizarlo
            if (window.actualizarDashboard) window.actualizarDashboard();

        } else {
            const errorMsg = resultado.error || resultado.mensaje || 'Error desconocido en el servidor';
            mostrarNotificacion(`❌ Error: ${errorMsg}`, 'error');
        }
    } catch (error) {
        console.error('❌ [Ensamble] Error crítico:', error);
        mostrarNotificacion(`❌ Error de conexión: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Buscar mapeo de ensamble cuando cambia el buje componente
 */
async function actualizarMapeoEnsamble() {
    const bujeCode = document.getElementById('ens-buje-componente')?.value;
    if (!bujeCode) {
        document.getElementById('ens-id-codigo').value = '';
        document.getElementById('ens-qty-bujes').value = '1';
        return;
    }

    try {
        console.log('🔍 Buscando ensamble para:', bujeCode);
        // Usar el endpoint existente que ya hace este trabajo
        const data = await fetchData(`/api/inyeccion/ensamble_desde_producto?codigo=${bujeCode}`);

        if (data && data.success) {
            console.log('✅ Mapeo encontrado:', data);

            const inputEnsamble = document.getElementById('ens-id-codigo');
            const inputQty = document.getElementById('ens-qty-bujes');

            if (inputEnsamble) inputEnsamble.value = data.codigo_ensamble || '';
            if (inputQty) {
                inputQty.value = data.qty || '1';
                console.log('📊 Actualizando QTY a:', inputQty.value);
            }

            // Actualizar cálculos
            actualizarCalculoEnsamble();
        } else {
            console.warn('⚠️ No se encontró mapeo para este buje');
            document.getElementById('ens-id-codigo').value = 'NO DEFINIDO';
            document.getElementById('ens-qty-bujes').value = '1';
        }
    } catch (error) {
        console.error('Error buscando mapeo:', error);
    }
}

/**
 * Actualizar cálculo de ensamble en tiempo real
 */
function actualizarCalculoEnsamble() {
    const cantidad = parseInt(document.getElementById('cantidad-ensamble')?.value) || 0;
    const pnc = parseInt(document.getElementById('pnc-ensamble')?.value) || 0;
    const qtyPerEnsamble = parseFloat(document.getElementById('ens-qty-bujes')?.value) || 1;

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
    console.log('🔧 Inicializando módulo de Ensamble (Refactorizado)...');
    cargarDatosEnsamble();

    // Configurar envío del formulario Juan Sebastian
    const form = document.getElementById('form-ensamble');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            registrarEnsamble();
        });
    }

    // Listeners para el mapeo automático
    document.getElementById('ens-buje-componente')?.addEventListener('change', actualizarMapeoEnsamble);

    // Listeners para el cálculo en tiempo real
    document.getElementById('cantidad-ensamble')?.addEventListener('input', actualizarCalculoEnsamble);
    document.getElementById('pnc-ensamble')?.addEventListener('input', actualizarCalculoEnsamble);
    document.getElementById('ens-qty-bujes')?.addEventListener('input', actualizarCalculoEnsamble);

    console.log('✅ Módulo de Ensamble inicializado');
}

// Exportar
window.initEnsamble = initEnsamble;
window.ModuloEnsamble = { inicializar: initEnsamble };
