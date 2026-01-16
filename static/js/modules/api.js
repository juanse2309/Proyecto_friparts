// static/js/modules/api.js

const API_BASE = '/api';

export const ApiService = {
    async getDetalleProducto(codigo) {
        const response = await fetch(`${API_BASE}/productos/detalle/${codigo}`);
        if (!response.ok) throw new Error('Error al obtener detalle');
        return await response.json();
    },

    async getMovimientos(codigo) {
        // Aquí corregimos el error 404 que tenías
        const response = await fetch(`${API_BASE}/movimientos/${codigo}`);
        if (!response.ok) throw new Error('Error al obtener movimientos');
        return await response.json();
    }
};