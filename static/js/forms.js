// Renderizar campos del formulario
function renderFields(tab) {
    const container = document.getElementById('dynamicFields');
    const btn = document.getElementById('btnSubmit');
    
    if (!container || !btn) return;
    
    container.innerHTML = '';
    btn.style.background = "var(--primary)";
    btn.innerText = 'Registrar Operación';

    const fields = configs[tab] || [];
    
    fields.forEach(f => {
        const div = document.createElement('div');
        div.className = f.full ? 'field full-width' : 'field';
        let inputHtml = '';

        if (f.type === 'select_responsable') {
            inputHtml = `<select name="${f.name}" ${f.req ? 'required' : ''}>
                <option value="">Seleccione...</option>
                ${window.AppState.listaResponsables.map(n => `<option value="${n}">${n}</option>`).join('')}
            </select>`;
        } else if (f.type === 'datalist_productos') {
            inputHtml = `
                <input list="opts_productos" name="${f.name}" 
                    ${f.req ? 'required' : ''} 
                    placeholder="Buscar..." 
                    style="text-transform: uppercase;">
                <datalist id="opts_productos">
                    ${window.AppState.listaProductos.map(p => `<option value="${p}">${p}</option>`).join('')}
                </datalist>
            `;
        } else if (f.type === 'datalist_clientes') {
            inputHtml = `
                <input list="opts_clientes" name="${f.name}" 
                    ${f.req ? 'required' : ''} 
                    placeholder="Buscar cliente...">
                <datalist id="opts_clientes">
                    ${window.AppState.listaClientes.map(c => `<option value="${c}">${c}</option>`).join('')}
                </datalist>
            `;
        } else if (f.type === 'select') {
            inputHtml = `<select name="${f.name}">
                ${f.options.map(o => `<option value="${o}">${o}</option>`).join('')}
            </select>`;
        } else if (f.type === 'textarea') {
            inputHtml = `<textarea name="${f.name}" rows="3" ${f.req ? 'required' : ''}></textarea>`;
        } else {
            const attrs = [];
            if (f.req) attrs.push('required');
            if (f.val !== undefined) attrs.push(`value="${f.val}"`);
            if (f.readonly) attrs.push('readonly');
            if (f.step) attrs.push(`step="${f.step}"`);
            if (f.min !== undefined) attrs.push(`min="${f.min}"`);
            
            inputHtml = `<input type="${f.type}" name="${f.name}" ${attrs.join(' ')}>`;
        }

        div.innerHTML = `<label>${f.label}</label>${inputHtml}`;
        container.appendChild(div);
    });

    // Lógica de cálculos automáticos
    if (tab === 'inyeccion') {
        setupInyeccionCalculations(container, btn);
    } else if (tab === 'pulido') {
        setupPulidoCalculations(container, btn);
    } else if (tab === 'ensamble') {
        setupEnsambleCalculations(container, btn);
    }

    // Auto-fecha hoy para campos de fecha vacíos
    container.querySelectorAll('input[type="date"]').forEach(d => { 
        if(!d.value) d.valueAsDate = new Date(); 
    });
    
    // Auto-hora actual para campos de hora vacíos
    container.querySelectorAll('input[type="time"]').forEach(t => { 
        if(!t.value) {
            const now = new Date();
            const horas = now.getHours().toString().padStart(2, '0');
            const minutos = now.getMinutes().toString().padStart(2, '0');
            t.value = `${horas}:${minutos}`;
        }
    });
}

