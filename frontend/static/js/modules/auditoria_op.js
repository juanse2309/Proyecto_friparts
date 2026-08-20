// auditoria_op.js - Módulo de Auditoría de Conciliación de Órdenes de Producción (OP)
// Consume GET /api/auditoria/conciliacion-ops (solo lectura). No escribe nada.

class AuditoriaOpModule {
    constructor() {
        this.endpoint = '/api/auditoria/conciliacion-ops';
        this.faltantes = [];
        this.anomalias = [];
        this.porPagina = 50;
        this.paginaActual = { faltantes: 1, anomalias: 1 };
    }

    inicializar() {
        this.cargar();
    }

    async cargar() {
        this._mostrarCargando();

        try {
            const response = await fetch(this.endpoint, {
                headers: this._headersAuth(),
                credentials: 'include',
            });

            if (response.status === 401 || response.status === 403) {
                this._mostrarError('No tienes permisos para ver la auditoría de Órdenes de Producción.');
                return;
            }

            const payload = await response.json();

            if (!payload.success) {
                this._mostrarError(payload.error || 'Error al cargar la conciliación de OP.');
                return;
            }

            this.faltantes = payload.data.faltantes_en_planta || [];
            this.anomalias = payload.data.anomalias || [];
            // Cada cargar() es un dato nuevo -- si te quedaste en la página 40
            // de la carga anterior, no tiene sentido abrir ahí la nueva.
            this.paginaActual = { faltantes: 1, anomalias: 1 };

            this._renderFaltantes();
            this._renderAnomalias();
        } catch (error) {
            console.error('❌ [AuditoriaOP] Error de red consultando conciliación de OP:', error);
            this._mostrarError('No se pudo contactar al servidor. Verifica tu conexión e intenta de nuevo.');
        }
    }

    // --- Infraestructura HTTP ---

    _headersAuth() {
        const pwaToken = localStorage.getItem('pwa_token');
        const headers = { 'Accept': 'application/json' };
        if (pwaToken) headers['Authorization'] = `Bearer ${pwaToken}`;
        return headers;
    }

    // --- Estados (carga / error) ---

    _mostrarCargando() {
        this._pintarFila('auditoria-op-faltantes-body', 5,
            '<i class="fas fa-spinner fa-spin fa-2x text-primary"></i>', 'text-muted');
        this._pintarFila('auditoria-op-anomalias-body', 4,
            '<i class="fas fa-spinner fa-spin fa-2x text-primary"></i>', 'text-muted');
        this._limpiarPaginacion();
    }

    _mostrarError(mensaje) {
        const contenido = `<i class="fas fa-exclamation-triangle me-2"></i>${this._escapar(mensaje)}`;
        this._pintarFila('auditoria-op-faltantes-body', 5, contenido, 'text-danger');
        this._pintarFila('auditoria-op-anomalias-body', 4, contenido, 'text-danger');
        this._actualizarContador('auditoria-op-faltantes-count', '—');
        this._actualizarContador('auditoria-op-anomalias-count', '—');
        this._limpiarPaginacion();
    }

    _limpiarPaginacion() {
        ['faltantes', 'anomalias'].forEach(tabla => {
            const el = document.getElementById(`auditoria-op-${tabla}-paginacion`);
            if (el) el.innerHTML = '';
        });
    }

    _pintarFila(idTbody, colspan, contenidoHtml, claseTexto) {
        const tbody = document.getElementById(idTbody);
        if (!tbody) return;
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-5 ${claseTexto}">${contenidoHtml}</td></tr>`;
    }

    _actualizarContador(idBadge, valor) {
        const el = document.getElementById(idBadge);
        if (el) el.textContent = valor;
    }

    // --- Paginación (cliente) ---
    // Con miles de filas, pintar todo de una vez es lo que hace sentir
    // "pesado" el módulo (miles de <tr> en el DOM a la vez). Los datos ya
    // están completos en memoria desde el fetch -- aquí solo se recorta la
    // porción visible por página, nada de esto pega al backend de nuevo.

    _paginar(lista, tabla) {
        const totalPaginas = Math.max(1, Math.ceil(lista.length / this.porPagina));
        if (this.paginaActual[tabla] > totalPaginas) this.paginaActual[tabla] = totalPaginas;
        if (this.paginaActual[tabla] < 1) this.paginaActual[tabla] = 1;
        const pagina = this.paginaActual[tabla];
        const inicio = (pagina - 1) * this.porPagina;
        return { pagina, totalPaginas, itemsPagina: lista.slice(inicio, inicio + this.porPagina) };
    }

    irAPagina(tabla, numero) {
        this.paginaActual[tabla] = numero;
        if (tabla === 'faltantes') this._renderFaltantes();
        else this._renderAnomalias();
    }

