
// auth.js - Manejo de Autenticación, Permisos y Portal B2B

const AuthModule = {
    currentUser: null,

    // Matriz de Permisos
    permissions: {
        'Administración': ['dashboard', 'inventario', 'inyeccion', 'pulido', 'ensamble', 'pnc', 'facturacion', 'mezcla', 'historial', 'reportes', 'pedidos', 'almacen'],
        'Comercial': ['pedidos', 'dashboard', 'inventario'],
        'Auxiliar Inventario': ['inventario', 'inyeccion', 'pnc', 'historial', 'almacen'],
        'Inyección': ['inyeccion', 'mezcla'],
        'Pulido': ['pulido'],
        'Ensamble': ['ensamble'],
        'Alistamiento': ['almacen', 'historial'],
        // NUEVO ROL CLIENTE
        'Cliente': ['portal-cliente'],
        // Fallback
        'Invitado': []
    },

    // Notificación Visual
    mostrarNotificacion: function (msg, tipo = 'info') {
        const div = document.createElement('div');
        div.className = 'custom-toast';
        div.innerHTML = `<i class="fas ${tipo === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'} me-2"></i> ${msg}`;

        let bgColor = '#3b82f6'; // Info
        if (tipo === 'success') bgColor = '#10b981';
        if (tipo === 'error') bgColor = '#ef4444';

        div.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            background-color: ${bgColor};
            color: white;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            z-index: 30000;
            font-weight: 500;
            display: flex;
            align-items: center;
            animation: slideInRight 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            font-size: 0.95rem;
        `;

        // Add animation keyframes if not exists
        if (!document.getElementById('toast-style')) {
            const style = document.createElement('style');
            style.id = 'toast-style';
            style.textContent = `@keyframes slideInRight { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }`;
            document.head.appendChild(style);
        }

        document.body.appendChild(div);

        setTimeout(() => {
            div.style.transition = 'all 0.4s ease';
            div.style.transform = 'translateX(100%)';
            div.style.opacity = '0';
            setTimeout(() => div.remove(), 400);
        }, 3000);
    },

    init: async function () {
        console.log("🔐 Inicializando Módulo de Autenticación Avancado...");

        // 1. Cargar lista de responsables (solo si es necesario, lazy load idealmente pero aqui eager)
        await this.loadResponsables();

        // 2. Listeners Staff Logic
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }

        const passwordInput = document.getElementById('login-password');
        if (passwordInput) {
            passwordInput.addEventListener('input', function (e) {
                this.value = this.value.replace(/[^0-9]/g, '');
            });
        }

        // 3. Bloquear interfaz o mostrar Landing
        this.checkSession();
    },

    // =================================================================
    // GESTIÓN DE PANTALLAS (Landing / Modales)
    // =================================================================

    showLandingScreen: function () {
        const landing = document.getElementById('landing-screen');
        if (landing) {
            landing.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
        // Cerrar otros modales por si acaso
        this.closeLoginModal();
        this.closeClientAuth();
    },

    hideLandingScreen: function () {
        const landing = document.getElementById('landing-screen');
        if (landing) {
            landing.style.setProperty('display', 'none', 'important'); // Forzar ocultamiento
            document.body.style.overflow = 'auto';
        }
    },

    openStaffLogin: function () {
        const modal = document.getElementById('login-modal');
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    },

    closeLoginModal: function () {
        const modal = document.getElementById('login-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    },

    openClientAuth: function () {
        const modal = document.getElementById('client-auth-modal');
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
            // Reset forms
            document.getElementById('client-login-form').style.display = 'block';
            document.getElementById('client-register-form').style.display = 'none';
            document.getElementById('auth-title').textContent = 'Bienvenido Cliente';
        }
    },

    closeClientAuth: function () {
        const modal = document.getElementById('client-auth-modal');
        if (modal) modal.style.display = 'none';
    },

    toggleClientForms: function () {
        // Disabled public registration
        // const loginForm = document.getElementById('client-login-form');
        // ...
        return;
    },

    // =================================================================
    // LÓGICA DE CLIENTE (Auth)
    // =================================================================

    // =================================================================
    // LÓGICA DE CLIENTE (Auth)
    // =================================================================

    handleClientLogin: async function () {
        const email = document.getElementById('client-email').value;
        const password = document.getElementById('client-password').value;
        const btn = document.querySelector('#client-login-form button');

        if (!email || !password) return alert("Complete los campos");

        btn.disabled = true;
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Conectando...';

        try {
            const response = await fetch('/api/auth/client/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success) {
                if (data.requires_password_change) {
                    this.closeClientAuth();
                    this.showChangePasswordModal(email, password); // Pass current creds
                } else {
                    this.setCurrentUser(data.user);
                    this.closeClientAuth();
                    this.hideLandingScreen();
                }
            } else {
                this.mostrarNotificacion(data.message || "Error de inicio de sesión", 'error');
            }
        } catch (e) {
            console.error(e);
            this.mostrarNotificacion("Error de conexión", 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    },

    showChangePasswordModal: function (email, oldPassword) {
        let modal = document.getElementById('change-pass-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'change-pass-modal';
            modal.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.85); z-index: 20000;
                display: flex; align-items: center; justify-content: center;
                backdrop-filter: blur(5px);
            `;
            modal.innerHTML = `
                <div class="bg-white rounded-3 shadow-lg p-4" style="width: 100%; max-width: 400px; animation: slideIn 0.3s ease;">
                    <div class="text-center mb-4">
                        <i class="fas fa-key fa-3x text-warning mb-3"></i>
                        <h4 class="fw-bold">Cambio de Contraseña</h4>
                        <p class="text-muted small">Por seguridad, debes actualizar tu contraseña temporal.</p>
                    </div>
                    <form id="change-pass-form">
                        <div class="mb-3">
                            <label class="form-label fw-bold small">Nueva Contraseña</label>
                            <input type="password" id="new-pass-1" class="form-control" required minlength="6">
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold small">Confirmar Contraseña</label>
                            <input type="password" id="new-pass-2" class="form-control" required minlength="6">
                        </div>
                        <div class="d-grid gap-2">
                            <button type="submit" class="btn btn-primary fw-bold">Actualizar Contraseña</button>
                        </div>
                    </form>
                </div>
            `;
            document.body.appendChild(modal);
        }

        // Reset inputs
        if (document.getElementById('new-pass-1')) document.getElementById('new-pass-1').value = '';
        if (document.getElementById('new-pass-2')) document.getElementById('new-pass-2').value = '';

        modal.style.display = 'flex';

        const form = document.getElementById('change-pass-form');
        form.onsubmit = async (e) => {
            e.preventDefault();
            const p1 = document.getElementById('new-pass-1').value;
            const p2 = document.getElementById('new-pass-2').value;

            if (p1 !== p2) return alert("Las contraseñas no coinciden");
            if (p1.length < 6) return alert("La contraseña debe tener al menos 6 caracteres");

            // Call API
            try {
                const btn = form.querySelector('button');
                const orig = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = 'Actualizando...';

                const res = await fetch('/api/auth/client/change-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: email,
                        old_password: oldPassword,
                        new_password: p1
                    })
                });

                const d = await res.json();
                if (d.success) {
                    alert("Contraseña actualizada correctamente. Ingresa de nuevo.");
                    modal.style.display = 'none';
                    this.openClientAuth(); // Re-open logic
                    // Pre-fill email?
                    const emailInput = document.getElementById('client-email');
                    if (emailInput) emailInput.value = email;
                    const passInput = document.getElementById('client-password');
                    if (passInput) passInput.value = ''; // Force them to type new pass
                } else {
                    alert(d.message || "Error al actualizar");
                }
                btn.disabled = false;
                btn.innerHTML = orig;

            } catch (err) {
                console.error(err);
                alert("Error de conexión");
            }
        };
    },

    // handleClientRegister REMOVED - Public registration disabled

    // =================================================================
    // LÓGICA DE STAFF (Responsables)
    // =================================================================

    loadResponsables: async function () {
        try {
            const select = document.getElementById('login-usuario');
            if (!select) return;

            select.innerHTML = '<option value="">Cargando...</option>';

            const response = await fetch('/api/auth/responsables');
            const users = await response.json();

            if (users.error) {
                // alert('Error cargando usuarios: ' + users.error);
                return; // Silent fail in landing mode
            }

            const usuariosActivos = users.filter(user => user.nombre && user.nombre.trim() !== '');

            select.innerHTML = '<option value="">Seleccione su nombre...</option>';
            usuariosActivos.forEach(user => {
                const option = document.createElement('option');
                option.value = user.nombre;
                option.dataset.dept = user.departamento;
                option.textContent = user.nombre;
                select.appendChild(option);
            });

        } catch (e) {
            console.error("Error fetching responsables:", e);
        }
    },

    handleLogin: async function (e) {
        e.preventDefault();

        const usuarioSelect = document.getElementById('login-usuario');
        const passwordInput = document.getElementById('login-password');
        const submitBtn = document.getElementById('btn-login-submit');
        const errorMsg = document.getElementById('login-error-msg');

        const nombre = usuarioSelect.value;
        const password = passwordInput.value;

        if (!nombre || !password) {
            this.showError("Por favor complete todos los campos.");
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verificando...';
        errorMsg.style.display = 'none';

        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ responsable: nombre, password: password })
            });

            const data = await response.json();

            if (data.success) {
                this.setCurrentUser(data.user);
                this.closeLoginModal();
                this.hideLandingScreen(); // Crucial
                passwordInput.value = '';
            } else {
                this.showError(data.message);
            }

        } catch (error) {
            console.error("Login error:", error);
            this.showError("Error de conexión con el servidor.");
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Ingresar al Sistema';
        }
    },

    showError: function (msg) {
        const el = document.getElementById('login-error-msg');
        if (el) {
            el.textContent = msg;
            el.style.display = 'block';
        } else {
            alert(msg);
        }
    },

    // =================================================================
    // GESTIÓN DE SESIÓN
    // =================================================================

    setCurrentUser: function (user) {
        this.currentUser = user;
        sessionStorage.setItem('friparts_user', JSON.stringify(user));

        if (!window.AppState) window.AppState = {};
        window.AppState.user = {
            name: user.nombre,
            nombre: user.nombre,
            rol: user.rol,
            tipo: user.tipo || 'STAFF',
            nit: user.nit || null,
            email: user.email || null,
            fullData: user
        };

        console.log(`👤 Usuario Logueado: ${user.nombre} (${user.rol})`);

        this.updateProfileUI();
        this.applyPermissions();

        // Si es cliente, mostrar mensaje diferente o nada
        if (user.rol !== 'Cliente') {
            this.showWelcomeMessage(user);
            this.autoFillForms();
        }

        // Re-iniciar modulo
        if (window.AppState?.paginaActual && window.AppState.paginaActual !== 'dashboard') {
            // Si el modulo actual NO esta permitido, applyPermissions lo redirigirá.
            // Si está permitido, lo re-init.
            // Pero para cliente, normalmente entra a portal-cliente-page por defecto.
            // Dejaremos que navigateTo maneje la redireccion inicial.
        }
    },

    showWelcomeMessage: function (user) {
        const mensajes = {
            'Inyección': `¡Hola ${user.nombre}! Listo para la producción.`,
            'Pulido': `¡Hola ${user.nombre}! Lista para pulir.`,
            'Administración': `Bienvenido al Centro de Control.`,
            'Comercial': `Bienvenido al Módulo de Pedidos.`,
            'Cliente': `Bienvenido a su Portal FriParts.`
        };
        const mensaje = mensajes[user.rol] || `¡Bienvenido ${user.nombre}!`;
        this.mostrarNotificacion(mensaje, 'success');
    },

    checkSession: function () {
        const stored = sessionStorage.getItem('friparts_user');
        if (stored) {
            try {
                const user = JSON.parse(stored);
                this.currentUser = user;
                if (!window.AppState) window.AppState = {};
                window.AppState.user = {
                    name: user.nombre,
                    nombre: user.nombre,
                    rol: user.rol,
                    tipo: user.tipo || 'STAFF',
                    nit: user.nit,
                    fullData: user
                };

                this.hideLandingScreen(); // Ocultar landing
                this.closeLoginModal();
                this.updateProfileUI();
                this.applyPermissions(); // Esto redirigira a la pagina correcta si la actual no es valida

                if (user.tipo === 'STAFF') {
                    this.autoFillForms();
                }

            } catch (e) {
                console.error("Error parsing session:", e);
                this.logout();
            }
        } else {
            // MOSTRAR LANDING SCREEN
            this.showLandingScreen();
        }
    },

    logout: function () {
        this.currentUser = null;
        sessionStorage.removeItem('friparts_user');
        // Mostrar Landing
        this.showLandingScreen();
        // Recargar para limpiar estados
        setTimeout(() => window.location.reload(), 200);
    },

    updateProfileUI: function () {
        if (!this.currentUser) return;
        const userNameEl = document.querySelector('.user-name');
        const userRoleEl = document.querySelector('.user-role');
        if (userNameEl) userNameEl.textContent = this.currentUser.nombre;
        if (userRoleEl) userRoleEl.textContent = this.currentUser.rol;
    },

    applyPermissions: function () {
        if (!this.currentUser) return;

        const role = this.currentUser.rol;
        let allowedPages = [...(this.permissions[role] || [])];

        // LOGICA EXCEPCIONES STAFF (Paola, Natalia)
        // LOGICA EXCEPCIONES STAFF (Paola, Natalia, Zoenia)
        const userNameUpper = this.currentUser.nombre.toUpperCase();

        // Helper para normalizar (quitar tildes)
        const normalize = (str) => str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        const nameNorm = normalize(userNameUpper);

        if (nameNorm.includes('NATALIA') || nameNorm.includes('NATHALIA')) {
            const modulosAdmin = ['almacen', 'pedidos', 'historial', 'reportes', 'inventario', 'dashboard'];
            modulosAdmin.forEach(m => { if (!allowedPages.includes(m)) allowedPages.push(m); });
        }

        // PAOLA y ZOENIA
        if (nameNorm.includes('PAOLA') || nameNorm.includes('ZOENIA')) {
            // Se agregan dashboard e inventario para mejor UX
            const modulosExtra = ['pulido', 'ensamble', 'historial', 'almacen', 'dashboard', 'inventario'];
            modulosExtra.forEach(m => { if (!allowedPages.includes(m)) allowedPages.push(m); });
        }

        // 1. Mostrar/Ocultar Menú Sidebar
        const menuItems = document.querySelectorAll('.sidebar-menu .menu-item');
        let firstAllowed = null;

        menuItems.forEach(item => {
            const pageName = item.getAttribute('data-page');

            // Si es Cliente, ocultar TODO el sidebar standard? 
            // O mostrar solo lo relevante?
            // Actualmente portal-cliente no está en el sidebar.
            // Asi que ocultamos todo para 'Cliente' si 'portal-cliente' no esta en la lista.

            if (allowedPages.includes(pageName)) {
                item.style.display = 'block';
                if (!firstAllowed) firstAllowed = pageName;
            } else {
                item.style.display = 'none';
            }
        });

        // 2. Redirección Forzada
        const activePage = document.querySelector('.page.active');
        // Si estamos en dashboard (default) pero usuario es Cliente -> Redirigir a Portal
        // Si no hay pagina activa conocida, o no permitida -> Redirigir

        // Determinar destino ideal
        let targetPage = 'dashboard'; // Default staff
        if (role === 'Cliente') targetPage = 'portal-cliente';
        else if (role === 'Comercial') targetPage = 'pedidos';
        else if (firstAllowed) targetPage = firstAllowed;

        if (activePage) {
            const pageId = activePage.id.replace('-page', '');
            if (!allowedPages.includes(pageId)) {
                console.warn(`🛑 ACCESO DENEGADO a ${pageId} para rol ${role}. Redirigiendo a ${targetPage}...`);
                this.navigateTo(targetPage);
            }
        } else {
            // Si no hay pagina activa (carga inicial), ir a target
            this.navigateTo(targetPage);
        }
    },

    navigateTo: function (pageName) {
        // Lógica de navegación. 
        // Si es Portal Cliente (que no está en sidebar), hacerlo manualmente.

        if (pageName === 'portal-cliente') {
            // Ocultar todas las paginas
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));

            // Mostrar Portal
            const portalPage = document.getElementById('portal-cliente-page');
            if (portalPage) portalPage.classList.add('active');

            // Sidebar: Desactivar todo o ocultar sidebar entero?
            // Mejor ocultar sidebar para Clientes para dar look de App
            if (this.currentUser.rol === 'Cliente') {
                const sidebar = document.querySelector('.sidebar');
                if (sidebar) sidebar.style.display = 'none';
                const main = document.querySelector('.main-content');
                if (main) main.style.marginLeft = '0'; // Full width
            }

            // Cargar datos iniciales del portal si existe Modulo
            if (window.ModuloPortal && typeof window.ModuloPortal.init === 'function') {
                window.ModuloPortal.init();
            }

        } else {
            // Navegación standard via clic en sidebar
            const link = document.querySelector(`.menu-item[data-page="${pageName}"] a`);
            if (link) {
                link.click();
            } else {
                console.error("No navigation link found for", pageName);
            }
        }
    },

    autoFillForms: function () {
        if (!this.currentUser) return;

        // Bloquear selects para que nadie registre a nombre de otros
        const selects = document.querySelectorAll('select[id^="responsable-"]');
        selects.forEach(select => {
            // Asegurar opcion
            let exists = false;
            for (let i = 0; i < select.options.length; i++) {
                if (select.options[i].value === this.currentUser.nombre) {
                    exists = true;
                    select.selectedIndex = i;
                    break;
                }
            }
            if (!exists) {
                const opt = document.createElement('option');
                opt.value = this.currentUser.nombre;
                opt.textContent = this.currentUser.nombre;
                select.appendChild(opt);
                select.value = this.currentUser.nombre;
            }
            // Bloquear (opcional, usuario pidio "persistencia", no explícitamente "bloqueo", pero es mas seguro)
            // select.disabled = true; 
        });

        const inputs = document.querySelectorAll('input[id^="responsable-"]');
        inputs.forEach(input => {
            if (input.type === 'text' || input.type === 'search') {
                input.value = this.currentUser.nombre;
            }
        });
    }
};

window.AuthModule = AuthModule;

document.addEventListener('DOMContentLoaded', () => {
    AuthModule.init();
});
