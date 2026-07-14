class PWAPushManager {
    constructor() {
        this.vapidPublicKey = null;
    }

    urlB64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/\-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    async initPush() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            console.warn('Push messaging no soportado.');
            return false;
        }

        try {
            // Verificar estado actual del permiso antes de solicitar
            let permission = Notification.permission;
            if (permission === 'default' || permission === 'denied') {
                permission = await Notification.requestPermission();
            }
            
            if (permission !== 'granted') {
                console.warn('Permiso de notificaciones denegado.');
                return false;
            }

            const res = await fetch('/api/pwa/vapid-public');
            const data = await res.json();
            if (!data.success) throw new Error(data.message);
            
            this.vapidPublicKey = data.vapid_public_key;
            
            const registration = await navigator.serviceWorker.ready;
            const existingSubscription = await registration.pushManager.getSubscription();
            
            if (existingSubscription) {
                console.log('Usuario ya suscrito.', existingSubscription);
                await this.enviarSuscripcionBackend(existingSubscription);
                return true;
            }

            const applicationServerKey = this.urlB64ToUint8Array(this.vapidPublicKey);
            console.log("VAPID Key validada y codificada en Uint8Array:", applicationServerKey);
            
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });

            console.log('Suscripción generada:', subscription);
            await this.enviarSuscripcionBackend(subscription);
            return true;
        } catch (error) {
            console.log("Error de suscripción:", error);
            console.error('Error inicializando Web Push:', error);
            return false;
        }
    }

    async enviarSuscripcionBackend(subscription) {
        try {
            const response = await fetch('/api/pwa/suscribir', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ subscription })
            });
            const data = await response.json();
            if (!data.success) {
                console.error('Error guardando suscripción:', data.message);
            } else {
                console.log('Suscripción guardada en el backend.');
            }
        } catch (err) {
            console.error('Error de red al enviar suscripción:', err);
        }
    }
}

window.PWAPushManager = new PWAPushManager();
console.log('✅ PWAPushManager cargado correctamente y anexado a window.');
