"""
time_utils.py — Fuente única de verdad para timestamps de negocio.

Fallo detectado: el servidor corre con reloj/TimeZone de sesión en UTC. Dos
patrones distintos en el código terminaban guardando la hora equivocada en
columnas `TIMESTAMP WITHOUT TIME ZONE`:

  1. `datetime.now()` (naive) -> captura la hora UTC del sistema tal cual,
     sin aplicar ningún offset de Colombia.
  2. `datetime.now(pytz.timezone('America/Bogota'))` (aware) -> la hora local
     es correcta, pero al insertarse con tzinfo en una columna sin zona
     horaria, Postgres la reconvierte contra el TimeZone de la sesión (UTC)
     y le vuelve a sumar el offset, desfasándola otra vez.

`get_colombia_time()` devuelve un datetime NAIVE que representa la hora de
pared de Bogota (GMT-5): se calcula con zona horaria y luego se le quita el
tzinfo, para que se inserte tal cual en las columnas DateTime naive del
proyecto sin que Postgres vuelva a convertirlo.
"""
from datetime import datetime
import pytz

COLOMBIA_TZ = pytz.timezone('America/Bogota')


def get_colombia_time() -> datetime:
    """Hora actual de Colombia (America/Bogota, GMT-5) como datetime naive.

    Úsese en los servicios como fuente de verdad para cualquier timestamp
    que se vaya a persistir (fecha_registro, hora_inicio, hora_fin, etc.).
    """
    return datetime.now(COLOMBIA_TZ).replace(tzinfo=None)
