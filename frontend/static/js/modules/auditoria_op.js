// auditoria_op.js - Auditoría de Órdenes de Producción de INYECCIÓN
// Consume GET /api/auditoria/conciliacion-ops (solo lectura). No escribe nada.
//
// Dos direcciones, agrupadas por OP (una OP trae varias referencias -- 379
// OPs distintas explican las 1.021 filas de faltantes, promedio 2.7 c/u; una
// llegó a traer 84). Cada grupo se despliega al hacer clic para ver el
// detalle por producto:
//   - Faltantes: OP de World Office que no tienen reporte en la app.
//     Trae la señal EPT (entrada real a inventario) por item, y un resumen
//     agregado en la fila colapsada.
//   - Reportadas sin OP: reportes de la app cuya OP no existe en World
//     Office -- para detectar OP inventadas o mal digitadas por el operario.

class AuditoriaOpModule {
    constructor() {
        this.endpoint = '/api/auditoria/conciliacion-ops';
        this.porPagina = 50; // OPs por pagina, no filas -- ver _agruparPorOp

        this.faltantes = [];
        this.paginaFaltantes = 1;
        this.expandidasFaltantes = new Set();

        this.sinWo = [];
        this.paginaSinWo = 1;
        this.expandidasSinWo = new Set();
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
            this.expandidasFaltantes.clear();

            this.sinWo = payload.data.reportadas_sin_wo || [];
            this.paginaSinWo = 1;
            this.expandidasSinWo.clear();

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

    toggleFaltante(numeroOp) {
        this._toggle(this.expandidasFaltantes, numeroOp);
        this._renderFaltantes();
    }

    toggleSinWo(numeroOp) {
        this._toggle(this.expandidasSinWo, numeroOp);
        this._renderSinWo();
    }

    _toggle(set, clave) {
        if (set.has(clave)) set.delete(clave);
        else set.add(clave);
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

    // --- Agrupación por OP (compartida por ambas tablas) ---

    _agruparPorOp(lista, campoOp) {
        const grupos = new Map();
        lista.forEach(item => {
            const clave = item[campoOp];
            if (!grupos.has(clave)) grupos.set(clave, []);
            grupos.get(clave).push(item);
        });
        // Mantener el orden de aparicion (ya viene ordenado por fecha desde el backend)
        return [...grupos.entries()].map(([numeroOp, items]) => ({ numeroOp, items }));
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

        const grupos = this._agruparPorOp(this.faltantes, 'numero_op');
        const { visibles, totalPaginas } = this._paginar(grupos, this.paginaFaltantes, v => this.paginaFaltantes = v);

        tbody.innerHTML = visibles.map(g => this._grupoFaltante(g)).join('');
        this._renderPaginacion('auditoria-op-faltantes-paginacion', this.paginaFaltantes, totalPaginas,
            grupos.length, 'irAPaginaFaltantes', `OP (${this.faltantes.length.toLocaleString('es-CO')} referencias en total)`);
    }

    _grupoFaltante(grupo) {
        const { numeroOp, items } = grupo;
        const expandido = this.expandidasFaltantes.has(numeroOp);

        if (items.length === 1) {
            return this._filaFaltanteDetalle(items[0], false);
        }

        const totalCant = items.reduce((s, f) => s + Number(f.cantidad_wo || 0), 0);
        const resumenEpt = this._resumenEpt(items);
        const primero = items[0];
        const caret = expandido ? 'fa-chevron-down' : 'fa-chevron-right';

        let html = `
            <tr style="cursor: pointer;" onclick="window.ModuloAuditoriaOP.toggleFaltante('${this._escapar(numeroOp)}')">
                <td class="fw-bold text-dark">
                    <i class="fas ${caret} text-secondary me-2 small"></i>
                    <i class="fas fa-hashtag text-secondary me-1"></i>${this._escapar(numeroOp)}
                </td>
                <td><span class="badge bg-light text-dark border">${items.length} productos</span></td>
                <td class="text-center">${totalCant.toLocaleString('es-CO')}</td>
                <td class="text-center">${resumenEpt}</td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">
                        <i class="fas fa-warehouse me-1 text-secondary"></i>${this._escapar(primero.bodega) || 'N/D'}
                    </span>
                </td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">
                        <i class="fas fa-calendar-alt me-1 text-secondary"></i>${this._escapar(primero.fecha) || 'N/D'}
                    </span>
                </td>
            </tr>`;

        if (expandido) {
            html += items.map(f => this._filaFaltanteDetalle(f, true)).join('');
        }
        return html;
    }

    _filaFaltanteDetalle(f, esHijo) {
        const cant = Number(f.cantidad_wo || 0).toLocaleString('es-CO');
        const claseHijo = esHijo ? ' bg-light bg-opacity-50' : '';
        const opCelda = esHijo
            ? `<span class="text-muted small ps-4"><i class="fas fa-level-up-alt fa-rotate-90 me-2"></i>${this._escapar(f.numero_op)}</span>`
            : `<i class="fas fa-hashtag text-secondary me-1"></i>${this._escapar(f.numero_op)}`;
        return `
            <tr class="${claseHijo}">
                <td class="${esHijo ? '' : 'fw-bold text-dark'}">${opCelda}</td>
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

    /** Resumen compacto de estados EPT para la fila colapsada de un grupo. */
    _resumenEpt(items) {
        const conteo = { COMPLETA: 0, PARCIAL: 0, EXCEDE: 0, SIN_EPT: 0 };
        items.forEach(f => { conteo[f.estado_ept] = (conteo[f.estado_ept] || 0) + 1; });

        const partes = [];
        if (conteo.COMPLETA) partes.push(`<span class="badge bg-success-subtle text-success border" title="World Office registró la entrada completa">${conteo.COMPLETA} completas</span>`);
        if (conteo.PARCIAL) partes.push(`<span class="badge bg-warning-subtle text-warning-emphasis border" title="Entró menos de lo ordenado">${conteo.PARCIAL} parciales</span>`);
        if (conteo.EXCEDE) partes.push(`<span class="badge bg-info-subtle text-info-emphasis border" title="Entró más de lo ordenado">${conteo.EXCEDE} exceden</span>`);
        if (conteo.SIN_EPT) partes.push(`<span class="badge bg-secondary-subtle text-secondary border" title="Sin entrada registrada">${conteo.SIN_EPT} sin EPT</span>`);
        return partes.join(' ');
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

        const grupos = this._agruparPorOp(this.sinWo, 'orden_produccion_reportada');
        const { visibles, totalPaginas } = this._paginar(grupos, this.paginaSinWo, v => this.paginaSinWo = v);

        tbody.innerHTML = visibles.map(g => this._grupoSinWo(g)).join('');
        this._renderPaginacion('auditoria-op-sinwo-paginacion', this.paginaSinWo, totalPaginas,
            grupos.length, 'irAPaginaSinWo', `OP reportadas (${this.sinWo.length.toLocaleString('es-CO')} referencias en total)`);
    }

    _grupoSinWo(grupo) {
        const { numeroOp, items } = grupo;
        const expandido = this.expandidasSinWo.has(numeroOp);

        if (items.length === 1) {
            return this._filaSinWoDetalle(items[0], false);
        }

        const totalCant = items.reduce((s, f) => s + Number(f.cantidad_reportada || 0), 0);
        const primero = items[0];
        const responsables = new Set(items.map(f => f.responsable).filter(Boolean));
        const responsable = responsables.size === 1
            ? this._escapar(primero.responsable)
            : (responsables.size > 1 ? `${responsables.size} operarios` : '<span class="text-muted">Sin asignar</span>');
        const caret = expandido ? 'fa-chevron-down' : 'fa-chevron-right';

        let html = `
            <tr style="cursor: pointer;" onclick="window.ModuloAuditoriaOP.toggleSinWo('${this._escapar(numeroOp)}')">
                <td class="fw-bold text-danger">
                    <i class="fas ${caret} text-secondary me-2 small"></i>
                    <i class="fas fa-question-circle me-1"></i>${this._escapar(numeroOp)}
                </td>
                <td><span class="badge bg-light text-dark border">${items.length} productos</span></td>
                <td class="text-center">${totalCant.toLocaleString('es-CO')}</td>
                <td>${responsable}</td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">
                        <i class="fas fa-calendar-alt me-1 text-secondary"></i>${this._escapar(primero.fecha) || 'N/D'}
                    </span>
                </td>
            </tr>`;

        if (expandido) {
            html += items.map(f => this._filaSinWoDetalle(f, true)).join('');
        }
        return html;
    }

    _filaSinWoDetalle(f, esHijo) {
        const cant = Number(f.cantidad_reportada || 0).toLocaleString('es-CO');
        const responsable = this._escapar(f.responsable) || '<span class="text-muted">Sin asignar</span>';
        const claseHijo = esHijo ? ' bg-light bg-opacity-50' : '';
        const opCelda = esHijo
            ? `<span class="text-muted small ps-4"><i class="fas fa-level-up-alt fa-rotate-90 me-2"></i>${this._escapar(f.orden_produccion_reportada)}</span>`
            : `<i class="fas fa-question-circle me-1"></i>${this._escapar(f.orden_produccion_reportada)}`;
        return `
            <tr class="${claseHijo}">
                <td class="${esHijo ? '' : 'fw-bold text-danger'}">${opCelda}</td>
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

    // --- Paginación (cliente, compartida por ambas tablas -- pagina por OPs, no por filas) ---

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
