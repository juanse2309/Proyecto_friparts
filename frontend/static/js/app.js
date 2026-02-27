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
    paginaActual: 'metals-dashboard',
    POWER_BI_URL: 'https://app.powerbi.com/view?r=eyJrIjoiZTBlYzc0MmUtNmVmZS00NDVjLWIwNTctMDY4NDA5MjEwNjk2IiwidCI6ImMwNmZiNTU5LTFiNjgtNGI4NC1hMTRmLTQ3ZDBkODM3YTVhYiIsImMiOjR9&pageName=baaf08bf7027114dad16',
    sharedData: {
        responsables: [],
        clientes: [],
        productos: [],
        maquinas: []
    }
};

// ... (existing code)



let datosCargados = false;
async function cargarDatosCompartidos() {
    if (datosCargados) return; // Evitar múltiples cargas
    try {
        console.log('🔄 INICIANDO CARGA DE DATOS COMPARTIDOS...');

        const t = Date.now();
        const [resProd, resResp, resMaq, resCli] = await Promise.all([
            fetch(`/api/productos/listar?_t=${t}`),
            fetch(`/api/obtener_responsables?_t=${t}`),
            fetch(`/api/obtener_maquinas?_t=${t}`),
            fetch(`/api/obtener_clientes?_t=${t}`)
        ]);

        // 1. Procesar productos
        console.log('  - Respuesta productos:', resProd.status);
        if (!resProd.ok) throw new Error(`Error HTTP productos: ${resProd.status}`);
        const productosData = await resProd.json();

        // DEBUG: Log full response structure
        console.log('  - productosData type:', typeof productosData);
        console.log('  - productosData.items?:', productosData.items?.length);
        console.log('  - productosData (is array)?:', Array.isArray(productosData), productosData.length);

        // Handle different response structures
        let productosRaw = [];
        if (productosData.items && Array.isArray(productosData.items)) {
            productosRaw = productosData.items;
        } else if (Array.isArray(productosData)) {
            productosRaw = productosData;
        } else if (productosData.productos && Array.isArray(productosData.productos)) {
            productosRaw = productosData.productos;
        }

        console.log('  - productosRaw length:', productosRaw.length);
        if (productosRaw.length > 0) {
            console.log('  - Sample producto:', JSON.stringify(productosRaw[0]).substring(0, 200));
        }

        window.AppState.sharedData.productos = productosRaw.map(p => ({
            id_codigo: p.id_codigo || p.ID_CODIGO || 0,
            codigo_sistema: p.codigo_sistema || p.codigo || p.CODIGO || '',
            codigo: p.codigo || p.codigo_sistema || '', // Backup
            descripcion: p.descripcion || p.DESCRIPCION || '',
            imagen: p.imagen || '',
            precio: p.precio || p.PRECIO || 0,
            stock_por_pulir: p.stock_por_pulir || p.POR_PULIR || 0,
            stock_terminado: p.stock_terminado || p.TERMINADO || 0,
            stock_total: p.stock_total || p.existencias_totales || p.EXISTENCIAS || 0,
            stock_disponible: p.stock_disponible || 0, // CRITICO
            semaforo: p.semaforo || { color: 'gray', estado: '', mensaje: '' },
            metricas: p.metricas || { min: 0, max: 0, reorden: 0 }
        }));
        console.log('  ✅ Productos cargados en cache:', window.AppState.sharedData.productos.length);

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

        // 4. Procesar clientes (ahora incluye NIT)
        if (resCli.ok) {
            const clientesData = await resCli.json();
            window.AppState.sharedData.clientes = clientesData; // Array de {nombre, nit}
            console.log('  ✅ Clientes cargados:', window.AppState.sharedData.clientes.length);
        }

        datosCargados = true;
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


    // --- Limpieza de procesos del módulo anterior ---
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
        'historial': window.ModuloHistorial,
        'pedidos': window.ModuloPedidos,
        'almacen': window.AlmacenModule,
        'portal-cliente': window.ModuloPortal,
        'admin-clientes': window.ModuloAdminClientes,
        'metals-produccion': window.ModuloMetals,
        'metals-dashboard': window.ModuloMetals,
        'procura': window.ModuloProcura,
        'rotacion': window.ModuloRotacion
    };

    if (window.AppState.paginaActual) {
        const moduloAnterior = modulos[window.AppState.paginaActual];
        if (moduloAnterior && typeof moduloAnterior.desactivar === 'function') {
            console.log(`🔌 Limpiando procesos de: ${window.AppState.paginaActual}`);
            moduloAnterior.desactivar();
        }
    }

    // Ocultar todas las páginas
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    // LÓGICA ESPECIAL PARA FRIMETALS (Páginas dinámicas)
    let pageIdToShow = nombrePagina;
    if (nombrePagina.startsWith('metals-') && nombrePagina !== 'metals-dashboard') {
        pageIdToShow = 'metals-produccion'; // Todas usan el mismo host dinámico
    }

    const pagina = document.getElementById(`${pageIdToShow}-page`);
    if (pagina) {
        pagina.classList.add('active');
        console.log('✅ Página visible:', pageIdToShow);
    } else {
        console.error('❌ Página no encontrada:', `${pageIdToShow}-page`);
        return;
    }

    // Actualizar menu items activos
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    const menuItem = document.querySelector(`.menu-item[data-page="${nombrePagina}"]`);
    if (menuItem) {
        menuItem.classList.add('active');
    }

    // Ensure overlay is removed when changing pages via any method
    document.querySelector('.sidebar')?.classList.remove('active');
    document.querySelector('.sidebar-overlay')?.classList.remove('active');

    // Gestionar historial para el botón atrás de móviles Juan Sebastian
    if (pushToHistory) {
        history.pushState({ page: nombrePagina }, '', `#${nombrePagina}`);
    }

    // Establecer página actual antes de inicializar para evitar race conditions
    window.AppState.paginaActual = nombrePagina;
    inicializarModulo(nombrePagina);

    // Guardar en localStorage para persistencia al recargar
    try {
        localStorage.setItem('friparts_last_page', nombrePagina);
    } catch (e) {
        console.warn('No se pudo guardar página en localStorage:', e);
    }

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
    const division = window.AppState.user?.division || 'FRIPARTS';

    // Si es FRIMETALS, volver a la cuadrícula de producción
    if (division === 'FRIMETALS') {
        cargarPagina('metals-produccion');
    } else {
        cargarPagina('inventario');
    }

    document.querySelector('.sidebar')?.classList.remove('active');
    document.querySelector('.sidebar-overlay')?.classList.remove('active');
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
        'historial': window.ModuloHistorial,
        'pedidos': window.ModuloPedidos,
        'almacen': window.AlmacenModule,
        'admin-clientes': window.ModuloAdminClientes,
        'metals-produccion': window.ModuloMetals,
        'metals-dashboard': window.ModuloMetals,
        'metals-torno': window.ModuloMetals,
        'metals-laser': window.ModuloMetals,
        'metals-soldadura': window.ModuloMetals,
        'metals-marcadora': window.ModuloMetals,
        'metals-taladro': window.ModuloMetals,
        'metals-dobladora': window.ModuloMetals,
        'metals-pintura': window.ModuloMetals,
        'metals-zincado': window.ModuloMetals,
        'metals-horno': window.ModuloMetals,
        'metals-pulido-m': window.ModuloMetals,
        'procura': window.ModuloProcura,
        'rotacion': window.ModuloRotacion
    };

    const modulo = modulos[nombrePagina];

    // Lógica especial para Dashboard (Power BI) Juan Sebastian
    // Lógica especial para Dashboard (Power BI) Juan Sebastian
    if (nombrePagina === 'dashboard') {
        const frame = document.getElementById('powerbi-frame');
        const placeholder = document.getElementById('powerbi-placeholder');

        if (frame && window.AppState.POWER_BI_URL) {
            // Si es un placeholder dummy, no intentar cargar
            if (window.AppState.POWER_BI_URL.includes('PLACEHOLDER')) {
                if (placeholder) placeholder.innerHTML = '<div class="text-center p-5">Dashboard no configurado. Contacte al administrador.</div>';
                return;
            }

            // Cargar solo si está vacío
            if (frame.src === 'about:blank' || frame.src === '') {
                console.log('📊 Cargando Power BI iframe...');
                frame.src = window.AppState.POWER_BI_URL;

                // Fallback por si el onload no dispara (seguridad)
                setTimeout(() => {
                    if (placeholder && placeholder.style.display !== 'none') {
                        console.log('⚠️ Power BI timeout - Ocultando placeholder forzosamente');
                        // No ocultamos del todo por si falla, pero permitimos interacción? 
                        // Mejor: mostramos mensaje de "Si no carga..."
                        const msg = document.createElement('div');
                        msg.innerHTML = `<p class="mt-3 text-muted">¿Tarda mucho? <a href="${window.AppState.POWER_BI_URL}" target="_blank">Abrir directamente en Power BI</a></p>`;
                        if (placeholder.querySelector('.spinner-border')) {
                            placeholder.querySelector('.text-center').appendChild(msg);
                        }
                    }
                }, 5000);

                frame.onload = () => {
                    console.log('✅ Power BI iframe cargado');
                    if (placeholder) placeholder.style.display = 'none';
                };
            }
        }
    }

    // CRÍTICO: Verificar que el usuario esté logueado antes de inicializar módulos
    const userLoggedIn = window.AppState && window.AppState.user && window.AppState.user.name;

    if (modulo?.inicializar) {
        if (!userLoggedIn && nombrePagina !== 'dashboard') {
            console.log(`ℹ️  Módulo ${nombrePagina} esperando login de usuario...`);

            // Función para intentar inicializar cuando el usuario esté listo
            const intentarInicializar = () => {
                const userNowLoggedIn = window.AppState && window.AppState.user && (window.AppState.user.name || window.AppState.user.nombre);
                if (userNowLoggedIn) {
                    // Asegurar campos por compatibilidad
                    if (!window.AppState.user.name) window.AppState.user.name = window.AppState.user.nombre;
                    if (!window.AppState.user.nombre) window.AppState.user.nombre = window.AppState.user.name;

                    console.log(`🔧 Inicializando módulo (vía evento/retry): ${nombrePagina}`);
                    modulo.inicializar();
                    return true;
                }
                return false;
            };

            // Escuchar evento de usuario listo (Solo una vez)
            const onUserReadyApp = () => {
                if (intentarInicializar()) {
                    window.removeEventListener('user-ready', onUserReadyApp);
                }
            };
            window.addEventListener('user-ready', onUserReadyApp);

            // Safety Retry (por si el evento se disparó justo antes)
            setTimeout(() => {
                if (intentarInicializar()) {
                    window.removeEventListener('user-ready', onUserReadyApp);
                    document.removeEventListener('user-ready', onUserReadyApp);
                } else {
                    console.warn(`⚠️  Módulo ${nombrePagina} sigue esperando usuario tras 1s...`);
                    // Un último reintento a los 3s
                    setTimeout(() => {
                        if (intentarInicializar()) {
                            window.removeEventListener('user-ready', onUserReadyApp);
                            document.removeEventListener('user-ready', onUserReadyApp);
                        } else {
                            console.error(`❌  Módulo ${nombrePagina} NO pudo inicializarse: usuario no logueado`);
                        }
                    }, 2000);
                }
            }, 1000);
            return;
        }
        console.log('🔧 Inicializando módulo:', nombrePagina);
        modulo.inicializar();
    }
    else {
        console.warn('⚠️  Módulo no encontrado (intento 1):', nombrePagina);
        // REINTENTO DE CARGA DE MODULO (Fix Race Condition Loading)
        setTimeout(() => {
            const modulosRetry = {
                'dashboard': window.ModuloDashboard,
                'inventario': window.ModuloInventario,
                'productos': window.ModuloProductos,
                'inyeccion': window.ModuloInyeccion,
                'pulido': window.ModuloPulido,
                'ensamble': window.ModuloEnsamble,
                'pnc': window.ModuloPNC,
                'facturacion': window.ModuloFacturacion,
                'mezcla': window.ModuloMezcla,
                'historial': window.ModuloHistorial,
                'pedidos': window.ModuloPedidos,
                'almacen': window.AlmacenModule,
                'admin-clientes': window.ModuloAdminClientes,
                'metals-produccion': window.ModuloMetals,
                'metals-dashboard': window.ModuloMetals,
                'procura': window.ModuloProcura,
                'rotacion': window.ModuloRotacion
            };
            const moduloRetry = modulosRetry[nombrePagina];
            if (moduloRetry?.inicializar) {
                console.log(`✅ Módulo ${nombrePagina} encontrado en reintento.`);
                moduloRetry.inicializar();
            } else {
                console.error(`❌ Error fatal: Módulo ${nombrePagina} no cargó después del reintento.`);
            }
        }, 800);
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
                document.querySelector('.sidebar-overlay')?.classList.remove('active');
            }
        });
    });

    // Configurar botones de toggle para el sidebar (hamburguesa)
    // Configurar botones de toggle para el sidebar (hamburguesa)
    const handleSidebarToggle = (e) => {
        const toggleBtn = e.target.closest('[id^="toggle-sidebar"]');
        if (toggleBtn) {
            e.preventDefault();
            console.log('🍔 Toggle sidebar pulsado');

            const sidebar = document.querySelector('.sidebar');
            const mainContent = document.querySelector('.main-content');
            const overlay = document.querySelector('.sidebar-overlay');

            // En móviles usamos 'active' para el overlay
            if (window.innerWidth < 992) {
                sidebar?.classList.toggle('active');
                overlay?.classList.toggle('active');
            } else {
                // En escritorio usamos 'collapsed' y 'expanded'
                sidebar?.classList.toggle('collapsed');
                mainContent?.classList.toggle('expanded');
            }
        }
    };

    document.addEventListener('click', handleSidebarToggle);
    document.addEventListener('touchstart', handleSidebarToggle, { passive: false });

    // CORRECCIÓN: Escuchar cambios en el hash para navegación directa
    window.addEventListener('hashchange', () => {
        const hashPage = window.location.hash.replace('#', '');
        console.log("🔄 Hash changed:", hashPage);
        if (hashPage && document.getElementById(`${hashPage}-page`)) {
            cargarPagina(hashPage);
        }
    });

    console.log('✅ Navegación configurada -', document.querySelectorAll('.menu-item').length, 'items');
}

