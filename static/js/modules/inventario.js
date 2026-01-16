// ===== GESTIÓN DE INVENTARIO =====

async function cargarProductos() {
    console.log('Cargando productos para inventario...');
    try {
        const response = await fetch('/api/productos/listar');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        let listaFinal = [];
        
        if (data.items && Array.isArray(data.items)) {
            listaFinal = data.items;
        } else if (Array.isArray(data)) {
            listaFinal = data;
        }

        if (listaFinal.length > 0) {
            window.AppState.productosData = listaFinal;
            renderizarTablaProductos(listaFinal);
            actualizarEstadisticasInventario(listaFinal);
            console.log('Productos cargados:', listaFinal.length);
        } else {
            console.warn('No se encontraron productos');
            mostrarNotificacion('No se encontraron productos para mostrar', 'warning');
        }
        
    } catch (error) {
        console.error('Error cargando productos:', error);
        mostrarNotificacion('Error cargando productos: ' + error.message, 'error');
    }
}

/**
 * Renderiza la tabla de productos con soporte para imágenes de Google Drive
 * y lógica anti-404 que verifica que las URLs comiencen con http/https
 */
function renderizarTablaProductos(productos) {
    const tbody = document.getElementById('tabla-productos-body');
    if (!tbody) return;

    // 1. Definir el placeholder exacto
    const PLACEHOLDER_THUMB = 'https://placehold.co/40x40/e9ecef/d1d5db?text=IMG';
    
    tbody.innerHTML = '';

    if (!productos || productos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4">No se encontraron productos</td></tr>';
        return;
    }

    const html = productos.map(p => {
        // 2. Determinar la URL de la imagen con lógica anti-404
        let imgUrl = PLACEHOLDER_THUMB; // Usar el placeholder por defecto
        
        // CORRECCIÓN CLAVE: Solo aceptamos la imagen si empieza con "http" o "https"
        // Esto evita que intente cargar rutas locales como "imagenes/5003.jpg" y de error 404
        if (p.imagen && typeof p.imagen === 'string') {
            const urlLimpia = p.imagen.trim();
            if (urlLimpia.length > 5 && 
                (urlLimpia.toLowerCase().startsWith('http://') || 
                 urlLimpia.toLowerCase().startsWith('https://'))) {
                imgUrl = urlLimpia;
            }
        }

        // 3. Determinar estado y estilos
        let estadoClass = '';
        let iconClass = '';
        
        if (p.stock_total <= 0) {
            estadoClass = 'badge-danger';
            iconClass = 'fa-times-circle';
        } else if (p.stock_total < (p.stock_minimo || 10)) {
            estadoClass = 'badge-warning';
            iconClass = 'fa-exclamation-triangle';
        } else {
            estadoClass = 'badge-success';
            iconClass = 'fa-check-circle';
        }

        // 4. Generar HTML de la fila
        return `
            <tr>
                <td class="producto-imagen-cell" style="width: 80px; text-align: center; vertical-align: middle;">
                    <div class="img-container" style="width: 50px; height: 50px; margin: 0 auto; overflow: hidden; border-radius: 8px; border: 1px solid #e2e8f0; background: #f8fafc;">
                        <img 
                            src="${imgUrl}" 
                            alt="${p.codigo_sistema}" 
                            class="producto-img"
                            loading="lazy"
                            referrerpolicy="no-referrer"
                            style="width: 100%; height: 100%; object-fit: cover; cursor: pointer;"
                            onclick="window.open('${imgUrl}', '_blank')"
                            onerror="this.onerror=null; this.src='${PLACEHOLDER_THUMB}';"
                        >
                    </div>
                </td>
                <td style="vertical-align: middle;">
                    <span class="fw-bold text-primary">${p.codigo_sistema}</span>
                </td>
                <td style="vertical-align: middle;">
                    <div class="fw-bold text-dark">${p.descripcion}</div>
                    <small class="text-muted">OEM: ${p.oem || '-'}</small>
                </td>
                <td class="text-center" style="vertical-align: middle;">
                    <span class="badge bg-light text-dark border">${p.stock_por_pulir || 0}</span>
                </td>
                <td class="text-center" style="vertical-align: middle;">
                    <span class="badge bg-light text-dark border">${p.stock_terminado || 0}</span>
                </td>
                <td class="text-center" style="vertical-align: middle;">
                    <span class="badge ${estadoClass} p-2">
                        <i class="fas ${iconClass} me-1"></i> ${p.estado || 'OK'}
                    </span>
                </td>
            </tr>
        `;
    }).join('');

    tbody.innerHTML = html;
}

