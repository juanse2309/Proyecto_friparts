# -*- coding: utf-8 -*-
"""
Hallazgo p9 de la auditoría: el backend tenía dos convenios de respuesta
JSON conviviendo -- ~116 rutas devuelven {'success': True/False, ...} y
~58 devuelven {'status': 'success'/'error', ...}, y el frontend está
dividido en consecuencia (algunos módulos chequean .success, otros
.status === 'success'). Reescribir todo a un solo convenio de una sola vez
habría sido un cambio de contrato de API arriesgado sin auditar antes cada
consumidor del frontend.

En vez de eso, se agregó 'success' como clave ADITIVA (nunca se quitó ni
tocó 'status') en cada respuesta que solo tenía 'status'. Este test es un
análisis estático simple (grep sobre el código fuente, no importa Flask)
que fija esa invariante: cualquier futura respuesta con 'status':
'success'/'error' debe traer también 'success': True/False en la misma
línea. Así, un desarrollador que agregue una ruta nueva con el patrón viejo
lo nota aquí, en vez de que el frontend vuelva a fragmentarse en silencio.
"""
import unittest
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ARCHIVOS_A_VERIFICAR = [
    "backend/routes/admin_routes.py",
    "backend/routes/asistencia_routes.py",
    "backend/routes/auth_routes.py",
    "backend/routes/dashboard_routes.py",
    "backend/routes/facturacion_routes.py",
    "backend/routes/gerencia_routes.py",
    "backend/routes/inventario_routes.py",
    "backend/routes/inyeccion_routes.py",
    "backend/routes/pedidos_routes.py",
    "backend/routes/procura_routes.py",
    "backend/routes/productos_routes.py",
    "backend/routes/programacion_routes.py",
    "backend/routes/wo_routes.py",
    "backend/services/inventario_service.py",
]

PAT_STATUS = re.compile(r"""(['"])status\1\s*:\s*(['"])(success|error)\2""")
PAT_SUCCESS_MISMA_LINEA = re.compile(r"""['"]success['"]\s*:""")


class TestFormatoRespuestaStatusSuccess(unittest.TestCase):
    def test_toda_respuesta_con_status_trae_success_hermano(self):
        # Ventana de +-1 linea: cubre el estilo multilinea ya existente en el
        # repo (p.ej. admin_routes.py:72-73, pedidos_routes.py:313-314) donde
        # 'success' y 'status' son claves CONSECUTIVAS del mismo dict, cada
        # una en su propia linea. No se usa una ventana mas ancha a propósito:
        # una ventana grande generó falsos negativos reales durante el
        # desarrollo de p9 (un 'success' de un jsonify() VECINO no
        # relacionado, 2-3 lineas mas arriba, hacia que el chequeo se
        # saltara por error una respuesta que en realidad seguía sin arreglar).
        infracciones = []
        for rel_path in ARCHIVOS_A_VERIFICAR:
            ruta = os.path.join(RAIZ, rel_path)
            with open(ruta, "r", encoding="utf-8") as f:
                lineas = f.readlines()
            for i, linea in enumerate(lineas):
                if not PAT_STATUS.search(linea):
                    continue
                ventana = lineas[max(0, i - 1): i + 2]
                if not any(PAT_SUCCESS_MISMA_LINEA.search(l) for l in ventana):
                    infracciones.append(f"{rel_path}:{i + 1}: {linea.strip()}")

        self.assertEqual(
            infracciones, [],
            "Respuestas con 'status' sin 'success' hermano (rompe la unificación de p9):\n" + "\n".join(infracciones)
        )


if __name__ == '__main__':
    unittest.main()
