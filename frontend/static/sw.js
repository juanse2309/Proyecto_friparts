const CACHE_NAME = 'friparts-cache-v1';
const STATIC_ASSETS = [
    '/',
    '/static/css/styles.css',
    '/static/js/app.js'
];

// Install Event - Precache static assets
self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('[SW] Precaching estáticos');
            // Usamos addAll ignorando errores si algún archivo no existe aún
            return cache.addAll(STATIC_ASSETS).catch(err => console.warn('[SW] Cuidado: archivo faltante en precache', err));
        })
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

// Fetch Event - Dual Strategy
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // CRÍTICO: Nunca interceptar el manifest.json, el navegador necesita acceso directo para la instalación
    if (url.pathname.endsWith('manifest.json')) {
        event.respondWith(fetch(request));
        return;
    }

    // Estrategia: Network-First para la API (/api/...)
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    // Opcional: clonar y guardar en caché para soporte de lectura offline
                    return response;
                })
                .catch(err => {
                    console.log('[SW] API offline fallback para:', request.url);
                    return caches.match(request); // Retorna caché si existe
                })
        );
    } 
    // Estrategia: Cache-First para recursos estáticos
    else {
        event.respondWith(
            caches.match(request).then(cachedResponse => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(request).then(response => {
                    return response;
                });
            })
        );
    }
});

// Background Sync Event
self.addEventListener('sync', event => {
    if (event.tag === 'sync-datos-offline') {
        console.log('[SW] Sincronización de fondo activada');
        // TODO: Leer IndexedDB, obtener PWA Token, vaciar Outbox enviando con Authorization: Bearer
    }
});

// Push Event - Recepción de Notificaciones
self.addEventListener('push', event => {
    console.log('[SW] Push recibido');
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            console.warn('[SW] Error parseando JSON del push', e);
            data = { title: 'Nueva Notificación', body: event.data.text() };
        }
    }

    const title = data.title || 'Friparts PWA';
    const options = {
        body: data.body || 'Tienes un nuevo mensaje.',
        icon: data.icon || '/static/img/icon-192.png',
        badge: data.badge || '/static/img/icon-192.png',
        vibrate: [200, 100, 200, 100, 200],
        requireInteraction: true,
        data: {
            url: data.url || (data.data && data.data.url) || '/'
        }
    };
    // Imagen enriquecida para campañas B2B Marketing
    if (data.image) {
        options.image = data.image;
    }

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Notification Click Event - Navegación y Focus
self.addEventListener('notificationclick', event => {
    console.log('[SW] Click en notificación');
    event.notification.close();

    const targetUrl = event.notification.data && event.notification.data.url ? event.notification.data.url : '/';
    
    event.waitUntil(
        clients.openWindow(targetUrl)
    );
});
