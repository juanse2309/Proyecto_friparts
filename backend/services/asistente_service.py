"""
Orquestacion del Asistente de Dashboard.

Flujo: el usuario pregunta en lenguaje natural -> Gemini elige UNA tool entre
las ya validadas para su rol (backend.services.asistente_tools) -> el backend
ejecuta esa tool contra datos reales -> Gemini redacta la respuesta final
sobre esos datos reales.

El LLM nunca genera SQL y nunca recibe la identidad del usuario como
parametro libre: el contexto (user/user_id/role/tenant) siempre lo arma el
backend a partir de la sesion/JWT ya autenticados (ver asistente_routes.py).
"""
import os
import json
import time
import logging
import threading

import google.generativeai as genai
import google.generativeai.protos as genai_protos

from backend.services.asistente_tools import tools_visibles_para_rol, ejecutar_tool
from backend.utils.time_utils import get_colombia_time

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("GOOGLE_API_KEY", "")
if API_KEY:
    genai.configure(api_key=API_KEY)

MODEL_NAME = "gemini-3.1-flash-lite"

SYSTEM_INSTRUCTION = """
Eres el asistente de datos del dashboard de FriTech (fabrica de bujes y componentes plasticos/metalicos).
Reglas estrictas:
1. Para CUALQUIER pregunta que involucre datos (ventas, produccion, calidad, inventario, cartera, nomina),
   DEBES invocar una de las tools disponibles. Nunca inventes cifras ni las calcules de memoria.
2. Si ninguna tool disponible sirve para responder la pregunta, dilo explicitamente en vez de adivinar.
3. Si el usuario pide datos de otra persona, otro vendedor u otro rol al que no tiene acceso, explica
   que no tiene permiso para esa consulta.
4. Responde siempre en espanol, de forma breve y concreta, citando las cifras reales que trajo la tool.
5. No reveles detalles tecnicos internos (nombres de tablas, columnas SQL, nombres de funciones o tools).
6. Puedes usar **negritas** y listas con guiones para enumerar varios items (el chat las
   renderiza correctamente); para una respuesta de un solo dato, prefiere una frase natural
   en vez de una lista de un solo elemento.
7. Si los datos de una tool incluyen cifras de mas de un anio o periodo para el mismo mes o
   concepto (ej. comparativo anio actual vs anio anterior), son totales INDEPENDIENTES para
   comparar entre si -- NUNCA los sumes como si fueran una sola cifra. Responde siempre con
   el valor del periodo/anio que el usuario pidio, no con la suma de varios.
8. Cuando la pregunta lo amerite, invoca 2 o 3 tools relacionadas en el mismo turno (no una
   sola) para dar una respuesta mas completa -- ej. una pregunta de cartera que mencione zonas
   o vendedores debe combinar 'cartera_estado' con 'analitica_comercial'. No inventes una
   relacion entre datos de tools distintas que no comparten una llave real (ej. no asumas que
   el 'vendedor' de una factura de cartera es el mismo que aparece en 'analitica_comercial'
   salvo que el nombre coincida literalmente) -- presenta cada dato con su fuente clara.
9. No te limites a repetir el numero: cuando tengas datos suficientes, agrega una lectura breve
   (que esta subiendo/bajando, que se ve alto o bajo respecto al resto, que cliente/zona/mes
   destaca) siempre y cuando esa lectura se apoye en cifras que SI trajiste, nunca en supuestos.
10. Si preguntan por VENTAS sin especificar si quieren dinero o unidades, reporta AMBAS cifras,
    pero lidera la respuesta con UNIDADES (piezas) -- es lo que mas le interesa a gerencia de
    planta, el dinero facturado va como dato secundario. Si la pregunta especifica claramente
    'facturado', 'plata', 'dinero' o similar, ahi si prioriza el dinero. Nunca omitas una de las
    dos si la tool trajo ambas.
""".strip()

# ── Rate limiting simple, in-memory, por usuario ─────────────────────────────
# Misma limitacion conocida que backend/utils/cache_manager.py: estado local
# del proceso, no sobrevive multiples workers de Gunicorn. Aceptado para v1
# porque el objetivo es acotar costo de API, no seguridad estricta.
_rate_lock = threading.Lock()
_rate_state = {}  # username -> [timestamps de preguntas recientes]
RATE_LIMIT_MAX = 15
RATE_LIMIT_WINDOW_SECONDS = 600


def _rate_limit_excedido(username):
    now = time.time()
    with _rate_lock:
        historial = [t for t in _rate_state.get(username, []) if now - t < RATE_LIMIT_WINDOW_SECONDS]
        if len(historial) >= RATE_LIMIT_MAX:
            _rate_state[username] = historial
            return True
        historial.append(now)
        _rate_state[username] = historial
        return False


def _json_seguro(valor):
    """Normaliza el resultado de una tool (Decimal/date/etc.) a tipos JSON puros
    antes de mandarlo de vuelta a Gemini o al frontend."""
    return json.loads(json.dumps(valor, default=str))


