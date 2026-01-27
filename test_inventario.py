"""
Script de prueba para verificar tabla de inventario
"""
import requests
import json

print("=" * 60)
print("PRUEBA DE TABLA DE INVENTARIO")
print("=" * 60)

# 1. Verificar que el servidor esté corriendo
try:
    response = requests.get('http://localhost:5005/api/productos/listar')
    print(f"\n✅ Servidor responde: {response.status_code}")
except Exception as e:
    print(f"\n❌ Error conectando al servidor: {e}")
    exit(1)

# 2. Verificar estructura de datos
data = response.json()
total_productos = len(data.get('items', []))
print(f"✅ Total productos: {total_productos}")

# 3. Verificar que los productos tengan el campo 'imagen'
if total_productos > 0:
    producto_ejemplo = data['items'][0]
    print(f"\n--- Producto de Ejemplo ---")
    print(f"Código: {producto_ejemplo.get('codigo', 'N/A')}")
    print(f"Descripción: {producto_ejemplo.get('descripcion', 'N/A')[:50]}...")
    print(f"Stock Total: {producto_ejemplo.get('existencias_totales', 0)}")
    print(f"Imagen URL: {producto_ejemplo.get('imagen', 'SIN IMAGEN')}")
    print(f"Semáforo: {producto_ejemplo.get('semaforo', {}).get('estado', 'N/A')}")
    
    # 4. Verificar cuántos productos tienen imagen
    con_imagen = sum(1 for p in data['items'] if p.get('imagen'))
    sin_imagen = total_productos - con_imagen
    print(f"\n--- Estadísticas de Imágenes ---")
    print(f"Con imagen: {con_imagen} ({con_imagen/total_productos*100:.1f}%)")
    print(f"Sin imagen: {sin_imagen} ({sin_imagen/total_productos*100:.1f}%)")
    
    # 5. Mostrar URLs de primeras 3 imágenes
    print(f"\n--- Primeras 3 URLs de Imágenes ---")
    count = 0
    for p in data['items']:
        if p.get('imagen') and count < 3:
            print(f"{count+1}. {p['codigo']}: {p['imagen'][:80]}...")
            count += 1

print(f"\n{'=' * 60}")
print("✅ PRUEBA COMPLETADA")
print(f"{'=' * 60}")
