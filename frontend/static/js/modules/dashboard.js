window.ModuloDashboard = (function () {
    let chartOperadores = null;
    let chartMaquinas = null;
    let chartTendencia = null;
    let chartPNC = null;

    const colores = {
        azul: ['rgba(59, 130, 246, 0.8)', 'rgba(96, 165, 250, 0.8)', 'rgba(147, 197, 253, 0.8)'],
        verde: ['#10b981', '#34d399', '#6ee7b7'],
        naranja: ['#f59e0b', '#fbbf24', '#fcd34d'],
        peligro: ['#ef4444', '#f87171', '#fca5a5']
    };

    let currentInsights = [];
    let insightIndex = 0;
    let insightInterval = null;

    async function cargarDatos() {
        try {
            const desde = document.getElementById('db-fecha-desde')?.value;
            const hasta = document.getElementById('db-fecha-hasta')?.value;

            let url = '/api/dashboard/stats';
            const params = new URLSearchParams();
            if (desde) params.append('desde', desde);
            if (hasta) params.append('hasta', hasta);
            if (params.toString()) url += `?${params.toString()}`;

            const response = await fetch(url);
            const result = await response.json();

            if (result.status === 'success') {
                const data = result.data;
                renderizarTodo(data);

                // Initialize Bootstrap tooltips if they exist
                const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
                const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
            }
        } catch (error) {
            console.error("Error en Dashboard BI:", error);
        }
    }

    function renderizarTodo(data) {
        // 1. KPIs Principales
        document.getElementById('cumplimiento-global').textContent = `${data.kpis.cumplimiento_pct}%`;
        document.getElementById('total-iny-piezas').textContent = `${data.kpis.inyeccion_ok.toLocaleString()} Pz`;
        document.getElementById('pnc-almacen-val').textContent = data.kpis.scrap_detalle.almacen.toLocaleString();

        // 2. Preparar Insights IA para el carrusel
        // Incluimos el rango como el primer insight
        currentInsights = [
            `Analizando datos clave del periodo: <strong>${data.rango.desde}</strong> al <strong>${data.rango.hasta}</strong>.`,
            ...data.insights_ia
        ];

        iniciarCarrouselBot();

        // 3. Gráficos
        const inyeccionOps = data.rankings.inyeccion_ops || [];
        renderChartInyeccion(inyeccionOps.slice(0, 10)); // Solo el Top 10 para el gráfico visual

        // Botón Ver Todos de Inyección
        const btnVerTodosIny = document.getElementById('btn-ver-todos-iny');
        if (btnVerTodosIny) {
            btnVerTodosIny.onclick = () => mostrarModalTodosInyeccion(inyeccionOps);
        }

        renderChartMaquinas(data.maquinas);
        renderChartTendencia(data.tendencia);
        renderChartPNC(data.kpis.scrap_detalle);

        // 4. Detalle Scrap Almacén
        renderScrapAlmacenDetalle(data.kpis.scrap_almacen_desglose || []);

        // 5. Tabla Pulido (Deep Ranking)
        renderTablaPulido(data.rankings.pulido_profundo);
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
        if (chartOperadores) chartOperadores.destroy();
        chartOperadores = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ops.map(o => o.nombre),
                datasets: [{ label: 'Buenas', data: ops.map(o => o.valor), backgroundColor: colores.azul[0], borderRadius: 6 }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        // Aquí, 'ops' es el array que pasamos a renderChartInyeccion (que ya está limitado a 10)
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
                }
            }
        });
    }

    function renderChartMaquinas(maqs) {
        const ctx = document.getElementById('chartMaquinas');
        if (!ctx) return;
        if (chartMaquinas) chartMaquinas.destroy();
        chartMaquinas = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: maqs.map(m => m.maquina),
                datasets: [{ data: maqs.map(m => m.valor), backgroundColor: colores.verde, borderWidth: 2 }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } }, cutout: '70%' }
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
                labels: ['Inyección', 'Pulido', 'Almacén'],
                datasets: [{ data: [pnc.inyeccion, pnc.pulido, pnc.almacen], backgroundColor: ['#3b82f6cc', '#10b981cc', '#ef4444cc'] }]
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
            const html = `
                <div class="list-group-item d-flex justify-content-between align-items-center py-2" style="border-left: 3px solid #ef4444;">
                    <div class="text-truncate" style="max-width: 75%;" title="${item.producto}">
                        <span class="text-muted me-1 fw-bold fs-6">${index + 1}.</span> 
                        <span class="fw-medium">${item.producto}</span>
                    </div>
                    <span class="badge bg-danger rounded-pill">${item.cantidad.toLocaleString()} Pz</span>
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

        // Ordenar por piezas buenas desc
        const sortedOps = operadoras.sort((a, b) => profundo[b].buenas - profundo[a].buenas);

        sortedOps.forEach((op, idx) => {
            const dataOp = profundo[op];
            const mix = dataOp.mix || [];
            const buenas = dataOp.buenas || 0;
            const pnc = dataOp.pnc || 0;

            const total = buenas + pnc;
            const eficiencia = total > 0 ? Math.round((buenas / total) * 100) : 100;
            const efColor = eficiencia > 95 ? 'success' : (eficiencia > 85 ? 'warning' : 'danger');

            const topProd = mix[0] ? mix[0].prod : "N/A";

            // Preparar el detalle para el alert (escapar saltos de línea y comillas simples)
            const detalleMix = mix.slice(0, 5).map(p => `${p.prod}: ${p.qty.toLocaleString()}`).join('\\n').replace(/'/g, "\\'");

            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            tr.onclick = (e) => {
                // Evitar que el botón de 'Ver Mix' dispare esto también si hacen clic en él
                if (e.target.closest('button')) return;
                const insightText = dataOp.insight || "Sin insights disponibles para Pulido.";
                mostrarModalOperador(op, buenas, 'Pulido', insightText, detalleMix);
            };
            tr.classList.add('hover-scale');
            tr.innerHTML = `
                <td class="ps-4"><span class="badge bg-light text-dark border">${idx + 1}</span></td>
                <td>
                    <div class="fw-bold">${op}</div>
                    <small class="text-muted">Expertiz: <span class="badge bg-info text-white">${topProd}</span></small>
                </td>
                <td class="text-center fw-bold text-success">${buenas.toLocaleString()}</td>
                <td class="text-center fw-bold text-danger">${pnc.toLocaleString()}</td>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="progress flex-grow-1" style="height: 8px; border-radius: 10px; background-color: #e2e8f0;">
                            <div class="progress-bar bg-${efColor}" style="width: ${eficiencia}%"></div>
                        </div>
                        <span class="fw-bold text-${efColor}" style="min-width: 40px;">${eficiencia}%</span>
                    </div>
                </td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-primary py-1 px-3" onclick="alert('Mix de producción de ${op}:\n\n${detalleMix}')">
                        <i class="fas fa-list-ol me-1"></i> Ver Mix
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }


    function iniciar() {
        console.log("🚀 Iniciando BI Dashboard...");

        // Predeterminar fechas (Últimos 30 días para ver más historial por defecto)
        const hoy = new Date();
        const hace30 = new Date();
        hace30.setDate(hoy.getDate() - 30);

        const f_desde = document.getElementById('db-fecha-desde');
        const f_hasta = document.getElementById('db-fecha-hasta');

        if (f_desde && !f_desde.value) f_desde.value = hace30.toISOString().split('T')[0];
        if (f_hasta && !f_hasta.value) f_hasta.value = hoy.toISOString().split('T')[0];

        cargarDatos();

        if (!window._dbTimer) {
            window._dbTimer = setInterval(cargarDatos, 600000); // 10 min refresh
        }
    }

    function mostrarModalOperador(nombre, totalOks, proceso, insightStr, detalleMix = null) {

        let extraHtml = '';
        if (detalleMix) {
            const mixLines = detalleMix.split('\\n').map(l => `<li>${l}</li>`).join('');
            extraHtml = `
                <div class="mt-3 text-start">
                    <h6 class="fw-bold"><i class="fas fa-boxes text-secondary"></i> Top Productos Fabricados:</h6>
                    <ul class="list-unstyled ms-3 small text-muted">
                        ${mixLines}
                    </ul>
                </div>
            `;
        }

        Swal.fire({
            title: `<i class="fas fa-user-circle text-primary"></i> Resumen de Operador`,
            html: `
                <div class="text-start mb-3">
                    <div class="p-3 bg-light rounded border-start border-4 border-primary shadow-sm mb-3">
                        <span class="fst-italic text-secondary"><i class="fas fa-lightbulb text-warning"></i> "${insightStr}"</span>
                    </div>
                
                    <p class="mb-1"><strong>Operador:</strong> ${nombre}</p>
                    <p class="mb-1"><strong>Proceso:</strong> ${proceso}</p>
                    <p class="mb-1"><strong>Producción Total:</strong> <span class="badge bg-success">${totalOks.toLocaleString()}</span> piezas</p>
                </div>
                ${extraHtml}
            `,
            icon: null,
            confirmButtonText: 'Cerrar',
            confirmButtonColor: '#3b82f6',
            width: '32em'
        });
    }

    function mostrarModalTodosInyeccion(ops) {
        if (!ops || ops.length === 0) return Swal.fire("Aviso", "No hay operadores de inyección", "info");

        // Construir tabla
        let rowsHtml = ops.map((op, idx) => {
            const topProd = op.mix && op.mix[0] ? op.mix[0].prod : "N/A";
            const detalleMixText = op.mix ? op.mix.slice(0, 5).map(p => `${p.prod}: ${p.qty.toLocaleString()}`).join('\\n').replace(/'/g, "\\'") : '';
            return `
                <tr style="cursor: pointer" onclick="ModuloDashboard.mostrarModalOperador('${op.nombre.replace(/'/g, "\\'")}', ${op.valor}, 'Inyección', '${(op.insight || '').replace(/'/g, "\\'")}', '${detalleMixText}')">
                    <td class="ps-3"><span class="badge bg-light text-dark border">${idx + 1}</span></td>
                    <td class="text-start">
                        <div class="fw-bold">${op.nombre}</div>
                        <small class="text-muted">Expertiz: <span class="badge bg-info text-white">${topProd}</span></small>
                    </td>
                    <td class="text-center fw-bold text-success">${op.valor.toLocaleString()}</td>
                </tr>
            `;
        }).join('');

        Swal.fire({
            title: `<i class="fas fa-users text-primary mb-2"></i><br>Todos los Operadores (Inyección)`,
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
            width: '36em',
            showConfirmButton: true,
            confirmButtonText: 'Cerrar',
            confirmButtonColor: '#3b82f6'
        });
    }

    return {
        inicializar: iniciar,
        refrescar: cargarDatos,
        mostrarModalOperador: mostrarModalOperador
    };
})();
