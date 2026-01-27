// =========================================
// M�DULO DE ENSAMBLE - VERSI�N CORREGIDA
// =========================================

// Estado privado del m�dulo
let defectosEnsamble = [];
let datosCompartidos = { responsables: [], productos: [], fichas: [] };

// ===== INICIALIZACI�N =====
const EnsambleModule = {
    async inicializar() {


        // Usar datos compartidos
        if (window.AppState && window.AppState.sharedData) {
            datosCompartidos = window.AppState.sharedData;

        }

        // 1. Cargar fichas t�cnicas primero (necesarias para poblar el select de productos)
        await this.cargarFichas();

        // 2. Poblar selects con datos
        this.poblarSelects();

        this.configurarEventos();
        this.inicializarFecha();


    },

    poblarSelects() {


        // Poblar responsables
        const selectResp = document.getElementById('responsable-ensamble');
        if (selectResp && datosCompartidos.responsables) {
            selectResp.innerHTML = '<option value="">Seleccionar...</option>';
            datosCompartidos.responsables.forEach(resp => {
                const option = document.createElement('option');
                option.value = resp;
                option.textContent = resp;
                selectResp.appendChild(option);
            });

        }

        // Poblar PRODUCTO FINAL (ID CODIGO)
        // Corregido: Ahora el select es para el producto que estamos haciendo.
        const selectProd = document.getElementById('ens-id-codigo');
        if (selectProd && datosCompartidos.fichas) {
            selectProd.innerHTML = '<option value="">-- Seleccionar Producto --</option>';

            // Usamos las fichas t�cnicas para listar los productos finales
            datosCompartidos.fichas.forEach(ficha => {
                if (ficha.id_codigo) {
                    const option = document.createElement('option');
                    option.value = ficha.id_codigo;
                    option.textContent = ficha.id_codigo;
                    selectProd.appendChild(option);
                }
            });

        }
    },

    async cargarFichas() {
        try {

            const response = await fetch('/api/obtener_fichas');
            const fichas = await response.json();

            if (Array.isArray(fichas)) {
                datosCompartidos.fichas = fichas;

            }
        } catch (error) {
            console.error('? Error cargando fichas:', error);
        }
    },

    configurarEventos() {


        // Formulario principal
        const form = document.getElementById('form-ensamble');
        if (form) {
            form.removeEventListener('submit', registrarEnsamble);
            form.addEventListener('submit', registrarEnsamble);
        }

        // C�lculo autom�tico
        const entradaInput = document.getElementById('cantidad-ensamble');
        const pncInput = document.getElementById('pnc-ensamble');
        const qtyBujeInput = document.getElementById('ens-qty-bujes');

        if (entradaInput) entradaInput.addEventListener('input', actualizarCalculoEnsamble);
        if (pncInput) pncInput.addEventListener('input', actualizarCalculoEnsamble);
        if (qtyBujeInput) qtyBujeInput.addEventListener('input', actualizarCalculoEnsamble);

        // AUTO-COMPLETADO (Trigger: Al seleccionar un PRODUCTO FINAL)
        const productSelect = document.getElementById('ens-id-codigo');
        if (productSelect) {
            productSelect.addEventListener('change', function () {
                const bujeInput = document.getElementById('ens-buje-componente');
                const qtyInput = document.getElementById('ens-qty-bujes');
                const idCodigoSeleccionado = this.value;

                if (idCodigoSeleccionado) {
                    // Buscar en fichas
                    if (datosCompartidos.fichas) {
                        const ficha = datosCompartidos.fichas.find(f => f.id_codigo === idCodigoSeleccionado);

                        if (ficha) {
                            // 1. Mostrar el Buje Componente autom�ticamente
                            if (bujeInput) {
                                bujeInput.value = ficha.buje_ensamble;

                            }

                            // 2. Autocompletar QTY
                            if (qtyInput) {
                                qtyInput.value = ficha.qty || 1;
                            }
                        } else {
                            console.warn('?? No se encontr� ficha t�cnica para este producto');
                            if (bujeInput) bujeInput.value = '';
                            if (qtyInput) qtyInput.value = 1;
                        }
                    }

                    // Actualizar c�lculos
                    actualizarCalculoEnsamble();
                }
            });
        }

        // Modal de defectos - listener de apertura
        const modalElement = document.getElementById('modalDefectosEnsamble');
        if (modalElement) {
            modalElement.addEventListener('shown.bs.modal', function () {

                cargarCriteriosPNCEnsamble();
            });
        }

        // Enter en cantidad del modal
        const cantidadModal = document.getElementById('modal-cantidad-ensamble');
        if (cantidadModal) {
            cantidadModal.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    agregarDefectoEnsamble();
                }
            });
        }


    },

    inicializarFecha() {
        const fechaInput = document.getElementById('fecha-ensamble');
        if (fechaInput && !fechaInput.value) {
            fechaInput.value = new Date().toISOString().split('T')[0];
        }
    }
};