// Exponer cargarPagina globalmente para que auth.js pueda re-inicializar módulos tras login
const _cargarPaginaOriginal = cargarPagina;
window.cargarPagina = function (page, push) { _cargarPaginaOriginal(page, push); };

async function inicializarAplicacion() {
    console.log('🚀 Aplicación inicializando...');
    try {
        configurarNavegacion();

        // --- Optimización Cuota (Error 429) ---
        // Solo cargar datos si YA hay un usuario en sesión
        const sessionUser = sessionStorage.getItem('friparts_user');
        if (sessionUser) {
            console.log('👤 Sesión activa detectada. Cargando datos...');
            await cargarDatosCompartidos();
        } else {
            console.log('⏳ Sin sesión activa. Datos compartidos se cargarán post-login.');
        }

        // Escuchar evento de login para cargar datos si no estaban cargados
        document.addEventListener('user-ready', async () => {
            console.log('🔔 Evento user-ready recibido. Asegurando carga de datos...');
            await cargarDatosCompartidos();
        });

        // 5. Cargar página inicial (Dashboard o Hash)
        // CORRECCIÓN CRÍTICA: Si AuthModule ya activó portal-cliente, no sobreescribir.
        const activePage = document.querySelector('.page.active');
        if (activePage && activePage.id === 'portal-cliente-page') {
            console.log("🚀 Portal Cliente ya activo. Preservando...");
            const pageId = activePage.id.replace('-page', '');
            inicializarModulo(pageId);
            console.log('✅ Aplicación inicializada correctamente (Portal Cliente preservado)');
            return;
        }

        const hashPage = window.location.hash.replace('#', '');
        const division = window.AppState.user?.division || 'FRIPARTS';

        // Intentar restaurar última página visitada desde localStorage
        let pageToLoad = null;

        if (hashPage && document.getElementById(`${hashPage}-page`)) {
            pageToLoad = hashPage;
            console.log('📍 Cargando desde hash:', hashPage);
        } else if (division === 'FRIMETALS') {
            // Juan Sebastian: Forzar aterrizaje en cuadrícula para Metales
            pageToLoad = 'metals-produccion';
            console.log('🏭 Forzando landing de Metales (Grid):', pageToLoad);
        } else {
            try {
                const lastPage = localStorage.getItem('friparts_last_page');
                if (lastPage && document.getElementById(`${lastPage}-page`)) {
                    pageToLoad = lastPage;
                    console.log('💾 Restaurando última página visitada:', lastPage);
                }
            } catch (e) {
                console.warn('No se pudo leer localStorage:', e);
            }
        }

        if (pageToLoad) {
            cargarPagina(pageToLoad);
        } else {
            // Fallback default
            cargarPagina('dashboard');
        }

        console.log('✅ Aplicación inicializada correctamente');
    } catch (error) {
        console.error('❌ Error fatal:', error);
        alert('Error iniciando aplicación. Ver consola.');
    }
}

/**
 * Configurar animaciones de entrada (Scroll Reveal)
 */
function configurarAnimacionesEntrada() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('reveal');
                // Una vez revelado, no necesitamos observarlo más
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observar elementos con clase .animate-on-scroll
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    inicializarAplicacion();
    configurarAnimacionesEntrada();
});