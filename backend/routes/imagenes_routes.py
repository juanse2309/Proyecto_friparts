from flask import Blueprint, Response, jsonify
import requests
from functools import lru_cache
import logging

imagenes_bp = Blueprint('imagenes', __name__)
logger = logging.getLogger(__name__)

# Caché en memoria para 1000 imágenes
@lru_cache(maxsize=1000)
def obtener_imagen_google_drive(file_id):
    '''Obtiene imagen de Google Drive con caché en memoria.'''
    try:
        url = f"https://drive.google.com/uc?export=view&id={file_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        
        if response.status_code == 200:
            return response.content, response.headers.get('Content-Type', 'image/jpeg')
        else:
            logger.warning(f"Error al obtener imagen {file_id}: {response.status_code}")
            return None, None
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout al obtener imagen {file_id}")
        return None, None
    except Exception as e:
        logger.error(f"Error al obtener imagen {file_id}: {str(e)}")
        return None, None

@imagenes_bp.route('/proxy/<file_id>')
def proxy_imagen(file_id):
    '''Endpoint de proxy con caché.'''
    
    if not file_id or len(file_id) < 10:
        return jsonify({'error': 'ID de archivo inválido'}), 400
    
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
        return jsonify({'error': 'No se pudo obtener la imagen'}), 504

@imagenes_bp.route('/limpiar-cache', methods=['POST'])
def limpiar_cache():
    '''Endpoint para limpiar el caché manualmente.'''
    obtener_imagen_google_drive.cache_clear()
    return jsonify({'mensaje': 'Caché limpiado exitosamente'}), 200
