// Variables para productos
let productosFiltrados = [];

// Cargar productos
async function cargarProductos() {
    try {
        showLoading('products-list', 'Cargando productos...');
        
        const response = await fetch('http://127.0.0.1:5000/api/productos/listar');
        if (!response.ok) throw new Error('Error HTTP');

        const data = await response.json();
        
        if (data.status !== 'success') throw new Error(data.message);

        window.AppState.listaProductosCompleta = data.items || [];
        productosFiltrados = [...window.AppState.listaProductosCompleta];
        
        mostrarProductos(window.AppState.listaProductosCompleta);
        actualizarResumen(window.AppState.listaProductosCompleta);

    } catch (e) {
        console.error('Error cargando productos:', e);
        const productsList = document.getElementById('products-list');
        productsList.innerHTML = `
            <div style="text-align:center;padding:40px;color:#dc2626;">
                ❌ Error al cargar productos: ${e.message}
            </div>
        `;
    }
}

// Filtrar productos
function filtrarProductos(filtro) {
    window.AppState.filtroActual = filtro;

    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    event.target.classList.add('active');

    let filtrados = [...window.AppState.listaProductosCompleta];

    if (filtro === 'bajo') {
        filtrados = filtrados.filter(i => i.producto?.estado === 'BAJO');
    } else if (filtro === 'agotado') {
        filtrados = filtrados.filter(i => i.producto?.estado === 'AGOTADO');
    } else if (filtro === 'ok') {
        filtrados = filtrados.filter(i => i.producto?.estado === 'OK');
    }

    productosFiltrados = filtrados;
    mostrarProductos(filtrados);
}

// Buscar productos
function buscarProductos() {
    const input = document.getElementById('searchInput');
    const query = input.value.trim().toLowerCase();

    if (!query) {
        productosFiltrados = [...window.AppState.listaProductosCompleta];
        mostrarProductos(window.AppState.listaProductosCompleta);
        return;
    }

    const resultados = window.AppState.listaProductosCompleta.filter(item => {
        const p = item.producto;
        return (
            p.codigo_sistema.toLowerCase().includes(query) ||
            (p.descripcion && p.descripcion.toLowerCase().includes(query)) ||
            (p.oem && p.oem.toLowerCase().includes(query))
        );
    });

    productosFiltrados = resultados;
    mostrarProductos(resultados);
}

// Actualizar resumen
function actualizarResumen(items) {
    const totalProductos = document.getElementById('totalProductos');
    const stockTotal = document.getElementById('stockTotal');
    const conStock = document.getElementById('conStock');
    const stockBajo = document.getElementById('stockBajo');
    const sinStock = document.getElementById('sinStock');

    if (!totalProductos || !stockTotal || !conStock || !stockBajo || !sinStock) {
        return;
    }

    const total = items.length;
    const stock = items.reduce((s, i) => s + (i.existencias?.total || 0), 0);
    const con = items.filter(i => (i.existencias?.total || 0) > 0).length;
    const bajo = items.filter(i => i.producto?.estado === 'BAJO').length;
    const sin = items.filter(i => (i.existencias?.total || 0) === 0).length;

    totalProductos.textContent = total;
    stockTotal.textContent = formatNumber(stock);
    conStock.textContent = con;
    stockBajo.textContent = bajo;
    sinStock.textContent = sin;
}

