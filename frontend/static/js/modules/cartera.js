// cartera.js - Módulo de Cartera (Cuentas por Cobrar / World Office)

const ModuloCartera = {
    clientes: [],
    ordenCampo: 'saldo_total',
    ordenAsc: false,
    _initDone: false,

    fmt: new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }),

    inicializar: function () {
        if (!this._initDone) {
            this._initDone = true;
            console.log('💰 Inicializando Módulo Cartera...');
        }
        this.cargar();
    },

    cargar: async function () {
        const tbody = document.getElementById('cartera-modulo-tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center py-5 text-muted"><i class="fas fa-spinner fa-spin fa-2x"></i></td></tr>';
        }

        try {
            const pwaToken = localStorage.getItem('pwa_token');
            const headers = { 'Accept': 'application/json' };
            if (pwaToken) headers['Authorization'] = `Bearer ${pwaToken}`;

            const [resumenRes, listadoRes] = await Promise.all([
                fetch('/api/dashboard/cartera', { headers, credentials: 'include' }),
                fetch('/api/cartera/listar', { headers, credentials: 'include' })
            ]);
            const resumen = await resumenRes.json();
            const listado = await listadoRes.json();

            if (resumen.success) {
                this.renderizarResumen(resumen.data);
            }

            if (listado.success) {
                this.clientes = listado.clientes || [];
                this.renderizarTabla();
            } else {
                throw new Error(listado.error || 'Error al obtener el listado de cartera');
            }
        } catch (error) {
            console.error('❌ Error cargando cartera:', error);
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="9" class="text-center py-5 text-danger">Error al cargar la cartera: ${error.message}</td></tr>`;
            }
        }
    },

    renderizarResumen: function (data) {
        const total = data.total_cartera || 0;
        const vencida = data.total_vencida || 0;
        const pct = total > 0 ? Math.round((vencida / total) * 100) : 0;

        const totalEl = document.getElementById('cartera-modulo-total-val');
        const vencidaEl = document.getElementById('cartera-modulo-vencida-val');
        const pctEl = document.getElementById('cartera-modulo-pct-val');

        if (totalEl) totalEl.textContent = this.fmt.format(total);
        if (vencidaEl) vencidaEl.textContent = this.fmt.format(vencida);
        if (pctEl) pctEl.textContent = `${pct}%`;
    },

    filtrar: function () {
        this.renderizarTabla();
    },

    ordenarPor: function (campo) {
        if (this.ordenCampo === campo) {
            this.ordenAsc = !this.ordenAsc;
        } else {
            this.ordenCampo = campo;
            this.ordenAsc = false;
        }
        this.renderizarTabla();
    },

    renderizarTabla: function () {
        const tbody = document.getElementById('cartera-modulo-tbody');
        if (!tbody) return;

        const buscador = document.getElementById('cartera-modulo-buscador');
        const query = (buscador?.value || '').trim().toUpperCase();

        let filtrados = this.clientes;
        if (query) {
            filtrados = filtrados.filter(c =>
                (c.nombre || '').toUpperCase().includes(query) ||
                (c.identificacion || '').toUpperCase().includes(query)
            );
        }

        const campo = this.ordenCampo;
        const asc = this.ordenAsc;
        filtrados = [...filtrados].sort((a, b) => {
            const va = campo === 'nombre' ? (a[campo] || '') : (parseFloat(a[campo]) || 0);
            const vb = campo === 'nombre' ? (b[campo] || '') : (parseFloat(b[campo]) || 0);
            if (va < vb) return asc ? -1 : 1;
            if (va > vb) return asc ? 1 : -1;
            return 0;
        });

        if (filtrados.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center py-5 text-muted">No se encontraron clientes con cartera pendiente.</td></tr>';
            return;
        }

        tbody.innerHTML = filtrados.map((c, idx) => `
            <tr style="cursor:pointer;" onclick="ModuloCartera.toggleDetalle('${c.identificacion}', ${idx})">
                <td class="fw-bold" data-label="Cliente" style="color:#1e293b;"><i class="fas fa-chevron-right me-2 text-muted" id="cartera-chevron-${idx}" style="font-size:0.7rem;"></i>${c.nombre}</td>
                <td data-label="NIT">${c.identificacion}</td>
                <td data-label="Vendedor"><span style="display:inline-block; max-width:170px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; vertical-align:middle;" title="${c.vendedor || ''}">${c.vendedor || 'N/A'}</span></td>
                <td class="text-end" data-label="Corriente">${this.fmt.format(c.corriente)}</td>
                <td class="text-end ${c.d1_30 > 0 ? 'text-warning fw-bold' : ''}" data-label="1-30 días">${this.fmt.format(c.d1_30)}</td>
                <td class="text-end ${c.d31_60 > 0 ? 'text-warning fw-bold' : ''}" data-label="31-60 días">${this.fmt.format(c.d31_60)}</td>
                <td class="text-end ${c.d61_90 > 0 ? 'text-danger fw-bold' : ''}" data-label="61-90 días">${this.fmt.format(c.d61_90)}</td>
                <td class="text-end ${c.mas_90 > 0 ? 'text-danger fw-bold' : ''}" data-label="+90 días">${this.fmt.format(c.mas_90)}</td>
                <td class="text-end fw-bold" data-label="Total">${this.fmt.format(c.saldo_total)}</td>
            </tr>
            <tr id="cartera-detalle-fila-${idx}" style="display:none;">
                <td colspan="9" class="p-0 td-detalle-anidado">
                    <div id="cartera-detalle-${idx}" class="p-3 bg-light"></div>
                </td>
            </tr>
        `).join('');
    },

    toggleDetalle: async function (identificacion, idx) {
        const fila = document.getElementById(`cartera-detalle-fila-${idx}`);
        const contenedor = document.getElementById(`cartera-detalle-${idx}`);
        const chevron = document.getElementById(`cartera-chevron-${idx}`);
        if (!fila || !contenedor) return;

        const abierto = fila.style.display !== 'none';
        if (abierto) {
            fila.style.display = 'none';
            if (chevron) chevron.className = 'fas fa-chevron-right me-2 text-muted';
            return;
        }

        fila.style.display = 'table-row';
        if (chevron) chevron.className = 'fas fa-chevron-down me-2 text-muted';

        if (contenedor.dataset.loaded === 'true') return;

        contenedor.innerHTML = '<div class="text-center py-2 text-muted"><i class="fas fa-spinner fa-spin"></i> Cargando facturas...</div>';

        try {
            const res = await fetch(`/api/cartera/cliente/${encodeURIComponent(identificacion)}`);
            const data = await res.json();

            if (!data.success || !data.facturas || data.facturas.length === 0) {
                contenedor.innerHTML = '<div class="text-muted small">No se encontraron facturas para este cliente.</div>';
                return;
            }

            const filasFacturas = data.facturas.map(f => `
                <tr>
                    <td>${f.documento}</td>
                    <td>${f.fecha_emision || 'N/A'}</td>
                    <td>${f.fecha_vencimiento || 'N/A'}</td>
                    <td class="text-center">${f.dias_mora ?? 'N/A'}</td>
                    <td class="text-end">${this.fmt.format(f.saldo)}</td>
                </tr>
            `).join('');

            contenedor.innerHTML = `
                <table class="table table-sm table-bordered bg-white mb-0">
                    <thead>
                        <tr><th>Documento</th><th>Emisión</th><th>Vence</th><th class="text-center">Días Mora</th><th class="text-end">Saldo</th></tr>
                    </thead>
                    <tbody>${filasFacturas}</tbody>
                </table>
            `;
            contenedor.dataset.loaded = 'true';
        } catch (error) {
            console.error('❌ Error cargando detalle de cliente:', error);
            contenedor.innerHTML = '<div class="text-danger small">Error al cargar el detalle.</div>';
        }
    },

    buscarFacturaWO: async function () {
        const input = document.getElementById('cartera-buscador-factura');
        const btn = document.getElementById('btn-buscar-factura-wo');
        const numero = (input?.value || '').trim();
        if (!numero) return;

        const icono = btn?.querySelector('i');
        const iconoOriginal = icono?.className;

        try {
            if (btn) btn.disabled = true;
            if (icono) icono.className = 'fas fa-spinner fa-spin';

            const pwaToken = localStorage.getItem('pwa_token');
            const headers = { 'Accept': 'application/json' };
            if (pwaToken) headers['Authorization'] = `Bearer ${pwaToken}`;

            const res = await fetch(`/api/cartera/factura/${encodeURIComponent(numero)}`, { headers, credentials: 'include' });
            const data = await res.json().catch(() => ({}));

            if (res.status === 404 || !data.success) {
                const mensaje = data.error || 'Factura no encontrada o no sincronizada.';
                if (window.Swal) {
                    Swal.fire({ icon: 'warning', title: 'Sin resultados', text: mensaje });
                } else {
                    alert(mensaje);
                }
                return;
            }

            this.renderModalFactura(data);
        } catch (error) {
            console.error('❌ Error buscando factura WO:', error);
            const mensaje = 'No fue posible consultar la factura.';
            if (window.Swal) {
                Swal.fire({ icon: 'error', title: 'Error', text: mensaje });
            } else {
                alert(mensaje);
            }
        } finally {
            if (btn) btn.disabled = false;
            if (icono && iconoOriginal) icono.className = iconoOriginal;
        }
    },

    renderModalFactura: function (data) {
        const existente = document.getElementById('modal-factura-wo');
        if (existente) existente.remove();

        const enc = data.encabezado || {};
        const items = data.items || [];
        const tot = data.totales || {};
        const fmtNum = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 });
        const naDash = '<span style="color:#cbd5e1;font-style:italic;">— N/D</span>';

        const campoEncabezado = (icono, etiqueta, valor) => `
            <div style="display:flex; align-items:flex-start; gap:10px; min-width:0;">
                <div style="width:30px;height:30px;border-radius:9px;background:#eef2ff;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;">
                    <i class="fas ${icono}" style="color:#4f46e5;font-size:0.8rem;"></i>
                </div>
                <div style="min-width:0;">
                    <div style="font-size:0.68rem;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:.04em;">${etiqueta}</div>
                    <div style="font-weight:600;color:#1e293b;word-break:break-word;">${valor}</div>
                </div>
            </div>`;

        const tieneSaldo = enc.saldo_pendiente !== null && enc.saldo_pendiente !== undefined;
        const saldoEsCero = tieneSaldo && Number(enc.saldo_pendiente) <= 0;

        const filasItems = items.map((it, idx) => `
            <tr style="background:${idx % 2 === 0 ? '#fff' : '#f8fafc'};">
                <td style="padding:10px 14px;"><span style="font-weight:600;color:#4f46e5;">${it.codigo_producto || ''}</span></td>
                <td style="padding:10px 14px;color:#475569;">${it.descripcion || naDash}</td>
                <td class="text-end" style="padding:10px 14px;">${fmtNum.format(it.cantidad || 0)}</td>
                <td class="text-end" style="padding:10px 14px;">${this.fmt.format(it.precio_unitario || 0)}</td>
                <td class="text-end" style="padding:10px 14px;font-weight:600;">${this.fmt.format(it.subtotal || 0)}</td>
                <td class="text-end" style="padding:10px 14px;">${it.iva !== null && it.iva !== undefined ? this.fmt.format(it.iva) : naDash}</td>
            </tr>
        `).join('');

        const modalHtml = `
            <div class="modal-overlay" id="modal-factura-wo" style="z-index: 10001; background: rgba(15,23,42,0.55); backdrop-filter: blur(2px); position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; padding: 20px;">
                <div class="modal-content" style="background: #fff; width: 100%; max-width: 860px; max-height: 90vh; overflow-y: auto; border-radius: 18px; box-shadow: 0 25px 60px -15px rgba(0,0,0,0.35); animation: zoomIn 0.25s ease;">
                    <div class="modal-header" style="background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%); padding: 22px 28px; display:flex; justify-content:space-between; align-items:center; position: sticky; top: 0; z-index: 1;">
                        <div style="display:flex; align-items:center; gap:14px;">
                            <div style="width:46px;height:46px;border-radius:13px;background:rgba(255,255,255,0.16);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                                <i class="fas fa-file-invoice-dollar" style="color:#fff;font-size:1.25rem;"></i>
                            </div>
                            <div>
                                <div style="color:rgba(255,255,255,0.65);font-size:0.7rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;">Factura World Office</div>
                                <div style="color:#fff;font-size:1.3rem;font-weight:700;line-height:1.2;">${enc.documento || ''}</div>
                            </div>
                        </div>
                        <button onclick="document.getElementById('modal-factura-wo').remove()" style="width:36px;height:36px;border-radius:10px;background:rgba(255,255,255,0.16);border:none;color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;" onmouseover="this.style.background='rgba(255,255,255,0.28)'" onmouseout="this.style.background='rgba(255,255,255,0.16)'">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body" style="padding: 26px 28px;">
                        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:20px 22px; margin-bottom:24px;">
                            <div class="row gy-3">
                                <div class="col-md-6">${campoEncabezado('fa-building', 'Cliente', enc.cliente || 'N/A')}</div>
                                <div class="col-md-6">${campoEncabezado('fa-id-card', 'Identificación', enc.identificacion || 'N/A')}</div>
                                <div class="col-md-6">${campoEncabezado('fa-user-tie', 'Vendedor', enc.vendedor || 'N/A')}</div>
                                <div class="col-md-6">${campoEncabezado('fa-map-marker-alt', 'Zona', enc.zona || 'N/A')}</div>
                                <div class="col-md-6">${campoEncabezado('fa-calendar-plus', 'Fecha emisión', enc.fecha_emision || 'N/A')}</div>
                                <div class="col-md-6">${campoEncabezado('fa-calendar-times', 'Fecha vencimiento', enc.fecha_vencimiento || 'N/A')}</div>
                                ${tieneSaldo ? `<div class="col-md-6">${campoEncabezado('fa-hand-holding-usd', 'Saldo pendiente',
                                    `<span style="display:inline-block;padding:2px 12px;border-radius:20px;font-weight:700;font-size:0.92rem;background:${saldoEsCero ? '#dcfce7' : '#fee2e2'};color:${saldoEsCero ? '#16a34a' : '#dc2626'};">${this.fmt.format(enc.saldo_pendiente)}</span>`)}</div>` : ''}
                            </div>
                        </div>

                        <div style="border:1px solid #e2e8f0; border-radius:14px; overflow:hidden; margin-bottom:22px;">
                            <div class="table-responsive">
                                <table class="table table-sm mb-0" style="font-size:0.88rem;">
                                    <thead>
                                        <tr style="background:#eef2ff;">
                                            <th style="padding:11px 14px;color:#4338ca;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;border:none;">Código</th>
                                            <th style="padding:11px 14px;color:#4338ca;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;border:none;">Descripción</th>
                                            <th class="text-end" style="padding:11px 14px;color:#4338ca;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;border:none;">Cantidad</th>
                                            <th class="text-end" style="padding:11px 14px;color:#4338ca;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;border:none;">Precio Unit.</th>
                                            <th class="text-end" style="padding:11px 14px;color:#4338ca;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;border:none;">Subtotal</th>
                                            <th class="text-end" style="padding:11px 14px;color:#4338ca;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;border:none;">IVA</th>
                                        </tr>
                                    </thead>
                                    <tbody>${filasItems || '<tr><td colspan="6" class="text-center text-muted py-4">Sin ítems</td></tr>'}</tbody>
                                </table>
                            </div>
                        </div>

                        <div style="display:flex; justify-content:flex-end;">
                            <div style="min-width: 280px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:16px 20px;">
                                <div class="d-flex justify-content-between align-items-center" style="padding:4px 0;">
                                    <span style="color:#64748b;font-size:0.88rem;">Subtotal</span>
                                    <strong style="color:#1e293b;">${this.fmt.format(tot.subtotal || 0)}</strong>
                                </div>
                                <div class="d-flex justify-content-between align-items-center" style="padding:4px 0;">
                                    <span style="color:#64748b;font-size:0.88rem;">IVA</span>
                                    <strong style="color:#1e293b;">${tot.iva !== null && tot.iva !== undefined ? this.fmt.format(tot.iva) : naDash}</strong>
                                </div>
                                <div class="d-flex justify-content-between align-items-center" style="border-top: 1px dashed #cbd5e1; margin-top:10px; padding-top:12px;">
                                    <span style="font-weight:700;color:#1e293b;">Total</span>
                                    <strong style="color:#16a34a;font-size:1.3rem;">${this.fmt.format(tot.total || 0)}</strong>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        const overlay = document.getElementById('modal-factura-wo');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) overlay.remove();
            });
        }
    },

    descargarExcel: async function () {
        const btn = document.getElementById('btn-descargar-edades-cartera');
        const text = document.getElementById('text-descargar-edades-cartera');
        if (!btn || btn.disabled) return;

        const iconoOriginal = btn.querySelector('i')?.className;
        const textoOriginal = text?.textContent;

        try {
            btn.disabled = true;
            const icono = btn.querySelector('i');
            if (icono) icono.className = 'fas fa-spinner fa-spin me-1';
            if (text) text.textContent = 'Generando...';

            const pwaToken = localStorage.getItem('pwa_token');
            const headers = {};
            if (pwaToken) headers['Authorization'] = `Bearer ${pwaToken}`;

            const response = await fetch('/api/cartera/exportar-edades', { method: 'GET', headers });

            if (!response.ok) {
                if (response.status === 401 || response.status === 403) {
                    throw new Error('No tienes permisos para descargar el reporte de cartera.');
                }
                throw new Error('Error al generar el archivo de exportación.');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'edades_cartera.xlsx';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            if (window.Swal) {
                Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: 'Reporte descargado', showConfirmButton: false, timer: 3000 });
            }
        } catch (error) {
            console.error('❌ Error descargando reporte de edades:', error);
            if (window.Swal) {
                Swal.fire({ toast: true, position: 'top-end', icon: 'error', title: error.message || 'Error al descargar el reporte', showConfirmButton: false, timer: 4000 });
            } else if (window.mostrarNotificacion) {
                mostrarNotificacion(error.message || 'Error al descargar el reporte', 'error');
            }
        } finally {
            btn.disabled = false;
            const icono = btn.querySelector('i');
            if (icono && iconoOriginal) icono.className = iconoOriginal;
            if (text && textoOriginal) text.textContent = textoOriginal;
        }
    }
};

window.ModuloCartera = ModuloCartera;
