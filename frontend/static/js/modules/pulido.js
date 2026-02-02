// ============================================
// pulido.js - Lógica de Pulido (SMART SEARCH)
// ============================================

let defectosPulido = [];

const ModuloPulido = {
    productosData: [],
    responsablesData: [],

    init: async function () {
        console.log('🔧 [Pulido] Inicializando módulo Smart...');
        await this.cargarDatos();
        this.configurarEventos();
        this.initAutocompleteProducto();
        this.initAutocompleteResponsable();

        // Inicializar Lote con fecha de hoy
        const loteInput = document.getElementById('lote-pulido');
        if (loteInput && !loteInput.value) {
            loteInput.value = new Date().toISOString().split('T')[0];
        }
    },

    // Alias para compatibilidad con app.js
    inicializar: function () {
        return this.init();
    },

    cargarDatos: async function () {
        try {
            console.log('📦 Cargando datos de pulido...');
            mostrarLoading(true);

            // 1. Cargar Responsables
            const responsables = await fetchData('/api/obtener_responsables');
            if (responsables) {
                this.responsablesData = responsables;
            }

            // 2. Cargar Productos (Cache Compartido)
            if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
                this.productosData = window.AppState.sharedData.productos;
            } else {
                const prods = await fetchData('/api/productos/listar');
                this.productosData = prods.items || prods;
            }

            mostrarLoading(false);
        } catch (error) {
            console.error('Error cargando datos:', error);
            mostrarLoading(false);
        }
    },

    // ---------------------------------------------------------
    // SMART SEARCH: PRODUCTO
    // ---------------------------------------------------------
    initAutocompleteProducto: function () {
        const input = document.getElementById('codigo-producto-pulido');
        const suggestionsDiv = document.getElementById('pulido-producto-suggestions');

        if (!input || !suggestionsDiv) return;

        let debounceTimer;

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();

            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            debounceTimer = setTimeout(() => {
                const resultados = this.productosData.filter(prod =>
                    (prod.codigo_sistema || '').toLowerCase().includes(query.toLowerCase()) ||
                    (prod.descripcion || '').toLowerCase().includes(query.toLowerCase())
                ).slice(0, 15);

                this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                    input.value = item.codigo_sistema || item.codigo;
                    suggestionsDiv.classList.remove('active');
                }, true);
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    // ---------------------------------------------------------
    // SMART SEARCH: RESPONSABLE
    // ---------------------------------------------------------
    initAutocompleteResponsable: function () {
        const input = document.getElementById('responsable-pulido');
        const suggestionsDiv = document.getElementById('pulido-responsable-suggestions');

        if (!input || !suggestionsDiv) return;

        input.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            if (query.length < 1) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            const resultados = this.responsablesData.filter(resp =>
                resp.toLowerCase().includes(query)
            );

            this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                input.value = item;
                suggestionsDiv.classList.remove('active');
            }, false);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    renderSuggestions: function (container, items, onSelect, isProduct) {
        if (items.length === 0) {
            container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
            container.classList.add('active');
            return;
        }

        container.innerHTML = items.map(item => {
            if (isProduct) {
                return `
                <div class="suggestion-item" data-val="${item.codigo_sistema || item.codigo}">
                    <strong>${item.codigo_sistema || item.codigo}</strong><br>
                    <small>${item.descripcion}</small>
                </div>`;
            } else {
                return `<div class="suggestion-item" data-val="${item}">${item}</div>`;
            }
        }).join('');

        container.querySelectorAll('.suggestion-item').forEach((div, index) => {
            div.addEventListener('click', () => {
                onSelect(items[index]);
            });
        });

        container.classList.add('active');
    },

    configurarEventos: function () {
        const form = document.getElementById('form-pulido');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                registrarPulido();
            });
        }

        const entradaInput = document.getElementById('entrada-pulido');
        const pncInput = document.getElementById('pnc-pulido');

        if (entradaInput) entradaInput.addEventListener('input', actualizarCalculoPulido);
        if (pncInput) pncInput.addEventListener('input', actualizarCalculoPulido);
    },

    // Referencias a funciones de defectos para mantenerlas encapsuladas si se quiere refactorizar
    // pero por ahora usamos las globales
    abrirModalDefectos: () => window.abrirModalDefectos(),
    agregarDefectoPulido: () => window.agregarDefectoPulido(),
    eliminarDefectoPulido: (i) => window.eliminarDefectoPulido(i),
    aplicarDefectosPulido: () => window.aplicarDefectosPulido()
};

// ==========================================
// FUNCIONES GLOBALES (Legacy/Compatibilidad)
// ==========================================

