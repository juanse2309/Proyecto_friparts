window.ModuloAsistencia = (function () {
    let colaboradoresData = [];
    let currentUserContext = null;

    function inicializar() {
        console.log("🕒 ModuloAsistencia: Inicializando con RBAC...");

        // 1. Obtener contexto del usuario desde AuthModule
        if (window.AuthModule && AuthModule.currentUser) {
            currentUserContext = AuthModule.currentUser;
        } else {
            console.error("No se pudo obtener el usuario activo. RBAC fallará.");
            Swal.fire('Error', 'Sesión no identificada. Recargue la página.', 'error');
            return;
        }

        const role = AuthModule.normalizeRole(currentUserContext.rol || currentUserContext.role || '');
        const depto = currentUserContext.departamento || 'FRIPARTS';
        const nombre = currentUserContext.nombre || 'Desconocido';

        // Helper para normalizar texto (quitar acentos)
        const normalize = (str) => {
            if (!str) return '';
            return str.toString().normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "")
                .toUpperCase().trim();
        };

        const nombreNorm = normalize(nombre);

        // Mapa de roles con sus áreas de responsabilidad (RBAC Estricto)
        let areasAsignadas = [];
        let esJefe = false;
        const ADMIN_ROLES = ['ADMINISTRACION', 'ADMINISTRADOR', 'GERENCIA', 'ADMIN', 'GERENCIA GLOBAL'];
        let esRolGerencia = ADMIN_ROLES.includes(role);

        if (esRolGerencia) {
            esJefe = true;
            areasAsignadas = null; // null = VE TODO
        } else if (role === 'JEFE INYECCION' || role === 'INYECCION') {
            esJefe = true;
            areasAsignadas = ['INYECCION', 'ENSAMBLE'];
        } else if (role === 'JEFE PULIDO' || role === 'PULIDO') {
            esJefe = true;
            areasAsignadas = ['PULIDO'];
        } else if (role === 'JEFE ALMACEN' || role === 'ALMACEN' || role === 'ALISTAMIENTO') {
            esJefe = true;
            areasAsignadas = ['ALISTAMIENTO'];
        } else if (role === 'AUXILIAR INVENTARIO') {
            esJefe = true;
            areasAsignadas = ['AUXILIAR INVENTARIO'];
        } else if (role === 'ENSAMBLE') {
            esJefe = true;
            areasAsignadas = ['ENSAMBLE'];
        } else if (role === 'JEFE DE PLANTA') {
            esJefe = true;
            areasAsignadas = [depto]; // Jeison ve su departamento (PLANTA)
        }

        // Juan Sebastian: Limpieza de cabecera (Solo Nombre y Áreas)
        document.getElementById('asistencia-user-name').textContent = nombre;
        if (esJefe) {
            let label = esRolGerencia ? 'GERENCIA GLOBAL' : (areasAsignadas ? areasAsignadas.join(' / ') : role);
            document.getElementById('asistencia-user-role').textContent = label;
            document.getElementById('asistencia-user-role').classList.add('text-primary', 'fw-bold');

            // Guardar las áreas asignadas para filtrado posterior
            currentUserContext._areasAsignadas = areasAsignadas;

            // Lógica Pestañas (Tabs) para Jefes
            const navGestion = document.getElementById('nav-item-gestion');
            if (navGestion) navGestion.style.display = 'block';

            // Activar tab de Gestión por defecto
            try {
                const tabElement = document.getElementById('tab-gestion');
                if (tabElement) {
                    const bsTab = new bootstrap.Tab(tabElement);
                    bsTab.show();
                }
            } catch (e) { console.error("Error activando tab gestion", e); }

            // Panel de Corte de Nómina: Solo visible para Administradores
            const panelCorte = document.getElementById('panel-corte-nomina');
            if (panelCorte) {
                if (esRolGerencia) {
                    panelCorte.style.display = 'block';
                } else {
                    panelCorte.style.display = 'none';
                }
            }

            const fechaInput = document.getElementById('asistencia-fecha');
            if (fechaInput) {
                fechaInput.value = new Date().toISOString().split('T')[0];
            }

            // Carga automática del personal a cargo y también de sus propias horas
            cargarPlanilla();
            cargarMisHoras();
        } else {
            // Lógica Pestañas (Tabs) para Operarios
            const navGestion = document.getElementById('nav-item-gestion');
            if (navGestion) navGestion.style.display = 'none';

            // Activar Tab Mis Horas obligatoriamente
            try {
                const tabElement = document.getElementById('tab-mis-horas');
                if (tabElement) {
                    const bsTab = new bootstrap.Tab(tabElement);
                    bsTab.show();
                }
            } catch (e) { console.error("Error activando tab mis horas", e); }

            // Carga automática de historial de usuario
            cargarMisHoras();
        }
    }

    // ==========================================
    // LÓGICA DE JEFES: Carga y Guardado
    // ==========================================

    async function cargarPlanilla() {
        const fechaInput = document.getElementById('asistencia-fecha');
        if (!fechaInput || !fechaInput.value) {
            Swal.fire('Atención', 'Seleccione una fecha válida', 'warning');
            return;
        }

        const overlay = document.getElementById('loading-overlay');
        if (overlay) { overlay.style.display = 'flex'; if (document.getElementById('loading-overlay-text')) document.getElementById('loading-overlay-text').textContent = 'Consultando registros existentes...'; }

        try {
            // 1. Obtener colaboradores base (Añadir división para filtro estricto en Metales)
            const division = currentUserContext?.division?.toLowerCase() || 'friparts';
            const resColab = await fetch(`/api/asistencia/colaboradores?division=${division}`);
            const dataColab = await resColab.json();

            // 2. Obtener registros existentes del día para PERSISTENCIA
            const resReg = await fetch(`/api/asistencia/registros_dia?fecha=${fechaInput.value}`);
            const dataReg = await resReg.json();

            if (dataColab.status === 'success') {
                let lista = dataColab.colaboradores;
                const regDia = dataReg.status === 'success' ? dataReg.registros : [];

                // Mezclar persistencia: Si el colaborador ya tiene registro, usarlo
                lista = lista.map(c => {
                    const findReg = regDia.find(r => r.colaborador === c.nombre);
                    if (findReg) {
                        return {
                            ...c,
                            hora_entrada: findReg.ingreso_real,
                            hora_salida: findReg.salida_real,
                            _yaRegistrado: true,
                            _estado: findReg.estado || 'PRESENTE',
                            _motivo: findReg.motivo || '',
                            _comentarios: findReg.comentarios || ''
                        };
                    }
                    return {
                        ...c,
                        _estado: 'PRESENTE',
                        _motivo: '',
                        _comentarios: ''
                    };
                });

                colaboradoresData = lista;
                const filtrados = filtrarPorDeptoDelJefe(colaboradoresData);
                renderizarTabla(filtrados);

                if (regDia.length > 0) {
                    AuthModule.mostrarNotificacion(`Cargados ${regDia.length} registros previos para hoy`, 'info');
                }
            } else {
                throw new Error(dataColab.message);
            }
        } catch (error) {
            console.error("Error cargando planilla:", error);
            Swal.fire('Error', 'No se pudo sincronizar la planilla', 'error');
        } finally {
            if (overlay) overlay.style.display = 'none';
        }
    }

    function filtrarPorDeptoDelJefe(lista) {
        // El Backend ya realiza el filtrado por departamento y RBAC.
        // El Frontend simplemente entrega la lista tal cual para evitar ocultar al Jefe.
        return lista;
    }

    function renderizarTabla(lista) {
        const body = document.getElementById('asistencia-body');
        const cardsContainer = document.getElementById('asistencia-cards-container');

        if (!lista.length) {
            const empty = '<tr><td colspan="7" class="text-center py-4 text-muted">No hay personal activo en su área de responsabilidad</td></tr>';
            body.innerHTML = empty;
            cardsContainer.innerHTML = '<div class="col-12 text-center py-5 text-muted">No hay personal asignado</div>';
            return;
        }

        // Render Tabla (Desktop)
        body.innerHTML = lista.map((c) => {
            const isAbsent = c._estado === 'AUSENTE';
            const hEntrada = formatTimeDisplay(c.hora_entrada);
            const hSalida = formatTimeDisplay(c.hora_salida);
            const statusClass = c._yaRegistrado ? (isAbsent ? 'table-warning' : 'table-success') : '';

            const badgeContent = isAbsent
                ? `<span class="badge bg-warning ms-2 shadow-sm text-dark"><i class="fas fa-exclamation-triangle me-1"></i> ${c._motivo}</span>`
                : (c._yaRegistrado ? '<i class="fas fa-check-circle text-success ms-2" title="Ya guardado"></i>' : '');

            return `
                <tr data-oficial-entrada="${c.hora_entrada}" data-oficial-salida="${c.hora_salida}" data-nombre="${c.nombre}" class="${statusClass}">
                    <td class="ps-4 fw-bold">
                        <div class="d-flex align-items-center">
                            <i class="fas fa-user-circle text-primary opacity-50 me-2"></i>
                            <span>${c.nombre}</span>
                            ${badgeContent}
                        </div>
                    </td>
                    <td><small class="badge bg-light text-dark border"><i class="fas fa-tag me-1 text-muted"></i>${c.departamento}</small></td>
                    <td class="text-center small text-muted font-monospace">${hEntrada} - ${hSalida}</td>
                    <td style="width: 160px;">
                        <div class="input-group input-group-sm">
                            <span class="input-group-text bg-white border-end-0 text-success"><i class="fas fa-sign-in-alt"></i></span>
                            <input type="time" class="form-control border-start-0 ps-0 bg-white" 
                                   onchange="ModuloAsistencia.calcularFila(this)" data-tipo="ingreso" value="${c.hora_entrada || c.hora_entrada_oficial}" ${isAbsent ? 'disabled' : ''}>
                        </div>
                    </td>
                    <td style="width: 160px;">
                        <div class="input-group input-group-sm">
                            <span class="input-group-text bg-white border-end-0 text-danger"><i class="fas fa-sign-out-alt"></i></span>
                            <input type="time" class="form-control border-start-0 ps-0 bg-white" 
                                   onchange="ModuloAsistencia.calcularFila(this)" data-tipo="salida" value="${c.hora_salida || c.hora_salida_oficial}" ${isAbsent ? 'disabled' : ''}>
                        </div>
                    </td>
                    <td class="text-center fw-bold text-primary" style="background: rgba(30, 64, 175, 0.02);">
                        <div class="d-flex align-items-center justify-content-center">
                            <i class="fas fa-hourglass-half me-2 opacity-50 small"></i>
                            <input type="number" class="form-control form-control-sm text-center bg-transparent border-0 fw-bold text-primary p-0" style="width: 40px;" disabled value="0" data-tipo="ordinarias">
                        </div>
                    </td>
                    <td class="text-center fw-bold text-danger" style="background: rgba(220, 38, 38, 0.02);">
                        <div class="d-flex align-items-center justify-content-center">
                            <i class="fas fa-bolt me-2 opacity-50 small"></i>
                            <input type="number" class="form-control form-control-sm text-center bg-transparent border-0 fw-bold text-danger p-0" style="width: 40px;" disabled value="0" data-tipo="extras">
                        </div>
                    </td>
                    <td class="text-center" style="width: 180px;">
                        <input type="text" class="form-control form-control-sm border-0 bg-light" placeholder="Nota..." data-tipo="comentarios" value="${c._comentarios || ''}" ${isAbsent ? 'disabled' : ''}>
                    </td>
                    <td class="text-center">
                        <button class="btn btn-sm btn-outline-warning rounded-pill border-0 shadow-sm px-3" onclick="ModuloAsistencia.abrirModalAusencia('${c.nombre}')" title="Marcar Ausencia" ${isAbsent ? 'disabled' : ''}>
                            <i class="fas fa-user-times"></i> Ausente
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        // Render Tarjetas (Mobile)
        cardsContainer.innerHTML = lista.map((c) => {
            const isAbsent = c._estado === 'AUSENTE';
            const hOficial = `${formatTimeDisplay(c.hora_entrada)} - ${formatTimeDisplay(c.hora_salida)}`;

            let cardBorder = 'border';
            if (c._yaRegistrado) {
                cardBorder = isAbsent ? 'border-warning border-4' : 'border-top border-success border-4';
            }

            const cardHeaderIcon = isAbsent
                ? `<div><span class="badge bg-warning text-dark px-2 py-1 rounded-pill"><i class="fas fa-exclamation-triangle me-1"></i> ${c._motivo}</span></div>`
                : (c._yaRegistrado ? '<i class="fas fa-check-circle text-success fa-lg shadow-sm"></i>' : '');

            return `
                <div class="col-12 col-sm-6 mb-3">
                    <div class="card border-0 shadow-sm h-100 ${cardBorder}" 
                         data-oficial-entrada="${c.hora_entrada}" data-oficial-salida="${c.hora_salida}" data-nombre="${c.nombre}"
                         style="border-radius: 20px; transition: transform 0.2s ease;">
                        <div class="card-body p-4">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <div class="d-flex align-items-center">
                                    <div class="avatar-circle bg-soft-primary text-primary me-3 d-flex align-items-center justify-content-center" style="width: 45px; height: 45px; border-radius: 50%; background: #eef2ff;">
                                        <i class="fas fa-user-circle fa-2x"></i>
                                    </div>
                                    <div>
                                        <h6 class="fw-bold mb-0 text-dark" style="font-size: 1.05rem;">${c.nombre}</h6>
                                        <span class="small text-muted"><i class="fas fa-tag me-1"></i>${c.departamento}</span>
                                    </div>
                                </div>
                                ${cardHeaderIcon}
                            </div>

                            <p class="small text-muted mb-3 bg-light p-2 rounded-3 text-center">
                                <i class="fas fa-clock me-1 text-primary"></i> Horario: <strong>${hOficial}</strong>
                            </p>

                            <div class="row g-3">
                                <div class="col-12 text-center">
                                    <label class="small fw-bold text-muted mb-1 d-block"><i class="fas fa-sign-in-alt me-1 text-success"></i>Llegada</label>
                                    <input type="time" class="form-control form-control-lg border-0 bg-light shadow-none text-center mx-auto" 
                                           style="border-radius: 15px; font-size: 1.1rem; width: 80%;"
                                           onchange="ModuloAsistencia.calcularFila(this)" data-tipo="ingreso" value="${c.hora_entrada || c.hora_entrada_oficial}" ${isAbsent ? 'disabled' : ''}>
                                </div>
                                <div class="col-12 text-center">
                                    <label class="small fw-bold text-muted mb-1 d-block"><i class="fas fa-sign-out-alt me-1 text-danger"></i>Salida</label>
                                    <input type="time" class="form-control form-control-lg border-0 bg-light shadow-none text-center mx-auto" 
                                           style="border-radius: 15px; font-size: 1.1rem; width: 80%;"
                                           onchange="ModuloAsistencia.calcularFila(this)" data-tipo="salida" value="${c.hora_salida || c.hora_salida_oficial}" ${isAbsent ? 'disabled' : ''}>
                                </div>
                                
                                <div class="col-12">
                                    <div class="p-3 bg-soft-primary rounded-4 text-center border border-primary border-opacity-10 h-100" style="background: rgba(30, 64, 175, 0.04); border-radius: 15px;">
                                        <span class="d-block small text-muted mb-1 font-monospace">ORDINARIAS</span>
                                        <span class="fw-bold text-primary h2 mb-0" data-tipo="ordinarias-card" style="letter-spacing: -2px;">0</span>
                                    </div>
                                </div>
                                <div class="col-12">
                                    <div class="p-3 bg-soft-danger rounded-4 text-center border border-danger border-opacity-10 h-100" style="background: rgba(220, 38, 38, 0.04); border-radius: 15px;">
                                        <span class="d-block small text-muted mb-1 font-monospace">EXTRAS</span>
                                        <span class="fw-bold text-danger h2 mb-0" data-tipo="extras-card" style="letter-spacing: -2px;">0</span>
                                    </div>
                                </div>
                                <div class="col-12 mt-2">
                                    <label class="small fw-bold text-muted mb-1 d-block"><i class="fas fa-comment-dots me-1 text-secondary"></i>Comentarios Jornada</label>
                                    <textarea class="form-control border-0 bg-light shadow-none" rows="2" style="border-radius: 12px; resize: none;" placeholder="Observaciones del día..." data-tipo="comentarios" ${isAbsent ? 'disabled' : ''}>${c._comentarios || ''}</textarea>
                                </div>
                                <div class="col-12 mt-3 text-end pt-2 border-top">
                                    <button class="btn btn-sm btn-outline-warning rounded-pill shadow-sm fw-bold px-4" onclick="ModuloAsistencia.abrirModalAusencia('${c.nombre}')" ${isAbsent ? 'disabled' : ''}>
                                        <i class="fas fa-user-times me-1"></i> Reportar Ausencia
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Disparar cálculo inicial y auto-llenado agresivo
        setTimeout(() => {
            document.querySelectorAll('#asistencia-body tr, #asistencia-cards-container .card').forEach(row => {
                const hEntradaInput = row.querySelector('[data-tipo="ingreso"]');
                const hSalidaInput = row.querySelector('[data-tipo="salida"]');
                
                // Si están vacíos, inyectar el horario oficial
                if (!hEntradaInput.value) hEntradaInput.value = row.dataset.oficialEntrada || "07:00";
                if (!hSalidaInput.value) hSalidaInput.value = row.dataset.oficialSalida || "17:00";
                
                // Trigger del cálculo por fila
                calcularFila(hEntradaInput);
            });
        }, 300);
    }

    function cambiarVista(modo) {
        const table = document.getElementById('asistencia-table-container');
        const cards = document.getElementById('asistencia-cards-container');
        const btnTab = document.getElementById('btn-view-table');
        const btnCrd = document.getElementById('btn-view-cards');

        if (modo === 'table') {
            table.style.display = 'block';
            cards.style.display = 'none';
            btnTab.classList.add('active');
            btnCrd.classList.remove('active');
        } else {
            table.style.display = 'none';
            cards.style.display = 'flex';
            btnTab.classList.remove('active');
            btnCrd.classList.add('active');
        }
    }

    function recalcularTodaLaTabla() {
        const inputs = document.querySelectorAll('#asistencia-body input[data-tipo="ingreso"], #asistencia-cards-container input[data-tipo="ingreso"]');
        inputs.forEach(input => calcularFila(input));
    }

    function calcularFila(input) {
        const parent = input.closest('tr') || input.closest('.card');
        const nombre = parent.dataset.nombre;
        if (!nombre) return;

        // Localizar elementos vinculados
        const row = document.querySelector(`#asistencia-body tr[data-nombre="${nombre}"]`);
        const card = Array.from(document.querySelectorAll('#asistencia-cards-container .card'))
            .find(c => c.dataset.nombre === nombre);

        const hRealIngresoInput = parent.querySelector('[data-tipo="ingreso"]').value;
        const hRealSalidaInput = parent.querySelector('[data-tipo="salida"]').value;
        const fechaStr = document.getElementById('asistencia-fecha').value;

        if (!hRealIngresoInput || !hRealSalidaInput) return;

        // 1. Convertir a Minutos Totales para Precisión
        const convertirAMinutos = (horaStr) => {
            const [hh, mm] = horaStr.split(':').map(Number);
            return (hh * 60) + mm;
        };

        const minIngreso = convertirAMinutos(hRealIngresoInput);
        let minSalida = convertirAMinutos(hRealSalidaInput);

        // 2. Manejo de Jornada Nocturna (si sale antes de entrar, sumamos 24h)
        if (minSalida < minIngreso) {
            minSalida += (24 * 60);
        }

        const totalMinutos = minSalida - minIngreso;
        
        // 2.1 Aplicar Descuento de Descanso (60 min obligatorios)
        const minutosNetos = Math.max(0, totalMinutos - 60);
        const horasNetas = minutosNetos / 60;

        // 3. Regla de Negocio: Máximo 9h Ordinarias (L-J) / 8h (V)
        const fecha = new Date(fechaStr + 'T00:00:00');
        const diaSemana = fecha.getDay(); 
        
        let maxOrd = 9;
        if (diaSemana === 5) maxOrd = 8;
        if (diaSemana === 0 || diaSemana === 6) maxOrd = 0;

        let ordinarias = Math.min(horasNetas, maxOrd);
        let extras = Math.max(0, horasNetas - ordinarias);

        // 4. Limpieza de decimales
        const ordFinal = Number(ordinarias.toFixed(1));
        const extFinal = Number(extras.toFixed(1));

        // 5. Actualización Sincronizada
        [row, card].forEach(el => {
            if (!el) return;
            el.querySelector('[data-tipo="ingreso"]').value = hRealIngresoInput;
            el.querySelector('[data-tipo="salida"]').value = hRealSalidaInput;
            
            const ordElem = el.querySelector('[data-tipo="ordinarias"]') || el.querySelector('[data-tipo="ordinarias-card"]');
            const extElem = el.querySelector('[data-tipo="extras"]') || el.querySelector('[data-tipo="extras-card"]');
            
            if (ordElem) {
                if (ordElem.tagName === 'INPUT') ordElem.value = ordFinal;
                else ordElem.textContent = ordFinal;
            }
            if (extElem) {
                if (extElem.tagName === 'INPUT') extElem.value = extFinal;
                else extElem.textContent = extFinal;
            }
        });
    }

    function timeToDecimal(timeStr) {
        if (!timeStr) return 0;
        const [hh, mm] = timeStr.split(':').map(Number);
        return hh + (mm / 60);
    }

    function formatTimeDisplay(timeStr) {
        if (!timeStr || typeof timeStr !== 'string') return '-';

        // Limpiar y separar
        const match = timeStr.trim().match(/(\d{1,2}):(\d{2})/);
        if (!match) return timeStr;

        let hh = parseInt(match[1]);
        const mm = match[2];
        const ampm = hh >= 12 ? 'pm' : 'am';

        hh = hh % 12;
        hh = hh ? hh : 12;
        return `${hh}:${mm} ${ampm} `;
    }

    async function guardarAsistencia() {
        const fecha = document.getElementById('asistencia-fecha').value;
        const filas = document.querySelectorAll('#asistencia-body tr[data-nombre]');
        const registros = [];

        if (!currentUserContext) {
            Swal.fire('Error', 'Falta contexto de usuario para autorizar registro', 'error');
            return;
        }

        filas.forEach(f => {
            const ingreso = f.querySelector('[data-tipo="ingreso"]').value;
            const salida = f.querySelector('[data-tipo="salida"]').value;
            const ord = parseFloat(f.querySelector('[data-tipo="ordinarias"]').value) || 0;
            const ext = parseFloat(f.querySelector('[data-tipo="extras"]').value) || 0;
            const comentariosElem = f.querySelector('[data-tipo="comentarios"]');
            const comentarios = comentariosElem ? comentariosElem.value.trim() : "";

            // Si la fila ya tiene table-success, significa que ya fue cargada de la base de datos hoy.
            // Para evitar duplicados en el Google Sheet al darle múltiples veces "Registrar Horas", la ignoramos.
            const yaRegistrado = f.classList.contains('table-success');

            if (ingreso && salida && !yaRegistrado) {
                registros.push({
                    fecha: fecha,
                    colaborador: f.dataset.nombre,
                    ingreso_real: ingreso,
                    salida_real: salida,
                    horas_ordinarias: ord,
                    horas_extras: ext,
                    registrado_por: currentUserContext.nombre, // Traza de auditoría de jefe
                    estado: 'PRESENTE',
                    motivo: '',
                    comentarios: comentarios
                });
            }
        });

        if (!registros.length) {
            Swal.fire('Atención', 'No hay registros de ingreso/salida completados para guardar', 'info');
            return;
        }

        const overlayText = document.getElementById('loading-overlay-text');
        if (overlayText) overlayText.textContent = 'Guardando registros...';
        mostrarLoading(true);
        try {
            const response = await fetch('/api/asistencia/guardar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ registros })
            });
            const result = await response.json();

            if (result.status === 'success') {
                Swal.fire('Éxito', result.message, 'success');
                // Opcionalmente limpiar después de guardar masivamente? Depende del flujo, mejor dejarlo visual.
                AuthModule.mostrarNotificacion('Horas cargadas exitosamente', 'success');
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            console.error("Error guardando:", error);
            Swal.fire('Error', 'No se pudo guardar la asistencia', 'error');
        } finally {
            mostrarLoading(false);
        }
    }

    // ==========================================
    // LÓGICA DE AUSENCIAS
    // ==========================================

    function abrirModalAusencia(nombre) {
        document.getElementById('ausencia-colaborador-nombre').value = nombre;
        document.getElementById('ausencia-colaborador-display').textContent = nombre;
        document.getElementById('ausencia-motivo').value = '';
        document.getElementById('ausencia-comentarios').value = '';
        document.getElementById('modal-ausencia').style.display = 'flex';
    }

    function cerrarModalAusencia() {
        document.getElementById('modal-ausencia').style.display = 'none';
        document.getElementById('ausencia-colaborador-nombre').value = '';
    }

    async function guardarAusencia() {
        const nombreColaborador = document.getElementById('ausencia-colaborador-nombre').value;
        const motivo = document.getElementById('ausencia-motivo').value;
        const comentarios = document.getElementById('ausencia-comentarios').value;
        const fecha = document.getElementById('asistencia-fecha').value;

        if (!motivo) {
            Swal.fire('Atención', 'Por favor seleccione un motivo de ausencia', 'warning');
            return;
        }

        if (!currentUserContext) {
            Swal.fire('Error', 'Falta contexto de usuario para autorizar registro', 'error');
            return;
        }

        const registroAusencia = {
            fecha: fecha,
            colaborador: nombreColaborador,
            ingreso_real: "AUSENTE",
            salida_real: motivo, // Temporarily store reason here if we don't have new columns yet (Wait, implementation plan agreed on new columns)
            horas_ordinarias: 0,
            horas_extras: 0,
            registrado_por: currentUserContext.nombre,
            estado: "AUSENTE",
            motivo: motivo,
            comentarios: comentarios
        };

        // We will adapt the backend to handle these new fields or fallback to INGRESO_REAL/SALIDA_REAL if needed.
        // Actually, backend will just append them.

        const overlayText = document.getElementById('loading-overlay-text');
        if (overlayText) overlayText.textContent = 'Registrando ausencia...';
        mostrarLoading(true);

        try {
            const response = await fetch('/api/asistencia/guardar_ausencia', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ registro: registroAusencia })
            });
            const result = await response.json();

            if (result.status === 'success') {
                Swal.fire('Éxito', result.message, 'success');
                cerrarModalAusencia();

                // Update UI visually
                reflejarAusenciaEnUI(nombreColaborador, motivo);

                AuthModule.mostrarNotificacion('Ausencia registrada exitosamente', 'success');
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            console.error("Error guardando ausencia:", error);
            Swal.fire('Error', 'No se pudo guardar la ausencia', 'error');
        } finally {
            mostrarLoading(false);
        }
    }

    function reflejarAusenciaEnUI(nombre, motivo) {
        // Find row in table
        const row = document.querySelector(`#asistencia-body tr[data-nombre="${nombre}"]`);
        if (row) {
            row.classList.add('table-warning');
            row.querySelector('[data-tipo="ingreso"]').value = '';
            row.querySelector('[data-tipo="salida"]').value = '';
            row.querySelector('[data-tipo="ingreso"]').disabled = true;
            row.querySelector('[data-tipo="salida"]').disabled = true;
            row.querySelector('[data-tipo="ordinarias"]').value = 0;
            row.querySelector('[data-tipo="extras"]').value = 0;
            const comentariosInputRow = row.querySelector('[data-tipo="comentarios"]');
            if (comentariosInputRow) {
                comentariosInputRow.value = '';
                comentariosInputRow.disabled = true;
            }

            // Add absent badge next to name
            const nameContainer = row.querySelector('.d-flex.align-items-center');
            if (nameContainer && !nameContainer.querySelector('.badge.bg-warning')) {
                const badge = document.createElement('span');
                badge.className = 'badge bg-warning ms-2 shadow-sm text-dark';
                badge.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i> ${motivo}`;
                nameContainer.appendChild(badge);
            }
        }

        // Find card
        const card = Array.from(document.querySelectorAll('#asistencia-cards-container .card'))
            .find(c => c.dataset.nombre === nombre);

        if (card) {
            card.classList.remove('border', 'border-success');
            card.classList.add('border-warning', 'border-4');
            card.querySelector('[data-tipo="ingreso"]').value = '';
            card.querySelector('[data-tipo="salida"]').value = '';
            card.querySelector('[data-tipo="ingreso"]').disabled = true;
            card.querySelector('[data-tipo="salida"]').disabled = true;

            const comentariosInputCard = card.querySelector('[data-tipo="comentarios"]');
            if (comentariosInputCard) {
                comentariosInputCard.value = '';
                comentariosInputCard.disabled = true;
            }

            const headerInfo = card.querySelector('.d-flex.justify-content-between.align-items-center');
            if (headerInfo && !headerInfo.querySelector('.badge.bg-warning')) {
                const badgeContainer = document.createElement('div');
                badgeContainer.innerHTML = `<span class="badge bg-warning text-dark px-2 py-1 rounded-pill"><i class="fas fa-exclamation-triangle me-1"></i> ${motivo}</span>`;
                headerInfo.appendChild(badgeContainer);
            }
        }
    }

    // ==========================================
    // LÓGICA DE OPERARIOS: Historial Semanal
    // ==========================================

    async function cargarMisHoras() {
        if (!currentUserContext || !currentUserContext.nombre) return;

        const body = document.getElementById('mis-horas-body');
        body.innerHTML = '<tr><td colspan="5" class="py-4 text-center"><i class="fas fa-spinner fa-spin text-success me-2"></i> Cargando mis horas...</td></tr>';

        try {
            // El backend ahora usa session['user'] en lugar de leer parámetros inseguros por GET
            const response = await fetch('/api/asistencia/mis_horas');
            const data = await response.json();

            if (data.status === 'success') {
                // ⚡ Sincronización del Encabezado (Admin Fix)
                const currentRol = data.rol || data.role || 'OPERARIO';
                const roleElem = document.getElementById('asistencia-user-role');
                if (roleElem && (roleElem.textContent.includes('...'))) {
                    const isGerencia = ['ADMINISTRACION', 'ADMIN', 'GERENCIA'].includes(currentRol.toUpperCase());
                    roleElem.textContent = isGerencia ? 'GERENCIA GLOBAL' : currentRol;
                    roleElem.classList.add('text-primary', 'fw-bold');
                }

                if (data.registros && data.registros.length > 0) {
                    let totalOrd = 0;
                    let totalExt = 0;

                    body.innerHTML = data.registros.map(r => {
                        const hOrd = parseFloat(r.horas_normales) || 0;
                        const hExt = parseFloat(r.horas_extras) || 0;
                        totalOrd += hOrd;
                        totalExt += hExt;

                        const isPendiente = (r.estado_pago === 'PENDIENTE');
                        const statusBadge = isPendiente 
                            ? `<span class="badge rounded-pill bg-info text-white"><i class="fas fa-clock me-1"></i>Pendiente</span>`
                            : `<span class="badge rounded-pill bg-success text-white"><i class="fas fa-check-circle me-1"></i>Pagado</span>`;

                        return `
                        <tr>
                            <td class="fw-bold text-muted">
                                <span class="text-primary small fw-bold d-block">${r.fecha}</span>
                            </td>
                            <td><span class="badge bg-light text-dark">${r.llegada}</span></td>
                            <td><span class="badge bg-light text-dark">${r.salida}</span></td>
                            <td class="text-primary fw-bold">${hOrd.toFixed(1)}</td>
                            <td class="text-danger fw-bold">${hExt.toFixed(1)}</td>
                            <td>${statusBadge}</td>
                        </tr>
                        `;
                    }).join('');

                    // Actualizar Footer con Totales
                    const footer = document.getElementById('mis-horas-footer');
                    if (footer) {
                        footer.innerHTML = `
                            <tr class="table-light border-top border-2">
                                <td colspan="3" class="text-end fw-bold py-3 px-4">TOTAL ACUMULADO DEL PERIODO:</td>
                                <td class="text-primary fw-bold h5 mb-0 py-3">${totalOrd.toFixed(1)}</td>
                                <td class="text-danger fw-bold h5 mb-0 py-3">${totalExt.toFixed(1)}</td>
                            </tr>
                        `;
                    }
                } else {
                    body.innerHTML = '<tr><td colspan="5" class="text-center py-5 text-muted"><i class="fas fa-clock fa-2x mb-3" style="opacity: 0.5;"></i><br>No hay horas registradas en el periodo actual de nómina</td></tr>';
                    const footer = document.getElementById('mis-horas-footer');
                    if (footer) footer.innerHTML = '';
                }
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            console.error("Error cargando historial de horas:", error);
            body.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-4">Error al cargar historial</td></tr>';
        }
    }

    return {
        inicializar,
        cargarPlanilla,
        calcularFila,
        cambiarVista,
        guardarAsistencia,
        cargarMisHoras,
        abrirModalAusencia,
        cerrarModalAusencia,
        guardarAusencia
    };
})();
