/**
 * ModuloRotacion.js
 * Gestión de rotación de inventario y prioridades de compra.
 */

if (!window.ModuloRotacionState) {
    window.ModuloRotacionState = {
        cargando: false,
        cargado: false,
        cache: []
    };
}

window.ModuloRotacion = (function () {
    let filtroTipoActual = 'TODOS';
    let filtroClaseActual = 'TODOS';

    async function inicializar() {
        console.log('🔄 Inicializando Módulo de Rotación...');
        await cargarPrioridades();

        // Evento para limpiar búsqueda al cambiar de pestaña
        const search = document.getElementById('rot-search-global');
        if (search) {
            search.addEventListener('input', () => {
                filtrarGlobal();
            });
        }
    }

    async function cargarPrioridades() {
        if (window.ModuloRotacionState.cargando || window.ModuloRotacionState.cargado) {
            return;
        }
        window.ModuloRotacionState.cargando = true;
        try {
            if (typeof window.mostrarLoading === 'function') window.mostrarLoading(true);
            const response = await fetch('/api/procura/rotacion/prioridades');
            const result = await response.json();

            if (result.status === 'success') {
                window.ModuloRotacionState.cache = result.data.prioridades || result.data || [];
                window.ModuloRotacionState.cargado = true;
                window.ModuloRotacionState.cargando = false;
                renderizarDashboard(window.ModuloRotacionState.cache);
                aplicarFiltrosCruzados();
                console.log('✅ Prioridades actualizadas');
            } else {
                console.error('Error al cargar prioridades:', result.message);
            }
        } catch (error) {
            console.error('Error fetch rotacion:', error);
        } finally {
            window.ModuloRotacionState.cargando = false;
            if (typeof window.mostrarLoading === 'function') window.mostrarLoading(false);
        }
    }

    function renderizarDashboard(data) {
        const total = data.length;
        const criticos = data.filter(d => d.semaforo === 'ROJO').length;
        const precaucion = data.filter(d => d.semaforo === 'AMARILLO').length;
        const ok = data.filter(d => d.semaforo === 'VERDE').length;

        if (document.getElementById('rot-count-total')) {
            document.getElementById('rot-count-total').innerText = total;
            document.getElementById('rot-count-a').innerText = criticos;
            document.getElementById('rot-count-caution').innerText = precaucion;
            document.getElementById('rot-count-ok').innerText = ok;
        }

        const miniCounter = document.getElementById('mini-alert-count');
        if (miniCounter) {
            miniCounter.innerHTML = `<span class="text-danger fw-bold">${criticos} urgentes</span> detectados`;
        }
    }

    function dibujarTablaPrioridades(productosFiltrados, totalCoincidencias = 0) {
        let htmlCabecera = `
            <tr style="background-color: #f8f9fa !important;">
                <th style="color: #000000 !important; font-weight: bold !important; padding: 12px; font-size: 0.85rem; text-transform: uppercase;">Pareto / Código</th>
                <th style="color: #000000 !important; font-weight: bold !important; padding: 12px; font-size: 0.85rem; text-transform: uppercase;">Descripción</th>
                <th style="color: #000000 !important; font-weight: bold !important; padding: 12px; font-size: 0.85rem; text-transform: uppercase;" class="text-center">Stock</th>
                <th style="color: #000000 !important; font-weight: bold !important; padding: 12px; font-size: 0.85rem; text-transform: uppercase;" class="text-center">Tránsito</th>
                <th style="color: #000000 !important; font-weight: bold !important; padding: 12px; font-size: 0.85rem; text-transform: uppercase;" class="text-center">Mínimo</th>
                <th style="color: #000000 !important; font-weight: bold !important; padding: 12px; font-size: 0.85rem; text-transform: uppercase;" class="text-center">Diferencia</th>
                <th style="color: #000000 !important; font-weight: bold !important; padding: 12px; font-size: 0.85rem; text-transform: uppercase;" class="text-center">Estado</th>
                <th style="color: #000000 !important; font-weight: bold !important; padding: 12px; font-size: 0.85rem; text-transform: uppercase;" class="text-center">Tipo</th>
            </tr>
        `;
        const tablaPadre = document.querySelector('#contenedor-prioridades-tabla')?.closest('table');
        if (tablaPadre && tablaPadre.querySelector('thead')) {
            tablaPadre.querySelector('thead').innerHTML = htmlCabecera;
        }

        let htmlFilas = '';
        const contenedor = document.getElementById('contenedor-prioridades-tabla');
        if (!contenedor) return;

        if (!productosFiltrados || productosFiltrados.length === 0) {
            contenedor.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-5">No hay ítems con los filtros seleccionados</td></tr>';
            return;
        }

        productosFiltrados.forEach(item => {
            try {
                // Construcción segura de variables fallback
                const codigo = item.codigo || 'S/C';
                const desc = item.descripcion || 'Sin descripción';
                const clase = item.clase || 'C';
                const stock = item.stock_actual !== undefined ? item.stock_actual : 0;
                const minimo = item.minimo || 0;
                const diferencia = item.diferencia || 0;
                const semaforo = item.semaforo || 'VERDE';

                // Determinar color del badge Pareto
                let badgeColor = 'bg-secondary text-white';
                if (clase === 'A') badgeColor = 'bg-danger text-white';
                if (clase === 'B') badgeColor = 'bg-warning text-dark';

                htmlFilas += `
                    <tr>
                        <td class="ps-4"><span class="badge ${badgeColor}" title="Unidades vendidas: ${item.unidades_vendidas || 0}">${clase}</span> <strong>${codigo}</strong></td>
                        <td class="small">${desc}</td>
                        <td class="text-center">${stock}</td>
                        <td class="text-center">${item.stock_externo || 0}</td>
                        <td class="text-center">${minimo}</td>
                        <td class="text-center font-weight-bold">${diferencia}</td>
                        <td class="text-center"><span class="badge bg-${semaforo === 'ROJO' ? 'danger' : (semaforo === 'AMARILLO' ? 'warning text-dark' : 'success')}">${semaforo}</span></td>
                        <td class="text-center">${item.tipo_buen || 'LIMPIO'}</td>
                    </tr>
                `;
            } catch (rowError) {
                console.error("Error renderizando fila individual de producto:", rowError, item);
                // Si una fila falla, el bucle continúa con el siguiente producto sin romper la tabla
            }
        });

        if (totalCoincidencias > productosFiltrados.length) {
            htmlFilas += `<tr><td colspan="8" class="text-center text-info small bg-dark py-2 border-0" style="color: #6c757d !important; background-color: #2b3035 !important;">Mostrando los ${productosFiltrados.length} ítems más críticos de ${totalCoincidencias} encontrados. Usa el buscador para encontrar referencias específicas.</td></tr>`;
        }

        contenedor.innerHTML = htmlFilas;
    }

    function setFiltroTipo(tipo, btn) {
        filtroTipoActual = tipo;
        document.querySelectorAll('.btn-filtro-tipo').forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');
        aplicarFiltrosCruzados();
    }

    function setFiltroClase(clase, btn) {
        filtroClaseActual = clase;
        document.querySelectorAll('.btn-filtro-clase').forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');
        aplicarFiltrosCruzados();
    }

    function aplicarFiltrosCruzados() {
        let filtrados = window.ModuloRotacionState.cache || [];

        // 1. Filtrar por Tipo de Buje (LIMPIO / ARMADO)
        if (filtroTipoActual && filtroTipoActual !== 'TODOS') {
            filtrados = filtrados.filter(p => String(p.tipo_buen || '').toUpperCase() === String(filtroTipoActual).toUpperCase());
        }

        // 2. Filtrar por Clasificación Pareto (A / B / C) - CORRECCIÓN CRÍTICA
        if (filtroClaseActual && filtroClaseActual !== 'TODOS') {
            filtrados = filtrados.filter(p => String(p.clase || '').toUpperCase().trim() === String(filtroClaseActual).toUpperCase().trim());
        }

        // 3. Filtrar por el buscador de texto si hay algo escrito
        const textoBuscador = document.getElementById('rot-search-global')?.value.toUpperCase().trim() || "";
        if (textoBuscador) {
            filtrados = filtrados.filter(p => 
                String(p.codigo || '').toUpperCase().includes(textoBuscador) || 
                String(p.descripcion || '').toUpperCase().includes(textoBuscador)
            );
        }

        const limiteCriticos = filtrados.slice(0, 100);
        dibujarTablaPrioridades(limiteCriticos, filtrados.length);
    }

    function filtrarGlobal() {
        aplicarFiltrosCruzados();
    }

    function prepararCompra(codigo) {
        // 1. Cambiar a la pestaña de Órdenes de Compra
        const ordenesTab = document.getElementById('ordenes-tab');
        if (ordenesTab) {
            const tabTrigger = new bootstrap.Tab(ordenesTab);
            tabTrigger.show();
        }

        // 2. Esperar un poco a que la pestaña carge y ejecutar lógica de compra
        setTimeout(() => {
            const inputCodigo = document.getElementById('codigo-producto-oc');
            if (inputCodigo) {
                inputCodigo.value = codigo;
                inputCodigo.classList.add('is-valid');

                // Efecto de foco visual potente
                const card = inputCodigo.closest('.card');
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                card.style.boxShadow = '0 0 20px rgba(67, 97, 238, 0.3)';
                setTimeout(() => card.style.boxShadow = '', 2000);

                inputCodigo.focus();
                inputCodigo.dispatchEvent(new Event('input', { bubbles: true }));

                Swal.fire({
                    title: '¡Producto Seleccionado!',
                    text: `Se ha cargado ${codigo} en la nueva orden.`,
                    icon: 'success',
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 3000
                });
            }
        }, 400);
    }

    return {
        inicializar,
        cargarPrioridades,
        filtrarGlobal,
        prepararCompra,
        setFiltroTipo,
        setFiltroClase
    };
})();
