// app.js - Gestión principal de la aplicación
// ===========================================

// ===== INICIALIZACIÓN DE LA APLICACIÓN =====

// Estado global de la aplicación
window.AppState = {
    currentPage: 'dashboard',
    productosData: [],
    productos: [],
    responsables: [],
    clientes: [],
    criteriosPNC: {},
    dashboardData: {
        indicador_inyeccion: { meta: 10000, actual: 0, pnc: 0 },
        indicador_pulido: { meta: 8000, actual: 0, pnc: 0 },
        ranking_inyeccion: [],
        produccion_maquina_avanzado: [],
        ventas_cliente_detallado: [],
        stock_inteligente: { criticos: [], bajo_stock: [] }
    }
};

// ===== FUNCIONES DE UTILIDAD =====

function mostrarLoading(mostrar) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = mostrar ? 'flex' : 'none';
    }
}

function mostrarNotificacion(mensaje, tipo = 'info') {
    console.log(`[${tipo.toUpperCase()}] ${mensaje}`);
    
    // Crear notificación visual
    const notificationDiv = document.createElement('div');
    notificationDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10002;
        animation: slideInRight 0.3s ease;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        max-width: 400px;
    `;
    
    // Colores según tipo
    switch(tipo) {
        case 'success':
            notificationDiv.style.backgroundColor = '#10b981';
            break;
        case 'error':
            notificationDiv.style.backgroundColor = '#ef4444';
            break;
        case 'warning':
            notificationDiv.style.backgroundColor = '#f59e0b';
            break;
        default:
            notificationDiv.style.backgroundColor = '#6366f1';
    }
    
    notificationDiv.textContent = mensaje;
    document.body.appendChild(notificationDiv);
    
    // Agregar animación CSS si no existe
    if (!document.querySelector('style#notification-animations')) {
        const style = document.createElement('style');
        style.id = 'notification-animations';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Remover después de 5 segundos
    setTimeout(() => {
        notificationDiv.style.animation = 'fadeOut 0.5s ease';
        setTimeout(() => {
            if (notificationDiv.parentNode) {
                notificationDiv.parentNode.removeChild(notificationDiv);
            }
        }, 500);
    }, 5000);
}

async function fetchData(url) {
    try {
        console.log(`Fetching data from: ${url}`);
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();
        console.log(`Data fetched from ${url}:`, data);
        return data;
    } catch (error) {
        console.error(`Error fetching ${url}:`, error);
        mostrarNotificacion(`Error al cargar datos: ${error.message}`, 'error');
        return null;
    }
}

function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    return parseFloat(num).toLocaleString('es-CO');
}

function getEstadoStock(stockActual, stockMinimo) {
    stockActual = parseFloat(stockActual || 0);
    stockMinimo = parseFloat(stockMinimo || 0);
    
    if (stockActual <= 0) {
        return { estado: 'AGOTADO', clase: 'bg-danger' };
    } else if (stockActual < stockMinimo) {
        return { estado: 'BAJO STOCK', clase: 'bg-warning' };
    } else {
        return { estado: 'STOCK OK', clase: 'bg-success' };
    }
}

// ===== FUNCIÓN CORREGIDA PARA NORMALIZAR IMÁGENES =====

function normalizarImagenProducto(imagenRaw) {
    if (!imagenRaw) return null;
    const val = String(imagenRaw).trim();
    if (!val) return null;
    
    // DEVUELVE LA URL TAL CUAL VIENE DE SHEETS
    return val;
}

// Placeholders remotos (URLs públicas)
const PLACEHOLDER_THUMB = 'https://placehold.co/40x40/e9ecef/d1d5db?text=IMG';
const PLACEHOLDER_MODAL = 'https://placehold.co/300x200/e9ecef/6b7280?text=Sin+Imagen';

// ===== FUNCIONES PARA CAVIDADES =====

function actualizarCalculoProduccion() {
    const cantidadDisparos = parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0;
    const cavidades = parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1;
    const pnc = parseInt(document.getElementById('pnc-inyeccion')?.value) || 0;
    
    const piezasTotales = cantidadDisparos * cavidades;
    const piezasBuenas = Math.max(0, piezasTotales - pnc);
    
    const produccionCalculada = document.getElementById('produccion-calculada');
    const formulaCalc = document.getElementById('formula-calc');
    
    if (produccionCalculada) {
        produccionCalculada.textContent = formatNumber(piezasBuenas);
        produccionCalculada.style.color = piezasBuenas > 0 ? '#10b981' : '#6b7280';
    }
    
    if (formulaCalc) {
        if (pnc > 0) {
            formulaCalc.innerHTML = `
                <span>Disparos (${cantidadDisparos}) × Cavidades (${cavidades}) = ${piezasTotales} piezas</span>
                <span style="color: #ef4444; margin-left: 5px;">- ${pnc} PNC = ${piezasBuenas} piezas buenas</span>
            `;
        } else {
            formulaCalc.textContent = `Disparos (${cantidadDisparos}) × Cavidades (${cavidades}) = ${piezasTotales} piezas`;
        }
    }
    
    return { piezasTotales, piezasBuenas, cavidades };
}

function configurarCalculadoraInyeccion() {
    const cantidadInput = document.getElementById('cantidad-inyeccion');
    const cavidadesSelect = document.getElementById('cavidades-inyeccion');
    const pncInput = document.getElementById('pnc-inyeccion');
    
    if (cantidadInput) {
        cantidadInput.addEventListener('input', actualizarCalculoProduccion);
    }
    if (cavidadesSelect) {
        cavidadesSelect.addEventListener('change', actualizarCalculoProduccion);
    }
    if (pncInput) {
        pncInput.addEventListener('input', actualizarCalculoProduccion);
    }
}

async function cargarConfiguracionCavidades() {
    try {
        const response = await fetch('/api/cavidades/config');
        if (response.ok) {
            const data = await response.json();
            if (data.status === 'success' && data.config) {
                return data.config;
            }
        }
    } catch (error) {
        console.error('Error cargando configuración de cavidades:', error);
    }
    
    // Configuración por defecto
    return {
        cavidades_disponibles: [1, 2, 4, 6, 8, 12, 16, 24, 32, 48],
        cavidades_por_defecto: 4,
        maquinas_config: {}
    };
}

async function actualizarCavidadesPorMaquina(maquina) {
    const selectCavidades = document.getElementById('cavidades-inyeccion');
    if (!selectCavidades) return;
    
    const config = await cargarConfiguracionCavidades();
    
    // Guardar valor actual
    const currentValue = selectCavidades.value;
    
    // Limpiar opciones
    selectCavidades.innerHTML = '';
    
    // Obtener cavidades específicas para la máquina
    let cavidades = config.cavidades_disponibles;
    let defaultCavidades = config.cavidades_por_defecto;
    
    if (config.maquinas_config[maquina]) {
        cavidades = config.maquinas_config[maquina].cavidades || cavidades;
        defaultCavidades = config.maquinas_config[maquina].default || defaultCavidades;
    }
    
    // Agregar opciones
    cavidades.forEach(num => {
        const option = document.createElement('option');
        option.value = num;
        option.textContent = num === 1 ? '1 Cavidad' : `${num} Cavidades`;
        if (num === defaultCavidades) {
            option.selected = true;
        }
        selectCavidades.appendChild(option);
    });
    
    // Restaurar valor si existe
    if (currentValue && cavidades.includes(parseInt(currentValue))) {
        selectCavidades.value = currentValue;
    }
    
    // Actualizar cálculo
    actualizarCalculoProduccion();
}

// ===== GESTIÓN DE NAVEGACIÓN =====

function getPageName(pageId) {
    const nombres = {
        'dashboard': 'Dashboard Analítico',
        'inventario': 'Productos y Existencias',
        'inyeccion': 'Registro de Inyección',
        'pulido': 'Registro de Pulido',
        'ensamble': 'Registro de Ensamble',
        'facturacion': 'Facturación',
        'reportes': 'Reportes'
    };
    return nombres[pageId] || pageId;
}

function cargarPagina(pagina) {
    console.log(`Cargando página: ${pagina}`);
    
    // Actualizar estado
    window.AppState.currentPage = pagina;
    
    // Actualizar menú activo
    document.querySelectorAll('.menu-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === pagina) {
            item.classList.add('active');
        }
    });
    
    // Ocultar todas las páginas primero
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
        page.style.display = 'none';
    });
    
    // Mostrar página seleccionada
    const paginaElement = document.getElementById(`${pagina}-page`);
    if (paginaElement) {
        paginaElement.classList.add('active');
        paginaElement.style.display = 'block';
    }
    
    // Ocultar detalles de producto si están visibles
    const detalleProducto = document.getElementById('detalle-producto');
    if (detalleProducto) {
        detalleProducto.classList.remove('active');
        detalleProducto.style.display = 'none';
    }
    
    // Ocultar modales existentes
    document.querySelectorAll('.modal').forEach(modal => {
        modal.style.display = 'none';
    });
    
    // Cargar datos específicos de la página
    switch(pagina) {
        case 'dashboard':
            inicializarDashboard();
            break;
        case 'inventario':
            cargarProductos();
            configurarEventosInventario();
            break;
        case 'inyeccion':
            cargarDatosInyeccion();
            break;
        case 'pulido':
            cargarDatosPulido();
            break;
        case 'ensamble':
            cargarDatosEnsamble();
            break;
        case 'facturacion':
            cargarDatosFacturacion();
            break;
        case 'reportes':
            cargarDatosReportes();
            break;
    }
    
    mostrarNotificacion(`Página ${getPageName(pagina)} cargada`, 'info');
}

// ===== CARGA DE DATOS INICIALES =====

async function cargarDatosIniciales() {
    try {
        mostrarLoading(true);
        console.log('Cargando datos iniciales...');
        
        // Cargar responsables
        const responsables = await fetchData('/api/obtener_responsables');
        if (responsables) {
            window.AppState.responsables = responsables;
            actualizarSelectsResponsables(responsables);
            console.log('Responsables cargados:', responsables.length);
        }
        
        // Cargar clientes
        const clientes = await fetchData('/api/obtener_clientes');
        if (clientes) {
            window.AppState.clientes = clientes;
            actualizarSelectClientes(clientes);
            console.log('Clientes cargados:', clientes.length);
        }
        

        // 🆕 Cargar máquinas válidas
        const maquinas = await fetchData('/api/obtener_maquinas');
        if (maquinas) {
            window.AppState.maquinas = maquinas;
            actualizarSelectMaquinas(maquinas);
            console.log('✅ Máquinas cargadas:', maquinas.length);
        }


        // Cargar productos para selects
        const productos = await fetchData('/api/obtener_productos');
        if (productos) {
            window.AppState.productos = productos;
            actualizarSelectsProductos(productos);
            console.log('Lista de productos cargada:', productos.length);
        }
        
        // Cargar criterios PNC para cada formulario
        await Promise.all([
            cargarCriteriosPNC('inyeccion', 'criterio-pnc-inyeccion'),
            cargarCriteriosPNC('pulido', 'criterio-pnc-pulido'),
            cargarCriteriosPNC('ensamble', 'criterio-pnc-ensamble')
        ]);
        
        mostrarLoading(false);
        console.log('Datos iniciales cargados correctamente');
        
    } catch (error) {
        console.error('Error cargando datos iniciales:', error);
        mostrarNotificacion('Error cargando datos iniciales', 'error');
        mostrarLoading(false);
    }
}

function actualizarSelectsResponsables(responsables) {
    const selects = document.querySelectorAll('select[id*="responsable"]');
    selects.forEach(select => {
        const currentValue = select.value;
        select.innerHTML = '<option value="">Seleccionar responsable...</option>';
        
        if (responsables && Array.isArray(responsables)) {
            responsables.forEach(responsable => {
                const option = document.createElement('option');
                option.value = responsable;
                option.textContent = responsable;
                select.appendChild(option);
            });
        }
        
        // Restaurar valor seleccionado si existe
        if (currentValue) {
            select.value = currentValue;
        }
    });
}

function actualizarSelectClientes(clientes) {
    const select = document.getElementById('cliente-facturacion');
    if (select) {
        const currentValue = select.value;
        select.innerHTML = '<option value="">Seleccionar cliente...</option>';
        
        if (clientes && Array.isArray(clientes)) {
            clientes.forEach(cliente => {
                const option = document.createElement('option');
                option.value = cliente;
                option.textContent = cliente;
                select.appendChild(option);
            });
        }
        
        if (currentValue) {
            select.value = currentValue;
        }
    }
}

function actualizarSelectsProductos(productos) {
    const selects = document.querySelectorAll('select[id*="producto"]');
    selects.forEach(select => {
        const currentValue = select.value;
        select.innerHTML = '<option value="">Buscar producto...</option>';
        
        if (productos && Array.isArray(productos)) {
            productos.forEach(producto => {
                const option = document.createElement('option');
                option.value = producto;
                option.textContent = producto;
                select.appendChild(option);
            });
        }
        
        if (currentValue) {
            select.value = currentValue;
        }
    });
}

async function cargarCriteriosPNC(tipo, selectId) {
    try {
        console.log(`Cargando criterios PNC para ${tipo}...`);
        
        // Cargar desde la API
        const response = await fetch(`/api/obtener_criterios_pnc/${tipo}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const criterios = await response.json();
        
        const select = document.getElementById(selectId);
        if (select) {
            // Guardar valor actual
            const currentValue = select.value;
            
            // Limpiar y agregar opciones
            select.innerHTML = '<option value="">Seleccionar criterio...</option>';
            
            if (criterios && Array.isArray(criterios) && criterios.length > 0) {
                criterios.forEach(criterio => {
                    const option = document.createElement('option');
                    option.value = criterio;
                    option.textContent = criterio;
                    select.appendChild(option);
                });
            } else {
                // Cargar criterios por defecto si no hay datos
                cargarCriteriosPNCDefault(tipo, select);
            }
            
            // Restaurar valor si existe
            if (currentValue) {
                select.value = currentValue;
            }
            
            console.log(`Criterios PNC para ${tipo} cargados: ${criterios?.length || 0}`);
        }
    } catch (error) {
        console.error(`Error cargando criterios PNC para ${tipo}:`, error);
        
        // Cargar criterios por defecto en caso de error
        const select = document.getElementById(selectId);
        if (select) {
            cargarCriteriosPNCDefault(tipo, select);
        }
    }
}

