# 🏭 FriTech MES - Sistema de Gestión de Producción e Inventario ![v1.5.0](https://img.shields.io/badge/versión-1.5.0--estable-green)

FriTech MES (Manufacturing Execution System) es una plataforma full-stack diseñada específicamente para el control y automatización de procesos de producción, gestión de inventarios y sincronización con el ERP World Office de la planta de fabricación de bujes de FriParts.

El sistema utiliza una **arquitectura 100% SQL-First**, empleando **PostgreSQL** en la nube como base de datos transaccional única. La dependencia histórica de Google Sheets ha sido completamente removida, conservando únicamente la API de Google Drive de manera opcional para el almacenamiento de reportes PDF generados.

## ✨ Novedades Versión 1.5.0 (Estable)
- **Arquitectura SQL-First**: Consolidación definitiva de base de datos transaccional PostgreSQL como origen único de persistencia y control de inventarios, eliminando por completo Google Sheets.
- **Decomisión de Módulos Obsoletos**: Purga completa de los dashboards de gerencia y métricas PNC antiguas en favor de consultas SQL directas y óptimas.
- **Estructuración del Proyecto**: Organización formal de scripts temporales en `scratch/` y pruebas en `tests/` para mantener la raíz limpia y segura.
- **Seguridad en Integraciones**: Robustecimiento de la comunicación HTTPS con World Office mediante handshakes seguros autenticados con tokens dinámicos.

---

## 🧭 Módulos Principales del Sistema

| Módulo | Descripción Técnica | Componentes Clave |
| :--- | :--- | :--- |
| **🏭 Inyección** | Control del proceso primario de inyección de plástico. Soporta configuraciones de "Molde de Familia" (múltiples SKUs por ciclo), control de cavidades y control de tiempos y contadores por máquina. | `inyeccion_routes.py`<br>`inyeccion.js`<br>`PDFGenerator` (ReportLab) |
| **✨ Pulido** | Monitoreo del acabado y calidad de piezas. Incluye el flujo de **Liquidación de Lote**, cálculo automático de diferencias e inventario en tránsito desde satélites externos. | `pulido_routes.py`<br>`pulido.js`<br>`trazabilidad_lotes` (SQL) |
| **🔩 Ensamble** | Mapeo y ensamble final de bujes con base en una ficha maestra (recetas de componentes). Realiza deducciones automáticas de stock del almacén de materias primas al ensamblar un SKU. | `ensamble_routes.py`<br>`ensamble.js`<br>`bom_service.py` |
| **🛒 Pedidos** | Gestión de órdenes de compra comerciales y solicitudes de clientes. Visualización en tiempo real optimizada para visualizadores en planta (Modo TV) con alertas sonoras integradas. | `pedidos_routes.py`<br>`pedidos.js` |
| **📦 Almacén** | Flujo logístico interno con **Doble Check**: Alistamiento de mercancía (**Box** 📦) y confirmación de Despacho de camiones (**Truck** 🚚), con soporte para despachos parciales. | `inventario_routes.py`<br>`almacen.js` |
| **⚠️ PNC** | Control de **Producto No Conforme**. Registro, clasificación y búsqueda inteligente de rechazos de control de calidad por tipo de defecto para mitigar mermas en planta. | `pnc.js` (Registros de Calidad) |

---

## 🛠️ Stack Tecnológico

*   **Backend:** Python 3.9+ con **Flask** (Estructura de Blueprints modulares).
*   **Base de Datos:** **PostgreSQL** (100% transaccional principal vía *Flask-SQLAlchemy*). El soporte de lectura/escritura de Google Sheets está completamente deprecado e inactivo.
*   **Frontend:** HTML5 semántico, **Vanilla CSS3** (layouts responsivos para pantallas de operador y celulares) y **JavaScript (ES6+)** con arquitectura modular.
*   **Reportes y PDF:** **ReportLab** para la generación local y carga automática en **Google Drive** de tiquetes de producción y fichas técnicas.
*   **Infraestructura:** Despliegue automatizado mediante CI/CD en **Render**.

---

## ⚙️ Configuración del Entorno

### Requisitos Previos
*   Python 3.9 o superior.
*   Instalación de PostgreSQL local o en la nube.
*   Credenciales de Google Cloud Platform (Service Account habilitado para la API de Google Drive para almacenamiento de reportes).

### Archivo de Variables de Entorno (`.env`)
Configura un archivo `.env` en la raíz del proyecto basándote en la siguiente plantilla:

