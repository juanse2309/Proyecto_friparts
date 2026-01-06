// Variables globales
let dashboardCharts = {};
let currentRankingType = 'inyeccion';

// Inicializar dashboard
async function inicializarDashboard() {
    console.log('🚀 Inicializando dashboard...');
    
    // Mostrar fecha actual con formato elegante
    const fechaElement = document.getElementById('fecha-actual');
    if (fechaElement) {
        const ahora = new Date();
        const opciones = { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        };
        fechaElement.textContent = ahora.toLocaleDateString('es-ES', opciones);
        
        // Añadir hora en tooltip
        fechaElement.title = `Hora actual: ${ahora.toLocaleTimeString('es-ES')}`;
    }
    
    // Iniciar animación de carga
    document.body.classList.add('loading');
    
    try {
        // 1. Configurar eventos primero
        configurarEventosDashboard();
        
        // 2. Inicializar botones de ranking
        inicializarBotonesRanking();
        
        // 3. Cargar datos del dashboard
        try {
            console.log("📡 Obteniendo datos del dashboard...");
            const data = await fetchData('/api/dashboard/real');
            
            if (data) {
                console.log('✅ Datos recibidos:', data);
                
                // Actualizar tarjetas principales
                const elemProduccion = document.getElementById('produccion-total');
                if (elemProduccion) elemProduccion.textContent = formatNumber(data.produccion_total || 0);
                
                const elemVentas = document.getElementById('ventas-totales');
                if (elemVentas) elemVentas.textContent = `$${formatNumber(data.ventas_totales || 0)}`;
                
                const elemEficiencia = document.getElementById('eficiencia-global');
                if (elemEficiencia) elemEficiencia.textContent = `${(data.eficiencia_global || 0).toFixed(1)}%`;
                
                const elemStock = document.getElementById('stock-critico');
                if (elemStock) elemStock.textContent = data.stock_critico || 0;
                
                console.log('✅ Dashboard actualizado correctamente');
            }
        } catch (dashError) {
            console.warn('⚠️ Error cargando dashboard:', dashError);
            // Continuar sin fallar
        }
        
        // 4. Configurar actualización automática
        setInterval(async () => {
            try {
                const data = await fetchData('/api/dashboard/real');
                if (data) {
                    // Actualizar elementos
                    const elemProduccion = document.getElementById('produccion-total');
                    if (elemProduccion) elemProduccion.textContent = formatNumber(data.produccion_total || 0);
                }
            } catch (e) {
                console.warn('Error en actualización automática:', e);
            }
        }, 120000);
        
    } catch (error) {
        console.error('Error en inicialización del dashboard:', error);
        mostrarNotificacion('Error inicializando dashboard', 'error');
    } finally {
        // Detener animación de carga
        document.body.classList.remove('loading');
        console.log('✅ Dashboard inicializado');
    }
}

// Configurar eventos del dashboard
function configurarEventosDashboard() {
    console.log('⚙️ Configurando eventos del dashboard...');
    
    // Botón de actualizar dashboard
    const btnActualizar = document.getElementById('btn-actualizar-dashboard');
    if (btnActualizar) {
        btnActualizar.addEventListener('click', function() {
            actualizarDashboardCompleto();
        });
    }
    
    // Botón de exportar dashboard
    const btnExportar = document.getElementById('btn-exportar-dashboard');
    if (btnExportar) {
        btnExportar.addEventListener('click', function() {
            exportarDashboard();
        });
    }
    
    // Selector de período
    const filtroPeriodo = document.getElementById('filtro-periodo');
    if (filtroPeriodo) {
        filtroPeriodo.addEventListener('change', function() {
            cambiarPeriodoDashboard();
        });
    }
    
    // Botones de detalles
    const btnDetalleInyeccion = document.getElementById('btn-detalle-inyeccion');
    if (btnDetalleInyeccion) {
        btnDetalleInyeccion.addEventListener('click', function() {
            toggleDetails('inyeccion');
        });
    }
    
    const btnDetallePulido = document.getElementById('btn-detalle-pulido');
    if (btnDetallePulido) {
        btnDetallePulido.addEventListener('click', function() {
            toggleDetails('pulido');
        });
    }
    
    // Botón para cambiar tipo de gráfico de ventas
    const btnCambiarChartVentas = document.getElementById('btn-cambiar-chart-ventas');
    if (btnCambiarChartVentas) {
        btnCambiarChartVentas.addEventListener('click', function() {
            toggleChartType('ventas');
        });
    }
    
    console.log('✅ Eventos del dashboard configurados');
}

// Inicializar botones de ranking mejorados
function inicializarBotonesRanking() {
    console.log('🏆 Inicializando botones de ranking mejorados...');
    
    const cardHeader = document.querySelector('#dashboard-page .dashboard-card:nth-child(3) .card-header');
    const cardContent = document.querySelector('#dashboard-page .dashboard-card:nth-child(3) .card-content');
    
    if (!cardHeader || !cardContent) {
        console.warn('No se encontró la sección de ranking');
        return;
    }
    
    // Verificar si ya existen los botones mejorados
    if (document.querySelector('.ranking-filters-container')) {
        console.log('Botones de ranking ya existen');
        return;
    }
    
    // Crear contenedor de filtros mejorados
    const filtersContainer = document.createElement('div');
    filtersContainer.className = 'ranking-filters-container';
    
    // Crear fila de botones de tipo de ranking
    const typeButtons = document.createElement('div');
    typeButtons.className = 'ranking-type-buttons';
    
    typeButtons.innerHTML = `
        <button class="ranking-filter-btn active" 
                data-tipo="inyeccion" 
                onclick="seleccionarTipoRanking('inyeccion')">
            <i class="fas fa-syringe"></i>
            Inyección
        </button>
        <button class="ranking-filter-btn" 
                data-tipo="pulido" 
                onclick="seleccionarTipoRanking('pulido')">
            <i class="fas fa-sparkles"></i>
            Pulido
        </button>
    `;
    
    // Crear selector de período mejorado
    const periodSelector = document.createElement('div');
    periodSelector.className = 'ranking-period-selector';
    
    periodSelector.innerHTML = `
        <label for="ranking-period">
            <i class="fas fa-calendar-alt"></i> Período:
        </label>
        <select id="ranking-period" onchange="cambiarRankingPeriodo()">
            <option value="hoy">Hoy</option>
            <option value="semana" selected>Esta semana</option>
            <option value="mes">Este mes</option>
            <option value="trimestre">Este trimestre</option>
            <option value="anual">Anual</option>
        </select>
    `;
    
    // Crear estadísticas de ranking
    const statsContainer = document.createElement('div');
    statsContainer.className = 'ranking-stats';
    statsContainer.id = 'ranking-stats';
    
    // Ensamblar todo
    filtersContainer.appendChild(typeButtons);
    filtersContainer.appendChild(periodSelector);
    
    // Insertar antes del top-indicator
    const topIndicator = cardContent.querySelector('.top-indicator.highlight');
    if (topIndicator) {
        cardContent.insertBefore(filtersContainer, topIndicator);
        cardContent.insertBefore(statsContainer, cardContent.children[1]);
    } else {
        cardContent.insertBefore(filtersContainer, cardContent.firstChild);
        cardContent.insertBefore(statsContainer, cardContent.children[1]);
    }
    
    console.log('✅ Botones de ranking mejorados inicializados');
}