// ===== FUNCIONES DE CRITERIOS PNC =====
function cargarCriteriosPNCEnsamble() {
    fetch('/api/obtener_criterios_pnc/ensamble')
        .then(response => response.json())
        .then(data => {
            if (data.success && Array.isArray(data.criterios)) {
                const selectModal = document.getElementById('modal-criterio-ensamble');
                if (selectModal) {
                    selectModal.innerHTML = '<option value="">-- Seleccionar defecto --</option>';
                    data.criterios.forEach(criterio => {
                        const option = document.createElement('option');
                        option.value = criterio;
                        option.textContent = criterio;
                        selectModal.appendChild(option);
                    });
                }
            }
        })
        .catch(error => console.error('? Error cargando criterios PNC:', error));
}

// ===== FUNCIONES DE LISTA VISUAL =====
function actualizarListaVisualEnsamble() {
    const ul = document.getElementById('modal-lista-defectos-ensamble');
    const totalSpan = document.getElementById('modal-total-ensamble');

    if (!ul || !totalSpan) return;

    ul.innerHTML = '';
    let total = 0;

    defectosEnsamble.forEach((d, i) => {
        total += d.cantidad;
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.style.cssText = 'background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 8px;';

        li.innerHTML = `
            <span style="font-weight: 500; color: #334155;">${d.criterio}</span>
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="background: #ef4444; color: white; padding: 4px 12px; border-radius: 6px; font-weight: 600;">${d.cantidad}</span>
                <i class="fas fa-times" onclick="eliminarDefectoEnsamble(${i})" style="cursor: pointer; color: #ef4444; font-size: 16px;" title="Eliminar"></i>
            </div>
        `;

        ul.appendChild(li);
    });

    totalSpan.textContent = total;

    const inputTotalPNC = document.getElementById('pnc-ensamble');
    if (inputTotalPNC) {
        inputTotalPNC.value = total;
    }
}

function actualizarCalculoEnsamble() {
    const cantidadInput = parseInt(document.getElementById('cantidad-ensamble')?.value) || 0;
    const qtyBujes = parseInt(document.getElementById('ens-qty-bujes')?.value) || 1;
    const pnc = parseInt(document.getElementById('pnc-ensamble')?.value) || 0;

    const bujesNecesarios = cantidadInput * qtyBujes;
    const ensamblesBuenos = Math.max(0, cantidadInput - pnc);

    const bujesNecDiv = document.getElementById('bujes-necesarios');
    const ensamProdDiv = document.getElementById('ensambles-producir');
    const ensamBuenosDiv = document.getElementById('ensambles-buenos');

    // Funci�n auxiliar para formato (si no existe, usa valor directo)
    const format = (n) => typeof formatNumber === 'function' ? formatNumber(n) : n;

    if (bujesNecDiv) bujesNecDiv.textContent = format(bujesNecesarios);
    if (ensamProdDiv) ensamProdDiv.textContent = format(cantidadInput);
    if (ensamBuenosDiv) ensamBuenosDiv.textContent = format(ensamblesBuenos);


}

// ===== FUNCIONES DEL MODAL =====
window.agregarDefectoEnsamble = function () {
    const sel = document.getElementById('modal-criterio-ensamble');
    const inp = document.getElementById('modal-cantidad-ensamble');
    const criterio = sel?.value;
    const cantidad = parseInt(inp?.value);

    if (!criterio || !cantidad || cantidad <= 0) {
        alert('Ingresa un criterio y cantidad v�lidos');
        return;
    }

    defectosEnsamble.push({ criterio, cantidad });
    sel.value = '';
    inp.value = '';
    inp.focus();

    actualizarListaVisualEnsamble();
    actualizarCalculoEnsamble();
};

