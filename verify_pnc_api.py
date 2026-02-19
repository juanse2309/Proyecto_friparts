
import requests
import datetime
import time

BASE_URL = "http://127.0.0.1:5005"

def test_pnc_fix():
    print("--- Verificando corrección de PNC PULIDO ---")
    
    payload = {
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d"),
        "codigo_producto": "TEST-FIX-GRID",
        "cantidad": 1,
        "criterio": "TEST_EXPANSION",
        "notas": "Verificando fix de grid limits",
        "origen": "pulido" # Aseguramos que vaya a PNC PULIDO si la API lo soporta, o modificamos el endpoint
    }
    
    # El endpoint /api/pnc en app.py parece manejar un parametro 'tipo_proceso' o similar?
    # Revisando app.py (linea 660 aprox), registrar_pnc_detalle recibe "tipo_proceso".
    # Pero el endpoint /api/pnc ¿cómo lo recibe?
    # Necesito ver la ruta /api/pnc en routes/common_routes.py o donde esté definido.
    # Asumiré por ahora que el test_all_modules.py usaba /api/pnc y funcionaba.
    # En test_all_modules.py:
    # pnc_data = { ... }
    # test_module("/api/pnc", pnc_data, "PNC Global")
    
    # Espera... registrar_pnc_detalle toma (tipo_proceso, id_operacion...)
    # ¿Quién llama a registrar_pnc_detalle?
    # Probablemente los endpoints de Inyeccion/Pulido/Ensamble cuando reportan PNC
    # O un endpoint dedicado de PNC.
    
    # Voy a invocar el endpoint de PULIDO (/api/pulido) con PNC > 0.
    # Eso debería disparar registrar_pnc_detalle con tipo_proceso='pulido'.
    
    pulido_payload = {
        "fecha_inicio": datetime.datetime.now().strftime("%Y-%m-%d"),
        "responsable": "TESTER-FIX",
        "hora_inicio": "12:00",
        "hora_fin": "13:00",
        "codigo_producto": "DE-1000",
        "lote": "LOTE-FIX-GRID",
        "cantidad_recibida": 1,
        "cantidad_real": 0,
        "pnc": 1,
        "criterio_pnc": "TEST_EXPANSION_GRID"  # Campo extra si la API lo usa, o notas
    }
    
    url = f"{BASE_URL}/api/pulido"
    print(f"Enviando POST a {url}")
    
    try:
        resp = requests.post(url, json=pulido_payload)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        if resp.status_code in [200, 201]:
            print("✅ Prueba de API exitosa. Verifica los logs del servidor para: '✅ PNC registrado exitosamente... Fila: ...' o mensaje de expansión.")
        else:
            print("❌ Falló la prueba de API.")
            
    except Exception as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    test_pnc_fix()
