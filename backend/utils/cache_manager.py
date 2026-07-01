import time
import logging
import threading
from functools import wraps
from flask import request

logger = logging.getLogger(__name__)

# Diccionario de cachés por namespace con su respectivo lock global
_caches = {}
_caches_lock = threading.Lock()

class NamespaceTTLCache:
    """
    Caché en memoria con límite de tamaño (maxsize) e invalidación por tiempo (TTL).
    Implementación segura frente a accesos concurrentes de múltiples hilos (Thread-Safe)
    mediante threading.Lock.

    ADVERTENCIA DE PRODUCCIÓN (GUNICORN / WORKERS):
    Esta caché utiliza memoria RAM local del proceso Python. Si la aplicación corre 
    detrás de un servidor WSGI como Gunicorn con múltiples procesos activos (workers > 1), 
    cada worker tendrá su propia instancia de esta caché aislada en memoria. Las escrituras 
    o invalidaciones en un proceso no se reflejarán en los demás. 
    Esta implementación es consistente y adecuada si la aplicación se ejecuta con un 
    solo worker (worker=1). Para despliegues horizontales multi-worker, se debe migrar 
    este gestor de caché a una solución compartida y centralizada como Redis o Memcached.
    """
    def __init__(self, maxsize=100, ttl=600):
        self.maxsize = maxsize
        self.ttl = ttl
        self.store = {}  # key -> (value, expires_at)
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            now = time.time()
            if key in self.store:
                value, expires_at = self.store[key]
                if now < expires_at:
                    return value
                else:
                    del self.store[key]
            return None

    def set(self, key, value):
        with self._lock:
            now = time.time()
            self._cleanup_unlocked()
            if len(self.store) >= self.maxsize:
                # Desalojo FIFO simple para evitar rebasar el límite de tamaño
                oldest_key = next(iter(self.store))
                del self.store[oldest_key]
                logger.debug(f"[CacheEvict] Evicted oldest key: {oldest_key}")
            self.store[key] = (value, now + self.ttl)

    def _cleanup_unlocked(self):
        """Método interno de limpieza que se asume llamado dentro de self._lock."""
        now = time.time()
        expired = [k for k, (_, exp) in self.store.items() if now >= exp]
        for k in expired:
            del self.store[k]

    def cleanup(self):
        with self._lock:
            self._cleanup_unlocked()

    def clear(self):
        with self._lock:
            self.store.clear()

def get_cache(namespace, maxsize=100, ttl=600):
    with _caches_lock:
        if namespace not in _caches:
            _caches[namespace] = NamespaceTTLCache(maxsize=maxsize, ttl=ttl)
        return _caches[namespace]

def cached_route(namespace, maxsize=100, ttl=600, key_builder=None):
    """
    Decorador para cachear respuestas de rutas Flask basado en namespaces.
    Soporta bypass con ?nocache=1 en URL.
    """
    cache = get_cache(namespace, maxsize=maxsize, ttl=ttl)

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            nocache = request.args.get('nocache') == '1'
            
            # Construir la llave de caché
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                # Llave por defecto: combinación de ruta y parámetros de búsqueda ordenados
                query_params = tuple(sorted(request.args.items()))
                key = (request.path, query_params)

            if nocache:
                logger.info(f"[CacheMiss] Cache bypass para namespace='{namespace}', key={key}")
                return f(*args, **kwargs)

            cached_data = cache.get(key)
            if cached_data is not None:
                logger.info(f"[CacheHit] Sirviendo desde caché para namespace='{namespace}', key={key}")
                return cached_data

            logger.info(f"[CacheMiss] Ejecutando ruta para namespace='{namespace}', key={key}")
            response = f(*args, **kwargs)
            
            # Solo cachear si la respuesta es exitosa (código 200)
            status_code = 200
            if isinstance(response, tuple):
                if len(response) > 1:
                    status_code = response[1]
            elif hasattr(response, 'status_code'):
                status_code = response.status_code

            if status_code == 200:
                cache.set(key, response)
                
            return response
        return decorated_function
    return decorator

def invalidate_cache(namespace):
    """
    Invalida todo el caché correspondiente a un namespace específico.
    """
    with _caches_lock:
        cache = _caches.get(namespace)
    if cache:
        cache.clear()
        logger.info(f"[CacheInvalidate] Todo el caché del namespace='{namespace}' fue invalidado.")
        return True
    logger.debug(f"[CacheInvalidate] No se encontró el namespace='{namespace}' para invalidar.")
    return False