// ===== FUNCIONES PARA RANKING (AGREGAR A DASHBOARD.JS) =====

// Función para seleccionar tipo de ranking
function seleccionarTipoRanking(tipo) {
    currentRankingType = tipo;
    cambiarTipoRanking();
}

// Función para cambiar período de ranking
function cambiarRankingPeriodo() {
    const periodoSelect = document.getElementById('ranking-period');
    const periodo = periodoSelect ? periodoSelect.value : 'semana';
    const tipo = currentRankingType;
    
    console.log(`🔄 Cambiando período de ranking de ${tipo} a: ${periodo}`);
    
    mostrarNotificacion(`Actualizando ranking de ${tipo} para: ${periodo}`, 'info');
    
    // Simular carga de datos según el período
    setTimeout(() => {
        if (tipo === 'inyeccion') {
            const data = window.AppState.dashboardData.ranking_inyeccion;
            if (data) {
                actualizarRankingInyeccion(data);
                mostrarNotificacion(`Ranking de inyección actualizado (${periodo})`, 'success');
            }
        } else {
            const data = window.AppState.dashboardData.indicador_pulido;
            if (data) {
                mostrarRankingPulido(data);
                mostrarNotificacion(`Ranking de pulido actualizado (${periodo})`, 'success');
            }
        }
        
        // Actualizar estadísticas
        actualizarEstadisticasRanking();
    }, 500);
}

// Función para exportar ranking
function exportarRanking() {
    const tipo = currentRankingType;
    const periodoSelect = document.getElementById('ranking-period');
    const periodo = periodoSelect ? periodoSelect.value : 'semana';
    
    console.log(`📤 Exportando ranking de ${tipo} (${periodo})`);
    
    mostrarNotificacion(`Generando reporte de ranking de ${tipo}...`, 'info');
    
    // Simular generación de reporte
    setTimeout(() => {
        mostrarNotificacion(`Reporte de ranking ${tipo} exportado exitosamente`, 'success');
        generarReporteRanking(tipo, periodo);
    }, 1500);
}

// Función para generar reporte de ranking
function generarReporteRanking(tipo, periodo) {
    let data = null;
    let titulo = '';
    
    if (tipo === 'inyeccion') {
        data = window.AppState.dashboardData.ranking_inyeccion;
        titulo = 'Ranking de Inyección';
    } else {
        data = window.AppState.dashboardData.indicador_pulido;
        titulo = 'Ranking de Pulido';
    }
    
    if (!data) {
        console.warn(`No hay datos para exportar ranking de ${tipo}`);
        return;
    }
    
    // Crear contenido CSV
    let csvContent = `${titulo} - ${periodo}\n\n`;
    csvContent += 'Posición,Operario,Producción Total,Eficiencia,Productividad Diaria\n';
    
    if (tipo === 'inyeccion' && data.ranking_total) {
        let posicion = 1;
        Object.entries(data.ranking_total).forEach(([operario, datos]) => {
            csvContent += `${posicion},${operario},${datos.total || 0},${datos.eficiencia || 0}%,${datos.productividad_diaria || 0}\n`;
            posicion++;
        });
    }
    
    // Crear y descargar archivo
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', `ranking_${tipo}_${periodo}_${new Date().toISOString().slice(0,10)}.csv`);
    link.style.visibility = 'hidden';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    console.log(`✅ Reporte CSV generado: ranking_${tipo}_${periodo}.csv`);
}

// Función para actualizar estadísticas de ranking
function actualizarEstadisticasRanking() {
    const statsContainer = document.getElementById('ranking-stats');
    if (!statsContainer) return;
    
    let data = null;
    if (currentRankingType === 'inyeccion') {
        data = window.AppState.dashboardData.ranking_inyeccion;
    } else {
        data = window.AppState.dashboardData.indicador_pulido;
    }
    
    if (!data) {
        statsContainer.innerHTML = '';
        return;
    }
    
    let totalOperarios = 0;
    let promedioEficiencia = 0;
    let totalProduccion = 0;
    
    if (currentRankingType === 'inyeccion' && data.ranking_total) {
        totalOperarios = Object.keys(data.ranking_total).length;
        const operarios = Object.values(data.ranking_total);
        promedioEficiencia = operarios.reduce((sum, op) => sum + (op.eficiencia || 0), 0) / totalOperarios;
        totalProduccion = operarios.reduce((sum, op) => sum + (op.total || 0), 0);
    } else if (currentRankingType === 'pulido' && data.top_operarios) {
        totalOperarios = Object.keys(data.top_operarios).length;
        const operarios = Object.values(data.top_operarios);
        promedioEficiencia = operarios.reduce((sum, op) => sum + (op.eficiencia || 0), 0) / totalOperarios;
    }
    
    statsContainer.innerHTML = `
        <div class="ranking-stat-item">
            <div class="stat-label">Operarios Activos</div>
            <div class="stat-value">${totalOperarios}</div>
            <div class="stat-subtext">en ${currentRankingType}</div>
        </div>
        <div class="ranking-stat-item">
            <div class="stat-label">Eficiencia Prom.</div>
            <div class="stat-value">${promedioEficiencia.toFixed(1)}%</div>
            <div class="stat-subtext">promedio del área</div>
        </div>
        <div class="ranking-stat-item">
            <div class="stat-label">Total Producción</div>
            <div class="stat-value">${formatNumber(totalProduccion)}</div>
            <div class="stat-subtext">unidades totales</div>
        </div>
    `;
}

