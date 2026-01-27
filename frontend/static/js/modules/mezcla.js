// ============================================
// mezcla.js - Lógica de Mezcla Material
// ============================================

/**
 * Cargar datos de Mezcla
 */
async function cargarDatosMezcla() {
    try {
        console.log('🧪 Cargando datos de Mezcla...');
        mostrarLoading(true);

        // Cargar responsables y máquinas desde el cache compartido
        if (window.AppState.sharedData.responsables) {
            actualizarSelectMezcla('responsable-mezcla', window.AppState.sharedData.responsables);
        }
        
        if (window.AppState.sharedData.maquinas) {
            actualizarSelectMezcla('maquina-mezcla', window.AppState.sharedData.maquinas);
        }

        console.log('✅ Datos de Mezcla cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos de mezcla:', error);
        mostrarLoading(false);
    }
}

function actualizarSelectMezcla(selectId, datos) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    select.innerHTML = '<option value="">-- Seleccionar --</option>';
    datos.forEach(item => {
        const option = document.createElement('option');
        const val = typeof item === 'object' ? (item.nombre || item.id) : item;
        option.value = val;
        option.textContent = val;
        select.appendChild(option);
    });
}

/**
 * Registrar Mezcla
 */
async function registrarMezcla() {
    try {
        mostrarLoading(true);
        
        const datos = {
            fecha: document.getElementById('fecha-mezcla')?.value || '',
            responsable: document.getElementById('responsable-mezcla')?.value || '',
            maquina: document.getElementById('maquina-mezcla')?.value || '',
            virgen: document.getElementById('virgen-mezcla')?.value || '0',
            molido: document.getElementById('molido-mezcla')?.value || '0',
            pigmento: document.getElementById('pigmento-mezcla')?.value || '0',
            observaciones: document.getElementById('observaciones-mezcla')?.value || ''
        };
        
        if (!datos.responsable || !datos.maquina) {
            mostrarNotificacion('⚠️ Datos incompletos', 'warning');
            mostrarLoading(false);
            return;
        }
        
        const response = await fetch('/api/mezcla', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        
        const res = await response.json();
        if (res.success) {
            mostrarNotificacion('✅ Mezcla registrada!', 'success');
            document.getElementById('form-mezcla')?.reset();
        } else {
            mostrarNotificacion(`❌ Error: ${res.error}`, 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarNotificacion('Error de conexión', 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Calcular proporción en tiempo real
 */
function calcularProporcionMezcla() {
    const v = parseFloat(document.getElementById('virgen-mezcla').value) || 0;
    const m = parseFloat(document.getElementById('molido-mezcla').value) || 0;
    const total = v + m;
    
    const display = document.getElementById('info-proporcion');
    if (display && total > 0) {
        const pV = ((v/total)*100).toFixed(1);
        const pM = ((m/total)*100).toFixed(1);
        display.innerHTML = `
            <div style="display:flex; justify-content: space-between; font-size: 14px; font-weight: 600;">
                <span style="color: #2563eb;">Virgen: ${pV}%</span>
                <span style="color: #059669;">Molido: ${pM}%</span>
                <span style="color: #1e293b;">Total: ${total.toFixed(2)} Kg</span>
            </div>
        `;
    }
}

function initMezcla() {
    console.log('🔧 Inicializando módulo de mezcla...');
    cargarDatosMezcla();
    
    document.getElementById('virgen-mezcla')?.addEventListener('input', calcularProporcionMezcla);
    document.getElementById('molido-mezcla')?.addEventListener('input', calcularProporcionMezcla);
    
    document.getElementById('form-mezcla')?.addEventListener('submit', (e) => {
        e.preventDefault();
        registrarMezcla();
    });
}

window.initMezcla = initMezcla;
window.ModuloMezcla = { inicializar: initMezcla };
