"""
Configuración de reglas operativas y horarios para el módulo de nómina.
"""

PERFILES_HORARIO = {
    'ESTANDAR': {
        0: {'inicio': '07:00', 'fin': '17:00', 'deduccion': 60}, # Lunes
        1: {'inicio': '07:00', 'fin': '17:00', 'deduccion': 60}, # Martes
        2: {'inicio': '07:00', 'fin': '17:00', 'deduccion': 60}, # Miércoles
        3: {'inicio': '07:00', 'fin': '17:00', 'deduccion': 60}, # Jueves
        4: {'inicio': '07:00', 'fin': '13:20', 'deduccion': 0},  # Viernes
    },
    'FLEX_1': {
        0: {'inicio': '06:00', 'fin': '15:00', 'deduccion': 20}, # Lunes
        1: {'inicio': '06:00', 'fin': '15:00', 'deduccion': 20}, # Martes
        2: {'inicio': '06:00', 'fin': '15:00', 'deduccion': 20}, # Miércoles
        3: {'inicio': '06:00', 'fin': '15:20', 'deduccion': 20}, # Jueves
        4: {'inicio': '06:00', 'fin': '13:20', 'deduccion': 20}, # Viernes
    }
}

MAPEO_PERFILES = {
    'paola nimisica': 'FLEX_1'
    # El resto caerá en ESTANDAR por defecto. Todas las llaves deben estar en minúsculas.
}