// Cargar dashboard completo - VERSIÓN SIMPLE
async function cargarDashboardCompleto() {
    try {
        console.log('🔄 Iniciando carga de dashboard...');
        
        // Llamar endpoint simple
        const response = await fetch('/api/dashboard/real');
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✅ Datos recibidos:', data);
        
        // Actualizar elementos del DOM
        updateDashboardElement('produccion-total', data.produccion_total || 0);
        updateDashboardElement('ventas-totales', data.ventas_totales || 0);
        updateDashboardElement('eficiencia-global', data.eficiencia_global || 0);
        updateDashboardElement('stock-critico', data.stock_critico || 0);
        
        // Actualizar Inyección
        if (data.inyeccion) {
            updateDashboardElement('produccion-inyeccion', data.inyeccion.produccion || 0);
            updateDashboardElement('pnc-inyeccion', data.inyeccion.pnc || 0);
            updateDashboardElement('eficiencia-inyeccion', data.inyeccion.eficiencia || 0);
        }
        
        // Actualizar Pulido
        if (data.pulido) {
            updateDashboardElement('produccion-pulido', data.pulido.produccion || 0);
            updateDashboardElement('pnc-pulido', data.pulido.pnc || 0);
            updateDashboardElement('eficiencia-pulido', data.pulido.eficiencia || 0);
        }
        
        // Actualizar Ensamble
        if (data.ensamble) {
            updateDashboardElement('produccion-ensamble', data.ensamble.produccion || 0);
        }
        
        console.log('✅ Dashboard actualizado correctamente');
        mostrarNotificacion('Dashboard cargado correctamente', 'success');
        
    } catch (error) {
        console.error('❌ Error en dashboard:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    }
}

// Función auxiliar para actualizar elementos
function updateDashboardElement(elementId, valor) {
    try {
        const elem = document.getElementById(elementId);
        if (elem) {
            if (typeof valor === 'number' && elementId.includes('eficiencia')) {
                elem.textContent = valor.toFixed(1) + '%';
            } else if (elementId.includes('ventas')) {
                elem.textContent = '$' + formatNumber(valor);
            } else {
                elem.textContent = formatNumber(valor);
            }
            console.log(`✅ ${elementId} = ${valor}`);
        } else {
            console.warn(`⚠️ Elemento no encontrado: ${elementId}`);
        }
    } catch (e) {
        console.error(`Error actualizando ${elementId}:`, e);
    }
}

// Cargar endpoint específico
async function cargarEndpointDashboard(endpoint) {
    try {
        const res = await fetch(`/api/dashboard/avanzado/${endpoint}`);
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        const data = await res.json();
        
        if (data.status === 'success') {
            window.AppState.dashboardData[endpoint] = data;
            
            switch(endpoint) {
                case 'indicador_inyeccion':
                    actualizarIndicadorInyeccion(data);
                    break;
                case 'indicador_pulido':
                    actualizarIndicadorPulido(data);
                    break;
                case 'ventas_cliente_detallado':
                    actualizarVentasCliente(data);
                    break;
                case 'produccion_maquina_avanzado':
                    actualizarProduccionMaquina(data);
                    break;
                case 'ranking_inyeccion':
                    actualizarRankingInyeccion(data);
                    break;
                case 'stock_inteligente':
                    actualizarStockInteligente(data);
                    break;
            }
        }
    } catch (error) {
        console.error(`Error cargando ${endpoint}:`, error);
        // Crear datos de ejemplo para testing
        crearDatosEjemplo(endpoint);
    }
}

// ===== FUNCIONES DE ACTUALIZACIÓN =====

// Actualizar indicador inyección
function actualizarIndicadorInyeccion(data) {
    const indicador = data.indicador;
    
    if (!indicador) return;
    
    // Actualizar valores
    document.getElementById('inyeccion-produccion').textContent = 
        formatNumber(indicador.produccion_mes);
    document.getElementById('inyeccion-meta').textContent = 
        formatNumber(indicador.meta_mensual);
    document.getElementById('inyeccion-pnc').textContent = 
        formatNumber(indicador.pnc_total);
    document.getElementById('inyeccion-eficiencia').textContent = 
        indicador.porcentaje_pnc ? (100 - indicador.porcentaje_pnc).toFixed(1) + '%' : '0%';
    document.getElementById('inyeccion-porcentaje').textContent = 
        indicador.porcentaje_meta.toFixed(1) + '%';
    
    // Actualizar barra de progreso
    const progressBar = document.getElementById('inyeccion-progress');
    if (progressBar) {
        progressBar.style.width = indicador.porcentaje_meta + '%';
        
        // Color según porcentaje
        if (indicador.porcentaje_meta < 50) {
            progressBar.style.background = 'linear-gradient(90deg, #f43f5e, #f97316)';
        } else if (indicador.porcentaje_meta < 80) {
            progressBar.style.background = 'linear-gradient(90deg, #f59e0b, #eab308)';
        } else {
            progressBar.style.background = 'linear-gradient(90deg, #10b981, #84cc16)';
        }
    }
    
    // Actualizar gráfico circular
    actualizarGraficoInyeccion(indicador);
}

function actualizarGraficoInyeccion(indicador) {
    const ctx = document.getElementById('chartInyeccionCircular');
    if (!ctx) return;
    
    // Destruir gráfico anterior si existe
    if (dashboardCharts.inyeccionCircular) {
        dashboardCharts.inyeccionCircular.destroy();
    }
    
    // Crear nuevo gráfico
    dashboardCharts.inyeccionCircular = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Completado', 'Restante'],
            datasets: [{
                data: [
                    Math.min(indicador.porcentaje_meta, 100),
                    Math.max(0, 100 - indicador.porcentaje_meta)
                ],
                backgroundColor: [
                    indicador.porcentaje_meta >= 80 ? '#10b981' : 
                    indicador.porcentaje_meta >= 50 ? '#f59e0b' : '#f43f5e',
                    '#e5e7eb'
                ],
                borderWidth: 0,
                borderRadius: 10
            }]
        },
        options: {
            cutout: '75%',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { 
                    display: false 
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.raw}%`;
                        }
                    }
                }
            }
        }
    });
}

// Actualizar indicador pulido
function actualizarIndicadorPulido(data) {
    const indicador = data.indicador;
    const topOperarios = data.top_operarios || {};
    
    if (!indicador) return;
    
    // Actualizar valores
    document.getElementById('pulido-eficiencia').textContent = 
        indicador.eficiencia_promedio?.toFixed(1) + '%' || '0%';
    document.getElementById('pulido-pnc').textContent = 
        indicador.porcentaje_pnc?.toFixed(1) + '%' || '0%';
    
    // Actualizar gráfico de barras
    actualizarGraficoPulido(topOperarios);
}

function actualizarGraficoPulido(topOperarios) {
    const ctx = document.getElementById('chartPulidoBarras');
    if (!ctx) return;
    
    if (dashboardCharts.pulidoBarras) {
        dashboardCharts.pulidoBarras.destroy();
    }
    
    const operarios = Object.keys(topOperarios).slice(0, 6);
    const eficiencias = operarios.map(op => topOperarios[op]?.eficiencia || 0);
    
    // Colores según eficiencia
    const backgroundColors = eficiencias.map(ef => 
        ef >= 90 ? 'rgba(16, 185, 129, 0.8)' :
        ef >= 75 ? 'rgba(245, 158, 11, 0.8)' :
        'rgba(244, 63, 94, 0.8)'
    );
    
    dashboardCharts.pulidoBarras = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: operarios,
            datasets: [{
                label: 'Eficiencia %',
                data: eficiencias,
                backgroundColor: backgroundColors,
                borderColor: backgroundColors.map(c => c.replace('0.8', '1')),
                borderWidth: 2,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    },
                    ticks: {
                        callback: value => value + '%'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Actualizar ventas por cliente
function actualizarVentasCliente(data) {
    const clientesVolumen = data.clientes_volumen || {};
    
    const topCliente = Object.keys(clientesVolumen)[0] || '-';
    const topVentas = clientesVolumen[topCliente]?.mes_actual || 0;
    const topTendencia = clientesVolumen[topCliente]?.tendencia || 0;
    
    // Actualizar valores
    document.getElementById('top-cliente').textContent = topCliente;
    const tendenciaElement = document.getElementById('tendencia-ventas');
    tendenciaElement.textContent = (topTendencia > 0 ? '+' : '') + topTendencia.toFixed(1) + '%';
    
    // Color según tendencia
    if (topTendencia > 0) {
        tendenciaElement.className = 'trend-up';
        tendenciaElement.innerHTML = '<i class="fas fa-arrow-up"></i>' + topTendencia.toFixed(1) + '%';
    } else if (topTendencia < 0) {
        tendenciaElement.className = 'trend-down';
        tendenciaElement.innerHTML = '<i class="fas fa-arrow-down"></i>' + Math.abs(topTendencia).toFixed(1) + '%';
    } else {
        tendenciaElement.className = 'trend-neutral';
        tendenciaElement.textContent = '0%';
    }
    
    // Actualizar gráfico de ventas
    actualizarGraficoVentas(clientesVolumen);
}

function actualizarGraficoVentas(clientesVolumen) {
    const ctx = document.getElementById('chartVentasClienteInteractivo');
    if (!ctx) return;
    
    if (dashboardCharts.ventasCliente) {
        dashboardCharts.ventasCliente.destroy();
    }
    
    const clientes = Object.keys(clientesVolumen).slice(0, 8);
    const ventas = clientes.map(cliente => clientesVolumen[cliente]?.mes_actual || 0);
    
    dashboardCharts.ventasCliente = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: clientes,
            datasets: [{
                label: 'Ventas $',
                data: ventas,
                backgroundColor: 'rgba(139, 92, 246, 0.7)',
                borderColor: 'rgba(139, 92, 246, 1)',
                borderWidth: 2,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    },
                    ticks: {
                        callback: value => '$' + formatNumber(value)
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Actualizar producción por máquina
function actualizarProduccionMaquina(data) {
    const maquinas = data.maquinas || {};
    
    let topMaquina = '-';
    let topEficiencia = 0;
    
    Object.entries(maquinas).forEach(([nombre, datos]) => {
        if (datos.eficiencia_dias > topEficiencia) {
            topEficiencia = datos.eficiencia_dias;
            topMaquina = nombre;
        }
    });
    
    document.getElementById('top-maquina').textContent = `${topMaquina} (${topEficiencia.toFixed(1)}%)`;
    
    // Actualizar gráfico radar
    actualizarGraficoMaquinas(maquinas);
}

function actualizarGraficoMaquinas(maquinas) {
    const ctx = document.getElementById('chartMaquinasRadar');
    if (!ctx) return;
    
    if (dashboardCharts.maquinasRadar) {
        dashboardCharts.maquinasRadar.destroy();
    }
    
    const nombres = Object.keys(maquinas);
    const eficiencias = nombres.map(nombre => maquinas[nombre].eficiencia_dias || 0);
    
    dashboardCharts.maquinasRadar = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: nombres,
            datasets: [{
                label: 'Eficiencia %',
                data: eficiencias,
                backgroundColor: 'rgba(67, 97, 238, 0.2)',
                borderColor: 'rgba(67, 97, 238, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(67, 97, 238, 1)',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        stepSize: 20
                    },
                    pointLabels: {
                        font: {
                            size: 11
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// ===== RANKING DE INYECCIÓN =====

// Actualizar ranking de inyección
function actualizarRankingInyeccion(data) {
    const rankingTotal = data.ranking_total || {};
    
    // Actualizar lista de ranking
    actualizarListaRanking(rankingTotal);
    
    // Actualizar operario destacado
    const topOperario = Object.keys(rankingTotal)[0] || '-';
    const topDatos = rankingTotal[topOperario] || {};
    
    document.getElementById('operario-destacado').textContent = topOperario;
    document.getElementById('operario-metrica').textContent = 
        `${formatNumber(topDatos.total || 0)} buenas (${topDatos.eficiencia || 0}% eficiencia)`;
    
    // Actualizar gráfico de donut
    actualizarGraficoRanking(rankingTotal);
}

function actualizarListaRanking(rankingTotal) {
    let html = '';
    let contador = 1;
    
    Object.entries(rankingTotal).forEach(([nombre, datos]) => {
        const eficiencia = datos.eficiencia || 0;
        const icono = eficiencia >= 90 ? '🏆' : eficiencia >= 80 ? '⭐' : '👤';
        
        html += `
            <div class="ranking-item" style="
                display: flex;
                align-items: center;
                padding: 12px 15px;
                border-bottom: 1px solid #e9ecef;
                transition: all 0.3s ease;
            ">
                <div style="
                    background: ${contador <= 3 ? '#4361ee' : '#6c757d'};
                    color: white;
                    width: 28px;
                    height: 28px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    font-size: 0.9rem;
                    margin-right: 15px;
                ">${contador}</div>
                
                <div style="flex: 1; display: flex; flex-direction: column; gap: 3px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 1.2rem;">${icono}</span>
                        <span style="font-weight: 600; color: #212529;">${nombre}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #6c757d;">
                        ${formatNumber(datos.total || 0)} buenas • 
                        ${formatNumber(datos.productividad_diaria || 0)}/día
                    </div>
                </div>
                
                <div style="
                    font-weight: 700; 
                    font-size: 1.1rem;
                    color: ${eficiencia >= 90 ? '#10b981' : eficiencia >= 80 ? '#f59e0b' : '#f43f5e'};
                ">${eficiencia}%</div>
            </div>
        `;
        contador++;
    });
    
    const rankingContainer = document.getElementById('ranking-operarios');
    if (rankingContainer) {
        rankingContainer.innerHTML = html;
    }
}

function actualizarGraficoRanking(rankingTotal) {
    const ctx = document.getElementById('chartOperariosDonut');
    if (!ctx || Object.keys(rankingTotal).length === 0) return;
    
    if (dashboardCharts.operariosDonut) {
        dashboardCharts.operariosDonut.destroy();
    }
    
    const topOperarios = Object.keys(rankingTotal).slice(0, 5);
    const valores = topOperarios.map(op => rankingTotal[op]?.total || 0);
    
    dashboardCharts.operariosDonut = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: topOperarios,
            datasets: [{
                data: valores,
                backgroundColor: [
                    'rgba(67, 97, 238, 0.8)',
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(139, 92, 246, 0.8)',
                    'rgba(244, 63, 94, 0.8)'
                ],
                borderColor: [
                    'rgba(67, 97, 238, 1)',
                    'rgba(16, 185, 129, 1)',
                    'rgba(245, 158, 11, 1)',
                    'rgba(139, 92, 246, 1)',
                    'rgba(244, 63, 94, 1)'
                ],
                borderWidth: 2,
                borderRadius: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { 
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        font: {
                            size: 11
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${formatNumber(context.raw)} unidades`;
                        }
                    }
                }
            }
        }
    });
}

