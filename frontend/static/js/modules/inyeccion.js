// ============================================
// inyeccion.js - Lógica de Inyección (SMART SEARCH) - NAMESPACED
// ============================================

const ModuloInyeccion = {
    productosData: [],
    responsablesData: [],
    items: [],
    isInitialized: false,
    isFetching: false,
    pncRows: [], // Lista de PNC dinámicos para el cierre
    currentModule: 'operator', // 'operator' (Reporte Máquina) o 'validation' (Validación Paola)

    
    normalizarCodigo: function(c) {
        if (!c) return "";
        return String(c).toUpperCase().replace(/FR-/gi, "").trim();
    },

    init: async function () {
        if (this.isInitialized) return;
        console.log('🔧 [Inyeccion] Inicializando...');
        await this.cargarDatos();
        this.configurarEventos();
        this.initAutocompleteProducto();
        this.initAutocompleteResponsable();
        this.intentarAutoSeleccionarResponsable();

        // Inicializar fecha
        const fechaHoy = new Date().toISOString().split('T')[0];
        const fechaInput = document.getElementById('fecha-inyeccion');
        if (fechaInput && !fechaInput.value) fechaInput.value = fechaHoy;

        // Configurar Smart Enter
        if (window.ModuloUX && window.ModuloUX.setupSmartEnter) {
            window.ModuloUX.setupSmartEnter({
                inputIds: [
                    'fecha-inyeccion', 'maquina-inyeccion', 'responsable-inyeccion',
                    'hora-llegada-inyeccion', 'hora-inicio-inyeccion', 'hora-termina-inyeccion',
                    'peso-vela-inyeccion', 'orden-produccion-inyeccion',
                    'codigo-producto-inyeccion', 'cavidades-inyeccion', 'cantidad-inyeccion',
                    'cantidad-real-inyeccion', 'pnc-inyeccion', 'peso-bujes-inyeccion', 'observaciones-inyeccion'
                ],
                actionBtnId: 'btn-agregar-inyeccion',
                autocomplete: {
                    inputId: 'codigo-producto-inyeccion',
                    suggestionsId: 'inyeccion-producto-suggestions'
                }
            });

            // Autocomplete para responsable
            window.ModuloUX.setupSmartEnter({
                inputIds: ['responsable-inyeccion'],
                autocomplete: {
                    inputId: 'responsable-inyeccion',
                    suggestionsId: 'inyeccion-responsable-suggestions'
                }
            });
        }

        // Registrar persistencia de formulario Juan Sebastian Request
        if (window.FormHelpers) {
            window.FormHelpers.registrarPersistencia('form-inyeccion');
        }

        // Persistir inicio al definir hora (patrón Pulido - visible en PC inmediatamente)
        document.getElementById('hora-inicio-inyeccion')?.addEventListener('change', () => {
            // Bloqueo crítico: Si estamos en modo VALIDACIÓN, NO crear un registro nuevo ni persistir inicio
            if (this.currentModule === 'validation' || this.esValidacionMode) {
                console.log('🚫 [Inyeccion] Persistencia bloqueada: Modo Validación activo.');
                return;
            }
            this.persistirInicioSQL();
        });

        this.isInitialized = true;
    },

    _idTurnoActivo: null, // ID para persistencia inmediata (patrón Pulido)

    /**
     * Persistencia inmediata al iniciar turno de inyección.
     * Crea un registro EN_PROCESO en db_inyeccion visible en el PC al instante.
     */
    persistirInicioSQL: async function () {
        // SEGURIDAD: No persistir si estamos en modo validación (Paola)
        if (this.currentModule === 'validation' || this.esValidacionMode) return;

        const responsable = document.getElementById('responsable-inyeccion')?.value || '';
        const maquina = document.getElementById('maquina-inyeccion')?.value || '';
        const id_codigo = document.getElementById('codigo-producto-inyeccion')?.value || '';

        if (!responsable || !maquina || !id_codigo) return;

        // Evitar múltiples llamadas al mismo tiempo
        if (this._persisting) return;
        this._persisting = true;

        const payload = {
            responsable: responsable,
            maquina: maquina,
            id_codigo: id_codigo,
            fecha_inicio: document.getElementById('fecha-inyeccion')?.value || '',
            hora_inicio: document.getElementById('hora-inicio-inyeccion')?.value || '',
            id_inyeccion: this._idTurnoActivo || undefined
        };

        try {
            const res = await fetchData('/api/iniciar_turno_inyeccion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res && res.success) {
                this._idTurnoActivo = res.id_inyeccion;
                this._idSqlActivo = res.id_sql; // Guardar ID primario para evitar duplicados
                console.log(`✅ [Inyeccion] Turno persistido en SQL: ${this._idTurnoActivo} (ID: ${this._idSqlActivo})`);
            }
        } catch (e) {
            console.error('Error persistencia inicio inyección:', e);
        } finally {
            this._persisting = false;
        }
    },

    cargarDatos: async function () {
        if (this.isFetching) return;
        try {
            this.isFetching = true;
            if (typeof window.mostrarLoading === 'function') window.mostrarLoading(true);

            console.log('📦 [Inyeccion] Cargando datos...');

            // 1. Cargar Responsables
            const responsables = await fetchData('/api/obtener_responsables');
            if (responsables) {
                // Mapear de objetos a strings para mantener compatibilidad con el buscador
                this.responsablesData = responsables.map(r => typeof r === 'object' ? r.nombre : r);
            }

            // 1.5 Cargar pendientes de validacion
            await this.cargarPendientesValidacion();

            // 2. Cargar Productos (Cache Compartido)
            if (window.AppState.sharedData.productos && window.AppState.sharedData.productos.length > 0) {
                this.productosData = window.AppState.sharedData.productos;
                console.log('✅ [Inyeccion] Usando productos del cache compartido:', this.productosData.length);
            } else {
                console.warn('⚠️ [Inyeccion] Cache vacío, intentando fetch...');
                const prods = await fetchData('/api/productos/listar');
                this.productosData = prods?.productos || prods?.items || (Array.isArray(prods) ? prods : []);
            }

            // 3. Cargar Máquinas
            const maquinas = await fetchData('/api/obtener_maquinas');
            this.actualizarSelect('maquina-inyeccion', maquinas);

            if (typeof window.mostrarLoading === 'function') window.mostrarLoading(false);
        } catch (error) {
            console.error('Error [Inyeccion] cargarDatos:', error);
            if (typeof window.mostrarLoading === 'function') window.mostrarLoading(false);
        } finally {
            this.isFetching = false;
        }
    },

    pendientesData: [], // Store the raw data from backend

    formatearFechaParaInput: function (fechaStr) {
        if (!fechaStr) return '';
        // DD/MM/YYYY -> YYYY-MM-DD
        const parts = fechaStr.split('/');
        if (parts.length === 3) {
            return `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
        }
        return fechaStr;
    },

    formatearHoraParaInput: function (horaStr) {
        if (!horaStr) return '';
        // H:mm -> HH:mm
        const parts = horaStr.split(':');
        if (parts.length === 2) {
            return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
        }
        return horaStr;
    },

    cargarPendientesValidacion: async function () {
        try {
            const select = document.getElementById('select-validar-lote');
            if (!select) return;

            select.innerHTML = '<option value="">Cargando...</option>';
            const res = await fetchData('/api/mes/pendientes_validacion');

            select.innerHTML = '<option value="">-- Seleccionar lote a validar (o dejar vacío para registro manual) --</option>';

            if (res && res.success && res.data) {
                this.pendientesData = res.data;
                console.log(`📋 [Inyeccion] ${res.data.length} pendientes cargados:`, res.data);
                
                // Agrupar por id_inyeccion para mostrar un solo lote por cada montaje mixto
                const grupos = {};
                res.data.forEach(lote => {
                    const id = lote.id_inyeccion;
                    if (!grupos[id]) {
                        grupos[id] = {
                            id: id,
                            maquina: lote.maquina || 'S/M',
                            codigos: [],
                            cantidadTotal: 0
                        };
                    }
                    if (lote.id_codigo) grupos[id].codigos.push(lote.id_codigo);
                    grupos[id].cantidadTotal += parseFloat(lote.cantidad_real) || 0;
                });

                Object.values(grupos).forEach(g => {
                    const opt = document.createElement('option');
                    opt.value = g.id;
                    const codigosTexto = [...new Set(g.codigos)].join(', ');
                    opt.textContent = `Lote: ${g.id} - ${g.maquina} - Códigos: ${codigosTexto}`;
                    select.appendChild(opt);
                });
            }
        } catch (err) {
            console.error("Error cargando pendientes validacion:", err);
            const select = document.getElementById('select-validar-lote');
            if (select) select.innerHTML = '<option value="">Error cargando pendientes</option>';
        }
    },

    seleccionarLoteValidacion: async function () {
        const select = document.getElementById('select-validar-lote');
        const idValidacion = select ? select.value : '';
        console.log(`🎯 [Inyeccion] Lote seleccionado ID: "${idValidacion}"`);

        if (!idValidacion) {
            console.log('🧹 [Inyeccion] No hay ID, limpiando formulario.');
            this.limpiarFormularioValidacion();
            return;
        }

        const registrosDelLote = this.pendientesData.filter(l => l.id_inyeccion === idValidacion);
        if (registrosDelLote.length === 0) {
            console.error('❌ [Inyeccion] No se encontraron registros para este ID.');
            return;
        }

        const lotePrincipal = registrosDelLote[0];

        const container = document.getElementById('contenedor-agregar-producto-inyeccion');
        if (container) container.classList.add('d-none');

        this.limpiarFormularioValidacion(false);
        this.esValidacionMode = true; // Activar modo validación inmediatamente
        this._idTurnoActivo = null;   // Limpiar ID temporal generado por persist-on-start previo

        if (document.getElementById('fecha-inyeccion')) {
            document.getElementById('fecha-inyeccion').value = (lotePrincipal.fecha || '').split('T')[0];
        }
        if (document.getElementById('maquina-inyeccion')) document.getElementById('maquina-inyeccion').value = lotePrincipal.maquina || '';
        if (document.getElementById('responsable-inyeccion')) document.getElementById('responsable-inyeccion').value = lotePrincipal.responsable || '';

        // Tarea 2: Llenar horas automáticamente
        if (document.getElementById('hora-inicio-inyeccion')) {
            document.getElementById('hora-inicio-inyeccion').value = lotePrincipal.hora_inicio || '';
        }
        if (document.getElementById('hora-termina-inyeccion')) {
            document.getElementById('hora-termina-inyeccion').value = lotePrincipal.hora_fin || '';
        }
        if (document.getElementById('hora-llegada-inyeccion')) {
            document.getElementById('hora-llegada-inyeccion').value = '06:00';
        }

        // 2. Poblar los Items desde los registros del lote
        registrosDelLote.forEach(reg => {
            const cavs = reg.cavidades || 1;
            const cantReal = parseFloat(String(reg.cantidad_real || 0).replace(/[^0-9.]/g, '')) || 0;
            const pncVal = parseFloat(String(reg.pnc || 0).replace(/[^0-9.]/g, '')) || 0;
            
            // Tarea 1: Calcular disparos reales
            const dispCalc = Math.ceil(cantReal / cavs);
            
            // Ajuste de Bruto vs Buenas Juan Sebastian Request
            // Si el backend envía cantReal (Buenas), el Bruto real es cantReal + pncVal
            const brutoReal = cantReal + pncVal;

            const nuevoItem = {
                id_item: Date.now().toString() + Math.random().toString(36).substr(2, 5),
                codigo_producto: reg.id_codigo || reg.codigo_sistema,
                no_cavidades: cavs,
                disparos: dispCalc,
                cantidad_real: brutoReal, // TOTAL (Buenas + PNC)
                manual_buenas: cantReal,   // BUENAS
                pnc: pncVal,
                piezasBuenas: cantReal,
                observaciones: reg.molde || '',
                id_inyeccion: reg.id_inyeccion,
                id_sql: reg.id_sql // <--- CAPTURAR ID PARA EVITAR SOBRESCRITURA
            };
            
            this.items.push(nuevoItem);
        });

        this.renderTablaItems();

        // Marcar explícitamente que estamos en modo validación
        this.esValidacionMode = true; 

        // Mostrar botón de VALIDACIÓN RÁPIDA en el header del form
        this.mostrarBotonValidacionRapida(idValidacion);
    },

    mostrarBotonValidacionRapida: function(idInyeccion) {
        const actions = document.querySelector('.form-actions');
        if (!actions) return;

        // Eliminar si ya existe
        const existing = document.getElementById('btn-validar-directo');
        if (existing) existing.remove();

        const btn = document.createElement('button');
        btn.id = 'btn-validar-directo';
        btn.type = 'button';
        btn.className = 'btn btn-success btn-lg mb-2';
        btn.style.width = '100%';
        btn.innerHTML = `<i class="fas fa-check-double me-2"></i> VALIDAR LOTE AHORA (Sin Modal)`;
        btn.onclick = () => this.validarRegistro(idInyeccion);

        actions.prepend(btn);
    },

    validarRegistro: async function (idInyeccion) {
        if (!idInyeccion) return;

        const result = await Swal.fire({
            title: '¿Validar Lote?',
            text: `Se marcarán todos los registros del lote ${idInyeccion} como VALIDADOS.`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, Validar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                mostrarLoading(true, 'Validando lote...');
                const res = await fetchData(`/api/inyeccion/validar/${idInyeccion}`, {
                    method: 'POST'
                });
                mostrarLoading(false);

                if (res && res.success) {
                    Swal.fire('¡Validado!', res.message, 'success');
                    this.limpiarFormularioValidacion(true);
                    if (window.ModuloHistorial) window.ModuloHistorial.cargarHistorial();
                } else {
                    Swal.fire('Error', res?.error || 'No se pudo validar', 'error');
                }
            } catch (err) {
                mostrarLoading(false);
                console.error("Error validando:", err);
                Swal.fire('Error', 'Error de conexión', 'error');
            }
        }
    },

    limpiarFormularioValidacion: function (limpiarSelect = true) {
        this.esValidacionMode = false; // Resetear modo validaciÃ³n
        if (limpiarSelect) {
            const select = document.getElementById('select-validar-lote');
            if (select) select.value = '';

            const container = document.getElementById('contenedor-agregar-producto-inyeccion');
            if (container) container.classList.remove('d-none');
        }

        if (document.getElementById('legacy-id-inyeccion')) {
            document.getElementById('legacy-id-inyeccion').value = '';
        }
        if (document.getElementById('legacy-id-programacion')) {
            document.getElementById('legacy-id-programacion').value = '';
        }

        this.items = [];
        this.renderTablaItems();
        this.limpiarFormularioProducto();
        document.getElementById('hora-llegada-inyeccion').value = '';
        document.getElementById('hora-inicio-inyeccion').value = '';
        document.getElementById('hora-termina-inyeccion').value = '';
        document.getElementById('orden-produccion-inyeccion').value = '';
        document.getElementById('peso-vela-inyeccion').value = 0;
        this.intentarAutoSeleccionarResponsable();
    },

    actualizarSelect: function (id, datos) {
        const select = document.getElementById(id);
        if (!select) return;
        select.innerHTML = '<option value="">-- Seleccionar --</option>';
        if (datos) {
            datos.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item;
                opt.textContent = item;
                select.appendChild(opt);
            });
        }
    },

    intentarAutoSeleccionarResponsable: function () {
        const input = document.getElementById('responsable-inyeccion');
        if (!input) return;

        let nombreUsuario = null;

        if (window.AppState?.user?.name) {
            nombreUsuario = window.AppState.user.name;
        } else if (window.AuthModule?.currentUser?.nombre) {
            nombreUsuario = window.AuthModule.currentUser.nombre;
        }

        if (nombreUsuario) {
            input.value = nombreUsuario;
            console.log(`✅ [Inyeccion] Responsable auto-asignado: ${nombreUsuario}`);
        } else {
            console.log('⏳ [Inyeccion] Esperando usuario para auto-asignación...');
            const handler = () => {
                this.intentarAutoSeleccionarResponsable();
                window.removeEventListener('user-ready', handler);
            };
            window.addEventListener('user-ready', handler);

            // Polling fallback
            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                if (window.AppState?.user?.name) {
                    this.intentarAutoSeleccionarResponsable();
                    clearInterval(interval);
                    window.removeEventListener('user-ready', handler);
                }
                if (attempts > 10) clearInterval(interval);
            }, 500);
        }
    },

    initAutocompleteProducto: function () {
        const input = document.getElementById('codigo-producto-inyeccion');
        const suggestionsDiv = document.getElementById('inyeccion-producto-suggestions');

        if (!input || !suggestionsDiv) return;

        let debounceTimer;

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim().toLowerCase();

            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            debounceTimer = setTimeout(() => {
                const resultados = this.productosData.filter(prod =>
                    String(prod.codigo_sistema || '').toLowerCase().includes(query) ||
                    String(prod.descripcion || '').toLowerCase().includes(query)
                ).slice(0, 15);

                this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                    input.value = item.codigo_sistema || item.codigo;
                    this.autocompletarCodigoEnsamble(input.value);
                    suggestionsDiv.classList.remove('active');
                }, true);
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    initAutocompleteResponsable: function () {
        const input = document.getElementById('responsable-inyeccion');
        const suggestionsDiv = document.getElementById('inyeccion-responsable-suggestions');

        if (!input || !suggestionsDiv) return;

        input.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            if (query.length < 1) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            const resultados = this.responsablesData.filter(resp =>
                resp.toLowerCase().includes(query)
            );

            this.renderSuggestions(suggestionsDiv, resultados, (item) => {
                input.value = item;
                suggestionsDiv.classList.remove('active');
            }, false);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    renderSuggestions: function (container, items, onSelect, isProduct) {
        if (isProduct) {
            renderProductSuggestions(container, items, onSelect);
        } else {
            if (items.length === 0) {
                container.innerHTML = '<div class="suggestion-item">No se encontraron resultados</div>';
                container.classList.add('active');
                return;
            }

            container.innerHTML = items.map(item => `<div class="suggestion-item" data-val="${item}">${item}</div>`).join('');

            container.querySelectorAll('.suggestion-item').forEach((div, index) => {
                div.addEventListener('click', () => {
                    onSelect(items[index]);
                });
            });

            container.classList.add('active');
        }
    },

    autocompletarCodigoEnsamble: async function (codigoProducto) {
        const codigoEnsambleField = document.getElementById('codigo-ensamble-inyeccion');
        if (!codigoProducto || !codigoEnsambleField) return;

        try {
            codigoEnsambleField.value = 'Buscando...';
            codigoEnsambleField.classList.add('loading');

            const response = await fetch(`/api/inyeccion/ensamble_desde_producto?codigo=${encodeURIComponent(codigoProducto)}`);
            const data = await response.json();

            if (data.success && data.codigo_ensamble) {
                codigoEnsambleField.value = data.codigo_ensamble;
            } else {
                codigoEnsambleField.value = '';
            }
        } catch (error) {
            console.error('Error [Inyeccion] buscando ensamble:', error);
            codigoEnsambleField.value = codigoProducto;
        } finally {
            codigoEnsambleField.classList.remove('loading');
        }
    },

    configurarEventos: function () {
        const form = document.getElementById('form-inyeccion');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.registrar();
            };
        }

        const btnAgregar = document.getElementById('btn-agregar-inyeccion');
        if (btnAgregar) {
            btnAgregar.onclick = () => this.agregarItem();
        }

        const btnDefectos = document.getElementById('btn-defectos-inyeccion');
        if (btnDefectos) {
            btnDefectos.replaceWith(btnDefectos.cloneNode(true));
            const newBtn = document.getElementById('btn-defectos-inyeccion');
            newBtn.onclick = () => {
                if (typeof window.abrirModalInyeccion === 'function') {
                    window.abrirModalInyeccion();
                }
            };
        }

        // Limpiar peso vela si cambia la maquina
        const selectMaquina = document.getElementById('maquina-inyeccion');
        if (selectMaquina) {
            selectMaquina.addEventListener('change', () => {
                const pesoVela = document.getElementById('peso-vela-inyeccion');
                if (pesoVela && this.items.length === 0) {
                    pesoVela.value = 0;
                }
            });
        }

        ['cantidad-inyeccion', 'cavidades-inyeccion', 'pnc-inyeccion', 'cantidad-real-inyeccion', 'inyeccion-entrada', 'inyeccion-salida'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', (e) => this.calculos(e.target.id));
        });
    },

    calculos: function (triggerId) {
        const inputEntrada = document.getElementById('inyeccion-entrada');
        const inputSalida = document.getElementById('inyeccion-salida');
        const inputDisparos = document.getElementById('cantidad-inyeccion');
        const inputReal = document.getElementById('cantidad-real-inyeccion');
        const inputCavidades = document.getElementById('cavidades-inyeccion');
        const inputPnc = document.getElementById('pnc-inyeccion');

        const entrada = parseInt(inputEntrada?.value) || 0;
        const salida = parseInt(inputSalida?.value) || 0;
        const cavidades = parseInt(inputCavidades?.value) || 1;
        const pnc = parseInt(inputPnc?.value) || 0;
        
        let disparos = parseInt(inputDisparos?.value);
        
        // 1. Sincronización de Disparos por Entrada/Salida
        // SOLO ocurre si el trigger fue entrada o salida para garantizar independencia total
        if ((triggerId === 'inyeccion-entrada' || triggerId === 'inyeccion-salida') && salida > 0 && salida >= entrada) {
            const calcDisparos = salida - entrada;
            disparos = calcDisparos;
            if (inputDisparos) inputDisparos.value = disparos;
        } 

        // Si disparos es NaN, lo tomamos como 0 para los cálculos pero NO sobrescribimos el input
        const disparosCalculo = isNaN(disparos) ? 0 : disparos;

        // Sincronizar items si estamos en modo validación
        if (this.esValidacionMode && this.items && this.items.length > 0 && disparosCalculo > 0) {
            let reRender = false;
            this.items.forEach(item => {
                if (item.disparos !== disparosCalculo) {
                    item.disparos = disparosCalculo;
                    const produccionTeorica = item.disparos * item.no_cavidades;
                    item.cantidad_real = produccionTeorica;
                    item.piezasBuenas = Math.max(0, produccionTeorica - item.pnc);
                    item.manual_buenas = null;
                    reRender = true;
                }
            });
            if (reRender) this.renderTablaItems();
        }

        const manualBuenas = parseInt(inputReal?.value) || 0;
        const isManual = inputReal?.value !== '';

        const produccionTeorica = disparosCalculo * cavidades;
        const piezasBuenas = isManual ? manualBuenas : Math.max(0, produccionTeorica - pnc);
        const produccionBrutaReal = isManual ? (manualBuenas + pnc) : produccionTeorica;

        const displayProduccion = document.getElementById('produccion-calculada');
        const displayFormula = document.getElementById('formula-calc');
        const displayBuenas = document.getElementById('piezas-buenas');

        // Alerta visual de proyección
        const projectionAlert = document.getElementById('inyeccion-proyeccion-alert');
        if (projectionAlert) {
            const diff = piezasBuenas - produccionTeorica;
            const sign = diff >= 0 ? '+' : '';
            const color = diff >= 0 ? '#10b981' : '#ef4444';
            const bgColor = diff >= 0 ? '#f0fdf4' : '#fef2f2';

            projectionAlert.style.display = 'block';
            projectionAlert.style.background = bgColor;
            projectionAlert.style.border = `1px solid ${color}`;
            projectionAlert.style.padding = '10px';
            projectionAlert.style.borderRadius = '8px';
            projectionAlert.style.marginTop = '10px';
            projectionAlert.style.fontWeight = 'bold';
            projectionAlert.style.color = color;
            projectionAlert.innerHTML = `
                <i class="fas ${diff >= 0 ? 'fa-check-circle' : 'fa-exclamation-triangle'}"></i> 
                Proyectado: ${produccionTeorica} | Diferencia: <span style="font-size: 1.1rem">${sign}${diff}</span>
            `;
        }

        if (displayProduccion) displayProduccion.textContent = piezasBuenas.toLocaleString();

        if (displayFormula) {
            if (isManual) {
                const diff = produccionBrutaReal - produccionTeorica;
                const sign = diff >= 0 ? '+' : '';
                const color = diff >= 0 ? '#4ade80' : '#f87171';
                displayFormula.innerHTML = `Teórica: <b>${produccionTeorica}</b> | Bruto (Buenas+PNC): <b>${produccionBrutaReal}</b> <span style="color: ${color}; font-weight: bold; margin-left:8px;">(${sign}${diff})</span>`;
            } else {
                displayFormula.textContent = `Disparos: ${disparosCalculo} × Cavidades: ${cavidades} = ${produccionTeorica} (Teórica)`;
            }
        }

        if (displayBuenas) displayBuenas.textContent = `Real: ${piezasBuenas} | PNC: ${pnc}`;
    },

    agregarItem: function () {
        const rawCode = document.getElementById('codigo-producto-inyeccion')?.value || '';
        const codigo_producto = this.normalizarCodigo(rawCode);
        const cavidades = parseInt(document.getElementById('cavidades-inyeccion')?.value) || 1;
        const disparos = parseInt(document.getElementById('cantidad-inyeccion')?.value) || 0;
        const inputReal = document.getElementById('cantidad-real-inyeccion');
        const manualBuenas = parseInt(inputReal?.value) || 0;
        const isManual = inputReal?.value !== '';

        if (!codigo_producto) {
            Swal.fire('Atención', 'Ingresa un código de producto', 'warning');
            return;
        }
        if (disparos <= 0) {
            Swal.fire('Atención', 'Los disparos deben ser mayor a 0', 'warning');
            return;
        }

        const pnc = parseInt(document.getElementById('pnc-inyeccion')?.value) || 0;
        const criterio_pnc = document.getElementById('criterio-pnc-hidden-inyeccion')?.value || '';

        const codigo_ensamble = document.getElementById('codigo-ensamble-inyeccion')?.value || '';
        const peso_bujes = parseFloat(document.getElementById('peso-bujes-inyeccion')?.value) || 0;
        const observaciones = document.getElementById('observaciones-inyeccion')?.value || '';

        const produccionTeorica = disparos * cavidades;
        const piezasBuenas = isManual ? manualBuenas : Math.max(0, produccionTeorica - pnc);
        const cantidadRealBruta = isManual ? (manualBuenas + pnc) : produccionTeorica;

        const legacyId = document.getElementById('legacy-id-inyeccion')?.value || '';

        const nuevoItem = {
            id_item: Date.now().toString() + Math.random().toString(36).substr(2, 5),
            codigo_producto,
            no_cavidades: cavidades,
            disparos,
            cantidad_real: cantidadRealBruta,
            manual_buenas: isManual ? manualBuenas : null,
            pnc,
            criterio_pnc,
            codigo_ensamble,
            peso_bujes,
            observaciones,
            piezasBuenas, // Solo para visualizacion
            id_inyeccion: legacyId ? legacyId : undefined // <-- INYECTAR ID AQUÍ
        };

        this.items.push(nuevoItem);
        this.renderTablaItems();
        this.limpiarFormularioProducto();

        // Limpiar el legacy ID luego de agregarlo para evitar duplicados en el mismo turno manual
        document.getElementById('legacy-id-inyeccion').value = '';

        Swal.fire({
            title: 'Agregado',
            text: 'Producto agregado a la lista',
            icon: 'success',
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 2000
        });
    },

    removerItem: function (index) {
        Swal.fire({
            title: '¿Eliminar producto?',
            text: "Se quitará de la lista actual.",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                this.items.splice(index, 1);
                this.renderTablaItems();
            }
        });
    },

    editarItem: function (index, campo, valor) {
        const item = this.items[index];
        if (!item) return;

        let val = parseFloat(valor);
        if (isNaN(val) || val < 0) val = 0;

        if (campo === 'manual_buenas') {
            item.manual_buenas = valor === '' ? null : val;
        } else if (campo === 'no_cavidades') {
            item.no_cavidades = val;
        } else {
            item[campo] = val;
        }

        const produccionTeorica = item.disparos * item.no_cavidades;

        if (item.manual_buenas !== null) {
            item.piezasBuenas = item.manual_buenas;
            item.cantidad_real = item.manual_buenas + item.pnc;
        } else {
            item.cantidad_real = produccionTeorica;
            item.piezasBuenas = Math.max(0, produccionTeorica - item.pnc);
        }

        this.renderTablaItems();
    },

    editarPNCLista: async function (index) {
        const item = this.items[index];

        const { value: formValues } = await Swal.fire({
            title: 'Reportar PNC',
            html: `
                <div class="mb-3 text-start">
                    <label class="form-label fw-bold">Cantidad PNC</label>
                    <input type="number" id="swal-pnc-qty" class="form-control" min="0" value="${item.pnc}">
                </div>
                <div class="text-start">
                    <label class="form-label fw-bold">Criterio (Opcional)</label>
                    <select id="swal-pnc-crit" class="form-select">
                        <option value="">Selecciona un motivo...</option>
                        <option value="ESCASO" ${item.criterio_pnc === 'ESCASO' ? 'selected' : ''}>Escaso</option>
                        <option value="RECHUPE" ${item.criterio_pnc === 'RECHUPE' ? 'selected' : ''}>Rechupe</option>
                        <option value="CONTAMINADO" ${item.criterio_pnc === 'CONTAMINADO' ? 'selected' : ''}>Contaminado</option>
                        <option value="BUJE DE PRUEBA" ${item.criterio_pnc === 'BUJE DE PRUEBA' ? 'selected' : ''}>Buje de Prueba</option>
                    </select>
                </div>
            `,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonText: 'Guardar PNC',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                return {
                    qty: parseInt(document.getElementById('swal-pnc-qty').value) || 0,
                    crit: document.getElementById('swal-pnc-crit').value
                }
            }
        });

        if (formValues) {
            item.pnc = formValues.qty;
            item.criterio_pnc = formValues.crit;
            // Forzar actualización
            this.editarItem(index, 'pnc', formValues.qty);
        }
    },

    limpiarFormularioProducto: function () {
        document.getElementById('codigo-producto-inyeccion').value = '';
        document.getElementById('cavidades-inyeccion').value = 1;
        // document.getElementById('cantidad-inyeccion').value = ''; // No limpiar, se mantiene por máquina
        document.getElementById('cantidad-real-inyeccion').value = '';
        document.getElementById('pnc-inyeccion').value = 0;
        document.getElementById('criterio-pnc-hidden-inyeccion').value = '';
        document.getElementById('codigo-ensamble-inyeccion').value = '';
        document.getElementById('peso-bujes-inyeccion').value = 0;
        document.getElementById('observaciones-inyeccion').value = '';
        this.calculos();
        document.getElementById('codigo-producto-inyeccion').focus();
    },

    renderTablaItems: function () {
        const tbody = document.getElementById('lista-inyeccion-body');
        const tfoot = document.getElementById('inyeccion-tfoot');

        if (!tbody) return;

        if (this.items.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted py-5">
                        <i class="fas fa-box-open mb-3" style="font-size: 2rem; color: #cbd5e1;"></i>
                        <p class="mb-0">No hay productos en la lista.</p>
                        <small>Llena la sección de Agregar Producto y presiona "+ Agregar Producto".</small>
                    </td>
                </tr>
            `;
            if (tfoot) tfoot.style.display = 'none';
            return;
        }

        let totalBuenas = 0;
        let totalPNC = 0;
        let totalBruto = 0;

        tbody.innerHTML = this.items.map((item, index) => {
            totalBuenas += item.piezasBuenas;
            totalPNC += item.pnc;
            totalBruto += item.cantidad_real;

            return `
            <tr>
                <td class="fw-bold align-middle">${item.codigo_producto}</td>
                <td class="text-center align-middle">
                    <input type="number" min="1" class="form-control form-control-sm text-center mx-auto" style="width: 60px;" value="${item.no_cavidades}" onchange="ModuloInyeccion.editarItem(${index}, 'no_cavidades', this.value)">
                </td>
                <td class="text-center align-middle">
                    <input type="number" min="1" class="form-control form-control-sm text-center mx-auto" style="width: 70px;" value="${item.disparos}" onchange="ModuloInyeccion.editarItem(${index}, 'disparos', this.value)">
                </td>
                <td class="text-center align-middle">
                    <div class="d-flex flex-column align-items-center">
                        <small class="text-muted" style="font-size: 0.65rem;">Cant. Real</small>
                        <input type="number" min="0" class="form-control form-control-sm text-center mx-auto fw-bold text-success border-success" style="width: 85px;" value="${item.manual_buenas !== null ? item.manual_buenas : item.piezasBuenas}" onchange="ModuloInyeccion.editarItem(${index}, 'manual_buenas', this.value)">
                    </div>
                </td>
                <td class="text-center align-middle">
                    <div class="d-flex flex-column align-items-center">
                        <small class="text-muted" style="font-size: 0.65rem;">PNC</small>
                        <div class="d-flex justify-content-center align-items-center gap-1">
                            <input type="number" min="0" class="form-control form-control-sm text-center text-danger fw-bold border-danger" style="width: 65px;" value="${item.pnc}" onchange="ModuloInyeccion.editarItem(${index}, 'pnc', this.value)">
                            <button type="button" class="btn btn-sm btn-outline-danger px-2 py-1" onclick="ModuloInyeccion.editarPNCLista(${index})"><i class="fas fa-list-ul"></i></button>
                        </div>
                    </div>
                </td>
                <td class="text-center align-middle">
                    <div class="d-flex flex-column align-items-center">
                        <small class="text-muted" style="font-size: 0.65rem;">Peso (kg)</small>
                        <input type="number" step="0.01" min="0" class="form-control form-control-sm text-center mx-auto border-primary" style="width: 80px;" value="${item.peso_bujes || 0}" onchange="ModuloInyeccion.editarItem(${index}, 'peso_bujes', this.value)">
                    </div>
                </td>
                <td class="text-center align-middle">
                    <span class="badge bg-secondary fs-6">${item.cantidad_real.toLocaleString()}</span>
                </td>
                <td class="text-center align-middle">
                    <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="ModuloInyeccion.removerItem(${index})" title="Eliminar">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
            `;
        }).join('');

        if (tfoot) {
            tfoot.style.display = 'table-footer-group';
            document.getElementById('inyeccion-total-buenas').textContent = totalBuenas.toLocaleString();
            document.getElementById('inyeccion-total-pnc').textContent = totalPNC.toLocaleString();
            const brutoFooter = document.getElementById('inyeccion-total-bruto');
            if (brutoFooter) brutoFooter.textContent = totalBruto.toLocaleString();
        }
    },

    registrar: async function () {
        if (this.items.length === 0) {
            Swal.fire('Advertencia', 'Agrega al menos un producto a la lista', 'warning');
            return;
        }

        // --- SUB-MÓDULO 3: VALIDACIÓN (Paola) ---
        if (this.currentModule === 'validation' || this.esValidacionMode) {
            const idIny = document.getElementById('select-validar-lote')?.value;
            
            // Si es un lote existente seleccionado del dropdown
            if (idIny) {
                this.validarRegistro(idIny);
                return;
            }

            // Si es "ENTRADA MANUAL" en el panel de Validación
            // REQUERIMIENTO: Guardado directo sin modal de PNC
            const confirm = await Swal.fire({
                title: '¿Registrar Entrada Manual?',
                text: "Se guardará el registro directamente como VALIDADO.",
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Sí, Registrar',
                cancelButtonText: 'Volver'
            });

            if (confirm.isConfirmed) {
                this.esValidacionMode = true; // Forzar para el backend
                this.confirmarRegistroFinal();
            }
            return;
        }

        // --- SUB-MÓDULO 2: REPORTE DE MÁQUINA (Operario) ---
        const horaInicio = document.getElementById('hora-inicio-inyeccion')?.value || '00:00';
        const horaFin = document.getElementById('hora-termina-inyeccion')?.value || '00:00';
        
        if (horaFin <= horaInicio) {
            Swal.fire({
                title: 'Error de Tiempos',
                text: 'La Hora de Fin (Termina) debe ser estrictamente posterior a la Hora de Inicio.',
                icon: 'error',
                confirmButtonColor: '#d33'
            });
            return;
        }

        // REQUERIMIENTO: SÍ debe salir el modal de 'Finalizar Reporte' (PNC, Disparos, etc.)
        this.abrirModalCierre();
    },

    abrirModalCierre: function () {
        const modal = document.getElementById('modal-cierre-inyeccion');
        if (!modal) return;

        // Reset de PNCs del modal
        this.pncRows = [];
        this.renderFilasPnc();

        // Calcular totales para el resumen
        let totalBuenas = 0;
        this.items.forEach(item => {
            totalBuenas += (item.piezasBuenas || 0);
        });

        document.getElementById('resumen-buenas-inyeccion').textContent = totalBuenas.toLocaleString();
        document.getElementById('resumen-pnc-inyeccion').textContent = "0";

        modal.style.display = 'flex';
    },

    agregarFilaPnc: function () {
        const id = Date.now();
        this.pncRows.push({
            id,
            codigo: '',
            motivo: '',
            cantidad: 0
        });
        this.renderFilasPnc();
    },

    eliminarFilaPnc: function (id) {
        this.pncRows = this.pncRows.filter(r => r.id !== id);
        this.renderFilasPnc();
        this.actualizarTotalesResumen();
    },

    actualizarDatoPnc: function (id, campo, valor) {
        const row = this.pncRows.find(r => r.id === id);
        if (row) {
            if (campo === 'cantidad') {
                row[campo] = parseInt(valor) || 0;
                this.actualizarTotalesResumen();
            } else {
                row[campo] = valor;
            }
        }
    },

    actualizarTotalesResumen: function () {
        const totalPnc = this.pncRows.reduce((sum, row) => sum + row.cantidad, 0);
        const display = document.getElementById('resumen-pnc-inyeccion');
        if (display) display.textContent = totalPnc.toLocaleString();
    },

    renderFilasPnc: function () {
        const container = document.getElementById('inyeccion-pnc-container');
        const emptyMsg = document.getElementById('inyeccion-pnc-empty-msg');
        if (!container) return;

        if (this.pncRows.length === 0) {
            if (emptyMsg) emptyMsg.style.display = 'block';
            container.querySelectorAll('.pnc-row').forEach(el => el.remove());
            return;
        }

        if (emptyMsg) emptyMsg.style.display = 'none';

        // Mantener solo las filas que existen en el estado
        const existingIds = this.pncRows.map(r => `pnc-row-${r.id}`);
        container.querySelectorAll('.pnc-row').forEach(el => {
            if (!existingIds.includes(el.id)) el.remove();
        });

        this.pncRows.forEach(row => {
            let rowEl = document.getElementById(`pnc-row-${row.id}`);
            if (!rowEl) {
                rowEl = document.createElement('div');
                rowEl.id = `pnc-row-${row.id}`;
                rowEl.className = 'pnc-row d-flex gap-2 align-items-start p-2 border rounded-3 bg-white shadow-sm';
                rowEl.innerHTML = `
                    <div class="flex-grow-1 position-relative">
                        <input type="text" class="form-control form-control-sm pnc-codigo-input" placeholder="Referencia..." value="${row.codigo}" oninput="ModuloInyeccion.actualizarDatoPnc(${row.id}, 'codigo', this.value)">
                        <div class="autocomplete-suggestions pnc-suggestions" id="suggestions-${row.id}"></div>
                    </div>
                    <div style="width: 140px;">
                        <select class="form-select form-select-sm" onchange="ModuloInyeccion.actualizarDatoPnc(${row.id}, 'motivo', this.value)">
                            <option value="">Motivo...</option>
                            <option value="RECHUPE" ${row.motivo === 'RECHUPE' ? 'selected' : ''}>Rechupe</option>
                            <option value="QUEMADO" ${row.motivo === 'QUEMADO' ? 'selected' : ''}>Quemado</option>
                            <option value="INCOMPLETA" ${row.motivo === 'INCOMPLETA' ? 'selected' : ''}>Incompleta</option>
                            <option value="REBABA" ${row.motivo === 'REBABA' ? 'selected' : ''}>Rebaba</option>
                            <option value="MANCHA ACEITE" ${row.motivo === 'MANCHA ACEITE' ? 'selected' : ''}>Mancha Aceite</option>
                            <option value="CONTAMINADO" ${row.motivo === 'CONTAMINADO' ? 'selected' : ''}>Contaminado</option>
                        </select>
                    </div>
                    <div style="width: 80px;">
                        <input type="number" class="form-control form-control-sm text-center" placeholder="Cant" value="${row.cantidad}" oninput="ModuloInyeccion.actualizarDatoPnc(${row.id}, 'cantidad', this.value)">
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="ModuloInyeccion.eliminarFilaPnc(${row.id})">
                        <i class="fas fa-times"></i>
                    </button>
                `;
                container.appendChild(rowEl);
                this.initAutocompletePncRow(row.id);
            }
        });
    },

    initAutocompletePncRow: function (rowId) {
        const rowEl = document.getElementById(`pnc-row-${rowId}`);
        if (!rowEl) return;
        const input = rowEl.querySelector('.pnc-codigo-input');
        const suggestionsDiv = rowEl.querySelector('.pnc-suggestions');

        let debounceTimer;
        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim().toLowerCase();
            if (query.length < 2) {
                suggestionsDiv.classList.remove('active');
                return;
            }

            debounceTimer = setTimeout(() => {
                const resultados = this.productosData.filter(prod =>
                    String(prod.codigo_sistema || '').toLowerCase().includes(query) ||
                    String(prod.descripcion || '').toLowerCase().includes(query)
                ).slice(0, 10);

                if (window.renderProductSuggestions) {
                    window.renderProductSuggestions(suggestionsDiv, resultados, (item) => {
                        input.value = item.codigo_sistema || item.codigo;
                        this.actualizarDatoPnc(rowId, 'codigo', input.value);
                        suggestionsDiv.classList.remove('active');
                    });
                }
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.remove('active');
            }
        });
    },

    confirmarRegistroFinal: async function () {
        const btn = document.getElementById('btn-finalizar-inyeccion');
        const btnSubmitOriginal = document.querySelector('#form-inyeccion button[type="submit"]');

        try {
            if (btn) btn.disabled = true;
            mostrarLoading(true, 'Guardando reporte e inyectando PNC...');

            // Datos comunes de turno
            const datosTurno = {
                fecha_inicio: document.getElementById('fecha-inyeccion')?.value || '',
                maquina: document.getElementById('maquina-inyeccion')?.value || '',
                responsable: document.getElementById('responsable-inyeccion')?.value || '',
                hora_llegada: document.getElementById('hora-llegada-inyeccion')?.value || '',
                hora_inicio: document.getElementById('hora-inicio-inyeccion')?.value || '',
                hora_termina: document.getElementById('hora-termina-inyeccion')?.value || '',
                orden_produccion: document.getElementById('orden-produccion-inyeccion')?.value || '',
                entrada_manual: parseFloat(String(document.getElementById('inyeccion-entrada')?.value || '0').replace(/[^0-9.]/g, '')) || 0,
                salida_manual: parseFloat(String(document.getElementById('inyeccion-salida')?.value || '0').replace(/[^0-9.]/g, '')) || 0,
                peso_vela_maquina: parseFloat(String(document.getElementById('peso-vela-inyeccion')?.value || '0').replace(/[^0-9.]/g, '')) || 0,
                id_programacion: document.getElementById('legacy-id-programacion')?.value || '',
                almacen_destino: 'POR PULIR',
                es_validacion: (this.currentModule === 'validation' || this.esValidacionMode),
                id_inyeccion: this._idTurnoActivo || undefined,
                id_sql: this._idSqlActivo || undefined
            };

            const payload = {
                turno: datosTurno,
                items: this.items,
                pnc_list: this.pncRows.filter(r => r.codigo && r.cantidad > 0)
            };

            console.log('📤 [Inyeccion] ENVIANDO REPORTE FINAL CON PNC:', payload);

            const response = await fetch('/api/inyeccion/lote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const resultado = await response.json();

            if (response.ok && resultado.success) {
                Swal.fire('¡Registrado!', 'El reporte de producción se ha guardado correctamente.', 'success');
                
                // Cerrar modal si estaba abierto
                const modal = document.getElementById('modal-cierre-inyeccion');
                if (modal) modal.style.display = 'none';

                // Reiniciar todo
                this.items = [];
                this.pncRows = [];
                this.renderTablaItems();
                document.getElementById('form-inyeccion')?.reset();
                if (window.FormHelpers) window.FormHelpers.limpiarPersistencia('form-inyeccion');
                this._idTurnoActivo = null;
                this._idSqlActivo = null; // Limpiar ID SQL
                this.intentarAutoSeleccionarResponsable();
                this.limpiarFormularioValidacion(true);
            } else {
                Swal.fire('Error', resultado.error || 'Error procesando reporte', 'error');
            }

        } catch (e) {
            console.error('Error [Inyeccion] confirmar registro:', e);
            Swal.fire('Error de Conexión', e.message, 'error');
        } finally {
            mostrarLoading(false);
            if (btn) btn.disabled = false;
        }
    },

    // Alias para compatibilidad
    inicializar: function () {
        return this.init();
    }
};

// Exportación global
window.ModuloInyeccion = ModuloInyeccion;
window.initInyeccion = () => ModuloInyeccion.init();
