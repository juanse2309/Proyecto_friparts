// mezcla.js - MÓDULO DE MEZCLA DE MATERIAL
// ===========================================

const ModuloMezcla = (() => {
    let isSubmitting = false;

    /**
     * Inicializa el módulo, configura eventos y carga datos.
     */
    function inicializar() {


        cargarSelectores();
        configurarEventos();
        establecerFechaActual();


    }

    /**
     * Carga responsables y máquinas desde AppState.
     */
    function cargarSelectores() {
        const { responsables, maquinas } = window.AppState.sharedData || {};

        const selectResp = document.getElementById('responsable-mezcla');
        if (selectResp && responsables) {
            selectResp.innerHTML = '<option value="">-- Seleccionar --</option>';
            responsables.forEach(r => {
                const option = document.createElement('option');
                option.value = r;
                option.textContent = r;
                selectResp.appendChild(option);
            });
        }

        const selectMaq = document.getElementById('maquina-mezcla');
        if (selectMaq && maquinas) {
            selectMaq.innerHTML = '<option value="">-- Seleccionar --</option>';
            maquinas.forEach(m => {
                const option = document.createElement('option');
                option.value = m;
                option.textContent = m;
                selectMaq.appendChild(option);
            });
        }
    }

    /**
     * Configura los eventos del formulario y calculadora.
     */
    function configurarEventos() {
        const form = document.getElementById('form-mezcla');
        if (form) {
            form.removeEventListener('submit', registrarMezcla);
            form.addEventListener('submit', registrarMezcla);
        }

        const inputs = ['virgen-mezcla', 'molido-mezcla'];
        inputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('input', actualizarIndicadorProporcion);
        });
    }

    /**
     * Calcula la proporción de molido vs virgen Jonathan.
     */
    function actualizarIndicadorProporcion() {
        const virgen = parseFloat(document.getElementById('virgen-mezcla').value) || 0;
        const molido = parseFloat(document.getElementById('molido-mezcla').value) || 0;
        const total = virgen + molido;

        const infoDiv = document.getElementById('info-proporcion');
        if (!infoDiv) return;

        if (total > 0) {
            const porcMolido = ((molido / total) * 100).toFixed(1);
            const colorClass = porcMolido > 30 ? 'text-danger fw-bold' : 'text-primary fw-bold';

            infoDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span><i class="fas fa-balance-scale"></i> Total Mezcla: <strong>${total.toFixed(2)} kg</strong></span>
                    <span class="${colorClass}">Molido: ${porcMolido}%</span>
                </div>
            `;
        } else {
            infoDiv.innerHTML = '<small class="text-muted">Ingresa pesos para ver la proporción</small>';
        }
    }

    function establecerFechaActual() {
        const input = document.getElementById('fecha-mezcla');
        if (input && !input.value) {
            input.value = new Date().toISOString().split('T')[0];
        }
    }

    /**
     * Registro en backend Jonathan.
     */
    async function registrarMezcla(e) {
        if (e) e.preventDefault();
        if (isSubmitting) return;

        const data = {
            fecha: document.getElementById('fecha-mezcla').value,
            responsable: document.getElementById('responsable-mezcla').value,
            maquina: document.getElementById('maquina-mezcla').value,
            virgen: document.getElementById('virgen-mezcla').value,
            molido: document.getElementById('molido-mezcla').value,
            pigmento: document.getElementById('pigmento-mezcla').value || 0,
            observaciones: document.getElementById('observaciones-mezcla').value
        };

        if (!data.responsable || !data.maquina || (parseFloat(data.virgen) + parseFloat(data.molido)) <= 0) {
            mostrarNotificacion('Completa los campos y asegura un peso válido', 'warning');
            return;
        }

        try {
            isSubmitting = true;
            mostrarLoading(true);

            const res = await fetch('/api/mezcla/guardar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await res.json();

            if (res.ok) {
                mostrarNotificacion(`✅ Mezcla guardada con éxito. Lote: ${result.lote || 'N/A'}`, 'success');
                document.getElementById('form-mezcla').reset();
                actualizarIndicadorProporcion();
                establecerFechaActual();
            } else {
                throw new Error(result.message || result.error || 'Error al guardar');
            }

        } catch (error) {
            mostrarNotificacion(error.message, 'error');
        } finally {
            isSubmitting = false;
            mostrarLoading(false);
        }
    }

    return { inicializar };
})();

// Scope global Jonathan
window.ModuloMezcla = ModuloMezcla;
window.initMezcla = ModuloMezcla.inicializar;
