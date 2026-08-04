# -*- coding: utf-8 -*-
import unittest
import os
import json

# Forzar variable de entorno de prueba antes de importar app
os.environ["WO_SYNC_API_KEY"] = "clave_de_prueba_secreta_123"

from backend.app import app

class TestWOSyncRoute(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_recibir_datos_sin_key(self):
        """Debe retornar 401 si no se envía la cabecera X-API-Key"""
        response = self.app.post(
            '/api/wo/recibir_datos',
            data=json.dumps([{"id": 1, "nombre": "Buje Prueba"}]),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data.decode('utf-8'))
        self.assertFalse(data["success"])
        self.assertIn("No autorizado", data["error"])

    def test_recibir_datos_key_incorrecta(self):
        """Debe retornar 401 si se envía una cabecera X-API-Key inválida"""
        headers = {
            'X-API-Key': 'clave_incorrecta_abc'
        }
        response = self.app.post(
            '/api/wo/recibir_datos',
            data=json.dumps([{"id": 1, "nombre": "Buje Prueba"}]),
            content_type='application/json',
            headers=headers
        )
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data.decode('utf-8'))
        self.assertFalse(data["success"])

    def test_recibir_datos_key_correcta_todos_stock_cero(self):
        """
        Debe retornar 400 cuando la key es valida pero TODOS los registros llegan
        sin stock (o en 0): es la pre-auditoria de seguridad de recibir_datos()
        (backend/routes/wo_routes.py) que aborta la sincronizacion a proposito,
        para no sobreescribir inventario_wo real con un reporte vacio/mal
        exportado. Los codigos FR-9304/FR-9305 son productos reales en
        inventario_wo (verificado en BD), por eso este test NO manda un campo
        de stock: no debe llegar nunca al DELETE+INSERT real.
        """
        headers = {
            'X-API-Key': 'clave_de_prueba_secreta_123'
        }
        payload = {
            "nombre_vista": "Vista_Tabla_Inventarios",
            "datos": [
                {"id": 1, "codigo": "FR-9304", "descripcion": "Buje Poliuretano"},
                {"id": 2, "codigo": "FR-9305", "descripcion": "Buje Metalico"}
            ]
        }
        response = self.app.post(
            '/api/wo/recibir_datos',
            data=json.dumps(payload),
            content_type='application/json',
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertFalse(data["success"])
        self.assertIn("saldos son 0", data["error"])

    def test_recibir_datos_fallback_lista(self):
        """Debe retornar 200 y soportar una lista directa por retrocompatibilidad"""
        headers = {
            'X-API-Key': 'clave_de_prueba_secreta_123'
        }
        payload = [
            {"id": 1, "codigo": "FR-9304", "descripcion": "Buje Poliuretano"},
            {"id": 2, "codigo": "FR-9305", "descripcion": "Buje Metalico"}
        ]
        response = self.app.post(
            '/api/wo/recibir_datos',
            data=json.dumps(payload),
            content_type='application/json',
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertTrue(data["success"])
        self.assertEqual(data["recibidos"], 2)
        self.assertEqual(data["nombre_vista"], "Desconocida (Lista directa)")

if __name__ == '__main__':
    unittest.main()
