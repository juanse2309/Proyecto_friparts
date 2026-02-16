"""
Rutas de productos.
Endpoints REST para operaciones con productos.
"""
from flask import Blueprint, jsonify, request
from backend.services.inventario_service import inventario_service
from backend.repositories.producto_repository import producto_repo
import logging

logger = logging.getLogger(__name__)

productos_bp = Blueprint('productos', __name__)


@productos_bp.route('/detalle/<codigo_sistema>', methods=['GET'])
def detalle_producto(codigo_sistema):
    """Obtiene el detalle completo de un producto."""
    try:
        resultado = inventario_service.obtener_detalle_producto(codigo_sistema)
        
        if resultado["status"] == "success":
            return jsonify(resultado), 200
        else:
            return jsonify(resultado), 404
            
    except Exception as e:
        logger.error(f"Error en endpoint detalle: {e}")
        return jsonify({
            "status": "error",
            "message": "Error interno del servidor"
        }), 500


@productos_bp.route('/buscar/<query>', methods=['GET'])
def buscar_productos(query):
    """Busca productos por código, descripción o OEM."""
    try:
        limite = request.args.get('limite', 20, type=int)
        resultados = producto_repo.buscar_por_termino(query, limite)
        
        productos_formateados = []
        for producto in resultados:
            stock_fisico = int(producto.get('P. TERMINADO', 0) or 0)
            stock_comprometido = int(producto.get('COMPROMETIDO', 0) or 0)
            stock_disponible = stock_fisico - stock_comprometido
            
            productos_formateados.append({
                'codigo_sistema': producto.get('CODIGO SISTEMA', ''),
                'id_codigo': producto.get('ID CODIGO', ''),
                'descripcion': producto.get('DESCRIPCION', ''),
                'stock_fisico': stock_fisico,
                'stock_comprometido': stock_comprometido,
                'stock_disponible': stock_disponible,
                'stock_por_pulir': int(producto.get('POR PULIR', 0) or 0),
                'stock_terminado': int(producto.get('P. TERMINADO', 0) or 0),
                'stock_minimo': int(producto.get('STOCK MINIMO', 10) or 10),
                'imagen': producto.get('IMAGEN', ''),
                'unidad': producto.get('UNIDAD', 'PZ')
            })
        
        return jsonify({
            'status': 'success',
            'resultados': productos_formateados
        }), 200
        
    except Exception as e:
        logger.error(f"Error en búsqueda: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@productos_bp.route('/', methods=['GET'])
def listar_productos():
    """Lista todos los productos con información completa."""
    try:
        productos = producto_repo.listar_todos()
        
        productos_formateados = []
        for p in productos:
            stock_fisico = int(p.get('P. TERMINADO', 0) or 0)
            stock_comprometido = int(p.get('COMPROMETIDO', 0) or 0)
            stock_disponible = stock_fisico - stock_comprometido
            
            productos_formateados.append({
                'codigo_sistema': p.get('CODIGO SISTEMA', ''),
                'id_codigo': p.get('ID CODIGO', ''),
                'descripcion': p.get('DESCRIPCION', ''),
                'stock_fisico': stock_fisico,
                'stock_comprometido': stock_comprometido,
                'stock_disponible': stock_disponible,
                'stock_por_pulir': int(p.get('POR PULIR', 0) or 0),
                'stock_terminado': int(p.get('P. TERMINADO', 0) or 0),
                'stock_ensamblado': int(p.get('PRODUCTO ENSAMBLADO', 0) or 0),
                'stock_minimo': int(p.get('STOCK MINIMO', 10) or 10),
                'imagen': p.get('IMAGEN', ''),
                'categoria': p.get('CATEGORIA', ''),
                'marca': p.get('MARCA', ''),
                'unidad': p.get('UNIDAD', 'PZ'),
                'precio': p.get('PRECIO', 0)
            })
        
        return jsonify({
            'status': 'success',
            'productos': productos_formateados
        }), 200
        
    except Exception as e:
        logger.error(f"Error listando productos: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500