// Función auxiliar para formatear números (si no la tienes en utils.js)
function formatNumber(num) {
    if (num === undefined || num === null || isNaN(num)) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function actualizarEstadisticasInventario(productos) {
    if (!productos || !Array.isArray(productos)) return;
    
    const totalProductos = productos.length;
    const stockBajo = productos.filter(p => {
        const actual = parseFloat(p.TOTAL_PRODUCCION || p.stock || 0);
        const minimo = parseFloat(p.STOCK_MINIMO || p.stock_minimo || 0);
        return actual > 0 && actual < minimo;
    }).length;
    
    const sinStock = productos.filter(p => parseFloat(p.TOTAL_PRODUCCION || p.stock || 0) <= 0).length;
    const stockOk = productos.filter(p => {
        const actual = parseFloat(p.TOTAL_PRODUCCION || p.stock || 0);
        const minimo = parseFloat(p.STOCK_MINIMO || p.stock_minimo || 0);
        return actual >= minimo;
    }).length;
    
    const updateElement = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = formatNumber(value);
    };
    
    updateElement('total-productos', totalProductos);
    updateElement('productos-bajo-stock', stockBajo);
    updateElement('productos-agotados', sinStock);
    updateElement('productos-stock-ok', stockOk);
}

function buscarProductos() {
    const buscarInput = document.getElementById('buscar-producto');
    if (!buscarInput || !window.AppState.productosData || window.AppState.productosData.length === 0) return;

    const termino = buscarInput.value.toLowerCase().trim();
    if (!termino) {
        renderizarTablaProductos(window.AppState.productosData);
        return;
    }

    const productosFiltrados = window.AppState.productosData.filter((p) => {
        const prod = p.producto || p;
        const camposABuscar = [
            prod.codigo_sistema,
            prod.codigo_interno,
            prod.codigo,
            prod.codigosistema,
            prod['CODIGO SISTEMA'],
            prod.descripcion,
            prod.nombre,
            prod.DESCRIPCION,
            prod.oem,
            prod.OEM
        ].filter(val => val);

        return camposABuscar.some(campo => {
            if (campo) {
                const valorBusqueda = String(campo).toLowerCase();
                if (valorBusqueda.includes(termino)) return true;
                if (/^\d+$/.test(termino)) {
                    if (valorBusqueda.replace(/\D/g, '').includes(termino)) return true;
                }
            }
            return false;
        });
    });

    if (productosFiltrados.length > 0) {
        renderizarTablaProductos(productosFiltrados);
        mostrarNotificacion(`Se encontraron ${productosFiltrados.length} productos`, 'info');
    } else {
        renderizarTablaProductos([]);
        mostrarNotificacion('No se encontraron productos con ese criterio', 'info');
    }
}

function filtrarProductos(filtro) {
    if (!window.AppState.productosData || window.AppState.productosData.length === 0) return;

    let resultados;
    const productos = window.AppState.productosData;

    const getTotales = (p) => {
        const prod = p.producto || p;
        const total = prod.existencias?.total ?? 0;
        const min   = prod.stockminimo ?? prod.STOCKMINIMO ?? 0;
        return { total: Number(total) || 0, min: Number(min) || 0 };
    };

    switch (filtro) {
        case "bajo-stock":
            resultados = productos.filter((p) => {
                const { total, min } = getTotales(p);
                return total > 0 && total < min;
            });
            break;
        case "agotados":
            resultados = productos.filter((p) => {
                const { total } = getTotales(p);
                return total === 0;
            });
            break;
        case "stock-ok":
            resultados = productos.filter((p) => {
                const { total, min } = getTotales(p);
                return total >= min && total > 0;
            });
            break;
        default:
            resultados = productos;
            break;
    }

    renderizarTablaProductos(resultados);

    document.querySelectorAll(".filter-btn").forEach((btn) => {
        btn.classList.remove("active");
        if (btn.dataset.filter === filtro) {
            btn.classList.add("active");
        }
    });
}

function configurarEventosInventario() {
    const buscarInput = document.getElementById('buscar-producto');
    if (buscarInput) {
        buscarInput.addEventListener('input', buscarProductos);
    }
    
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const filtro = this.dataset.filter;
            if (filtro) filtrarProductos(filtro);
        });
    });
    
    const btnActualizar = document.getElementById('btn-actualizar-productos');
    if (btnActualizar) {
        btnActualizar.addEventListener('click', cargarProductos);
    }
    
    // ELIMINADO: Evento para btn-nuevo-producto
    // const btnNuevoProducto = document.getElementById('btn-nuevo-producto');
    // if (btnNuevoProducto) {
    //     btnNuevoProducto.addEventListener('click', mostrarModalNuevoProducto);
    // }
    
    const btnExportar = document.getElementById('btn-exportar-inventario');
    if (btnExportar) {
        btnExportar.addEventListener('click', function() {
            mostrarNotificacion('Función de exportación en desarrollo', 'info');
        });
    }
}