    _renderPaginacion(tabla, paginaActual, totalPaginas, totalItems) {
        const contenedor = document.getElementById(`auditoria-op-${tabla}-paginacion`);
        if (!contenedor) return;

        if (totalPaginas <= 1) {
            contenedor.innerHTML = '';
            return;
        }

        const boton = (etiqueta, pagina, deshabilitado, activo = false) => `
            <li class="page-item ${deshabilitado ? 'disabled' : ''} ${activo ? 'active' : ''}">
                <a class="page-link" href="#" onclick="event.preventDefault(); window.ModuloAuditoriaOP.irAPagina('${tabla}', ${pagina})">${etiqueta}</a>
            </li>`;

        const RANGO = 1; // paginas vecinas visibles a cada lado de la actual
        const desde = Math.max(1, paginaActual - RANGO);
        const hasta = Math.min(totalPaginas, paginaActual + RANGO);

        let html = '<nav><ul class="pagination pagination-sm justify-content-center flex-wrap mb-0">';
        html += boton('&laquo;', paginaActual - 1, paginaActual === 1);

        if (desde > 1) {
            html += boton('1', 1, false);
            if (desde > 2) html += `<li class="page-item disabled"><span class="page-link">…</span></li>`;
        }
        for (let p = desde; p <= hasta; p++) {
            html += boton(String(p), p, false, p === paginaActual);
        }
        if (hasta < totalPaginas) {
            if (hasta < totalPaginas - 1) html += `<li class="page-item disabled"><span class="page-link">…</span></li>`;
            html += boton(String(totalPaginas), totalPaginas, false);
        }

        html += boton('&raquo;', paginaActual + 1, paginaActual === totalPaginas);
        html += '</ul></nav>';
        html += `<p class="text-center text-muted small mt-2 mb-0">Página ${paginaActual} de ${totalPaginas} — ${totalItems.toLocaleString('es-CO')} registros en total</p>`;

        contenedor.innerHTML = html;
    }

    // --- Tabla A: OPs Pendientes/Faltantes en Planta ---

    _renderFaltantes() {
        this._actualizarContador('auditoria-op-faltantes-count', this.faltantes.length);

        const tbody = document.getElementById('auditoria-op-faltantes-body');
        if (!tbody) return;

        if (this.faltantes.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-success">
                <i class="fas fa-check-circle me-2"></i>No hay OP pendientes de reportar en planta.</td></tr>`;
            this._renderPaginacion('faltantes', 1, 1, 0);
            return;
        }

        const { pagina, totalPaginas, itemsPagina } = this._paginar(this.faltantes, 'faltantes');
        tbody.innerHTML = itemsPagina.map(op => this._filaFaltante(op)).join('');
        this._renderPaginacion('faltantes', pagina, totalPaginas, this.faltantes.length);
    }

    _filaFaltante(op) {
        const cantidad = Number(op.cantidad_wo || 0).toLocaleString('es-CO');
        return `
            <tr>
                <td class="fw-bold text-dark"><i class="fas fa-hashtag text-secondary me-1"></i>${this._escapar(op.numero_op)}</td>
                <td>${this._escapar(op.codigo_producto)}</td>
                <td class="text-center">${cantidad}</td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">
                        <i class="fas fa-warehouse me-1 text-secondary"></i>${this._escapar(op.bodega) || 'N/D'}
                    </span>
                </td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">
                        <i class="fas fa-calendar-alt me-1 text-secondary"></i>${this._escapar(op.fecha) || 'N/D'}
                    </span>
                </td>
            </tr>`;
    }

    // --- Tabla B: Anomalías de Reporte ---

    _renderAnomalias() {
        this._actualizarContador('auditoria-op-anomalias-count', this.anomalias.length);

        const tbody = document.getElementById('auditoria-op-anomalias-body');
        if (!tbody) return;

        if (this.anomalias.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center py-4 text-success">
                <i class="fas fa-check-circle me-2"></i>Sin anomalías de reporte.</td></tr>`;
            this._renderPaginacion('anomalias', 1, 1, 0);
            return;
        }

        const { pagina, totalPaginas, itemsPagina } = this._paginar(this.anomalias, 'anomalias');
        tbody.innerHTML = itemsPagina.map(a => this._filaAnomalia(a)).join('');
        this._renderPaginacion('anomalias', pagina, totalPaginas, this.anomalias.length);
    }

    _filaAnomalia(anomalia) {
        const origenBadge = anomalia.origen === 'INYECCION'
            ? '<span class="badge bg-primary-subtle text-primary border">Inyección</span>'
            : '<span class="badge bg-info-subtle text-info border">Pulido</span>';
        const responsable = this._escapar(anomalia.responsable) || '<span class="text-muted">Sin asignar</span>';

        return `
            <tr>
                <td>${origenBadge}</td>
                <td class="fw-bold text-danger"><i class="fas fa-question-circle me-1"></i>${this._escapar(anomalia.orden_produccion_reportada)}</td>
                <td>${this._escapar(anomalia.codigo_producto)}</td>
                <td>${responsable}</td>
            </tr>`;
    }

    // --- Utilidad ---

    _escapar(valor) {
        if (valor === null || valor === undefined || valor === '') return '';
        const div = document.createElement('div');
        div.textContent = String(valor);
        return div.innerHTML;
    }
}

window.ModuloAuditoriaOP = new AuditoriaOpModule();