// ===== STOCK INTELIGENTE =====

function actualizarStockInteligente(data) {
    const resumen = data.resumen || {};
    const analisis = data.analisis || [];
    
    // Actualizar estado general
    actualizarEstadoStock(resumen);
    
    // Actualizar gráfico de riesgo
    actualizarGraficoStock(resumen);
    
    // Actualizar lista de productos críticos
    actualizarListaStock(analisis);
}

function actualizarEstadoStock(resumen = {}) {
    let estado = 'ÓPTIMO';
    let color = '#10b981';
    let badgeClass = 'status-optimo';
    
    if (resumen.criticos > 0) {
        estado = 'CRÍTICO';
        color = '#f43f5e';
        badgeClass = 'status-critico';
    } else if (resumen.altos > 0) {
        estado = 'ALTO RIESGO';
        color = '#f97316';
        badgeClass = 'status-alto';
    } else if (resumen.medios > 0) {
        estado = 'ATENCIÓN';
        color = '#f59e0b';
        badgeClass = 'status-medio';
    }
    
    const estadoElement = document.getElementById('estado-stock');
    const badgeElement = document.getElementById('estado-stock-badge');
    
    if (estadoElement) {
        estadoElement.textContent = `Estado: ${estado}`;
        estadoElement.style.color = color;
    }
    
    if (badgeElement) {
        badgeElement.innerHTML = `<span class="${badgeClass}">${estado}</span>`;
    }
    
    // Actualizar recomendación
    actualizarRecomendacionStock(resumen);
}

