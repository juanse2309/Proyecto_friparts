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
    maquinas: [],
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



// ===== GESTIÓN DE NAVEGACIÓN =====

function getPageName(pageId) {
    const nombres = {
        'dashboard': 'Dashboard Analítico',
        'inventario': 'Productos y Existencias',
        'inyeccion': 'Registro de Inyección',
        'pulido': 'Registro de Pulido',
        'ensamble': 'Registro de Ensamble',
        'pnc': 'Productos No Conformes',
        'facturacion': 'Facturación',
        'reportes': 'Reportes',
        'mezcla': 'Control de Mezcla',
        'historial': 'Historial Global'
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
            if (typeof inicializarDashboard === 'function') inicializarDashboard();
            break;
        case 'inventario':
            cargarProductos();
            configurarEventosInventario();
            break;
            case 'inyeccion':
        if (typeof initInyeccion === 'function') {
            initInyeccion();
        } else if (typeof cargarDatosInyeccion === 'function') {
            cargarDatosInyeccion();
        }
        break;

        case 'pulido':
        if (typeof initPulido === 'function') {
            initPulido();
        } else if (typeof cargarDatosPulido === 'function') {
            cargarDatosPulido();
        }
        break;

        case 'ensamble':
        if (typeof initEnsamble === 'function') {
            initEnsamble();
        } else if (typeof cargarDatosEnsamble === 'function') {
            cargarDatosEnsamble();
        }
        break;

        case 'pnc':
        if (typeof initPNC === 'function') {
            initPNC();
        } else if (typeof cargarDatosPNC === 'function') {
            cargarDatosPNC();
        }
        break;

        case 'facturacion':
            if (typeof cargarDatosFacturacion === 'function') cargarDatosFacturacion();
            break;
        case 'reportes':
            if (typeof cargarDatosReportes === 'function') cargarDatosReportes();
            break;
        case 'mezcla':
            // La página de mezcla ya está inicializada por initMezcla()
            break;
        case 'historial':
        // NO cargar automáticamente, solo cuando el usuario haga clic en "Filtrar"
        console.log('📜 Historial listo. Haz clic en Filtrar para cargar datos.');
        break;
        
        }
    
    mostrarNotificacion(`Página ${getPageName(pagina)} cargada`, 'info');
}

// ===== CARGA DE DATOS INICIALES =====

async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetch en ${url}:`, error);
        mostrarNotificacion(`Error cargando datos de ${url}`, 'error');
        return null;
    }
}

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

        // Cargar máquinas
        const maquinas = await fetchData('/api/obtener_maquinas');
        if (maquinas) {
            window.AppState.maquinas = maquinas;
            actualizarSelectMaquinas(maquinas);
            console.log('✅ Máquinas cargadas:', maquinas.length);
        }

        // Cargar productos
        const productos = await fetchData('/api/obtener_productos');
        if (productos && Array.isArray(productos)) {
            window.AppState.productos = productos;
            actualizarSelectsProductos(productos);
            actualizarProductosList(productos);
            console.log(`✅ Productos cargados: ${productos.length}`);
        } else {
            console.warn('⚠️ No se obtuvieron productos válidos');
        }

        // Cargar criterios PNC para cada formulario
        await Promise.all([
            cargarCriteriosPNC('inyeccion', 'criterio-pnc-inyeccion'),
            cargarCriteriosPNC('pulido', 'criterio-pnc-pulido'),
            cargarCriteriosPNC('ensamble', 'criterio-pnc-ensamble')
        ]);
        
        mostrarLoading(false);
        console.log('✅ Datos iniciales cargados correctamente');
        
    } catch (error) {
        console.error('❌ Error cargando datos iniciales:', error);
        mostrarNotificacion('Error cargando datos iniciales', 'error');
        mostrarLoading(false);
    }
}

function mostrarLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Sistema de notificaciones visuales tipo toast
 */
function mostrarNotificacion(mensaje, tipo = 'info', duracion = 4000) {
    console.log(`Notificación [${tipo}]: ${mensaje}`);
    
    // Crear contenedor de notificaciones si no existe
    let container = document.getElementById('notifications-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notifications-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 400px;
        `;
        document.body.appendChild(container);
    }
    
    // Crear notificación
    const notification = document.createElement('div');
    notification.className = `notification notification-${tipo}`;
    
    // Iconos según tipo
    const iconos = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    };
    
    const colores = {
        'success': 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        'error': 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
        'warning': 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        'info': 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)'
    };
    
    notification.style.cssText = `
        background: ${colores[tipo]};
        color: white;
        padding: 16px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        gap: 12px;
        animation: slideIn 0.3s ease;
        min-width: 300px;
        max-width: 400px;
        font-size: 14px;
        font-weight: 500;
    `;
    
    notification.innerHTML = `
        <i class="fas ${iconos[tipo]}" style="font-size: 20px;"></i>
        <span style="flex: 1;">${mensaje}</span>
        <button onclick="this.parentElement.remove()" style="background: none; border: none; color: white; cursor: pointer; font-size: 18px; opacity: 0.8; padding: 0; margin-left: 8px;">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    container.appendChild(notification);
    
    // Auto-cerrar después de la duración especificada
    if (duracion > 0) {
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, duracion);
    }
}


function formatNumber(num) {
    return new Intl.NumberFormat('es-ES').format(num);
}

function getEstadoStock(total, minimo) {
    if (total <= 0) return 'agotado';
    if (total < minimo) return 'bajo';
    return 'ok';
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
                option.value = String(producto).trim();
                option.textContent = String(producto).trim();
                select.appendChild(option);
            });
        }
        
        if (currentValue) {
            select.value = currentValue;
        }
    });
}

function actualizarProductosList(productos) {
    const datalist = document.getElementById('productos-list');
    if (!datalist) return;
    
    datalist.innerHTML = '';
    
    if (!productos || productos.length === 0) {
        return;
    }
    
    productos.forEach(producto => {
        const option = document.createElement('option');
        option.value = String(producto).trim();
        option.textContent = String(producto).trim();
        datalist.appendChild(option);
    });
}

async function cargarCriteriosPNC(tipo, selectId) {
    try {
        const response = await fetch(`/api/obtener_criterios_pnc/${tipo}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const criterios = await response.json();
        const select = document.getElementById(selectId);
        
        if (select) {
            const currentValue = select.value;
            select.innerHTML = '<option value="">Seleccionar criterio...</option>';
            
            if (criterios && Array.isArray(criterios) && criterios.length > 0) {
                criterios.forEach(criterio => {
                    const option = document.createElement('option');
                    option.value = criterio;
                    option.textContent = criterio;
                    select.appendChild(option);
                });
            } else {
                cargarCriteriosPNCDefault(tipo, select);
            }
            
            if (currentValue) {
                select.value = currentValue;
            }
        }
    } catch (error) {
        console.error(`Error cargando criterios PNC para ${tipo}:`, error);
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
}