function cargarCriteriosPNCDefault(tipo, select) {
    let criteriosDefault = [];
    
    switch(tipo) {
        case 'inyeccion':
            criteriosDefault = ["Carcaza manchada", "Carcaza abierta", "Material defectuoso", "Buje de prueba", "Otro"];
            break;
        case 'pulido':
            criteriosDefault = ["Daño en pulido", "Acabado defectuoso", "Rayones", "Contaminado", "Otro"];
            break;
        case 'ensamble':
            criteriosDefault = ["Falta de piezas", "Ensamblaje defectuoso", "Daño en transporte", "Prueba", "Otro"];
            break;
    }
    
    select.innerHTML = '<option value="">Seleccionar criterio...</option>';
    criteriosDefault.forEach(criterio => {
        const option = document.createElement('option');
        option.value = criterio;
        option.textContent = criterio;
        select.appendChild(option);
    });
    
    console.log(`Criterios PNC por defecto cargados para ${tipo}: ${criteriosDefault.length}`);
}

// ===== GESTIÓN DE INVENTARIO =====

async function cargarProductos() {
    console.log('Cargando productos para inventario...');
    try {
        const response = await fetch('/api/productos/listar');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Datos recibidos del servidor:', data);

        // Procesar datos recibidos
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

function renderizarTablaProductos(productos) {
    console.log("Renderizando tabla de productos...");
    const tbody = document.getElementById("tabla-productos-body");
    if (!tbody) {
        console.error("ERROR: No se encontró el elemento tabla-productos-body");
        return;
    }

    if (!productos || productos.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align:center; padding:40px; color:#666;">
                    <i class="fas fa-box-open" style="font-size: 2rem; margin-bottom: 10px; display: block;"></i>
                    <p>No hay productos para mostrar</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = productos
        .map((p) => {
            // Soportar formato { producto: { ... } } o plano
            const producto = p.producto || p;
            const existencias = p.existencias || producto.existencias || {};

            const codigoSistema =
                producto.codigo_sistema ||
                producto.codigosistema ||
                producto["CODIGO SISTEMA"] ||
                "";

            const descripcion =
                producto.descripcion ||
                producto.PRODUCTO ||
                producto.DESCRIPCION ||
                "Sin descripción";

            const oem =
                producto.oem ||
                producto.OEM ||
                "-";

            const unidad =
                producto.unidad ||
                producto.UNIDAD ||
                "PZ";

            const porPulir  = existencias.por_pulir ?? 0;
            const terminado = existencias.terminado ?? 0;
            const total     = existencias.total ?? 0;
            const stockMinimo =
                producto.stock_minimo ??
                producto.stockminimo ??
                producto.STOCKMINIMO ??
                0;    

            const estado = getEstadoStock(total, stockMinimo);

            // CORRECCIÓN: NORMALIZAR LA IMAGEN - usar placeholder remoto si no hay URL
            const imagenUrl = normalizarImagenProducto(producto.IMAGEN) || PLACEHOLDER_THUMB;

            console.log("Fila producto:", {
                codigoSistema,
                porPulir,
                terminado,
                imagenRaw: producto.IMAGEN,
                imagenNormalizada: imagenUrl,
                existencias: producto.existencias
            });

            return `
              <tr data-codigo="${codigoSistema}" style="cursor:pointer;">
                <!-- IMAGEN -->
                <td style="padding:10px 12px;">
                  <div style="display:flex; align-items:center; justify-content:center;">
                    <img src="${imagenUrl}"
                         style="width:40px; height:40px; object-fit:cover; border-radius:6px; border:1px solid #ddd;"
                         alt="${descripcion}"
                         onerror="this.src='${PLACEHOLDER_THUMB}'">
                  </div>
                </td>

                
                <td style="padding:10px 12px;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <span style="width:8px; height:8px; border-radius:999px; background:#10b981; display:inline-block;"></span>
                    <span style="font-weight:600; color:#111827; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;">
                      ${codigoSistema}
                    </span>
                  </div>
                </td>

                
                <td style="padding:10px 12px;">
                  <div style="font-weight:600; color:#111827; margin-bottom:2px;">
                    ${descripcion}
                  </div>
                  <div style="font-size:0.75rem; color:#9ca3af;">
                    OEM ${oem || 'N/A'}
                  </div>
                </td>

                <!-- UNIDAD -->
                <td style="padding:10px 12px; text-align:center;">
                  <span style="
                    display:inline-block;
                    padding:4px 10px;
                    background:#f3f4f6;
                    border-radius:6px;
                    font-size:0.875rem;
                    font-weight:500;
                    color:#374151;
                  ">
                    ${unidad}
                  </span>
                </td>

                <!-- POR PULIR -->
                <td class="col-num">
                  <span class="badge-stock ${
                    porPulir === 0
                      ? 'badge-stock-zero'
                      : porPulir < stockMinimo
                      ? 'badge-stock-low'
                      : 'badge-stock-ok'
                  }">
                    ${formatNumber(porPulir)}
                  </span>
                </td>
              
                <!-- P. TERMINADO -->
                <td class="col-num">
                  <span class="badge-stock ${
                    terminado === 0
                      ? 'badge-stock-zero'
                      : terminado < stockMinimo
                      ? 'badge-stock-low'
                      : 'badge-stock-ok'
                  }">
                    ${formatNumber(terminado)}
                  </span>
                </td>
              
                <!-- ACCIONES -->
                <td style="padding:10px 12px; text-align:center;">
                  <button class="btn-icon"
                          onclick="event.stopPropagation(); verDetalleProducto('${codigoSistema}')">
                    <i class="fas fa-eye" style="color:#6366f1;"></i>
                  </button>
                </td>
              </tr>
            `;

        })
        .join("");

    // Eventos de click en filas para abrir detalle
    tbody.querySelectorAll("tr[data-codigo]").forEach((row) => {
        row.addEventListener("click", function () {
            const codigo = this.dataset.codigo;
            if (codigo) {
                verDetalleProducto(codigo);
            }
        });
    });
}

function actualizarEstadisticasInventario(productos) {
    if (!productos || !Array.isArray(productos)) {
        console.warn('No hay datos para estadísticas');
        return;
    }
    
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
    
    // Actualizar elementos HTML
    const updateElement = (id, value, color = null) => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = formatNumber(value);
            if (color) {
                el.style.color = color;
            }
        }
    };
    
    updateElement('total-productos', totalProductos);
    updateElement('productos-bajo-stock', stockBajo, stockBajo > 0 ? '#f59e0b' : null);
    updateElement('productos-agotados', sinStock, sinStock > 0 ? '#ef4444' : null);
    updateElement('productos-stock-ok', stockOk, stockOk > 0 ? '#10b981' : null);
    
    console.log(`Estadísticas: Total=${totalProductos}, Bajo=${stockBajo}, Sin=${sinStock}, OK=${stockOk}`);
}

function buscarProductos() {
    const buscarInput = document.getElementById('buscar-producto');
    if (!buscarInput || !window.AppState.productosData || window.AppState.productosData.length === 0) {
        console.warn('No hay datos para buscar');
        return;
    }

    const termino = buscarInput.value.toLowerCase().trim();
    console.log('Buscando por término:', termino);

    if (!termino) {
        // Sin texto: mostrar todos
        renderizarTablaProductos(window.AppState.productosData);
        return;
    }

    // Función para buscar en cualquier campo numérico o de texto
    const productosFiltrados = window.AppState.productosData.filter((p) => {
        const prod = p.producto || p;

        // Buscar en todos los campos posibles
        const camposABuscar = [
            prod.codigo_sistema,
            prod.codigo_interno,
            prod.codigo,
            prod.codigosistema,
            prod['CODIGO SISTEMA'],
            prod.id_codigo,
            prod.ID_CODIGO,
            prod.descripcion,
            prod.nombre,
            prod.DESCRIPCION,
            prod.oem,
            prod.OEM,
            prod.codigo_alterno,
            prod.codigo_fabricante,
            prod.referencia,
            prod.categoria,
            prod.marca
        ].filter(val => val); // Remover valores undefined o null

        // Buscar el término en todos los campos
        return camposABuscar.some(campo => {
            if (campo) {
                const valorBusqueda = String(campo).toLowerCase();
                
                // Buscar coincidencia exacta o parcial
                if (valorBusqueda.includes(termino)) {
                    return true;
                }
                
                // Buscar números que contengan el término (si el término es numérico)
                if (/^\d+$/.test(termino)) {
                    // Buscar en cualquier parte del número
                    if (valorBusqueda.replace(/\D/g, '').includes(termino)) {
                        return true;
                    }
                }
            }
            return false;
        });
    });

    console.log('Resultados encontrados:', productosFiltrados.length);
    
    if (productosFiltrados.length > 0) {
        renderizarTablaProductos(productosFiltrados);
        mostrarNotificacion(`Se encontraron ${productosFiltrados.length} productos`, 'info');
    } else {
        renderizarTablaProductos([]);
        mostrarNotificacion('No se encontraron productos con ese criterio', 'info');
    }
}

function filtrarProductos(filtro) {
    if (!window.AppState.productosData || window.AppState.productosData.length === 0) {
        console.warn("No hay datos para filtrar");
        return;
    }

    let resultados;
    const productos = window.AppState.productosData;
    console.log("Aplicando filtro:", filtro);

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

        default: // "todos"
            resultados = productos;
            break;
    }

    console.log("Productos filtrados:", resultados.length);
    renderizarTablaProductos(resultados);

    // Actualizar botones activos
    document.querySelectorAll(".filter-btn").forEach((btn) => {
        btn.classList.remove("active");
        if (btn.dataset.filter === filtro) {
            btn.classList.add("active");
        }
    });
}

