// ============================================
// facturacion.js - Lógica de Facturación
// ============================================

/**
 * Cargar datos de Facturación
 */
async function cargarDatosFacturacion() {
    try {
        console.log('📦 Cargando datos de Facturación...');
        mostrarLoading(true);

        // Cargar clientes
        const clientes = await fetchData('/api/obtener_clientes');
        if (clientes && Array.isArray(clientes)) {
            actualizarSelectFacturacion('cliente-facturacion', clientes);
        }

        // Usar productos del cache compartido
        if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
            console.log('✅ Usando productos del cache compartido en Facturación');
            const datalist = document.getElementById('fac-productos-list');
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
            console.warn('⚠️ No hay productos en cache compartido para Facturación');
        }

        console.log('✅ Datos de Facturación cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos:', error);
        mostrarLoading(false);
    }
}


function initAutocompleteProducto() {
    const input = document.getElementById('producto-facturacion');
    const suggestionsDiv = document.getElementById('facturacion-producto-suggestions');

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
 * Actualizar select en Facturación
 */
function actualizarSelectFacturacion(selectId, datos) {
    // Deprecated for smart search, but kept if needed or can be removed. 
    // Actually, we need to adapt this data for the smart search cache.
    window.AppState.sharedData.clientes = datos;
}

function initAutocompleteCliente() {
    const input = document.getElementById('cliente-facturacion');
    const suggestionsDiv = document.getElementById('facturacion-cliente-suggestions');

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
            const clientes = window.AppState.sharedData.clientes || [];
            const resultados = clientes.filter(c =>
                (c.nombre || '').toLowerCase().includes(query.toLowerCase()) ||
                (c.id || '').toString().includes(query)
            ).slice(0, 15);

            renderSuggestionsCliente(suggestionsDiv, resultados, (item) => {
                input.value = item.nombre;
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

function renderSuggestionsCliente(container, items, onSelect) {
    if (items.length === 0) {
        container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
        container.classList.add('active');
        return;
    }

    container.innerHTML = items.map(item => `
        <div class="suggestion-item" data-val="${item.id}">
            <strong>${item.nombre}</strong><br>
            <small>ID: ${item.id}</small>
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
 * Registrar Facturación
 */
async function registrarFacturacion() {
    try {
        mostrarLoading(true);

        const datos = {
            cliente: document.getElementById('cliente-facturacion')?.value || '',
            codigo_producto: document.getElementById('producto-facturacion')?.value || '',
            cantidad_vendida: document.getElementById('cantidad-facturacion')?.value || '0',
            precio_unitario: document.getElementById('precio-facturacion')?.value || '0',
            orden_compra: document.getElementById('orden-compra-facturacion')?.value || '',
            fecha_inicio: document.getElementById('fecha-facturacion')?.value || new Date().toISOString().split('T')[0],
            observaciones: document.getElementById('observaciones-facturacion')?.value || ''
        };

        if (!datos.cliente || !datos.codigo_producto) {
            mostrarNotificacion('⚠️ Selecciona cliente y producto', 'error');
            mostrarLoading(false);
            return;
        }

        const response = await fetch('/api/facturacion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();

        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje}`, 'success');
            document.getElementById('form-facturacion')?.reset();
            setTimeout(() => location.reload(), 1500);
        } else {
            mostrarNotificacion(`❌ ${resultado.error || 'Error'}`, 'error');
        }
    } catch (error) {
        console.error('Error register:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

/**
 * Cálculo de total en tiempo real
 */
function actualizarTotalFacturacion() {
    const cantidad = parseFloat(document.getElementById('cantidad-facturacion')?.value) || 0;
    const precio = parseFloat(document.getElementById('precio-facturacion')?.value) || 0;
    const total = cantidad * precio;

    const displayTotal = document.getElementById('total-facturacion');
    if (displayTotal) {
        displayTotal.textContent = `$ ${formatNumber(total)}`;
    }
}

/**
 * Inicializar módulo
 */
function initFacturacion() {
    console.log('🔧 Inicializando módulo de Facturación...');
    cargarDatosFacturacion();

    // Init Smart Search
    initAutocompleteProducto();
    initAutocompleteCliente();

    document.getElementById('cantidad-facturacion')?.addEventListener('input', actualizarTotalFacturacion);
    document.getElementById('precio-facturacion')?.addEventListener('input', actualizarTotalFacturacion);

    // Si hay un formulario, prevenir el submit por defecto y usar nuestra función
    document.getElementById('form-facturacion')?.addEventListener('submit', (e) => {
        e.preventDefault();
        registrarFacturacion();
    });

    console.log('✅ Módulo de Facturación inicializado');
}

// Exportar
window.initFacturacion = initFacturacion;
window.ModuloFacturacion = { inicializar: initFacturacion };
