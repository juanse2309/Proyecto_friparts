import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:5005"

def test_listar_productos_refresh():
    print("\n[TEST] /api/productos/listar?refresh=true")
    try:
        url = f"{BASE_URL}/api/productos/listar?refresh=true"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            if isinstance(data, list) and len(data) > 0:
                print("Data type: List")
                print("First item keys:", data[0].keys())
                print("First item sample:", data[0])
            else:
                print("Data received:", data)
    except Exception as e:
        print(f"Error: {e}")

def test_historial_pulido():
    print("\n[TEST] /api/historial-global?tipo=PULIDO")
    try:
        # Assuming there is some data, or at least no error
        url = f"{BASE_URL}/api/historial-global?tipo=PULIDO"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            if data.get('success'):
                items = data.get('data', [])
                print(f"Items count: {len(items)}")
                if items:
                    print("First item:", items[0])
                    # Check specific fields
                    first = items[0]
                    print(f"Orden (should be LOTE/Fecha): {first.get('Orden')}")
                    print(f"Cant (should be BUJES BUENOS): {first.get('Cant')}")
            else:
                print("Failed:", data)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_listar_productos_refresh()
    test_historial_pulido()
