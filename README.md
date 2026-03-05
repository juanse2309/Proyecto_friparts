# Proyecto Bujes - Sistema de Gestión de Producción ![v1.4.3](https://img.shields.io/badge/versión-1.4.3-green)

Este proyecto es una aplicación web full-stack diseñada para gestionar la producción, inventario y facturación de una fábrica de bujes. Utiliza **Google Sheets** como base de datos en tiempo real.

## ✨ Novedades Versión 1.4.3 (Backfill de Pulido)
- **Sincronización de Fecha**: La fecha ahora también se recupera del último registro en Sheets al seleccionar el operario, facilitando el ingreso masivo de datos históricos sin tener que re-ingresar el día.

## ✨ Novedades Versión 1.4.2 (Sincronización de Pulido)
- **Historial Global de Pulido**: Ahora el banner de último registro se sincroniza con Google Sheets. Esto permite que los operarios vean su último trabajo incluso si cambian de dispositivo o borran el historial del navegador.

## ✨ Novedades Versión 1.4.1 (UX Pulido & PDF Fix)
- **UX Pulido Optimizado**: Campos "pegajosos" (Sticky Inputs) para Fecha y Responsable, junto con un banner de notificación del último registro para agilizar ingresos masivos.
- **Fix PDF Inyección**: Robustez mejorada para evitar fallos silenciosos ante datos nulos o mal formateados en el proceso de inyección multi-sku.

## ✨ Novedades Versión 1.4.0 (Arquitectura & Persistencia)
- **Persistencia Global de Formularios**: Los formularios de producción (Inyección, Pulido, Ensamble, Mezcla) y Pedidos ahora guardan el progreso automáticamente en el navegador. No más pérdida de datos al recargar.
- **Memoria de Aplicación**: El sistema recuerda la última página visitada y la máquina seleccionada en el módulo MES.
- **Seguridad de Repositorio**: Optimización de `.gitignore` y limpieza de historial para proteger credenciales de Google Cloud y variables de entorno.
- **Plantilla PDF Premium**: Nueva generación de reportes de inyección con soporte para "Molde de Familia" (múltiples productos por inyección) y resumen ejecutivo.
- **Hotfix Render**: Corrección de dependencias (`reportlab`) para estabilidad en producción.

## ✨ Novedades Versión 1.3.1 (Hotfix & Mejoras)
- **Restauración en Deshacer**: Ahora al deshacer un registro, los datos se restauran en el formulario para corrección rápida.
- **Feedback Sonoro Mejorado**: Nuevos sonidos para error crítico y notificación de pedidos en modo TV.
- **Scroll en Modales**: Solucionado el problema de scroll en modales de auditoría en móviles.

## ✨ Novedades Versión 1.3.0 (UX & Personalización)
Esta versión se enfoca en mejorar la experiencia del operario, haciéndola más amigable y segura.

### 🎨 Personalización
- **Saludo Dinámico**: La barra lateral saluda según la hora del día (Buenos días/tardes).
- **Avatar de Usuario**: Generación automática de avatar con iniciales y color único por usuario.

### ↩️ Botón de Pánico (Deshacer)
- **Seguridad Operativa**: Al registrar en Inyección, Pulido o Ensamble, aparece un botón **"DESHACER"** por 5 segundos.
- **Corrección Inmediata**: Permite eliminar el último registro erróneo sin necesidad de soporte técnico.

## 🚀 Características

### 📊 Dashboard y Analítica
- **Dashboard en Tiempo Real**: KPIs y analítica avanzada integrada con **Chart.js** (reemplaza Power BI externo)
- **Modo TV**: Vista de monitoreo continuo para planta con auto-refresco (30s) y fuentes de alto contraste
- **Semáforo de Inventario**: Alertas visuales de stock (Verde/Amarillo/Rojo)

### 📦 Gestión de Almacén
- **Sistema de Doble Check**: Alistamiento (Box 📦) y Despacho (Truck 🚚) con seguimiento de entregas parciales
- **Auto-Refresh**: Actualización automática cada 15 segundos
- **Delegación de Pedidos**: Asignación de órdenes a colaboradoras específicas

### 🛒 Portal Cliente
- **Catálogo de Productos**: Vista moderna con búsqueda inteligente y paginación
- **Carrito de Compras**: Gestión de pedidos con cálculo automático de totales
- **Historial de Pedidos**: Seguimiento de estado y progreso de entregas

### 🏭 Gestión de Procesos
- **Inyección**: Registro de producción con control de operarios y máquinas (Soporte Multi-SKU)
- **Pulido**: Seguimiento de acabado y calidad
- **Ensamble**: Control de ensamblaje final con selector dinámico de recetas
- **Mezclas Automáticas**: Gestión de formulaciones y materias primas
- **PNC (Producto No Conforme)**: Control detallado de rechazos por calidad con Smart Search

### 🔐 Seguridad y Permisos
- **Autenticación**: Sistema de login con Google Sheets como base de usuarios
- **Roles Granulares**: Administración, Comercial, Producción, Almacén
- **Arquitectura de Secretos**: Compatible con Google Service Accounts y variables de entorno seguras en Render.

## 📁 Estructura del Proyecto
- `backend/`: Contiene `app.py` (Flask) y la lógica de módulos (services, routes, utils).
- `frontend/`:
  - `templates/`: Archivos HTML (index.html, login.html).
  - `static/`: Estilos (CSS), Imágenes y Módulos de Javascript (`js/modules`).
- `requirements.txt`: Dependencias de Python (Flask, gspread, reportlab, etc.).

## 🛠️ Stack Tecnológico

### Backend
- **Python 3.9+** / **Flask**
- **gspread**: Google Sheets API
- **ReportLab**: Generación de PDFs profesionales
- **python-dotenv**: Gestión de secretos

### Frontend
- **JavaScript (ES6+)** / **Vanilla CSS3**
- **Chart.js**: Visualización de datos y analítica en tiempo real.
- **Arquitectura Modular**: Módulos independientes para cada proceso (inyeccion.js, pulido.js, etc.)

## 🛠️ Instalación Local

1.  **Clonar el repositorio**:
    ```bash
    git clone https://github.com/juanse2309/Proyecto_friparts.git
    cd Proyecto_friparts
    ```

2.  **Crear entorno virtual e instalar dependencias**:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate  # Windows
    pip install -r requirements.txt
    ```

3.  **Configurar credenciales**:
    - Renombra `.env.example` a `.env`.
    - Coloca `credentials_apps.json` en la raíz (está ignorado por seguridad).

4.  **Ejecutar**:
    ```bash
    python -m backend.app
    ```

## 🌐 Despliegue en Render

La aplicación utiliza un flujo CI/CD vía GitHub. 
- **Start Command**: `gunicorn backend.app:app`
- **Secret Files**: Subir `credentials_apps.json`, `token.json` y `client_secrets.json` a la sección "Secret Files" de Render.

---
*Desarrollado con ❤️ por Juan Sebastian.*
