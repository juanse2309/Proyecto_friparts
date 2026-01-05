// Utilities para el dashboard

// Formatear números
function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    return new Intl.NumberFormat('es-ES').format(Math.round(num));
}

// Formatear moneda
function formatCurrency(num) {
    if (num === null || num === undefined || isNaN(num)) return '$0';
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(num);
}

// Formatear porcentaje
function formatPercent(num) {
    if (num === null || num === undefined || isNaN(num)) return '0%';
    return num.toFixed(1).replace('.', ',') + '%';
}

// Formatear fecha
function formatDate(date, includeTime = false) {
    if (!date) return '';
    
    const d = new Date(date);
    const options = {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    };
    
    if (includeTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }
    
    return d.toLocaleDateString('es-ES', options);
}

// Obtener color según valor
function getColorByValue(value, type = 'efficiency') {
    if (type === 'efficiency') {
        if (value >= 90) return '#10b981';
        if (value >= 80) return '#f59e0b';
        return '#f43f5e';
    }
    
    if (type === 'stock') {
        if (value === 'CRITICO') return '#f43f5e';
        if (value === 'ALTO') return '#f97316';
        if (value === 'MEDIO') return '#f59e0b';
        if (value === 'BAJO') return '#84cc16';
        return '#10b981';
    }
    
    return '#6b7280';
}

// Validar email
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// Validar teléfono
function isValidPhone(phone) {
    return /^[\+]?[0-9\s\-\(\)]{8,}$/.test(phone);
}

// Obtener iniciales
function getInitials(name) {
    return name
        .split(' ')
        .map(word => word[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
}

// Capitalizar texto
function capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

// Calcular edad
function calculateAge(birthDate) {
    const today = new Date();
    const birth = new Date(birthDate);
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();
    
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
        age--;
    }
    
    return age;
}

// Debounce para eventos
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle para eventos
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// LocalStorage helpers
const storage = {
    set: (key, value) => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('Error saving to localStorage:', e);
            return false;
        }
    },
    
    get: (key) => {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : null;
        } catch (e) {
            console.error('Error reading from localStorage:', e);
            return null;
        }
    },
    
    remove: (key) => {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (e) {
            console.error('Error removing from localStorage:', e);
            return false;
        }
    },
    
    clear: () => {
        try {
            localStorage.clear();
            return true;
        } catch (e) {
            console.error('Error clearing localStorage:', e);
            return false;
        }
    }
};

// Session helpers
const session = {
    set: (key, value) => {
        try {
            sessionStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('Error saving to sessionStorage:', e);
            return false;
        }
    },
    
    get: (key) => {
        try {
            const item = sessionStorage.getItem(key);
            return item ? JSON.parse(item) : null;
        } catch (e) {
            console.error('Error reading from sessionStorage:', e);
            return null;
        }
    },
    
    remove: (key) => {
        try {
            sessionStorage.removeItem(key);
            return true;
        } catch (e) {
            console.error('Error removing from sessionStorage:', e);
            return false;
        }
    }
};

// API helpers
const api = {
    get: async (url) => {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('GET Error:', error);
            throw error;
        }
    },
    
    post: async (url, data) => {
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('POST Error:', error);
            throw error;
        }
    },
    
    put: async (url, data) => {
        try {
            const response = await fetch(url, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('PUT Error:', error);
            throw error;
        }
    },
    
    delete: async (url) => {
        try {
            const response = await fetch(url, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('DELETE Error:', error);
            throw error;
        }
    }
};

// Date helpers
const dateHelpers = {
    getCurrentDate: () => new Date().toISOString().split('T')[0],
    
    getCurrentDateTime: () => new Date().toISOString().replace('T', ' ').split('.')[0],
    
    formatDateToLocal: (dateString) => {
        const date = new Date(dateString);
        return date.toLocaleDateString('es-ES', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    },
    
    formatDateTimeToLocal: (dateString) => {
        const date = new Date(dateString);
        return date.toLocaleDateString('es-ES', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    addDays: (date, days) => {
        const result = new Date(date);
        result.setDate(result.getDate() + days);
        return result;
    },
    
    getDaysBetween: (startDate, endDate) => {
        const start = new Date(startDate);
        const end = new Date(endDate);
        const diffTime = Math.abs(end - start);
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    }
};

// Number helpers
const numberHelpers = {
    randomBetween: (min, max) => Math.floor(Math.random() * (max - min + 1)) + min,
    
    round: (num, decimals = 2) => {
        const factor = Math.pow(10, decimals);
        return Math.round(num * factor) / factor;
    },
    
    clamp: (num, min, max) => Math.min(Math.max(num, min), max),
    
    average: (arr) => {
        if (!arr.length) return 0;
        return arr.reduce((a, b) => a + b, 0) / arr.length;
    },
    
    sum: (arr) => arr.reduce((a, b) => a + b, 0)
};

// DOM helpers
const dom = {
    show: (element) => {
        if (element) element.style.display = 'block';
    },
    
    hide: (element) => {
        if (element) element.style.display = 'none';
    },
    
    toggle: (element) => {
        if (element) {
            element.style.display = element.style.display === 'none' ? 'block' : 'none';
        }
    },
    
    addClass: (element, className) => {
        if (element) element.classList.add(className);
    },
    
    removeClass: (element, className) => {
        if (element) element.classList.remove(className);
    },
    
    toggleClass: (element, className) => {
        if (element) element.classList.toggle(className);
    }
};

// Exportar todas las funciones
window.utils = {
    formatNumber,
    formatCurrency,
    formatPercent,
    formatDate,
    getColorByValue,
    isValidEmail,
    isValidPhone,
    getInitials,
    capitalize,
    calculateAge,
    debounce,
    throttle,
    storage,
    session,
    api,
    dateHelpers,
    numberHelpers,
    dom
};