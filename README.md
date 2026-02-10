# Proyecto Bujes - Sistema de Gestión de Producción

Este proyecto es una aplicación web full-stack diseñada para gestionar la producción, inventario y facturación de una fábrica de bujes. Utiliza **Google Sheets** como base de datos en tiempo real.

## 🚀 Características

### 📊 Dashboard y Analítica
- **Dashboard en Tiempo Real**: KPIs y gráficos de producción integrados con Power BI
- **Modo TV**: Vista de monitoreo continuo para planta con auto-refresco (30s) y fuentes de alto contraste
- **Semáforo de Inventario**: Alertas visuales de stock (Verde/Amarillo/Rojo)

### 📦 Gestión de Almacén
- **Sistema de Doble Check**: Alistamiento (Box 📦) y Despacho (Truck 🚚) con seguimiento de entregas parciales
- **Auto-Refresh**: Actualización automática cada 15 segundos
- **Delegación de Pedidos**: Asignación de órdenes a colaboradoras específicas
- **Eliminación de Productos**: Andrés y Admins pueden eliminar productos de pedidos con restauración automática de inventario
- **Modo Solo Lectura**: Usuarios Comercial pueden visualizar sin editar (excepto Andrés)

### 🛒 Portal Cliente
- **Catálogo de Productos**: Vista moderna con búsqueda inteligente y paginación
- **Toggle de Vista**: Cambio entre vista Lista y Cuadrícula (cards)
- **Carrito de Compras**: Gestión de pedidos con cálculo automático de totales
- **Historial de Pedidos**: Seguimiento de estado y progreso de entregas
- **Optimización Mobile**: Diseño responsivo tipo e-commerce

### 🏭 Gestión de Procesos
- **Inyección**: Registro de producción con control de operarios y máquinas
- **Pulido**: Seguimiento de acabado y calidad
- **Ensamble**: Control de ensamblaje final
- **Mezclas Automáticas**: Gestión de formulaciones y materias primas
- **PNC (Producto No Conforme)**: Control detallado de rechazos por calidad con Smart Search

### 📋 Facturación y Pedidos
- **Creación de Órdenes**: Sistema completo con múltiples productos
- **PDF Premium**: Generación automática con logo oficial y datos extensos
- **Descuentos Globales**: Aplicación de descuentos por pedido
- **Sincronización de Inventario**: Descuento automático de stock al crear pedidos
- **Formas de Pago**: Contado, Crédito, Transferencia

### 🔐 Seguridad y Permisos
- **Autenticación**: Sistema de login con Google Sheets como base de usuarios
- **Roles Granulares**: Administración, Comercial, Producción, Almacén
- **Permisos Especiales**: Configuración específica para Andrés, Natalia y otros supervisores
- **Modo Solo Lectura**: Restricción de edición para roles específicos

## 📁 Estructura del Proyecto
- `backend/`: Contiene `app.py` (Flask) y la lógica de integración con Google Sheets.
- `frontend/`:
  - `templates/`: Archivos HTML.
  - `static/`: Estilos (CSS), Imágenes y Módulos de Javascript (`js/modules`).
- `requirements.txt`: Dependencias de Python.
- `.env.example`: Plantilla de configuración de variables de entorno.

## 🛠️ Stack Tecnológico

### Backend
- **Python 3.9+**: Lenguaje principal
- **Flask**: Framework web minimalista
- **gspread**: Cliente de Google Sheets API
- **ReportLab**: Generación de PDFs
- **python-dotenv**: Gestión de variables de entorno

### Frontend
- **HTML5/CSS3**: Estructura y estilos
- **JavaScript (ES6+)**: Lógica del cliente
- **Bootstrap 5**: Framework CSS responsivo
- **Font Awesome**: Iconografía
- **Arquitectura Modular**: Cada módulo (almacen.js, pedidos.js, etc.) es independiente

### Base de Datos
- **Google Sheets**: Base de datos en tiempo real
- **Google Sheets API v4**: Integración con Python
- **Service Account**: Autenticación segura

### Analítica
- **Power BI**: Dashboards y reportes interactivos
- **Power BI Service**: Publicación y compartición de reportes

### Despliegue
- **Render**: Hosting de aplicación web
- **GitHub**: Control de versiones y CI/CD automático
- **Gunicorn**: Servidor WSGI para producción

## 🛠️ Instalación Local

1.  **Clonar el repositorio**:
    ```bash
    git clone https://github.com/juanse2309/Proyecto_friparts.git
    cd Proyecto_friparts
    ```

2.  **Crear entorno virtual**:
    ```bash
    python -m venv .venv
    # En Windows:
    .venv\Scripts\activate
    # En Linux/Mac:
    source .venv/bin/activate
    ```

3.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar credenciales**:
    - Renombra `.env.example` a `.env` y completa los valores.
    - Coloca el archivo `credentials_apps.json` (Service Account de Google) en la raíz del proyecto.
    - **IMPORTANTE**: Este archivo NO debe subirse al repositorio (ya está en `.gitignore`).

5.  **Ejecutar el servidor**:
    ```bash
    # Opción 1: Módulo
    python -m backend.app
    
    # Opción 2: Script directo
    python backend/app.py
    ```
    
    El servidor estará disponible en `http://127.0.0.1:5005`

## 🌐 Despliegue en Render

La aplicación está configurada para desplegarse automáticamente al hacer push a la rama `main`. 

