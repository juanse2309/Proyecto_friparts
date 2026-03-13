import traceback
from backend.core.database import sheets_client as gc

def test_sheet():
    try:
        ws_costos = gc.get_worksheet("DB_COSTOS")
        if not ws_costos:
            print("DB_COSTOS not found")
            return
        vals = ws_costos.get_all_values()
        if vals:
            print("Headers:", vals[0])
            if len(vals) > 1:
                print("Row 1:", vals[1])
    except Exception as e:
        traceback.print_exc()

test_sheet()