def _construir_tools_gemini(role):
    tools_dict = tools_visibles_para_rol(role)
    if not tools_dict:
        return None
    declarations = [
        {'name': name, 'description': tool['description'], 'parameters': tool['parameters']}
        for name, tool in tools_dict.items()
    ]
    return [{'function_declarations': declarations}]


class AsistenteService:
    @staticmethod
    def responder(pregunta, contexto_dashboard, user, user_id, role, tenant):
        pregunta = (pregunta or '').strip()
        if not pregunta:
            return {'success': False, 'error': 'La pregunta no puede estar vacia.'}

        if not API_KEY:
            return {'success': False, 'error': 'El asistente no esta configurado (falta GOOGLE_API_KEY).'}

        if _rate_limit_excedido(user or 'anon'):
            return {
                'success': False,
                'error': 'Has hecho muchas preguntas seguidas. Espera unos minutos e intenta de nuevo.',
            }

        ctx = {'user': user, 'user_id': user_id, 'role': role, 'tenant': tenant}

        gemini_tools = _construir_tools_gemini(role)
        if not gemini_tools:
            return {'success': False, 'error': 'Tu rol no tiene consultas disponibles en el asistente.'}

        # La empresa opera en hora Colombia (America/Bogota, GMT-5), pero Gemini no
        # tiene forma de saberlo por su cuenta -- sin esto, una pregunta relativa
        # ("este mes", "hoy") sin filtro de fechas activo en el dashboard quedaba
        # a que el modelo ADIVINARA la fecha actual, con riesgo real de desfase
        # (ej. de noche en Colombia ya es "manana" en UTC).
        hoy_colombia = get_colombia_time().strftime('%Y-%m-%d')
        contexto_txt = f"\nFecha de HOY en Colombia (America/Bogota): {hoy_colombia}."
        if contexto_dashboard and contexto_dashboard.get('desde') and contexto_dashboard.get('hasta'):
            contexto_txt += (
                f" El usuario tiene el dashboard filtrado actualmente entre "
                f"{contexto_dashboard['desde']} y {contexto_dashboard['hasta']}. "
                f"Si la pregunta no especifica fechas, usa ese rango."
            )

        try:
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                tools=gemini_tools,
                system_instruction=SYSTEM_INSTRUCTION + contexto_txt,
            )
            chat = model.start_chat()
            response = chat.send_message(pregunta)
        except Exception as e:
            logger.error(f"[Asistente] Error llamando a Gemini: {e}")
            return {'success': False, 'error': 'No fue posible contactar al asistente en este momento.'}

        tool_usado = []
        datos_por_tool = {}
        tipo_grafica = None
        serie_grafica = None
        enlace_sugerido = None

        try:
            parts = response.candidates[0].content.parts
            function_calls = [p.function_call for p in parts if p.function_call and p.function_call.name]

            if function_calls:
                response_parts = []
                for fc in function_calls:
                    nombre = fc.name
                    args = dict(fc.args) if fc.args else {}
                    logger.info(f"[Asistente] user={user} role={role} tool={nombre} args={args}")
                    try:
                        datos, grafica_tool, serie_tool, enlace_tool = ejecutar_tool(nombre, args, ctx)
                        datos = _json_seguro(datos)
                        tool_usado.append(nombre)
                        datos_por_tool[nombre] = datos
                        if grafica_tool and not tipo_grafica:
                            tipo_grafica = grafica_tool
                        if serie_tool and not serie_grafica:
                            serie_grafica = _json_seguro({**serie_tool, 'toolName': nombre})
                        if enlace_tool and not enlace_sugerido:
                            enlace_sugerido = enlace_tool
                        payload = {'result': datos}
                    except PermissionError as e:
                        payload = {'error': str(e)}
                    except ValueError as e:
                        payload = {'error': str(e)}
                    except Exception as e:
                        logger.error(f"[Asistente] Error ejecutando tool '{nombre}': {e}")
                        payload = {'error': 'No fue posible obtener ese dato en este momento.'}

                    response_parts.append(genai_protos.Part(
                        function_response=genai_protos.FunctionResponse(name=nombre, response=payload)
                    ))

                response = chat.send_message(genai_protos.Content(parts=response_parts))

            texto_final = (response.text or '').strip()
        except Exception as e:
            logger.error(f"[Asistente] Error procesando respuesta de Gemini: {e}")
            return {'success': False, 'error': 'El asistente no pudo generar una respuesta.'}

        return {
            'success': True,
            'respuesta': texto_final or 'No tengo una respuesta para esa pregunta.',
            'tool_usado': tool_usado,
            'datos': datos_por_tool,
            'tipo_grafica': tipo_grafica,
            'serie_grafica': serie_grafica,
            'enlace_sugerido': enlace_sugerido,
        }