window.eliminarDefectoEnsamble = function (index) {
    defectosEnsamble.splice(index, 1);
    actualizarListaVisualEnsamble();
    actualizarCalculoEnsamble();
};

window.resetPNCEnsamble = function () {
    defectosEnsamble = [];
    actualizarListaVisualEnsamble();
    const sel = document.getElementById('modal-criterio-ensamble');
    const inp = document.getElementById('modal-cantidad-ensamble');
    if (sel) sel.value = '';
    if (inp) inp.value = '';
    const pncInput = document.getElementById('pnc-ensamble');
    if (pncInput) pncInput.value = 0;
};

window.aplicarDefectosEnsamble = function () {
    const totalDefectos = defectosEnsamble.reduce((sum, d) => sum + d.cantidad, 0);
    const pncInput = document.getElementById('pnc-ensamble');
    if (pncInput) pncInput.value = totalDefectos;

    const modalElement = document.getElementById('modalDefectosEnsamble');
    if (modalElement) {
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) modal.hide();
    }
    actualizarCalculoEnsamble();
};

// ===== REGISTRO PRINCIPAL =====
async function registrarEnsamble(e) {
    if (e) e.preventDefault();

    try {
        mostrarLoading(true);

        const entrada = parseInt(document.getElementById('cantidad-ensamble')?.value) || 0;
        const pnc = parseInt(document.getElementById('pnc-ensamble')?.value) || 0;
        const cantidad_real = Math.max(0, entrada - pnc);

        const datos = {
            fecha_inicio: document.getElementById('fecha-ensamble')?.value,
            responsable: document.getElementById('responsable-ensamble')?.value,
            codigo_producto: document.getElementById('ens-id-codigo')?.value,
            cantidad_recibida: entrada,
            pnc: pnc,
            cantidad_real: cantidad_real,
            qty_unitaria: parseInt(document.getElementById('ens-qty-bujes')?.value) || 1,
            almacen_origen: document.getElementById('almacen-origen-ensamble')?.value || 'P. TERMINADO',
            almacen_destino: document.getElementById('almacen-destino-ensamble')?.value || 'PRODUCTO ENSAMBLADO',
            hora_inicio: document.getElementById('hora-inicio-ensamble')?.value || '00:00',
            hora_fin: document.getElementById('hora-fin-ensamble')?.value || '00:00',
            orden_produccion: document.getElementById('op-ensamble')?.value || '',
            observaciones: document.getElementById('observaciones-ensamble')?.value || '',
            criterio_pnc: defectosEnsamble.map(d => d.criterio).join(', '),
            defectos: defectosEnsamble
        };



        // Validaciones
        if (!datos.codigo_producto) {
            alert('Selecciona un Producto Final');
            mostrarLoading(false);
            return;
        }

        if (datos.cantidad_recibida <= 0) {
            alert('Ingresa una cantidad v�lida');
            mostrarLoading(false);
            return;
        }

        const response = await fetch('/api/ensamble', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await response.json();

        if (response.ok && resultado.success) {
            alert(resultado.mensaje || 'Ensamble registrado correctamente');

            // Limpiar formulario y resumen
            document.getElementById('form-ensamble').reset();
            document.getElementById('pnc-ensamble').value = 0;

            // Limpiar resumen visual
            if (document.getElementById('bujes-necesarios')) document.getElementById('bujes-necesarios').textContent = '0';
            if (document.getElementById('ensambles-producir')) document.getElementById('ensambles-producir').textContent = '0';
            if (document.getElementById('ensambles-buenos')) document.getElementById('ensambles-buenos').textContent = '0';

            const fechaInput = document.getElementById('fecha-ensamble');
            if (fechaInput) fechaInput.value = new Date().toISOString().split('T')[0];

            resetPNCEnsamble();
        } else {
            alert(resultado.error || 'Error desconocido del servidor');
        }
    } catch (error) {
        console.error('? Error registrando ensamble:', error);
        alert('Error fatal: ' + error.message);
    } finally {
        mostrarLoading(false);
    }
}

// ===== EXPORTAR =====
window.ModuloEnsamble = {
    inicializar: EnsambleModule.inicializar.bind(EnsambleModule)
};
window.initEnsamble = EnsambleModule.inicializar.bind(EnsambleModule);
window.registrarEnsamble = registrarEnsamble;


