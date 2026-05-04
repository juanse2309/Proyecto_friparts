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
        const tbody = document.querySelector('#tabla-inventario tbody') || document.getElementById('tabla-productos-body');
        if (!tbody) return;

        const start = (currentPage - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const productosPagina = productosFiltrados.slice(start, end);

        tbody.innerHTML = productosPagina.map(p => {
            // Lógica de Estado: Basada en existencias reales (SQL)
            const pTerminado = parseFloat(p.p_terminado) || 0;
            const stockBodega = parseFloat(p.stock_bodega) || 0;
            const tieneStock = pTerminado > 0 || stockBodega > 0;
            
            const estadoSemaforo = tieneStock ? 'disponible' : 'agotado';
            const badgeClass = tieneStock ? 'badge-success' : 'badge-danger';
            
            // Fallback de Imagen: Evitar 404 si la URL está vacía o es nula
            const srcImagen = (p.imagen && p.imagen.trim() !== "") ? p.imagen : 
                'data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'60\' height=\'60\'%3E%3Crect width=\'100%25\' height=\'100%25\' fill=\'%23f0f0f0\'/%3E%3Ctext x=\'50%25\' y=\'50%25\' font-family=\'Arial\' font-size=\'10\' fill=\'%23a0a0a0\' text-anchor=\'middle\' dy=\'.3em\'%3ESIN IMAGEN%3C/text%3E%3C/svg%3E';

            return `
            <tr data-semaforo="${estadoSemaforo}">
                <td class="text-center"><img src="${srcImagen}" alt="${p.nombre_producto}" class="img-thumbnail-tabla" style="width:40px; height:40px; object-fit:cover; border-radius:8px;" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'60\' height=\'60\'%3E%3Crect fill=\'%23ddd\'/%3E%3C/svg%3E'"></td>
                <td><strong>${p.codigo_sistema || 'S/N'}</strong></td>
                <td class="small">${p.nombre_producto || 'Sin descripción'}</td>
                <td style="text-align:right">${pTerminado.toFixed(0)}</td>
                <td style="text-align:right">${parseFloat(p.comprometido || 0).toFixed(0)}</td>
                <td style="text-align:right; font-weight:bold; color:#1e40af">${parseFloat(p.disponible || 0).toFixed(0)}</td>
                <td style="text-align:right">${stockBodega.toFixed(0)}</td>
                <td style="text-align:right">${parseFloat(p.por_pulir || 0).toFixed(0)}</td>
                <td style="text-align:center"><span class="badge ${badgeClass}" style="padding: 5px 10px; border-radius: 12px; font-size: 0.7rem;">${estadoSemaforo.toUpperCase()}</span></td>
            </tr>
            `;
        }).join('');

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
        document.querySelector('.table-container')?.scrollIntoView({ behavior: 'smooth' });
    }

    function configurarBusqueda() {
        const input = document.getElementById('buscar-producto');
        if (!input) return;

        input.addEventListener('input', (e) => {
            const termino = e.target.value.toLowerCase();
            productosFiltrados = termino ?
                productosOriginales.filter(p =>
                    (p.codigo_sistema || "").toLowerCase().includes(termino) ||
                    (p.nombre_producto || "").toLowerCase().includes(termino)
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
                (p.codigo_sistema || "").toLowerCase().includes(termino) ||
                (p.nombre_producto || "").toLowerCase().includes(termino)
            ) : [...productosOriginales];

        if (filtro !== 'todos') {
            resultados = resultados.filter(p => {
                const tieneStock = (parseFloat(p.p_terminado) || 0) > 0 || (parseFloat(p.stock_bodega) || 0) > 0;
                const estadoSemaforo = tieneStock ? 'disponible' : 'agotado';
                return estadoSemaforo === filtro;
            });
        }

        productosFiltrados = resultados;
        currentPage = 1; 
        renderizarProductos();
    }

    return { inicializar, cambiarPagina };
})();

window.ModuloInventario = ModuloInventario;