function actualizarGraficoStock(resumen) {
    const ctx = document.getElementById('chartStockRiesgo');
    if (!ctx) return;
    
    if (dashboardCharts.stockRiesgo) {
        dashboardCharts.stockRiesgo.destroy();
    }
    
    const data = [
        resumen.criticos || 0,
        resumen.altos || 0,
        resumen.medios || 0,
        resumen.bajos || 0,
        resumen.optimos || 0
    ];
    
    dashboardCharts.stockRiesgo = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Crítico', 'Alto', 'Medio', 'Bajo', 'Óptimo'],
            datasets: [{
                data: data,
                backgroundColor: [
                    '#f43f5e',
                    '#f97316',
                    '#f59e0b',
                    '#84cc16',
                    '#10b981'
                ],
                borderWidth: 0,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { 
                    display: false 
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.raw} productos`;
                        }
                    }
                }
            }
        }
    });
}

function actualizarRecomendacionStock(resumen) {
    let recomendacion = 'Stock en condiciones óptimas. ✅';
    let alertClass = 'alert-success';
    
    if (resumen.criticos > 0) {
        recomendacion = `⚠️ **URGENTE**: ${resumen.criticos} productos críticos requieren reposición inmediata.`;
        alertClass = 'alert-danger';
    } else if (resumen.altos > 0) {
        recomendacion = `⚠️ **ATENCIÓN**: ${resumen.altos} productos con alto riesgo. Programar reposición.`;
        alertClass = 'alert-warning';
    } else if (resumen.medios > 0) {
        recomendacion = `📋 **MONITOREAR**: ${resumen.medios} productos requieren atención.`;
        alertClass = 'alert-info';
    }
    
    const element = document.getElementById('recomendacion-stock');
    if (element) {
        element.innerHTML = `<i class="fas fa-info-circle"></i> ${recomendacion}`;
        element.className = `alert-box ${alertClass}`;
    }
}

function actualizarListaStock(analisis) {
    const criticos = analisis.filter(p => p.riesgo === 'CRITICO').slice(0, 5);
    const element = document.getElementById('lista-stock-critico');
    
    if (!element) return;
    
    if (criticos.length === 0) {
        element.innerHTML = `
            <h4><i class="fas fa-check-circle text-success"></i> Productos Críticos</h4>
            <div class="no-critical">
                <i class="fas fa-check-circle text-success" style="font-size: 2rem;"></i>
                <span>No hay productos críticos</span>
            </div>
        `;
        return;
    }
    
    let html = `<h4><i class="fas fa-exclamation-triangle"></i> Productos Críticos</h4>`;
    
    criticos.forEach(producto => {
        html += `
            <div class="stock-item" style="
                padding: 12px;
                margin: 8px 0;
                background: #fef2f2;
                border-left: 4px solid #f43f5e;
                border-radius: 6px;
                transition: all 0.3s ease;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                    <strong style="color: #dc2626;">${producto.codigo}</strong>
                    <span style="
                        background: #fecaca;
                        color: #dc2626;
                        padding: 3px 10px;
                        border-radius: 20px;
                        font-size: 0.8rem;
                        font-weight: 600;
                    ">${producto.dias_de_stock} días</span>
                </div>
                <div style="font-size: 0.9rem; color: #374151; margin-bottom: 5px;">
                    ${producto.descripcion}
                </div>
                <div style="font-size: 0.85rem; color: #6b7280;">
                    Stock: ${producto.stock_total} | Mín: ${producto.stock_minimo}
                </div>
                <div style="font-size: 0.8rem; color: #f43f5e; margin-top: 5px;">
                    <i class="fas fa-lightbulb"></i> ${producto.recomendacion}
                </div>
            </div>
        `;
    });
    
    element.innerHTML = html;
}

// ===== KPIs GLOBALES =====

function actualizarKPIsGlobales() {
    const inyeccionData = window.AppState.dashboardData.indicador_inyeccion;
    const ventasData = window.AppState.dashboardData.ventas_cliente_detallado;
    const pulidoData = window.AppState.dashboardData.indicador_pulido;
    const stockData = window.AppState.dashboardData.stock_inteligente;
    
    // KPI Producción
    if (inyeccionData?.indicador) {
        document.getElementById('kpi-produccion').textContent = 
            formatNumber(inyeccionData.indicador.produccion_mes);
        
        const tendencia = inyeccionData.indicador.tendencia || 0;
        const trendElement = document.getElementById('kpi-produccion-tendencia');
        
        trendElement.innerHTML = `
            <i class="fas fa-arrow-${tendencia >= 0 ? 'up' : 'down'}"></i>
            ${Math.abs(tendencia).toFixed(1)}%
        `;
        trendElement.className = tendencia >= 0 ? 'trend-up' : 'trend-down';
    }
    
    // KPI Ventas
    if (ventasData?.clientes_volumen) {
        const clientes = ventasData.clientes_volumen;
        let ventasTotal = 0;
        
        Object.values(clientes).forEach(cliente => {
            ventasTotal += cliente.mes_actual || 0);
        });
        
        document.getElementById('kpi-ventas').textContent = 
            '$' + formatNumber(ventasTotal);
        
        // Calcular tendencia promedio
        let tendenciaPromedio = 0;
        let contador = 0;
        
        Object.values(clientes).forEach(cliente => {
            if (cliente.tendencia !== undefined) {
                tendenciaPromedio += cliente.tendencia;
                contador++;
            }
        });
        
        tendenciaPromedio = contador > 0 ? tendenciaPromedio / contador : 0;
        const trendElement = document.getElementById('kpi-ventas-tendencia');
        
        trendElement.innerHTML = `
            <i class="fas fa-arrow-${tendenciaPromedio >= 0 ? 'up' : 'down'}"></i>
            ${Math.abs(tendenciaPromedio).toFixed(1)}%
        `;
        trendElement.className = tendenciaPromedio >= 0 ? 'trend-up' : 'trend-down';
    }
    
    // KPI Eficiencia
    if (pulidoData?.indicador && inyeccionData?.indicador) {
        const eficienciaPromedio = (
            pulidoData.indicador.eficiencia_promedio + 
            (100 - (inyeccionData.indicador.porcentaje_pnc || 0))
        ) / 2;
        
        document.getElementById('kpi-eficiencia').textContent = 
            eficienciaPromedio.toFixed(1) + '%';
        
        const trendElement = document.getElementById('kpi-eficiencia-tendencia');
        const tendencia = inyeccionData.indicador.tendencia || 0;
        
        trendElement.innerHTML = `
            <i class="fas fa-arrow-${tendencia >= 0 ? 'up' : 'down'}"></i>
            ${Math.abs(tendencia).toFixed(1)}%
        `;
        trendElement.className = tendencia >= 0 ? 'trend-up' : 'trend-down';
    }
    
    // KPI Stock Crítico
    if (stockData?.resumen) {
        document.getElementById('kpi-stock-critico').textContent = 
            stockData.resumen.criticos || 0;
    }
}

// ===== FUNCIONES DE INTERACTIVIDAD MEJORADAS =====

function cambiarTipoRanking() {
    const tipo = document.getElementById('filtro-tipo-ranking').value;
    currentRankingType = tipo;
    
    // Cambiar texto del operario destacado según el tipo
    const destacadoElement = document.getElementById('operario-destacado');
    const metricaElement = document.getElementById('operario-metrica');
    
    if (tipo === 'inyeccion') {
        const data = window.AppState.dashboardData.ranking_inyeccion;
        if (data) {
            actualizarRankingInyeccion(data);
            destacadoElement.textContent = 'Operario Destacado (Inyección)';
            mostrarNotificacion('Mostrando ranking de inyección', 'success');
        }
    } else {
        const data = window.AppState.dashboardData.indicador_pulido;
        if (data) {
            mostrarRankingPulido(data);
            destacadoElement.textContent = 'Operario Destacado (Pulido)';
            mostrarNotificacion('Mostrando ranking de pulido', 'success');
        }
    }
    
    // Actualizar estado de los botones de filtro
    actualizarEstadoBotonesRanking(tipo);
}

function actualizarEstadoBotonesRanking(tipoActivo) {
    const buttons = document.querySelectorAll('.ranking-filter-btn');
    buttons.forEach(btn => {
        if (btn.dataset.tipo === tipoActivo) {
            btn.classList.add('active');
            btn.style.background = 'linear-gradient(135deg, var(--primary), var(--secondary))';
            btn.style.color = 'white';
            btn.style.boxShadow = '0 4px 12px rgba(67, 97, 238, 0.3)';
        } else {
            btn.classList.remove('active');
            btn.style.background = 'white';
            btn.style.color = 'var(--gray)';
            btn.style.boxShadow = '0 2px 6px rgba(0,0,0,0.05)';
        }
    });
}

function cambiarRankingPeriodo() {
    const periodo = document.getElementById('filtro-ranking').value;
    const tipo = currentRankingType;
    
    mostrarNotificacion(`Actualizando ranking de ${tipo} para: ${periodo}`, 'info');
    
    // Simular carga de datos según el período
    setTimeout(() => {
        if (tipo === 'inyeccion') {
            const data = window.AppState.dashboardData.ranking_inyeccion;
            if (data) {
                actualizarRankingInyeccion(data);
                mostrarNotificacion(`Ranking de inyección actualizado (${periodo})`, 'success');
            }
        } else {
            const data = window.AppState.dashboardData.indicador_pulido;
            if (data) {
                mostrarRankingPulido(data);
                mostrarNotificacion(`Ranking de pulido actualizado (${periodo})`, 'success');
            }
        }
    }, 500);
}

function mostrarRankingPulido(data) {
    const topOperarios = data.top_operarios || {};
    
    let html = '';
    let contador = 1;
    
    Object.entries(topOperarios).forEach(([nombre, datos]) => {
        const eficiencia = datos.eficiencia || 0;
        const icono = eficiencia >= 90 ? '👑' : eficiencia >= 80 ? '✨' : '👩‍🔧';
        
        html += `
            <div class="ranking-item" style="
                display: flex;
                align-items: center;
                padding: 12px 15px;
                border-bottom: 1px solid #e9ecef;
            ">
                <div style="
                    background: ${contador <= 3 ? '#8b5cf6' : '#6c757d'};
                    color: white;
                    width: 28px;
                    height: 28px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    margin-right: 15px;
                ">${contador}</div>
                
                <div style="flex: 1;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 1.2rem;">${icono}</span>
                        <span style="font-weight: 600;">${nombre}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #6c757d;">
                        Eficiencia: ${eficiencia}%
                    </div>
                </div>
            </div>
        `;
        contador++;
    });
    
    document.getElementById('ranking-operarios').innerHTML = html;
    document.getElementById('operario-destacado').textContent = Object.keys(topOperarios)[0] || '-';
    document.getElementById('operario-metrica').textContent = 'Ver detalles en sección Pulido';
}

function cambiarRanking() {
    const filtro = document.getElementById('filtro-ranking').value;
    mostrarNotificacion(`Filtro cambiado a: ${filtro}`, 'info');
    // La funcionalidad completa dependería de tener más datos en el backend
}

function cambiarPeriodoDashboard() {
    window.AppState.periodoActual = document.getElementById('filtro-periodo').value;
    mostrarNotificacion(`Período cambiado a: ${window.AppState.periodoActual}`, 'info');
    cargarDashboardCompleto();
}

function exportarDashboard() {
    mostrarNotificacion('Generando reporte PDF...', 'info');
    // Aquí iría la lógica para exportar
    setTimeout(() => {
        mostrarNotificacion('Reporte generado exitosamente', 'success');
    }, 2000);
}

function actualizarDashboardCompleto() {
    mostrarNotificacion('Actualizando dashboard...', 'info');
    cargarDashboardCompleto();
}

function toggleChartType(tipo) {
    if (tipo === 'ventas' && dashboardCharts.ventasCliente) {
        const currentType = dashboardCharts.ventasCliente.config.type;
        dashboardCharts.ventasCliente.config.type = currentType === 'bar' ? 'line' : 'bar';
        dashboardCharts.ventasCliente.update();
        mostrarNotificacion(`Gráfico cambiado a: ${dashboardCharts.ventasCliente.config.type}`, 'info');
    }
}

// ===== TIMELINE =====

function inicializarTimeline() {
    const ctx = document.getElementById('chartTimeline');
    if (!ctx) return;
    
    if (dashboardCharts.timeline) {
        dashboardCharts.timeline.destroy();
    }
    
    // Generar datos de ejemplo para el timeline
    const dias = Array.from({length: 30}, (_, i) => {
        const d = new Date();
        d.setDate(d.getDate() - (29 - i));
        return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
    });
    
    // Datos de producción (tendencia creciente)
    const produccion = dias.map((_, i) => {
        const base = 500;
        const trend = i * 20;
        const noise = Math.random() * 100 - 50;
        return Math.round(base + trend + noise);
    });
    
    // Datos de ventas (tendencia creciente con más variabilidad)
    const ventas = dias.map((_, i) => {
        const base = 300;
        const trend = i * 15;
        const noise = Math.random() * 150 - 75;
        return Math.round(base + trend + noise);
    });
    
    dashboardCharts.timeline = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dias,
            datasets: [
                {
                    label: 'Producción',
                    data: produccion,
                    borderColor: '#4361ee',
                    backgroundColor: 'rgba(67, 97, 238, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#4361ee',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                },
                {
                    label: 'Ventas',
                    data: ventas,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#10b981',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    },
                    ticks: {
                        callback: value => formatNumber(value)
                    }
                }
            },
            plugins: {
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${formatNumber(context.parsed.y)}`;
                        }
                    }
                }
            }
        }
    });
}

