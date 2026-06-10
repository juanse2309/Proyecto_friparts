# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
import os
import logging

wo_bp = Blueprint('wo', __name__)
logger = logging.getLogger(__name__)

@wo_bp.route('/api/wo/recibir_datos', methods=['POST'])
def recibir_datos():
    """
    Endpoint para recibir datos sincronizados desde el agente local de World Office.
    Verifica el header X-API-Key contra la variable de entorno WO_SYNC_API_KEY.
    """
    # Validar API Key de seguridad
    api_key_header = request.headers.get('X-API-Key')
    api_key_env = os.environ.get('WO_SYNC_API_KEY')
    
    if not api_key_env:
        logger.error("❌ Variable de entorno WO_SYNC_API_KEY no configurada en el servidor.")
        return jsonify({
            "success": False, 
            "error": "Configuración de seguridad incompleta en el servidor"
        }), 500
        
    if api_key_header != api_key_env:
        logger.warning(f"⚠️ Intento de sincronización WO no autorizado. Header X-API-Key: {api_key_header}")
        return jsonify({
            "success": False, 
            "error": "No autorizado. API Key inválida o ausente."
        }), 401

    try:
        payload = request.json
        if payload is None:
            payload = {}

        # Soportar formato envuelto {nombre_vista, datos} y fallback de lista directa
        if isinstance(payload, dict):
            nombre_vista = payload.get("nombre_vista", "Desconocida")
            datos = payload.get("datos", [])
        else:
            nombre_vista = "Desconocida (Lista directa)"
            datos = payload

        if not isinstance(datos, list):
            datos = [datos] if datos else []
            
        logger.info(f"Datos de WO recibidos ({nombre_vista}): {len(datos)} registros")
        
        return jsonify({
            "success": True,
            "message": f"Datos de la vista '{nombre_vista}' recibidos con éxito",
            "recibidos": len(datos),
            "nombre_vista": nombre_vista
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en endpoint recibir_datos de WO: {e}")
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500
