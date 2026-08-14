import os
import multiprocessing

# Bind to the port defined by the environment variable PORT, default to 10000
port = os.getenv('PORT', '10000')
bind = f'0.0.0.0:{port}'
bind = "0.0.0.0:" + os.environ.get("PORT", "10000")

# Worker configuration.
# Antes: workers=2, worker_class='sync' -- ese modelo limitaba TODA la app a
# 2 requests concurrentes (cada worker sync atiende uno a la vez) y, al ser
# 2 procesos separados, duplicaba las cachés en memoria del proceso
# (PRODUCTOS_V2_CACHE, NamespaceTTLCache, etc.), haciendo que quedaran
# inconsistentes entre sí tras una invalidación.
# Ahora: 1 worker + varios threads (gthread). Un solo proceso Python = una
# sola copia de cada caché en memoria (se resuelve la inconsistencia sin
# Redis), y los threads permiten atender varios requests I/O-bound (queries
# SQL, llamadas a World Office/Gemini) en paralelo dentro de ese proceso.
# El comentario original decía que 'gthread' era inseguro por compartir un
# cliente gspread/SSL entre threads -- ese cliente ya no existe en el código
# (la app es 100% SQL-Native), así que esa restricción ya no aplica.
# CRITICAL: Render free tier tiene 512MB RAM -- 1 worker con threads usa
# memoria de un solo proceso Python en vez de duplicarla por worker.
workers = 1
worker_class = 'gthread'
threads = 4

# Increase timeout to allow for slow initial connections (e.g. Google Sheets)
timeout = 120
keepalive = 5

# Logging to stdout/stderr
accesslog = '-'
errorlog = '-'
loglevel = 'info'
