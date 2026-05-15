import os
import json
import logging
from flask import Blueprint, request, jsonify
import google.generativeai as genai
import tempfile
import time

ia_bp = Blueprint('ia_bp', __name__)
logger = logging.getLogger(__name__)

API_KEY = os.environ.get("GOOGLE_API_KEY", "")
if API_KEY:
    genai.configure(api_key=API_KEY)

@ia_bp.route('/api/ia/procesar-audio-ensamble', methods=['POST'])
def procesar_audio_ensamble():
    if not API_KEY:
        return jsonify({'success': False, 'error': 'GOOGLE_API_KEY no configurada en el servidor.'}), 500

    if 'audio' not in request.files:
        return jsonify({'success': False, 'error': 'No se recibió ningún archivo de audio.'}), 400

    audio_file = request.files['audio']
    
    # Guardar en temporal
    fd, temp_path = tempfile.mkstemp(suffix=".webm")
    try:
        with os.fdopen(fd, 'wb') as f:
            audio_file.save(f)

        file_size = os.path.getsize(temp_path)
        logger.info(f"[IA-Voz] Procesando audio en: {temp_path} ({file_size} bytes)")
        
        if file_size == 0:
            return jsonify({'success': False, 'error': 'El archivo de audio recibido está vacío (0 bytes). Verifica el micrófono.'}), 400

        # Subir a Gemini File API con MIME explícito
        uploaded_file = genai.upload_file(path=temp_path, mime_type='audio/webm')
        
        # Espera activa (polling) para asegurar que el archivo esté procesado (ACTIVE)
        logger.info(f"[IA-Voz] Esperando a que el archivo {uploaded_file.name} esté ACTIVE...")
        for _ in range(10):
            file_info = genai.get_file(uploaded_file.name)
            if file_info.state.name == "ACTIVE":
                logger.info(f"[IA-Voz] Archivo listo para ser procesado.")
                break
            elif file_info.state.name == "FAILED":
                logger.error(f"[IA-Voz] Procesamiento fallido en Gemini. Info: {file_info}")
                return jsonify({'success': False, 'error': 'El procesamiento del archivo de audio falló en los servidores de IA.'}), 500
            time.sleep(1)
        else:
            return jsonify({'success': False, 'error': 'Tiempo de espera agotado procesando el audio en la IA.'}), 500
        
        # Preparar instrucciones del sistema
        system_instructions = """
Eres un asistente experto en captura de datos industriales para la plataforma FriParts.
Tu objetivo es escuchar el audio del operario y extraer los siguientes datos al formato JSON estricto.
Solo debes devolver un objeto JSON, sin texto Markdown ni explicaciones.
Campos a extraer:
- id_codigo (String): El código de producto mencionado (Ej: FR-9380).
- cantidad (Number): Cantidad ensamblada.
- responsable (String): Nombre del operario (sólo si lo dice explícitamente, de lo contrario devuelve null).
- op_numero (String): Número de Orden de Producción (OP).
- pnc (Number): Cantidad de piezas malas o no conformes. Si no menciona, es 0.
- hora_inicio (String): Hora de inicio del turno o tarea en formato "HH:MM" (24h).
- hora_fin (String): Hora de finalización del turno o tarea en formato "HH:MM" (24h).
- componentes_seleccionados (String): Si el operario indica que usó todos los componentes o el kit completo, devuelve "TODOS". De lo contrario, describe brevemente o devuelve null.
- observaciones (String): Cualquier comentario extra.
- fecha (String): Formato YYYY-MM-DD. Si no menciona, devuelve null.

Ejemplo de respuesta:
{
  "id_codigo": "FR-9380",
  "cantidad": 50,
  "responsable": "Juan Perez",
  "op_numero": "OP-1234",
  "pnc": 0,
  "hora_inicio": "08:00",
  "hora_fin": "17:00",
  "componentes_seleccionados": "TODOS",
  "observaciones": "Lote completado sin problemas",
  "fecha": null
}
"""
        # Debug: Listar modelos disponibles
        logger.info("[IA-Voz] Verificando modelos disponibles...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                logger.info(f"Modelo disponible: {m.name}")

        model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=system_instructions
        )

        response = model.generate_content(
            [uploaded_file, "Extrae los datos de producción de este audio según las instrucciones y responde ÚNICAMENTE con el objeto JSON."],
            generation_config={"response_mime_type": "application/json"}
        )

        # Opcional: Eliminar el archivo de la API de Gemini para ahorrar cuota
        try:
            uploaded_file.delete()
        except Exception as e:
            logger.warning(f"[IA-Voz] No se pudo borrar archivo remoto: {e}")

        try:
            text_response = response.text.strip()
            # Safety measure against markdown blocks
            if text_response.startswith('```json'):
                text_response = text_response[7:-3]
            elif text_response.startswith('```'):
                text_response = text_response[3:-3]
                
            data = json.loads(text_response)
            
            logger.info(f"[IA-Voz] JSON extraído con éxito: {data}")
            return jsonify({'success': True, 'data': data})
        except json.JSONDecodeError:
            logger.error(f"[IA-Voz] Error decodificando JSON de Gemini: {response.text}")
            return jsonify({'success': False, 'error': 'Respuesta de IA no válida', 'raw': response.text}), 500

    except Exception as e:
        logger.error(f"[IA-Voz] Error procesando audio: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        try:
            os.remove(temp_path)
        except:
            pass
