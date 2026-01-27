/**
 * Gestor unificado de defectos/PNC.
 * Elimina las 3+ implementaciones duplicadas en ensamble, inyección, pulido.
 */

class DefectosManager {
    constructor(config) {
        this.containerId = config.containerId;
        this.totalId = config.totalId;
        this.btnAgregarId = config.btnAgregarId;
        this.selectCriterioId = config.selectCriterioId;
        this.inputCantidadId = config.inputCantidadId;
        
        this.defectos = [];
        
        this._init();
    }

    _init() {
        const btnAgregar = document.getElementById(this.btnAgregarId);
        if (btnAgregar) {
            btnAgregar.addEventListener('click', () => this.agregar());
        }
    }

    agregar() {
        const selectCriterio = document.getElementById(this.selectCriterioId);
        const inputCantidad = document.getElementById(this.inputCantidadId);
        
        if (!selectCriterio || !inputCantidad) {
            console.error('Elementos no encontrados');
            return;
        }

        const criterio = selectCriterio.value;
        const cantidad = parseInt(inputCantidad.value) || 0;

        if (!criterio) {
            mostrarNotificacion('Seleccione un criterio de defecto', 'warning');
            return;
        }

        if (cantidad <= 0) {
            mostrarNotificacion('La cantidad debe ser mayor a 0', 'warning');
            return;
        }

        this.defectos.push({ criterio, cantidad });
        
        // Limpiar inputs
        selectCriterio.value = '';
        inputCantidad.value = '';
        inputCantidad.focus();
        
        this.renderizar();
        mostrarNotificacion('Defecto agregado', 'success', 2000);
    }

    eliminar(index) {
        if (index >= 0 && index < this.defectos.length) {
            this.defectos.splice(index, 1);
            this.renderizar();
            mostrarNotificacion('Defecto eliminado', 'info', 2000);
        }
    }

    obtenerTotal() {
        return this.defectos.reduce((sum, d) => sum + d.cantidad, 0);
    }

    obtenerDatos() {
        return [...this.defectos];
    }

    limpiar() {
        this.defectos = [];
        this.renderizar();
    }

    renderizar() {
        const container = document.getElementById(this.containerId);
        const totalSpan = document.getElementById(this.totalId);
        
        if (!container) return;

        if (this.defectos.length === 0) {
            container.innerHTML = '<p class="text-muted">No hay defectos registrados</p>';
        } else {
            container.innerHTML = this.defectos
                .map((d, i) => this._crearItemHTML(d, i))
                .join('');
        }

        if (totalSpan) {
            totalSpan.textContent = this.obtenerTotal();
        }
    }

    _crearItemHTML(defecto, index) {
        const criterioEscapado = this._escaparHTML(defecto.criterio);
        
        return `
            <div class="defecto-item" style="display: flex; justify-content: space-between; align-items: center; padding: 8px; border: 1px solid #dee2e6; border-radius: 4px; margin-bottom: 8px;">
                <span style="flex: 1;">${criterioEscapado}</span>
                <span style="font-weight: 600; margin: 0 12px; color: #495057;">${defecto.cantidad}</span>
                <button 
                    type="button" 
                    class="btn-eliminar-defecto"
                    onclick="window._defectosManager_${this.containerId}.eliminar(${index})"
                    style="background: #dc3545; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer;">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
    }

    _escaparHTML(texto) {
        const div = document.createElement('div');
        div.textContent = texto;
        return div.innerHTML;
    }
}

// Exportar para uso global
window.DefectosManager = DefectosManager;