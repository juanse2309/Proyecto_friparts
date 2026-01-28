import requests
import json
import random
import time
from datetime import datetime

BASE_URL = "http://127.0.0.1:5005"

def log(msg, type="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{type}] {msg}")

def get_data(endpoint):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"Error fetching {endpoint}: {e}", "ERROR")
        return None

def run_stress_test():
    log("🚀 INICIANDO TEST DE ESTRÉS PARA POWER BI Y DATA INTEGRITY")
    
    # 1. FETCH METADATA
    log("📥 Recuperando metadatos (Productos, Responsables, Máquinas)...")
    productos = get_data("/api/productos/listar")
    responsables = get_data("/api/obtener_responsables")
    maquinas = get_data("/api/obtener_maquinas")
    
    if not productos or not responsables or not maquinas:
        log("❌ Fallo obteniendo metadatos. Abortando.", "CRITICAL")
        return

    # Validar estructura de productos
    lista_productos = productos.get("items", productos) if isinstance(productos, dict) else productos
    if not lista_productos:
        log("❌ No hay productos en el sistema.", "CRITICAL")
        return

    # Seleccionar datos de prueba
    producto = random.choice(lista_productos)
    responsable = random.choice(responsables) if responsables else "PRUEBA_STR"
    maquina = random.choice(maquinas) if maquinas else "MAQ-TEST"
    
    codigo_prod = producto.get('codigo') or producto.get('codigo_sistema')
    log(f"Test Subject: Producto={codigo_prod}, Resp={responsable}, Maq={maquina}")

    # ==========================================
    # TEST 1: INYECCIÓN (Debe guardar Enteros)
    # ==========================================
    log("🧪 TEST 1: Registro de Inyección...")
    payload_iny = {
        "fecha": datetime.now().strftime('%Y-%m-%d'),
        "responsable": responsable,
        "maquina": maquina,
        "hora_inicio": "08:00",
        "hora_termina": "10:00",
        "codigo_producto": codigo_prod,
        "no_cavidades": 2,          # INT
        "cantidad_real": 100,       # INT (Disparos) -> 200 Total
        "pnc": 10,                  # INT
        "criterio_pnc": "RECHUPE",
        "almacen_destino": "POR PULIR",
        "observaciones": "TEST AUTOMÁTICO - Validar INT en Power BI"
    }
    
    try:
        r = requests.post(f"{BASE_URL}/api/inyeccion", json=payload_iny)
        if r.status_code in [200, 201]:
            log("✅ Inyección guardada correctamente.", "SUCCESS")
        else:
            log(f"❌ Fallo Inyección: {r.text}", "ERROR")
    except Exception as e:
        log(f"❌ Excepción Inyección: {e}", "ERROR")

    # ==========================================
    # TEST 2: PULIDO (Input Enteros)
    # ==========================================
    log("🧪 TEST 2: Registro de Pulido...")
    payload_pul = {
        "fecha_inicio": datetime.now().strftime('%Y-%m-%d'), # FIXED
        "responsable": responsable,
        "hora_inicio": "10:00",
        "hora_fin": "12:00",
        "codigo_producto": codigo_prod,
        "cantidad_recibida": 190,   # INT
        "pnc": 5,                   # INT
        "cantidad_real": 185,       # INT
        "observaciones": "TEST PULIDO INT"
    }

    try:
        r = requests.post(f"{BASE_URL}/api/pulido", json=payload_pul)
        if r.status_code in [200, 201]:
            log("✅ Pulido guardado correctamente.", "SUCCESS")
        else:
            log(f"❌ Fallo Pulido: {r.text}", "ERROR")
    except Exception as e:
        log(f"❌ Excepción Pulido: {e}", "ERROR")

    # ==========================================
    # TEST 3: ENSAMBLE
    # ==========================================
    # Necesitamos un producto que sea ensamble. 
    # El sistema espera 'codigo_producto' como el PRODUCTO FINAL.
    # Dado que no sabemos si 'codigo_prod' es un ensamble o un componente, validacion puede fallar
    # si el sistema busca su buje origen. 
    # Para el test, usaremos 'codigo_prod' como producto final.
    log("🧪 TEST 3: Registro de Ensamble...")
    payload_ens = {
        "fecha_inicio": datetime.now().strftime('%Y-%m-%d'), # FIXED
        "responsable": responsable,
        "hora_inicio": "13:00",
        "hora_fin": "15:00",
        "codigo_producto": f"{codigo_prod}", # FIXED: Espera codigo_producto
        "qty_unitaria": 1,          # Forzar QTY
        "cantidad_recibida": 50,    # Bujes usados
        "cantidad_real": 50,        # Ensambles hechos
        "pnc": 0,
        "observaciones": "TEST ENSAMBLE INT"
    }

    try:
        r = requests.post(f"{BASE_URL}/api/ensamble", json=payload_ens)
        if r.status_code in [200, 201]:
            log("✅ Ensamble guardado correctamente.", "SUCCESS")
        else:
            log(f"❌ Fallo Ensamble: {r.text}", "ERROR")
            # Es posible que falle si codigo_prod no tiene buje configurado, pero validamos payload.
    except Exception as e:
        log(f"❌ Excepción Ensamble: {e}", "ERROR")

    # ==========================================
    # TEST 4: FACTURACIÓN (Resta Stock)
    # ==========================================
    log("🧪 TEST 4: Facturación (Venta)...")
    payload_fac = {
        "fecha_inicio": datetime.now().strftime('%Y-%m-%d'), # FIXED
        "cliente": "CLIENTE TEST",
        "codigo_producto": codigo_prod, # FIXED
        "cantidad_vendida": 10,         # FIXED: cantidad_vendida
        "precio_unitario": 5.50 
    }

    try:
        r = requests.post(f"{BASE_URL}/api/facturacion", json=payload_fac)
        if r.status_code in [200, 201]:
            log("✅ Facturación guardada correctamente.", "SUCCESS")
        else:
            log(f"❌ Fallo Facturación: {r.text}", "ERROR")
    except Exception as e:
        log(f"❌ Excepción Facturación: {e}", "ERROR")
    
    # ==========================================
    # TEST 5: MEZCLA
    # ==========================================
    log("🧪 TEST 5: Registro de Mezcla...")
    payload_mezcla = {
        "fecha": datetime.now().strftime('%Y-%m-%d'),
        "responsable": responsable,
        "maquina": maquina,
        "virgen": 25.5,
        "molido": 10.0,
        "pigmento": 0.5,
        "observaciones": "TEST MEZCLA APIS"
    }
    
    try:
        r = requests.post(f"{BASE_URL}/api/mezcla", json=payload_mezcla)
        if r.status_code in [200, 201]:
            log("✅ Mezcla guardada correctamente.", "SUCCESS")
        else:
            log(f"❌ Fallo Mezcla: {r.text}", "ERROR")
    except Exception as e:
        log(f"❌ Excepción Mezcla: {e}", "ERROR")

    log("🏁 TEST FINALIZADO. Verificar Google Sheets para consistencia.", "INFO")

if __name__ == "__main__":
    run_stress_test()
