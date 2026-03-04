import os
import json
import gspread
from google.oauth2.service_account import Credentials

# Configuration
GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
CREDENTIALS_PATH = "credentials_apps.json"
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# ── Esquema FINAL de columnas MES en INYECCION (29 columnas totales) ────────
# A-V  (1-22):  Columnas históricas existentes — NO TOCAR
# W    (23):    ESTADO
# X    (24):    ID_PROGRAMACION
# Y    (25):    PRODUCCION_TEORICA
# Z    (26):    PNC_TOTAL
# AA   (27):    PNC_DETALLE
# AB   (28):    PESO_LOTE
# AC   (29):    CALIDAD_RESPONSABLE
# ────────────────────────────────────────────────────────────────────────────
# NOTA IMPORTANTE: La columna P (16) = CANTIDAD REAL ya existe en el histórico.
# CANTIDAD_REAL fue creada erróneamente como col AB en un script anterior.
# Este script la elimina si existe para restaurar el esquema correcto.

MES_COLS = [
    "ESTADO",               # 23 - Estado del ciclo MES
    "ID_PROGRAMACION",      # 24 - FK a PROGRAMACION_INYECCION
    "PRODUCCION_TEORICA",   # 25 - Cierres × Cavidades (INT)
    "PNC_TOTAL",            # 26 - Total de piezas No Conformes (INT)
    "PNC_DETALLE",          # 27 - Detalle JSON de motivos de PNC
    "PESO_LOTE",            # 28 - Peso del lote en kg (FLOAT)
    "CALIDAD_RESPONSABLE",  # 29 - Quién realizó la revisión de calidad
]

def init_db():
    print("Iniciando actualización de esquema MES...")
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPE)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)

    # 1. Crear/Verificar PROGRAMACION_INYECCION
    try:
        ws_prog = ss.worksheet("PROGRAMACION_INYECCION")
        print("✅ Hoja PROGRAMACION_INYECCION ya existe.")
    except gspread.exceptions.WorksheetNotFound:
        print("➕ Creando hoja PROGRAMACION_INYECCION...")
        ws_prog = ss.add_worksheet(title="PROGRAMACION_INYECCION", rows=2000, cols=10)
        headers = [
            "ID_PROGRAMACION", "FECHA_CREACION", "MAQUINA", "CODIGO_PRODUCTO",
            "MOLDE", "CAVIDADES", "ESTADO", "RESPONSABLE_PLANTA", "OBSERVACIONES"
        ]
        ws_prog.update('A1', [headers])
        print("✅ Hoja PROGRAMACION_INYECCION creada con éxito.")

    # 2. Limpiar columna CANTIDAD_REAL duplicada si existe en INYECCION
    ws_iny = ss.worksheet("INYECCION")
    headers_iny = ws_iny.row_values(1)

    # Buscar CANTIDAD_REAL en cualquier posición DESPUÉS de la col 22 (histórico)
    # La col P (índice 15, col 16) es la legítima — solo eliminar duplicados MES
    for col_idx, header in enumerate(headers_iny[22:], start=23):  # buscar desde col 23 en adelante
        if header == "CANTIDAD_REAL":
            print(f"⚠️  Columna duplicada CANTIDAD_REAL encontrada en posición {col_idx}. Eliminando...")
            # Usar la API de Sheets para eliminar la columna (índice 0-based para la request)
            spreadsheet_id = GSHEET_KEY
            sheet_id = ws_iny.id
            body = {
                "requests": [{
                    "deleteDimension": {
                        "range": {
                            "sheetId":    sheet_id,
                            "dimension":  "COLUMNS",
                            "startIndex": col_idx - 1,  # 0-based
                            "endIndex":   col_idx       # exclusive
                        }
                    }
                }]
            }
            ss.batch_update(body)
            print("✅ Columna CANTIDAD_REAL duplicada eliminada.")
            # Refrescar headers tras eliminación
            headers_iny = ws_iny.row_values(1)
            break

    # 3. Agregar columnas MES faltantes al final (Zero-Impact)
    cols_to_add = [col for col in MES_COLS if col not in headers_iny]

    if cols_to_add:
        print(f"➕ Agregando {len(cols_to_add)} columnas a INYECCION: {cols_to_add}")
        ws_iny.add_cols(len(cols_to_add))
        headers_iny = ws_iny.row_values(1)  # Refresh
        current_len = len(headers_iny)
        for i, col in enumerate(cols_to_add):
            ws_iny.update_cell(1, current_len + i + 1, col)
        print("✅ Columnas agregadas con éxito.")
    else:
        print("✅ Todas las columnas MES ya existen en INYECCION.")

    # 4. Validación final
    final_headers = ws_iny.row_values(1)
    print(f"\n=== Esquema MES actualizado correctamente ===")
    print(f"Total columnas: {len(final_headers)}")
    for i, h in enumerate(final_headers[22:], start=23):
        print(f"  Col {i} ({chr(64 + i) if i <= 26 else chr(64 + i // 26) + chr(64 + i % 26 or 26)}): {h}")

if __name__ == "__main__":
    init_db()
