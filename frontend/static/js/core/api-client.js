const apiClient = {
    baseURL: '/api',
    
    async get(endpoint) {
        try {
            const url = endpoint.startsWith(this.baseURL) ? endpoint : `${this.baseURL}${endpoint}`;
            const headers = {};
            const token = localStorage.getItem('pwa_token');
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(url, { headers });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`[API GET] ${endpoint}:`, error);
            throw error;
        }
    },
    
    async post(endpoint, data) {
        try {
            const url = endpoint.startsWith(this.baseURL) ? endpoint : `${this.baseURL}${endpoint}`;
            const headers = { 'Content-Type': 'application/json' };
            const token = localStorage.getItem('pwa_token');
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(data)
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`[API POST] ${endpoint}:`, error);
            throw error;
        }
    }
};
window.apiClient = apiClient;