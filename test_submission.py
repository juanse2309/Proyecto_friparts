import requests
import json
import datetime

BASE_URL = "http://localhost:5005"
TIMESTAMP = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def test_inyeccion():
    print("\n--- TEST INYECCION ---")
    payload = {
        "fecha_inicio": "2026-02-03",
        "maquina": "MAQ-01",
        "responsable": "TESTER",
        "codigo_producto": "TEST-PROD-01",
        "no_cavidades": 4, # Mapeado a 'Cavidades'
        "disparos": 100,
        "cavidades": 4, # Enviaremos ambos por si acaso
        "cantidad_real": 390, # (100 * 4) - 10
        "pnc": 10,
        "observaciones": f"TEST AUTO {TIMESTAMP}"
    }
    
    try:
        url = f"{BASE_URL}/api/inyeccion"
        print(f"POST {url}")
        print("Payload:", json.dumps(payload, indent=2))
        resp = requests.post(url, json=payload)
        print("Status:", resp.status_code)
        print("Response:", resp.text)
        return resp.status_code == 200
    except Exception as e:
        print("Error:", e)
        return False

def test_pulido():
    print("\n--- TEST PULIDO ---")
    payload = {
        "fecha_inicio": "2026-02-03",
        "responsable": "TESTER",
        "codigo_producto": "TEST-PROD-01",
        "cantidad_recibida": "100", 
        "pnc": "5",
        "cantidad_real": "95", 
        "hora_inicio": "08:00",
        "hora_fin": "10:00",
        "orden_produccion": "OP-TEST",
        "lote": "LOTE-TEST",
        "observaciones": f"TEST AUTO {TIMESTAMP}"
    }

    try:
        url = f"{BASE_URL}/api/pulido"
        print(f"POST {url}")
        print("Payload:", json.dumps(payload, indent=2))
        resp = requests.post(url, json=payload)
        print("Status:", resp.status_code)
        print("Response:", resp.text)
        return resp.status_code == 200
    except Exception as e:
        print("Error:", e)
        return False

def test_ensamble():
    print("\n--- TEST ENSAMBLE ---")
    payload = {
        "fecha_inicio": "2026-02-03",
        "responsable": "TESTER",
        "codigo_producto": "TEST-ENS-01",
        "qty_unitaria": 50, # 50 piezas por bolsa
        "cantidad_recibida": 10, # 10 bolsas
        "cantidad_bolsas": 10,
        "total_piezas": 500, # 10 * 50
        "pnc": 20, # 20 malas
        "cantidad_real": 480, # 500 - 20 buenas
        "hora_inicio": "08:00",
        "hora_fin": "10:00",
        "orden_produccion": "OP-TEST",
        "observaciones": f"TEST AUTO {TIMESTAMP}"
    }

    try:
        url = f"{BASE_URL}/api/ensamble"
        print(f"POST {url}")
        print("Payload:", json.dumps(payload, indent=2))
        resp = requests.post(url, json=payload)
        print("Status:", resp.status_code)
        print("Response:", resp.text)
        return resp.status_code == 200
    except Exception as e:
        print("Error:", e)
        return False

if __name__ == "__main__":
    print("INICIANDO PRUEBAS DE INTEGRACIÓN")
    i = test_inyeccion()
    p = test_pulido()
    e = test_ensamble()
    
    print("\nRESUMEN FINAL:")
    print(f"Inyección: {'PASS' if i else 'FAIL'}")
    print(f"Pulido:    {'PASS' if p else 'FAIL'}")
    print(f"Ensamble:  {'PASS' if e else 'FAIL'}")