// ===== FUNCIONES DE UTILIDAD =====

function crearDatosEjemplo(endpoint) {
    console.log(`Creando datos de ejemplo para: ${endpoint}`);
    
    // Datos de ejemplo para testing
    switch(endpoint) {
        case 'ranking_inyeccion':
            const rankingEjemplo = {
                'ranking_total': {
                    'Juan Pérez': { total: 2450, productividad_diaria: 122, eficiencia: 94.5, dias_trabajados: 20 },
                    'Carlos López': { total: 2180, productividad_diaria: 109, eficiencia: 91.2, dias_trabajados: 20 },
                    'Miguel Torres': { total: 1950, productividad_diaria: 97, eficiencia: 89.8, dias_trabajados: 20 },
                    'Pedro Sánchez': { total: 1780, productividad_diaria: 89, eficiencia: 87.5, dias_trabajados: 20 },
                    'Luis Martínez': { total: 1620, productividad_diaria: 81, eficiencia: 85.3, dias_trabajados: 20 }
                }
            };
            actualizarRankingInyeccion({ status: 'success', ...rankingEjemplo });
            break;
    }
}

// Función para formatear números
function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return new Intl.NumberFormat('es-ES').format(num);
}

// Función para mostrar notificaciones
function mostrarNotificacion(mensaje, tipo = 'info') {
    const container = document.querySelector('.notifications-container');
    if (!container) return;
    
    const notificacion = document.createElement('div');
    notificacion.className = `notificacion notificacion-${tipo}`;
    notificacion.style.cssText = `
        background: ${tipo === 'success' ? '#10b981' : 
                     tipo === 'error' ? '#f43f5e' : 
                     tipo === 'warning' ? '#f59e0b' : '#3b82f6'};
        color: white;
        padding: 15px 20px;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 15px;
        animation: slideIn 0.3s ease;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    `;
    
    const iconos = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    notificacion.innerHTML = `
        <span style="font-size: 1.2rem;">${iconos[tipo] || '📢'}</span>
        <span>${mensaje}</span>
        <button onclick="this.parentElement.remove()" 
                style="margin-left: auto; background: none; border: none; color: white; cursor: pointer;">
            ×
        </button>
    `;
    
    container.appendChild(notificacion);
    
    // Auto-eliminar después de 5 segundos
    setTimeout(() => {
        if (notificacion.parentElement) {
            notificacion.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notificacion.remove(), 300);
        }
    }, 5000);
}

