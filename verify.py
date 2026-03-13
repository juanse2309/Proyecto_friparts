import requests
try:
    res=requests.get('http://127.0.0.1:5005/api/dashboard/stats?desde=2026-01-01&hasta=2026-03-31&nocache=1')
    data=res.json()['data']
    print('PNC $:', data['kpis'].get('perdida_calidad_dinero'))
    print('Missing:', len(data['kpis'].get('faltan_costos_pnc', [])))
    print('Missing list:', data['kpis'].get('faltan_costos_pnc', [])[:5])
except Exception as e:
    print(e)
