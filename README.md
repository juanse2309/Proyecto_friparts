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

---
*Desarrollado con ❤️ por Juan Sebastian.*
