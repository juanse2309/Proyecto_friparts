import requests
import json

BASE_URL = "http://localhost:5000"

def test_fetch_bom():
    print("--- Testing FETCH BOM for 9430 ---")
    try:
        response = requests.get(f"{BASE_URL}/api/inyeccion/ensamble_desde_producto?codigo=9430")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2))
        
        if data.get('success') and len(data.get('opciones', [])) >= 3:
            print("✅ SUCCESS: Found multiple components for 9430")
        else:
            print("❌ FAILURE: Expected multiple components")
    except Exception as e:
        print(f"Error connecting to backend: {e}")

def test_register_ensamble_multi():
    print("\n--- Testing REGISTER ENSAMBLE with multiple components ---")
    payload = {
        "fecha_inicio": "2026-02-19",
        "responsable": "TEST AGENT",
        "hora_inicio": "10:00",
        "hora_fin": "11:00",
        "codigo_producto": "9430",
        "cantidad_real": 5,
        "cantidad_recibida": 5,
        "pnc": 0,
        "almacen_origen": "P. TERMINADO",
        "almacen_destino": "PRODUCTO ENSAMBLADO",
        "orden_produccion": "TEST-BOM-001",
        "componentes": [
            {"buje_origen": "9430 A", "qty_unitaria": 1},
            {"buje_origen": "9430 B", "qty_unitaria": 1},
            {"buje_origen": "9430 C", "qty_unitaria": 1}
        ]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/ensamble", json=payload)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2))
        
        if data.get('success') and data.get('componentes_descontados') == 3:
            print("✅ SUCCESS: Processed 3 components correctly")
        else:
            print(f"❌ FAILURE: {data.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"Error connecting to backend: {e}")

if __name__ == "__main__":
    test_fetch_bom()
    test_register_ensamble_multi()
