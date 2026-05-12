const apiClient = {
    async get(endpoint) {
        try {
            const response = await fetch(endpoint);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`[API GET] ${endpoint}:`, error);
            throw error;
        }
    },

    async post(endpoint, data, retries = 3) {
        for (let i = 0; i < retries; i++) {
            try {
                if (!navigator.onLine) {
                    throw new Error("Sin conexión a internet detectada.");
                }

                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP ${response.status}: ${errorText}`);
                }

                return await response.json();
            } catch (error) {
                console.warn(`[API POST] Intento ${i + 1}/${retries} fallido para ${endpoint}:`, error);
                
                if (i === retries - 1) {
                    throw error;
                }
                
                // Espera exponencial básica (1s, 2s, 3s)
                await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
            }
        }
    }
};
window.apiClient = apiClient;