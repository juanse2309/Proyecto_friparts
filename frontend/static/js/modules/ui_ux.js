/**
 * Módulo de UX/UI - Personalización y Gamificación
 * v1.0.0
 */

const ModuloUX = (() => {

    // Configuración de Sonidos (Web Audio API para no depender de archivos)
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();

    const playTone = (freq, type, duration) => {
        try {
            const osc = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            osc.type = type;
            osc.frequency.setValueAtTime(freq, audioContext.currentTime);

            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);

            osc.connect(gainNode);
            gainNode.connect(audioContext.destination);

            osc.start();
            osc.stop(audioContext.currentTime + duration);
        } catch (e) {
            console.warn("Audio blocked or failed", e);
        }
    };

    /**
     * Reproducir sonido de éxito o error
     * @param {string} type 'success' | 'error'
     */
    const playSound = (type) => {
        if (type === 'success') {
            // Ding alegre (Do mayor arpegio rápido)
            playTone(523.25, 'sine', 0.1); // C5
            setTimeout(() => playTone(659.25, 'sine', 0.1), 100); // E5
        } else if (type === 'error') {
            // Error (Tono bajo)
            playTone(150, 'sawtooth', 0.3);
        }
    };

    /**
     * Generar Avatar e Iniciales
     */
    const actualizarPerfil = () => {
        try {
            const user = window.AppState?.user;
            if (!user) return;

            const nombre = user.nombre || user.name || 'Usuario';

            // 1. Saludo según hora
            const hora = new Date().getHours();
            let saludo = 'Hola';
            let icono = '👋';

            if (hora < 12) { saludo = 'Buenos días'; icono = '☀️'; }
            else if (hora < 19) { saludo = 'Buenas tardes'; icono = '🌤️'; }
            else { saludo = 'Buenas noches'; icono = '🌙'; }

            // 2. Renderizar Saludo
            const greetingEl = document.getElementById('user-greeting');
            const nameDisplayEl = document.getElementById('user-name-display');

            if (greetingEl) greetingEl.innerHTML = `${saludo}, ${icono}`;
            if (nameDisplayEl) nameDisplayEl.textContent = nombre.split(' ')[0]; // Primer nombre

            // 3. Avatar con iniciales
            const avatarEl = document.getElementById('user-avatar');
            if (avatarEl) {
                const iniciales = nombre.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
                avatarEl.textContent = iniciales;

                // Color de fondo consistente basado en el nombre (Hash simple)
                const hash = nombre.split('').reduce((acc, char) => char.charCodeAt(0) + ((acc << 5) - acc), 0);
                const hue = Math.abs(hash) % 360;
                avatarEl.style.background = `linear-gradient(135deg, hsl(${hue}, 70%, 50%), hsl(${hue + 40}, 70%, 40%))`;
            }

        } catch (e) {
            console.error("Error actualizando perfil UX", e);
        }
    };

    return {
        init: () => {
            console.log("🎨 Modulo UX Inicializado");
            // Esperar a que el usuario cargue en AppState
            const checkUser = setInterval(() => {
                if (window.AppState && window.AppState.user) {
                    actualizarPerfil();
                    clearInterval(checkUser);
                }
            }, 500);
        },
        playSound
    };

})();

// Exponer globalmente
window.ModuloUX = ModuloUX;

// Auto-init si el DOM ya está listo, o esperar
document.addEventListener('DOMContentLoaded', ModuloUX.init);
