window.ModuloDashboard = (function () {
    let chartOperadores = null;
    let chartMaquinas = null;
    let chartTendencia = null;
    let chartPNC = null;
    let selectedOperators = []; // Para comparativa cara a cara

    let chartPulidoBoard = null;
    let chartMensualInst = null;
    let inc_unidades_original = [];
    let inc_dinero_original = [];
    let chartTopMejoresInst = null;
    let chartTopPeoresInst = null;
    let lastJefaturaData = null;
    let inc_consolidado_original = [];
    let currentIncSortMode = 'units'; // 'units' or 'money'
    let searchListenerAttached = false;
    let isInitialized = false;
    let isFetching = false;
    let tableRowCache = {}; // Cache para búsquedas ultra-rápidas

    // Helper: Debounce function for performance
    const debounce = (func, wait) => {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    };

    const colores = {
        azul: ['rgba(59, 130, 246, 0.8)', 'rgba(96, 165, 250, 0.8)', 'rgba(147, 197, 253, 0.8)'],
        verde: ['#10b981', '#34d399', '#6ee7b7'],
        naranja: ['#f59e0b', '#fbbf24', '#fcd34d'],
        peligro: ['#ef4444', '#f87171', '#fca5a5']
    };

    let currentInsights = [];
    let insightIndex = 0;
    let insightInterval = null;

    // --- Loading overlay helper ---
    function showLoading(show) {
        let overlay = document.getElementById('db-loading-overlay');
        if (!overlay && show) {
            overlay = document.createElement('div');
            overlay.id = 'db-loading-overlay';
            overlay.innerHTML = `
                <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(255,255,255,0.7);
                    z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px);">
                    <div style="text-align:center;padding:2rem;">
                        <i class="fas fa-sync-alt fa-spin" style="font-size:2.5rem;color:#3b82f6;"></i>
                        <p style="margin-top:1rem;font-weight:600;color:#334155;">Cargando datos de Sheets...</p>
                        <p style="font-size:0.8rem;color:#94a3b8;">La primera carga puede tardar unos segundos</p>
                    </div>
                </div>`;
            document.body.appendChild(overlay);
        }
        if (overlay) overlay.style.display = show ? 'block' : 'none';
    }

    async function cargarDatos(nocache = false) {
        if (isFetching) {
            console.warn("⏳ Petición cargarDatos en curso, ignorando duplicada.");
            return;
        }

        try {
            isFetching = true;
            showLoading(true);
            console.log("📡 Cargando datos del dashboard...");
            const desde = document.getElementById('db-fecha-desde')?.value;
            const hasta = document.getElementById('db-fecha-hasta')?.value;

            let url = '/api/dashboard/stats';
            const params = new URLSearchParams();
            if (desde) params.append('desde', desde);
            if (hasta) params.append('hasta', hasta);
            if (nocache) params.append('nocache', '1');
            if (params.toString()) url += `?${params.toString()}`;

            const responseStats = fetch(url).then(res => res.json());

            // RBAC: Solo cargar datos de Jefatura / Finanzas si es Admin, Gerencia o Comercial
            let isAdminOrManagement = false;
            let resultJefatura = null;

            if (window.AppState && window.AppState.user && window.AppState.user.rol) {
                const rol = window.AppState.user.rol.toUpperCase();
                isAdminOrManagement = ['ADMINISTRACION', 'ADMINISTRACIÓN', 'ADMINISTRADOR', 'GERENCIA', 'COMERCIAL'].includes(rol);
            }

            if (isAdminOrManagement) {
                const adminParams = new URLSearchParams();
                if (desde) adminParams.append('start', desde);
                if (hasta) adminParams.append('end', hasta);
                if (nocache) adminParams.append('nocache', '1');

                // Timeout de 30s para evitar que la página se congele
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000);

                const jefUrl = `/api/admin/dashboard?${adminParams.toString()}`;
                console.log("📡 Consultando Jefatura:", jefUrl);

                try {
                    const reqJefatura = fetch(jefUrl, {
                        headers: { 'Accept': 'application/json' },
                        signal: controller.signal
                    }).then(res => res.json());

                    const [result, jefaturaData] = await Promise.all([responseStats, reqJefatura]);
                    clearTimeout(timeoutId);
                    console.log("📊 Datos recibidos (Admin):", { result, jefaturaData });

                    if (result && result.status === 'success') {
                        renderizarTodo(result.data, jefaturaData);
                    }
                } catch (fetchErr) {
                    clearTimeout(timeoutId);
                    if (fetchErr.name === 'AbortError') {
                        console.warn("⏰ Timeout en /api/admin/dashboard - mostrando stats sin datos de Jefatura");
                        const result = await responseStats;
                        if (result && result.status === 'success') {
                            renderizarTodo(result.data, null);
                        }
                    } else {
                        throw fetchErr;
                    }
                }
            } else {
                const result = await responseStats;
                if (result && result.status === 'success') {
                    renderizarTodo(result.data, null);
                }
            }

            // Initialize Bootstrap tooltips if they exist
            const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

        } catch (error) {
            console.error("Error en Dashboard BI / Jefatura:", error);
        } finally {
            isFetching = false;
            showLoading(false);
        }
    }

    function renderizarTodo(data, jefaturaData) {
        console.log("🚀 Iniciando renderizado de componentes...", { data, jefaturaData });

        // Limpiar cache de filas al renderizar datos nuevos
        tableRowCache = {};

        if (!data || !data.kpis) {
            console.error("❌ Error: Estructura de datos inválida para renderizarTodo. Faltan KPIs.", data);
            // Intentamos seguir si al menos hay datos de Jefatura (para que no quede todo negro)
            if (!jefaturaData) return;
        }

        const safeSetText = (id, text) => {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
            else console.warn(`⚠️ Elemento no encontrado: ${id}`);
        };

        try {
            // 1. KPIs Principales
            safeSetText('total-iny-piezas', `${(data.kpis.inyeccion_ok || 0).toLocaleString()} Pz`);

            const formatCOP_PNC = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(data.kpis.perdida_calidad_dinero || 0);
            safeSetText('perdida-calidad-global', formatCOP_PNC);

            safeSetText('pnc-global-val', (data.kpis.scrap_total || 0).toLocaleString());

            // 2. Insights IA Avanzados
            let smartInsights = [];

            // Insight Basico Fechas
            smartInsights.push(`Analizando datos clave de producción y ventas: <strong>${data.rango?.desde || ''}</strong> al <strong>${data.rango?.hasta || ''}</strong>.`);

            if (jefaturaData && jefaturaData.data) {
                const jd = jefaturaData.data;
                // Filtrar el peor cliente en incumplimiento
                if (jd.incumplimiento_dinero && jd.incumplimiento_dinero.length > 0) {
                    const topInc = [...jd.incumplimiento_dinero].sort((a, b) => b.dinero_perdido - a.dinero_perdido)[0];
                    if (topInc && topInc.dinero_perdido > 0) {
                        smartInsights.push(`<span class="text-danger"><i class="fas fa-exclamation-circle"></i> <strong>Atención Comercial (Histórico General):</strong></span> El mayor impacto global es con <b>${topInc.cliente}</b> perdiendo <b class="text-danger">${new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(topInc.dinero_perdido)}</b> por faltantes del producto <i>${topInc.producto}</i>.`);
                    }
                }

                // Productos Estrella vs Riesgo
                if (jd.top_productos_dinero && jd.top_productos_dinero.length > 0) {
                    const topVendido = jd.top_productos_dinero[0];
                    smartInsights.push(`<i class="fas fa-star text-warning"></i> <strong>Líder de Ventas (Histórico General):</strong> La referencia <b>${topVendido.producto}</b> lidera los ingresos con <b class="text-success">${new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(topVendido.ventas_dinero)}</b> facturados.`);
                }
            }

            // Insight Calidad (Scrap)
            if (data.kpis.perdida_calidad_dinero > 0) {
                smartInsights.push(`<i class="fas fa-recycle text-secondary"></i> <strong>Alerta de Calidad:</strong> El acumulado de piezas rechazadas representa un costo hundido estimado en <b class="text-danger">${formatCOP_PNC}</b>. Revise los procesos de Pulido e Inyección.`);
            }

            // Avisos de Costos Faltantes
            if (data.kpis.faltan_costos_pnc && data.kpis.faltan_costos_pnc.length > 0) {
                smartInsights.push(`<span class="text-warning"><i class="fas fa-exclamation-triangle"></i> <strong>Faltan Costos:</strong></span> Hay ${data.kpis.faltan_costos_pnc.length} referencias reportando scrap que no tienen costo asignado en DB_COSTOS. La Pérdida por Calidad mostrada es menor a la real.`);
            }

            // Darle formato visual a los insights que vienen del backend (Inyección, Pulido, Cuellos de botella)
            const legacyInsightsFormatted = (data.insights_ia || []).map(text => {
                if (text.includes('Cumplimiento')) return `<i class="fas fa-chart-line text-primary"></i> <strong>Eficiencia:</strong> ${text}`;
                if (text.includes('Cuello de botella')) return `<i class="fas fa-hourglass-half text-warning"></i> <strong>Producción:</strong> ${text}`;
                if (text.includes('Líder de Iny')) return `<i class="fas fa-industry text-info"></i> <strong>Inyección:</strong> ${text}`;
                if (text.includes('Líder de Pul')) return `<i class="fas fa-hand-sparkles text-success"></i> <strong>Pulido:</strong> ${text}`;
                if (text.includes('ritmo de Inyección')) return `<i class="fas fa-sync text-success"></i> <strong>Flujo Óptimo:</strong> ${text}`;
                if (text.includes('Calidad')) return `<i class="fas fa-times-circle text-danger"></i> <strong>Control:</strong> ${text}`;
                return `<i class="fas fa-info-circle text-muted"></i> ${text}`;
            });

            currentInsights = [
                ...smartInsights,
                ...legacyInsightsFormatted
            ];
            iniciarCarrouselBot();

            // 3. Gráficos de Producción
            if (data.rankings?.inyeccion_ops) {
                renderChartInyeccion(data.rankings.inyeccion_ops.slice(0, 10));
                const btnVerTodosIny = document.getElementById('btn-ver-todos-iny');
                if (btnVerTodosIny) {
                    btnVerTodosIny.onclick = () => mostrarModalTodosInyeccion(data.rankings.inyeccion_ops);
                }
            }

            if (data.maquinas) renderChartMaquinas(data.maquinas);
            if (data.tendencia) renderChartTendencia(data.tendencia);
            if (data.kpis.scrap_detalle) renderChartPNC(data.kpis.scrap_detalle);

            // 4. Detalle Scrap Almacén
            renderScrapAlmacenDetalle(data.kpis.scrap_almacen_desglose || []);

            // 5. Tabla Pulido
            renderTablaPulido(data.rankings?.pulido_profundo || []);
            renderChartPulidoLeaderboard(data.rankings?.pulido_profundo || []);

            // 6. Datos de Jefatura
            if (jefaturaData && (jefaturaData.success || jefaturaData.status === 'success') && jefaturaData.data) {
                console.log("📈 Renderizando datos de Jefatura...");
                lastJefaturaData = jefaturaData.data;

                renderChartMensual(lastJefaturaData.mensual, 'money');
                renderChartTopMejores(lastJefaturaData.top_productos_dinero, 'money');
                renderChartTopPeores(lastJefaturaData.peores_productos_dinero, 'money');

                if (lastJefaturaData.incumplimiento_unidades) {
                    inc_unidades_original = lastJefaturaData.incumplimiento_unidades;
                }
                if (lastJefaturaData.incumplimiento_dinero) {
                    inc_dinero_original = lastJefaturaData.incumplimiento_dinero;
                }
                if (lastJefaturaData.incumplimiento_consolidado) {
                    inc_consolidado_original = lastJefaturaData.incumplimiento_consolidado;
                    renderTablaIncumplimientoConsolidada(inc_consolidado_original);
                }
            }
            console.log("✅ Renderizado completado sin errores.");
        } catch (err) {
            console.error("❌ Error crítico durante el renderizado del dashboard:", err);
        }
    }

    function iniciarCarrouselBot() {
        if (insightInterval) clearInterval(insightInterval);

        insightIndex = 0;
        mostrarSiguienteInsight();

        insightInterval = setInterval(mostrarSiguienteInsight, 6000); // Cambiar cada 6 segundos
    }

    function mostrarSiguienteInsight() {
        const container = document.getElementById('dashboard-bot-container');
        const textElement = document.getElementById('dashboard-bot-text');
        if (!container || !textElement || currentInsights.length === 0) return;

        // Efecto de desvanecimiento
        container.style.opacity = "0";

        setTimeout(() => {
            textElement.innerHTML = currentInsights[insightIndex];
            container.style.opacity = "1";

            // Avanzar índice
            insightIndex = (insightIndex + 1) % currentInsights.length;
        }, 500);
    }


    function renderChartInyeccion(ops) {
        const ctx = document.getElementById('chartInyeccionOperadores');
        if (!ctx) return;

        const labels = ops.map(o => o.nombre);
        const dataBuenas = ops.map(o => o.valor);

        // Crear gradientes para un look más "premium"
        const chartCtx = ctx.getContext('2d');
        const gradientGold = chartCtx.createLinearGradient(0, 0, 0, 400);
        gradientGold.addColorStop(0, 'rgba(251, 191, 36, 1)');
        gradientGold.addColorStop(1, 'rgba(217, 119, 6, 0.8)');

        const gradientBlue = chartCtx.createLinearGradient(0, 0, 0, 400);
        gradientBlue.addColorStop(0, 'rgba(59, 130, 246, 1)');
        gradientBlue.addColorStop(1, 'rgba(37, 99, 235, 0.8)');

        const bgColors = dataBuenas.map((val, idx) => idx === 0 ? gradientGold : gradientBlue);
        const borderColors = dataBuenas.map((val, idx) => idx === 0 ? 'rgba(217, 119, 6, 1)' : 'rgba(37, 99, 235, 1)');

        if (chartOperadores) chartOperadores.destroy();

        chartOperadores = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Buenas',
                    data: dataBuenas,
                    backgroundColor: bgColors,
                    borderColor: borderColors,
                    borderWidth: 0,
                    borderRadius: { topLeft: 8, topRight: 8, bottomLeft: 0, bottomRight: 0 },
                    barPercentage: 0.5,
                    categoryPercentage: 0.7
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 1500, easing: 'easeOutQuart' },
                layout: { padding: { top: 20 } },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleFont: { size: 14, weight: 'bold' },
                        bodyFont: { size: 13 },
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            label: (context) => `🎯 ${context.raw.toLocaleString()} Piezas Inyectadas`
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const operador = ops[index].nombre;
                        const valor = ops[index].valor;
                        const mixData = ops[index].mix || [];
                        const detalleMix = mixData.slice(0, 5).map(p => `${p.prod}: ${p.qty.toLocaleString()}`).join('\\n').replace(/'/g, "\\'");
                        const insightText = ops[index].insight || "Sin insights disponibles para Inyección.";
                        mostrarModalOperador(operador, valor, 'Inyección', insightText, detalleMix);
                    }
                },
                onHover: (event, chartElement) => {
                    event.native.target.style.cursor = chartElement[0] ? 'pointer' : 'default';
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(226, 232, 240, 0.5)', drawBorder: false },
                        ticks: { font: { weight: '600' }, color: '#64748b', padding: 10 }
                    },
                    x: {
                        grid: { display: false, drawBorder: false },
                        ticks: { font: { weight: 'bold', size: 11 }, color: '#334155', maxRotation: 25, minRotation: 0 }
                    }
                }
            }
        });
    }

    function renderChartMaquinas(maqs) {
        const ctx = document.getElementById('chartMaquinas');
        if (!ctx) return;
        if (chartMaquinas) chartMaquinas.destroy();

        // Paleta de colores variados para máquinas
        const palette = [
            '#10b981', // Emerald
            '#6366f1', // Indigo
            '#f59e0b', // Amber
            '#f43f5e', // Rose
            '#8b5cf6', // Violet
            '#06b6d4'  // Cyan
        ];

        chartMaquinas = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: maqs.map(m => m.maquina),
                datasets: [{
                    data: maqs.map(m => m.valor),
                    backgroundColor: palette,
                    borderWidth: 4,
                    borderColor: '#ffffff',
                    hoverOffset: 15
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: window.innerWidth < 768 ? 'bottom' : 'right',
                        labels: {
                            padding: window.innerWidth < 768 ? 10 : 20,
                            font: { size: window.innerWidth < 768 ? 10 : 12, weight: '600' },
                            color: '#475569'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: (context) => ` ⚙️ ${context.label}: ${context.raw.toLocaleString()} Pz`
                        }
                    }
                }
            }
        });
    }

    function renderChartTendencia(tendencia) {
        const ctx = document.getElementById('chartTendencia');
        if (!ctx) return;
        if (chartTendencia) chartTendencia.destroy();
        chartTendencia = new Chart(ctx, {
            type: 'line',
            data: {
                labels: tendencia.map(t => t.fecha.split('-').reverse().join('/')),
                datasets: [
                    { label: 'Inyección', data: tendencia.map(t => t.iny), borderColor: '#3b82f6', tension: 0.3, fill: false },
                    { label: 'Pulido', data: tendencia.map(t => t.pul), borderColor: '#10b981', tension: 0.3, fill: false }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
        });
    }

    function renderChartPNC(pnc) {
        const ctx = document.getElementById('chartPNCGlobal');
        if (!ctx) return;
        if (chartPNC) chartPNC.destroy();
        chartPNC = new Chart(ctx, {
            type: 'polarArea',
            data: {
                labels: ['Inyección', 'Pulido', 'Ensamble', 'Almacén'],
                datasets: [{ data: [pnc.inyeccion, pnc.pulido, pnc.ensamble, pnc.almacen], backgroundColor: ['#3b82f6cc', '#10b981cc', '#f59e0bcc', '#ef4444cc'] }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
        });
    }

    function renderScrapAlmacenDetalle(desglose) {
        const container = document.getElementById('pnc-almacen-desglose');
        if (!container) return;

        container.innerHTML = '';

        if (!desglose || desglose.length === 0) {
            container.innerHTML = '<div class="list-group-item text-muted text-center py-3"><i class="fas fa-check-circle text-success mb-2 fs-4"></i><br>Sin Scrap reportado</div>';
            return;
        }

        // Tomar top 5
        const top5 = desglose.slice(0, 5);
        top5.forEach((item, index) => {
            const fCosto = item.costo > 0 ? new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(item.costo) : 'S/C';
            const html = `
                <div class="list-group-item d-flex justify-content-between align-items-center py-2 px-3" style="border-left: 4px solid #ef4444; background-color: #fafafa; margin-bottom: 8px; border-radius: 8px;">
                    <div class="text-truncate me-3" style="max-width: 65%;" title="${item.producto}">
                        <span class="text-muted me-2 fw-bold fs-6">${index + 1}.</span> 
                        <span class="fw-bold text-dark" style="font-size: 0.95rem;">${item.producto}</span>
                    </div>
                    <div class="d-flex flex-column align-items-end justify-content-center">
                        <span class="fw-bold text-danger" style="font-size: 1.05rem; letter-spacing: -0.5px;">${fCosto}</span>
                        <span class="badge rounded-pill mt-1" style="background-color: #cbd5e1; color: #334155; font-size: 0.75rem;"><i class="fas fa-cubes me-1"></i>${item.cantidad.toLocaleString()} Pz</span>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        });
    }

    function renderTablaPulido(profundo) {
        const tbody = document.querySelector('#tabla-leaderboard-pulido tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        // Mostrar TODAS las operadoras
        const operadoras = Object.keys(profundo);
        if (operadoras.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">No hay datos de pulido en este rango.</td></tr>';
            return;
        }

        // Ordenar por puntaje de esfuerzo desc (Requerimiento 2)
        const sortedOps = operadoras.sort((a, b) => (profundo[b].puntos || 0) - (profundo[a].puntos || 0));

        sortedOps.forEach((op, idx) => {
            const dataOp = profundo[op];
            const mix = dataOp.mix || [];
            const buenas = dataOp.buenas || 0;
            const pnc = dataOp.pnc || 0;
            const costoPnc = dataOp.costo_pnc || 0;

            const total = buenas + pnc;
            // Evitar el "100%" falso si hay scrap (PNC)
            const eficienciaRaw = total > 0 ? (buenas / total) * 100 : 100;
            const eficiencia = (buenas > 0 && pnc > 0 && eficienciaRaw > 99) ? eficienciaRaw.toFixed(2) : Math.round(eficienciaRaw);
            const efColor = eficienciaRaw > 95 ? 'success' : (eficienciaRaw > 85 ? 'warning' : 'danger');

            const topProd = mix[0] ? mix[0].prod : "N/A";

            // Preparar el detalle para el alert (escapar saltos de línea y comillas simples)
            const detalleMix = mix.slice(0, 5).map(p => `${p.prod}:${p.qty}:${p.u_pts || 1}:${p.pts || 0}`).join('\\n').replace(/'/g, "\\'");

            const isChecked = selectedOperators.some(s => s.nombre === op);

            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            tr.onclick = (e) => {
                // Si es clic en checkbox, lo maneja el onchange
                if (e.target.closest('.comparison-checkbox')) return;
                // Si es clic en botón (si hubiera), lo maneja el botón
                if (e.target.closest('button')) return;
                const insightText = dataOp.insight || "Sin insights disponibles para Pulido.";
                mostrarModalOperador(op, buenas, 'Pulido', insightText, detalleMix, dataOp.puntos || 0);
            };
            tr.classList.add('hover-scale');
            tr.innerHTML = `
                <td class="ps-4">
                    ${idx === 0 ? '<i class="fas fa-medal text-warning fs-5" title="Líder de Esfuerzo"></i>' : `<span class="badge bg-light text-dark border">${idx + 1}</span>`}
                </td>
                <td class="text-center">
                    <input type="checkbox" class="comparison-checkbox form-check-input" 
                        ${isChecked ? 'checked' : ''} 
                        data-op="${op}"
                        onchange="window.ModuloDashboard.toggleOperatorSelection('${op}', ${buenas}, ${pnc}, ${costoPnc}, ${eficiencia}, ${dataOp.puntos || 0}, ${dataOp.tiempo_estandar || 0}, '${detalleMix}')">
                </td>
                <td>
                    <div class="fw-bold">${op}</div>
                    <small class="text-muted">Expertiz: <span class="badge bg-info text-white">${topProd}</span></small>
                </td>
                <td class="text-center fw-bold text-primary">${Math.round(dataOp.puntos || 0).toLocaleString()} pts</td>
                <td class="text-center fw-bold text-dark">${total.toLocaleString()}</td>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="progress flex-grow-1" style="height: 8px; border-radius: 10px; background-color: #e2e8f0;">
                            <div class="progress-bar bg-${efColor}" style="width: ${eficiencia}%"></div>
                        </div>
                        <span class="fw-bold text-${efColor}" style="min-width: 40px;">${eficiencia}%</span>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }


    function aplicarPermisosVisuales() {
        console.log("🔒 Aplicando permisos visuales al Dashboard IA...");

        let rolUsuario = 'DESCONOCIDO';
        if (window.AppState && window.AppState.user && window.AppState.user.rol) {
            rolUsuario = window.AppState.user.rol.toUpperCase();
        } else if (window.AuthModule && window.AuthModule.currentUser && window.AuthModule.currentUser.rol) {
            rolUsuario = window.AuthModule.currentUser.rol.toUpperCase();
        }

        // Mapear roles antiguos/generales a los roles de acceso que configuramos en HTML
        let rolesEfectivos = [];
        if (['ADMINISTRACION', 'ADMINISTRACIÓN', 'ADMINISTRADOR', 'GERENCIA'].includes(rolUsuario)) {
            rolesEfectivos.push('ADMIN');
            rolesEfectivos.push('GERENCIA');
        }
        if (['INYECCION', 'INYECCIÓN'].includes(rolUsuario)) rolesEfectivos.push('INYECCION');
        if (['PULIDO'].includes(rolUsuario)) rolesEfectivos.push('PULIDO');
        if (['COMERCIAL', 'VENTAS'].includes(rolUsuario)) rolesEfectivos.push('COMERCIAL');

        console.log(`Rol Usuario: ${rolUsuario} -> Evaluando como [${rolesEfectivos.join(', ')}]`);

        // Preparar flow-container para reordenar
        const container = document.querySelector('#dashboard-page .container-fluid');
        if (container) {
            container.classList.add('d-flex', 'flex-column');
        }

        const chartPulido = document.getElementById('dashboard-section-pulido-leaderboard');
        const tablaPulido = document.getElementById('dashboard-section-pulido-table');

        if (rolUsuario === 'PULIDO') {
            if (chartPulido) chartPulido.style.order = '-2';
            if (tablaPulido) tablaPulido.style.order = '-1';
        } else {
            if (chartPulido) chartPulido.style.order = '';
            if (tablaPulido) tablaPulido.style.order = '';
        }

        const secciones = document.querySelectorAll('[data-role-access]');
        secciones.forEach(seccion => {
            const accessStr = seccion.getAttribute('data-role-access');
            if (!accessStr) return;

            const rolesPermitidos = accessStr.split(',').map(r => r.trim().toUpperCase());

            // Ver si al menos uno de los roles efectivos está permitido en esta sección
            const accesoPermitido = rolesEfectivos.some(r => rolesPermitidos.includes(r));

            if (accesoPermitido) {
                // Mantener visibilidad original (block o flex, quitar d-none preventivo)
                seccion.style.display = '';
            } else {
                // Ocultar sección completa
                seccion.style.setProperty('display', 'none', 'important');
            }
        });
    }


    function iniciar() {
        if (isInitialized) {
            console.log("🛡️ Dashboard ya inicializado. Abortando secuencia redundante.");
            return;
        }
        isInitialized = true;
        console.log("🚀 Iniciando BI Dashboard...");

        aplicarPermisosVisuales();

        // Filtros de Incumplimiento (Interactive)
        const inputBusca = document.getElementById('buscador-incumplimiento');

        const filterIncumplimiento = debounce(() => {
            try {
                const term = inputBusca && inputBusca.value ? String(inputBusca.value).toLowerCase().trim() : "";
                const isFiltering = term !== "";

                console.log(`🔍 Filtrando por: "${term}"`);

                const activeTbodyId = 'incumplimiento-consolidado-body';

                // Filtrar Tablas vía Cache (Ultra performance)
                const filtrarTablaPorNodos = (tbodyId) => {
                    const tbody = document.getElementById(tbodyId);
                    if (!tbody) return;

                    requestAnimationFrame(() => {
                        const rows = tbody.querySelectorAll('tr');
                        let count = 0;

                        rows.forEach((row, index) => {
                            const searchStr = row.getAttribute('data-search') || "";
                            const matches = !term || searchStr.indexOf(term) !== -1;

                            // Determinamos el estado objetivo
                            const targetDisplay = matches ? (isFiltering ? '' : (index < 12 ? '' : 'none')) : 'none';

                            // SOLO escribimos al DOM si el estado cambió
                            if (row.style.display !== targetDisplay) {
                                row.style.display = targetDisplay;
                            }

                            if (matches) count++;
                        });

                        // Actualizar contador
                        if (tbodyId === activeTbodyId) {
                            const countSpan = document.getElementById('bo-count');
                            if (countSpan) {
                                countSpan.textContent = isFiltering ? count : inc_consolidado_original.length;
                            }
                        }
                    });
                };

                filtrarTablaPorNodos(activeTbodyId);

            } catch (err) {
                console.error("❌ Error en filterIncumplimiento:", err);
            }
        }, 600);

        if (inputBusca && !searchListenerAttached) {
            inputBusca.addEventListener('input', filterIncumplimiento);
            searchListenerAttached = true;
            console.log("✅ Event Listener del buscador registrado");
        }

        // ── PERSISTENCIA DE FILTROS (localStorage) ────────────────────────────
        const LS_DESDE = 'db_filtro_desde';
        const LS_HASTA = 'db_filtro_hasta';
        const LS_TOGGLE = 'db_toggle_mode';

        const f_desde = document.getElementById('db-fecha-desde');
        const f_hasta = document.getElementById('db-fecha-hasta');

        // Restaurar desde localStorage o usar valores por defecto (últimos 30 días)
        const hoy = new Date();
        const hace30 = new Date();
        hace30.setDate(hoy.getDate() - 30);

        if (f_desde) {
            f_desde.value = localStorage.getItem(LS_DESDE) || hace30.toISOString().split('T')[0];
            f_desde.addEventListener('change', () => localStorage.setItem(LS_DESDE, f_desde.value));
        }
        if (f_hasta) {
            f_hasta.value = localStorage.getItem(LS_HASTA) || hoy.toISOString().split('T')[0];
            f_hasta.addEventListener('change', () => localStorage.setItem(LS_HASTA, f_hasta.value));
        }

        const savedToggle = localStorage.getItem(LS_TOGGLE) || 'money';
        window._db_toggleMode = savedToggle;

        cargarDatos();
    }

    function sortIncumplimiento(mode) {
        currentIncSortMode = mode;

        // Update Buttons UI
        document.getElementById('btn-sort-units')?.classList.toggle('active', mode === 'units');
        document.getElementById('btn-sort-money')?.classList.toggle('active', mode === 'money');

        if (!inc_consolidado_original || inc_consolidado_original.length === 0) return;

        let sorted = [...inc_consolidado_original];
        if (mode === 'units') {
            sorted.sort((a, b) => (b.unidades_fallidas || 0) - (a.unidades_fallidas || 0));
        } else {
            sorted.sort((a, b) => (b.dinero_perdido || 0) - (a.dinero_perdido || 0));
        }

        renderTablaIncumplimientoConsolidada(sorted);
    }

    /**
     * Renderiza tabla consolidada de Incumplimiento (Panel Gerencial)
     */
    function renderTablaIncumplimientoConsolidada(data) {
        try {
            const tbody = document.getElementById('incumplimiento-consolidado-body');
            const countSpan = document.getElementById('bo-count');

            // Nuevos IDs para KPIs Globales
            const kpiUnits = document.getElementById('bo-total-units');
            const kpiMoney = document.getElementById('bo-total-money');

            if (!tbody) return;

            if (!Array.isArray(data)) {
                tbody.innerHTML = `<tr><td colspan="3" class="text-center py-4 text-muted small">Error en formato de datos.</td></tr>`;
                return;
            }

            if (countSpan) countSpan.textContent = data.length;

            // Cálculos Globales (Grand Totals) para el Jefe
            let totalUnitsGlobal = 0;
            let totalMoneyGlobal = 0;

            let html = '';
            data.forEach((item, index) => {
                const cli = String(item.cliente || "S/N");
                const units = Number(item.unidades_fallidas) || 0;
                const money = Number(item.dinero_perdido) || 0;

                // Sumatoria
                totalUnitsGlobal += units;
                totalMoneyGlobal += money;

                const searchIndex = `${cli}`.toLowerCase().trim();
                const displayStyle = (index < 12) ? '' : 'none'; // Show top 12 by default
                const safeCli = cli.replace(/'/g, "\\'").replace(/"/g, "&quot;");

                html += `
                    <tr class="table-row-hover" style="display: ${displayStyle}; cursor: pointer; transition: background-color 0.2s;" data-search="${searchIndex}" onclick="window.ModuloDashboard.mostrarDetalleIncumplimiento('${safeCli}')">
                        <td class="ps-4 py-2" style="font-size: 0.85rem;">
                            <div class="fw-bold text-dark text-truncate" style="max-width: 300px;" title="${cli}">${cli}</div>
                        </td>
                        <td class="text-center text-danger fw-bold py-2" style="font-size: 0.95rem;">
                            ${formatNumber(units)}
                        </td>
                        <td class="text-center text-success fw-bold py-2" style="font-size: 0.95rem;">
                            ${formatCOP(money)}
                        </td>
                    </tr>
                `;
            });

            // Inyectar Totales Globales
            if (kpiUnits) kpiUnits.textContent = formatNumber(totalUnitsGlobal);
            if (kpiMoney) kpiMoney.textContent = formatCOP(totalMoneyGlobal);

            tbody.innerHTML = html || '<tr><td colspan="3" class="text-center py-4 text-muted">No hay registros de incumplimiento.</td></tr>';

        } catch (e) {
            console.error("❌ Error en renderTablaIncumplimientoConsolidada:", e);
        }
    }

    /**
     * Alterna la vista de las gráficas entre Dinero y Unidades
     */
    function mostrarModalOperador(nombre, totalOks, proceso, insightStr, detalleMix = null, puntos = null) {

        let extraHtml = '';
        if (detalleMix) {
            // Convertir las líneas en items bonitos de lista (soporta \n literal o salto de línea real)
            const mixLines = detalleMix.split(/\\n|\n/).map(l => {
                const parts = l.split(':');
                if (parts.length >= 4) {
                    const ref = parts[0].trim();
                    const qty = parseFloat(String(parts[1]).replace(/[^0-9.-]/g, '')) || 0;
                    const unitPts = parseFloat(String(parts[2]).replace(/[^0-9.-]/g, '')) || 0;
                    const pts = parseFloat(String(parts[3]).replace(/[^0-9.-]/g, '')) || 0;

                    return `
                        <div class="d-flex flex-wrap flex-md-nowrap justify-content-between align-items-start align-items-md-center py-2 border-bottom gap-2">
                            <span class="fw-medium text-dark text-nowrap" style="font-size: 0.85rem;"><i class="fas fa-cube text-muted me-1"></i> Ref: ${ref}</span>
                            <div class="d-flex align-items-center gap-1 flex-wrap">
                                <span class="badge bg-light text-secondary border-0 text-nowrap" style="font-size: 0.75rem;">${qty.toLocaleString()} pz</span>
                                <span class="text-muted small">×</span>
                                <span class="badge bg-light text-secondary border-0 text-nowrap" style="font-size: 0.75rem;">${unitPts.toLocaleString()} pts</span>
                                <span class="text-muted small">=</span>
                                <span class="badge bg-white text-primary border-primary border-opacity-25 fw-bold text-nowrap" style="min-width: 65px; color: #3b82f6 !important;">${Math.round(pts).toLocaleString()} pts</span>
                            </div>
                        </div>`;
                } else if (parts.length >= 2) {
                    const ref = parts[0].trim();
                    const val = parts[1].trim();
                    return `
                        <div class="d-flex flex-wrap flex-md-nowrap justify-content-between align-items-start align-items-md-center py-2 border-bottom gap-2">
                            <span class="fw-medium text-dark text-nowrap"><i class="fas fa-cube text-muted me-2"></i> Ref: ${ref}</span>
                            <span class="badge bg-light text-primary border text-nowrap">${val}</span>
                        </div>`;
                }
                return `<li>${l}</li>`;
            }).join('');

            extraHtml = `
                <div class="mt-4 text-start">
                    <h6 class="fw-bold text-uppercase text-secondary mb-3" style="font-size: 0.8rem; letter-spacing: 1px;">
                        <i class="fas fa-list-ol ms-1"></i> Referencias Trabajadas
                    </h6>
                    <div class="bg-white rounded-3 shadow-sm border p-3">
                        ${mixLines}
                    </div>
                </div>
                `;
        }

        // Definir un color temático según el proceso
        const themeColor = proceso.toUpperCase() === 'PULIDO' ? '#10b981' : '#3b82f6';
        const iconProceso = proceso.toUpperCase() === 'PULIDO' ? 'fa-gem' : 'fa-cogs';

        Swal.fire({
            title: null, // Quitamos el título estándar para customizar el header completo
            html: `
                <div class="modal-operador-custom">
                    <!-- Cabecera Principal -->
                    <div class="text-center mb-4">
                        <div class="d-inline-flex justify-content-center align-items-center rounded-circle mb-3 shadow-sm border" 
                             style="width: 70px; height: 70px; background-color: #f8fafc;">
                            <i class="fas fa-user-tie fs-1" style="color: ${themeColor}"></i>
                        </div>
                        <h4 class="fw-bold text-dark mb-0">${nombre}</h4>
                        <span class="badge rounded-pill mt-2 px-3 py-2 shadow-sm" style="background-color: ${themeColor}; color: white; font-weight: 500;">
                            <i class="fas ${iconProceso} me-1"></i> Área de ${proceso}
                        </span>
                    </div>

                    <!-- Insight Box (El tip del Bot) -->
                    <div class="p-3 bg-light rounded-3 border-start border-4 mb-4 shadow-sm text-start" style="border-left-color: #f59e0b !important;">
                        <p class="mb-0 fst-italic text-secondary small" style="line-height: 1.5;">
                            <i class="fas fa-lightbulb text-warning me-1"></i> "${insightStr}"
                        </p>
                    </div>

                    <!-- Grid de Estadísticas Rápidas -->
                    <div class="row g-2 mb-2 text-center">
                        <div class="col-6">
                            <div class="p-3 rounded-3" style="background-color: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2);">
                                <h6 class="text-secondary text-uppercase mb-1" style="font-size: 0.75rem;"><i class="fas fa-check-circle text-success me-1"></i> Piezas Conformes</h6>
                                <h2 class="fw-bold mb-0 text-success">${totalOks.toLocaleString()}</h2>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="p-3 rounded-3" style="background-color: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2);">
                                <h6 class="text-secondary text-uppercase mb-1" style="font-size: 0.75rem;"><i class="fas fa-star text-primary me-1"></i> Puntaje Esfuerzo</h6>
                                <h2 class="fw-bold mb-0 text-primary">${puntos !== null ? Math.round(puntos).toLocaleString() : '---'}</h2>
                            </div>
                        </div>
                    </div>

                    <!-- Desglose de Mix -->
                ${extraHtml}
                </div>
                `,
            showConfirmButton: true,
            confirmButtonText: '<i class="fas fa-times me-1"></i> Cerrar Resumen',
            confirmButtonColor: '#334155', // Slate 700 para que sea sobrio
            buttonsStyling: true,
            customClass: {
                confirmButton: 'btn rounded-pill px-4 shadow-sm'
            },
            width: window.innerWidth > 768 ? '32em' : '95%',
            padding: window.innerWidth > 768 ? '2rem' : '1rem'
        });
    }

    function mostrarModalTodosInyeccion(ops) {
        if (!ops || ops.length === 0) return Swal.fire("Aviso", "No hay operadores de inyección", "info");

        // Construir tabla
        let rowsHtml = ops.map((op, idx) => {
            const topProd = op.mix && op.mix[0] ? op.mix[0].prod : "N/A";
            // Usamos cuádruple backslash para que en el atributo HTML llegue como doble backslash (literal \n)
            const detalleMixText = op.mix ? op.mix.slice(0, 5).map(p => `${p.prod}:${p.qty}:${p.u_pts || 1}:${p.pts || 0} `).join('\\\\n').replace(/'/g, "\\'") : '';
            const nombreEscaped = op.nombre.replace(/'/g, "\\'");
            const insightEscaped = (op.insight || "Sin insights disponibles para Inyección.").replace(/'/g, "\\'");

            return `
                < tr style = "cursor: pointer" onclick = "ModuloDashboard.mostrarModalOperador('${nombreEscaped}', ${op.valor}, 'Inyección', '${insightEscaped}', '${detalleMixText}')" >
                    <td class="ps-3"><span class="badge bg-light text-dark border">${idx + 1}</span></td>
                    <td class="text-start">
                        <div class="fw-bold">${op.nombre}</div>
                        <small class="text-muted">Expertiz: <span class="badge bg-info text-white">${topProd}</span></small>
                    </td>
                    <td class="text-center fw-bold text-success">${op.valor.toLocaleString()}</td>
                </tr >
                `;
        }).join('');

        Swal.fire({
            title: `< i class="fas fa-users text-primary mb-2" ></i > <br>Todos los Operadores (Inyección)`,
            html: `
                <div class="table-responsive" style="max-height: 400px;">
                    <table class="table table-hover align-middle small mb-0">
                        <thead class="bg-light sticky-top">
                            <tr>
                                <th style="width: 15%;">#</th>
                                <th class="text-start" style="width: 55%;">Operador</th>
                                <th class="text-center" style="width: 30%;">Piezas Buenas</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
                <div class="mt-2 text-muted small"><i class="fas fa-hand-pointer"></i> Haz clic en un operador para ver su detalle</div>
                `,
            width: window.innerWidth > 768 ? '36em' : '100%',
            showConfirmButton: true,
            confirmButtonText: 'Cerrar',
            confirmButtonColor: '#3b82f6'
        });
    }

    function renderChartPulidoLeaderboard(profundo) {
        const ctx = document.getElementById('chartPulidoLeaderboard');
        if (!ctx || !profundo || typeof profundo !== 'object') return;

        // 1. Procesar datos REALES del objeto profundo
        const operadoras = Object.keys(profundo);
        // Ordenamos descendentemente por puntos
        const sortedOps = operadoras.sort((a, b) => (profundo[b].puntos || 0) - (profundo[a].puntos || 0));

        // Tomar el Top 5 o Top 10 para la gráfica
        const topN = sortedOps.slice(0, 7);

        const labels = topN;
        const dataPuntos = topN.map(op => profundo[op].puntos || 0);

        // Crear gradientes para un look más "premium"
        const chartCtx = ctx.getContext('2d');
        const gradientGold = chartCtx.createLinearGradient(0, 0, 0, 400);
        gradientGold.addColorStop(0, 'rgba(251, 191, 36, 1)'); // Amber 400
        gradientGold.addColorStop(1, 'rgba(217, 119, 6, 0.8)'); // Amber 600

        const gradientBlue = chartCtx.createLinearGradient(0, 0, 0, 400);
        gradientBlue.addColorStop(0, 'rgba(99, 102, 241, 1)'); // Indigo 500
        gradientBlue.addColorStop(1, 'rgba(67, 56, 202, 0.8)'); // Indigo 700

        // 2. Colores (Dorado para el #1)
        const bgColors = dataPuntos.map((val, idx) => idx === 0 ? gradientGold : gradientBlue);
        const borderColors = dataPuntos.map((val, idx) => idx === 0 ? 'rgba(217, 119, 6, 1)' : 'rgba(67, 56, 202, 1)');

        if (chartPulidoBoard) chartPulidoBoard.destroy();

        chartPulidoBoard = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Puntaje de Esfuerzo',
                    data: dataPuntos,
                    backgroundColor: bgColors,
                    borderColor: borderColors,
                    borderWidth: 0, // Quitamos borde para look más limpio con el gradiente
                    borderRadius: { topLeft: 8, topRight: 8, bottomLeft: 0, bottomRight: 0 },
                    barPercentage: 0.5,
                    categoryPercentage: 0.7,
                    hoverBackgroundColor: borderColors // Efecto hover
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 1500,
                    easing: 'easeOutQuart'
                },
                layout: {
                    padding: { top: 20 } // Espacio para que no se pegue arriba
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)', // Slate 900
                        titleFont: { size: 14, weight: 'bold' },
                        bodyFont: { size: 13 },
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            label: (context) => `⭐ ${Math.round(context.raw).toLocaleString()} Puntos de Esfuerzo`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(226, 232, 240, 0.5)', // Slate 200 muy suave
                            drawBorder: false
                        },
                        ticks: {
                            font: { weight: '600' },
                            color: '#64748b', // Slate 500
                            padding: 10
                        }
                    },
                    x: {
                        grid: { display: false, drawBorder: false },
                        ticks: {
                            font: { weight: 'bold', size: 11 },
                            color: '#334155', // Slate 700
                            maxRotation: 25,
                            minRotation: 0
                        }
                    }
                }
            }
        });
    }

    // --- Helpers de Formateo ---
    const formatCOP = (num) => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(num);
    const formatNumber = (num) => new Intl.NumberFormat('es-CO').format(num);

    function renderChartMensual(datosMensuales, mode = 'money') {
        const ctx = document.getElementById('chartMensual');
        if (!ctx || !Array.isArray(datosMensuales) || datosMensuales.length === 0) return;

        try {
            const labels = datosMensuales.map(d => d.mes);
            const isMoney = mode === 'money';

            // Año desde los inputs reales del filtro
            const hastaInput = document.getElementById('db-fecha-hasta');
            const yearActual = hastaInput?.value
                ? new Date(hastaInput.value).getFullYear()
                : new Date().getFullYear();
            const yearPrev = yearActual - 1;

            // Datos
            const dataActualVentas = datosMensuales.map(d => isMoney ? (d.actual_dinero || 0) : (d.actual_unidades || 0));
            const dataPrevVentas = datosMensuales.map(d => isMoney ? (d.prev_dinero || 0) : (d.prev_unidades || 0));
            const dataActualPedidos = datosMensuales.map(d => isMoney ? (d.actual_pedidos || 0) : (d.actual_pedidos_unidades || 0));
            const dataPrevPedidos = datosMensuales.map(d => isMoney ? (d.prev_pedidos || 0) : (d.prev_pedidos_unidades || 0));

            // Ocultar líneas de Pedidos en Unidades si no hay datos reales
            const hayPedidosUnidades = !isMoney && dataActualPedidos.some(v => v > 0);

            if (chartMensualInst) chartMensualInst.destroy();

            // Colores base
            const AZUL_BARRA = 'rgba(59, 130, 246, 0.88)';
            const GRIS_BARRA = 'rgba(148, 163, 184, 0.65)';
            const AZUL_META = '#f59e0b';   // ámbar — contraste con barra azul
            const GRIS_META = '#a78bfa';   // púrpura suave — contraste con barra gris

            chartMensualInst = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [
                        // ── Barras agrupadas ──────────────────────────
                        {
                            label: isMoney ? `Ventas ${yearActual} ($)` : `Ventas ${yearActual} (Unds)`,
                            data: dataActualVentas,
                            backgroundColor: AZUL_BARRA,
                            borderRadius: 3,
                            barPercentage: 0.9,
                            categoryPercentage: 0.8,
                            order: 3
                        },
                        {
                            label: isMoney ? `Ventas ${yearPrev} ($)` : `Ventas ${yearPrev} (Unds)`,
                            data: dataPrevVentas,
                            backgroundColor: GRIS_BARRA,
                            borderRadius: 3,
                            barPercentage: 0.9,
                            categoryPercentage: 0.8,
                            order: 4
                        },
                        // ── Metas elegantes: línea punteada + diamante ─
                        {
                            label: isMoney ? `Pedidos ${yearActual} ($)` : `Pedidos ${yearActual} (Unds)`,
                            data: dataActualPedidos,
                            type: 'line',
                            showLine: true,
                            borderColor: AZUL_META,
                            borderWidth: 1.5,
                            borderDash: [5, 5],
                            backgroundColor: 'transparent',
                            pointStyle: 'diamond',
                            pointRadius: 5,
                            pointHoverRadius: 7,
                            pointBackgroundColor: AZUL_META,
                            pointBorderColor: '#fff',
                            pointBorderWidth: 1.5,
                            tension: 0,
                            hidden: !isMoney && !hayPedidosUnidades,
                            order: 1
                        },
                        {
                            label: isMoney ? `Pedidos ${yearPrev} ($)` : `Pedidos ${yearPrev} (Unds)`,
                            data: dataPrevPedidos,
                            type: 'line',
                            showLine: true,
                            borderColor: GRIS_META,
                            borderWidth: 1.5,
                            borderDash: [5, 5],
                            backgroundColor: 'transparent',
                            pointStyle: 'circle',
                            pointRadius: 5,
                            pointHoverRadius: 7,
                            pointBackgroundColor: GRIS_META,
                            pointBorderColor: '#fff',
                            pointBorderWidth: 1.5,
                            tension: 0,
                            hidden: !isMoney && !hayPedidosUnidades,
                            order: 2
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 400, easing: 'easeOutCubic' },
                    interaction: { mode: 'nearest', intersect: true },
                    plugins: {
                        legend: {
                            labels: {
                                usePointStyle: true,
                                font: { size: 11 },
                                padding: 16,
                                filter: item => item.text !== ''
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: (c) => c.raw > 0
                                    ? ` ${c.dataset.label}: ${isMoney ? formatCOP(c.raw) : formatNumber(c.raw)}`
                                    : null
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { borderDash: [4, 4], color: 'rgba(0,0,0,0.04)' },
                            ticks: {
                                callback: v => {
                                    if (!isMoney) return formatNumber(v);
                                    if (v >= 1000000) return '$' + (v / 1000000).toFixed(1) + 'M';
                                    return '$' + formatNumber(v);
                                }
                            }
                        },
                        x: { grid: { display: false } }
                    }
                }
            });
        } catch (e) {
            console.error("Error renderizando chartMensual:", e);
        }
    }

    function renderChartTopMejores(datos, mode = 'money') {
        const ctx = document.getElementById('chartTopMejores');
        if (!ctx || !Array.isArray(datos) || datos.length === 0) return;

        try {
            const isMoney = mode === 'money';
            const labels = datos.slice(0, 10).map(d => {
                const name = d.producto || '';
                return name.substring(0, 20) + (name.length > 20 ? '...' : '');
            });
            const dataVals = datos.slice(0, 10).map(d => isMoney ? d.ventas_dinero : d.ventas_unidades);

            if (chartTopMejoresInst) chartTopMejoresInst.destroy();

            chartTopMejoresInst = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: isMoney ? 'Ventas ($)' : 'Ventas (Unds)',
                        data: dataVals,
                        backgroundColor: 'rgba(245, 158, 11, 0.85)',
                        borderRadius: 4,
                        barPercentage: 0.7
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 300 },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (context) => {
                                    const d = datos[context[0].dataIndex];
                                    return d.producto || '';
                                },
                                label: (context) => ` Ventas: ${isMoney ? formatCOP(context.raw) : formatNumber(context.raw)}`
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { borderDash: [4, 4] },
                            ticks: {
                                callback: function (value) {
                                    if (!isMoney) return formatNumber(value);
                                    if (value >= 1000000) return '$' + (value / 1000000) + 'M';
                                    return '$' + formatNumber(value);
                                }
                            }
                        },
                        y: { grid: { display: false }, ticks: { font: { size: 10 } } }
                    }
                }
            });
        } catch (e) {
            console.error("Error renderizando chartTopMejores:", e);
        }
    }
    function renderChartTopPeores(datos, mode = 'money') {
        const ctx = document.getElementById('chartTopPeores');
        if (!ctx || !Array.isArray(datos) || datos.length === 0) return;

        try {
            const isMoney = mode === 'money';
            const labels = datos.slice(0, 10).map(d => {
                const name = d.producto || '';
                return name.substring(0, 20) + (name.length > 20 ? '...' : '');
            });
            const dataVals = datos.slice(0, 10).map(d => isMoney ? d.ventas_dinero : d.ventas_unidades);

            if (chartTopPeoresInst) chartTopPeoresInst.destroy();

            chartTopPeoresInst = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: isMoney ? 'Ventas ($)' : 'Ventas (Unds)',
                        data: dataVals,
                        backgroundColor: 'rgba(239, 68, 68, 0.75)',
                        borderRadius: 4,
                        barPercentage: 0.7
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (context) => {
                                    const d = datos[context[0].dataIndex];
                                    return d.producto || '';
                                },
                                label: (context) => ` Ventas: ${isMoney ? formatCOP(context.raw) : formatNumber(context.raw)}`
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { borderDash: [4, 4] },
                            ticks: {
                                callback: function (value) {
                                    if (!isMoney) return formatNumber(value);
                                    if (value >= 1000000) return '$' + (value / 1000000) + 'M';
                                    return '$' + formatNumber(value);
                                }
                            }
                        },
                        y: { grid: { display: false }, ticks: { font: { size: 10 } } }
                    }
                }
            });
        } catch (e) {
            console.error("Error renderizando chartTopPeores:", e);
        }
    }

    /**
     * Alterna la vista de las gráficas entre Dinero y Unidades
     */
    function toggleChartView(chartType, mode) {
        if (!lastJefaturaData) return;

        // Persistir en localStorage
        localStorage.setItem('db_toggle_mode', mode);

        // Update Button UI
        const btnMoney = document.getElementById(`toggle-${chartType}-money`);
        const btnUnits = document.getElementById(`toggle-${chartType}-units`);
        if (btnMoney) btnMoney.classList.toggle('active', mode === 'money');
        if (btnUnits) btnUnits.classList.toggle('active', mode === 'units');

        if (chartType === 'mensual') {
            renderChartMensual(lastJefaturaData.mensual, mode);
        } else if (chartType === 'mejores') {
            const arr = mode === 'money' ? lastJefaturaData.top_productos_dinero : lastJefaturaData.top_productos_unidades;
            const sorted = [...arr].sort((a, b) => (mode === 'money' ? b.ventas_dinero - a.ventas_dinero : b.ventas_unidades - a.ventas_unidades));
            renderChartTopMejores(sorted, mode);
        } else if (chartType === 'peores') {
            const arr = mode === 'money' ? lastJefaturaData.peores_productos_dinero : lastJefaturaData.peores_productos_unidades;
            const sorted = [...arr].sort((a, b) => (mode === 'money' ? a.ventas_dinero - b.ventas_dinero : a.ventas_unidades - b.ventas_unidades));
            renderChartTopPeores(sorted, mode);
        }
    }

    function mostrarDetalleIncumplimiento(cliente) {
        if (!inc_unidades_original || !inc_dinero_original) return;

        const cliStr = (cliente || "").trim().toLowerCase();
        const f_unidades = inc_unidades_original.filter(d => (d.cliente || "").trim().toLowerCase() === cliStr);
        const f_dinero = inc_dinero_original.filter(d => (d.cliente || "").trim().toLowerCase() === cliStr);

        const mapProductos = {};
        const normalizeProd = p => (p || 'Sin Referencia').trim().toLowerCase();

        f_unidades.forEach(d => {
            const rawP = d.producto || 'Sin Referencia';
            const normP = normalizeProd(rawP);
            if (!mapProductos[normP]) {
                mapProductos[normP] = { prod: rawP, p_unds: 0, v_unds: 0, f_unds: 0, money: 0 };
            }
            mapProductos[normP].p_unds += (Number(d.pedidos) || 0);
            mapProductos[normP].v_unds += (Number(d.ventas) || 0);
            mapProductos[normP].f_unds += (Number(d.unidades_fallidas) || 0);
        });

        f_dinero.forEach(d => {
            const rawP = d.producto || 'Sin Referencia';
            const normP = normalizeProd(rawP);
            if (!mapProductos[normP]) {
                mapProductos[normP] = { prod: rawP, p_unds: 0, v_unds: 0, f_unds: 0, money: 0 };
            }
            mapProductos[normP].money += (Number(d.dinero_perdido) || 0);
        });

        const listado = Object.values(mapProductos).sort((a, b) => b.f_unds - a.f_unds);

        if (listado.length === 0) {
            Swal.fire("Información", `No hay detalle de faltantes para ${cliente}`, "info");
            return;
        }

        const decodedCliente = cliente.replace(/&quot;/g, '"');
        let rowsHtml = '';
        let totP = 0, totV = 0, totF = 0, totM = 0;

        listado.forEach((item, idx) => {
            totP += item.p_unds;
            totV += item.v_unds;
            totF += item.f_unds;
            totM += item.money;

            const rowBg = idx % 2 === 0 ? 'rgba(248, 250, 252, 0.8)' : '#ffffff';

            rowsHtml += `
                <tr style="background-color: ${rowBg}; border-bottom: 1px solid #f1f5f9;">
                    <td class="text-start ps-3 py-3" style="font-size: 0.85rem; width: 42%;">
                        <div class="fw-bold text-slate-800">${item.prod}</div>
                    </td>
                    <td class="text-end pe-3 py-3 text-muted" style="font-size: 0.9rem; font-family: 'JetBrains Mono', monospace;">${formatNumber(item.p_unds)}</td>
                    <td class="text-end pe-3 py-3 text-primary" style="font-size: 0.9rem; font-family: 'JetBrains Mono', monospace;">${formatNumber(item.v_unds)}</td>
                    <td class="text-end pe-3 py-3 text-danger fw-bold" style="font-size: 0.95rem; font-family: 'JetBrains Mono', monospace; background-color: rgba(239, 68, 68, 0.04);">${formatNumber(item.f_unds)}</td>
                    <td class="text-end pe-4 py-3 text-success fw-bold" style="font-size: 0.95rem; font-family: 'JetBrains Mono', monospace;">${formatCOP(item.money)}</td>
                </tr>
                `;
        });

        Swal.fire({
            title: `<div class="mb-1"><i class="fas fa-history text-danger fs-3"></i></div><div style="font-size:1.25rem; font-weight:800; color: #1e293b;">KPI: Faltantes de Facturación</div><div class="text-muted small fw-normal">${decodedCliente}</div>`,
            html: `
                <div class="table-responsive border rounded-3" style="max-height: 520px; overflow-y: auto; position: relative;">
                    <table class="table table-sm table-hover align-middle mb-0" style="min-width: 900px; border-collapse: separate; border-spacing: 0;">
                        <thead style="position: sticky; top: 0; z-index: 20; background-color: #1e293b; color: #f8fafc;">
                            <tr>
                                <th class="text-start ps-3 py-3" style="font-size:0.75rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: none;">REFERENCIA / PRODUCTO</th>
                                <th class="text-end pe-3 py-3" style="font-size:0.75rem; text-transform: uppercase; border-bottom: none;">PEDIDO</th>
                                <th class="text-end pe-3 py-3" style="font-size:0.75rem; text-transform: uppercase; border-bottom: none;">FACTURADO</th>
                                <th class="text-end pe-3 py-3" style="font-size:0.75rem; text-transform: uppercase; border-bottom: none;">FALTANTE</th>
                                <th class="text-end pe-4 py-3" style="font-size:0.75rem; text-transform: uppercase; border-bottom: none;">IMPACTO ($)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                        <tfoot style="position: sticky; bottom: 0; z-index: 20; background-color: #f8fafc; border-top: 2px solid #cbd5e1; box-shadow: 0 -4px 6px -1px rgb(0 0 0 / 0.1);">
                            <tr class="fw-bolder">
                                <td class="ps-3 py-3 text-uppercase" style="font-size: 0.8rem; color: #475569;">Total Consolidado Historico</td>
                                <td class="text-end pe-3 py-3 text-dark" style="font-size: 1rem; font-family: 'JetBrains Mono', monospace;">${formatNumber(totP)}</td>
                                <td class="text-end pe-3 py-3 text-primary" style="font-size: 1rem; font-family: 'JetBrains Mono', monospace;">${formatNumber(totV)}</td>
                                <td class="text-end pe-3 py-3 text-danger" style="font-size: 1.1rem; font-family: 'JetBrains Mono', monospace; background-color: rgba(239, 68, 68, 0.06);">${formatNumber(totF)}</td>
                                <td class="text-end pe-4 py-3 text-success" style="font-size: 1.1rem; font-family: 'JetBrains Mono', monospace;">${formatCOP(totM)}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
                <div class="mt-4 d-flex justify-content-between align-items-center gap-3">
                    <div class="p-3 bg-light rounded-2 flex-grow-1 text-start" style="font-size: 0.75rem; border-left: 4px solid #ef4444;">
                        <strong>Definición:</strong> Estos datos representan productos que no pudieron ser entregados en ventas pasadas por falta de disponibilidad.
                    </div>
                </div>
                `,
            width: window.innerWidth > 768 ? '65em' : '100%',
            confirmButtonText: '<i class="fas fa-times me-2"></i> Cerrar Análisis',
            confirmButtonColor: '#334155',
            customClass: {
                confirmButton: 'btn rounded-pill px-5 py-2 fw-bold shadow-lg mt-2'
            }
        });
    }

    function toggleOperatorSelection(nombre, buenas, pnc, costoPnc, eficiencia, puntos, tiempoEstandar, detalleMix = null) {
        const index = selectedOperators.findIndex(s => s.nombre === nombre);
        if (index > -1) {
            selectedOperators.splice(index, 1);
        } else {
            if (selectedOperators.length >= 3) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Límite alcanzado',
                    text: 'Solo puedes comparar hasta 3 operarios a la vez.',
                    confirmButtonColor: '#3b82f6'
                });
                renderTablaPulido(lastJefaturaData?.profundo_pulido || {}); // Refrescar para desmarcar el checkbox
                return;
            }
            selectedOperators.push({ nombre, buenas, pnc, costoPnc, eficiencia, puntos, tiempoEstandar, detalleMix });
        }

        actualizarUIComparativa();
    }

    function actualizarUIComparativa() {
        const btn = document.getElementById('btn-comparar-pulido');
        const count = document.getElementById('count-comparar');

        if (btn && count) {
            count.textContent = selectedOperators.length;
            if (selectedOperators.length >= 2) {
                btn.classList.remove('d-none');
            } else {
                btn.classList.add('d-none');
            }
        }
    }

    function abrirModalComparativa() {
        console.log("📊 Abriendo comparativa cara a cara...", selectedOperators);
        const grid = document.getElementById('comparativa-grid');
        if (!grid) return;

        grid.innerHTML = '';

        const maxPuntos = Math.max(...selectedOperators.map(o => o.puntos || 0));
        const minCosto = Math.min(...selectedOperators.map(o => o.costoPnc));
        const maxEfi = Math.max(...selectedOperators.map(o => o.eficiencia));

        selectedOperators.forEach(op => {
            const fmtMoney = v => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(v);
            const precisionEfi = op.buenas === (op.buenas + op.pnc) ? 100 : ((op.buenas / (op.buenas + op.pnc)) * 100).toFixed(2);

            const esGanadorPuntos = (op.puntos || 0) === maxPuntos && maxPuntos > 0;
            const esGanadorCalidad = op.costoPnc === minCosto;

            // Procesar Mix para el Top 5
            let mixHtml = '<div class="text-muted small py-2">Sin datos de referencias</div>';
            if (op.detalleMix) {
                const lines = op.detalleMix.split(/\\n|\n/).slice(0, 5); // Tomar solo los primeros 5
                mixHtml = lines.map(l => {
                    const parts = l.split(':');
                    if (parts.length >= 4) {
                        const ref = parts[0].trim().substring(0, 25); // Truncar si es muy largo
                        const qty = parseFloat(String(parts[1]).replace(/[^0-9.-]/g, '')) || 0;
                        const pts = parseFloat(String(parts[3]).replace(/[^0-9.-]/g, '')) || 0;
                        return `
                <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom border-light">
                    <span style="font-size: 0.65rem; color: #475569;" class="text-truncate" title="${parts[0].trim()}">${ref}</span>
                    <div class="d-flex align-items-center gap-1">
                        <span class="badge bg-light text-dark" style="font-size: 0.6rem;">${qty.toLocaleString()} pz</span>
                        <span class="badge bg-white text-primary border border-primary border-opacity-10" style="font-size: 0.6rem; min-width: 45px;">${Math.round(pts).toLocaleString()} pts</span>
                    </div>
                </div>
                `;
                    }
                    return '';
                }).join('');
            }

            const html = `
                <div class="comparison-column ${esGanadorPuntos ? 'winner-column' : ''}">
                    ${esGanadorPuntos ? '<div class="winner-badge"><i class="fas fa-medal me-1"></i> Líder de Esfuerzo</div>' : ''}
                    <div class="comparison-header">
                        <div class="comparison-avatar">
                            <i class="fas fa-user-ninja"></i>
                        </div>
                        <h4 class="fw-bold text-dark mb-1" style="font-size: 1.1rem;">${op.nombre}</h4>
                        <span class="text-muted small">Experto en Pulido</span>
                    </div>

                    <div class="comparison-metric bg-light">
                        <div class="metric-row">
                            <div class="metric-label-group">
                                <div class="metric-icon"><i class="fas fa-star text-warning"></i></div>
                                <span class="metric-label">Esfuerzo (Pts)</span>
                            </div>
                            <span class="metric-value ${esGanadorPuntos ? 'metric-highlight' : ''}">${(op.puntos || 0).toLocaleString(undefined, { minimumFractionDigits: 1 })}</span>
                        </div>
                        <div class="comparison-progress-container mt-3">
                            <div class="comparison-progress-bar bg-warning" style="width: ${maxPuntos > 0 ? ((op.puntos || 0) / maxPuntos) * 100 : 0}%"></div>
                        </div>
                    </div>

                    <div class="mb-3 px-3">
                        <div class="text-uppercase text-secondary fw-bold mb-2" style="font-size: 0.65rem; letter-spacing: 0.05em;">
                            <i class="fas fa-trophy text-info me-1"></i> Top 5 Referencias
                        </div>
                        <div class="bg-white rounded-2 p-2 shadow-sm border border-light">
                            ${mixHtml}
                        </div>
                    </div>

                    <div class="comparison-metric">
                        <div class="metric-row">
                            <div class="metric-label-group">
                                <div class="metric-icon"><i class="fas fa-hand-holding-usd text-danger"></i></div>
                                <span class="metric-label">Pérdida Calidad</span>
                            </div>
                            <span class="metric-value ${esGanadorCalidad ? 'metric-highlight text-success' : 'text-danger'}">${fmtMoney(op.costoPnc)}</span>
                        </div>
                    </div>

                    <div class="comparison-metric bg-light">
                        <div class="metric-row">
                            <div class="metric-label-group">
                                <div class="metric-icon"><i class="fas fa-chart-line text-success"></i></div>
                                <span class="metric-label">Efectividad</span>
                            </div>
                            <span class="metric-value ${op.eficiencia === maxEfi ? 'metric-highlight' : ''}">${precisionEfi}%</span>
                        </div>
                    </div>

                    <div class="comparison-metric">
                        <div class="metric-row">
                            <div class="metric-label-group">
                                <div class="metric-icon"><i class="fas fa-clock text-info"></i></div>
                                <span class="metric-label">Tiempo Est (min)</span>
                            </div>
                            <span class="metric-value" style="font-size: 1rem;">${(op.tiempoEstandar || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}'</span>
                        </div>
                    </div>
                </div>
                `;
            grid.insertAdjacentHTML('beforeend', html);
        });

        const modal = new bootstrap.Modal(document.getElementById('modalComparativaPulido'));
        modal.show();
    }

    // Attach to windows for HTML access
    window.ModuloDashboard = {
        inicializar: iniciar,
        refrescar: cargarDatos,
        refrescarDatos: () => cargarDatos(true),   // botón 🔄: fuerza lectura fresca (nocache)
        mostrarModalOperador: mostrarModalOperador,
        toggleChartView: toggleChartView,
        mostrarDetalleIncumplimiento: mostrarDetalleIncumplimiento,
        sortIncumplimiento: sortIncumplimiento,
        toggleOperatorSelection,
        abrirModalComparativa
    };

    return window.ModuloDashboard;
})();
