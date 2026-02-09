"""
Script para agregar mobile.css al index.html
"""

def main():
    index_path = r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\templates\index.html'
    
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Buscar la línea de mobile-ux.css
    old_line = '    <link rel="stylesheet" href="/static/css/mobile-ux.css?v=1.0.0">'
    new_lines = '''    <link rel="stylesheet" href="/static/css/mobile-ux.css?v=1.0.0">
    <link rel="stylesheet" href="/static/css/mobile.css?v=1.0.0">'''
    
    if 'mobile.css' in content:
        print("✅ mobile.css ya está en index.html")
        return
    
    if old_line in content:
        content = content.replace(old_line, new_lines)
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ mobile.css agregado correctamente a index.html")
    else:
        print("❌ No se encontró la línea de mobile-ux.css")

if __name__ == '__main__':
    main()
