// simulador.js — Sandbox what-if de programación de inyección.
// Consume /api/simulador/* (ver backend/services/simulador_service.py).
// No toca el MES real (db_programacion) — su propio estado vive en
// simulador_asignaciones.

const ModuloSimulador = {
    _snapshotPendiente: [],
    _candidatosActuales: [],
    _estadoReqId: 0,
    _candidatosReqId: 0,

    async inicializar() {
        console.log('🤖 Inicializando Módulo Simulador');
        this._bindEventos();
        this._renderSnapshotPendiente();
        await this.autoDetectar();
        await this.cargarTodo();
    },

    desactivar() {
        // Sin timers/polling que limpiar.
    },

    _bindEventos() {
        if (this._eventosVinculados) return; // evita duplicar listeners si inicializar() corre mas de una vez
        this._eventosVinculados = true;

        document.getElementById('sim-btn-agregar-snapshot-fila')
            ?.addEventListener('click', () => this.agregarFilaPendiente());
        document.getElementById('sim-btn-guardar-snapshot')
            ?.addEventListener('click', () => this.guardarSnapshot());
        document.getElementById('sim-btn-refrescar')
            ?.addEventListener('click', () => this.cargarTodo());
        document.getElementById('sim-btn-auto-detectar')
            ?.addEventListener('click', () => this.autoDetectar(true));
    },

    async autoDetectar(manual = false) {
        const btn = document.getElementById('sim-btn-auto-detectar');
        if (btn?.disabled) return;
        if (btn) btn.disabled = true;
        try {
            const res = await fetch('/api/simulador/auto-detectar', { method: 'POST' });
            const resultado = await res.json();
            if (res.ok && resultado.success) {
                this._ultimaDeteccion = resultado;
                this._renderSinResolver(resultado);
                if (manual) {
                    mostrarNotificacion(
                        `🤖 Detectadas ${resultado.resueltas.length} automáticamente, ${resultado.sin_resolver.length} necesitan dato manual`,
                        'success'
                    );
                    await this.cargarTodo();
                }
            } else {
                console.error('Error en autoDetectar:', resultado.error);
            }
        } catch (e) {
            console.error('Error en autoDetectar:', e);
        } finally {
            if (btn) btn.disabled = false;
        }
    },

    _renderSinResolver(resultado) {
        const cont = document.getElementById('sim-sin-resolver');
        if (!cont) return;
        const { resueltas, sin_resolver } = resultado;
        let html = `<div class="mb-2"><i class="fas fa-check-circle text-success"></i> ${resueltas.length} máquina(s) detectada(s) sola(s)`;
        if (resueltas.length) {
            html += ': ' + resueltas.map(r => `<strong>${r.maquina}</strong> (${r.codigo_referencia})`).join(', ');
        }
        html += '</div>';
        if (sin_resolver.length) {
            html += `<div><i class="fas fa-exclamation-triangle text-warning"></i> ${sin_resolver.length} sin poder resolver, completa abajo a mano: `
                + sin_resolver.map(s => `<strong>${s.maquina || s.maquina_original}</strong> (${s.codigo_referencia}, ${s.motivo})`).join(', ')
                + '</div>';
        } else {
            html += '<div class="text-success"><i class="fas fa-check"></i> Todo lo activo quedó detectado — no hace falta completar nada a mano.</div>';
        }
        cont.innerHTML = html;
    },

    async cargarTodo() {
        await Promise.all([this.cargarEstado(), this.cargarCandidatos()]);
    },

    async cargarEstado() {
        const reqId = ++this._estadoReqId;
        try {
            const res = await fetch('/api/simulador/estado');
            const data = await res.json();
            if (reqId !== this._estadoReqId) return; // respuesta obsoleta, una mas nueva ya esta en curso
            this._renderEstado(data || []);

            // Precarga el snapshot pendiente con el estado SNAPSHOT_INICIAL
            // actual, para que "Guardar" extienda lo que ya hay en vez de
            // reemplazarlo a ciegas (cargar_snapshot_inicial reemplaza TODO
            // el snapshot manual con lo que se envie).
            if (!this._snapshotPendiente.length) {
                this._snapshotPendiente = (data || [])
                    .filter(f => f.origen === 'SNAPSHOT_INICIAL')
                    .map(f => ({
                        maquina: f.maquina,
                        codigo_molde: f.codigo_molde,
                        codigo_portamolde: f.codigo_portamolde,
                        codigo_referencia: f.codigo_referencia,
                        codigo_macho: f.codigo_macho,
                        cavidades: f.cavidades,
                    }));
                this._renderSnapshotPendiente();
            }
        } catch (e) {
            console.error('Error cargando estado del simulador:', e);
        }
    },

    async cargarCandidatos() {
        const reqId = ++this._candidatosReqId;
        const tbody = document.getElementById('sim-candidatos-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-3">Buscando candidatos...</td></tr>';
        try {
            const res = await fetch('/api/simulador/candidatos?limite=100');
            const data = await res.json();
            if (reqId !== this._candidatosReqId) return; // respuesta obsoleta
            this._candidatosActuales = data || [];
            this._renderCandidatos(this._candidatosActuales);
        } catch (e) {
            console.error('Error cargando candidatos:', e);
        }
    },

    _renderEstado(filas) {
        const tbody = document.getElementById('sim-estado-body');
        if (!tbody) return;
        if (!filas.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">Todo libre — sin asignaciones activas en el sandbox.</td></tr>';
            return;
        }
        const ORIGEN_LABEL = {
            AUTO_DETECTADO: { clase: 'bg-primary', texto: '🤖 Auto' },
            SNAPSHOT_INICIAL: { clase: 'bg-info', texto: 'Manual' },
            SUGERIDO_ACEPTADO: { clase: 'bg-success', texto: 'Sugerido' },
        };
        tbody.innerHTML = filas.map(f => {
            const origen = ORIGEN_LABEL[f.origen] || { clase: 'bg-secondary', texto: f.origen };
            return `
            <tr>
                <td><strong>${f.maquina}</strong></td>
                <td>${f.codigo_molde}</td>
                <td><span class="badge bg-secondary">${f.codigo_portamolde}</span></td>
                <td>${f.codigo_referencia}</td>
                <td>${f.codigo_macho || '—'}</td>
                <td>${f.cavidades}</td>
                <td><span class="badge ${origen.clase}">${origen.texto}</span></td>
                <td><button class="btn btn-sm btn-outline-danger" onclick="ModuloSimulador.liberar(${f.id})" title="Liberar"><i class="fas fa-unlock"></i></button></td>
            </tr>`;
        }).join('');
    },

    _renderCandidatos(filas) {
        const tbody = document.getElementById('sim-candidatos-body');
        if (!tbody) return;
        if (!filas.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-3">Sin candidatos factibles ahora mismo (todo ocupado, o sin brecha de producción pendiente).</td></tr>';
            return;
        }
        tbody.innerHTML = filas.map((c, i) => {
            const macho = c.macho_requerido
                ? `${c.macho_requerido} ${c.macho_disponible ? '<span class="text-success"><i class="fas fa-check"></i></span>' : '<span class="text-danger">sin disp.</span>'}`
                : '—';
            const tiempo = c.tiempo_ciclo_seg_promedio
                ? `${c.tiempo_ciclo_seg_promedio}s <small class="text-muted">(${c.corridas_historicas} corridas)</small>`
                : (c.pared !== null ? `<span class="text-muted">sin historial · pared ${c.pared}</span>` : '<span class="text-muted">sin historial</span>');
            const bloqueado = c.macho_requerido && c.macho_disponible === false;
            return `
            <tr>
                <td><strong>${c.codigo_referencia}</strong><br><small class="text-muted">${c.descripcion || ''}</small></td>
                <td>${Math.round(c.faltante)}</td>
                <td>${c.codigo_molde}</td>
                <td><span class="badge bg-secondary">${c.portamolde_sugerido}</span></td>
                <td>${c.maquina_sugerida}</td>
                <td>${c.cavidades}</td>
                <td>${macho}</td>
                <td>${tiempo}</td>
                <td><button class="btn btn-sm btn-primary" ${bloqueado ? 'disabled' : ''} onclick="ModuloSimulador.aceptar(${i})">
                    <i class="fas fa-check"></i> Aceptar
                </button></td>
            </tr>`;
        }).join('');
    },

    async aceptar(indice) {
        const candidato = this._candidatosActuales[indice];
        if (!candidato) return;
        try {
            const res = await fetch('/api/simulador/aceptar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ candidato })
            });
            const resultado = await res.json();
            if (res.ok && resultado.success) {
                mostrarNotificacion(`✅ Asignado: ${candidato.codigo_referencia} en ${candidato.maquina_sugerida} (portamolde ${candidato.portamolde_sugerido})`, 'success');
                await this.cargarTodo();
            } else {
                mostrarNotificacion(`❌ ${resultado.error || 'Error al aceptar la sugerencia'}`, 'error');
            }
        } catch (e) {
            console.error('Error en aceptar:', e);
            mostrarNotificacion(`Error: ${e.message}`, 'error');
        }
    },

    async liberar(id) {
        try {
            const res = await fetch(`/api/simulador/liberar/${id}`, { method: 'POST' });
            const resultado = await res.json();
            if (res.ok && resultado.success) {
                mostrarNotificacion('✅ Liberado', 'success');
                await this.cargarTodo();
            } else {
                mostrarNotificacion(`❌ ${resultado.error || 'Error al liberar'}`, 'error');
            }
        } catch (e) {
            console.error('Error en liberar:', e);
            mostrarNotificacion(`Error: ${e.message}`, 'error');
        }
    },

    agregarFilaPendiente() {
        const maquina = document.getElementById('sim-input-maquina').value;
        const codigo_molde = document.getElementById('sim-input-molde').value.trim();
        const codigo_portamolde = document.getElementById('sim-input-portamolde').value.trim().toUpperCase();
        const codigo_referencia = document.getElementById('sim-input-referencia').value.trim();
        const cavidades = parseInt(document.getElementById('sim-input-cavidades').value, 10) || 1;

        if (!maquina || !codigo_molde || !codigo_portamolde || !codigo_referencia) {
            mostrarNotificacion('⚠️ Completa máquina, molde, portamolde y referencia', 'error');
            return;
        }
        if (this._snapshotPendiente.some(f => f.maquina === maquina)) {
            mostrarNotificacion(`⚠️ Ya agregaste una fila para ${maquina} — una máquina solo puede tener un trabajo activo`, 'error');
            return;
        }

        this._snapshotPendiente.push({ maquina, codigo_molde, codigo_portamolde, codigo_referencia, cavidades });
        this._renderSnapshotPendiente();

        ['sim-input-molde', 'sim-input-portamolde', 'sim-input-referencia'].forEach(id => {
            document.getElementById(id).value = '';
        });
        document.getElementById('sim-input-cavidades').value = '1';
    },

    quitarFilaPendiente(indice) {
        this._snapshotPendiente.splice(indice, 1);
        this._renderSnapshotPendiente();
    },

    _renderSnapshotPendiente() {
        const tbody = document.getElementById('sim-snapshot-pendiente-body');
        if (!tbody) return;
        if (!this._snapshotPendiente.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-2">Agrega filas antes de guardar el snapshot.</td></tr>';
            return;
        }
        tbody.innerHTML = this._snapshotPendiente.map((f, i) => `
            <tr>
                <td>${f.maquina}</td><td>${f.codigo_molde}</td><td>${f.codigo_portamolde}</td>
                <td>${f.codigo_referencia}</td><td>${f.cavidades}</td>
                <td><button class="btn btn-sm btn-outline-danger" onclick="ModuloSimulador.quitarFilaPendiente(${i})"><i class="fas fa-times"></i></button></td>
            </tr>
        `).join('');
    },

    async guardarSnapshot() {
        if (!this._snapshotPendiente.length) {
            mostrarNotificacion('⚠️ No hay filas para guardar', 'error');
            return;
        }
        const btn = document.getElementById('sim-btn-guardar-snapshot');
        if (btn?.disabled) return; // ya hay un guardado en curso, ignora el reintento
        if (btn) btn.disabled = true;
        try {
            const res = await fetch('/api/simulador/snapshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ asignaciones: this._snapshotPendiente })
            });
            const resultado = await res.json();
            if (res.ok && resultado.success) {
                mostrarNotificacion(`✅ Snapshot guardado (${resultado.filas_creadas} filas)`, 'success');
                this._snapshotPendiente = [];
                this._renderSnapshotPendiente();
                await this.cargarTodo();
            } else {
                mostrarNotificacion(`❌ ${resultado.error || 'Error al guardar el snapshot'}`, 'error');
            }
        } catch (e) {
            console.error('Error en guardarSnapshot:', e);
            mostrarNotificacion(`Error: ${e.message}`, 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    },
};

window.ModuloSimulador = ModuloSimulador;
