import urllib.request
import json
import uuid

BASE_URL = "http://127.0.0.1:5005"

def test_mezcla_fix():
    print("\n[TEST] /api/mezcla POST")
    data = {
        "fecha": "2024-01-29",
        "responsable": "TEST_USER",
        "maquina": "TEST_MACHINE",
        "virgen": "100",
        "molido": "50",
        "pigmento": "2",
        "observaciones": "Test automatico Juan Sebastian"
    }
    
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/mezcla",
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            print("Response:", result)
            
            if response.status == 200 and result.get('success'):
                print("✅ Test PASSED: Mezcla saved successfully.")
            else:
                print("❌ Test FAILED: Server returned error.")
                
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.read().decode()}")
    except Exception as e:
        print(f"❌ critical Error: {e}")

if __name__ == "__main__":
    test_mezcla_fix()
