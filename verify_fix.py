import requests
import json

BASE_URL = "http://127.0.0.1:5005"

def verify():
    print("🔍 Verifying Product Fixes...")
    try:
        # Force refresh to ensure we get new logic
        r = requests.get(f"{BASE_URL}/api/productos/listar?refresh=true")
        if r.status_code != 200:
            print(f"❌ Error fetching products: {r.status_code}")
            return
        
        data = r.json()
        items = data.get('items', [])
        
        if not items:
            print("❌ No items returned!")
            return

        print(f"✅ Loaded {len(items)} products.")
        
        # Check IDs
        empty_codes = [p for p in items if not p.get('codigo')]
        if empty_codes:
            print(f"❌ Found {len(empty_codes)} items with empty 'codigo'.")
        else:
            print("✅ All items have 'codigo'.")

        # Check Semaphores
        colors = set()
        for p in items:
            sem = p.get('semaforo', {})
            colors.add(sem.get('color'))
        
        print(f"🎨 Semaphore Colors found: {colors}")
        
        expected = {'green', 'yellow', 'red', 'dark'} # Dark is allowed for <=0 per my code, but handled as red/agotado
        unexpected = colors - expected
        if unexpected:
            print(f"⚠️ Unexpected colors found: {unexpected}")
        else:
            print("✅ Semaphore colors are valid.")

    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    verify()
