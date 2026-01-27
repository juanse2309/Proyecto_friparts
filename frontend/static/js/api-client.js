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
    }
};
window.apiClient = apiClient;