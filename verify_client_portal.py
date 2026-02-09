"""
Script de verificación rápida del Portal de Clientes
"""
import gspread
from google.oauth2.service_account import Credentials

def main():
    print("🔍 VERIFICACIÓN PORTAL DE CLIENTES")
    print("=" * 60)
    
    # Conectar con permisos completos
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file('credentials_apps.json', scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key('1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM')
    
    # 1. Verificar USUARIOS_CLIENTES
    print("\n📋 1. USUARIOS_CLIENTES")
    try:
        ws_users = ss.worksheet('USUARIOS_CLIENTES')
        headers_users = ws_users.row_values(1)
        print(f"   ✅ Hoja encontrada")
        print(f"   Columnas: {headers_users}")
        
        registros = ws_users.get_all_records()
        print(f"   Total usuarios registrados: {len(registros)}")
        if len(registros) > 0:
            print(f"   Ejemplo: {registros[0].get('EMAIL', 'N/A')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 2. Verificar PEDIDOS
    print("\n📦 2. PEDIDOS")
    try:
        ws_pedidos = ss.worksheet('PEDIDOS')
        headers_pedidos = ws_pedidos.row_values(1)
        print(f"   ✅ Hoja encontrada")
        print(f"   Columnas: {headers_pedidos}")
        
        registros = ws_pedidos.get_all_records()
        print(f"   Total pedidos: {len(registros)}")
        
        # Contar pedidos de Portal Web
        portal_orders = [p for p in registros if str(p.get('VENDEDOR', '')).upper() == 'PORTAL WEB']
        print(f"   Pedidos desde Portal Web: {len(portal_orders)}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 3. Verificar CLIENTES (Master List)
    print("\n👥 3. CLIENTES (Lista Maestra)")
    try:
        ws_clientes = ss.worksheet('CLIENTES')
        headers_clientes = ws_clientes.row_values(1)
        print(f"   ✅ Hoja encontrada")
        print(f"   Columnas: {headers_clientes}")
        
        registros = ws_clientes.get_all_records()
        print(f"   Total clientes en lista maestra: {len(registros)}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 4. Verificar PRODUCTOS (para catálogo)
    print("\n📦 4. PRODUCTOS (Catálogo)")
    try:
        ws_productos = ss.worksheet('PRODUCTOS')
        registros = ws_productos.get_all_records()
        print(f"   ✅ Total productos disponibles: {len(registros)}")
        
        # Contar con stock
        con_stock = [p for p in registros if float(str(p.get('P. TERMINADO', 0) or 0).replace(',','')) > 0]
        print(f"   Productos con stock en P. TERMINADO: {len(con_stock)}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Verificación completada")

if __name__ == '__main__':
    main()