// Configurar cálculos para inyección
function setupInyeccionCalculations(container, btn) {
    const inCav = container.querySelector('[name="no_cavidades"]');
    const inGol = container.querySelector('[name="cantidad_real"]');
    const inPNC = container.querySelector('[name="pnc"]');
    
    const calcularTotal = () => {
        const cav = parseInt(inCav.value) || 0;
        const gol = parseInt(inGol.value) || 0;
        const pnc = parseInt(inPNC.value) || 0;
        const total = (cav * gol) - pnc;
        
        if (total > 0) {
            btn.innerText = `✅ REGISTRAR ${total} PIEZAS BUENAS`;
            btn.style.background = "var(--success)";
        } else if (total === 0) {
            btn.innerText = 'Registrar Operación';
            btn.style.background = "var(--warning)";
        } else {
            btn.innerText = '❌ PNC mayor a producción';
            btn.style.background = "var(--primary-red)";
        }
    };
    
    if (inCav && inGol && inPNC) {
        inCav.oninput = inGol.oninput = inPNC.oninput = calcularTotal;
        calcularTotal();
    }
}

// Configurar cálculos para pulido
function setupPulidoCalculations(container, btn) {
    const inRec = container.querySelector('[name="cantidad_recibida"]');
    const inPNC = container.querySelector('[name="pnc"]');
    const inReal = container.querySelector('[name="cantidad_real"]');
    
    const calcularPulido = () => {
        const recibida = parseInt(inRec.value) || 0;
        const pnc = parseInt(inPNC.value) || 0;
        const buenos = recibida - pnc;
        
        if (inReal) {
            inReal.value = buenos >= 0 ? buenos : 0;
        }
        
        if (buenos > 0) {
            btn.innerText = `✅ REGISTRAR ${buenos} BUJES BUENOS`;
            btn.style.background = "var(--success)";
        } else if (buenos === 0 && recibida > 0) {
            btn.innerText = '⚠️ TODOS SON PNC';
            btn.style.background = "var(--warning)";
        } else {
            btn.innerText = 'Registrar Operación';
            btn.style.background = "var(--primary)";
        }
    };
    
    if (inRec && inPNC) {
        inRec.oninput = inPNC.oninput = calcularPulido;
        calcularPulido();
    }
}

// Configurar cálculos para ensamble
function setupEnsambleCalculations(container, btn) {
    const inRecibida = container.querySelector('[name="cantidad_recibida"]');
    const inPNC = container.querySelector('[name="pnc"]');
    const inReal = container.querySelector('[name="cantidad_real"]');
    
    const calcularEnsamble = () => {
        const recibida = parseInt(inRecibida.value) || 0;
        const pnc = parseInt(inPNC.value) || 0;
        const buenos = recibida - pnc;
        
        if (inReal) {
            inReal.value = buenos >= 0 ? buenos : 0;
        }
        
        if (buenos > 0) {
            btn.innerText = `✅ REGISTRAR ${buenos} BUJES BUENOS`;
            btn.style.background = "var(--success)";
        } else if (buenos === 0 && recibida > 0) {
            btn.innerText = '⚠️ TODOS SON PNC';
            btn.style.background = "var(--warning)";
        } else {
            btn.innerText = 'Registrar Operación';
            btn.style.background = "var(--primary)";
        }
    };
    
    if (inRecibida && inPNC) {
        inRecibida.oninput = inPNC.oninput = calcularEnsamble;
        calcularEnsamble();
    }
}

// Obtener ficha técnica automáticamente
async function obtenerFichaTecnica(codigo) {
    try {
        const response = await fetch(`http://127.0.0.1:5000/api/obtener_ficha/${codigo}`);
        if (response.ok) {
            const data = await response.json();
            return data;
        }
    } catch (error) {
        console.error('Error obteniendo ficha técnica:', error);
    }
    return null;
}

// Configurar autocompletado de ficha técnica
function setupAutoFicha(container) {
    const codigoInput = container.querySelector('[name="codigo_producto"]');
    if (codigoInput) {
        codigoInput.addEventListener('change', async function() {
            if (this.value.trim()) {
                const ficha = await obtenerFichaTecnica(this.value);
                if (ficha) {
                    mostrarNotificacion(`Ficha encontrada: ${ficha.buje_origen}`, 'info');
                }
            }
        });
    }
}

// Exportar funciones globales
window.renderFields = renderFields;
window.obtenerFichaTecnica = obtenerFichaTecnica;