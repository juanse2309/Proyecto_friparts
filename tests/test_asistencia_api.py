import urllib.request
import urllib.parse
import json
import time
from datetime import datetime

base_url = "http://127.0.0.1:5005/api/asistencia"

def test_guardar():
    print("--- TEST: Guardar Asistencia ---")
    
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    mock_payload = {
        "registros": [
            {
                "fecha": hoy_str,
                "colaborador": "OPERARIO PRUEBA RBAC",
                "ingreso_real": "06:00",
                "salida_real": "16:00",
                "horas_ordinarias": 8.5,
                "horas_extras": 1.5,
                "registrado_por": "JEFE SISTEMA AUTOMATICO"
            }
        ]
    }
    
    try:
        req = urllib.request.Request(
            f"{base_url}/guardar",
            data=json.dumps(mock_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"Respuesta POST /guardar: {result}")
            return result
    except Exception as e:
        print(f"Error test_guardar: {e}")
        return None

def test_mis_horas():
    print("\n--- TEST: Consultar Mis Horas ---")
    
    colaborador_name = "OPERARIO PRUEBA RBAC"
    try:
        url = f"{base_url}/mis_horas?nombre={urllib.parse.quote(colaborador_name)}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"Respuesta GET /mis_horas:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return result
    except Exception as e:
        print(f"Error test_mis_horas: {e}")
        return None

if __name__ == "__main__":
    print(f"Iniciando pruebas Asistencia (RBAC) a las {datetime.now().strftime('%H:%M:%S')}")
    res_guardar = test_guardar()
    if res_guardar and res_guardar.get('status') == 'success':
        time.sleep(2) # Esperar a Sheets
        test_mis_horas()
