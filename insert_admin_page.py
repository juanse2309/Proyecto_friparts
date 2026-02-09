"""
Script para insertar la página de admin clientes en index.html
"""

def main():
    index_path = r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\templates\index.html'
    admin_page_path = r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\templates\admin_clientes_page.html'
    
    # Leer el HTML de la página de admin
    with open(admin_page_path, 'r', encoding='utf-8') as f:
        admin_html = f.read()
    
    # Leer index.html
    with open(index_path, 'r', encoding='utf-8') as f:
        index_content = f.read()
    
    # Buscar el marcador para insertar (antes de portal-cliente-page o al final de las páginas)
    # Vamos a insertar antes del cierre de #page-content
    marker = '            <!-- PORTAL CLIENTE (Nuevo) -->'
    
    if marker in index_content:
        # Insertar antes del portal cliente
        parts = index_content.split(marker)
        new_content = parts[0] + '\n' + admin_html + '\n\n' + marker + parts[1]
    else:
        # Buscar otro marcador
        marker2 = '        </div>\n    </main>'
        if marker2 in index_content:
            parts = index_content.split(marker2)
            new_content = parts[0] + '\n' + admin_html + '\n' + marker2 + parts[1]
        else:
            print("❌ No se encontró un marcador adecuado")
            return
    
    # Guardar
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Página de admin insertada correctamente en index.html")

if __name__ == '__main__':
    main()