//


// ===== FUNCIONES AUXILIARES =====

function actualizarSelectMaquinas(maquinas) {
    const selects = document.querySelectorAll('select[id*="maquina"]');
    selects.forEach(select => {
        const currentValue = select.value;
        select.innerHTML = '<option value="">-- Selecciona máquina --</option>';
        
        if (maquinas && Array.isArray(maquinas)) {
            maquinas.forEach(maquina => {
                const option = document.createElement('option');
                option.value = maquina;
                option.textContent = maquina;
                select.appendChild(option);
            });
        }
        
        if (currentValue && maquinas.includes(currentValue)) {
            select.value = currentValue;
        }
    });
}

function configurarFormularios() {
    console.log('Configurando formularios...');
    
    const hoy = new Date().toISOString().split('T')[0];
    document.querySelectorAll('input[type="date"]').forEach(input => {
        if (!input.value) input.value = hoy;
    });
    
    const formInyeccion = document.getElementById('form-inyeccion');
    if (formInyeccion) {
        formInyeccion.addEventListener('submit', function(e) {
            e.preventDefault();
            if (typeof registrarInyeccion === 'function') registrarInyeccion();
        });
    }
    
    const formPulido = document.getElementById('form-pulido');
    if (formPulido) {
        formPulido.addEventListener('submit', function(e) {
            e.preventDefault();
            if (typeof registrarPulido === 'function') registrarPulido();
        });
    }
    
    const formEnsamble = document.getElementById('form-ensamble');
    if (formEnsamble) {
        formEnsamble.addEventListener('submit', function(e) {
            e.preventDefault();
            if (typeof registrarEnsamble === 'function') registrarEnsamble();
        });
    }
    
    const formPNC = document.getElementById('form-pnc');
    if (formPNC) {
        formPNC.addEventListener('submit', function(e) {
            e.preventDefault();
            if (typeof registrarPNC === 'function') registrarPNC();
        });
    }
    
    const formFacturacion = document.getElementById('form-facturacion');
    if (formFacturacion) {
        formFacturacion.addEventListener('submit', function(e) {
            e.preventDefault();
            if (typeof registrarFacturacion === 'function') registrarFacturacion();
        });
    }
}

// ===== INICIALIZACIÓN DE LA APLICACIÓN =====

function inicializarAplicacion() {
    console.log('Aplicación inicializando...');
    
    // Configurar navegación
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
    
    // Inicializar nuevos módulos si existen
    if (typeof initMezcla === 'function') {
        console.log('✅ Inicializando módulo de Mezcla...');
        initMezcla();
    } else {
        console.warn('⚠️ initMezcla no está definido');
    }
    
    if (typeof initHistorial === 'function') {
        console.log('✅ Inicializando módulo de Historial...');
        initHistorial();
    } else {
        console.warn('⚠️ initHistorial no está definido');
    }
    
    console.log('✅ Aplicación inicializada correctamente');
}

// ===== INICIALIZAR CUANDO EL DOM ESTÉ LISTO =====

document.addEventListener('DOMContentLoaded', function() {
    console.log('🏭 DOM cargado, iniciando aplicación...');
    
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
    
    // Configurar fecha actual en los formularios
    const fechaHoy = new Date().toISOString().split('T')[0];
    document.querySelectorAll('input[type="date"]').forEach(input => {
        // NO llenar fechas de historial automáticamente
        if (input.id === 'fechaDesde' || input.id === 'fechaHasta') {
            // Configurar fechas para historial
            if (input.id === 'fechaDesde') {
                input.value = '2024-01-01';
            }
            if (input.id === 'fechaHasta') {
                input.value = fechaHoy;
            }
            return;
        }

        if (!input.value) {
            input.value = fechaHoy;
        }
    });

    // Botón exportar historial
    const btnExportarHistorial = document.getElementById('btn-exportar-historial');
    if (btnExportarHistorial) {
        btnExportarHistorial.addEventListener('click', function() {
            if (typeof exportarHistorial === 'function') {
                exportarHistorial();
            } else {
                console.error('❌ exportarHistorial no está definido');
            }
        });
    }
    
    // Inicializar aplicación
    inicializarAplicacion();
});

// ===== EXPORTAR FUNCIONES GLOBALES =====

window.cargarPagina = cargarPagina;
window.buscarProductos = buscarProductos;
window.filtrarProductos = filtrarProductos;
// ELIMINADO: Referencias a funciones inexistentes
// window.verDetalleProducto = verDetalleProducto;
// window.mostrarModalNuevoProducto = mostrarModalNuevoProducto;
// window.exportarInventario = exportarInventario;