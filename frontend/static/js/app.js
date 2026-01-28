// Global Error Handler for random execution errors
window.onerror = function (msg, url, lineNo, columnNo, error) {
    console.error('🚨 Global Error:', { msg, url, lineNo, columnNo, error });
    // Optional: Send to backend logging endpoint
    return false;
};

window.addEventListener('unhandledrejection', event => {
    console.error('🚨 Unhandled Promise Rejection:', event.reason);
});

window.AppState = {
    paginaActual: 'dashboard',
    POWER_BI_URL: 'https://app.powerbi.com/view?r=eyJrIjoiZTBlYzc0MmUtNmVmZS00NDVjLWIwNTctMDY4NDA5MjEwNjk2IiwidCI6ImMwNmZiNTU5LTFiNjgtNGI4NC1hMTRmLTQ3ZDBkODM3YTVhYiIsImMiOjR9',
    sharedData: {
        responsables: [],
        clientes: [],
        productos: [],
        maquinas: []
    }
};

// ... (existing code)



async function cargarDatosCompartidos() {
    try {
        console.log('🔄 INICIANDO CARGA DE DATOS COMPARTIDOS...');

        // Cargar todos los datos en paralelo para mejor rendimiento
        const [resProd, resResp, resMaq, resCli] = await Promise.all([
            fetch('/api/productos/listar'),  // Endpoint correcto (no listar_v2)
            fetch('/api/obtener_responsables'),
            fetch('/api/obtener_maquinas'),
            fetch('/api/obtener_clientes')
        ]);

        // 1. Procesar productos
        console.log('  - Respuesta productos:', resProd.status);
        if (!resProd.ok) throw new Error(`Error HTTP productos: ${resProd.status}`);
        const productosData = await resProd.json();
        const productosRaw = productosData.items || productosData;

        window.AppState.sharedData.productos = productosRaw.map(p => ({
            id_codigo: p.id_codigo || 0,
            codigo_sistema: p.codigo || '',
            descripcion: p.descripcion || '',
            imagen: p.imagen || '',
            stock_por_pulir: p.stock_por_pulir || 0,
            stock_terminado: p.stock_terminado || 0,
            stock_total: p.existencias_totales || 0,
            semaforo: p.semaforo || { color: 'gray', estado: '', mensaje: '' },
            metricas: p.metricas || { min: 0, max: 0, reorden: 0 }
        }));
        console.log('  ✅ Productos cargados:', window.AppState.sharedData.productos.length);

        // 2. Procesar responsables
        if (resResp.ok) {
            window.AppState.sharedData.responsables = await resResp.json();
            console.log('  ✅ Responsables cargados:', window.AppState.sharedData.responsables.length);
        }

        // 3. Procesar máquinas
        if (resMaq.ok) {
            window.AppState.sharedData.maquinas = await resMaq.json();
            console.log('  ✅ Máquinas cargadas:', window.AppState.sharedData.maquinas.length);
        }

        // 4. Procesar clientes
        if (resCli.ok) {
            window.AppState.sharedData.clientes = await resCli.json();
            console.log('  ✅ Clientes cargados:', window.AppState.sharedData.clientes.length);
        }

    } catch (error) {
        console.error('❌ CRITICAL ERROR en cargarDatosCompartidos:', error);
        alert('Error conectando con el servidor. Revisa la consola (F12) y asegura que el backend esté corriendo.');
    }
}

/**
 * Cargar una página específica
 */
function cargarPagina(nombrePagina, pushToHistory = true) {
    console.log('📄 Cargando página:', nombrePagina);

    // Ocultar todas las páginas
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    const pagina = document.getElementById(`${nombrePagina}-page`);
    if (pagina) {
        pagina.classList.add('active');
        console.log('✅ Página visible:', nombrePagina);
    } else {
        console.error('❌ Página no encontrada:', `${nombrePagina}-page`);
        return;
    }

    // Actualizar menu items activos
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    const menuItem = document.querySelector(`.menu-item[data-page="${nombrePagina}"]`);
    if (menuItem) {
        menuItem.classList.add('active');
    }

    // Gestionar historial para el botón atrás de móviles Juan Sebastian
    if (pushToHistory) {
        history.pushState({ page: nombrePagina }, '', `#${nombrePagina}`);
    }

    inicializarModulo(nombrePagina);
    window.AppState.paginaActual = nombrePagina;

    // Controlar visibilidad del botón 'Volver' en móviles
    const backBtnContainer = document.getElementById('back-button-container');
    if (backBtnContainer) {
        if (nombrePagina !== 'dashboard' && window.innerWidth < 991) {
            backBtnContainer.classList.add('active');
        } else {
            backBtnContainer.classList.remove('active');
        }
    }
}

