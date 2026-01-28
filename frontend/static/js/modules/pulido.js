// ============================================
// pulido.js - Lógica de Pulido
// ============================================

let defectosPulido = [];

/**
 * Cargar datos de Pulido
 */
async function cargarDatosPulido() {
    try {
        console.log('🔄 Cargando datos de pulido...');
        mostrarLoading(true);

        // Cargar responsables
        const responsables = await fetchData('/api/obtener_responsables');
        if (responsables && Array.isArray(responsables)) {
            actualizarSelectPulido('responsable-pulido', responsables);
        }

        // Usar productos del cache compartido
        if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
            console.log('✅ Usando productos del cache compartido en Pulido');
            const datalist = document.getElementById('productos-list');
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
            console.warn('⚠️ No hay productos en cache compartido para Pulido');
        }

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
    select.innerHTML = '<option value="">-- Seleccionar --</option>';

    if (datos && Array.isArray(datos)) {
        datos.forEach(item => {
            const option = document.createElement('option');
            if (typeof item === 'object') {
                const val = item.nombre || item.id || item.codigo || '';
                option.value = val;
                option.textContent = val;
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
 * Registrar Pulido
 */
async function registrarPulido() {
    try {
        console.log('🚀 [Pulido] Intentando registrar...');
        mostrarLoading(true);

        // Mapeo exacto de lo que espera el backend (app.py)
        const datos = {
            fecha_inicio: document.getElementById('fecha-pulido')?.value || '',
            responsable: document.getElementById('responsable-pulido')?.value || '',
            hora_inicio: document.getElementById('hora-inicio-pulido')?.value || '',
            hora_fin: document.getElementById('hora-fin-pulido')?.value || '',
            codigo_producto: document.getElementById('codigo-producto-pulido')?.value || '',
            lote: document.getElementById('lote-pulido')?.value || '',
            orden_produccion: document.getElementById('orden-produccion-pulido')?.value || '',
            cantidad_recibida: document.getElementById('entrada-pulido')?.value || '0',
            cantidad_real: document.getElementById('bujes-buenos-pulido')?.value || '0',
            pnc: document.getElementById('pnc-pulido')?.value || '0',
            observaciones: document.getElementById('observaciones-pulido')?.value || ''
        };

        console.log('📦 [Pulido] Datos a enviar:', datos);

        if (!datos.codigo_producto?.trim()) {
            mostrarNotificacion('⚠️ Ingresa código del producto', 'error');
            mostrarLoading(false);
            return;
        }

        const response = await fetch('/api/pulido', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();
        console.log('📥 [Pulido] Respuesta:', resultado);

        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje || 'Pulido registrado correctamente'}`, 'success');

            // Limpiar formulario sin recargar la página
            document.getElementById('form-pulido')?.reset();
            defectosPulido = [];
            actualizarListaDefectosPulido();
            actualizarCalculoPulido(); // Resetear visualmente el resumen

        } else {
            // Mostrar error técnico detallado para depuración
            const msgError = resultado.error || resultado.mensaje || 'Error desconocido en el servidor';
            mostrarNotificacion(`❌ Error: ${msgError}`, 'error');
            console.error('❌ [Pulido] Error del servidor:', msgError);
        }
    } catch (error) {
        console.error('❌ [Pulido] Error crítico:', error);
        mostrarNotificacion(`❌ Error de conexión: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Cálculo en tiempo real
 */
function actualizarCalculoPulido() {
    const entrada = parseInt(document.getElementById('entrada-pulido')?.value) || 0;
    const pnc = parseInt(document.getElementById('pnc-pulido')?.value) || 0;
    const totalReal = Math.max(0, entrada - pnc);

    const displaySalida = document.getElementById('salida-calculada');
    const formulaCalc = document.getElementById('formula-calc-pulido');
    const piezasBuenasDisplay = document.getElementById('piezas-buenas-pulido');

    if (displaySalida) displaySalida.textContent = formatNumber(totalReal);
    if (formulaCalc) {
        formulaCalc.textContent = `Recibida: ${formatNumber(entrada)} - PNC: ${formatNumber(pnc)} = ${formatNumber(totalReal)} piezas pulidas`;
    }
    if (piezasBuenasDisplay) {
        piezasBuenasDisplay.textContent = `Total: ${formatNumber(totalReal)} piezas buenas`;
    }

    // Actualizar también el campo de bujes buenos
    const inputBuenos = document.getElementById('bujes-buenos-pulido');
    if (inputBuenos) inputBuenos.value = totalReal;
}

/**
 * Lógica del Modal de Defectos (PNC)
 */
function abrirModalDefectos() {
    const modal = new bootstrap.Modal(document.getElementById('modalDefectosPulido'));
    modal.show();
}

function agregarDefectoPulido() {
    const criterio = document.getElementById('modal-criterio-pulido').value;
    const cantidad = parseInt(document.getElementById('modal-cantidad-pulido').value) || 0;

    if (!criterio || cantidad <= 0) {
        mostrarNotificacion('⚠️ Seleccione defecto y cantidad', 'warning');
        return;
    }

    defectosPulido.push({ criterio, cantidad });
    document.getElementById('modal-cantidad-pulido').value = '';
    actualizarListaDefectosPulido();
}

function eliminarDefectoPulido(index) {
    defectosPulido.splice(index, 1);
    actualizarListaDefectosPulido();
}

function actualizarListaDefectosPulido() {
    const lista = document.getElementById('modal-lista-defectos-pulido');
    const totalSpan = document.getElementById('modal-total-pulido');
    if (!lista || !totalSpan) return;

    lista.innerHTML = '';
    let total = 0;

    defectosPulido.forEach((d, index) => {
        total += d.cantidad;
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.innerHTML = `
            <span><strong>${d.criterio}</strong>: ${d.cantidad}</span>
            <button onclick="eliminarDefectoPulido(${index})" class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></button>
        `;
        lista.appendChild(li);
    });

    totalSpan.textContent = total;
}

function aplicarDefectosPulido() {
    let total = 0;
    defectosPulido.forEach(d => total += d.cantidad);

    const inputPNC = document.getElementById('pnc-pulido');
    if (inputPNC) {
        inputPNC.value = total;
        // Disparar evento input para recalcular piezas buenas
        inputPNC.dispatchEvent(new Event('input'));
    }

    const modal = bootstrap.Modal.getInstance(document.getElementById('modalDefectosPulido'));
    if (modal) modal.hide();

    mostrarNotificacion(`✅ ${total} piezas PNC aplicadas`, 'success');
}

/**
 * Inicializar módulo
 */
function initPulido() {
    console.log('🔧 Inicializando módulo de Pulido...');
    cargarDatosPulido();

    // Configurar envío del formulario Juan Sebastian
    const form = document.getElementById('form-pulido');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            registrarPulido();
        });
    }

    document.getElementById('entrada-pulido')?.addEventListener('input', actualizarCalculoPulido);
    document.getElementById('pnc-pulido')?.addEventListener('input', actualizarCalculoPulido);

    console.log('✅ Módulo de Pulido inicializado');
}

// Exportar
window.initPulido = initPulido;
window.ModuloPulido = {
    inicializar: initPulido,
    abrirModalDefectos,
    agregarDefectoPulido,
    eliminarDefectoPulido,
    aplicarDefectosPulido
};

// Hacer funciones globales para onclick
window.agregarDefectoPulido = agregarDefectoPulido;
window.eliminarDefectoPulido = eliminarDefectoPulido;
window.aplicarDefectosPulido = aplicarDefectosPulido;
