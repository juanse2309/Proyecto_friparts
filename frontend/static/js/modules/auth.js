
// auth.js - Manejo de Autenticación y Permisos

const AuthModule = {
    currentUser: null,

    // Matriz de Permisos
    // Roles: 'Administración', 'Comercial', 'Auxiliar Inventario', 'Inyección', 'Pulido', 'Ensamble'
    permissions: {
        'Administración': ['dashboard', 'inventario', 'inyeccion', 'pulido', 'ensamble', 'pnc', 'facturacion', 'mezcla', 'historial', 'reportes', 'pedidos', 'almacen'],
        'Comercial': ['pedidos'],  // Solo acceso a Pedidos
        'Auxiliar Inventario': ['inventario', 'inyeccion', 'pnc', 'historial', 'almacen'],
        'Inyección': ['inyeccion', 'mezcla'],
        'Pulido': ['pulido'],
        'Ensamble': ['ensamble'],
        'Alistamiento': ['almacen', 'historial'], // Las colaboradoras ven almacen e historial
        // Fallback
        'Invitado': []
    },

    init: async function () {
        console.log("🔐 Inicializando Módulo de Autenticación...");

        // 1. Crear Modal de Login si no existe (lo inyectamos dinámicamente o esperamos que esté en HTML)
        // Check HTML presence, if not, wait or create. 
        // For consistency, I will assume HTML is added to index.html as per plan.

        // 2. Cargar lista de responsables
        await this.loadResponsables();

        // 3. Setup Listeners
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }

        const passwordInput = document.getElementById('login-password');
        if (passwordInput) {
            // "Validación de Contraseña: El campo de contraseña solo debe permitir caracteres numéricos"
            passwordInput.addEventListener('input', function (e) {
                this.value = this.value.replace(/[^0-9]/g, '');
            });
        }

        // 4. Bloquear interfaz si no hay usuario
        this.checkSession();
    },

    loadResponsables: async function () {
        try {
            const select = document.getElementById('login-usuario');
            if (!select) return;

            select.innerHTML = '<option value="">Cargando...</option>';

            const response = await fetch('/api/auth/responsables');
            const users = await response.json();

            if (users.error) {
                alert('Error cargando usuarios: ' + users.error);
                return;
            }

            // FILTRO FRONTEND: Solo usuarios activos
            const usuariosActivos = users.filter(user => {
                // El backend ya filtra, pero doble verificación
                return user.nombre && user.nombre.trim() !== '';
            });

            console.log(`🔐 Usuarios activos cargados: ${usuariosActivos.length}`);

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
            document.getElementById('login-usuario').innerHTML = '<option value="">Error de conexión</option>';
        }
    },

    handleLogin: async function (e) {
        e.preventDefault();

        const usuarioSelect = document.getElementById('login-usuario');
        const passwordInput = document.getElementById('login-password');
        const submitBtn = document.getElementById('btn-login-submit');
        const errorMsg = document.getElementById('login-error-msg');

        const nombre = usuarioSelect.value;
        const password = passwordInput.value; // Documento

        if (!nombre || !password) {
            this.showError("Por favor complete todos los campos.");
            return;
        }

        // UI Loading
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
                // Login Exitoso
                this.setCurrentUser(data.user);
                this.closeLoginModal();
                // Limpiar password
                passwordInput.value = '';
            } else {
                // Error
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

    setCurrentUser: function (user) {
        this.currentUser = user;

        // Persistir en sessionStorage
        sessionStorage.setItem('friparts_user', JSON.stringify(user));

        // CRÍTICO: Guardar en window.AppState para acceso global
        if (!window.AppState) window.AppState = {};
        window.AppState.user = {
            name: user.nombre,
            nombre: user.nombre, // Compatibilidad
            rol: user.rol,
            fullData: user
        };

        console.log(`👤 Usuario Logueado: ${user.nombre} (${user.rol})`);
        console.log(`📦 AppState.user actualizado:`, window.AppState.user);

        // Actualizar UI
        this.updateProfileUI();

        // Aplicar Permisos
        this.applyPermissions();

        // Mensaje de bienvenida personalizado
        this.showWelcomeMessage(user);

        // Auto-rellenar selects de responsables en la app
        this.autoFillForms();
    },

    showWelcomeMessage: function (user) {
        const mensajes = {
            'Inyección': `¡Hola ${user.nombre}! Listo para la producción de inyección.`,
            'Pulido': `¡Buen turno, ${user.nombre}! Estación de trabajo lista.`,
            'Ensamble': `¡Buen turno, ${user.nombre}! Estación de trabajo lista.`,
            'Administración': `Bienvenido al Centro de Control FriTech.`,
            'Comercial': `¡Bienvenido ${user.nombre}! Acceso habilitado para el módulo de Pedidos.`,
            'Auxiliar Inventario': `¡Buen turno, ${user.nombre}! Estación de trabajo lista.`
        };

        const mensaje = mensajes[user.rol] || `¡Bienvenido ${user.nombre}!`;

        console.log(`👋 MENSAJE DE BIENVENIDA: ${mensaje}`);

        // Mostrar notificación si existe la función
        if (typeof mostrarNotificacion === 'function') {
            mostrarNotificacion(mensaje, 'success');
        } else {
            // Fallback: alert temporal
            setTimeout(() => alert(mensaje), 500);
        }
    },

    checkSession: function () {
        const stored = sessionStorage.getItem('friparts_user');
        if (stored) {
            try {
                const user = JSON.parse(stored);
                // Restaurar sesión
                this.currentUser = user;

                // CRÍTICO: Restaurar AppState también
                if (!window.AppState) window.AppState = {};
                window.AppState.user = {
                    name: user.nombre,
                    nombre: user.nombre, // Compatibilidad
                    rol: user.rol,
                    fullData: user
                };

                console.log(`🔄 Sesión restaurada: ${user.nombre} (${user.rol})`);
                console.log(`📦 AppState.user restaurado:`, window.AppState.user);

                this.closeLoginModal();
                this.updateProfileUI();
                this.applyPermissions();
                this.autoFillForms();
            } catch (e) {
                console.error("Error parsing session:", e);
                this.logout();
            }
        } else {
            // Mostrar Login
            this.openLoginModal();
        }
    },

    logout: function () {
        this.currentUser = null;
        sessionStorage.removeItem('friparts_user');
        this.openLoginModal();
        // Recargar para limpiar estados si es necesario
        window.location.reload();
    },

    openLoginModal: function () {
        const modal = document.getElementById('login-modal');
        if (modal) {
            modal.style.display = 'flex'; // Flex para centrar
            document.body.style.overflow = 'hidden'; // Bloquear scroll
        }
    },

    closeLoginModal: function () {
        const modal = document.getElementById('login-modal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto'; // Restaurar scroll
        }
    },

    updateProfileUI: function () {
        if (!this.currentUser) return;

        // Sidebar footer update
        // "En la sección inferior donde aparece la fecha, muestra dinámicamente: [NOMBRE] y debajo [DEPARTAMENTO]"
        // Sidebar format:
        // <div class="user-details"> <span class="user-name">Administrador</span> <span class="user-role">Supervisor</span> </div>

        const userNameEl = document.querySelector('.user-name');
        const userRoleEl = document.querySelector('.user-role');

        if (userNameEl) userNameEl.textContent = this.currentUser.nombre;
        if (userRoleEl) userRoleEl.textContent = this.currentUser.rol;
    },

    applyPermissions: function () {
        if (!this.currentUser) return;

        const role = this.currentUser.rol;
        let allowedPages = [...(this.permissions[role] || [])];

        // EXCEPCIÓN ESPECIAL: Natalia/Nathalia es la jefa de Alistamiento, requiere permisos de administración en este flujo
        const userNameUpper = this.currentUser.nombre.toUpperCase();
        if (userNameUpper.includes('NATALIA') || userNameUpper.includes('NATHALIA')) {
            const modulosAdmin = ['almacen', 'pedidos', 'historial', 'reportes', 'inventario', 'dashboard'];
            modulosAdmin.forEach(m => {
                if (!allowedPages.includes(m)) allowedPages.push(m);
            });
            console.log("🔓 Permisos de Jefa aplicados para Natalia");
        }

        // EXCEPCIÓN ESPECIAL: Paola requiere acceso a Pulido y Ensamble independientemente de su rol
        if (this.currentUser.nombre.toUpperCase() === 'PAOLA') {
            const modulosExtra = ['pulido', 'ensamble', 'historial', 'almacen'];
            modulosExtra.forEach(m => {
                if (!allowedPages.includes(m)) allowedPages.push(m);
            });
            console.log("🔓 Permisos extendidos aplicados para Paola");
        }

        // 1. Sidebar Links
        const menuItems = document.querySelectorAll('.sidebar-menu .menu-item');
        let firstAllowed = null;

        menuItems.forEach(item => {
            const pageName = item.getAttribute('data-page');
            if (allowedPages.includes(pageName)) {
                item.style.display = 'block'; // Show
                if (!firstAllowed) firstAllowed = pageName;
            } else {
                item.style.display = 'none'; // Hide
            }
        });

        // 2. BLINDAJE: Redirección forzada si está en página no autorizada
        const activePage = document.querySelector('.page.active');
        if (activePage) {
            const pageId = activePage.id.replace('-page', '');
            if (!allowedPages.includes(pageId)) {
                console.warn(`🛑 ACCESO DENEGADO a ${pageId} para rol ${role}. Redirigiendo...`);

                // CRÍTICO: Ocultar contenido inmediatamente
                const mainContent = document.querySelector('.main-content');
                if (mainContent) {
                    mainContent.style.visibility = 'hidden';
                }

                // Determinar página de destino según rol
                let targetPage;
                if (role === 'Comercial') {
                    // Comercial siempre va a Pedidos
                    targetPage = 'pedidos';
                } else if (allowedPages.includes('dashboard')) {
                    targetPage = 'dashboard';
                } else if (firstAllowed) {
                    targetPage = firstAllowed;
                } else {
                    alert("No tienes acceso a ningún módulo. Contacta al administrador.");
                    this.logout();
                    return;
                }

                // Redirección forzada
                console.log(`🔀 Redirigiendo a: ${targetPage}`);
                this.navigateTo(targetPage);

                // Restaurar visibilidad después de redirección
                setTimeout(() => {
                    if (mainContent) mainContent.style.visibility = 'visible';
                }, 300);
            }
        }
    },

    navigateTo: function (pageName) {
        // Implementación simple compatible con el router existente (si existe)
        // O simular clic en el menú
        const link = document.querySelector(`.menu-item[data-page="${pageName}"] a`);
        if (link) {
            link.click();
        } else {
            console.error("No navigation link found for", pageName);
        }
    },

    autoFillForms: function () {
        if (!this.currentUser) return;

        // "Persistencia: el nombre elegido debe viajar automáticamente como vendedor..."
        // Buscar todos los selects de responsables
        const selects = document.querySelectorAll('select[id^="responsable-"]');
        selects.forEach(select => {
            // Llenar si está vacío (lo cual debería ser, porque cargan por JS)
            // O agregar la opción del usuario actual y seleccionarla.
            // Primero asegurarnos que tiene la opción.

            // Wait, logic in Utils or other modules might populate this dropdown too.
            // If they are empty, I populate them.
            // If they are populated, I select the user.

            // Hack: Force option
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

            // Lock logic? Wait, user requirement: "viajar automáticamente...". 
            // Doesn't explicitly say lock, but implies automation. 
            // I'll leave it selectable but pre-selected.
        });

        // Soporte para INPUTS (Readonly o Smart Search) 
        const inputs = document.querySelectorAll('input[id^="responsable-"]');
        inputs.forEach(input => {
            if (input.type === 'text' || input.type === 'search') {
                input.value = this.currentUser.nombre;
                // Si es readonly, ya cumple "auto-fill y bloqueo" si se desea
            }
        });

        // Facturación
        const vendedorInput = document.getElementById('vendedor-facturacion'); // If exists
        // Need to check specific IDs for other forms based on index.html analysis
        // Pulido: responsable-pulido
        // Ensamble: responsable-ensamble
        // Inyeccion: responsable-inyeccion
    }
};

// Export global
window.AuthModule = AuthModule;

// Auto-init on load
document.addEventListener('DOMContentLoaded', () => {
    AuthModule.init();
});
