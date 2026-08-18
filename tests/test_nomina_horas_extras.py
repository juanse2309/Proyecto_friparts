import os
import sys
from datetime import date

import pytest

sys.path.append(os.getcwd())

from backend.services.nomina_service import ReglasAsistencia, _cache_nombres_usuarios
from backend.models.nomina_models import RegistroAsistencia

COLABORADOR_TEST = "operario_generico"


@pytest.fixture(autouse=True)
def _perfil_estandar_sin_db(monkeypatch):
    """Evita que _resolver_username_colaborador golpee la BD: precarga el
    caché en memoria para que el colaborador de prueba resuelva a perfil
    ESTANDAR sin necesitar sesión/contexto de Flask."""
    monkeypatch.setattr(ReglasAsistencia, "_usuarios_precargados", True)
    _cache_nombres_usuarios[COLABORADOR_TEST] = COLABORADOR_TEST
    yield
    _cache_nombres_usuarios.pop(COLABORADOR_TEST, None)


def _calcular(ingreso, salida, fecha=date(2026, 8, 17)):  # 2026-08-17 = lunes
    dto = RegistroAsistencia(
        fecha=fecha,
        ingreso_real=ingreso,
        salida_real=salida,
        colaborador=COLABORADOR_TEST,
    )
    return ReglasAsistencia.calcular_jornada_y_extras(dto)


def test_retiro_anticipado_no_genera_horas_extras():
    """Llega temprano (06:00) pero se retira 2h antes del cierre oficial (17:00).
    No debe generar horas extras bajo ninguna circunstancia."""
    resultado = _calcular("06:00", "15:00")

    assert resultado["horas_extras"] == 0.0, (
        f"Falso positivo: se otorgaron {resultado['horas_extras']}h extra "
        f"a un operario que se retiró antes de finalizar su jornada oficial."
    )
    assert resultado["horas_ordinarias"] > 0.0


def test_llegada_tardia_no_completa_jornada_no_genera_extras():
    """Llega tarde (11:00) pero su salida coincide con el cierre oficial (17:00).
    Nunca completó las horas ordinarias del día, por lo que no debe haber extras."""
    resultado = _calcular("11:00", "17:00")

    assert resultado["horas_extras"] == 0.0
    assert resultado["horas_ordinarias"] > 0.0


def test_jornada_completa_con_salida_tardia_si_genera_extras():
    """Caso de control: entra a la hora oficial y se queda 1h30 más allá del
    cierre. Debe seguir generando horas extra legítimas (no debe romperse por
    el candado)."""
    resultado = _calcular("07:00", "18:30")

    assert resultado["horas_extras"] == 1.5
    assert resultado["horas_ordinarias"] == 9.0


def test_jornada_exacta_sin_extras():
    """Cumple exactamente la jornada oficial (07:00 a 17:00): 0 extras."""
    resultado = _calcular("07:00", "17:00")

    assert resultado["horas_extras"] == 0.0
    assert resultado["horas_ordinarias"] == 9.0
