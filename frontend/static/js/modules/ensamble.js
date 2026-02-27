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
        this.initAutocompleteResponsable();
        this.intentarAutoSeleccionarResponsable();
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
            if (responsables) {
                // Mapear de objetos a strings (nombres) para el sistema de búsqueda
                this.responsablesData = responsables.map(r => typeof r === 'object' ? r.nombre : r);
            }

            // 2. Cargar Productos (Para Buje Origen)
            await this._cargarProductos();

            mostrarLoading(false);
        } catch (error) {
            console.error('Error cargando datos:', error);
            mostrarLoading(false);
        }
    },

    _cargarProductos: async function () {
        // Intentar desde cache compartida
        if (window.AppState?.sharedData?.productos?.length > 0) {
            this.productosData = window.AppState.sharedData.productos;
            console.log('📦 Productos desde cache:', this.productosData.length);
            return;
        }

        // Fallback: cargar directamente desde API
        try {
            const prods = await fetchData('/api/productos/listar');
            if (prods) {
                const items = prods?.productos || prods?.items || (Array.isArray(prods) ? prods : []);
                if (Array.isArray(items) && items.length > 0) {
                    this.productosData = items;
                    console.log('📦 Productos desde API directa:', this.productosData.length);
                    return;
                }
            }
        } catch (e) {
            console.warn('⚠️ Fallo carga directa de productos:', e);
        }

        // Último intento: esperar 1.5s por si cargarDatosCompartidos aún no termina
        console.log('⏳ Productos no disponibles aún, reintentando en 1.5s...');
        await new Promise(resolve => setTimeout(resolve, 1500));
        if (window.AppState?.sharedData?.productos?.length > 0) {
            this.productosData = window.AppState.sharedData.productos;
            console.log('📦 Productos cargados en reintento:', this.productosData.length);
        } else {
            console.error('❌ No se pudieron cargar productos para Ensamble');
        }
    },

    intentarAutoSeleccionarResponsable: function () {
        const input = document.getElementById('responsable-ensamble');
        if (!input) return;

        let nombreUsuario = null;

        if (window.AppState?.user?.name) {
            nombreUsuario = window.AppState.user.name;
        } else if (window.AuthModule?.currentUser?.nombre) {
            nombreUsuario = window.AuthModule.currentUser.nombre;
        }

        if (nombreUsuario) {
            input.value = nombreUsuario;
            console.log(`✅ [Ensamble] Responsable auto-asignado: ${nombreUsuario}`);
        } else {
            console.log('⏳ [Ensamble] Esperando usuario para auto-asignación...');
            const handler = () => {
                this.intentarAutoSeleccionarResponsable();
                window.removeEventListener('user-ready', handler);
            };
            window.addEventListener('user-ready', handler);

            // Polling fallback
            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                if (window.AppState?.user?.name) {
                    this.intentarAutoSeleccionarResponsable();
                    clearInterval(interval);
                    window.removeEventListener('user-ready', handler);
                }
                if (attempts > 10) clearInterval(interval);
            }, 500);
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
                    String(prod.codigo_sistema || '').toLowerCase().includes(query.toLowerCase()) ||
                    String(prod.descripcion || '').toLowerCase().includes(query.toLowerCase())
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

    isSubmitting: false,

    configurarEventos: function () {
        const form = document.getElementById('form-ensamble');
        if (form) {
            // Eliminar listener previo si existe para evitar duplicación
            form.onsubmit = null;
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                registrarEnsamble();
            });
        }

        document.getElementById('cantidad-ensamble')?.addEventListener('input', actualizarCalculoEnsamble);
        document.getElementById('pnc-ensamble')?.addEventListener('input', actualizarCalculoEnsamble);
        document.getElementById('ens-qty-bujes')?.addEventListener('input', actualizarCalculoEnsamble);

        // El mapeo se dispara desde initAutocompleteComponente al seleccionar

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
    if (ModuloEnsamble.isSubmitting) return;

    try {
        console.log('🚀 [Ensamble] Intentando registrar...');
        ModuloEnsamble.isSubmitting = true;
        mostrarLoading(true);

        const btnSubmit = document.querySelector('#form-ensamble button[type="submit"]');
        if (btnSubmit) btnSubmit.disabled = true;

        const cantidadBolsas = parseInt(document.getElementById('cantidad-ensamble')?.value) || 0;
        const pnc = parseInt(document.getElementById('pnc-ensamble')?.value) || 0;
        const qty = parseFloat(document.getElementById('ens-qty-bujes')?.value) || 1;

        // Cálculo: (Bolsas * QTY) - PNC = Total Piezas Buenas
        const totalPiezas = cantidadBolsas * qty;
        const cantidadReal = Math.max(0, totalPiezas - pnc);

        // NUEVA LÓGICA: Recopilar componentes del BOM si existe
        const bomItems = document.querySelectorAll('.bom-item');
        let componentes = [];

        if (bomItems && bomItems.length > 0) {
            bomItems.forEach(item => {
                const checkbox = item.querySelector('.bom-checkbox');
                if (checkbox && checkbox.checked) {
                    const dataRaw = item.querySelector('.bom-data')?.value;
                    if (dataRaw) {
                        const op = JSON.parse(dataRaw);
                        componentes.push({
                            buje_origen: op.buje_origen,
                            qty_unitaria: op.qty || op.qty_unitaria || 1
                        });
                    }
                }
            });
        }

        const datos = {
            fecha_inicio: document.getElementById('fecha-ensamble')?.value || '',
            responsable: document.getElementById('responsable-ensamble')?.value || '',
            hora_inicio: document.getElementById('hora-inicio-ensamble')?.value || '',
            hora_fin: document.getElementById('hora-fin-ensamble')?.value || '',
            codigo_producto: document.getElementById('ens-id-codigo')?.value || '', // Producto final
            buje_componente: document.getElementById('ens-buje-componente')?.value || '',
            qty_unitaria: qty,
            cantidad_bolsas: cantidadBolsas,
            cantidad_recibida: cantidadBolsas,
            cantidad_real: cantidadReal,
            total_piezas: totalPiezas,
            almacen_origen: document.getElementById('almacen-origen-ensamble')?.value || 'P. TERMINADO',
            almacen_destino: document.getElementById('almacen-destino-ensamble')?.value || 'PRODUCTO ENSAMBLADO',
            orden_produccion: document.getElementById('op-ensamble')?.value || '',
            pnc: pnc,
            criterio_pnc: document.getElementById('criterio-pnc-hidden-ensamble')?.value || '',
            observaciones: document.getElementById('observaciones-ensamble')?.value || '',
            componentes: componentes.length > 0 ? componentes : [] // Enviar lista si existe
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
            // Preparar datos para restauración
            const datosRestaurar = { ...datos };
            const metaConCallback = {
                ...resultado.undo_meta,
                restoreCallback: async () => {
                    // Restaurar valores Ensamble
                    document.getElementById('fecha-ensamble').value = datosRestaurar.fecha_inicio;
                    document.getElementById('responsable-ensamble').value = datosRestaurar.responsable;
                    document.getElementById('hora-inicio-ensamble').value = datosRestaurar.hora_inicio;
                    document.getElementById('hora-fin-ensamble').value = datosRestaurar.hora_fin;
                    document.getElementById('op-ensamble').value = datosRestaurar.orden_produccion;

                    // Trigger change confirmando mapeo
                    const bujeSelect = document.getElementById('ens-buje-componente');
                    if (bujeSelect) {
                        bujeSelect.value = datosRestaurar.buje_componente;
                        // Trigger change manual para actualizar IDs
                        if (typeof actualizarMapeoEnsamble === 'function') {
                            await actualizarMapeoEnsamble();
                        }
                    }

                    // Restaurar Lógica de Negocio (Almacenes)
                    document.getElementById('almacen-origen-ensamble').value = datosRestaurar.almacen_origen || '';
                    document.getElementById('almacen-destino-ensamble').value = datosRestaurar.almacen_destino || '';

                    // Restaurar cantidades (después de mapeo seguro)
                    document.getElementById('cantidad-ensamble').value = datosRestaurar.cantidad_bolsas;
                    document.getElementById('ens-qty-bujes').value = datosRestaurar.qty_unitaria; // Sobreescribe lo que traiga el mapeo si es diferente
                    document.getElementById('pnc-ensamble').value = datosRestaurar.pnc;
                    document.getElementById('criterio-pnc-hidden-ensamble').value = datosRestaurar.criterio_pnc;
                    document.getElementById('observaciones-ensamble').value = datosRestaurar.observaciones;
                    // Re-calcular
                    if (typeof actualizarCalculoEnsamble === 'function') actualizarCalculoEnsamble();
                    mostrarNotificacion('Formulario restaurado', 'info');
                }
            };
            mostrarNotificacion(`✅ ${resultado.mensaje || 'Ensamble registrado correctamente'}`, 'success', metaConCallback);
            document.getElementById('form-ensamble')?.reset();
            ModuloEnsamble.intentarAutoSeleccionarResponsable();

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
        ModuloEnsamble.isSubmitting = false;
        const btnSubmit = document.querySelector('#form-ensamble button[type="submit"]');
        if (btnSubmit) btnSubmit.disabled = false;
    }
}

