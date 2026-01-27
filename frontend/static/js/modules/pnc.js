// ============================================
// pnc.js - Lógica de PNC (Producto No Conforme)
// ============================================

/**
 * Cargar datos de PNC
 */
async function cargarDatosPNC() {
    try {
        console.log('📦 Cargando datos de PNC...');
        mostrarLoading(true);
        
        // Generar ID automático
        const timestamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 14);
        const idPNC = `PNC-${timestamp}`;
        const inputId = document.getElementById('id-pnc');
        if (inputId) inputId.value = idPNC;
        
        // Fecha actual
        const hoy = new Date().toISOString().split('T')[0];
        const fechaInput = document.getElementById('fecha-pnc');
        if (fechaInput) fechaInput.value = hoy;
        
        // Usar productos del cache compartido
        if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
            console.log('✅ Usando productos del cache compartido en PNC');
            const datalist = document.getElementById('productos-pnc-list');
            if (datalist) {
                datalist.innerHTML = '';
                window.AppState.sharedData.productos.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.codigo_sistema || p.codigo;
                    opt.textContent = `${p.codigo_sistema || p.codigo} - ${p.descripcion}`;
                    datalist.appendChild(opt);
                });
            }
        } else {
            console.warn('⚠️ No hay productos en cache compartido para PNC');
        }
        
        // Configurar botones de criterio
        configurarCriteriosPNC();
        
        console.log('✅ Datos de PNC cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos:', error);
        mostrarLoading(false);
    }
}

/**
 * Configurar botones de criterio
 */
function configurarCriteriosPNC() {
    const botones = document.querySelectorAll('.criterio-btn');
    const inputHidden = document.getElementById('criterio-pnc-hidden');
    
    botones.forEach(btn => {
        btn.addEventListener('click', function() {
            botones.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const criterio = this.dataset.criterio;
            if (inputHidden) inputHidden.value = criterio;
            console.log('Criterio seleccionado:', criterio);
        });
    });
}

/**
 * Registrar PNC
 */
async function registrarPNC() {
    try {
        mostrarLoading(true);
        
        const datos = {
            fecha: document.getElementById('fecha-pnc')?.value || '',
            id_pnc: document.getElementById('id-pnc')?.value || '',
            codigo_producto: document.getElementById('codigo-producto-pnc')?.value || '',
            cantidad: document.getElementById('cantidad-pnc')?.value || '0',
            criterio: document.getElementById('criterio-pnc-hidden')?.value || '',
            codigo_ensamble: document.getElementById('codigo-ensamble-pnc')?.value || ''
        };
        
        if (!datos.codigo_producto?.trim()) {
            mostrarNotificacion('⚠️ Ingresa código del producto', 'error');
            mostrarLoading(false);
            return;
        }
        
        const response = await fetch('/api/pnc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        
        const resultado = await response.json();
        
        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');
            document.getElementById('form-pnc')?.reset();
            setTimeout(() => cargarDatosPNC(), 1500);
        } else {
            mostrarNotificacion(`❌ ${resultado.error || 'Error'}`, 'error');
        }
    } catch (error) {
        console.error('Error registrar:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Inicializar módulo
 */
function initPnc() {
    console.log('🔧 Inicializando módulo de PNC...');
    cargarDatosPNC();
    console.log('✅ Módulo de PNC inicializado');
}

// Exportar
window.initPnc = initPnc;
window.ModuloPNC = { inicializar: initPnc };
