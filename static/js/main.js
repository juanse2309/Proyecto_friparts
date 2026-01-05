// Configuración de formularios
const configs = {
    inyeccion: [
        { label: 'Fecha Inicio', name: 'fecha_inicio', type: 'date', req: true },
        { label: 'Fecha Fin', name: 'fecha_fin', type: 'date', req: true },
        { label: 'Máquina', name: 'maquina', type: 'select', options: ['1','2','3','4'], req: true },
        { label: 'Responsable', name: 'responsable', type: 'select_responsable', req: true },
        { label: 'ID Código Buje', name: 'codigo_producto', type: 'datalist_productos', req: true },
        { label: 'No. Cavidades', name: 'no_cavidades', type: 'number', req: true, val: 1 },
        { label: 'Hora Inicio', name: 'hora_inicio', type: 'time', req: true },
        { label: 'Hora Fin', name: 'hora_fin', type: 'time', req: true },
        { label: 'Golpes Máquina', name: 'cantidad_real', type: 'number', req: true },
        { label: 'PNC (Malos)', name: 'pnc', type: 'number', val: 0 },
        { label: 'Criterio PNC', name: 'criterio_pnc', type: 'select', options: ['', 'Escaso', 'Manchado o contaminado', 'Rechupe', 'Buje de prueba'] },
        { label: 'Orden Producción', name: 'orden_produccion', type: 'text' },
        { label: 'Observaciones', name: 'observaciones', type: 'textarea', full: true }
    ],
    pulido: [
        { label: 'ID Pulido', name: 'id_pulido', type: 'text', val: 'AUTO-GENERADO', readonly: true },
        { label: 'Fecha', name: 'fecha_inicio', type: 'date', req: true },
        { label: 'Responsable', name: 'responsable', type: 'select_responsable', req: true },
        { label: 'Hora Inicio', name: 'hora_inicio', type: 'time', req: true },
        { label: 'Hora Fin', name: 'hora_fin', type: 'time', req: true },
        { label: 'Código Producto', name: 'codigo_producto', type: 'datalist_productos', req: true },
        { label: 'Lote (Fecha)', name: 'lote', type: 'date' },
        { label: 'Orden Producción', name: 'orden_produccion', type: 'text' },
        { label: 'Cantidad Recibida', name: 'cantidad_recibida', type: 'number', req: true },
        { label: 'PNC (Malos)', name: 'pnc', type: 'number', val: 0 },
        { label: 'Criterio PNC', name: 'criterio_pnc', type: 'select', options: ['', 'Escaso', 'Manchado o contaminado', 'Rechupe', 'Buje de prueba'] },
        { label: 'Cantidad Real (Buenos)', name: 'cantidad_real', type: 'number', readonly: true },
        { label: 'Observaciones', name: 'observaciones', type: 'textarea', full: true }
    ],
    ensamble: [
        { label: 'Fecha', name: 'fecha_inicio', type: 'date', req: true },
        { label: 'Responsable', name: 'responsable', type: 'select_responsable', req: true },
        { label: 'Código Final (A Ensamblar)', name: 'codigo_producto', type: 'datalist_productos', req: true },
        { label: 'Cantidad Recibida', name: 'cantidad_recibida', type: 'number', req: true, val: 0 },
        { label: 'PNC (Malos)', name: 'pnc', type: 'number', val: 0 },
        { label: 'Criterio PNC', name: 'criterio_pnc', type: 'select', options: ['', 'Carcaza manchada', 'Carcaza abierta', 'Falta de piezas', 'Ensamblaje defectuoso', 'Daño en transporte', 'Material defectuoso', 'Otro'] },
        { label: 'Cantidad Final (Buenos)', name: 'cantidad_real', type: 'number', readonly: true, val: 0 },
        { label: 'Almacén Origen', name: 'almacen_origen', type: 'select', options: ['P. TERMINADO', 'POR PULIR', 'PRODUCTO ENSAMBLADO'], req: true },
        { label: 'Almacén Destino', name: 'almacen_destino', type: 'select', options: ['PRODUCTO ENSAMBLADO', 'CLIENTE'], req: true },
        { label: 'Orden Producción', name: 'orden_produccion', type: 'text' },
        { label: 'Hora Inicio', name: 'hora_inicio', type: 'time' },
        { label: 'Hora Fin', name: 'hora_fin', type: 'time' },
        { label: 'Observaciones', name: 'observaciones', type: 'textarea', full: true }
    ],
    facturacion: [
        { label: 'Cliente', name: 'cliente', type: 'datalist_clientes', req: true },
        { label: 'Fecha', name: 'fecha_inicio', type: 'date', req: true },
        { label: 'Código Producto', name: 'codigo_producto', type: 'datalist_productos', req: true },
        { label: 'Cantidad Vendida', name: 'cantidad_vendida', type: 'number', req: true },
        { label: 'Total Venta', name: 'total_venta', type: 'number', step: '0.01' },
        { label: 'Observaciones', name: 'observaciones', type: 'textarea', full: true }
    ]
};