async function registrarPulido() {
    // Copia de la lógica de registro original
    try {
        console.log('🚀 [Pulido] Intentando registrar...');
        mostrarLoading(true);

        const datos = {
            fecha_inicio: document.getElementById('fecha-pulido')?.value || '',
            responsable: document.getElementById('responsable-pulido')?.value || '', // Input
            hora_inicio: document.getElementById('hora-inicio-pulido')?.value || '',
            hora_fin: document.getElementById('hora-fin-pulido')?.value || '',
            codigo_producto: document.getElementById('codigo-producto-pulido')?.value || '', // Input
            lote: document.getElementById('lote-pulido')?.value || '',
            orden_produccion: document.getElementById('orden-produccion-pulido')?.value || '',
            cantidad_recibida: document.getElementById('entrada-pulido')?.value || '0',
            cantidad_real: document.getElementById('bujes-buenos-pulido')?.value || '0',
            pnc: document.getElementById('pnc-pulido')?.value || '0',
            observaciones: document.getElementById('observaciones-pulido')?.value || ''
        };

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

        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje || 'Pulido registrado correctamente'}`, 'success');
            document.getElementById('form-pulido')?.reset();
            defectosPulido = [];
            actualizarListaDefectosPulido();
            actualizarCalculoPulido();
        } else {
            const msgError = resultado.error || resultado.mensaje || 'Error desconocido';
            mostrarNotificacion(`❌ Error: ${msgError}`, 'error');
        }
    } catch (error) {
        console.error('❌ [Pulido] Error crítico:', error);
        mostrarNotificacion(`❌ Error de conexión: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

function actualizarCalculoPulido() {
    const entradaInput = document.getElementById('entrada-pulido');
    const pncInput = document.getElementById('pnc-pulido');
    const buenosInput = document.getElementById('bujes-buenos-pulido');

    let entrada = Number(entradaInput?.value) || 0;
    let pnc = Number(pncInput?.value) || 0;

    if (pnc > entrada) {
        mostrarNotificacion('⚠️ PNC no puede ser mayor que la cantidad recibida', 'warning');
        pnc = entrada;
        if (pncInput) pncInput.value = pnc;
    }

    const totalReal = Math.max(0, entrada - pnc);
    const displaySalida = document.getElementById('salida-calculada');
    const formulaCalc = document.getElementById('formula-calc-pulido');
    const piezasBuenasDisplay = document.getElementById('piezas-buenas-pulido');

    if (displaySalida) displaySalida.textContent = formatNumber(totalReal);
    if (formulaCalc) formulaCalc.textContent = `Recibida: ${formatNumber(entrada)} - PNC: ${formatNumber(pnc)} = ${formatNumber(totalReal)} piezas pulidas`;
    if (piezasBuenasDisplay) piezasBuenasDisplay.textContent = `Total: ${formatNumber(totalReal)} piezas buenas`;

    if (buenosInput) buenosInput.value = totalReal;
}

// FORMAT NUMBER
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// LOGICA DEFECTOS (KEEPING GLOBAL AS PER ORIGINAL FILE TO AVOID BREAKING)
// ... (The original defect logic was global variable based, so we keep `defectosPulido` global)

window.abrirModalDefectos = function () {
    const modal = new bootstrap.Modal(document.getElementById('modalDefectosPulido'));
    modal.show();
};

window.agregarDefectoPulido = function () {
    const criterio = document.getElementById('modal-criterio-pulido').value;
    const cantidad = Number(document.getElementById('modal-cantidad-pulido').value) || 0;

    if (!criterio || cantidad <= 0) {
        mostrarNotificacion('⚠️ Seleccione defecto y cantidad', 'warning');
        return;
    }

    defectosPulido.push({ criterio, cantidad });
    document.getElementById('modal-cantidad-pulido').value = '';
    actualizarListaDefectosPulido();
};

window.eliminarDefectoPulido = function (index) {
    defectosPulido.splice(index, 1);
    actualizarListaDefectosPulido();
};

window.actualizarListaDefectosPulido = function () {
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
};

window.aplicarDefectosPulido = function () {
    let total = 0;
    defectosPulido.forEach(d => total += d.cantidad);

    const inputPNC = document.getElementById('pnc-pulido');
    if (inputPNC) {
        inputPNC.value = total;
        inputPNC.dispatchEvent(new Event('input'));
    }

    const modal = bootstrap.Modal.getInstance(document.getElementById('modalDefectosPulido'));
    if (modal) modal.hide();

    mostrarNotificacion(`✅ ${total} piezas PNC aplicadas`, 'success');
};


// EXPORTS
window.initPulido = () => ModuloPulido.init();
window.ModuloPulido = ModuloPulido;
