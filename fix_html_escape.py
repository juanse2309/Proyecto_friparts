import re

# Read the file
with open(r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\templates\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace escaped HTML characters
content = content.replace('\\u003c', '<')
content = content.replace('\\u003e', '>')

# Write back
with open(r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\templates\index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed escaped HTML characters in index.html")