async function actualizarMapeoEnsamble() {
    const bujeCode = document.getElementById('ens-buje-componente')?.value;
    const selectorContainer = document.getElementById('ens-opciones-selector');
    const bomSection = document.getElementById('ensamble-bom-section');
    const bomLista = document.getElementById('ensamble-bom-lista');

    // Limpiar UI anterior
    if (selectorContainer) selectorContainer.remove();
    if (bomSection) bomSection.style.display = 'none';
    if (bomLista) bomLista.innerHTML = '';

    if (!bujeCode) {
        document.getElementById('ens-id-codigo').value = '';
        document.getElementById('ens-qty-bujes').value = '1';
        return;
    }

    try {
        console.log('🔍 Buscando ensamble para:', bujeCode);
        const data = await fetchData(`/api/inyeccion/ensamble_desde_producto?codigo=${encodeURIComponent(bujeCode)}`);

        if (data && data.success) {
            // Si hay múltiples opciones, decidir si es BOM o Selector
            if (data.opciones && data.opciones.length > 0) {
                console.log('🔀 Múltiples registros encontrados:', data.opciones);

                // Detectar si es un BOM (Estructura de múltiples componentes para un mismo producto final)
                // Se asume BOM si la búsqueda fue por PRODUCTO FINAL y devolvió varias filas
                const esBOM = data.opciones.every(o => o.tipo === 'producto');

                if (esBOM) {
                    renderBOM(data.opciones);
                    // Llenar campos principales con el primer componente (compatibilidad)
                    document.getElementById('ens-id-codigo').value = data.opciones[0].codigo_ensamble || '';
                    document.getElementById('ens-qty-bujes').value = data.opciones[0].qty || 1;
                } else {
                    // Es un selector de opciones (Un componente usado en varios productos posibles)
                    mostrarSelectorOpciones(data.opciones);
                }
            } else if (data.codigo_ensamble) {
                // Una sola opción: asignar directamente
                document.getElementById('ens-id-codigo').value = data.codigo_ensamble || '';
                const qtyValue = data.qty || data.qty_unitaria || data.cantidad || 1;
                document.getElementById('ens-qty-bujes').value = qtyValue;
            }
            actualizarCalculoEnsamble();
        } else {
            document.getElementById('ens-id-codigo').value = 'NO DEFINIDO';
            document.getElementById('ens-qty-bujes').value = '1';
        }
    } catch (error) {
        console.error('❌ Error buscando mapeo:', error);
    }
}