function configurarEventosInventario() {
    // Buscador
    const buscarInput = document.getElementById('buscar-producto');
    if (buscarInput) {
        buscarInput.addEventListener('input', buscarProductos);
    }
    
    // Botones de filtro
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const filtro = this.dataset.filter;
            if (filtro) {
                filtrarProductos(filtro);
            }
        });
    });
    
    // Botón de actualizar
    const btnActualizar = document.getElementById('btn-actualizar-productos');
    if (btnActualizar) {
        btnActualizar.addEventListener('click', cargarProductos);
    }
    
    // Botón de nuevo producto
    const btnNuevoProducto = document.getElementById('btn-nuevo-producto');
    if (btnNuevoProducto) {
        btnNuevoProducto.addEventListener('click', mostrarModalNuevoProducto);
    }
    
    // Botón de exportar
    const btnExportar = document.getElementById('btn-exportar-inventario');
    if (btnExportar) {
        btnExportar.addEventListener('click', exportarInventario);
    }
}

// ===== DETALLE DE PRODUCTO - VERSIÓN COMPLETA CON CIERRE CORRECTO =====

async function verDetalleProducto(codigoSistema) {
    console.log('Ver detalle de producto:', codigoSistema);
    
    try {
        mostrarLoading(true);

        // ✅ 1. FETCH DEL DETALLE DEL PRODUCTO
        console.log(`🔍 Fetching: /api/productos/detalle/${codigoSistema}`);
        const response = await fetch(`/api/productos/detalle/${codigoSistema}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const detalle = await response.json();
        console.log("📦 DATOS DEL PRODUCTO:", detalle);

        const producto = detalle.producto || {};
        
        if (!producto.codigo_sistema && !producto.codigo) {
            throw new Error("Producto no encontrado en la respuesta");
        }

        // ✅ 2. FETCH DE MOVIMIENTOS
        let movimientos = [];
        try {
            console.log("🔄 Obteniendo movimientos para:", codigoSistema);
            const movResponse = await fetch(`/api/productos/movimientos/${codigoSistema}`);
            
            if (movResponse.ok) {
                const movData = await movResponse.json();
                console.log("📊 DATOS DE MOVIMIENTOS:", movData);
                
                const movimientosRaw = movData.movimientos || [];
                console.log(`📊 Movimientos crudos recibidos: ${movimientosRaw.length}`);
                
                // Normalizar campos
                movimientos = movimientosRaw.map(mov => ({
                    fecha_inicio: mov.fecha_inicio || mov.fecha || mov.FECHA_INICIO || mov.fecha_creacion || new Date().toISOString(),
                    transaction_type: mov.transaction_type || mov.tipo || mov.TRANSACTION_TYPE || mov.tipo_movimiento || 'INY',
                    cantidad_real: mov.cantidad_real || mov.cantidad || mov.CANTIDAD_REAL || mov.cantidad_total || 0,
                    responsable: mov.responsable || mov.RESPONSABLE || mov.usuario || 'Desconocido',
                    maquina: mov.maquina || mov.MAQUINA || mov.maquina_id || 'N/A',
                    PNC: mov.PNC !== undefined ? mov.PNC : (mov.pnc !== undefined ? mov.pnc : 0),
                    estado: mov.estado || mov.ESTADO || mov.status || 'COMPLETADO'
                }));
                
                console.log("✅ Movimientos obtenidos:", movimientos.length);
                
            } else {
                console.warn("⚠️ No se pudieron obtener movimientos, status:", movResponse.status);
                movimientos = [];
            }
        } catch (error) {
            console.error("❌ Error obteniendo movimientos:", error);
            movimientos = [];
        }

        // ✅ 3. PROCESAR DATOS DEL PRODUCTO
        const stockPorPulir = producto.stock_por_pulir ?? 0;
        const stockTerminado = producto.stock_terminado ?? 0;
        const stockActual = producto.stock_total ?? (stockPorPulir + stockTerminado);
        const stockMinimo = producto.stock_minimo ?? 0;
        const estadoStock = getEstadoStockModal(stockActual, stockMinimo);

        // CORRECCIÓN: NORMALIZAR LA RUTA DE LA IMAGEN
        const imagenUrl = normalizarImagenProducto(
            producto.imagen || 
            producto.IMAGEN || 
            producto.imagen_url
        ) || PLACEHOLDER_MODAL;

        // ✅ 4. GENERAR HTML DE MOVIMIENTOS
        const htmlMovimientos = generarMovimientosHTMLModal(movimientos, codigoSistema);

        // ✅ 5. GENERAR HTML COMPLETO DEL MODAL
        console.log('🖨️ Generando HTML para movimientos...');

        const modalHtml = `
            <div id="modalDetalleProducto" class="custom-modal-overlay" style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
                opacity: 0;
                animation: fadeIn 0.3s ease forwards;
            ">
                <div class="custom-modal" style="
                    background: white;
                    border-radius: 12px;
                    width: 90%;
                    max-width: 1200px;
                    max-height: 90vh;
                    overflow-y: auto;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    position: relative;
                ">
                    <!-- Header del Modal -->
                    <div class="custom-modal-header" style="
                        padding: 20px 24px;
                        border-bottom: 1px solid #e5e7eb;
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 12px 12px 0 0;
                        color: white;
                    ">
                        <h5 class="custom-modal-title" style="
                            margin: 0;
                            font-size: 1.5rem;
                            font-weight: 600;
                            display: flex;
                            align-items: center;
                            gap: 10px;
                        ">
                            <i class="fas fa-cube"></i>
                            ${producto.descripcion || producto.nombre || 'Detalle de producto'}
                        </h5>
                        <button id="btnCerrarDetalleProductoHeader" class="btn-cerrar-modal" style="
                            background: transparent;
                            border: none;
                            font-size: 1.8rem;
                            color: white;
                            cursor: pointer;
                            width: 40px;
                            height: 40px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            border-radius: 50%;
                            transition: background 0.2s;
                        ">
                            &times;
                        </button>
                    </div>
                    
                    <!-- Body del Modal -->
                    <div class="custom-modal-body" style="padding: 24px;">
                        <!-- Contenido del detalle del producto -->
                        <div style="display: grid; grid-template-columns: 300px 1fr; gap: 24px;">
                            <!-- Columna izquierda: Imagen y datos básicos -->
                            <div>
                                <!-- Imagen del producto -->
                                <div style="margin-bottom: 20px;">
                                    <img src="${imagenUrl}" 
                                         alt="${producto.descripcion || 'Producto'}" 
                                         style="
                                            width: 100%;
                                            height: 200px;
                                            object-fit: cover;
                                            border-radius: 8px;
                                            border: 1px solid #e5e7eb;
                                         "
                                         onerror="this.src='${PLACEHOLDER_MODAL}'">
                                </div>
                                
                                <!-- Información básica -->
                                <div style="background: #f9fafb; padding: 16px; border-radius: 8px;">
                                    <h6 style="margin-top: 0; margin-bottom: 12px; color: #374151;">
                                        <i class="fas fa-info-circle"></i> Información Básica
                                    </h6>
                                    
                                    <div style="display: grid; gap: 8px;">
                                        <div>
                                            <small style="color: #6b7280; display: block;">Código Sistema</small>
                                            <strong style="color: #111827;">${producto.codigo_sistema || producto.codigo || 'N/A'}</strong>
                                        </div>
                                        
                                        ${producto.codigo_interno ? `
                                        <div>
                                            <small style="color: #6b7280; display: block;">Código Interno</small>
                                            <strong style="color: #111827;">${producto.codigo_interno}</strong>
                                        </div>
                                        ` : ''}
                                        
                                        ${producto.proveedor ? `
                                        <div>
                                            <small style="color: #6b7280; display: block;">Proveedor</small>
                                            <strong style="color: #111827;">${producto.proveedor}</strong>
                                        </div>
                                        ` : ''}
                                        
                                        <div>
                                            <small style="color: #6b7280; display: block;">Estado</small>
                                            <span style="
                                                display: inline-block;
                                                padding: 4px 12px;
                                                border-radius: 20px;
                                                font-size: 0.875rem;
                                                font-weight: 500;
                                                background: ${producto.activo !== false ? '#10b981' : '#ef4444'};
                                                color: white;
                                            ">
                                                ${producto.activo !== false ? 'ACTIVO' : 'INACTIVO'}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Estado del stock -->
                                <div style="margin-top: 20px; background: #f9fafb; padding: 16px; border-radius: 8px;">
                                    <h6 style="margin-top: 0; margin-bottom: 12px; color: #374151;">
                                        <i class="fas fa-boxes"></i> Estado del Stock
                                    </h6>
                                    
                                    <div style="display: grid; gap: 12px;">
                                        <div style="display: flex; justify-content: space-between;">
                                            <span style="color: #6b7280;">Por pulir</span>
                                            <span style="font-weight: 600; color: #111827;">${formatNumber(stockPorPulir)}</span>
                                        </div>
                                        
                                        <div style="display: flex; justify-content: space-between;">
                                            <span style="color: #6b7280;">Terminado</span>
                                            <span style="font-weight: 600; color: #111827;">${formatNumber(stockTerminado)}</span>
                                        </div>
                                        
                                        <div style="display: flex; justify-content: space-between;">
                                            <span style="color: #6b7280;">Stock actual</span>
                                            <span style="font-weight: 600; color: ${estadoStock.color || '#111827'};">${formatNumber(stockActual)}</span>
                                        </div>
                                        
                                        <div style="display: flex; justify-content: space-between;">
                                            <span style="color: #6b7280;">Stock mínimo</span>
                                            <span style="font-weight: 600; color: #111827;">${formatNumber(stockMinimo)}</span>
                                        </div>
                                        
                                        <div style="text-align: center; margin-top: 8px;">
                                            <span style="
                                                display: inline-block;
                                                padding: 6px 16px;
                                                border-radius: 20px;
                                                font-size: 0.875rem;
                                                font-weight: 600;
                                                background: ${estadoStock.bgColor || '#6b7280'};
                                                color: white;
                                            ">
                                                ${estadoStock.text}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Columna derecha: Tabs y contenido -->
                            <div>
                                <!-- Tabs de navegación -->
                                <div style="margin-bottom: 20px; border-bottom: 1px solid #e5e7eb;">
                                    <div style="display: flex; gap: 4px;">
                                        <button class="tab-btn active" data-tab="info" style="
                                            padding: 10px 16px;
                                            background: transparent;
                                            border: none;
                                            border-bottom: 2px solid #6366f1;
                                            color: #6366f1;
                                            font-weight: 500;
                                            cursor: pointer;
                                            display: flex;
                                            align-items: center;
                                            gap: 6px;
                                        ">
                                            <i class="fas fa-info-circle"></i>
                                            Información
                                        </button>
                                        
                                        <button class="tab-btn" data-tab="precios" style="
                                            padding: 10px 16px;
                                            background: transparent;
                                            border: none;
                                            border-bottom: 2px solid transparent;
                                            color: #6b7280;
                                            font-weight: 500;
                                            cursor: pointer;
                                            display: flex;
                                            align-items: center;
                                            gap: 6px;
                                        ">
                                            <i class="fas fa-money-bill-wave"></i>
                                            Precios
                                        </button>
                                        
                                        <button class="tab-btn" data-tab="movimientos" style="
                                            padding: 10px 16px;
                                            background: transparent;
                                            border: none;
                                            border-bottom: 2px solid transparent;
                                            color: #6b7280;
                                            font-weight: 500;
                                            cursor: pointer;
                                            display: flex;
                                            align-items: center;
                                            gap: 6px;
                                            position: relative;
                                        ">
                                            <i class="fas fa-history"></i>
                                            Movimientos
                                            ${movimientos.length > 0 ? `
                                            <span style="
                                                background: #ef4444;
                                                color: white;
                                                font-size: 0.75rem;
                                                padding: 2px 6px;
                                                border-radius: 10px;
                                                margin-left: 4px;
                                            ">
                                                ${movimientos.length}
                                            </span>
                                            ` : ''}
                                        </button>
                                    </div>
                                </div>
                                
                                <!-- Contenido de los tabs -->
                                <div id="tab-content-area">
                                    <!-- Tab Información -->
                                    <div class="tab-content active" id="tab-info" style="display: block;">
                                        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 16px;">
                                            <div style="background: #f9fafb; padding: 16px; border-radius: 8px;">
                                                <small style="color: #6b7280; display: block;">Descripción</small>
                                                <div style="margin-top: 4px; color: #111827;">
                                                    ${producto.descripcion_larga || producto.descripcion || 'Sin descripción'}
                                                </div>
                                            </div>
                                            
                                            <div style="background: #f9fafb; padding: 16px; border-radius: 8px;">
                                                <small style="color: #6b7280; display: block;">Categoría</small>
                                                <div style="margin-top: 4px; color: #111827;">
                                                    ${producto.categoria || 'No asignada'}
                                                </div>
                                            </div>
                                            
                                            <div style="background: #f9fafb; padding: 16px; border-radius: 8px;">
                                                <small style="color: #6b7280; display: block;">Marca</small>
                                                <div style="margin-top: 4px; color: #111827;">
                                                    ${producto.marca || 'No especificada'}
                                                </div>
                                            </div>
                                            
                                            <div style="background: #f9fafb; padding: 16px; border-radius: 8px;">
                                                <small style="color: #6b7280; display: block;">Ubicación</small>
                                                <div style="margin-top: 4px; color: #111827;">
                                                    ${producto.ubicacion || 'No especificada'}
                                                </div>
                                            </div>
                                            
                                            ${producto.material ? `
                                            <div style="background: #f9fafb; padding: 16px; border-radius: 8px;">
                                                <small style="color: #6b7280; display: block;">Material</small>
                                                <div style="margin-top: 4px; color: #111827;">
                                                    ${producto.material}
                                                </div>
                                            </div>
                                            ` : ''}
                                            
                                            ${producto.color ? `
                                            <div style="background: #f9fafb; padding: 16px; border-radius: 8px;">
                                                <small style="color: #6b7280; display: block;">Color</small>
                                                <div style="margin-top: 4px; color: #111827;">
                                                    ${producto.color}
                                                </div>
                                            </div>
                                            ` : ''}
                                        </div>
                                    </div>
                                    
                                    <!-- Tab Precios -->
                                    <div class="tab-content" id="tab-precios" style="display: none;">
                                        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px;">
                                            ${producto.precio_compra ? `
                                            <div style="background: #f9fafb; padding: 20px; border-radius: 8px; text-align: center;">
                                                <small style="color: #6b7280; display: block;">Precio Compra</small>
                                                <div style="margin-top: 8px; font-size: 1.5rem; font-weight: 600; color: #059669;">
                                                    $${formatCurrency(parseFloat(producto.precio_compra))}
                                                </div>
                                            </div>
                                            ` : ''}
                                            
                                            ${producto.precio_venta ? `
                                            <div style="background: #f9fafb; padding: 20px; border-radius: 8px; text-align: center;">
                                                <small style="color: #6b7280; display: block;">Precio Venta</small>
                                                <div style="margin-top: 8px; font-size: 1.5rem; font-weight: 600; color: #6366f1;">
                                                    $${formatCurrency(parseFloat(producto.precio_venta))}
                                                </div>
                                            </div>
                                            ` : ''}
                                            
                                            ${producto.precio_venta_sugerido ? `
                                            <div style="background: #f9fafb; padding: 20px; border-radius: 8px; text-align: center;">
                                                <small style="color: #6b7280; display: block;">Precio Sugerido</small>
                                                <div style="margin-top: 8px; font-size: 1.5rem; font-weight: 600; color: #f59e0b;">
                                                    $${formatCurrency(parseFloat(producto.precio_venta_sugerido))}
                                                </div>
                                            </div>
                                            ` : ''}
                                            
                                            ${producto.utilidad_esperada ? `
                                            <div style="background: #f9fafb; padding: 20px; border-radius: 8px; text-align: center;">
                                                <small style="color: #6b7280; display: block;">Utilidad</small>
                                                <div style="margin-top: 8px; font-size: 1.5rem; font-weight: 600; color: #10b981;">
                                                    ${parseFloat(producto.utilidad_esperada).toFixed(2)}%
                                                </div>
                                            </div>
                                            ` : ''}
                                        </div>
                                    </div>
                                    
                                    <!-- Tab Movimientos -->
                                    <div class="tab-content" id="tab-movimientos" style="display: none;">
                                        ${htmlMovimientos}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Footer del Modal -->
                    <div class="custom-modal-footer" style="
                        padding: 16px 24px;
                        border-top: 1px solid #e5e7eb;
                        display: flex;
                        justify-content: flex-end;
                        gap: 12px;
                    ">
                        <button id="btnCerrarDetalleProducto" style="
                            padding: 10px 20px;
                            background: #6b7280;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            font-weight: 500;
                            cursor: pointer;
                            transition: background 0.2s;
                        ">
                            <i class="fas fa-times"></i> Cerrar
                        </button>
                        <button id="btnEditarProducto" style="
                            padding: 10px 20px;
                            background: #6366f1;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            font-weight: 500;
                            cursor: pointer;
                            transition: background 0.2s;
                        ">
                            <i class="fas fa-edit"></i> Editar Producto
                        </button>
                    </div>
                </div>
            </div>
        `;

        // ✅ 6. INSERTAR MODAL EN EL DOM
        const existing = document.getElementById('modalDetalleProducto');
        if (existing) {
            existing.remove();
        }
        const wrapper = document.createElement('div');
        wrapper.innerHTML = modalHtml.trim();
        const modalElement = wrapper.firstChild;
        document.body.appendChild(modalElement);
        document.body.classList.add('modal-open');

        // ✅ 7. AGREGAR ANIMACIONES CSS
        if (!document.querySelector('style#modal-animations')) {
            const style = document.createElement('style');
            style.id = 'modal-animations';
            style.textContent = `
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes fadeOut {
                    from { opacity: 1; }
                    to { opacity: 0; }
                }
                .modal-open {
                    overflow: hidden;
                }
            `;
            document.head.appendChild(style);
        }

        // ✅ 8. CONFIGURAR EVENTOS DE CIERRE
        const btnCerrar = document.getElementById('btnCerrarDetalleProducto');
        const btnCerrarHeader = document.getElementById('btnCerrarDetalleProductoHeader');

        const cerrarModal = () => {
            const modal = document.getElementById('modalDetalleProducto');
            if (modal) {
                modal.style.animation = 'fadeOut 0.3s ease forwards';
                setTimeout(() => {
                    if (modal.parentNode) {
                        modal.parentNode.removeChild(modal);
                    }
                    document.body.classList.remove('modal-open');
                }, 300);
            }
        };

        if (btnCerrar) {
            btnCerrar.addEventListener('click', cerrarModal);
        }
        if (btnCerrarHeader) {
            btnCerrarHeader.addEventListener('click', cerrarModal);
        }

        // Cerrar al hacer clic fuera del contenido
        modalElement.addEventListener('click', (e) => {
            if (e.target.id === 'modalDetalleProducto') {
                cerrarModal();
            }
        });

        // Cerrar con tecla Escape
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                cerrarModal();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);

        // ✅ 9. CONFIGURAR TABS
        configurarTabsModal();

        // ✅ 10. CONFIGURAR BOTÓN EDITAR
        const btnEditar = document.getElementById('btnEditarProducto');
        if (btnEditar) {
            btnEditar.addEventListener('click', () => {
                editarProducto(codigoSistema);
            });
        }

        console.log('✅ Modal creado exitosamente');
        console.log('📊 Resumen:');
        console.log('  - Producto:', producto.codigo_sistema || producto.codigo);
        console.log('  - Movimientos:', movimientos.length);
        console.log('  - Stock actual:', stockActual);
        console.log('  - Estado stock:', estadoStock.text);

    } catch (error) {
        console.error('❌ Error en verDetalleProducto:', error);
        mostrarNotificacion('Error al cargar detalle del producto: ' + error.message, 'error');
    } finally {
        mostrarLoading(false);
    }
}

// ===== FUNCIONES AUXILIARES PARA EL MODAL =====

function configurarTabsModal() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            
            // Remover clase active de todos los botones
            tabBtns.forEach(b => {
                b.style.borderBottom = '2px solid transparent';
                b.style.color = '#6b7280';
            });
            
            // Agregar clase active al botón clickeado
            this.style.borderBottom = '2px solid #6366f1';
            this.style.color = '#6366f1';
            
            // Ocultar todos los contenidos
            tabContents.forEach(content => {
                content.style.display = 'none';
            });
            
            // Mostrar el contenido correspondiente
            const tabContent = document.getElementById(`tab-${tabId}`);
            if (tabContent) {
                tabContent.style.display = 'block';
            }
        });
    });
}

function generarMovimientosHTMLModal(movimientos, codigoSistema) {
    if (!movimientos || movimientos.length === 0) {
        return `
            <div style="
                text-align: center;
                padding: 60px 20px;
                background: #f9fafb;
                border-radius: 8px;
                border: 2px dashed #d1d5db;
            ">
                <i class="fas fa-inbox" style="font-size: 3rem; color: #9ca3af; margin-bottom: 16px;"></i>
                <h4 style="margin: 0 0 8px 0; color: #374151;">No hay movimientos registrados</h4>
                <p style="color: #6b7280; margin: 0;">No se encontraron registros de inyección para este producto.</p>
            </div>
        `;
    }

    const ultimosMovimientos = movimientos.slice(0, 10);
    
    return `
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: #f9fafb; border-bottom: 2px solid #e5e7eb;">
                        <th style="padding: 12px; text-align: left; color: #374151; font-weight: 600;">Fecha</th>
                        <th style="padding: 12px; text-align: left; color: #374151; font-weight: 600;">Tipo</th>
                        <th style="padding: 12px; text-align: left; color: #374151; font-weight: 600;">Cantidad</th>
                        <th style="padding: 12px; text-align: left; color: #374151; font-weight: 600;">Responsable</th>
                        <th style="padding: 12px; text-align: left; color: #374151; font-weight: 600;">Máquina</th>
                        <th style="padding: 12px; text-align: left; color: #374151; font-weight: 600;">PNC</th>
                        <th style="padding: 12px; text-align: left; color: #374151; font-weight: 600;">Estado</th>
                    </tr>
                </thead>
                <tbody>
                    ${ultimosMovimientos.map(mov => `
                        <tr style="border-bottom: 1px solid #e5e7eb; transition: background 0.2s;">
                            <td style="padding: 12px;">
                                <div>
                                    <div style="font-weight: 500; color: #111827;">${formatDateShort(mov.fecha_inicio)}</div>
                                    <div style="font-size: 0.875rem; color: #6b7280;">${formatTime(mov.fecha_inicio)}</div>
                                </div>
                            </td>
                            <td style="padding: 12px;">
                                <span style="
                                    display: inline-block;
                                    padding: 4px 12px;
                                    border-radius: 20px;
                                    font-size: 0.875rem;
                                    font-weight: 500;
                                    ${getTipoEstilo(mov.transaction_type)}
                                ">
                                    ${getTipoTexto(mov.transaction_type)}
                                </span>
                            </td>
                            <td style="padding: 12px;">
                                <div>
                                    <div style="font-weight: 600; color: #111827;">${formatNumber(mov.cantidad_real || 0)}</div>
                                    <div style="font-size: 0.875rem; color: #6b7280;">unid.</div>
                                </div>
                            </td>
                            <td style="padding: 12px; color: #374151;">
                                ${mov.responsable || '-'}
                            </td>
                            <td style="padding: 12px;">
                                <span style="
                                    display: inline-block;
                                    padding: 4px 10px;
                                    background: #e0e7ff;
                                    color: #3730a3;
                                    border-radius: 6px;
                                    font-size: 0.875rem;
                                    font-family: monospace;
                                ">
                                    ${mov.maquina || '-'}
                                </span>
                            </td>
                            <td style="padding: 12px;">
                                <span style="
                                    font-weight: 600;
                                    color: ${mov.PNC && mov.PNC > 0 ? '#ef4444' : '#10b981'};
                                ">
                                    ${mov.PNC ? formatNumber(mov.PNC) : '0'}
                                </span>
                            </td>
                            <td style="padding: 12px;">
                                <span style="
                                    display: inline-block;
                                    padding: 4px 12px;
                                    border-radius: 20px;
                                    font-size: 0.875rem;
                                    font-weight: 500;
                                    ${getEstadoMovimientoEstilo(mov.estado)}
                                ">
                                    ${mov.estado || 'COMPLETADO'}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        
        ${movimientos.length > 10 ? `
        <div style="margin-top: 16px; text-align: center;">
            <button onclick="verTodosMovimientos('${codigoSistema}')" style="
                padding: 8px 16px;
                background: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                color: #374151;
                font-weight: 500;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                transition: all 0.2s;
            ">
                <i class="fas fa-list"></i>
                Ver todos los movimientos (${movimientos.length})
            </button>
        </div>
        ` : ''}
    `;
}

function getEstadoStockModal(stockActual, stockMinimo) {
    if (stockActual <= 0) {
        return {
            text: 'AGOTADO',
            color: '#ef4444',
            bgColor: '#ef4444'
        };
    } else if (stockActual <= stockMinimo) {
        return {
            text: 'BAJO STOCK',
            color: '#f59e0b',
            bgColor: '#f59e0b'
        };
    } else if (stockActual <= stockMinimo * 1.5) {
        return {
            text: 'NORMAL',
            color: '#3b82f6',
            bgColor: '#3b82f6'
        };
    } else {
        return {
            text: 'ÓPTIMO',
            color: '#10b981',
            bgColor: '#10b981'
        };
    }
}

function getTipoEstilo(tipo) {
    const tipoUpper = (tipo || '').toUpperCase();
    switch(tipoUpper) {
        case 'INY':
        case 'INYECCIÓN':
        case 'INYECCION':
            return 'background: #dbeafe; color: #1e40af;';
        case 'AJT':
        case 'AJUSTE':
            return 'background: #fef3c7; color: #92400e;';
        case 'TRS':
        case 'TRANSFERENCIA':
            return 'background: #f3e8ff; color: #5b21b6;';
        case 'SAL':
        case 'SALIDA':
            return 'background: #fee2e2; color: #991b1b;';
        case 'ENT':
        case 'ENTRADA':
            return 'background: #dcfce7; color: #166534;';
        default:
            return 'background: #f3f4f6; color: #374151;';
    }
}

function getTipoTexto(tipo) {
    const tipoUpper = (tipo || '').toUpperCase();
    const textos = {
        'INY': 'Inyección',
        'INYECCIÓN': 'Inyección',
        'INYECCION': 'Inyección',
        'AJT': 'Ajuste',
        'AJUSTE': 'Ajuste',
        'TRS': 'Transferencia',
        'TRANSFERENCIA': 'Transferencia',
        'SAL': 'Salida',
        'SALIDA': 'Salida',
        'ENT': 'Entrada',
        'ENTRADA': 'Entrada',
        'PRO': 'Producción',
        'PRODUCCIÓN': 'Producción'
    };
    return textos[tipoUpper] || tipo || 'Movimiento';
}

function getEstadoMovimientoEstilo(estado) {
    const estadoUpper = (estado || '').toUpperCase();
    switch(estadoUpper) {
        case 'COMPLETADO':
            return 'background: #dcfce7; color: #166534;';
        case 'EN_PROCESO':
        case 'EN PROGRESO':
            return 'background: #fef3c7; color: #92400e;';
        case 'PENDIENTE':
            return 'background: #e0e7ff; color: #3730a3;';
        case 'CANCELADO':
            return 'background: #f3f4f6; color: #6b7280;';
        case 'ERROR':
            return 'background: #fee2e2; color: #991b1b;';
        default:
            return 'background: #f3f4f6; color: #374151;';
    }
}

function formatCurrency(num) {
    return new Intl.NumberFormat('es-ES', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(num);
}

function formatDateShort(dateString) {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('es-ES', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        }).format(date);
    } catch (e) {
        return dateString.split('T')[0] || dateString;
    }
}

function formatTime(dateString) {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('es-ES', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        }).format(date);
    } catch (e) {
        return dateString.includes('T') ? dateString.split('T')[1].substring(0, 8) : '-';
    }
}

// Función placeholder para ver todos los movimientos
function verTodosMovimientos(codigoProducto) {
    console.log('Ver todos los movimientos para:', codigoProducto);
    mostrarNotificacion(`Abriendo reporte completo de movimientos para ${codigoProducto}`, 'info');
    // Aquí podrías abrir otro modal o redirigir a una página de movimientos
}

// Función placeholder para editar producto
function editarProducto(codigo) {
    console.log('Editando producto:', codigo);
    mostrarNotificacion('Funcionalidad de edición en desarrollo', 'info');
    // Aquí implementarías la lógica para editar el producto
}

// ===== GESTIÓN DE FORMULARIOS =====

function configurarFormularios() {
    console.log('Configurando formularios...');
    
    // Configurar fechas por defecto
    const hoy = new Date().toISOString().split('T')[0];
    document.querySelectorAll('input[type="date"]').forEach(input => {
        if (!input.value) {
            input.value = hoy;
        }
    });
    
    // Formulario de Inyección
    const formInyeccion = document.getElementById('form-inyeccion');
    if (formInyeccion) {
        formInyeccion.addEventListener('submit', function(e) {
            e.preventDefault();
            registrarInyeccion();
        });
        
        // Evento para ficha técnica
        const productoSelect = document.getElementById('codigo-producto-inyeccion');
        if (productoSelect) {
            productoSelect.addEventListener('change', function() {
                if (this.value) {
                    actualizarFichaProducto(this.value);
                }
            });
        }
    }

    // Evento para actualizar cavidades según máquina
        const maquinaSelect = document.getElementById('maquina-inyeccion');
        if (maquinaSelect) {
            maquinaSelect.addEventListener('change', function() {
                if (this.value) {
                    actualizarCavidadesPorMaquina(this.value);
                }
            });
        }
        // Configurar calculadora automática
        configurarCalculadoraInyeccion();
        actualizarCalculoProduccion(); // Calcular inicial
    }

    // Formulario de Pulido
    const formPulido = document.getElementById('form-pulido');
    if (formPulido) {
        formPulido.addEventListener('submit', function(e) {
            e.preventDefault();
            registrarPulido();
        });
    }
    
    // Formulario de Ensamble
    const formEnsamble = document.getElementById('form-ensamble');
    if (formEnsamble) {
        formEnsamble.addEventListener('submit', function(e) {
            e.preventDefault();
            registrarEnsamble();
        });
        
        // Evento para receta
        const productoSelect = document.getElementById('codigo-producto-ensamble');
        if (productoSelect) {
            productoSelect.addEventListener('change', function() {
                if (this.value) {
                    cargarFichaEnsamble(this.value);
                }
            });
        }
    }
    
    // Formulario de Facturación
    const formFacturacion = document.getElementById('form-facturacion');
    if (formFacturacion) {
        formFacturacion.addEventListener('submit', function(e) {
            e.preventDefault();
            registrarFacturacion();
        });
        
        // Eventos para calcular total
        const cantidadInput = document.getElementById('cantidad-facturacion');
        const precioInput = document.getElementById('precio-unitario');
        
        if (cantidadInput) {
            cantidadInput.addEventListener('input', calcularTotalFacturacion);
        }
        if (precioInput) {
            precioInput.addEventListener('input', calcularTotalFacturacion);
        }
        
        // Evento para precio del producto
        const productoSelect = document.getElementById('codigo-producto-facturacion');
        if (productoSelect) {
            productoSelect.addEventListener('change', function() {
                if (this.value) {
                    actualizarPrecioProducto(this.value);
                }
            });
        }
    }
    
    console.log('Formularios configurados correctamente');


async function actualizarFichaProducto(codigo) {
    if (!codigo) {
        const fichaTecnica = document.getElementById('ficha-tecnica');
        if (fichaTecnica) {
            fichaTecnica.style.display = 'none';
        }
        return;
    }
    
    try {
        const response = await fetch(`/api/obtener_ficha/${codigo}`);
        const data = await response.json();
        
        const fichaContent = document.getElementById('ficha-content');
        const fichaTecnica = document.getElementById('ficha-tecnica');
        
        if (fichaContent && fichaTecnica) {
            if (data.buje_origen || data.qty_unitaria) {
                fichaContent.innerHTML = `
                    <div class="ficha-info">
                        <div><strong>Producto:</strong> ${data.codigo_sistema || codigo}</div>
                        ${data.buje_origen ? `<div><strong>Buje Origen:</strong> ${data.buje_origen}</div>` : ''}
                        ${data.qty_unitaria ? `<div><strong>Cantidad por Unidad:</strong> ${data.qty_unitaria}</div>` : ''}
                    </div>
                `;
                fichaTecnica.style.display = 'block';
            } else {
                fichaTecnica.style.display = 'none';
            }
        }
        
    } catch (error) {
        console.error('Error cargando ficha:', error);
        const fichaTecnica = document.getElementById('ficha-tecnica');
        if (fichaTecnica) {
            fichaTecnica.style.display = 'none';
        }
    }
}

async function cargarFichaEnsamble(codigo) {
    if (!codigo) {
        const infoReceta = document.getElementById('info-receta');
        if (infoReceta) {
            infoReceta.style.display = 'none';
        }
        return;
    }
    
    try {
        const response = await fetch(`/api/obtener_ficha/${codigo}`);
        const data = await response.json();
        
        const recetaContent = document.getElementById('receta-content');
        const infoReceta = document.getElementById('info-receta');
        
        if (recetaContent && infoReceta) {
            if (data.buje_origen || data.qty_unitaria) {
                recetaContent.innerHTML = `
                    <div class="receta-info">
                        <div><strong>Producto Final:</strong> ${data.codigo_sistema || codigo}</div>
                        ${data.buje_origen ? `<div><strong>Buje Origen:</strong> ${data.buje_origen}</div>` : ''}
                        ${data.qty_unitaria ? `<div><strong>Cantidad por Unidad:</strong> ${data.qty_unitaria}</div>` : ''}
                </div>
                `;
                infoReceta.style.display = 'block';
            } else {
                infoReceta.style.display = 'none';
            }
        }
        
    } catch (error) {
        console.error('Error cargando receta:', error);
        const infoReceta = document.getElementById('info-receta');
        if (infoReceta) {
            infoReceta.style.display = 'none';
        }
    }
}

async function actualizarPrecioProducto(codigo) {
    if (!codigo) return;
    
    try {
        const response = await fetch(`/api/productos/detalle/${codigo}`);
        const data = await response.json();
        
        const precioInput = document.getElementById('precio-unitario');
        if (precioInput && data.status === 'success' && data.producto.precio) {
            precioInput.value = data.producto.precio;
            calcularTotalFacturacion();
        }
    } catch (error) {
        console.error('Error cargando precio:', error);
    }
}

function calcularTotalFacturacion() {
    const cantidad = parseInt(document.getElementById('cantidad-facturacion')?.value) || 0;
    const precio = parseFloat(document.getElementById('precio-unitario')?.value) || 0;
    const total = cantidad * precio;
    
    const totalInput = document.getElementById('total-venta');
    if (totalInput) {
        totalInput.value = total.toFixed(2);
    }
}

// ===== REGISTROS =====

async function registrarInyeccion() {
    try {
        const { piezasBuenas, cavidades } = actualizarCalculoProduccion();
        
        const formData = {
            fecha_inicio: document.getElementById('fecha-inyeccion')?.value,
            responsable: document.getElementById('responsable-inyeccion')?.value,
            codigo_producto: document.getElementById('codigo-producto-inyeccion')?.value,
            maquina: document.getElementById('maquina-inyeccion')?.value,
            cantidad_real: parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0,
            no_cavidades: cavidades, // ← NUEVO: Agregar cavidades
            pnc: parseInt(document.getElementById('pnc-inyeccion')?.value) || 0,
            criterio_pnc: document.getElementById('criterio-pnc-inyeccion')?.value,
            observaciones: document.getElementById('observaciones-inyeccion')?.value
        };
        
        console.log('Registrando inyección con cavidades:', formData);
        
        // Validaciones mejoradas
        if (!formData.fecha_inicio || !formData.responsable || !formData.codigo_producto || 
            !formData.cantidad_real || !formData.no_cavidades) {
            mostrarNotificacion('Complete todos los campos obligatorios', 'warning');
            return;
        }
        
        if (formData.cantidad_real <= 0) {
            mostrarNotificacion('La cantidad de disparos debe ser mayor a 0', 'error');
            return;
        }
        
        if (formData.no_cavidades <= 0) {
            mostrarNotificacion('El número de cavidades debe ser mayor a 0', 'error');
            return;
        }
        
        const pnc = formData.pnc || 0;
        const piezasTotales = formData.cantidad_real * formData.no_cavidades;
        
        if (pnc > piezasTotales) {
            mostrarNotificacion(`El PNC no puede ser mayor que la producción total (${piezasTotales} piezas)`, 'error');
            return;
        }
        
        // Mostrar resumen antes de enviar
        const confirmacion = `¿Registrar inyección?
• Producto: ${formData.codigo_producto}
• Disparos: ${formData.cantidad_real}
• Cavidades: ${formData.no_cavidades}
• Producción total: ${piezasTotales} piezas
• PNC: ${pnc} piezas
• Piezas buenas: ${piezasBuenas} piezas

¿Desea continuar?`;
        
        if (!confirm(confirmacion)) {
            return;
        }
        
        mostrarLoading(true);
        
        const response = await fetch('/api/inyeccion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            mostrarNotificacion(`✅ Inyección registrada exitosamente: ${piezasBuenas} piezas buenas`, 'success');
            
            // Limpiar formulario
            document.getElementById('form-inyeccion')?.reset();
            
            // Restablecer valores
            const hoy = new Date().toISOString().split('T')[0];
            document.getElementById('fecha-inyeccion').value = hoy;
            document.getElementById('cavidades-inyeccion').value = '4'; // Valor por defecto
            actualizarCalculoProduccion(); // Actualizar cálculo
            
            // Ocultar ficha técnica
            const fichaTecnica = document.getElementById('ficha-tecnica');
            if (fichaTecnica) {
                fichaTecnica.style.display = 'none';
            }
        } else {
            throw new Error(result.message || 'Error registrando inyección');
        }
        
    } catch (error) {
        console.error('Error registrando inyección:', error);
        mostrarNotificacion('Error: ' + error.message, 'error');
    } finally {
        mostrarLoading(false);
    }
}
async function registrarPulido() {
    try {
        const formData = {
            fecha_inicio: document.getElementById('fecha-pulido')?.value,
            responsable: document.getElementById('responsable-pulido')?.value,
            codigo_producto: document.getElementById('codigo-producto-pulido')?.value,
            cantidad_recibida: parseInt(document.getElementById('cantidad-recibida-pulido')?.value) || 0,
            cantidad_real: parseInt(document.getElementById('cantidad-pulido')?.value) || 0,
            pnc: parseInt(document.getElementById('pnc-pulido')?.value) || 0,
            criterio_pnc: document.getElementById('criterio-pnc-pulido')?.value,
            observaciones: document.getElementById('observaciones-pulido')?.value
        };
        
        console.log('Registrando pulido:', formData);
        
        // Validaciones
        if (!formData.fecha_inicio || !formData.responsable || !formData.codigo_producto || 
            !formData.cantidad_recibida || !formData.cantidad_real) {
            mostrarNotificacion('Complete todos los campos obligatorios', 'warning');
            return;
        }
        
        if (formData.cantidad_recibida <= 0) {
            mostrarNotificacion('La cantidad recibida debe ser mayor a 0', 'error');
            return;
        }
        
        if (formData.pnc > formData.cantidad_recibida) {
            mostrarNotificacion('El PNC no puede ser mayor que la cantidad recibida', 'error');
            return;
        }
        
        mostrarLoading(true);
        
        const response = await fetch('/api/pulido', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            mostrarNotificacion('Pulido registrado exitosamente', 'success');
            document.getElementById('form-pulido')?.reset();
            
            // Restablecer fecha
            const hoy = new Date().toISOString().split('T')[0];
            document.getElementById('fecha-pulido').value = hoy;
        } else {
            throw new Error(result.message || 'Error registrando pulido');
        }
        
    } catch (error) {
        console.error('Error registrando pulido:', error);
        mostrarNotificacion('Error: ' + error.message, 'error');
    } finally {
        mostrarLoading(false);
    }
}

async function registrarEnsamble() {
    try {
        const formData = {
            fecha_inicio: document.getElementById('fecha-ensamble')?.value,
            responsable: document.getElementById('responsable-ensamble')?.value,
            codigo_producto: document.getElementById('codigo-producto-ensamble')?.value,
            cantidad_real: parseInt(document.getElementById('cantidad-ensamble')?.value) || 0,
            pnc: parseInt(document.getElementById('pnc-ensamble')?.value) || 0,
            criterio_pnc: document.getElementById('criterio-pnc-ensamble')?.value,
            almacen_origen: document.getElementById('almacen-origen')?.value,
            almacen_destino: document.getElementById('almacen-destino')?.value,
            observaciones: document.getElementById('observaciones-ensamble')?.value
        };
        
        console.log('Registrando ensamble:', formData);
        
        // Validaciones
        if (!formData.fecha_inicio || !formData.responsable || !formData.codigo_producto || 
            !formData.cantidad_real || !formData.almacen_origen || !formData.almacen_destino) {
            mostrarNotificacion('Complete todos los campos obligatorios', 'warning');
            return;
        }
        
        if (formData.cantidad_real <= 0) {
            mostrarNotificacion('La cantidad debe ser mayor a 0', 'error');
            return;
        }
        
        if (formData.pnc > formData.cantidad_real) {
            mostrarNotificacion('El PNC no puede ser mayor que la cantidad real', 'error');
            return;
        }
        
        mostrarLoading(true);
        
        const response = await fetch('/api/ensamble', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            mostrarNotificacion('Ensamble registrado exitosamente', 'success');
            document.getElementById('form-ensamble')?.reset();
            
            // Restablecer fecha
            const hoy = new Date().toISOString().split('T')[0];
            document.getElementById('fecha-ensamble').value = hoy;
            
            // Ocultar info receta
            const infoReceta = document.getElementById('info-receta');
            if (infoReceta) {
                infoReceta.style.display = 'none';
            }
        } else {
            throw new Error(result.message || 'Error registrando ensamble');
        }
        
    } catch (error) {
        console.error('Error registrando ensamble:', error);
        mostrarNotificacion('Error: ' + error.message, 'error');
    } finally {
        mostrarLoading(false);
    }
}

async function registrarFacturacion() {
    try {
        const formData = {
            fecha_inicio: document.getElementById('fecha-facturacion')?.value,
            cliente: document.getElementById('cliente-facturacion')?.value,
            codigo_producto: document.getElementById('codigo-producto-facturacion')?.value,
            cantidad_vendida: parseInt(document.getElementById('cantidad-facturacion')?.value) || 0,
            total_venta: parseFloat(document.getElementById('total-venta')?.value) || 0,
            observaciones: document.getElementById('observaciones-facturacion')?.value
        };
        
        console.log('Registrando facturación:', formData);
        
        // Validaciones
        if (!formData.fecha_inicio || !formData.cliente || !formData.codigo_producto || 
            !formData.cantidad_vendida || !formData.total_venta) {
            mostrarNotificacion('Complete todos los campos obligatorios', 'warning');
            return;
        }
        
        if (formData.cantidad_vendida <= 0) {
            mostrarNotificacion('La cantidad debe ser mayor a 0', 'error');
            return;
        }
        
        if (formData.total_venta <= 0) {
            mostrarNotificacion('El total debe ser mayor a 0', 'error');
            return;
        }
        
        mostrarLoading(true);
        
        const response = await fetch('/api/facturacion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            mostrarNotificacion('Facturación registrada exitosamente', 'success');
            document.getElementById('form-facturacion')?.reset();
            
            // Restablecer fecha
            const hoy = new Date().toISOString().split('T')[0];
            document.getElementById('fecha-facturacion').value = hoy;
            
            // Restablecer total
            document.getElementById('total-venta').value = '0.00';
        } else {
            throw new Error(result.message || 'Error registrando facturación');
        }
        
    } catch (error) {
        console.error('Error registrando facturación:', error);
        mostrarNotificacion('Error: ' + error.message, 'error');
    } finally {
        mostrarLoading(false);
    }
}

// ===== DATOS ESPECÍFICOS DE PÁGINAS =====

async function cargarDatosInyeccion() {
    console.log('Cargando datos de inyección...');
    mostrarNotificacion('Módulo de inyección cargado', 'info');
    
    // ========== AUTOCOMPLETE PARA PRODUCTOS ==========
    const productoInput = document.getElementById('codigo-producto-inyeccion');
    const sugerenciasContainer = document.getElementById('sugerencias-productos');

    if (productoInput) {
        productoInput.addEventListener('input', async function(e) {
            const valor = e.target.value.trim().toUpperCase();
            
            console.log('🔍 Buscando productos:', valor);
            
            if (valor.length < 1) {
                if (sugerenciasContainer) sugerenciasContainer.style.display = 'none';
                return;
            }
            
            try {
                const response = await fetch('/api/productos');
                const productos = await response.json();
                
                console.log('📦 Productos disponibles:', productos.length);
                
                // Filtrar: busca que CONTENGA el valor (no que empiece)
                const filtrados = productos.filter(p => 
                    p.codigo.toUpperCase().includes(valor) || 
                    p.nombre.toUpperCase().includes(valor)
                );
                
                console.log('✅ Productos filtrados:', filtrados.length);
                
                if (!sugerenciasContainer) {
                    console.warn('⚠️ No existe elemento sugerencias-productos en HTML');
                    return;
                }
                
                if (filtrados.length === 0) {
                    sugerenciasContainer.innerHTML = '<div class="sugerencia-item" style="color:red; padding:10px; cursor:default;">❌ Producto no encontrado</div>';
                    sugerenciasContainer.style.display = 'block';
                    return;
                }
                
                sugerenciasContainer.innerHTML = filtrados.map(p => 
                    `<div class="sugerencia-item" onclick="seleccionarProductoInyeccion('${p.codigo}', '${p.nombre}')" style="padding:10px; cursor:pointer; border-bottom:1px solid #eee; background:white;" onmouseover="this.style.background='#f0f0f0'" onmouseout="this.style.background='white'">
                        <strong>${p.codigo}</strong> - ${p.nombre}
                    </div>`
                ).join('');
                sugerenciasContainer.style.display = 'block';
            } catch (error) {
                console.error('❌ Error cargando productos:', error);
                if (sugerenciasContainer) {
                    sugerenciasContainer.innerHTML = '<div class="sugerencia-item" style="color:red; padding:10px;">Error cargando productos</div>';
                    sugerenciasContainer.style.display = 'block';
                }
            }
        });
        
        // Cerrar sugerencias al hacer clic fuera
        document.addEventListener('click', function(e) {
            if (sugerenciasContainer && e.target !== productoInput && !sugerenciasContainer.contains(e.target)) {
                sugerenciasContainer.style.display = 'none';
            }
        });
        
        // Cerrar sugerencias con ESC
        productoInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && sugerenciasContainer) {
                sugerenciasContainer.style.display = 'none';
            }
        });
    }
}

