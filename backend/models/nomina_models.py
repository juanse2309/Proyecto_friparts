from dataclasses import dataclass
from typing import Optional
from datetime import date

@dataclass
class RegistroAsistencia:
    fecha: date
    ingreso_real: Optional[str]
    salida_real: Optional[str]
    rol_usuario: Optional[str] = None
    division: Optional[str] = None