/**
 * Renderiza la lista de componentes requeridos para el ensamble
 */
function renderBOM(opciones) {
    const bomSection = document.getElementById('ensamble-bom-section');
    const bomLista = document.getElementById('ensamble-bom-lista');
    if (!bomSection || !bomLista) return;

    bomSection.style.display = 'block';
    bomLista.innerHTML = opciones.map((op, idx) => `
        <div class="bom-item" style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; flex: 1; min-width: 150px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span style="font-weight: 600; font-size: 11px; color: #64748b; text-transform: uppercase;">
                    <i class="fas fa-puzzle-piece"></i> Componente ${idx + 1}
                </span>
                <input type="checkbox" checked class="bom-checkbox" data-idx="${idx}" style="width: 16px; height: 16px; cursor: pointer;" title="Incluir en el descuento de stock">
            </div>
            <div style="font-size: 15px; font-weight: 800; color: #1e293b; margin: 2px 0;">${op.buje_origen}</div>
            <div class="text-muted small" style="font-weight: 500;">
                Consumo: <span class="badge bg-light text-dark border">${op.qty} und</span>
            </div>
            <input type="hidden" class="bom-data" value='${JSON.stringify(op).replace(/'/g, "&apos;")}'>
        </div>
    `).join('');
}

/**
 * Muestra un mini-selector cuando un producto tiene múltiples opciones de componente
 * Por ejemplo: 9721 puede usar CB9721 o FR-9303
 */
