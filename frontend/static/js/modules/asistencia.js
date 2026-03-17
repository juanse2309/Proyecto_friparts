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

        // Mapa de jefes con sus áreas de responsabilidad (Normalizado)
        const JEFES_AREA = {
            'NATHALIA': { areas: ['ALISTAMIENTO'] },
            'NATALIA': { areas: ['ALISTAMIENTO'] },
            'PAOLA': { areas: ['AUXILIAR INVENTARIO', 'INVENTARIO'] },
            'OSCAR PRIETO': { areas: ['INYECCION', 'ENSAMBLE'] },
            'OSCAR': { areas: ['INYECCION', 'ENSAMBLE'] },
            'DANIEL': { areas: ['PULIDO'] },
            'LAURA': { areas: ['PULIDO'] }
        };

        // Detectar si es jefe: por rol O por nombre
        const esRolGerencia = role.includes('ADMINISTRADOR') || role.includes('ADMINISTRACION') || role.includes('GERENCIA');
        const jefeMatch = Object.keys(JEFES_AREA).find(key => nombreNorm.includes(key));
        const esJefe = esRolGerencia || !!jefeMatch;

        // Juan Sebastian: Limpieza de cabecera (Solo Nombre y Áreas)
        document.getElementById('asistencia-user-name').textContent = nombre;
        if (esJefe) {
            let label = esRolGerencia ? 'GERENCIA GLOBAL' : (JEFES_AREA[jefeMatch]?.areas.join(' / ') || role);
            document.getElementById('asistencia-user-role').textContent = label;
            document.getElementById('asistencia-user-role').classList.add('text-primary', 'fw-bold');
        } else {
            document.getElementById('asistencia-user-role').textContent = depto;
        }

        if (esJefe) {
            // Guardar las áreas asignadas para filtrado posterior
            if (esRolGerencia) {
                currentUserContext._areasAsignadas = null; // null = VE TODO
            } else if (jefeMatch) {
                currentUserContext._areasAsignadas = JEFES_AREA[jefeMatch].areas;
            }

            document.getElementById('asistencia-jefe-view').style.display = 'block';
            document.getElementById('asistencia-operario-view').style.display = 'none';

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

            // Carga automática del personal a cargo
            cargarPlanilla();
        } else {
            document.getElementById('asistencia-jefe-view').style.display = 'none';
            document.getElementById('asistencia-operario-view').style.display = 'block';

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
            // 1. Obtener colaboradores base
            const resColab = await fetch('/api/asistencia/colaboradores');
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
        if (!currentUserContext) return [];

        // Helper interno de normalización
        const norm = (str) => (str || '').toString().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().trim();

        // Excluir departamentos y personas que no requieren registro de asistencia
        const DEPTOS_EXCLUIDOS = ['COMERCIAL', 'ADMINISTRACION', 'ADMINISTRACIÓN'];
        const NOMBRES_EXCLUIDOS = ['TEMPORAL PULIDO 1', 'ADRIANA SATELITE'];

        lista = lista.filter(c => {
            const deptoC = norm(c.departamento);
            const nombreC = norm(c.nombre);
            const excluidoDepto = DEPTOS_EXCLUIDOS.some(d => deptoC.includes(norm(d)));
            const excluidoNombre = NOMBRES_EXCLUIDOS.some(n => nombreC.includes(norm(n)));
            return !excluidoDepto && !excluidoNombre;
        });

        // Gerencia / Admin → ven a TODOS
        const areasAsignadas = currentUserContext._areasAsignadas;
        if (areasAsignadas === null || areasAsignadas === undefined) {
            return lista;
        }

        // Jefes de área → solo ven personal de sus áreas asignadas (Normalizado)
        return lista.filter(c => {
            const deptoC = norm(c.departamento);
            return areasAsignadas.some(area => {
                const areaNorm = norm(area);
                return deptoC.includes(areaNorm) || areaNorm.includes(deptoC);
            });
        });
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
                                   onchange="ModuloAsistencia.calcularFila(this)" data-tipo="ingreso" value="${isAbsent ? '' : c.hora_entrada}" ${isAbsent ? 'disabled' : ''}>
                        </div>
                    </td>
                    <td style="width: 160px;">
                        <div class="input-group input-group-sm">
                            <span class="input-group-text bg-white border-end-0 text-danger"><i class="fas fa-sign-out-alt"></i></span>
                            <input type="time" class="form-control border-start-0 ps-0 bg-white" 
                                   onchange="ModuloAsistencia.calcularFila(this)" data-tipo="salida" value="${isAbsent ? '' : c.hora_salida}" ${isAbsent ? 'disabled' : ''}>
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
                                           onchange="ModuloAsistencia.calcularFila(this)" data-tipo="ingreso" value="${isAbsent ? '' : c.hora_entrada}" ${isAbsent ? 'disabled' : ''}>
                                </div>
                                <div class="col-12 text-center">
                                    <label class="small fw-bold text-muted mb-1 d-block"><i class="fas fa-sign-out-alt me-1 text-danger"></i>Salida</label>
                                    <input type="time" class="form-control form-control-lg border-0 bg-light shadow-none text-center mx-auto" 
                                           style="border-radius: 15px; font-size: 1.1rem; width: 80%;"
                                           onchange="ModuloAsistencia.calcularFila(this)" data-tipo="salida" value="${isAbsent ? '' : c.hora_salida}" ${isAbsent ? 'disabled' : ''}>
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

        // Disparar cálculo inicial para todas las filas auto-completadas
        recalcularTodaLaTabla();
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

        // Localizar ambos elementos vinculados al mismo colaborador
        const row = document.querySelector(`#asistencia-body tr[data-nombre="${nombre}"]`);
        const card = Array.from(document.querySelectorAll('#asistencia-cards-container .card'))
            .find(c => c.dataset.nombre === nombre);

        const hRealIngreso = parent.querySelector('[data-tipo="ingreso"]').value;
        const hRealSalida = parent.querySelector('[data-tipo="salida"]').value;
        const hOficialEntrada = parent.dataset.oficialEntrada;
        const hOficialSalida = parent.dataset.oficialSalida;
        const fechaStr = document.getElementById('asistencia-fecha').value;

        if (!hRealIngreso || !hRealSalida) return;

        // Lógica de cálculo
        const fecha = new Date(fechaStr + 'T00:00:00');
        const diaSemana = fecha.getDay(); // 0: Dom, 1: Lun ... 6: Sáb

        const tIngreso = timeToDecimal(hRealIngreso);
        const tSalida = timeToDecimal(hRealSalida);
        const tOficialEntrada = timeToDecimal(hOficialEntrada);
        const tOficialSalida = timeToDecimal(hOficialSalida);

        let totalHoras = tSalida - tIngreso;
        if (totalHoras < 0) totalHoras += 24; // Turnos que cruzan medianoche

        let ordinarias = 0;
        let extras = 0;

        // Reglas de negocio
        if (diaSemana === 0 || diaSemana === 6) {
            // Sábado (6) o Domingo (0) -> Todo es Extra
            ordinarias = 0;
            extras = totalHoras;
        } else {
            // Lunes a Viernes: Solo es ordinario lo que solapa con el horario oficial
            const inicioOrdinario = Math.max(tIngreso, tOficialEntrada);
            const finOrdinario = Math.min(tSalida, tOficialSalida);

            ordinarias = Math.max(0, finOrdinario - inicioOrdinario);
            extras = Math.max(0, totalHoras - ordinarias);
        }

        // Mostrar resultados con números limpios (sin decimales innecesarios)
        const ordFinal = Number(ordinarias.toFixed(2));
        const extFinal = Number(extras.toFixed(2));

        // ACTUALIZAR TABLA (Donde se leen los datos para Guardar)
        if (row) {
            row.querySelector('[data-tipo="ingreso"]').value = hRealIngreso;
            row.querySelector('[data-tipo="salida"]').value = hRealSalida;
            const inputOrd = row.querySelector('[data-tipo="ordinarias"]');
            const inputExt = row.querySelector('[data-tipo="extras"]');
            if (inputOrd) inputOrd.value = ordFinal;
            if (inputExt) inputExt.value = extFinal;
        }

        // ACTUALIZAR CARD (Visual en móvil)
        if (card) {
            card.querySelector('[data-tipo="ingreso"]').value = hRealIngreso;
            card.querySelector('[data-tipo="salida"]').value = hRealSalida;
            const labelOrd = card.querySelector('[data-tipo="ordinarias-card"]');
            const labelExt = card.querySelector('[data-tipo="extras-card"]');
            if (labelOrd) labelOrd.textContent = ordFinal;
            if (labelExt) labelExt.textContent = extFinal;
        }
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

            if (ingreso && salida) {
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
            const response = await fetch(`/ api / asistencia / mis_horas ? nombre = ${encodeURIComponent(currentUserContext.nombre)} `);
            const data = await response.json();

            if (data.status === 'success') {
                if (data.registros && data.registros.length > 0) {
                    body.innerHTML = data.registros.map(r => `
            < tr >
                            <td class="fw-bold text-muted">${r.fecha}</td>
                            <td><span class="badge bg-light text-dark">${formatTimeDisplay(r.ingreso_real)}</span></td>
                            <td><span class="badge bg-light text-dark">${formatTimeDisplay(r.salida_real)}</span></td>
                            <td class="text-primary fw-bold">${r.horas_ordinarias}</td>
                            <td class="text-danger fw-bold">${r.horas_extras}</td>
                        </tr >
            `).join('');
                } else {
                    body.innerHTML = '<tr><td colspan="5" class="text-center py-5 text-muted"><i class="fas fa-clock fa-2x mb-3" style="opacity: 0.5;"></i><br>Aún no hay horas registradas para esta semana</td></tr>';
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
