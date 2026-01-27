import re
import time

# Leer el archivo HTML
with open('frontend/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Timestamp actual
version = str(int(time.time()))

# Reemplazar todos los scripts de módulos con versión
patterns = [
    (r'src="/static/js/modules/([^"?]+\.js)(\?v=[^"]+)?"', f'src="/static/js/modules/\\1?v={version}"'),
    (r'src="/static/js/app\.js(\?v=[^"]+)?"', f'src="/static/js/app.js?v={version}"'),
]

for pattern, replacement in patterns:
    content = re.sub(pattern, replacement, content)

# Guardar el archivo
with open('frontend/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ Scripts actualizados con versión: {version}")