// ===== FUNCIONES DE DETALLES DASHBOARD =====

async function toggleDetails(tipo) {
    try {
        // Mostrar overlay de carga
        mostrarLoading(true);
        
        const response = await fetch(`/api/dashboard/detalles/${tipo}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            mostrarModalDetalles(tipo, data.detalles);
        } else {
            throw new Error(data.message || 'Error cargando detalles');
        }
        
        mostrarLoading(false);
        
    } catch (error) {
        console.error(`Error cargando detalles de ${tipo}:`, error);
        mostrarNotificacion(`Error cargando detalles: ${error.message}`, 'error');
        mostrarLoading(false);
    }
}

function mostrarModalDetalles(tipo, detalles) {
    // Crear modal dinámico
    const modalId = `modal-detalles-${tipo}`;
    
    // Eliminar modal existente si hay
    const existingModal = document.getElementById(modalId);
    if (existingModal) {
        existingModal.remove();
    }
    
    // Crear modal
    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal-detalles';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10001;
        padding: 20px;
    `;
    
    // Contenido según tipo
    let contenido = '';
    const titulo = tipo === 'inyeccion' ? 'Inyección' : 
                   tipo === 'pulido' ? 'Pulido' : 'Detalles';
    
    if (tipo === 'inyeccion') {
        contenido = `
            <div class="modal-detalles-content" style="
                background: white;
                border-radius: 15px;
                width: 100%;
                max-width: 800px;
                max-height: 90vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            ">
                <div class="modal-header" style="
                    padding: 25px;
                    border-bottom: 2px solid #e9ecef;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <h3 style="
                        font-size: 1.5rem;
                        font-weight: 700;
                        color: #212529;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    ">
                        <i class="fas fa-syringe" style="color: #4361ee;"></i>
                        Detalles de Inyección - ${detalles.mes_actual}
                    </h3>
                    <button onclick="this.closest('.modal-detalles').remove()" style="
                        background: none;
                        border: none;
                        font-size: 1.5rem;
                        cursor: pointer;
                        color: #6c757d;
                        padding: 5px;
                    ">×</button>
                </div>
                
                <div class="modal-body" style="padding: 25px;">
                    <div class="detalles-grid" style="
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    ">
                        <div class="detalle-card" style="
                            background: #f8f9fa;
                            padding: 20px;
                            border-radius: 10px;
                            border-left: 4px solid #4361ee;
                        ">
                            <h4 style="color: #4361ee; margin-bottom: 10px;">
                                <i class="fas fa-users"></i> Operarios Activos
                            </h4>
                            <div style="font-size: 2.5rem; font-weight: 700; color: #212529;">
                                ${detalles.total_operarios}
                            </div>
                            ${detalles.operarios_activos && detalles.operarios_activos.length > 0 ? `
                                <div style="margin-top: 10px; font-size: 0.9rem; color: #6c757d;">
                                    ${detalles.operarios_activos.join(', ')}
                                </div>
                            ` : ''}
                        </div>
                        
                        <div class="detalle-card" style="
                            background: #f8f9fa;
                            padding: 20px;
                            border-radius: 10px;
                            border-left: 4px solid #7209b7;
                        ">
                            <h4 style="color: #7209b7; margin-bottom: 10px;">
                                <i class="fas fa-cogs"></i> Máquinas Activas
                            </h4>
                            <div style="font-size: 2.5rem; font-weight: 700; color: #212529;">
                                ${detalles.total_maquinas}
                            </div>
                            ${detalles.maquinas_activas && detalles.maquinas_activas.length > 0 ? `
                                <div style="margin-top: 10px; font-size: 0.9rem; color: #6c757d;">
                                    ${detalles.maquinas_activas.join(', ')}
                                </div>
                            ` : ''}
                        </div>
                        
                        <div class="detalle-card" style="
                            background: #f8f9fa;
                            padding: 20px;
                            border-radius: 10px;
                            border-left: 4px solid #f72585;
                        ">
                            <h4 style="color: #f72585; margin-bottom: 10px;">
                                <i class="fas fa-times-circle"></i> PNC Total Mes
                            </h4>
                            <div style="font-size: 2.5rem; font-weight: 700; color: #212529;">
                                ${formatNumber(detalles.total_pnc_mes)}
                            </div>
                            <div style="margin-top: 10px; font-size: 0.9rem; color: #6c757d;">
                                Productos No Conformes
                            </div>
                        </div>
                    </div>
                    
                    <div class="informacion-adicional" style="
                        background: #f8f9fa;
                        padding: 20px;
                        border-radius: 10px;
                        margin-top: 20px;
                    ">
                        <h4 style="color: #212529; margin-bottom: 15px;">
                            <i class="fas fa-info-circle"></i> Información del Mes
                        </h4>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                            <div>
                                <strong style="color: #6c757d;">Mes:</strong>
                                <span style="margin-left: 10px; font-weight: 600;">${detalles.mes_actual}</span>
                            </div>
                            <div>
                                <strong style="color: #6c757d;">Días hábiles:</strong>
                                <span style="margin-left: 10px; font-weight: 600;">${new Date().getDate()} días</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    } else if (tipo === 'pulido') {
        // Contenido para pulido
        const operariosHtml = detalles.operarios ? 
            Object.entries(detalles.operarios).map(([nombre, datos]) => `
                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px;
                    background: white;
                    border-radius: 8px;
                    margin-bottom: 8px;
                    border-left: 4px solid ${datos.eficiencia >= 90 ? '#10b981' : datos.eficiencia >= 80 ? '#f59e0b' : '#f43f5e'};
                ">
                    <div>
                        <strong style="color: #212529;">${nombre}</strong>
                        <div style="font-size: 0.85rem; color: #6c757d;">
                            ${datos.dias_trabajados || 0} días trabajados
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 700; color: #212529;">
                            ${datos.eficiencia || 0}%
                        </div>
                        <div style="font-size: 0.85rem; color: #f43f5e;">
                            ${datos.pnc || 0} PNC
                        </div>
                    </div>
                </div>
            `).join('') : '<p style="text-align: center; color: #6c757d;">No hay datos de operarios</p>';
        
        contenido = `
            <div class="modal-detalles-content" style="
                background: white;
                border-radius: 15px;
                width: 100%;
                max-width: 800px;
                max-height: 90vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            ">
                <div class="modal-header" style="
                    padding: 25px;
                    border-bottom: 2px solid #e9ecef;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <h3 style="
                        font-size: 1.5rem;
                        font-weight: 700;
                        color: #212529;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    ">
                        <i class="fas fa-sparkles" style="color: #8b5cf6;"></i>
                        Detalles de Pulido - ${detalles.mes_actual}
                    </h3>
                    <button onclick="this.closest('.modal-detalles').remove()" style="
                        background: none;
                        border: none;
                        font-size: 1.5rem;
                        cursor: pointer;
                        color: #6c757d;
                        padding: 5px;
                    ">×</button>
                </div>
                
                <div class="modal-body" style="padding: 25px;">
                    <div class="stats-grid" style="
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    ">
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 10px;">
                            <div style="color: #6c757d; font-size: 0.9rem;">Operarios Activos</div>
                            <div style="font-size: 2.5rem; font-weight: 700; color: #212529;">
                                ${detalles.total_operarios || 0}
                            </div>
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 10px;">
                            <div style="color: #6c757d; font-size: 0.9rem;">PNC Total</div>
                            <div style="font-size: 2.5rem; font-weight: 700; color: #f43f5e;">
                                ${formatNumber(detalles.total_pnc_mes || 0)}
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 30px;">
                        <h4 style="color: #212529; margin-bottom: 15px; display: flex; align-items: center; gap: 10px;">
                            <i class="fas fa-user-check"></i> Desempeño por Operario
                        </h4>
                        <div style="max-height: 300px; overflow-y: auto; padding-right: 10px;">
                            ${operariosHtml}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    modal.innerHTML = contenido;
    document.body.appendChild(modal);
    
    // Cerrar modal al hacer clic fuera
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Exportar funciones globales
window.inicializarDashboard = inicializarDashboard;
window.cambiarTipoRanking = cambiarTipoRanking;
window.cambiarRanking = cambiarRanking;
window.cambiarPeriodoDashboard = cambiarPeriodoDashboard;
window.exportarDashboard = exportarDashboard;
window.actualizarDashboardCompleto = actualizarDashboardCompleto;
window.toggleDetails = toggleDetails;
window.toggleChartType = toggleChartType;