// Función para seleccionar un producto del autocomplete
function seleccionarProductoInyeccion(codigo, nombre) {
    const input = document.getElementById('codigo-producto-inyeccion');
    if (input) input.value = codigo;
    
    const sugerencias = document.getElementById('sugerencias-productos');
    if (sugerencias) sugerencias.style.display = 'none';
    
    console.log(`✅ Producto seleccionado: ${codigo} - ${nombre}`);
    
    // Actualizar ficha técnica si existe
    actualizarFichaProducto(codigo);
}

async function cargarDatosPulido() {
    console.log('Cargando datos de pulido...');
    mostrarNotificacion('Módulo de pulido cargado', 'info');
}

async function cargarDatosEnsamble() {
    console.log('Cargando datos de ensamble...');
    mostrarNotificacion('Módulo de ensamble cargado', 'info');
}

async function cargarDatosFacturacion() {
    console.log('Cargando datos de facturación...');
    mostrarNotificacion('Módulo de facturación cargado', 'info');
}

async function cargarDatosReportes() {
    console.log('Cargando datos de reportes...');
    mostrarNotificacion('Módulo de reportes cargado', 'info');
    
    // Configurar eventos de reportes
    document.querySelectorAll('[id^="btn-reporte-"]').forEach(btn => {
        btn.addEventListener('click', function() {
            const tipo = this.id.replace('btn-reporte-', '');
            generarReporte(tipo);
        });
    });
    
    const btnGenerarTodos = document.getElementById('btn-generar-todos-reportes');
    if (btnGenerarTodos) {
        btnGenerarTodos.addEventListener('click', generarReporteCompleto);
    }
}



