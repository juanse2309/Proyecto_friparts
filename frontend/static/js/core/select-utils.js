/**
 * Utilidades para manejo de elementos <select>.
 * Elimina código duplicado en todos los módulos.
 */

class SelectUtils {
    static actualizar(selectId, opciones, placeholder = '-- Seleccionar --') {
        const select = document.getElementById(selectId);
        if (!select) {
            console.warn(`Select #${selectId} no encontrado`);
            return;
        }

        const valorActual = select.value;
        
        // Limpiar y agregar placeholder
        select.innerHTML = `<option value="">${placeholder}</option>`;

        // Agregar opciones
        opciones.forEach(item => {
            const option = document.createElement('option');
            
            if (typeof item === 'object') {
                option.value = item.value || item.codigo || item;
                option.textContent = item.label || item.nombre || item.descripcion || item.value;
            } else {
                option.value = item;
                option.textContent = item;
            }
            
            select.appendChild(option);
        });

        // Restaurar valor si existía
        if (valorActual) {
            select.value = valorActual;
        }
    }

    static obtenerValor(selectId) {
        const select = document.getElementById(selectId);
        return select ? select.value : null;
    }

    static setValor(selectId, valor) {
        const select = document.getElementById(selectId);
        if (select) {
            select.value = valor;
        }
    }

    static obtenerTextoSeleccionado(selectId) {
        const select = document.getElementById(selectId);
        if (!select) return null;
        
        const opcionSeleccionada = select.options[select.selectedIndex];
        return opcionSeleccionada ? opcionSeleccionada.text : null;
    }

    static limpiar(selectId, placeholder = '-- Seleccionar --') {
        const select = document.getElementById(selectId);
        if (select) {
            select.innerHTML = `<option value="">${placeholder}</option>`;
        }
    }
}

// Exportar para uso global
window.SelectUtils = SelectUtils;