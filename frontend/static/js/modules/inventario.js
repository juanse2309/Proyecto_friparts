// ===========================
// M�DULO DE INVENTARIO
// ===========================

const ModuloInventario = (() => {
    let productosOriginales = [];
    let productosFiltrados = [];
    let paginaActual = 1;
    const productosPorPagina = 50;

    function inicializar() {
        productosOriginales = window.AppState.sharedData.productos || [];
        productosFiltrados = [...productosOriginales];
        renderizarProductos();
        actualizarEstadisticas(); // Nueva funci�n para las tarjetas
        configurarBusqueda();
        configurarFiltros();
        configurarPaginacion();
        configurarBotonActualizar();

    }

    /**
     * Actualiza las tarjetas de estad�sticas superiores.
     */
    function actualizarEstadisticas() {
        const totalEl = document.getElementById('total-productos');
        const okEl = document.getElementById('productos-stock-ok');
        const bajoEl = document.getElementById('productos-bajo-stock');
        const agotadosEl = document.getElementById('productos-agotados');

        if (!totalEl) return; // Si no hay elementos, salir

        const total = productosOriginales.length;
        const agotados = productosOriginales.filter(p => (p.stock_total || 0) <= 0).length;

        const ok = productosOriginales.filter(p => {
            const sem = typeof p.semaforo === 'object' ? p.semaforo.color : p.semaforo;
            return sem === 'success';
        }).length;

        const bajo = productosOriginales.filter(p => {
            const sem = typeof p.semaforo === 'object' ? p.semaforo.color : p.semaforo;
            return sem === 'warning' || sem === 'danger';
        }).length;

        // Actualizar UI
        totalEl.textContent = total.toLocaleString();
        okEl.textContent = ok.toLocaleString();
        bajoEl.textContent = bajo.toLocaleString();
        agotadosEl.textContent = agotados.toLocaleString();


    }

    function renderizarProductos() {
        const tbody = document.getElementById('tabla-productos-body') ||
            document.querySelector('.table-inventario tbody');

        if (!tbody) {
            console.error('? No se encontr� tbody del inventario');
            return;
        }

        if (productosFiltrados.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align:center;padding:3rem;color:#999;">
                        <i class="fas fa-search" style="font-size:3rem;margin-bottom:1rem;display:block;"></i>
                        <p style="font-size:1.1rem;">No se encontraron productos</p>
                    </td>
                </tr>
            `;
            return;
        }

        const inicio = (paginaActual - 1) * productosPorPagina;
        const fin = inicio + productosPorPagina;
        const productosPagina = productosFiltrados.slice(inicio, fin);

        tbody.innerHTML = productosPagina.map(p => {
            const semaforoColor = typeof p.semaforo === 'object' ? p.semaforo.color : p.semaforo;
            const semaforoTexto = typeof p.semaforo === 'object' ? p.semaforo.estado : (p.semaforo || 'N/A');

            const badgeStyle = semaforoColor === 'success' ? 'background:#10b981;color:white;' :
                semaforoColor === 'warning' ? 'background:#f59e0b;color:white;' :
                    semaforoColor === 'danger' ? 'background:#ef4444;color:white;' :
                        'background:#6b7280;color:white;';

            const tieneImagenValida = p.imagen &&
                (p.imagen.startsWith('http://') ||
                    p.imagen.startsWith('https://'));

            return `
                <tr style="border-bottom:1px solid #e5e7eb;">
                    <td style="padding:1rem;">
                        <div style="display:flex;align-items:center;gap:1rem;">
                            ${tieneImagenValida ? `
                                <img src="${p.imagen}" 
                                     alt="${p.descripcion}"
                                     style="width:60px;height:60px;object-fit:cover;border-radius:8px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);display:block;" 
                                     onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
                                <div style="width:60px;height:60px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);display:none;align-items:center;justify-content:center;border-radius:8px;flex-shrink:0;">
                                    <i class="fas fa-image" style="color:white;font-size:1.5rem;"></i>
                                </div>
                            ` : `
                                <div style="width:60px;height:60px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);display:flex;align-items:center;justify-content:center;border-radius:8px;flex-shrink:0;">
                                    <i class="fas fa-image" style="color:white;font-size:1.5rem;"></i>
                                </div>
                            `}
                            <div style="min-width:0;flex:1;">
                                <div style="font-weight:600;color:#1f2937;font-size:0.95rem;margin-bottom:0.25rem;">
                                    ${p.codigo_sistema}
                                </div>
                                <div style="color:#6b7280;font-size:0.875rem;line-height:1.4;">
                                    ${p.descripcion}
                                </div>
                                <span style="${badgeStyle}padding:0.25rem 0.5rem;border-radius:4px;font-size:0.75rem;font-weight:600;display:inline-block;margin-top:0.25rem;">
                                    ${semaforoTexto}
                                </span>
                            </div>
                        </div>
                    </td>
                    <td style="text-align:center;padding:1rem;font-size:1.1rem;font-weight:600;color:#1f2937;">
                        ${p.stock_por_pulir.toLocaleString()}
                    </td>
                    <td style="text-align:center;padding:1rem;font-size:1.1rem;font-weight:600;color:#1f2937;">
                        ${p.stock_terminado.toLocaleString()}
                    </td>
                    <td style="text-align:center;padding:1rem;font-size:1.2rem;font-weight:700;color:#2563eb;">
                        ${p.stock_total.toLocaleString()}
                    </td>
                    <td style="text-align:center;padding:1rem;">
                        <button class="btn-ver-detalles" data-codigo="${p.codigo_sistema}" 
                                style="padding:0.5rem 1rem;background:#3b82f6;color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.875rem;font-weight:500;transition:all 0.2s;"
                                onmouseover="this.style.background='#2563eb'"
                                onmouseout="this.style.background='#3b82f6'">
                            <i class="fas fa-eye"></i> Ver Detalles
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        renderizarPaginacion();
        configurarBotonesAcciones();

    }

    function configurarBotonesAcciones() {
        document.querySelectorAll('.btn-ver-detalles').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const codigo = e.currentTarget.getAttribute('data-codigo');

                alert(`Detalles del producto: ${codigo}\n(Funcionalidad por implementar)`);
            });
        });
    }

    function configurarBusqueda() {
        const input = document.getElementById('buscar-producto');
        if (!input) {
            console.warn('?? Input de b�squeda no encontrado');
            return;
        }

        input.addEventListener('input', (e) => {
            const termino = e.target.value.toLowerCase().trim();
            paginaActual = 1;

            if (termino === '') {
                productosFiltrados = [...productosOriginales];
            } else {
                productosFiltrados = productosOriginales.filter(p =>
                    p.codigo_sistema.toLowerCase().includes(termino) ||
                    p.descripcion.toLowerCase().includes(termino)
                );
            }

            aplicarFiltroActual();

        });


    }

    function configurarFiltros() {
        // Usar .rounded-pill que es la clase real de los botones
        const botones = document.querySelectorAll('.rounded-pill');

        if (botones.length === 0) {
            console.warn('?? Botones de filtro no encontrados');
            return;
        }

        // Mapeo de texto a filtro
        const mapaFiltros = {
            'Todos': 'todos',
            'Cr�ticos': 'danger',
            'Por Pedir': 'warning',
            'Stock OK': 'success',
            'Agotados': 'agotados'
        };

        botones.forEach((btn, index) => {
            const texto = btn.textContent.trim();
            const filtro = mapaFiltros[texto] || 'todos';

            // Asignar data-filtro din�micamente
            btn.setAttribute('data-filtro', filtro);

            btn.addEventListener('click', () => {
                // Remover active de todos
                botones.forEach(b => {
                    b.classList.remove('active', 'btn-primary');
                    b.classList.add('btn-light', 'border');
                });

                // Activar el clickeado
                btn.classList.add('active', 'btn-primary');
                btn.classList.remove('btn-light', 'border');

                paginaActual = 1;
                aplicarFiltroActual();


            });


        });


    }

    function aplicarFiltroActual() {
        const btnActivo = document.querySelector('.rounded-pill.active');
        const filtro = btnActivo?.getAttribute('data-filtro') || 'todos';
        const termino = document.getElementById('buscar-producto')?.value.toLowerCase().trim() || '';

        // Primero aplicar b�squeda
        let resultados = termino === '' ? [...productosOriginales] :
            productosOriginales.filter(p =>
                p.codigo_sistema.toLowerCase().includes(termino) ||
                p.descripcion.toLowerCase().includes(termino)
            );

        // Luego aplicar filtro de sem�foro
        if (filtro !== 'todos') {
            if (filtro === 'agotados') {
                resultados = resultados.filter(p => p.stock_total === 0);
            } else {
                resultados = resultados.filter(p => {
                    const color = typeof p.semaforo === 'object' ? p.semaforo.color : p.semaforo;
                    return color === filtro;
                });
            }
        }

        productosFiltrados = resultados;
        renderizarProductos();
    }

    function configurarBotonActualizar() {
        const btnActualizar = document.getElementById('btn-actualizar-productos');

        if (!btnActualizar) {
            console.warn('?? Bot�n actualizar no encontrado');
            return;
        }

        btnActualizar.addEventListener('click', async () => {


            // Animaci�n de carga
            const iconoOriginal = btnActualizar.innerHTML;
            btnActualizar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Actualizando...';
            btnActualizar.disabled = true;

            try {
                // Recargar productos del servidor
                const productosRaw = await apiClient.get('/productos/listar_v2');
                window.AppState.sharedData.productos = productosRaw.map(p => ({
                    id_codigo: p.id_codigo || 0,
                    codigo_sistema: p.codigo || '',
                    descripcion: p.descripcion || '',
                    imagen: p.imagen || '',
                    stock_por_pulir: p.stock_por_pulir || 0,
                    stock_terminado: p.stock_terminado || 0,
                    stock_total: p.existencias_totales || 0,
                    semaforo: p.semaforo || 'rojo',
                    metricas: p.metricas || { min: 0, max: 0, reorden: 0 }
                }));

                // Re-inicializar
                productosOriginales = window.AppState.sharedData.productos;
                productosFiltrados = [...productosOriginales];
                paginaActual = 1;

                // Limpiar b�squeda y resetear filtros
                const inputBusqueda = document.getElementById('buscar-producto');
                if (inputBusqueda) inputBusqueda.value = '';

                const botones = document.querySelectorAll('.rounded-pill');
                botones.forEach((btn, i) => {
                    if (i === 0) {
                        btn.classList.add('active', 'btn-primary');
                        btn.classList.remove('btn-light', 'border');
                    } else {
                        btn.classList.remove('active', 'btn-primary');
                        btn.classList.add('btn-light', 'border');
                    }
                });

                renderizarProductos();
                actualizarEstadisticas();



            } catch (error) {
                console.error('? Error actualizando:', error);
                alert('Error al actualizar el inventario. Ver consola.');
            } finally {
                btnActualizar.innerHTML = iconoOriginal;
                btnActualizar.disabled = false;
            }
        });


    }

    function configurarPaginacion() {
        const container = document.querySelector('.table-inventario')?.parentElement;
        if (!container) return;

        let paginacionDiv = document.getElementById('paginacion-inventario');
        if (!paginacionDiv) {
            paginacionDiv = document.createElement('div');
            paginacionDiv.id = 'paginacion-inventario';
            paginacionDiv.style.cssText = 'display:flex;justify-content:center;align-items:center;gap:1rem;margin-top:1.5rem;padding:1rem;';
            container.appendChild(paginacionDiv);
        }
    }

    function renderizarPaginacion() {
        const paginacionDiv = document.getElementById('paginacion-inventario');
        if (!paginacionDiv) return;

        const totalPaginas = Math.ceil(productosFiltrados.length / productosPorPagina);

        if (totalPaginas <= 1) {
            paginacionDiv.innerHTML = '';
            return;
        }

        paginacionDiv.innerHTML = `
            <button onclick="ModuloInventario.cambiarPagina(${paginaActual - 1})" 
                    ${paginaActual === 1 ? 'disabled' : ''}
                    style="padding:0.6rem 1.2rem;border-radius:6px;border:1px solid #d1d5db;background:white;cursor:${paginaActual === 1 ? 'not-allowed' : 'pointer'};font-weight:500;opacity:${paginaActual === 1 ? '0.5' : '1'};">
                <i class="fas fa-chevron-left"></i> Anterior
            </button>
            <span style="color:#6b7280;font-weight:500;">P�gina <strong>${paginaActual}</strong> de <strong>${totalPaginas}</strong> (${productosFiltrados.length} productos)</span>
            <button onclick="ModuloInventario.cambiarPagina(${paginaActual + 1})" 
                    ${paginaActual === totalPaginas ? 'disabled' : ''}
                    style="padding:0.6rem 1.2rem;border-radius:6px;border:1px solid #d1d5db;background:white;cursor:${paginaActual === totalPaginas ? 'not-allowed' : 'pointer'};font-weight:500;opacity:${paginaActual === totalPaginas ? '0.5' : '1'};">
                Siguiente <i class="fas fa-chevron-right"></i>
            </button>
        `;
    }

    function cambiarPagina(nuevaPagina) {
        const totalPaginas = Math.ceil(productosFiltrados.length / productosPorPagina);
        if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
        paginaActual = nuevaPagina;
        renderizarProductos();
        document.querySelector('.table-inventario')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    return {
        inicializar,
        cambiarPagina
    };
})();

window.ModuloInventario = ModuloInventario;

