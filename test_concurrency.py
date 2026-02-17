
import threading
import requests
import time

URL = "http://127.0.0.1:5005/api/clientes"

def make_request(i):
    try:
        start = time.time()
        print(f"Hilo {i}: Iniciando solicitud...")
        response = requests.get(URL)
        duration = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else 0
            print(f"✅ Hilo {i}: Éxito ({duration:.2f}s) - {count} clientes")
        else:
            print(f"❌ Hilo {i}: Error {response.status_code} - {response.text[:50]}")
    except Exception as e:
        print(f"💀 Hilo {i}: Excepción - {e}")

threads = []
print("🚀 Iniciando prueba de concurrencia (5 hilos)...")

# Crear 5 hilos simultáneos
for i in range(5):
    t = threading.Thread(target=make_request, args=(i,))
    threads.append(t)
    t.start()

# Esperar a todos
for t in threads:
    t.join()

print("🏁 Prueba finalizada.")
