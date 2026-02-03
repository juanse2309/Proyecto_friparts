import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5005"

def test_module(endpoint, payload, name):
    print(f"\n--- Testing {name} ---")
    try:
        response = requests.post(f"{BASE_URL}{endpoint}", json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error testing {name}: {e}")
        return False

def run_tests():
    # 1. Inyección
    inyeccion_data = {
        "fecha_inicio": datetime.now().strftime("%Y-%m-%d"),
        "responsable": "TESTER",
        "maquina": "MAQ-1",
        "hora_inicio": "08:00",
        "hora_fin": "09:00",  # frontend uses hora_termina usually, but registrarInyeccion had hora_termina
        "hora_termina": "09:00",
        "hora_llegada": "07:30",
        "codigo_producto": "TEST-PROD",
        "no_cavidades": 2,
        "disparos": 100,
        "cantidad_real": 195,
        "pnc": 5,
        "almacen_destino": "POR PULIR",
        "codigo_ensamble": "TEST-ENS",
        "peso_vela_maquina": 50,
        "peso_bujes": 45
    }
    test_module("/api/inyeccion", inyeccion_data, "Inyección")

    # 2. Pulido
    pulido_data = {
        "fecha_inicio": datetime.now().strftime("%Y-%m-%d"),
        "responsable": "TESTER",
        "hora_inicio": "09:00",
        "hora_fin": "10:00",
        "codigo_producto": "TEST-PROD",
        "lote": "2026-02-03",
        "cantidad_recibida": 200,
        "cantidad_real": 190,
        "pnc": 10
    }
    test_module("/api/pulido", pulido_data, "Pulido")

    # 3. Ensamble
    ensamble_data = {
        "fecha_inicio": datetime.now().strftime("%Y-%m-%d"),
        "responsable": "TESTER",
        "hora_inicio": "10:00",
        "hora_fin": "11:00",
        "codigo_producto": "TEST-ENS",
        "buje_componente": "TEST-PROD",
        "cantidad_bolsas": 50,
        "qty_unitaria": 2,
        "total_piezas": 100,
        "cantidad_real": 98,
        "pnc": 2
    }
    test_module("/api/ensamble", ensamble_data, "Ensamble")

    # 4. PNC
    pnc_data = {
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "codigo_producto": "TEST-PROD",
        "cantidad": 15,
        "criterio": "RECHUPE",
        "notas": "Smoke test"
    }
    test_module("/api/pnc", pnc_data, "PNC Global")

    # 5. Facturacion
    fact_data = {
        "fecha_inicio": datetime.now().strftime("%Y-%m-%d"),
        "cliente": "CLIENTE-TEST",
        "codigo_producto": "TEST-PROD",
        "cantidad_vendida": 10,
        "precio_unitario": 5000
    }
    test_module("/api/facturacion", fact_data, "Facturación")

    # 6. Mezcla
    mezcla_data = {
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "responsable": "TESTER",
        "maquina": "MEZCLADORA-1",
        "virgen": 25.5,
        "molido": 12.2,
        "pigmento": 500
    }
    test_module("/api/mezcla", mezcla_data, "Mezcla")

if __name__ == "__main__":
    run_tests()
