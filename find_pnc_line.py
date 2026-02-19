
filename = r"c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\backend\app.py"
with open(filename, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if "pnc" in line.lower() and "@" in line:
            print(f"{i+1}: {line.strip()}")
        if "/api/pnc" in line:
             print(f"{i+1}: {line.strip()}")
