from flask import Blueprint, Response, jsonify
import requests
from functools import lru_cache
import logging

imagenes_bp = Blueprint('imagenes', __name__)
logger = logging.getLogger(__name__)

# Caché en memoria para 1000 imágenes
@lru_cache(maxsize=1000)
def obtener_imagen_google_drive(file_id):
    '''Obtiene imagen de Google Drive con caché en memoria, manejando disclaimers de virus.'''
    try:
        session = requests.Session()
        # Formato de descarga directa que suele ser más estable para el proxy
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = session.get(url, headers=headers, timeout=10, stream=True)
        
        # Si Google pide confirmación por archivo grande/virus (típico en Drive API sin auth)
        if response.status_code == 200 and ("confirm=" in response.text or "download" not in response.headers.get('Content-Disposition', '')):
            import re
            match = re.search(r'confirm=([a-zA-Z0-9_-]+)', response.text)
            if match:
                confirm_token = match.group(1)
                url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
                response = session.get(url, headers=headers, timeout=10, stream=True)

        if response.status_code == 200:
            return response.content, response.headers.get('Content-Type', 'image/jpeg')
        else:
            logger.warning(f"Error al obtener imagen {file_id}: status {response.status_code}")
            return None, None
            
    except Exception as e:
        logger.error(f"Excepción al obtener imagen {file_id}: {str(e)}")
        return None, None

@imagenes_bp.route('/proxy/<file_id>')
def proxy_imagen(file_id):
    '''Endpoint de proxy con caché. Acepta IDs de archivo de Google Drive.'''
    
    if not file_id or len(file_id) < 5:
        return jsonify({'error': 'ID de archivo inválido'}), 400
    
    # Si el ID parece una URL completa (raro pero posible si se pasa mal), intentar extraer el ID
    if 'drive.google.com' in file_id:
        import re
        match = re.search(r'(?:id=|[ /])([a-zA-Z0-9_-]{25,})', file_id)
        if match:
            file_id = match.group(1)

    content, content_type = obtener_imagen_google_drive(file_id)
    
    if content:
        return Response(
            content,
            mimetype=content_type,
            headers={
                'Cache-Control': 'public, max-age=31536000',
                'Access-Control-Allow-Origin': '*'
            }
        )
    else:
        logger.error(f"❌ Proxy falló para file_id: {file_id}")
        return jsonify({'error': 'No se pudo obtener la imagen del servidor de Google'}), 502

@imagenes_bp.route('/limpiar-cache', methods=['POST'])
def limpiar_cache():
    '''Endpoint para limpiar el caché manualmente.'''
    obtener_imagen_google_drive.cache_clear()
    return jsonify({'mensaje': 'Caché limpiado exitosamente'}), 200