// ===== FUNCIONES DE REPORTES =====

function generarReporte(tipo) {
    const periodo = document.getElementById('periodo-reporte')?.value || 'mes';
    const formato = document.getElementById('formato-reporte')?.value || 'excel';
    const detalle = document.getElementById('detalle-reporte')?.value || 'resumen';
    
    console.log(`Generando reporte de ${tipo}: periodo=${periodo}, formato=${formato}, detalle=${detalle}`);
    mostrarNotificacion(`Generando reporte de ${tipo} en formato ${formato.toUpperCase()}...`, 'info');
    
    // Simular generación de reporte
    setTimeout(() => {
        mostrarNotificacion(`Reporte de ${tipo} generado exitosamente`, 'success');
    }, 2000);
}

function generarReporteCompleto() {
    console.log('Generando reporte completo...');
    mostrarNotificacion('Generando todos los reportes...', 'info');
    
    setTimeout(() => {
        mostrarNotificacion('Todos los reportes generados exitosamente', 'success');
    }, 3000);
}

// ===== FUNCIONES DE MODALES =====

function mostrarModalNuevoProducto() {
    console.log('Mostrando modal de nuevo producto...');
    const modal = document.getElementById('modal-nuevo-producto');
    if (modal) {
        modal.style.display = 'flex';
        
        // Configurar eventos del modal
        const btnCerrar = document.getElementById('btn-cerrar-modal-producto');
        const btnCancelar = document.getElementById('btn-cancelar-modal-producto');
        const btnGuardar = document.getElementById('btn-guardar-producto');
        
        if (btnCerrar) {
            btnCerrar.addEventListener('click', function() {
                cerrarModal('modal-nuevo-producto');
            });
        }
        
        if (btnCancelar) {
            btnCancelar.addEventListener('click', function() {
                cerrarModal('modal-nuevo-producto');
            });
        }
        
        if (btnGuardar) {
            btnGuardar.addEventListener('click', guardarNuevoProducto);
        }
    }
}

function cerrarModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

function guardarNuevoProducto() {
    console.log('Guardando nuevo producto...');
    mostrarNotificacion('Funcionalidad en desarrollo', 'info');
    cerrarModal('modal-nuevo-producto');
}

function exportarInventario() {
    console.log('Exportando inventario...');
    mostrarNotificacion('Exportando inventario en formato Excel...', 'info');
    
    setTimeout(() => {
        mostrarNotificacion('Inventario exportado exitosamente', 'success');
    }, 2000);
}

function exportarMovimientos(codigo) {
    mostrarNotificacion(`Exportando movimientos de ${codigo}...`, 'info');
    
    setTimeout(() => {
        mostrarNotificacion('Movimientos exportados exitosamente', 'success');
    }, 1500);
}

// Agrega esta función al final de tu app.js
function cerrarDetalle() {
    console.log("🔒 Cerrando detalles...");
    const modal = document.getElementById('modal-detalle');
    if (modal) {
        modal.style.display = 'none';
    }
    const overlay = document.querySelector('.modal-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
    document.body.style.overflow = 'auto';
}

// También puedes agregar la función para abrir detalles
function abrirDetalle(titulo, contenido) {
    console.log("🔓 Abriendo detalles: " + titulo);
    const modal = document.getElementById('modal-detalle');
    const modalTitle = document.getElementById('modal-detalle-title');
    const modalBody = document.getElementById('modal-detalle-body');
    
    if (modal && modalTitle && modalBody) {
        modalTitle.textContent = titulo;
        modalBody.innerHTML = contenido;
        modal.style.display = 'block';
        
        const overlay = document.querySelector('.modal-overlay');
        if (overlay) {
            overlay.style.display = 'block';
        }
        document.body.style.overflow = 'hidden';
    }
}

// ========== FUNCIÓN PARA ACTUALIZAR SELECT DE MÁQUINAS ==========

function actualizarSelectMaquinas(maquinas) {
    console.log('Actualizando selects de máquina con:', maquinas);
    
    const selects = document.querySelectorAll('select[id*="maquina"]');
    console.log(`Encontrados ${selects.length} selects de máquina`);
    
    selects.forEach(select => {
        const currentValue = select.value;
        
        // Limpiar
        select.innerHTML = '<option value="">-- Selecciona máquina --</option>';
        
        // Agregar opciones
        if (maquinas && Array.isArray(maquinas)) {
            maquinas.forEach(maquina => {
                const option = document.createElement('option');
                option.value = maquina;
                option.textContent = maquina;
                select.appendChild(option);
            });
        }
        
        // Restaurar valor si existía
        if (currentValue && maquinas.includes(currentValue)) {
            select.value = currentValue;
        }
        
        console.log(`✅ Select ${select.id} actualizado con ${maquinas.length} máquinas`);
    });
}


// ===== INICIALIZACIÓN DE LA APLICACIÓN =====

function inicializarAplicacion() {
    console.log('Aplicación inicializando...');
    
    // Configurar menú de navegación
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const pagina = this.dataset.page;
            if (pagina) {
                cargarPagina(pagina);
            }
        });
    });
    
    // Configurar formularios
    configurarFormularios();
    
    // Cargar datos iniciales
    cargarDatosIniciales();
    
    // Cargar página inicial
    cargarPagina('dashboard');
    
    console.log('Aplicación inicializada correctamente');
}