// Inicialización de la aplicación
async function inicializarApp() {
    console.log('Inicializando aplicación...');
    await cargarDatosIniciales();
    configurarEventListeners();
    console.log('Aplicación lista');
}

// Cargar datos iniciales
async function cargarDatosIniciales() {
    try {
        const [resResp, resProd, resCli] = await Promise.all([
            fetch('http://127.0.0.1:5000/api/obtener_responsables'),
            fetch('http://127.0.0.1:5000/api/obtener_productos'),
            fetch('http://127.0.0.1:5000/api/obtener_clientes')
        ]);
        
        window.AppState.listaResponsables = await resResp.json();
        window.AppState.listaProductos = await resProd.json();
        window.AppState.listaClientes = await resCli.json();
        
        console.log('Datos cargados:', {
            responsables: window.AppState.listaResponsables.length,
            productos: window.AppState.listaProductos.length,
            clientes: window.AppState.listaClientes.length
        });
        
    } catch (err) { 
        console.error("Error cargando datos iniciales:", err);
        mostrarNotificacion('Error cargando datos iniciales', 'error');
    }
}

// Configurar event listeners
function configurarEventListeners() {
    const mainForm = document.getElementById('mainForm');
    if (mainForm) {
        mainForm.addEventListener('submit', manejarEnvioFormulario);
    }
}

// Navegación principal
function navigateTo(section, tab = null) {
    const sections = [
        'main-menu',
        'form-container',
        'products-container',
        'product-detail-container',
        'dashboard-avanzado-container'
    ];
    
    sections.forEach(sectionId => safeHide(sectionId));
    
    switch(section) {
        case 'registro':
            if (safeDisplay('form-container')) {
                window.AppState.currentTab = tab;
                if (typeof renderFields === 'function') {
                    renderFields(tab);
                }
            }
            break;
            
        case 'productos':
            if (safeDisplay('products-container')) {
                if (typeof cargarProductos === 'function') {
                    cargarProductos();
                }
                if (typeof cargarEstadisticas === 'function') {
                    cargarEstadisticas();
                }
            }
            break;
            
        case 'dashboard':
            if (safeDisplay('dashboard-avanzado-container')) {
                if (typeof inicializarDashboard === 'function') {
                    inicializarDashboard();
                }
            }
            break;
            
        default:
            console.warn(`Sección "${section}" no reconocida`);
            goBack();
    }
}

// Volver al menú principal
function goBack() {
    safeHide('form-container');
    safeHide('products-container');
    safeHide('product-detail-container');
    safeHide('dashboard-avanzado-container');
    safeDisplay('main-menu');
}

// Volver a lista de productos desde detalle
function volverAListaProductos() {
    safeHide('product-detail-container');
    safeDisplay('products-container');
}

// Manejar envío de formulario
async function manejarEnvioFormulario(e) {
    e.preventDefault();
    const respDiv = safeGetElement('response');
    const btnSubmit = safeGetElement('btnSubmit');
    
    if (!btnSubmit) return;
    
    btnSubmit.disabled = true;
    btnSubmit.style.opacity = '0.7';
    btnSubmit.innerHTML = '⏳ Procesando...';
    
    const data = Object.fromEntries(new FormData(e.target).entries());
    
    try {
        const res = await fetch(`http://127.0.0.1:5000/api/${window.AppState.currentTab}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await res.json();
        
        if (respDiv) {
            respDiv.className = res.ok ? 'success' : 'error';
            respDiv.innerText = (res.ok ? '✅ ' : '❌ ') + result.message;
            respDiv.style.display = 'block';
        }
        
        if(res.ok) { 
            mostrarNotificacion('Operación registrada exitosamente', 'success');
            setTimeout(() => {
                e.target.reset(); 
                if (typeof renderFields === 'function') {
                    renderFields(window.AppState.currentTab);
                }
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }, 1000);
        } else {
            mostrarNotificacion(result.message, 'error');
        }
    } catch (err) { 
        if (respDiv) {
            respDiv.className = 'error'; 
            respDiv.innerText = '❌ Error de conexión con el servidor'; 
            respDiv.style.display = 'block';
        }
        mostrarNotificacion('Error de conexión con el servidor', 'error');
        console.error('Error en solicitud:', err);
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.style.opacity = '1';
        btnSubmit.innerHTML = 'Registrar Operación';
        
        setTimeout(() => {
            if (typeof renderFields === 'function') {
                renderFields(window.AppState.currentTab);
            }
        }, 3000);
    }
}

// Exportar funciones globales
window.navigateTo = navigateTo;
window.goBack = goBack;
window.volverAListaProductos = volverAListaProductos;
window.manejarEnvioFormulario = manejarEnvioFormulario;
window.configs = configs;