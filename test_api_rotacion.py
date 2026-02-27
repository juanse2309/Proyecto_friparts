import requests
import json

def test_api():
    url = "http://localhost:5000/api/rotacion/prioridades"
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        data = response.json()
        if data.get("status") == "success":
            print(f"Total items: {len(data['data'])}")
            # Mostrar los primeros 5 ítems para ver el ordenamiento
            for i, item in enumerate(data['data'][:10]):
                print(f"{i+1}. [{item['clase']}] {item['codigo']} - Stock: {item['stock_actual']}/{item['minimo']} - Semaforo: {item['semaforo']}")
        else:
            print("Error en la respuesta API")
    except Exception as e:
        print(f"Conexión fallida: {e}. ¿Está el backend corriendo?")

if __name__ == "__main__":
    test_api()
