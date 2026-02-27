import sys, os
sys.path.append(os.path.abspath('.'))
from backend.core.database import sheets_client as gc
from backend.config.settings import Hojas
try:
    ws1 = gc.get_worksheet(Hojas.ORDENES_DE_COMPRA)
    with open('debug.txt', 'w') as f:
        f.write(str(ws1.row_values(1)))
except Exception as e:
    with open('debug.txt', 'w') as f:
        f.write(str(e))
