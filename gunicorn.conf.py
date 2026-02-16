import os
import multiprocessing

# Bind to the port defined by the environment variable PORT, default to 10000
port = os.getenv('PORT', '10000')
bind = f'0.0.0.0:{port}'

# Worker configuration (standard formula: 2 * CPUs + 1)
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gthread'
threads = 2

# Increase timeout to allow for slow initial connections (e.g. Google Sheets)
timeout = 120
keepalive = 5

# Logging to stdout/stderr
accesslog = '-'
errorlog = '-'
loglevel = 'info'
