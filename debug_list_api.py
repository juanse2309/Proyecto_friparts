
import requests
import json

try:
    print("Solicitando /api/productos/listar...")
    response = requests.get("http://127.0.0.1:5005/api/productos/listar?refresh=true")
    if response.status_code == 200:
        data = response.json()
        items = data.get('items', [])
        print(f"Items recibidos: {len(items)}")
        if items:
            print("Claves del primer item:")
            print(json.dumps(list(items[0].keys()), indent=2))
            print("Primer item (muestra):")
            print(json.dumps(items[0], indent=2))
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print(f"Excepcion: {e}")