window.initDashboard = function() {
    if (window.inicializarDashboard) {
        window.inicializarDashboard();
    }
};


// ===== INICIALIZAR CUANDO EL DOM ESTÉ LISTO =====

document.addEventListener('DOMContentLoaded', function() {
    // Mostrar fecha actual en el sidebar
    const fechaElement = document.getElementById('fecha-actual');
    if (fechaElement) {
        const hoy = new Date();
        fechaElement.textContent = hoy.toLocaleDateString('es-ES', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }
    
    // Inicializar aplicación
    inicializarAplicacion();
});

// ===== EXPORTAR FUNCIONES GLOBALES =====

window.cargarPagina = cargarPagina;
window.buscarProductos = buscarProductos;
window.filtrarProductos = filtrarProductos;
window.verDetalleProducto = verDetalleProducto;
window.verTodosMovimientos = verTodosMovimientos;
window.editarProducto = editarProducto;
window.cerrarDetalle = cerrarDetalle;
window.actualizarFichaProducto = actualizarFichaProducto;
window.cargarFichaEnsamble = cargarFichaEnsamble;
window.actualizarPrecioProducto = actualizarPrecioProducto;
window.calcularTotal = calcularTotalFacturacion;
window.generarReporte = generarReporte;
window.generarReporteCompleto = generarReporteCompleto;
window.mostrarModalNuevoProducto = mostrarModalNuevoProducto;
window.cerrarModal = cerrarModal;
window.guardarNuevoProducto = guardarNuevoProducto;
window.exportarInventario = exportarInventario;
window.exportarMovimientos = exportarMovimientos;