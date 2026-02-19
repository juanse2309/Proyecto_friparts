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
     * Reproducir sonido según el tema configurado
     * @param {string} type 'success' | 'error' | 'new_order'
     */
    const playSound = (type) => {
        const theme = localStorage.getItem('friparts_sound_theme') || 'classic';

        if (type === 'success') {
            playTone(523.25, 'sine', 0.1); // C5
            setTimeout(() => playTone(659.25, 'sine', 0.1), 100); // E5
        } else if (type === 'error') {
            playTone(150, 'sawtooth', 0.4);
            playTone(110, 'square', 0.4);
        } else if (type === 'new_order') {
            switch (theme) {
                case 'siren':
                    // Sirena Industrial (Llamativa y potente)
                    [800, 600, 800, 600].forEach((f, i) => {
                        setTimeout(() => playTone(f, 'sawtooth', 0.2), i * 200);
                    });
                    break;
                case 'mega_siren':
                    // Mega Sirena (Largo - 8 ciclos)
                    for (let i = 0; i < 8; i++) {
                        setTimeout(() => playTone(800, 'sawtooth', 0.2), i * 400);
                        setTimeout(() => playTone(600, 'sawtooth', 0.2), i * 400 + 200);
                    }
                    break;
                case 'urgent':
                    // Alarma Urgente (Rápida y penetrante)
                    for (let i = 0; i < 12; i++) {
                        setTimeout(() => playTone(1200, 'square', 0.05), i * 100);
                    }
                    break;
                case 'sonar':
                    // Eco de Sonar (Pulsos profundos)
                    [400, 400, 400].forEach((f, i) => {
                        setTimeout(() => {
                            playTone(f, 'sine', 0.8);
                            playTone(f * 1.5, 'sine', 0.4);
                        }, i * 1000);
                    });
                    break;
                case 'melody':
                    // Secuencia Melódica (Elegante y larga)
                    [523, 659, 783, 1046, 783, 659, 523].forEach((f, i) => {
                        setTimeout(() => playTone(f, 'sine', 0.3), i * 200);
                    });
                    break;
                case 'pulse':
                    // Pulso Moderno (Corto y penetrante)
                    playTone(1000, 'square', 0.05);
                    setTimeout(() => playTone(1000, 'square', 0.05), 100);
                    setTimeout(() => playTone(1200, 'square', 0.1), 200);
                    break;
                case 'arpeggio':
                    // Arpeggio Melódico
                    [440, 554, 659, 880].forEach((f, i) => {
                        setTimeout(() => playTone(f, 'sine', 0.15), i * 100);
                    });
                    break;
                case 'classic':
                default:
                    // Campana Clásica (Mejorada)
                    playTone(600, 'sine', 0.1);
                    setTimeout(() => playTone(800, 'sine', 0.4), 150);
                    break;
            }
        }
    };

    const getSoundTheme = () => localStorage.getItem('friparts_sound_theme') || 'classic';
    const setSoundTheme = (theme) => localStorage.setItem('friparts_sound_theme', theme);

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
        playSound,
        getSoundTheme,
        setSoundTheme
    };

})();

// Exponer globalmente
window.ModuloUX = ModuloUX;

// Auto-init si el DOM ya está listo, o esperar
document.addEventListener('DOMContentLoaded', ModuloUX.init);
