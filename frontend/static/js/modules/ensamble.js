// ============================================
// ensamble.js - Lógica de Ensamble (SMART SEARCH)
// ============================================

const ModuloEnsamble = {
    productosData: [],
    responsablesData: [],

    init: async function () {
        console.log('🔧 [Ensamble] Inicializando módulo Smart...');
        await this.cargarDatos();
        this.configurarEventos();
        this.initAutocompleteComponente();
        // this.initAutocompleteResponsable(); // Eliminado por solicitud de usuario (Auto-fill simple)
    },

    // Alias para compatibilidad con app.js
    inicializar: function () {
        return this.init();
    },

    cargarDatos: async function () {
        try {
            console.log('📦 Cargando datos de ensamble...');
            mostrarLoading(true);

            // 1. Cargar Responsables
            const responsables = await fetchData('/api/obtener_responsables');
            if (responsables) this.responsablesData = responsables;

            // 2. Cargar Productos (Para Buje Origen)
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
    // SMART SEARCH: BUJE ORIGEN (COMPONENTE)
    // ---------------------------------------------------------
    initAutocompleteComponente: function () {
        const input = document.getElementById('ens-buje-componente');
        const suggestionsDiv = document.getElementById('ensamble-componente-suggestions');

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

                    // IMPORTANTE: Trigger manual del mapeo de ensamble
                    actualizarMapeoEnsamble();

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
        const input = document.getElementById('responsable-ensamble');
        const suggestionsDiv = document.getElementById('ensamble-responsable-suggestions');

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
        if (isProduct) {
            renderProductSuggestions(container, items, onSelect);
        } else {
            if (items.length === 0) {
                container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
                container.classList.add('active');
                return;
            }

            container.innerHTML = items.map(item => `<div class="suggestion-item" data-val="${item}">${item}</div>`).join('');

            container.querySelectorAll('.suggestion-item').forEach((div, index) => {
                div.addEventListener('click', () => {
                    onSelect(items[index]);
                });
            });

            container.classList.add('active');
        }
    },

    configurarEventos: function () {
        const form = document.getElementById('form-ensamble');
        if (form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                registrarEnsamble();
            });
        }

        document.getElementById('cantidad-ensamble')?.addEventListener('input', actualizarCalculoEnsamble);
        document.getElementById('pnc-ensamble')?.addEventListener('input', actualizarCalculoEnsamble);
        document.getElementById('ens-qty-bujes')?.addEventListener('input', actualizarCalculoEnsamble);

        // Listener en input manual o pegado
        document.getElementById('ens-buje-componente')?.addEventListener('change', actualizarMapeoEnsamble);

        // Configurar botón de defectos
        const btnDefectos = document.getElementById('btn-defectos-ensamble');
        if (btnDefectos) {
            btnDefectos.replaceWith(btnDefectos.cloneNode(true));
            const newBtn = document.getElementById('btn-defectos-ensamble');
            newBtn.addEventListener('click', function () {
                if (typeof window.abrirModalEnsamble === 'function') {
                    window.abrirModalEnsamble();
                } else {
                    console.error('❌ Función window.abrirModalEnsamble no encontrada');
                }
            });
        }
    }
};

// ==========================================
// FUNCIONES GLOBALES (Legacy/Compatibilidad)
// ==========================================

