import urllib.request
import json

BASE_URL = "http://127.0.0.1:5005"

def test_historial_pulido():
    print("\n[TEST] /api/historial-global?tipo=PULIDO")
    try:
        url = f"{BASE_URL}/api/historial-global?tipo=PULIDO"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            if data.get('success'):
                items = data.get('data', [])
                print(f"Items count: {len(items)}")
                if items:
                    print("First item:", items[0])
                    first = items[0]
                    # Verify mapping
                    print(f"Orden (mapped from LOTE/FECHA): {first.get('Orden')}")
                    print(f"Cant (mapped from BUJES BUENOS): {first.get('Cant')}")
            else:
                print("Failed:", data)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_historial_pulido()
