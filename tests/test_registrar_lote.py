# -*- coding: utf-8 -*-
"""
Tests de caracterización de InyeccionService.registrar_lote, escritos ANTES de
tocar la búsqueda de registro existente (backend/services/inyeccion_service.py,
~línea 311-330): hasta 3 queries secuenciales por item (id_sql -> id_inyeccion+
código -> máquina+responsable+código+fecha+estado) que el hallazgo p6 de la
auditoría pide convertir a una sola query batch. Estos tests fijan el
comportamiento actual (incluida la PRIORIDAD entre los 3 niveles) para que ese
refactor no invierta silenciosamente cuál fila se actualiza.

Corre contra la base de datos real configurada en DATABASE_URL (mismo patrón
que tests/test_wo_sync.py -- no hay BD de staging separada en este proyecto).
Usa id_inyeccion/maquina/id_codigo con el prefijo/valor TEST-AUDIT- o 999999x
para no colisionar con datos reales, y limpia todo lo que crea en tearDown.
"""
import unittest
import os
from datetime import datetime

os.environ.setdefault("WO_SYNC_API_KEY", "clave_de_prueba_secreta_123")

from backend.app import app
from backend.core.sql_database import db
from backend.models.sql_models import ProduccionInyeccion, PncInyeccion
from backend.services.inyeccion_service import InyeccionService

RESPONSABLE_TEST = "TEST AUDIT ROBOT"
MAQUINA_TEST = "TEST-MAQ-AUDIT"