async function registrarEnsamble() {
    try {
        console.log('🚀 [Ensamble] Intentando registrar...');
        mostrarLoading(true);

        const cantidadBolsas = parseInt(document.getElementById('cantidad-ensamble')?.value) || 0;
        const pnc = parseInt(document.getElementById('pnc-ensamble')?.value) || 0;
        const qty = parseFloat(document.getElementById('ens-qty-bujes')?.value) || 1;

        // Cálculo: (Bolsas * QTY) - PNC = Total Piezas Buenas
        const totalPiezas = cantidadBolsas * qty;
        const cantidadReal = Math.max(0, totalPiezas - pnc);

        const datos = {
            fecha_inicio: document.getElementById('fecha-ensamble')?.value || '',
            responsable: document.getElementById('responsable-ensamble')?.value || '',
            hora_inicio: document.getElementById('hora-inicio-ensamble')?.value || '',
            hora_fin: document.getElementById('hora-fin-ensamble')?.value || '',
            codigo_producto: document.getElementById('ens-id-codigo')?.value || '', // Producto final
            buje_componente: document.getElementById('ens-buje-componente')?.value || '',
            qty_unitaria: qty,
            cantidad_bolsas: cantidadBolsas, // Explicitly sending bags
            cantidad_recibida: cantidadBolsas, // Keeping for backward compat if needed, or remove if backend updated
            cantidad_real: cantidadReal, // Piezas Buenas
            total_piezas: totalPiezas, // Raw total pieces
            almacen_origen: document.getElementById('almacen-origen-ensamble')?.value || 'P. TERMINADO',
            almacen_destino: document.getElementById('almacen-destino-ensamble')?.value || 'PRODUCTO ENSAMBLADO',
            orden_produccion: document.getElementById('op-ensamble')?.value || '',
            pnc: pnc,
            criterio_pnc: document.getElementById('criterio-pnc-hidden-ensamble')?.value || '',
            observaciones: document.getElementById('observaciones-ensamble')?.value || ''
        };

        if (!datos.codigo_producto || datos.codigo_producto === 'NO DEFINIDO') {
            mostrarNotificacion('⚠️ Selecciona un buje componente válido', 'error');
            mostrarLoading(false);
            return;
        }

        console.log('📤 [Ensamble] DATOS ENVIADOS:', JSON.stringify(datos, null, 2));

        const response = await fetch('/api/ensamble', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();
        console.log('📥 [Ensamble] RESPUESTA SERVIDOR:', resultado);

        if (response.ok && resultado.success) {
            mostrarNotificacion(`✅ ${resultado.mensaje || 'Ensamble registrado correctamente'}`, 'success');
            document.getElementById('form-ensamble')?.reset();

            // Reset state
            window.tmpDefectosEnsamble = [];
            actualizarCalculoEnsamble();
        } else {
            const errorMsg = resultado.error || resultado.mensaje || 'Error desconocido';
            mostrarNotificacion(`❌ Error: ${errorMsg}`, 'error');
        }
    } catch (error) {
        console.error('❌ [Ensamble] Error crítico:', error);
        mostrarNotificacion(`❌ Error de conexión: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}

async function actualizarMapeoEnsamble() {
    const bujeCode = document.getElementById('ens-buje-componente')?.value;
    if (!bujeCode) {
        document.getElementById('ens-id-codigo').value = '';
        document.getElementById('ens-qty-bujes').value = '1';
        return;
    }

    try {
        console.log('🔍 Buscando ensamble para:', bujeCode);
        const data = await fetchData(`/api/inyeccion/ensamble_desde_producto?codigo=${encodeURIComponent(bujeCode)}`);

        if (data && data.success) {
            document.getElementById('ens-id-codigo').value = data.codigo_ensamble || '';
            const qtyValue = data.qty || data.qty_unitaria || data.cantidad || 1;
            document.getElementById('ens-qty-bujes').value = qtyValue;
            actualizarCalculoEnsamble();
        } else {
            document.getElementById('ens-id-codigo').value = 'NO DEFINIDO';
            document.getElementById('ens-qty-bujes').value = '1';
        }
    } catch (error) {
        console.error('❌ Error buscando mapeo:', error);
    }
}

function actualizarCalculoEnsamble() {
    const cantidadBolsas = parseInt(document.getElementById('cantidad-ensamble')?.value) || 0;
    const pnc = parseInt(document.getElementById('pnc-ensamble')?.value) || 0;
    const qtyPerEnsamble = parseFloat(document.getElementById('ens-qty-bujes')?.value) || 1;

    const totalPiezas = cantidadBolsas * qtyPerEnsamble;
    const ensamblesBuenos = Math.max(0, totalPiezas - pnc);

    const displaySalida = document.getElementById('produccion-calculada-ensamble');
    const formulaCalc = document.getElementById('formula-calc-ensamble');
    const piezasBuenasDisplay = document.getElementById('piezas-buenas-ensamble');

    if (displaySalida) displaySalida.textContent = formatNumber(ensamblesBuenos);
    if (formulaCalc) formulaCalc.textContent = `Bolsas: ${formatNumber(cantidadBolsas)} × QTY: ${qtyPerEnsamble} = ${formatNumber(totalPiezas)} piezas`;
    if (piezasBuenasDisplay) piezasBuenasDisplay.textContent = `Total: ${formatNumber(totalPiezas)} - PNC: ${pnc} = ${formatNumber(ensamblesBuenos)} buenas`;
}

function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

window.initEnsamble = () => ModuloEnsamble.init();
window.ModuloEnsamble = ModuloEnsamble;
