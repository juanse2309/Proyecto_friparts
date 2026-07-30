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


def generar_excel_historial_global(movimientos):
    """
    Construye el Workbook del Historial Global con 3 hojas:
      - 'Historial Completo': todos los movimientos (comportamiento anterior).
      - 'Inyección': solo Tipo == 'INYECCION'.
      - 'Control PNC': solo Tipo == 'PNC' (agrupa Inyección/Pulido/Ensamble,
        que en el DTO ya comparten el mismo Tipo 'PNC' — ver historial_routes.py).
    Devuelve el buffer BytesIO listo para send_file.
    """
    from openpyxl import Workbook
    from io import BytesIO

    columnas = [
        'Fecha', 'Hora Inicio', 'Hora Fin', 'Tipo', 'Responsable',
        'Producto', 'Orden Prod.', 'Máquina', 'Cantidad',
        'Peso Bujes (g)', 'Cavidades', 'Duración (s)', 'Tiempo Total (min)', 'Seg/Unidad',
        'Detalle'
    ]
    anchos = [12, 11, 11, 12, 20, 18, 15, 15, 10, 14, 10, 12, 16, 12, 40]

    wb = Workbook()

    _escribir_hoja_historial(wb.active, "Historial Completo", movimientos, columnas, anchos)

    movimientos_inyeccion = [m for m in movimientos if m.get('Tipo') == 'INYECCION']
    _escribir_hoja_historial(wb.create_sheet("Inyección"), "Inyección", movimientos_inyeccion, columnas, anchos)

    movimientos_pnc = [m for m in movimientos if m.get('Tipo') == 'PNC']
    _escribir_hoja_historial(wb.create_sheet("Control PNC"), "Control PNC", movimientos_pnc, columnas, anchos)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def _escribir_hoja_historial(ws, titulo, movimientos, columnas, anchos):
    """Escribe cabecera en negrita, filas saneadas, cebreado y anchos en una hoja del Historial Global."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    ws.title = titulo

    header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin', color='D5D8DC'),
        right=Side(style='thin', color='D5D8DC'),
        top=Side(style='thin', color='D5D8DC'),
        bottom=Side(style='thin', color='D5D8DC')
    )
    zebra_fill = PatternFill(start_color='F2F3F4', end_color='F2F3F4', fill_type='solid')
    data_align = Alignment(horizontal='center', vertical='center')
    text_align = Alignment(horizontal='left', vertical='center', wrap_text=True)

    for col_idx, titulo_col in enumerate(columnas, 1):
        cell = ws.cell(row=1, column=col_idx, value=titulo_col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    for row_idx, r in enumerate(movimientos, 2):
        fila = [
            r.get('Fecha', ''),
            r.get('HORA_INICIO', ''),
            r.get('HORA_FIN', ''),
            r.get('Tipo', ''),
            r.get('Responsable', ''),
            r.get('Producto', ''),
            r.get('Orden', ''),
            r.get('maquina', 'N/A'),
            r.get('Cant', 0),
            r.get('peso_bujes'),
            r.get('cavidades'),
            r.get('duracion_segundos'),
            r.get('tiempo_total_minutos'),
            r.get('segundos_por_unidad'),
            r.get('Detalle', '')
        ]

        for col_idx, valor in enumerate(fila, 1):
            # Purgar estrictamente cualquier representación de nulo a None para celda vacía en Excel
            if valor is None or (isinstance(valor, float) and (valor != valor)) or str(valor).strip().lower() in ('nan', 'none', 'null'):
                cell_val = None
            else:
                cell_val = valor

            cell = ws.cell(row=row_idx, column=col_idx, value=cell_val)
            cell.border = thin_border

            # Columnas 2 y 3 = Hora Inicio / Hora Fin: forzar formato Texto
            # para que OpenPyXL/Excel nunca reinterprete el string 24h
            # normalizado como una hora 12h dependiente del locale.
            if col_idx in (2, 3):
                cell.number_format = '@'

            if col_idx in (4, 5, 6, 7, 8, 15):
                cell.alignment = text_align
            else:
                cell.alignment = data_align

        if row_idx % 2 == 0:
            for col_idx in range(1, len(columnas) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = zebra_fill

    for i, w in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = 'A2'