// Escuchar el botón atrás del navegador Juan Sebastian
window.addEventListener('popstate', (event) => {
    if (event.state && event.state.page) {
        cargarPagina(event.state.page, false);
    } else {
        cargarPagina('dashboard', false);
    }
});

/**
 * Función global para volver al dashboard
 */
window.volverAlDashboard = function () {
    console.log('🔙 Volviendo al Dashboard...');
    cargarPagina('dashboard');
};

function inicializarModulo(nombrePagina) {
    const modulos = {
        'dashboard': window.ModuloDashboard,
        'inventario': window.ModuloInventario,
        'productos': window.ModuloProductos,
        'inyeccion': window.ModuloInyeccion,
        'pulido': window.ModuloPulido,
        'ensamble': window.ModuloEnsamble,
        'pnc': window.ModuloPNC,
        'facturacion': window.ModuloFacturacion,
        'mezcla': window.ModuloMezcla,
        'historial': window.ModuloHistorial
    };

    const modulo = modulos[nombrePagina];

    // Lógica especial para Dashboard (Power BI) Juan Sebastian
    if (nombrePagina === 'dashboard') {
        const frame = document.getElementById('powerbi-frame');
        const placeholder = document.getElementById('powerbi-placeholder');
        if (frame && window.AppState.POWER_BI_URL && window.AppState.POWER_BI_URL !== 'https://app.powerbi.com/view?r=PLACEHOLDER') {
            if (frame.src === 'about:blank') {
                frame.src = window.AppState.POWER_BI_URL;
                frame.onload = () => { if (placeholder) placeholder.style.display = 'none'; };
            }
        }
    }

    if (modulo?.inicializar) {
        console.log('🔧 Inicializando módulo:', nombrePagina);
        modulo.inicializar();
    } else {
        console.warn('⚠️  Módulo no encontrado:', nombrePagina);
    }
}

function configurarNavegacion() {
    // CORRECCIÓN: Escuchar clicks en .menu-item en lugar de .nav-link
    document.querySelectorAll('.menu-item').forEach(menuItem => {
        menuItem.addEventListener('click', (e) => {
            e.preventDefault();
            const pagina = menuItem.getAttribute('data-page');
            console.log('🖱️  Click en menú:', pagina);
            cargarPagina(pagina);

            // Cerrar sidebar en móvil al hacer click en un item
            if (window.innerWidth < 992) {
                document.querySelector('.sidebar')?.classList.remove('active');
            }
        });
    });

    // Configurar botones de toggle para el sidebar (hamburguesa)
    document.addEventListener('click', (e) => {
        const toggleBtn = e.target.closest('[id^="toggle-sidebar"]');
        if (toggleBtn) {
            console.log('🍔 Toggle sidebar pulsado');
            document.querySelector('.sidebar')?.classList.toggle('active');
        }
    });

    console.log('✅ Navegación configurada -', document.querySelectorAll('.menu-item').length, 'items');
}

async function inicializarAplicacion() {
    console.log('🚀 Aplicación inicializando...');
    try {
        configurarNavegacion();
        await cargarDatosCompartidos();

        // 5. Cargar página inicial (Dashboard o Hash) Juan Sebastian
        const hashPage = window.location.hash.replace('#', '');
        if (hashPage && document.getElementById(`${hashPage}-page`)) {
            cargarPagina(hashPage);
        } else {
            cargarPagina('dashboard');
        }

        console.log('✅ Aplicación inicializada correctamente');
    } catch (error) {
        console.error('❌ Error fatal:', error);
        alert('Error iniciando aplicación. Ver consola.');
    }
}

document.addEventListener('DOMContentLoaded', inicializarAplicacion);