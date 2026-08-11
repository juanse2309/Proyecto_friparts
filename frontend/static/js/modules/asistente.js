/**
 * Modulo Asistente de Dashboard (NL -> consulta de datos reales).
 * Vive dentro de la pagina del Dashboard (no es una pagina propia).
 * No dispara ninguna llamada de red hasta que el usuario escribe una pregunta.
 */
window.ModuloAsistente = (function () {
    let inicializado = false;
    let enviando = false;
    let contadorMensajes = 0;

    // Misma paleta de marca que dashboard.js (azul/verde/naranja/peligro) + un par
    // de acentos extra para series con mas de 4 categorias.
    const PALETA = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#6366f1'];

    const TITULOS_TOOL = {
        ventas_periodo: 'Ventas y producción del período',
        comparativo_mensual: 'Comparativo mensual',
        desglose_ventas_mensual: 'Desglose de ventas del mes',
        backorder_cliente: 'Backorder del cliente',
        ranking_operarios: 'Ranking de operarios',
        produccion_por_maquina: 'Producción por máquina',
        scrap_detalle: 'Detalle de scrap',
        productos_sin_rotacion: 'Productos sin rotación',
        cartera_estado: 'Estado de cartera',
        pnc_metricas: 'Métricas de calidad (PNC)',
        stock_producto: 'Stock del producto',
        stock_critico: 'Productos en stock crítico',
        analitica_comercial: 'Analítica comercial',
        nomina_consolidado: 'Consolidado de nómina',
        pedidos_pendientes_facturacion: 'Pedidos pendientes de facturar',
        alertas_abastecimiento: 'Alertas de abastecimiento',
        programacion_maquinas: 'Programación de máquinas',
        ensamble_tareas_pendientes: 'Tareas de ensamble pendientes',
    };

    // Claves que se muestran como dinero (COP) en vez de número plano.
    const CLAVES_DINERO = /dinero|monto|venta|precio|saldo|costo/i;

    function construirAuthHeaders(extraHeaders = {}) {
        const pwaToken = localStorage.getItem('pwa_token');
        const headers = { 'Content-Type': 'application/json', ...extraHeaders };
        if (pwaToken) headers['Authorization'] = `Bearer ${pwaToken}`;
        return headers;
    }

    function obtenerFiltrosActivos() {
        const desde = document.getElementById('db-fecha-desde')?.value || null;
        const hasta = document.getElementById('db-fecha-hasta')?.value || null;
        return { desde, hasta };
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = String(str ?? '');
        return div.innerHTML;
    }

    // Markdown ligero -> HTML seguro: negritas (**texto**) y listas con * o -.
    // Gemini responde con este formato de forma natural; antes se mostraba crudo
    // (con los asteriscos literales) porque solo se escapaba el texto sin interpretarlo.
    function formatearMarkdownLigero(texto) {
        const lineas = escapeHtml(texto).split(/\r?\n/);
        let html = '';
        let dentroDeLista = false;

        const cerrarLista = () => { if (dentroDeLista) { html += '</ul>'; dentroDeLista = false; } };

        for (const lineaRaw of lineas) {
            const linea = lineaRaw.trim();
            if (!linea) { cerrarLista(); continue; }

            const esItem = /^[*\-]\s+/.test(linea);
            if (esItem) {
                if (!dentroDeLista) { html += '<ul class="mb-1 ps-3">'; dentroDeLista = true; }
                html += `<li>${linea.replace(/^[*\-]\s+/, '')}</li>`;
            } else {
                cerrarLista();
                html += `<div>${linea}</div>`;
            }
        }
        cerrarLista();

        // Negritas: se aplica al final, sobre HTML ya escapado (los asteriscos no son
        // caracteres HTML especiales, así que sobreviven el escape intactos).
        return html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    }

    function formatearNumero(valor, esDinero) {
        const n = Number(valor) || 0;
        const texto = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(n);
        return esDinero ? `$${texto}` : texto;
    }

    function agregarMensaje(html, tipo) {
        const lista = document.getElementById('asistente-mensajes');
        if (!lista) return null;
        const wrapper = document.createElement('div');
        wrapper.className = `asistente-msg asistente-msg-${tipo}`;
        wrapper.innerHTML = html;
        lista.appendChild(wrapper);
        lista.scrollTop = lista.scrollHeight;
        return wrapper;
    }

    // ── Extraccion generica de una serie graficable a partir del payload de datos ──
    function buscarSerieEn(valor, profundidad = 0) {
        if (profundidad > 2 || valor == null) return null;

        if (Array.isArray(valor)) {
            if (valor.length && typeof valor[0] === 'object' && valor[0] !== null) {
                const keys = Object.keys(valor[0]);
                const labelKey = keys.find(k => typeof valor[0][k] === 'string') || keys[0];
                const valueKey = keys.find(k => typeof valor[0][k] === 'number');
                if (labelKey && valueKey) {
                    return {
                        labels: valor.map(r => String(r[labelKey] ?? '')),
                        values: valor.map(r => Number(r[valueKey]) || 0),
                        etiqueta: valueKey
                    };
                }
            }
            return null;
        }

        if (typeof valor === 'object') {
            const keys = Object.keys(valor);
            const numericKeys = keys.filter(k => typeof valor[k] === 'number');
            if (numericKeys.length >= 2 && numericKeys.length === keys.length) {
                return { labels: numericKeys, values: numericKeys.map(k => valor[k]), etiqueta: 'valor' };
            }
            for (const k of keys) {
                const sub = buscarSerieEn(valor[k], profundidad + 1);
                if (sub) return sub;
            }
        }
        return null;
    }

    function extraerSerieGrafica(datosPorTool) {
        if (!datosPorTool) return null;
        for (const nombreTool of Object.keys(datosPorTool)) {
            const serie = buscarSerieEn(datosPorTool[nombreTool]);
            if (serie) return { ...serie, toolName: nombreTool };
        }
        return null;
    }

    function renderizarGrafica(contenedor, tipoGrafica, serieOriginal) {
        // Top 10 + orden descendente para barras: mucho mas legible que 20+ categorias sin ordenar.
        let serie = serieOriginal;
        if (tipoGrafica === 'bar' && serie.labels.length > 1) {
            const combinado = serie.labels
                .map((label, i) => ({ label, valor: serie.values[i] }))
                .sort((a, b) => b.valor - a.valor)
                .slice(0, 10);
            serie = { ...serie, labels: combinado.map(c => c.label), values: combinado.map(c => c.valor) };
        }

        const esDinero = CLAVES_DINERO.test(serie.etiqueta || '');
        const titulo = TITULOS_TOOL[serie.toolName] || 'Resultado de la consulta';

        const canvasId = `asistente-chart-${++contadorMensajes}`;
        const wrap = document.createElement('div');
        wrap.style.cssText = 'width:100%;max-width:600px;height:280px;margin-top:0.6rem;background:#fff;border-radius:10px;padding:0.5rem;';
        wrap.innerHTML = `<canvas id="${canvasId}"></canvas>`;
        contenedor.appendChild(wrap);

        const ctx = document.getElementById(canvasId);
        if (!ctx || typeof Chart === 'undefined') return;

        const esLinea = tipoGrafica === 'line';
        const colores = serie.labels.map((_, i) => PALETA[i % PALETA.length]);

        new Chart(ctx, {
            type: esLinea ? 'line' : 'bar',
            data: {
                labels: serie.labels,
                datasets: [{
                    label: serie.etiqueta,
                    data: serie.values,
                    backgroundColor: esLinea ? 'rgba(59, 130, 246, 0.15)' : colores,
                    borderColor: esLinea ? '#3b82f6' : colores,
                    borderWidth: esLinea ? 2 : 0,
                    borderRadius: esLinea ? 0 : 6,
                    borderSkipped: false,
                    fill: esLinea,
                    tension: esLinea ? 0.35 : 0,
                    pointRadius: esLinea ? 3 : 0,
                    pointBackgroundColor: '#3b82f6',
                    maxBarThickness: 46,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: titulo, font: { size: 13, weight: '600' }, color: '#1e293b', padding: { bottom: 10 } },
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (item) => `${formatearNumero(item.parsed.y ?? item.parsed, esDinero)}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#f1f5f9' },
                        ticks: { callback: (v) => formatearNumero(v, esDinero) }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { autoSkip: true, maxRotation: 40, minRotation: 0 }
                    }
                }
            }
        });
    }

    // ── Render de tabla legible (no JSON crudo) ──────────────────────────────
    function construirTablaDesdeLista(lista) {
        const columnas = Object.keys(lista[0]);
        const filas = lista.slice(0, 50).map(fila => `
            <tr>${columnas.map(c => `<td class="px-2 py-1 border-bottom">${escapeHtml(fila[c])}</td>`).join('')}</tr>
        `).join('');
        return `
            <table class="table table-sm mb-0" style="font-size:0.8rem;">
                <thead><tr>${columnas.map(c => `<th class="px-2 py-1 text-muted text-uppercase" style="font-size:0.7rem;">${escapeHtml(c)}</th>`).join('')}</tr></thead>
                <tbody>${filas}</tbody>
            </table>
        `;
    }

    function construirTablaDesdeDict(obj) {
        const filas = Object.entries(obj).map(([clave, val]) => {
            const valorTexto = (val !== null && typeof val === 'object') ? JSON.stringify(val) : String(val);
            return `<tr><td class="px-2 py-1 border-bottom text-muted">${escapeHtml(clave)}</td><td class="px-2 py-1 border-bottom fw-semibold">${escapeHtml(valorTexto)}</td></tr>`;
        }).join('');
        return `<table class="table table-sm mb-0" style="font-size:0.8rem;"><tbody>${filas}</tbody></table>`;
    }

    function renderizarTabla(contenedor, datosPorTool) {
        const wrap = document.createElement('div');
        wrap.style.cssText = 'max-height:280px;overflow:auto;background:#f8fafc;border-radius:8px;margin-top:0.6rem;';

        const bloques = Object.entries(datosPorTool).map(([nombreTool, valor]) => {
            const titulo = TITULOS_TOOL[nombreTool] || nombreTool;
            let cuerpo;
            if (Array.isArray(valor) && valor.length && typeof valor[0] === 'object') {
                cuerpo = construirTablaDesdeLista(valor);
            } else if (valor && typeof valor === 'object') {
                // Busca la primera lista de objetos anidada (patrón común: {area, ranking:[...]})
                const listaAnidada = Object.values(valor).find(v => Array.isArray(v) && v.length && typeof v[0] === 'object');
                cuerpo = listaAnidada ? construirTablaDesdeLista(listaAnidada) : construirTablaDesdeDict(valor);
            } else {
                cuerpo = `<div class="px-2 py-1">${escapeHtml(valor)}</div>`;
            }
            return `<div class="px-2 pt-2"><div class="fw-bold text-muted small mb-1">${escapeHtml(titulo)}</div>${cuerpo}</div>`;
        }).join('');

        wrap.innerHTML = bloques;
        contenedor.appendChild(wrap);
    }

    async function enviarPregunta() {
        if (enviando) return;
        const input = document.getElementById('asistente-input');
        if (!input) return;
        const pregunta = input.value.trim();
        if (!pregunta) return;

        agregarMensaje(`<i class="fas fa-user-circle me-1"></i> ${escapeHtml(pregunta)}`, 'usuario');
        input.value = '';
        input.disabled = true;
        enviando = true;

        const btn = document.getElementById('asistente-btn-enviar');
        if (btn) btn.disabled = true;

        const pensando = agregarMensaje('<i class="fas fa-spinner fa-spin me-1"></i> Consultando datos...', 'cargando');

        try {
            const { desde, hasta } = obtenerFiltrosActivos();
            const res = await fetch('/api/dashboard/asistente/preguntar', {
                method: 'POST',
                credentials: 'include',
                headers: construirAuthHeaders(),
                body: JSON.stringify({ pregunta, desde, hasta })
            });
            const data = await res.json().catch(() => ({}));
            pensando?.remove();

            if (!res.ok || !data.success) {
                agregarMensaje(`<i class="fas fa-exclamation-triangle me-1"></i> ${escapeHtml(data.error || 'No fue posible procesar la pregunta.')}`, 'error');
                return;
            }

            const bubble = agregarMensaje(`<i class="fas fa-robot me-1"></i> ${formatearMarkdownLigero(data.respuesta)}`, 'asistente');

            if (bubble && data.datos && Object.keys(data.datos).length) {
                if (data.tipo_grafica === 'bar' || data.tipo_grafica === 'line') {
                    // El backend ya identifica el campo correcto a graficar (ver
                    // asistente_tools.py: jsonify ordena las claves alfabéticamente,
                    // así que adivinar "el primer campo numérico" del lado del cliente
                    // es poco confiable). El heurístico genérico queda solo de respaldo
                    // para tools futuras sin extractor explícito.
                    const serie = (data.serie_grafica && data.serie_grafica.labels && data.serie_grafica.labels.length)
                        ? data.serie_grafica
                        : extraerSerieGrafica(data.datos);
                    if (serie && serie.labels && serie.labels.length) {
                        renderizarGrafica(bubble, data.tipo_grafica, serie);
                    } else {
                        renderizarTabla(bubble, data.datos);
                    }
                } else if (data.tipo_grafica === 'table') {
                    renderizarTabla(bubble, data.datos);
                }
            }
        } catch (e) {
            console.error('[ModuloAsistente] Error consultando el asistente:', e);
            pensando?.remove();
            agregarMensaje('<i class="fas fa-exclamation-triangle me-1"></i> Error de conexión con el asistente.', 'error');
        } finally {
            input.disabled = false;
            if (btn) btn.disabled = false;
            enviando = false;
            input.focus();
        }
    }

    function inicializar() {
        if (inicializado) return;
        const btn = document.getElementById('asistente-btn-enviar');
        const input = document.getElementById('asistente-input');
        if (!btn || !input) return; // Card no presente en este rol/vista

        btn.addEventListener('click', enviarPregunta);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                enviarPregunta();
            }
        });

        inicializado = true;
    }

    return { inicializar };
})();
