// auditoria_op.js - Auditoría de Órdenes de Producción de INYECCIÓN
// Consume GET /api/auditoria/conciliacion-ops (solo lectura). No escribe nada.
//
// Dos direcciones:
//   - Faltantes: OP de World Office que no tienen reporte en la app.
//     Trae la señal EPT (entrada real a inventario) para saber si ya se
//     produjo y solo falta el reporte, o si tampoco entró a inventario.
//   - Reportadas sin OP: reportes de la app cuya OP no existe en World
//     Office -- para detectar OP inventadas o mal digitadas por el operario.

class AuditoriaOpModule {
    constructor() {
        this.endpoint = '/api/auditoria/conciliacion-ops';
        this.porPagina = 50;

        this.faltantes = [];
        this.paginaFaltantes = 1;

        this.sinWo = [];
        this.paginaSinWo = 1;
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

            this.faltantes = payload.data.faltantes_inyeccion || [];
            this.paginaFaltantes = 1;
            this.sinWo = payload.data.reportadas_sin_wo || [];
            this.paginaSinWo = 1;

            this._renderFaltantes();
            this._renderSinWo();
        } catch (error) {
            console.error('❌ [AuditoriaOP] Error de red consultando conciliación de OP:', error);
            this._mostrarError('No se pudo contactar al servidor. Verifica tu conexión e intenta de nuevo.');
        }
    }

    irAPaginaFaltantes(numero) {
        this.paginaFaltantes = numero;
        this._renderFaltantes();
    }

    irAPaginaSinWo(numero) {
        this.paginaSinWo = numero;
        this._renderSinWo();
    }

    // --- HTTP ---

    _headersAuth() {
        const pwaToken = localStorage.getItem('pwa_token');
        const headers = { 'Accept': 'application/json' };
        if (pwaToken) headers['Authorization'] = `Bearer ${pwaToken}`;
        return headers;
    }

    // --- Estados ---

    _mostrarCargando() {
        this._pintarFila('auditoria-op-faltantes-body', 6,
            '<i class="fas fa-spinner fa-spin fa-2x text-primary"></i>', 'text-muted');
        this._pintarFila('auditoria-op-sinwo-body', 5,
            '<i class="fas fa-spinner fa-spin fa-2x text-primary"></i>', 'text-muted');
        this._limpiarPaginacion('auditoria-op-faltantes-paginacion');
        this._limpiarPaginacion('auditoria-op-sinwo-paginacion');
    }

    _mostrarError(mensaje) {
        const contenido = `<i class="fas fa-exclamation-triangle me-2"></i>${this._escapar(mensaje)}`;
        this._pintarFila('auditoria-op-faltantes-body', 6, contenido, 'text-danger');
        this._pintarFila('auditoria-op-sinwo-body', 5, contenido, 'text-danger');
        this._actualizarContador('auditoria-op-faltantes-count', '—');
        this._actualizarContador('auditoria-op-sinwo-count', '—');
        this._limpiarPaginacion('auditoria-op-faltantes-paginacion');
        this._limpiarPaginacion('auditoria-op-sinwo-paginacion');
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

    _limpiarPaginacion(idContenedor) {
        const el = document.getElementById(idContenedor);
        if (el) el.innerHTML = '';
    }

    // --- Tabla A: OP de World Office sin reporte en planta ---

    _renderFaltantes() {
        this._actualizarContador('auditoria-op-faltantes-count', this.faltantes.length.toLocaleString('es-CO'));

        const tbody = document.getElementById('auditoria-op-faltantes-body');
        if (!tbody) return;

        if (this.faltantes.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-success">
                <i class="fas fa-check-circle me-2"></i>Todas las OP de inyección están reportadas.</td></tr>`;
            this._limpiarPaginacion('auditoria-op-faltantes-paginacion');
            return;
        }

        const { visibles, totalPaginas } = this._paginar(this.faltantes, this.paginaFaltantes, v => this.paginaFaltantes = v);
        tbody.innerHTML = visibles.map(f => this._filaFaltante(f)).join('');
        this._renderPaginacion('auditoria-op-faltantes-paginacion', this.paginaFaltantes, totalPaginas,
            this.faltantes.length, 'irAPaginaFaltantes', 'OP de inyección sin reportar');
    }

    _filaFaltante(f) {
        const cant = Number(f.cantidad_wo || 0).toLocaleString('es-CO');
        return `
            <tr>
                <td class="fw-bold text-dark"><i class="fas fa-hashtag text-secondary me-1"></i>${this._escapar(f.numero_op)}</td>
                <td>${this._escapar(f.codigo_producto)}</td>
                <td class="text-center">${cant}</td>
                <td class="text-center">${this._badgeEpt(f)}</td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">
                        <i class="fas fa-warehouse me-1 text-secondary"></i>${this._escapar(f.bodega) || 'N/D'}
                    </span>
                </td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">
                        <i class="fas fa-calendar-alt me-1 text-secondary"></i>${this._escapar(f.fecha) || 'N/D'}
                    </span>
                </td>
            </tr>`;
    }

    /**
     * La señal EPT es la que da la lectura accionable:
     *  - COMPLETA -> World Office ya registró toda la entrada: se produjo, falta el reporte en la app.
     *  - PARCIAL / EXCEDE -> entró a inventario una cantidad distinta a la ordenada.
     *  - SIN_EPT -> no hay entrada registrada: posiblemente nunca se produjo.
     * Se muestra el numero de documento EPT (si existe) para que planta lo
     * pueda ubicar directo en World Office.
     */
    _badgeEpt(f) {
        const numEpt = f.numero_ept ? ` <span class="text-muted small">(EPT ${this._escapar(f.numero_ept)})</span>` : '';

        if (f.estado_ept === 'SIN_EPT') {
            return '<span class="badge bg-secondary-subtle text-secondary border" title="World Office no registró entrada a inventario para esta OP">Sin EPT</span>';
        }

        const ept = Number(f.cantidad_ept);
        if (f.estado_ept === 'COMPLETA') {
            return `<span class="badge bg-success-subtle text-success border" title="World Office registró la entrada completa: se produjo, falta el reporte en la app">Entró ${ept.toLocaleString('es-CO')}</span>${numEpt}`;
        }
        const dif = Number(f.diferencia_ept || 0);
        const signo = dif > 0 ? '+' : '';
        const clase = f.estado_ept === 'PARCIAL' ? 'warning' : 'info';
        return `<span class="badge bg-${clase}-subtle text-${clase}-emphasis border" title="Cantidad que entró a inventario vs. la ordenada en la OP">${ept.toLocaleString('es-CO')} (${signo}${dif.toLocaleString('es-CO')})</span>${numEpt}`;
    }

    // --- Tabla B: reportado en la app, no existe en World Office ---

    _renderSinWo() {
        this._actualizarContador('auditoria-op-sinwo-count', this.sinWo.length.toLocaleString('es-CO'));

        const tbody = document.getElementById('auditoria-op-sinwo-body');
        if (!tbody) return;

        if (this.sinWo.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-success">
                <i class="fas fa-check-circle me-2"></i>Todo lo reportado en inyección tiene su OP en World Office.</td></tr>`;
            this._limpiarPaginacion('auditoria-op-sinwo-paginacion');
            return;
        }

        const { visibles, totalPaginas } = this._paginar(this.sinWo, this.paginaSinWo, v => this.paginaSinWo = v);
        tbody.innerHTML = visibles.map(f => this._filaSinWo(f)).join('');
        this._renderPaginacion('auditoria-op-sinwo-paginacion', this.paginaSinWo, totalPaginas,
            this.sinWo.length, 'irAPaginaSinWo', 'reportes sin OP válida en World Office');
    }

    _filaSinWo(f) {
        const cant = Number(f.cantidad_reportada || 0).toLocaleString('es-CO');
        const responsable = this._escapar(f.responsable) || '<span class="text-muted">Sin asignar</span>';
        return `
            <tr>
                <td class="fw-bold text-danger"><i class="fas fa-question-circle me-1"></i>${this._escapar(f.orden_produccion_reportada)}</td>
                <td>${this._escapar(f.codigo_producto)}</td>
                <td class="text-center">${cant}</td>
                <td>${responsable}</td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">
                        <i class="fas fa-calendar-alt me-1 text-secondary"></i>${this._escapar(f.fecha) || 'N/D'}
                    </span>
                </td>
            </tr>`;
    }

    // --- Paginación (cliente, compartida por ambas tablas) ---

    _paginar(lista, paginaActual, setPagina) {
        const totalPaginas = Math.max(1, Math.ceil(lista.length / this.porPagina));
        let pagina = paginaActual;
        if (pagina > totalPaginas) pagina = totalPaginas;
        if (pagina < 1) pagina = 1;
        setPagina(pagina);

        const inicio = (pagina - 1) * this.porPagina;
        return { visibles: lista.slice(inicio, inicio + this.porPagina), totalPaginas };
    }

    _renderPaginacion(idContenedor, paginaActual, totalPaginas, totalItems, metodo, etiquetaTotal) {
        const contenedor = document.getElementById(idContenedor);
        if (!contenedor) return;

        if (totalPaginas <= 1) {
            contenedor.innerHTML = '';
            return;
        }

        const boton = (etiqueta, pagina, deshabilitado, activo = false) => `
            <li class="page-item ${deshabilitado ? 'disabled' : ''} ${activo ? 'active' : ''}">
                <a class="page-link" href="#" onclick="event.preventDefault(); window.ModuloAuditoriaOP.${metodo}(${pagina})">${etiqueta}</a>
            </li>`;

        const RANGO = 1;
        const desde = Math.max(1, paginaActual - RANGO);
        const hasta = Math.min(totalPaginas, paginaActual + RANGO);

        let html = '<nav><ul class="pagination pagination-sm justify-content-center flex-wrap mb-0">';
        html += boton('&laquo;', paginaActual - 1, paginaActual === 1);
        if (desde > 1) {
            html += boton('1', 1, false);
            if (desde > 2) html += '<li class="page-item disabled"><span class="page-link">…</span></li>';
        }
        for (let p = desde; p <= hasta; p++) html += boton(String(p), p, false, p === paginaActual);
        if (hasta < totalPaginas) {
            if (hasta < totalPaginas - 1) html += '<li class="page-item disabled"><span class="page-link">…</span></li>';
            html += boton(String(totalPaginas), totalPaginas, false);
        }
        html += boton('&raquo;', paginaActual + 1, paginaActual === totalPaginas);
        html += '</ul></nav>';
        html += `<p class="text-center text-muted small mt-2 mb-0">Página ${paginaActual} de ${totalPaginas} — ${totalItems.toLocaleString('es-CO')} ${etiquetaTotal}</p>`;

        contenedor.innerHTML = html;
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
