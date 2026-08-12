/**
 * Gate de logs de consola.
 *
 * Por defecto, console.log/console.info quedan silenciados en todo momento
 * (incluida produccion) para que la consola no se llene de trazas de "cargando",
 * "renderizado ok", etc. en cada auto-refresco. console.warn y console.error
 * NO se tocan: los errores reales siempre deben verse.
 *
 * Para depurar: abrir la URL con ?debug=1 (queda recordado en localStorage
 * para las siguientes cargas) o ejecutar en la consola:
 *   localStorage.setItem('debug', '1')
 * y luego recargar. Para desactivarlo de nuevo: localStorage.removeItem('debug').
 */
(function () {
    var activo = false;
    try {
        if (/[?&]debug=1(&|$)/.test(location.search)) {
            localStorage.setItem('debug', '1');
        }
        activo = localStorage.getItem('debug') === '1';
    } catch (e) {
        // localStorage puede fallar (modo incognito estricto, etc.); se deja apagado por defecto
    }

    if (!activo) {
        console.log = function () {};
        console.info = function () {};
    } else {
        console.log('%c[debug] logging de consola activado (?debug=1 / localStorage.debug)', 'color:#888');
    }
})();
