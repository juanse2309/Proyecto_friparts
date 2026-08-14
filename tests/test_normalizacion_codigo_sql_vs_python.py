# -*- coding: utf-8 -*-
"""
Caracteriza si sql_expr_codigo_sin_prefijo_fr() (SQL, usada en el WHERE de
InyeccionService.registrar_lote para tier 2/3) y normalizar_codigo_sin_prefijo()
(Python, usada para construir el valor que se compara contra esa expresion) son
equivalentes para valores reales -- y documenta el caso donde NO lo son.

Por que importa para el batch de p6: si el fix de N+1 llegara a implementarse
trayendo candidatos de la BD y despues filtrando en Python re-normalizando con
normalizar_codigo_sin_prefijo(), ese filtro podria no coincidir con lo que la
query SQL original habria encontrado. La forma segura de evitar el problema
(usada en el batch real) es pedirle a la propia query SQL que devuelva la
expresion ya normalizada como una columna mas (SELECT expr_cod AS cod_norm),
en vez de tratar de replicar su logica en Python -- pero este archivo deja
constancia de POR QUE esa decision de diseno importa, no solo que se tomo.
"""
import unittest
from sqlalchemy import text

from backend.app import app
from backend.core.sql_database import db
from backend.utils.formatters import normalizar_codigo_sin_prefijo


class TestNormalizacionCodigoSqlVsPython(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def _sql_normalizado(self, valor):
        """Evalua la MISMA expresion que sql_expr_codigo_sin_prefijo_fr()
        (backend/utils/formatters.py) pero sobre un literal, sin tocar ninguna tabla."""
        return db.session.execute(
            text("SELECT REPLACE(UPPER(TRIM(:val)), 'FR-', '')"),
            {"val": valor}
        ).scalar()

    def test_equivalen_para_codigos_realistas_con_prefijo_fr(self):
        """Para el universo de codigos real del proyecto (con o sin prefijo FR-/MT-/CAR-/CB-,
        con espacios o mayusculas mixtas) ambas normalizaciones coinciden."""
        casos = [
            "FR-1005", "fr-1005", "  FR-1005  ", "Fr-1005",
            "1005", "  1005  ",
            "MT-5007", "CAR-9890", "CB-100", "DE-42", "HR-7", "KIT-3", "AL-9",
        ]
        for codigo in casos:
            with self.subTest(codigo=codigo):
                self.assertEqual(
                    self._sql_normalizado(codigo),
                    normalizar_codigo_sin_prefijo(codigo),
                    f"SQL y Python divergen para un codigo realista: {codigo!r}"
                )

    def test_divergen_si_fr_guion_aparece_fuera_del_prefijo(self):
        """
        Caracteriza la divergencia real entre ambas normalizaciones: SQL REPLACE
        quita 'FR-' en CUALQUIER posicion de la cadena; Python (normalizar_codigo_sin_prefijo)
        solo la quita si aparece como PREFIJO literal (cod.startswith('FR-')).

        No se confirmo que este caso exista hoy en datos reales de db_inyeccion,
        pero la sola posibilidad es lo que hace insegura una implementacion del
        batch de p6 que "reconstruya" el valor normalizado en Python en vez de
        pedirselo a la propia query SQL como columna calculada.
        """
        codigo = "AB-FR-123"  # 'FR-' en medio de la cadena, no al inicio
        sql_val = self._sql_normalizado(codigo)
        py_val = normalizar_codigo_sin_prefijo(codigo)

        self.assertEqual(sql_val, "AB-123", "SQL quita 'FR-' aunque no este al inicio")
        self.assertEqual(py_val, "AB-FR-123", "Python NO toca el codigo: no empieza con 'FR-'")
        self.assertNotEqual(
            sql_val, py_val,
            "Divergencia confirmada -- el batch de p6 debe leer el valor ya "
            "normalizado por SQL (SELECT expr AS cod_norm), nunca re-derivarlo en Python"
        )


if __name__ == '__main__':
    unittest.main()