### Configuración Requerida en Render:
1. **Build Command**: `pip install -r requirements.txt`
2. **Start Command**: `gunicorn backend.app:app`
3. **Environment Variables**:
   - Configura todas las variables del archivo `.env`
   - Agrega el contenido de `credentials_apps.json` como variable de entorno si es necesario

### Variables de Entorno Críticas:
- `FLASK_ENV`: production
- `SECRET_KEY`: Clave secreta para sesiones
- Credenciales de Google Sheets API

## 📊 Documentación de Analítica y Auditoría (Power BI)

Esta sección describe la arquitectura de inteligencia de negocios integrada en el sistema, diseñada para facilitar la trazabilidad y la toma de decisiones estratégicas.

### 🏗️ Arquitectura de Datos
El sistema opera bajo un modelo de **Microservicios Híbridos**:
1.  **Base de Datos en Tiempo Real (Google Sheets):** Actúa como la fuente única de la verdad (Single Source of Truth). Todas las transacciones (entradas, salidas, PNC) se persisten aquí inmediatamente.
2.  **Backend (Flask/Python):** Procesa, valida y normaliza los datos antes de enviarlos a las hojas.
3.  **Power BI Service:** Consume directamente los datasets de las hojas clave (`INYECCION`, `PULIDO`, `PEDIDOS`, `PRODUCTOS`) para generar visualizaciones interactivas.

### 📈 Dashboard de Control Operativo
**Enlace del Reporte en Vivo:** [Ver Dashboard Power BI](https://app.powerbi.com/view?r=eyJrIjoiZTBlYzc0MmUtNmVmZS00NDVjLWIwNTctMDY4NDA5MjEwNjk2IiwidCI6ImMwNmZiNTU5LTFiNjgtNGI4NC1hMTRmLTQ3ZDBkODM3YTVhYiIsImMiOjR9)

#### Propósito
Centralizar la trazabilidad completa del ciclo de vida del producto, desde la inyección de materia prima hasta la entrega final al cliente, permitiendo auditorías visuales rápidas.

#### Guía de Visualizadores (Para Auditores)

| Visualizador | Propósito de Auditoría | Lógica de Negocio |
| :--- | :--- | :--- |
| **Gráficos de Producción** | Medir eficiencia operativa (OEE). | Permite identificar **cuellos de botella** comparando la producción teórica vs. real por operario y máquina. |
| **Mapa de Ventas** | Análisis de distribución. | Visualiza el cumplimiento de despachos por zona geográfica y penetración de mercado. |
| **Semáforo de Inventario** | Alerta temprana de stock. | - **Verde:** Stock > Punto de Reorden (Saludable)<br>- **Amarillo:** Stock <= Punto de Reorden (Alerta)<br>- **Rojo:** Stock <= 0 (Stockout/Crítico) |
| **Tasa de PNC** | Control de Calidad. | Monitorea el porcentaje de desperdicio (Producto No Conforme) respecto a la producción total. |

### 📖 Diccionario de Datos (Headers)
Para garantizar la integridad del reporte, los siguientes campos son críticos en la sincronización Backend -> Google Sheets -> Power BI:

- **ID CODIGO:** Identificador único técnico del producto (base para todas las relaciones).
- **CANTIDAD REAL:** Producción neta validada (descontando defectos).
- **PNC (Producto No Conforme):** Cantidad de piezas rechazadas por calidad.
- **PUNTO DE REORDEN:** Umbral mínimo de inventario antes de disparar alerta de compras.
- **FORMA DE PAGO/NIT:** Datos cruzados para conciliación financiera en el módulo de Pedidos.

### ⚙️ Manual de Operación Técnica
1.  **Ingesta de Datos:** El backend Python normaliza todos los códigos (elimina espacios, unifica mayúsculas) antes de escribir en Sheets para asegurar que Power BI pueda relacionar las tablas sin errores.
2.  **Cálculo de Totales:** Los descuentos y subtotales se calculan en el servidor (`app.py`) y se guardan como *valores finales* en Sheets, liberando a Power BI de cálculos complejos a nivel de fila.
3.  **Actualización:** El reporte de Power BI está configurado para actualizarse periódicamente contra la API de Google Sheets.

## 🔄 Flujo de Trabajo

### Ciclo de Vida de un Pedido
1. **Creación**: Cliente o Comercial crea pedido en Portal/Módulo Pedidos
2. **Registro**: Backend valida y guarda en hoja PEDIDOS, descuenta inventario
3. **Delegación**: Natalia/Admin asigna pedido a colaboradora de almacén
4. **Alistamiento**: Colaboradora marca productos como alistados (Box 📦)
5. **Despacho**: Colaboradora marca productos como despachados (Truck 🚚)
6. **Seguimiento**: Cliente puede ver progreso en Portal Cliente
7. **Completado**: Cuando todos los productos están despachados, pedido se marca como COMPLETADO

### Sincronización de Inventario
- **Pedidos**: Descuenta de P. TERMINADO al crear pedido
- **Inyección/Ensamble**: Suma a P. TERMINADO al registrar producción
- **Eliminación de Producto**: Restaura a P. TERMINADO al eliminar de pedido
- **PNC**: Descuenta de inventario al registrar rechazo

## 🤝 Contribución

Este es un proyecto privado para FriParts. Para contribuir:
1. Crea una rama feature desde `main`
2. Realiza tus cambios
3. Haz commit con mensajes descriptivos (formato: `feat:`, `fix:`, `docs:`)
4. Haz push y crea un Pull Request

---
*Desarrollado con ❤️ por Juan Sebastian.*
