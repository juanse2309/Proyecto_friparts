# Proyecto Bujes - Sistema de Gestión de Producción

Este proyecto es una aplicación web full-stack diseñada para gestionar la producción, inventario y facturación de una fábrica de bujes. Utiliza **Google Sheets** como base de datos en tiempo real.

## 🚀 Características
- **Dashboard en Tiempo Real**: KPIs y gráficos de producción.
- **Gestión de Procesos**: Módulos para Inyección, Pulido y Ensamble.
- **Control de Inventario**: Seguimiento de stock con alertas de reorden.
- **Facturación**: Registro de ventas y exportación de historial.
- **PNC (Producto No Conforme)**: Registro detallado de defectos.

## 📁 Estructura del Proyecto
- `backend/`: Contiene `app.py` (Flask) y la lógica de integración con Google Sheets.
- `frontend/`:
  - `templates/`: Archivos HTML.
  - `static/`: Estilos (CSS), Imágenes y Módulos de Javascript (`js/modules`).
- `requirements.txt`: Dependencias de Python.
- `.env.example`: Plantilla de configuración de variables de entorno.

## 🛠️ Instalación Local

1.  **Clonar el repositorio**:
    ```bash
    git clone https://github.com/juanse2309/proyecto_bujes.git
    cd proyecto_bujes
    ```

2.  **Crear entorno virtual**:
    ```bash
    python -m venv venv
    source venv/bin/scripts/activate  # En Windows: venv\Scripts\activate
    ```

3.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar credenciales**:
    - Renombra `.env.example` a `.env` y completa los valores.
    - Asegúrate de tener el archivo `credentials_apps.json` en la raíz (no se sube al repositorio).

5.  **Ejecutar**:
    ```bash
    python backend/app.py
    ```

## 🌐 Despliegue en Render
La aplicación está configurada para desplegarse automáticamente al hacer push a la rama `main`. Asegúrate de configurar las **Environment Variables** en el panel de Render usando los valores de tu `.env`.

---
*Desarrollado con ❤️ por Juan Sebastian.*
