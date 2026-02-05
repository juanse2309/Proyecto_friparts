import requests
try:
    resp = requests.get("http://localhost:5005/api/obtener_responsables")
    print(resp.json()[:2])
except Exception as e:
    print(e)
