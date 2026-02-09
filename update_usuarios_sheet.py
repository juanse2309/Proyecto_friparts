"""
Script para actualizar la estructura de USUARIOS_CLIENTES
Agrega columnas: TELEFONO, DIRECCION, CIUDAD
"""
import gspread
from google.oauth2.service_account import Credentials

def main():
    print("🔧 ACTUALIZANDO ESTRUCTURA DE USUARIOS_CLIENTES")
    print("=" * 60)
    
    # Conectar
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file('credentials_apps.json', scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key('1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM')
    
    # Obtener hoja
    ws = ss.worksheet('USUARIOS_CLIENTES')
    headers = ws.row_values(1)
    
    print(f"\n📋 Columnas actuales:")
    print(f"   {headers}")
    
    # Verificar si ya existen las columnas
    columnas_necesarias = ['TELEFONO', 'DIRECCION', 'CIUDAD']
    columnas_faltantes = [c for c in columnas_necesarias if c not in headers]
    
    if not columnas_faltantes:
        print(f"\n✅ Todas las columnas ya existen. No se requiere actualización.")
        return
    
    print(f"\n⚠️  Columnas faltantes: {columnas_faltantes}")
    print(f"   Agregando al final de la fila de encabezados...")
    
    # Agregar columnas faltantes
    nueva_fila_headers = headers + columnas_faltantes
    ws.update('1:1', [nueva_fila_headers])
    
    print(f"\n✅ Columnas agregadas exitosamente")
    print(f"   Nueva estructura: {nueva_fila_headers}")
    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