// Mostrar productos en tabla
function mostrarProductos(items) {
    const productsList = document.getElementById('products-list');

    if (items.length === 0) {
        productsList.innerHTML = `
            <div style="text-align:center;padding:40px;color:#6b7280;">
                No hay productos para este filtro
            </div>
        `;
        return;
    }

    let html = `
        <div class="products-table-container">
            <table class="products-table">
                <thead>
                    <tr>
                        <th>Código</th>
                        <th>Descripción</th>
                        <th>Total (Prod)</th>
                        <th>Por Pulir</th>
                        <th>Terminado</th>
                        <th>Ensamble</th>
                        <th>Estado</th>
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody>
    `;

    items.forEach(item => {
        const { producto, existencias } = item;

        const stockClass =
            producto.estado === 'OK' ? 'stock-ok' :
            producto.estado === 'BAJO' ? 'stock-low' :
            'stock-out';

        const statusClass =
            producto.estado === 'OK' ? 'status-ok' :
            producto.estado === 'BAJO' ? 'status-low' :
            'status-out';

        html += `
            <tr>
                <td><strong>${producto.codigo_sistema}</strong></td>
                <td>${producto.descripcion}</td>
                <td class="stock-cell ${stockClass}">${existencias.total}</td>
                <td class="stock-cell">${existencias.por_pulir}</td>
                <td class="stock-cell">${existencias.terminado}</td>
                <td class="stock-cell">${existencias.ensamblado}</td>
                <td>
                    <span class="status-badge ${statusClass}">
                        ${producto.estado}
                    </span>
                </td>
                <td>
                    <button onclick="verDetalleProducto('${producto.codigo_sistema}')" 
                            class="action-btn">
                        Ver más
                    </button>
                </td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
        <div style="margin-top:10px;color:#6b7280;">
            Mostrando ${items.length} productos<br>
            <small><i>Total producción = Por Pulir + Terminado</i></small>
        </div>
    `;

    productsList.innerHTML = html;
}

// Ver detalle de producto
async function verDetalleProducto(codigo) {
    try {
        safeHide('products-container');
        safeDisplay('product-detail-container');
        
        showLoading('product-detail', 'Cargando información del producto...');
        
        const res = await fetch(`http://127.0.0.1:5000/api/productos/detalle/${codigo}`);
        if (!res.ok) throw new Error('Error al obtener detalle');
        
        const data = await res.json();
        
        if (data.status !== 'success') throw new Error(data.message);
        
        mostrarDetalleProducto(data);
        
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('product-detail').innerHTML = `
            <div style="text-align:center;padding:40px;color:#dc2626;">
                ❌ Error al cargar el detalle del producto
                <p style="font-size:0.9rem;margin-top:10px;">${error.message}</p>
                <br>
                <button onclick="volverAListaProductos()" class="action-btn" style="margin-top:20px;">
                    ← Volver a Productos y Existencias
                </button>
            </div>
        `;
    }
}

// Mostrar detalle del producto
function mostrarDetalleProducto(data) {
    const producto = data.producto;
    const ficha = data.ficha_tecnica || {};
    const movimientos = data.movimientos_recientes || [];
    const resumen = data.resumen_stock || {};
    
    const statusClass =
        producto.estado === 'OK' ? 'status-ok' :
        producto.estado === 'BAJO' ? 'status-low' :
        'status-out';
    
    let html = `
        <div class="product-detail-card">
            <div class="product-header">
                <div class="product-info">
                    <h3>${producto.descripcion || 'Producto sin descripción'}</h3>
                    <div class="product-codes">
                        <span class="code-badge"><strong>Sistema:</strong> ${producto.codigo_sistema}</span>
                        ${producto.id_codigo ? `<span class="code-badge"><strong>ID:</strong> ${producto.id_codigo}</span>` : ''}
                        ${producto.codigo ? `<span class="code-badge"><strong>Código:</strong> ${producto.codigo}</span>` : ''}
                        ${producto.oem ? `<span class="code-badge"><strong>OEM:</strong> ${producto.oem}</span>` : ''}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.2rem; font-weight: 700; color: var(--primary);">
                        ${resumen.total_produccion || producto.stock_total || 0} ${producto.unidad || 'PZ'}
                    </div>
                    <div style="font-size: 0.85rem; color: #6b7280; margin-top: 5px;">
                        Stock en Producción
                    </div>
                    <div style="font-size: 0.85rem; color: #6b7280; margin-top: 5px;">
                        Stock en Cliente: ${producto.stock_cliente || 0}
                    </div>
                    <div style="margin-top: 10px;">
                        <span class="status-badge ${statusClass}">
                            ${producto.estado || 'OK'}
                        </span>
                    </div>
                </div>
            </div>
            
            <div class="stock-grid">
                <div class="stock-stage-card">
                    <div class="stage-name">Por Pulir</div>
                    <div class="stage-value">${producto.stock_por_pulir || resumen.por_etapa?.['POR PULIR'] || 0}</div>
                </div>
                <div class="stock-stage-card">
                    <div class="stage-name">Terminado</div>
                    <div class="stage-value">${producto.stock_terminado || resumen.por_etapa?.['P. TERMINADO'] || 0}</div>
                </div>
                <div class="stock-stage-card">
                    <div class="stage-name">Ensamble</div>
                    <div class="stage-value">${producto.stock_ensamblado || resumen.por_etapa?.['PRODUCTO ENSAMBLADO'] || 0}</div>
                </div>
                <div class="stock-stage-card">
                    <div class="stage-name">Cliente</div>
                    <div class="stage-value">${producto.stock_cliente || resumen.por_etapa?.['CLIENTE'] || 0}</div>
                </div>
            </div>
            
            <div style="margin: 25px 0;">
                <h4 style="margin-bottom: 15px; color: #374151;">📋 Información General</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div>
                        <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 5px;">Unidad</div>
                        <div style="font-weight: 600;">${producto.unidad || 'PZ'}</div>
                    </div>
                    ${producto.stock_minimo ? `
                    <div>
                        <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 5px;">Stock Mínimo</div>
                        <div style="font-weight: 600;">${producto.stock_minimo}</div>
                    </div>` : ''}
                    ${producto.precio ? `
                    <div>
                        <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 5px;">Precio</div>
                        <div style="font-weight: 600;">$${producto.precio}</div>
                    </div>` : ''}
                </div>
            </div>
    `;
    
    if (ficha.buje_origen) {
        html += `
            <div style="margin: 25px 0; padding: 15px; background: #f0f9ff; border-radius: 8px;">
                <h4 style="margin-bottom: 15px; color: #374151;">🔧 Ficha Técnica</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div>
                        <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 5px;">Buje Origen</div>
                        <div style="font-weight: 600;">${ficha.buje_origen}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 5px;">Cantidad Unitaria</div>
                        <div style="font-weight: 600;">${ficha.qty_unitaria}</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    if (movimientos.length > 0) {
        html += `
            <div style="margin: 25px 0;">
                <h4 style="margin-bottom: 15px; color: #374151;">📊 Movimientos Recientes</h4>
                <div style="overflow-x: auto;">
                    <table class="movimientos-table">
                        <thead>
                            <tr>
                                <th>Fecha</th>
                                <th>Tipo</th>
                                <th>Cantidad</th>
                                <th>Responsable</th>
                                <th>Detalle</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        movimientos.forEach(mov => {
            html += `
                <tr>
                    <td>${mov.fecha || '-'}</td>
                    <td>${mov.tipo || '-'}</td>
                    <td>${mov.cantidad}</td>
                    <td>${mov.responsable || '-'}</td>
                    <td>${mov.detalle || '-'}</td>
                </tr>
            `;
        });
        
        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    } else {
        html += `
            <div style="margin: 25px 0; text-align: center; color: #6b7280; padding: 20px; background: #f9fafb; border-radius: 8px;">
                No hay movimientos recientes para este producto
            </div>
        `;
    }
    
    html += `</div>`;
    
    document.getElementById('product-detail').innerHTML = html;
}

// Cargar estadísticas
async function cargarEstadisticas() {
    const statsSection = document.getElementById('stats-section');
    
    try {
        const response = await fetch('http://127.0.0.1:5000/api/productos/estadisticas');
        const data = await response.json();
        
        if (data.status === 'success') {
            const stats = data.estadisticas;
            
            let html = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="totalProductos">${stats.total_productos}</div>
                    <div class="stat-label">Productos Totales</div>
                </div>
            
                <div class="stat-card">
                    <div class="stat-value" id="stockTotal">${stats.total_stock_produccion}</div>
                    <div class="stat-label">Stock Producción</div>
                </div>
            
                <div class="stat-card">
                    <div class="stat-value" id="conStock">${stats.productos_con_stock}</div>
                    <div class="stat-label">Con Stock</div>
                </div>
            
                <div class="stat-card">
                    <div class="stat-value" id="stockBajo">${stats.productos_bajo_stock}</div>
                    <div class="stat-label">Stock Bajo</div>
                </div>
            
                <div class="stat-card">
                    <div class="stat-value" id="sinStock">${stats.productos_sin_stock}</div>
                    <div class="stat-label">Sin Stock</div>
                </div>
            </div>
            `;
            
            statsSection.innerHTML = html;
            
            if (window.AppState.listaProductosCompleta.length > 0) {
                actualizarResumen(window.AppState.listaProductosCompleta);
            }
        }
    } catch (error) {
        console.error('Error cargando estadísticas:', error);
        statsSection.innerHTML = `
            <div style="color: #dc2626; text-align: center; padding: 10px;">
                Error al cargar estadísticas
            </div>
        `;
    }
}

// Exportar productos a Excel
async function exportarProductosExcel() {
    try {
        mostrarNotificacion('Generando reporte Excel...', 'info');
        
        const response = await fetch('http://127.0.0.1:5000/api/productos/listar');
        const data = await response.json();
        
        if (data.status === 'success') {
            let csvContent = "Código Sistema,Descripción,Por Pulir,Terminado,Ensamble,Cliente,Total,Estado,Stock Mínimo,Unidad\n";
            
            data.items.forEach(item => {
                const p = item.producto;
                const e = item.existencias;
                
                csvContent += `"${p.codigo_sistema}","${p.descripcion}",${e.por_pulir},${e.terminado},${e.ensamblado},${e.total},${p.estado},${p.stock_minimo},"${p.unidad}"\n`;
            });
            
            const fecha = new Date().toISOString().split('T')[0];
            downloadFile(`productos_${fecha}.csv`, csvContent, 'text/csv');
            mostrarNotificacion('Reporte exportado exitosamente', 'success');
        }
    } catch (error) {
        console.error('Error exportando productos:', error);
        mostrarNotificacion('Error al exportar productos', 'error');
    }
}

// Exportar funciones globales
window.cargarProductos = cargarProductos;
window.filtrarProductos = filtrarProductos;
window.buscarProductos = buscarProductos;
window.verDetalleProducto = verDetalleProducto;
window.cargarEstadisticas = cargarEstadisticas;
window.exportarProductosExcel = exportarProductosExcel;