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
Extrae datos de producción FriParts en JSON estricto. Sin texto extra.
Campos:
- id_codigo: SKU (Ej: FR-9380)
- cantidad: Unidades (Número)
- responsable: Nombre o null
- op_numero: Orden de Producción
- pnc: Piezas malas (Número, default 0)
- hora_inicio, hora_fin: "HH:MM"
- componentes_seleccionados: "TODOS" o null
- observaciones: String o null
- fecha: DEBE ser siempre 'YYYY-MM-DD' (Ej: 2026-03-12). Si dice 'hoy', usa la fecha actual.
"""
        # Debug: Listar modelos disponibles
        logger.info("[IA-Voz] Verificando modelos disponibles...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                logger.info(f"Modelo disponible: {m.name}")

        model = genai.GenerativeModel(
            model_name="gemini-3.1-flash-lite",
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
