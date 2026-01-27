"""
Script para verificar semáforos de productos
"""
import requests
import json

print("=" * 70)
print("DIAGNÓSTICO DE SEMÁFOROS - INVENTARIO")
print("=" * 70)

try:
    response = requests.get('http://localhost:5005/api/productos/listar', timeout=10)
    print(f"\n✅ Servidor responde: {response.status_code}")
    
    data = response.json()
    
    # Verificar estructura
    if 'items' in data:
        productos = data['items']
        print(f"✅ Estructura correcta: {{items: [...]}}")
    elif isinstance(data, list):
        productos = data
        print(f"⚠️  Estructura antigua: lista directa")
    else:
        print(f"❌ Estructura desconocida: {type(data)}")
        exit(1)
    
    print(f"✅ Total productos: {len(productos)}")
    
    # Verificar primer producto
    if productos:
        p = productos[0]
        print(f"\n--- PRIMER PRODUCTO ---")
        print(f"Código: {p.get('codigo', 'SIN CODIGO')}")
        print(f"Descripción: {p.get('descripcion', 'N/A')[:50]}...")
        print(f"Stock Total: {p.get('existencias_totales', 0)}")
        print(f"Stock Mínimo: {p.get('stock_minimo', 0)}")
        print(f"Punto Reorden: {p.get('punto_reorden', 0)}")
        
        if 'semaforo' in p:
            print(f"\n✅ Tiene objeto 'semaforo':")
            print(f"  - Color: {p['semaforo'].get('color', 'N/A')}")
            print(f"  - Estado: {p['semaforo'].get('estado', 'N/A')}")
            print(f"  - Mensaje: {p['semaforo'].get('mensaje', '')}")
        else:
            print(f"\n❌ NO tiene objeto 'semaforo'")
    
    # Buscar FR-9304
    print(f"\n--- BUSCANDO FR-9304 ---")
    p9304 = next((p for p in productos if '9304' in p.get('codigo', '')), None)
    
    if p9304:
        print(f"✅ FR-9304 encontrado:")
        print(f"  Stock: {p9304.get('existencias_totales', 0)}")
        print(f"  Mínimo: {p9304.get('stock_minimo', 0)}")
        print(f"  Reorden: {p9304.get('punto_reorden', 0)}")
        if 'semaforo' in p9304:
            print(f"  Semáforo: {p9304['semaforo'].get('estado')} ({p9304['semaforo'].get('color')})")
        else:
            print(f"  ❌ Sin semáforo")
    else:
        print(f"❌ FR-9304 no encontrado")
    
    # Contar por semáforo
    print(f"\n--- ESTADÍSTICAS DE SEMÁFORO ---")
    if productos and 'semaforo' in productos[0]:
        verde = sum(1 for p in productos if p.get('semaforo', {}).get('color') == 'green')
        amarillo = sum(1 for p in productos if p.get('semaforo', {}).get('color') == 'yellow')
        rojo = sum(1 for p in productos if p.get('semaforo', {}).get('color') == 'red')
        gris = sum(1 for p in productos if p.get('semaforo', {}).get('color') == 'dark')
        print(f"🟢 Stock OK (verde): {verde}")
        print(f"🟡 Por Pedir (amarillo): {amarillo}")
        print(f"🔴 Críticos (rojo): {rojo}")
        print(f"⚫ Agotados (gris): {gris}")
    else:
        print(f"❌ No se puede calcular (sin semáforo)")

except requests.RequestException as e:
    print(f"❌ Error de conexión: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

print(f"\n{'=' * 70}")
