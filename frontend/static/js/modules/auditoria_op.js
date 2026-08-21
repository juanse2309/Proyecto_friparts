// auditoria_op.js - Auditoría de Órdenes de Producción de INYECCIÓN
// Consume GET /api/auditoria/conciliacion-ops (solo lectura). No escribe nada.
//
// Muestra las OP de inyección de World Office que no tienen reporte en la app,
// con la señal EPT al lado: si World Office registró la entrada a inventario,
// la producción sí ocurrió y lo que falta es el reporte en planta.

class AuditoriaOpModule {
    constructor() {
        this.endpoint = '/api/auditoria/conciliacion-ops';
        this.filas = [];
        this.porPagina = 50;
        this.pagina = 1;
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

            this.filas = payload.data.faltantes_inyeccion || [];
            this.pagina = 1;
            this._render();
        } catch (error) {
            console.error('❌ [AuditoriaOP] Error de red consultando conciliación de OP:', error);
            this._mostrarError('No se pudo contactar al servidor. Verifica tu conexión e intenta de nuevo.');
        }
    }

    irAPagina(numero) {
        this.pagina = numero;
        this._render();
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
        this._pintarFila('<i class="fas fa-spinner fa-spin fa-2x text-primary"></i>', 'text-muted');
        this._limpiarPaginacion();
    }

    _mostrarError(mensaje) {
        this._pintarFila(
            `<i class="fas fa-exclamation-triangle me-2"></i>${this._escapar(mensaje)}`, 'text-danger');
        this._actualizarContador('—');
        this._limpiarPaginacion();
    }

    _pintarFila(contenidoHtml, claseTexto) {
        const tbody = document.getElementById('auditoria-op-faltantes-body');
        if (!tbody) return;
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-5 ${claseTexto}">${contenidoHtml}</td></tr>`;
    }

    _actualizarContador(valor) {
        const el = document.getElementById('auditoria-op-faltantes-count');
        if (el) el.textContent = valor;
    }

    _limpiarPaginacion() {
        const el = document.getElementById('auditoria-op-faltantes-paginacion');
        if (el) el.innerHTML = '';
    }

    // --- Render ---

    _render() {
        this._actualizarContador(this.filas.length.toLocaleString('es-CO'));

        const tbody = document.getElementById('auditoria-op-faltantes-body');
        if (!tbody) return;

        if (this.filas.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-success">
                <i class="fas fa-check-circle me-2"></i>Todas las OP de inyección están reportadas.</td></tr>`;
            this._limpiarPaginacion();
            return;
        }

        const totalPaginas = Math.max(1, Math.ceil(this.filas.length / this.porPagina));
        if (this.pagina > totalPaginas) this.pagina = totalPaginas;
        if (this.pagina < 1) this.pagina = 1;

        const inicio = (this.pagina - 1) * this.porPagina;
        const visibles = this.filas.slice(inicio, inicio + this.porPagina);

        tbody.innerHTML = visibles.map(f => this._fila(f)).join('');
        this._renderPaginacion(totalPaginas);
    }

    _fila(f) {
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
     */
    _badgeEpt(f) {
        const ept = f.cantidad_ept === null || f.cantidad_ept === undefined
            ? null : Number(f.cantidad_ept);

        if (f.estado_ept === 'SIN_EPT') {
            return '<span class="badge bg-secondary-subtle text-secondary border" title="World Office no registró entrada a inventario para esta OP">Sin EPT</span>';
        }
        if (f.estado_ept === 'COMPLETA') {
            return `<span class="badge bg-success-subtle text-success border" title="World Office registró la entrada completa: se produjo, falta el reporte en la app">Entró ${ept.toLocaleString('es-CO')}</span>`;
        }
        const dif = Number(f.diferencia_ept || 0);
        const signo = dif > 0 ? '+' : '';
        const clase = f.estado_ept === 'PARCIAL' ? 'warning' : 'info';
        return `<span class="badge bg-${clase}-subtle text-${clase}-emphasis border" title="Cantidad que entró a inventario vs. la ordenada en la OP">${ept.toLocaleString('es-CO')} (${signo}${dif.toLocaleString('es-CO')})</span>`;
    }

    _renderPaginacion(totalPaginas) {
        const contenedor = document.getElementById('auditoria-op-faltantes-paginacion');
        if (!contenedor) return;

        if (totalPaginas <= 1) {
            contenedor.innerHTML = '';
            return;
        }

        const boton = (etiqueta, pagina, deshabilitado, activo = false) => `
            <li class="page-item ${deshabilitado ? 'disabled' : ''} ${activo ? 'active' : ''}">
                <a class="page-link" href="#" onclick="event.preventDefault(); window.ModuloAuditoriaOP.irAPagina(${pagina})">${etiqueta}</a>
            </li>`;

        const RANGO = 1;
        const desde = Math.max(1, this.pagina - RANGO);
        const hasta = Math.min(totalPaginas, this.pagina + RANGO);

        let html = '<nav><ul class="pagination pagination-sm justify-content-center flex-wrap mb-0">';
        html += boton('&laquo;', this.pagina - 1, this.pagina === 1);
        if (desde > 1) {
            html += boton('1', 1, false);
            if (desde > 2) html += '<li class="page-item disabled"><span class="page-link">…</span></li>';
        }
        for (let p = desde; p <= hasta; p++) html += boton(String(p), p, false, p === this.pagina);
        if (hasta < totalPaginas) {
            if (hasta < totalPaginas - 1) html += '<li class="page-item disabled"><span class="page-link">…</span></li>';
            html += boton(String(totalPaginas), totalPaginas, false);
        }
        html += boton('&raquo;', this.pagina + 1, this.pagina === totalPaginas);
        html += '</ul></nav>';
        html += `<p class="text-center text-muted small mt-2 mb-0">Página ${this.pagina} de ${totalPaginas} — ${this.filas.length.toLocaleString('es-CO')} OP de inyección sin reportar</p>`;

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
