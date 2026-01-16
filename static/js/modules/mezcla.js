// static/js/modules/mezcla.js

// Función de inicialización que app.js está buscando
function initMezcla() {
    console.log('🧪 Inicializando módulo de Mezcla...');
    
    configurarFormularioMezcla();
    configurarCalculadoraProporcion();
}

function configurarCalculadoraProporcion() {
    // Calcular porcentaje de recuperación en tiempo real
    const inputs = ['virgen-mezcla', 'molido-mezcla'];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', actualizarIndicadorProporcion);
    });
}

function actualizarIndicadorProporcion() {
    const virgen = parseFloat(document.getElementById('virgen-mezcla').value) || 0;
    const molido = parseFloat(document.getElementById('molido-mezcla').value) || 0;
    const total = virgen + molido;

    const infoDiv = document.getElementById('info-proporcion');
    if (!infoDiv) return;

    if (total > 0) {
        const porcMolido = ((molido / total) * 100).toFixed(1);
        const colorClass = porcMolido > 30 ? 'text-danger' : 'text-success'; // Ejemplo: Alerta si > 30% molido
        
        infoDiv.innerHTML = `
            <small class="fw-bold">Total Mezcla: ${total.toFixed(2)} kg</small><br>
            <small class="${colorClass}">Proporción Molido: ${porcMolido}%</small>
        `;
    } else {
        infoDiv.innerHTML = '';
    }
}

function configurarFormularioMezcla() {
    const form = document.getElementById('form-mezcla');
    if (!form) return; // Si no estamos en la página correcta, salir

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (!confirm('¿Están correctos los pesos de la mezcla?')) return;

        window.mostrarLoading(true);

        try {
            const data = {
                responsable: document.getElementById('responsable-mezcla').value,
                maquina: document.getElementById('maquina-mezcla').value,
                virgen: document.getElementById('virgen-mezcla').value,
                molido: document.getElementById('molido-mezcla').value,
                pigmento: document.getElementById('pigmento-mezcla').value || 0,
                observaciones: document.getElementById('observaciones-mezcla').value
            };

            const response = await fetch('/api/mezcla/guardar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                window.mostrarNotificacion(`Mezcla registrada. Lote: ${result.lote}`, 'success');
                form.reset();
                document.getElementById('info-proporcion').innerHTML = ''; // Limpiar calc
            } else {
                throw new Error(result.message || 'Error desconocido');
            }

        } catch (error) {
            console.error('Error:', error);
            window.mostrarNotificacion(error.message, 'error');
        } finally {
            window.mostrarLoading(false);
        }
    });
}

// Exportar al scope global
window.initMezcla = initMezcla;
