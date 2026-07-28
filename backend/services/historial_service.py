import logging
from datetime import datetime, date, time

logger = logging.getLogger(__name__)

# Se intenta primero con AM/PM explicito (para resolver sin ambiguedad textos
# legacy tipo '09:00:00 PM'), y luego con 24 horas (formato ya correcto).
_FORMATOS_HORA_TEXTO = [
    '%I:%M:%S %p', '%I:%M %p',
    '%H:%M:%S', '%H:%M',
]


def _parsear_hora_texto(valor_str):
    """
    Intenta interpretar un string de hora en cualquiera de los formatos conocidos
    (12h con AM/PM o 24h) y devuelve un time() sin ambiguedad.
    Si el string es un '%H:%M' de 12 horas SIN indicador AM/PM (ej. formularios
    legacy que guardaron '09:00'), no existe forma de recuperar si era AM o PM;
    se respeta ese valor como 24h (09:00 = 9 de la mañana), unica lectura valida
    sin informacion adicional.
    """
    valor_str = valor_str.strip()
    if not valor_str:
        return None
    for fmt in _FORMATOS_HORA_TEXTO:
        try:
            return datetime.strptime(valor_str, fmt).time()
        except ValueError:
            continue
    return None


def normalizar_hora_24h(valor):
    """Normaliza cualquier valor de hora (datetime, time o string 12h/24h) a 'HH:MM:SS' en formato militar de 24 horas."""
    if valor is None or valor == '':
        return ''
    if isinstance(valor, datetime):
        return valor.strftime('%H:%M:%S')
    if isinstance(valor, time):
        return valor.strftime('%H:%M:%S')

    hora = _parsear_hora_texto(str(valor))
    if hora is None:
        logger.warning(f"[HistorialService] No se pudo normalizar hora a 24h, se deja el valor original: '{valor}'")
        return str(valor).strip()
    return hora.strftime('%H:%M:%S')


def normalizar_fecha_hora_24h(valor):
    """Normaliza un valor de fecha/hora completo a 'YYYY-MM-DD HH:MM:SS' en formato militar de 24 horas."""
    if valor is None or valor == '':
        return ''
    if isinstance(valor, datetime):
        return valor.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(valor, date):
        return datetime.combine(valor, time.min).strftime('%Y-%m-%d %H:%M:%S')

    valor_str = str(valor).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y %H:%M:%S'):
        try:
            return datetime.strptime(valor_str, fmt).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    return valor_str


def preparar_movimientos_para_excel(movimientos):
    """
    Recibe la lista de movimientos del Historial Global (ya serializados por el
    endpoint principal) y devuelve una copia normalizada para exportacion a Excel:
    los campos de hora quedan estrictamente en formato militar de 24 horas
    (HH:MM:SS), eliminando cualquier ambiguedad AM/PM antes de llegar a OpenPyXL.
    """
    movimientos_excel = []
    for mov in movimientos:
        mov_excel = dict(mov)
        mov_excel['HORA_INICIO'] = normalizar_hora_24h(mov.get('HORA_INICIO'))
        mov_excel['HORA_FIN'] = normalizar_hora_24h(mov.get('HORA_FIN'))
        movimientos_excel.append(mov_excel)
    return movimientos_excel