class TestRegistrarLoteBusquedaRegistro(unittest.TestCase):
    """
    Caracteriza la resolución de `registro` en registrar_lote:
    Tier 1: db.session.get(ProduccionInyeccion, id_sql) -- si viene id_sql.
    Tier 2: filter(id_inyeccion == ..., expr_cod == cod_lookup) -- si no hubo id_sql.
    Tier 3: filter(maquina, responsable, expr_cod, fecha, estado='EN_PROCESO') -- último recurso.
    Si ninguno matchea: crea una fila nueva.
    """

    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        self._limpiar()

    def tearDown(self):
        self._limpiar()
        self.ctx.pop()

    def _limpiar(self):
        db.session.query(PncInyeccion).filter(
            PncInyeccion.id_inyeccion.like('TEST-AUDIT-%')
        ).delete(synchronize_session=False)
        db.session.query(ProduccionInyeccion).filter(
            db.or_(
                ProduccionInyeccion.id_inyeccion.like('TEST-AUDIT-%'),
                ProduccionInyeccion.maquina == MAQUINA_TEST,
            )
        ).delete(synchronize_session=False)
        db.session.commit()

    def _payload(self, turno=None, items=None):
        base_turno = {
            "fecha_inicio": "2026-01-15",
            "maquina": MAQUINA_TEST,
            "responsable": RESPONSABLE_TEST,
            "id_inyeccion": "TEST-AUDIT-001",
        }
        if turno:
            base_turno.update(turno)
        base_items = items if items is not None else [{
            "codigo_producto": "9999999",
            "cantidad_real": 10,
            "no_cavidades": 2,
        }]
        return {"turno": base_turno, "items": base_items}

    def test_crea_registro_nuevo_si_no_hay_coincidencia(self):
        data = self._payload()
        resultado = InyeccionService.registrar_lote(data, RESPONSABLE_TEST)
        self.assertTrue(resultado['success'])
        self.assertEqual(len(resultado['items']), 1)

        fila = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion="TEST-AUDIT-001").first()
        self.assertIsNotNone(fila)
        self.assertEqual(fila.maquina, MAQUINA_TEST)
        self.assertEqual(fila.cantidad_real, 10)
        self.assertEqual(fila.estado, 'PENDIENTE')

    def test_actualiza_por_id_sql_tier1(self):
        InyeccionService.registrar_lote(self._payload(), RESPONSABLE_TEST)
        fila = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion="TEST-AUDIT-001").first()
        id_sql_previo = fila.id

        data2 = self._payload(items=[{
            "id_sql": id_sql_previo,
            "codigo_producto": "9999999",
            "cantidad_real": 25,
            "no_cavidades": 2,
        }])
        resultado = InyeccionService.registrar_lote(data2, RESPONSABLE_TEST)
        self.assertTrue(resultado['success'])

        filas = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion="TEST-AUDIT-001").all()
        self.assertEqual(len(filas), 1, "no debio crear una fila nueva, debio actualizar la existente (tier 1)")
        self.assertEqual(filas[0].id, id_sql_previo)
        self.assertEqual(filas[0].cantidad_real, 25)

    def test_actualiza_por_id_inyeccion_y_codigo_tier2(self):
        InyeccionService.registrar_lote(self._payload(), RESPONSABLE_TEST)
        fila = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion="TEST-AUDIT-001").first()
        id_sql_previo = fila.id

        # Reenvio SIN id_sql, mismo id_inyeccion+codigo -> debe encontrar la misma fila (tier 2)
        data2 = self._payload(items=[{
            "codigo_producto": "9999999",
            "cantidad_real": 40,
            "no_cavidades": 2,
        }])
        InyeccionService.registrar_lote(data2, RESPONSABLE_TEST)

        filas = db.session.query(ProduccionInyeccion).filter_by(id_inyeccion="TEST-AUDIT-001").all()
        self.assertEqual(len(filas), 1, "el fallback tier 2 (id_inyeccion+codigo) debio reusar la fila, no crear otra")
        self.assertEqual(filas[0].id, id_sql_previo)
        self.assertEqual(filas[0].cantidad_real, 40)

    def test_actualiza_por_maquina_responsable_fecha_estado_tier3(self):
        # Fila EN_PROCESO preexistente, simulando lo que deja mes_iniciar_trabajo,
        # con un id_inyeccion que el lote entrante NO va a reutilizar.
        registro = ProduccionInyeccion(
            id_inyeccion="TEST-AUDIT-DISTINTO",
            id_codigo="9999998",
            maquina=MAQUINA_TEST,
            responsable=RESPONSABLE_TEST,
            estado="EN_PROCESO",
            fecha_inicia=datetime(2026, 1, 15),
        )
        db.session.add(registro)
        db.session.commit()
        id_sql_previo = registro.id

        data = self._payload(
            turno={"id_inyeccion": "TEST-AUDIT-002"},
            items=[{
                "codigo_producto": "9999998",
                "cantidad_real": 15,
                "no_cavidades": 2,
            }]
        )
        InyeccionService.registrar_lote(data, RESPONSABLE_TEST)

        filas = db.session.query(ProduccionInyeccion).filter(
            ProduccionInyeccion.id_codigo == "9999998"
        ).all()
        self.assertEqual(len(filas), 1, "el fallback tier 3 debio reusar la fila EN_PROCESO existente, no crear otra")
        self.assertEqual(filas[0].id, id_sql_previo)
        self.assertEqual(filas[0].cantidad_real, 15)
        # Comportamiento actual (verificado, no asumido): el bloque de sincronizacion de
        # campos (linea ~351-357) NUNCA reasigna id_inyeccion en un registro existente,
        # solo lo fija una vez al CREAR la fila. Una fila encontrada por tier 2/3 se queda
        # con su id_inyeccion original aunque el lote entrante traiga uno distinto. Un
        # refactor que "corrija" esto sin que sea deliberado rompe la caracterizacion.
        self.assertEqual(filas[0].id_inyeccion, "TEST-AUDIT-DISTINTO", "id_inyeccion NO se reasigna en updates -- solo se fija al crear")

    def test_prioridad_tier2_sobre_tier3(self):
        """
        Si una fila matchea por id_inyeccion+codigo (tier 2) y una fila DISTINTA
        tambien matchearia por maquina+responsable+codigo+fecha+estado (tier 3),
        debe ganar tier 2 -- es la busqueda mas especifica y va primero en el
        codigo actual. Un refactor a batch no puede invertir este orden.
        """
        fila_a_tier3 = ProduccionInyeccion(
            id_inyeccion="TEST-AUDIT-OTRA",
            id_codigo="9999997",
            maquina=MAQUINA_TEST,
            responsable=RESPONSABLE_TEST,
            estado="EN_PROCESO",
            fecha_inicia=datetime(2026, 1, 15),
        )
        fila_b_tier2 = ProduccionInyeccion(
            id_inyeccion="TEST-AUDIT-003",
            id_codigo="9999997",
            maquina=MAQUINA_TEST,
            responsable=RESPONSABLE_TEST,
            estado="PENDIENTE",
            fecha_inicia=datetime(2026, 1, 15),
        )
        db.session.add(fila_a_tier3)
        db.session.add(fila_b_tier2)
        db.session.commit()
        id_fila_a = fila_a_tier3.id
        id_fila_b = fila_b_tier2.id

        data = self._payload(
            turno={"id_inyeccion": "TEST-AUDIT-003"},
            items=[{
                "codigo_producto": "9999997",
                "cantidad_real": 99,
                "no_cavidades": 2,
            }]
        )
        InyeccionService.registrar_lote(data, RESPONSABLE_TEST)

        filas = db.session.query(ProduccionInyeccion).filter(
            ProduccionInyeccion.id_codigo == "9999997"
        ).all()
        self.assertEqual(len(filas), 2, "no debio crear una fila nueva ni fusionar A y B")

        fila_a_final = db.session.get(ProduccionInyeccion, id_fila_a)
        fila_b_final = db.session.get(ProduccionInyeccion, id_fila_b)
        self.assertEqual(fila_a_final.cantidad_real, 0, "la fila candidata a tier 3 (A) NO debio tocarse")
        self.assertEqual(fila_b_final.cantidad_real, 99, "debio actualizar la fila B (tier 2, mas especifica)")

    def test_dos_items_del_mismo_lote_con_mismo_codigo_no_se_autodeduplican(self):
        """
        Caracteriza un caso limite relevante para el batch de p6: si el MISMO
        lote trae dos items que normalizan al mismo id_inyeccion+codigo, el
        codigo actual (queries en vivo por item, con autoflush de SQLAlchemy)
        podria encontrar la fila que el primer item acaba de crear cuando el
        segundo item hace su propia query tier 2. Este test lo confirma o lo
        descarta empiricamente -- un batch que resuelva TODOS los tiers en un
        solo paso ANTES del loop no puede reproducir un comportamiento
        "autorreferencial" como este salvo que lo replique a propósito.
        """
        data = self._payload(items=[
            {"codigo_producto": "9999996", "cantidad_real": 5, "no_cavidades": 1},
            {"codigo_producto": "9999996", "cantidad_real": 7, "no_cavidades": 1},
        ])
        InyeccionService.registrar_lote(data, RESPONSABLE_TEST)

        filas = db.session.query(ProduccionInyeccion).filter_by(id_codigo="9999996").all()
        # CONFIRMADO empiricamente: el codigo actual SI autodedupe -- el
        # autoflush de SQLAlchemy antes de cada query hace que el segundo item
        # encuentre la fila recien creada (sin commit todavia) por el primero.
        # El batch debe reproducir esto a propósito, registrando cada fila
        # resuelta/creada en los mapas de lookup ANTES de procesar el siguiente item.
        self.assertEqual(len(filas), 1, "el lote debio autodeduplicarse a 1 sola fila, como hace el codigo actual")
        self.assertEqual(filas[0].cantidad_real, 7, "el segundo item (misma fila) debio pisar el valor del primero")


if __name__ == '__main__':
    unittest.main()
