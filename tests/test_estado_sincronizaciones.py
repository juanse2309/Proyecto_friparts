# -*- coding: utf-8 -*-
"""
Tests de /api/wo/estado_sincronizaciones y del helper _sellar_ultima_sync_exitosa
(backend/routes/wo_routes.py) -- hallazgo e8 de la auditoría: los agentes de
cartera/clientes/comercial corren desatendidos cada 15 min y antes no dejaban
ningún rastro consultable de cuándo fue su última sincronización EXITOSA (a
diferencia de inventario_wo, que sí expone su antigüedad vía
/api/wo/inventario/estado desde el hallazgo de "avisa antigüedad del stock WO").

Corre contra la base de datos real (mismo patrón que el resto de tests/),
limpiando las claves TEST-AUDIT- que crea.
"""
import unittest
import os
from datetime import datetime, timedelta

os.environ.setdefault("WO_SYNC_API_KEY", "clave_de_prueba_secreta_123")

from backend.app import app
from backend.core.sql_database import db
from backend.models.sql_models import AppConfig
from backend.routes.wo_routes import (
    _sellar_ultima_sync_exitosa,
    SYNC_EXITOSA_CARTERA_KEY,
    SYNC_EXITOSA_CLIENTES_KEY,
    SYNC_EXITOSA_COMERCIAL_KEY,
)


class TestEstadoSincronizaciones(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True
        self.ctx = app.app_context()
        self.ctx.push()
        self._limpiar()

    def tearDown(self):
        self._limpiar()
        self.ctx.pop()

    def _limpiar(self):
        for clave in (SYNC_EXITOSA_CARTERA_KEY, SYNC_EXITOSA_CLIENTES_KEY, SYNC_EXITOSA_COMERCIAL_KEY):
            registro = db.session.get(AppConfig, clave)
            if registro:
                db.session.delete(registro)
        db.session.commit()

    def test_sin_sesion_devuelve_401(self):
        resp = self.client.get('/api/wo/estado_sincronizaciones')
        self.assertEqual(resp.status_code, 401)

    def test_rol_sin_permiso_devuelve_403(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'test'
            sess['role'] = 'PULIDO'
        resp = self.client.get('/api/wo/estado_sincronizaciones')
        self.assertEqual(resp.status_code, 403)

    def test_admin_sin_datos_devuelve_fecha_nula(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'test-admin'
            sess['role'] = 'ADMIN'
        resp = self.client.get('/api/wo/estado_sincronizaciones')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        for clave in ('cartera', 'clientes', 'comercial'):
            self.assertIsNone(data[clave]['fecha'])
            self.assertIsNone(data[clave]['antiguedad_horas'])

    def test_sellar_y_leer_antiguedad_reciente(self):
        _sellar_ultima_sync_exitosa(SYNC_EXITOSA_CARTERA_KEY)

        with self.client.session_transaction() as sess:
            sess['user'] = 'test-admin'
            sess['role'] = 'ADMIN'
        resp = self.client.get('/api/wo/estado_sincronizaciones')
        data = resp.get_json()

        self.assertIsNotNone(data['cartera']['fecha'])
        # Recién sellado: antigüedad debe ser prácticamente 0, nunca negativa
        # ni de horas -- si esto falla, el cálculo de antigüedad_horas está mal.
        self.assertGreaterEqual(data['cartera']['antiguedad_horas'], 0)
        self.assertLess(data['cartera']['antiguedad_horas'], 0.01)
        # Las otras dos claves siguen sin dato -- sellar una no afecta a las demás.
        self.assertIsNone(data['clientes']['fecha'])
        self.assertIsNone(data['comercial']['fecha'])

    def test_antiguedad_de_una_sync_vieja_se_calcula_en_horas(self):
        vieja = (datetime.now() - timedelta(hours=30)).isoformat()
        db.session.add(AppConfig(clave=SYNC_EXITOSA_CLIENTES_KEY, valor=vieja))
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user'] = 'test-admin'
            sess['role'] = 'ADMIN'
        resp = self.client.get('/api/wo/estado_sincronizaciones')
        data = resp.get_json()

        self.assertAlmostEqual(data['clientes']['antiguedad_horas'], 30, delta=0.1)


if __name__ == '__main__':
    unittest.main()
