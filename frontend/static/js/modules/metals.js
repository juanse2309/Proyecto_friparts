/**
 * metals.js - Lógica de Producción FriMetals
 */

const ModuloMetals = {
    productosData: [],

    inicializar: async function () {
        console.log('🏭 [Metals] Inicializando...');

        const isDashboard = window.AppState.paginaActual === 'metals-dashboard';

        if (isDashboard) {
            await this.cargarDashboard();
        } else {
            this.configurarFecha();
            this.intentarAutoSeleccionarResponsable();
            await this.cargarProductos();
            this.initAutocompleteProducto();
            this.configurarEventos();
        }
    },

    cargarDashboard: async function () {
        try {
            console.log('📊 [Metals] Cargando dashboard...');
            const response = await fetch('/api/metals/produccion/historial');
            const data = await response.json();

            if (data.success && data.historial) { // Corrected from `res.success` to `data.success`
                this.renderDashboard(data.historial);
            }
        } catch (error) {
            console.error('Error cargando dashboard metals:', error);
        }
    },

    renderDashboard: function (registros) {
        const tbody = document.getElementById('metals-dashboard-history');
        if (!tbody) return;

        const hoy = new Date().toISOString().split('T')[0];
        let cantHoy = 0;
        let lotesUnicos = new Set();
        let pncTotal = 0;

        tbody.innerHTML = registros.slice(0, 20).map(r => {
            const rFecha = r.FECHA || '';
            // Convertir D/M/YYYY a YYYY-MM-DD para comparar con hoy
            let rFechaISO = '';
            if (rFecha.includes('/')) {
                const parts = rFecha.split('/');
                rFechaISO = `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
            }

            if (rFechaISO === hoy) {
                cantHoy += parseInt(r.CANT_LOGRADA || 0);
                pncTotal += parseInt(r.PNC || 0);
            }
            if (r.ESTADO !== 'FINALIZADO') lotesUnicos.add(r.LOTE);

            return `
                <tr>
                    <td>${r.FECHA}</td>
                    <td><span class="badge bg-light text-dark shadow-sm border">${r.LOTE}</span></td>
                    <td>${r.CODIGO_PRODUCTO}</td>
                    <td><span class="text-primary fw-bold">${r.PROCESO}</span></td>
                    <td>${r.OPERARIO}</td>
                    <td><span class="text-success fw-bold">${r.CANT_LOGRADA}</span></td>
                    <td><i class="far fa-clock me-1 text-muted"></i>${r.TIEMPO_TOTAL || '--'}</td>
                    <td><span class="badge ${r.ESTADO === 'COMPLETADO' ? 'bg-success' : 'bg-warning'}">${r.ESTADO}</span></td>
                </tr>
            `;
        }).join('');

        if (registros.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center p-4">No hay registros aún</td></tr>';
        }

        // Actualizar KPIs
        document.getElementById('metals-kpi-hoy').textContent = cantHoy;
        document.getElementById('metals-kpi-lotes').textContent = lotesUnicos.size;
        document.getElementById('metals-kpi-pnc').textContent = pncTotal;
    },

    configurarFecha: function () {
        const fechaInput = document.getElementById('fecha-metals');
        if (fechaInput) {
            fechaInput.value = new Date().toISOString().split('T')[0];
        }
    },

    intentarAutoSeleccionarResponsable: function () {
        const input = document.getElementById('responsable-metals');
        if (!input) return;

        if (window.AppState?.user?.name) {
            input.value = window.AppState.user.name;
        } else {
            // Re-intentar cuando el usuario esté listo
            window.addEventListener('user-ready', () => {
                input.value = window.AppState.user.name;
            }, { once: true });
        }
    },

    cargarProductos: async function () {
        try {
            console.log('📦 [Metals] Cargando productos especializados...');
            const response = await fetch('/api/metals/productos/listar');
            const data = await response.json();
            this.productosData = data.productos || [];
            console.log(`✅ [Metals] ${this.productosData.length} productos cargados.`);
        } catch (error) {
            console.error('Error cargando productos metals:', error);
        }
    },

    initAutocompleteProducto: function () {
        const input = document.getElementById('producto-metals');
        const suggestionsDiv = document.getElementById('metals-producto-suggestions');

        if (!input || !suggestionsDiv) return;

        input.addEventListener('input', (e) => {
            const query = e.target.value.trim().toLowerCase();
            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            const resultados = this.productosData.filter(prod =>
                String(prod.CODIGO || '').toLowerCase().includes(query) ||
                String(prod.DESCRIPCION || '').toLowerCase().includes(query)
            ).slice(0, 10);

            this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                input.value = `${item.CODIGO} - ${item.DESCRIPCION}`;
                input.dataset.codigo = item.CODIGO;
                suggestionsDiv.classList.remove('active');
                this.determinarProximoPaso();
            });
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });

        // Listener para Lote
        const loteInput = document.getElementById('lote-metals');
        if (loteInput) {
            loteInput.addEventListener('change', () => this.determinarProximoPaso());
            loteInput.addEventListener('blur', () => this.determinarProximoPaso());
        }
    },

    determinarProximoPaso: async function () {
        const productInput = document.getElementById('producto-metals');
        const loteInput = document.getElementById('lote-metals');
        const procesoInput = document.getElementById('proceso-metals');

        const codigo = productInput?.dataset?.codigo;
        const lote = loteInput?.value?.trim();

        if (!codigo || !lote || !procesoInput) return;

        try {
            console.log(`🔍 [Metals] Consultando próximo paso para ${codigo} Lote ${lote}...`);
            const response = await fetch(`/api/metals/produccion/proximo_paso?codigo_producto=${codigo}&lote=${lote}`);
            const res = await response.json();

            if (res.success) {
                procesoInput.value = res.proximo || 'No definido';
                if (res.proximo === 'FINALIZADO') {
                    Swal.fire('Atención', 'Este lote ya ha completado todos los procesos definidos.', 'info');
                }
            }
        } catch (error) {
            console.error('Error determinando proximo paso:', error);
        }
    },

    renderSuggestions: function (container, items, onSelect) {
        if (items.length === 0) {
            container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
        } else {
            container.innerHTML = items.map(item => `
                <div class="suggestion-item" style="padding: 10px; border-bottom: 1px solid #eee; cursor: pointer;">
                    <strong>${item.CODIGO}</strong> - ${item.DESCRIPCION}
                </div>
            `).join('');

            container.querySelectorAll('.suggestion-item').forEach((div, index) => {
                div.addEventListener('click', () => onSelect(items[index]));
            });
        }
        container.classList.add('active');
    },

    marcarHora: function (tipo) {
        const input = document.getElementById(tipo === 'inicio' ? 'hora-inicio-metals' : 'hora-fin-metals');
        if (input) {
            const ahora = new Date();
            const horas = String(ahora.getHours()).padStart(2, '0');
            const minutos = String(ahora.getMinutes()).padStart(2, '0');
            input.value = `${horas}:${minutos}`;
        }
    },

    configurarEventos: function () {
        const form = document.getElementById('form-metals-produccion');
        if (form) {
            form.addEventListener('submit', (e) => this.handleSubmit(e));
        }
    },

    handleSubmit: async function (e) {
        e.preventDefault();

        const data = {
            responsable: document.getElementById('responsable-metals').value,
            fecha: document.getElementById('fecha-metals').value,
            maquina: document.getElementById('maquina-metals').value,
            codigo_producto: document.getElementById('producto-metals').dataset.codigo,
            lote: document.getElementById('lote-metals').value,
            proceso: document.getElementById('proceso-metals').value,
            cant_solicitada: document.getElementById('cant-solicitada-metals').value,
            hora_inicio: document.getElementById('hora-inicio-metals').value,
            hora_fin: document.getElementById('hora-fin-metals').value,
            cant_ok: document.getElementById('cant-ok-metals').value,
            pnc: document.getElementById('pnc-metals').value
        };

        if (!data.codigo_producto || !data.maquina) {
            return Swal.fire('Error', 'Debe seleccionar un producto y una máquina', 'error');
        }

        try {
            mostrarLoading(true);
            const response = await fetch('/api/metals/produccion/registrar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const res = await response.json();
            mostrarLoading(false);

            if (res.success) {
                Swal.fire('¡Éxito!', 'Actividad registrada correctamente', 'success');
                e.target.reset();
                this.configurarFecha();
                this.intentarAutoSeleccionarResponsable();
            } else {
                Swal.fire('Error', res.message || 'Error al registrar', 'error');
            }
        } catch (error) {
            console.error('Error submit metals:', error);
            mostrarLoading(false);
            Swal.fire('Error', 'Error de conexión', 'error');
        }
    }
};

window.ModuloMetals = ModuloMetals;

// Escuchar cambios de página si se maneja vía app.js
window.addEventListener('hashchange', () => {
    if (window.location.hash === '#metals-produccion') {
        ModuloMetals.inicializar();
    }
});