```ini
# ============================================
# CONFIGURACIÓN GOOGLE DRIVE (REPORTES PDF)
# ============================================
DRIVE_REPORTS_FOLDER_ID=id_de_la_carpeta_de_drive_para_reportes

# ============================================
# CONFIGURACIÓN DE CACHÉ Y SEGURIDAD FLASK
# ============================================
FLASK_ENV=development # development | production
FLASK_DEBUG=true
PORT=5005
SECRET_KEY=clave_secreta_para_sesiones_flask
CACHE_TTL=120
CACHE_ENABLED=true

# ============================================
# CONFIGURACIÓN DE BASE DE DATOS TRANSACCIONAL
# ============================================
# Utilizado por Flask-SQLAlchemy para persistencia de producción
DATABASE_URL=postgresql://usuario:password@host:port/database_name

# ============================================
# INTEGRACIÓN ERP WORLD OFFICE (WO)
# ============================================
# Conexión local del agente a la BD SQL Server de World Office
WO_SERVER=SERVERWO\WORLDOFFICE17
WO_DB=FRIPARTS2021
WO_USER=wo_cliente
WO_PASSWORD=wo_cliente

# Handshake seguro de API de Sincronización
WO_SYNC_API_KEY=token_seguro_de_comunicacion_wo
API_RENDER_URL=https://tu-app-en-render.com/api/wo/recibir_datos

# ============================================
# CONFIGURACIÓN DE INTELIGENCIA ARTIFICIAL
# ============================================
GOOGLE_API_KEY=api_key_para_google_ai_studio
```

---

## 🔄 Integraciones y Flujos Críticos

### 1. Sincronización con World Office ERP
El sistema mantiene una comunicación fluida con la base de datos comercial y de inventario de World Office mediante un agente automatizado (`agente_wo_comercial.py` / `agente_wo.py`):
1.  **Agente Local**: Lee de manera segura la base de datos del ERP en SQL Server.
2.  **Handshake Seguro**: Empaqueta los datos y los envía a la API en Render usando cabeceras de autorización firmadas con `X-Sync-Token` (asociado a `WO_SYNC_API_KEY`).
3.  **Procesamiento**: Los endpoints en `backend/routes/wo_routes.py` reciben y actualizan los saldos de inventario comprometido y de ventas acumuladas en PostgreSQL.

### 2. Flujo de Satélite / Pulido
*   El material inyectado se clasifica como "Por Pulir".
*   Al enviarse a satélites de pulido, se crea un **Lote de Pulido** en estado "ACTIVO" en la base de datos.
*   El frontend en `pulido.js` implementa campos "pegajosos" (Sticky Inputs) y notificaciones dinámicas basadas en caché de persistencia de sesión para acelerar el registro del operario.
*   **Liquidación de Lote**: Cuando el lote retorna, el supervisor cierra el lote a través de la acción "Liquidar Lote", lo que transfiere automáticamente el stock pulido a "Producto Terminado" o "Producto Ensamblado" y registra diferencias de producción.

---

## 🔧 Reglas de Mantenimiento y Estructura de Limpieza

Para mantener el repositorio limpio y el código en producción libre de archivos basura, se han establecido reglas estrictas de segregación de carpetas:

```
📂 proyecto_friparts/
├── 📂 backend/           # Lógica del servidor Python/Flask, modelos y rutas
├── 📂 frontend/          # Interfaz de usuario (HTML, CSS, módulos JS)
├── 📂 scratch/           # Carpeta exclusiva para scripts de desarrollo
└── 📂 tests/             # Carpeta para pruebas automáticas y de integración
```

*   **🚫 Cero Scripts en la Raíz**: Queda estrictamente prohibido crear scripts de prueba rápida o utilitarios sueltos en el directorio raíz o dentro de `backend/`.
*   **📁 Carpeta `scratch/`**: Todos los scripts de migración de datos (`migrate.py`), pruebas de query rápidas (`test_query_cot.py`) o diagnósticos temporales deben guardarse en `scratch/`. Esta carpeta está diseñada para no interferir con las ejecuciones en producción.
*   **📁 Carpeta `tests/`**: Los archivos que verifiquen el comportamiento de la aplicación de manera automatizada (e.g., pruebas unitarias o de integración como `test_wo_sync.py`) deben residir en esta sección.

---

## 🚀 Puesta en Marcha (Instalación Local)

1.  **Clonar e ingresar al directorio del proyecto**:
    ```bash
    git clone https://github.com/juanse2309/Proyecto_friparts.git
    cd Proyecto_friparts
    ```

2.  **Crear el entorno virtual y activar**:
    *   **En Windows:**
        ```bash
        python -m venv .venv
        .venv\Scripts\activate
        ```
    *   **En macOS/Linux:**
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```

3.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar credenciales de acceso**:
    *   Duplicar `.env.example`, renombrarlo a `.env` y configurar las credenciales correctas.
    *   Ubicar el archivo de cuenta de servicio de Google Cloud (`credentials_apps.json`) en la raíz del proyecto (este archivo se encuentra en el `.gitignore` por seguridad).

5.  **Ejecutar la aplicación**:
    ```bash
    python -m backend.app
    ```
    La aplicación se iniciará en `http://localhost:5005` (o en el puerto definido en tus variables de entorno).
