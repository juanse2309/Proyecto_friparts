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
            const datalist = document.getElementById('pnc-productos-list');
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
        btn.addEventListener('click', function () {
            botones.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const criterio = this.dataset.criterio;
            if (inputHidden) inputHidden.value = criterio;
            console.log('Criterio seleccionado:', criterio);
        });
    });
}

function initAutocompleteProducto() {
    const input = document.getElementById('pnc-manual-producto');
    const suggestionsDiv = document.getElementById('pnc-manual-producto-suggestions');

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
            const products = window.AppState.sharedData.productos || [];
            const resultados = products.filter(prod =>
                (prod.codigo_sistema || '').toLowerCase().includes(query.toLowerCase()) ||
                (prod.descripcion || '').toLowerCase().includes(query.toLowerCase())
            ).slice(0, 15);

            renderSuggestions(suggestionsDiv, resultados, (item) => {
                input.value = item.codigo_sistema || item.codigo;
                suggestionsDiv.classList.remove('active');
            });
        }, 300);
    });

    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
            suggestionsDiv.classList.remove('active');
        }
    });
}

function renderSuggestions(container, items, onSelect) {
    if (items.length === 0) {
        container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
        container.classList.add('active');
        return;
    }

    container.innerHTML = items.map(item => `
        <div class="suggestion-item" data-val="${item.codigo_sistema || item.codigo}">
            <strong>${item.codigo_sistema || item.codigo}</strong><br>
            <small>${item.descripcion}</small>
        </div>
    `).join('');

    container.querySelectorAll('.suggestion-item').forEach((div, index) => {
        div.addEventListener('click', () => {
            onSelect(items[index]);
        });
    });

    container.classList.add('active');
}

/**
 * Registar PNC
 */
async function registrarPNC() {
    try {
        mostrarLoading(true);

        const datos = {
            fecha: document.getElementById('pnc-manual-fecha')?.value || '',
            id_pnc: document.getElementById('id-pnc')?.value || '', // Check if this ID exists in HTML, might need fix
            codigo_producto: document.getElementById('pnc-manual-producto')?.value || '',
            cantidad: document.getElementById('pnc-manual-cantidad')?.value || '0',
            criterio: document.getElementById('pnc-manual-criterio')?.value || '',
            // Mapping html ID to logic
            codigo_ensamble: document.getElementById('pnc-manual-ensamble')?.value || ''
        };
        // ... rest of logic
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
            document.getElementById('form-manual-pnc')?.reset();
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
    initAutocompleteProducto();
    console.log('✅ Módulo de PNC inicializado');
}

// Exportar
window.initPnc = initPnc;
window.ModuloPNC = { inicializar: initPnc };
