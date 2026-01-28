import requests
import time

URL = "http://127.0.0.1:5005"

def test_sync():
    print("🔍 Iniciando prueba de sincronización de stock...")
    
    # 1. Obtener productos y buscar uno activo
    res = requests.get(f"{URL}/api/productos/listar")
    if res.status_code != 200:
        print("❌ Error al listar productos")
        return
    
    productos_data = res.json()
    # Si la respuesta es una lista directa, usarla; si es un dict con 'items', extraerlos.
    productos = productos_data.get('items', productos_data) if isinstance(productos_data, dict) else productos_data

    if not productos or len(productos) == 0:
        print("❌ No hay productos para probar")
        return
    
    prod = productos[0]  # Tomamos el primero
    codigo = prod['codigo']
    stock_inicial = prod.get('stock_por_pulir', 0)
    
    print(f"📦 Producto: {codigo}")
    print(f"📊 Stock inicial (POR PULIR): {stock_inicial}")
    
    # 2. Registrar Inyección
    data = {
        "fecha_inicio": "2026-01-27",
        "responsable": "TEST AGENTE",
        "maquina": "MAQ-TEST",
        "codigo_producto": codigo,
        "cantidad_real": 10,
        "no_cavidades": 1,
        "almacen_destino": "POR PULIR",
        "pnc": 0
    }
    
    print(f"🚀 Registrando inyección de 10 piezas para {codigo}...")
    res_post = requests.post(f"{URL}/api/inyeccion", json=data)
    
    if res_post.status_code == 200:
        print("✅ Registro exitoso")
        
        # Esperar un poco para que el cache se invalide (aunque es síncrono en app.py)
        time.sleep(2)
        
        # 3. Verificar nuevo stock
        res_new = requests.get(f"{URL}/api/productos/listar")
        productos_new_data = res_new.json()
        productos_new = productos_new_data.get('items', productos_new_data) if isinstance(productos_new_data, dict) else productos_new_data
        
        prod_new = next((p for p in productos_new if (p.get('codigo') == codigo or p.get('codigo_sistema') == codigo)), None)
        
        if prod_new:
            stock_final = prod_new.get('stock_por_pulir', 0)
            print(f"📊 Stock final (POR PULIR): {stock_final}")
            
            if stock_final == stock_inicial + 10:
                print("🎉 PRUEBA EXITOSA: El stock se actualizó correctamente!")
            else:
                print(f"❌ FALLO: El stock esperado era {stock_inicial + 10}, pero es {stock_final}")
        else:
            print("❌ No se encontró el producto en la segunda carga")
    else:
        print(f"❌ Error en POST: {res_post.text}")

if __name__ == "__main__":
    test_sync()