function mostrarSelectorOpciones(opciones) {
    // Crear contenedor del selector
    const container = document.createElement('div');
    container.id = 'ens-opciones-selector';
    container.style.cssText = `
        background: linear-gradient(135deg, #fef3c7, #fde68a);
        border: 2px solid #f59e0b;
        border-radius: 10px;
        padding: 12px 16px;
        margin-top: 8px;
        animation: fadeIn 0.3s ease;
    `;

    container.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
            <i class="fas fa-exclamation-triangle" style="color: #d97706; font-size: 18px;"></i>
            <strong style="color: #92400e; font-size: 14px;">¿Con cuál componente se hizo?</strong>
        </div>
        <div id="ens-opciones-btns" style="display: flex; gap: 8px; flex-wrap: wrap;"></div>
    `;

    const btnsContainer = container.querySelector('#ens-opciones-btns');

    opciones.forEach((opcion, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.style.cssText = `
            flex: 1;
            min-width: 120px;
            padding: 10px 16px;
            border: 2px solid #d97706;
            border-radius: 8px;
            background: white;
            color: #92400e;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: center;
        `;
        btn.innerHTML = `<i class="fas fa-cube"></i> ${opcion.buje_origen}`;
        btn.addEventListener('mouseenter', () => {
            btn.style.background = '#f59e0b';
            btn.style.color = 'white';
            btn.style.transform = 'scale(1.03)';
        });
        btn.addEventListener('mouseleave', () => {
            if (!btn.classList.contains('selected')) {
                btn.style.background = 'white';
                btn.style.color = '#92400e';
                btn.style.transform = 'scale(1)';
            }
        });
        btn.addEventListener('click', () => {
            // Seleccionar esta opción
            document.getElementById('ens-id-codigo').value = opcion.codigo_ensamble || '';
            document.getElementById('ens-qty-bujes').value = opcion.qty || 1;
            actualizarCalculoEnsamble();

            // Marcar como seleccionado visualmente
            btnsContainer.querySelectorAll('button').forEach(b => {
                b.classList.remove('selected');
                b.style.background = 'white';
                b.style.color = '#92400e';
                b.style.transform = 'scale(1)';
            });
            btn.classList.add('selected');
            btn.style.background = '#059669';
            btn.style.color = 'white';
            btn.style.borderColor = '#059669';
            btn.style.transform = 'scale(1.03)';
            btn.innerHTML = `<i class="fas fa-check-circle"></i> ${opcion.buje_origen}`;

            console.log(`✅ Opción seleccionada: ${opcion.buje_origen} → ${opcion.codigo_ensamble} (QTY: ${opcion.qty})`);
        });
        btnsContainer.appendChild(btn);
    });

    // Insertar después del campo de Código Ensamble
    const codigoField = document.getElementById('ens-id-codigo');
    if (codigoField) {
        const parentGroup = codigoField.closest('.form-group');
        if (parentGroup) {
            parentGroup.appendChild(container);
        }
    }

    // Poner "Seleccionar..." en el campo hasta que elijan
    document.getElementById('ens-id-codigo').value = '⚠️ Seleccionar componente...';
    document.getElementById('ens-qty-bujes').value = '1';
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
