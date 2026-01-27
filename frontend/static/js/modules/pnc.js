// ============================================
// pnc.js - L??gica de PNC (Producto No Conforme)
// ============================================

/**
 * Cargar datos de PNC
 */
async function cargarDatosPNC() {
    try {
        console.log('?????? Cargando datos de PNC...');
        mostrarLoading(true);
        
        // Generar ID autom??tico
        const timestamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 14);
        const idPNC = `PNC-${timestamp}`;
        const inputId = document.getElementById('id-pnc');
        if (inputId) {
            inputId.value = idPNC;
        }
        
        // Fecha actual
        const hoy = new Date().toISOString().split('T')[0];
        const fechaInput = document.getElementById('fecha-pnc');
        if (fechaInput) {
            fechaInput.value = hoy;
        }
        
        // Cargar productos en datalist
        const productos = await fetchData('/api/obtener_productos');
        if (productos) {
            const datalist = document.getElementById('productos-pnc-list');
            if (datalist) {
                datalist.innerHTML = '';
                productos.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p;
                    datalist.appendChild(opt);
                });
            }
        }
        
        // Configurar botones de criterio
        configurarCriteriosPNC();
        
        console.log('??? Datos de PNC cargados');
        mostrarLoading(false);
    } catch (error) {
        console.error('Error cargando datos:', error);
        mostrarLoading(false);
    }
}

/**
 * Configurar botones de criterio
 */
function configurarCriteriosPNC() {
    const botones = document.querySelectorAll('.criterio-btn');
    const inputHidden = document.getElementById('criterio-pnc-hidden');
    
    botones.forEach(btn => {
        btn.addEventListener('click', function() {
            // Quitar activo de todos
            botones.forEach(b => b.classList.remove('active'));
            
            // Marcar este como activo
            this.classList.add('active');
            
            // Guardar en input hidden
            const criterio = this.dataset.criterio;
            if (inputHidden) {
                inputHidden.value = criterio;
            }
            
            console.log('Criterio seleccionado:', criterio);
        });
    });
}

/**
 * Registrar PNC
 */
async function registrarPNC() {
    try {
        mostrarLoading(true);
        
        const datos = {
            fecha: document.getElementById('fecha-pnc')?.value || '',
            id_pnc: document.getElementById('id-pnc')?.value || '',
            codigo_producto: document.getElementById('codigo-producto-pnc')?.value || '',
            cantidad: document.getElementById('cantidad-pnc')?.value || '0',
            criterio: document.getElementById('criterio-pnc-hidden')?.value || '',
            codigo_ensamble: document.getElementById('codigo-ensamble-pnc')?.value || ''
        };
        
        console.log('???? Datos de PNC:', datos);
        
        // Validaciones
        if (!datos.codigo_producto?.trim()) {
            mostrarNotificacion('??? Ingresa c??digo del producto', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.cantidad || datos.cantidad === '0') {
            mostrarNotificacion('??? Ingresa cantidad de PNC', 'error');
            mostrarLoading(false);
            return;
        }
        
        if (!datos.criterio?.trim()) {
            mostrarNotificacion('??? Selecciona un criterio', 'error');
            mostrarLoading(false);
            return;
        }
        
        // Enviar al servidor
        const response = await fetch('/api/pnc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        
        const resultado = await response.json();
        
        if (response.ok && resultado.success) {
            mostrarNotificacion(`??? ${resultado.mensaje}`, 'success');
            
            // Limpiar formulario
            document.getElementById('form-pnc')?.reset();
            
            // Recargar
            setTimeout(() => {
                cargarDatosPNC();
            }, 1000);
        } else {
            const errores = resultado.errors 
                ? Object.values(resultado.errors).join(', ') 
                : resultado.error || 'Error desconocido';
            mostrarNotificacion(`??? ${errores}`, 'error');
        }
    } catch (error) {
        console.error('Error registrando:', error);
        mostrarNotificacion(`Error: ${error.message}`, 'error');
    } finally {
        mostrarLoading(false);
    }
}
