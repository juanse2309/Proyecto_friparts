const ModuloInventario = (() => {
    let productosOriginales = [];
    let productosFiltrados = [];
    let currentPage = 1;
    const itemsPerPage = 50; // Mobile-friendly limit

    function inicializar() {
        productosOriginales = window.AppState.sharedData.productos;
        productosFiltrados = [...productosOriginales];
        renderizarProductos();
        configurarBusqueda();
        configurarFiltros();
        console.log('✅ Inventario listo');
    }

    function renderizarProductos() {
        const tbody = document.querySelector('#tabla-inventario tbody');
        if (!tbody) return;

        const start = (currentPage - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const productosPagina = productosFiltrados.slice(start, end);

        tbody.innerHTML = productosPagina.map(p => `
            <tr data-semaforo="${p.semaforo}">
                <td><img src="${p.imagen}" alt="${p.descripcion}" class="img-thumbnail-tabla" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'60\' height=\'60\'%3E%3Crect fill=\'%23ddd\'/%3E%3C/svg%3E'"></td>
                <td><strong>${p.codigo_sistema}</strong></td>
                <td>${p.descripcion}</td>
                <td style="text-align:center"><span class="badge badge-${p.semaforo}">${p.semaforo.toUpperCase()}</span></td>
                <td style="text-align:center">${p.stock_por_pulir}</td>
                <td style="text-align:center">${p.stock_terminado}</td>
                <td style="text-align:center"><strong>${p.stock_total}</strong></td>
            </tr>
        `).join('');

        renderizarPaginacion();
    }

    function renderizarPaginacion() {
        const container = document.getElementById('pagination-container');
        if (!container) return;

        const totalPages = Math.ceil(productosFiltrados.length / itemsPerPage);

        let html = `
            <nav aria-label="Page navigation">
                <ul class="pagination">
                    <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                        <a class="page-link" href="#" onclick="window.ModuloInventario.cambiarPagina(${currentPage - 1})">Anterior</a>
                    </li>
                    <li class="page-item disabled">
                        <span class="page-link">Página ${currentPage} de ${totalPages || 1}</span>
                    </li>
                    <li class="page-item ${currentPage === totalPages || totalPages === 0 ? 'disabled' : ''}">
                        <a class="page-link" href="#" onclick="window.ModuloInventario.cambiarPagina(${currentPage + 1})">Siguiente</a>
                    </li>
                </ul>
            </nav>
        `;
        container.innerHTML = html;
    }

    function cambiarPagina(page) {
        const totalPages = Math.ceil(productosFiltrados.length / itemsPerPage);
        if (page < 1 || page > totalPages) return;
        currentPage = page;
        renderizarProductos();
        // Scroll to top of table
        document.querySelector('.table-container')?.scrollIntoView({ behavior: 'smooth' });
    }

    function configurarBusqueda() {
        const input = document.getElementById('buscar-producto');
        if (!input) return;

        input.addEventListener('input', (e) => {
            const termino = e.target.value.toLowerCase();
            productosFiltrados = termino ?
                productosOriginales.filter(p =>
                    p.codigo_sistema.toLowerCase().includes(termino) ||
                    p.descripcion.toLowerCase().includes(termino)
                ) : [...productosOriginales];
            aplicarFiltroSemaforo();
        });
    }

    function configurarFiltros() {
        document.querySelectorAll('.btn-filtro-semaforo').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.btn-filtro-semaforo').forEach(b => b.classList.remove('activo'));
                btn.classList.add('activo');
                aplicarFiltroSemaforo();
            });
        });
    }

    function aplicarFiltroSemaforo() {
        const btnActivo = document.querySelector('.btn-filtro-semaforo.activo');
        const filtro = btnActivo?.getAttribute('data-filtro') || 'todos';
        const termino = document.getElementById('buscar-producto')?.value.toLowerCase() || '';

        let resultados = termino ?
            productosOriginales.filter(p =>
                p.codigo_sistema.toLowerCase().includes(termino) ||
                p.descripcion.toLowerCase().includes(termino)
            ) : [...productosOriginales];

        if (filtro !== 'todos') {
            resultados = resultados.filter(p => p.semaforo === filtro);
        }

        productosFiltrados = resultados;
        currentPage = 1; // Reset to first page on filter
        renderizarProductos();
    }

    return { inicializar, cambiarPagina };
})();

window.ModuloInventario = ModuloInventario;