
from flask import Blueprint, jsonify, request
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import uuid
import datetime
import logging

pedidos_bp = Blueprint('pedidos', __name__)
logger = logging.getLogger(__name__)

@pedidos_bp.route('/api/pedidos/registrar', methods=['POST'])
def registrar_pedido():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Extract fields
        # Orden Columnas (13): ID PEDIDO, FECHA, ID CODIGO, DESCRIPCION, VENDEDOR, CLIENTE, NIT, FORMA DE PAGO, DESCUENTO %, TOTAL, ESTADO, CANTIDAD, PRECIO UNITARIO
        
        fecha = data.get('fecha')
        id_codigo = data.get('id_codigo') # Code of product
        descripcion = data.get('descripcion', '')
        vendedor = data.get('vendedor')
        cliente = data.get('cliente')
        nit = data.get('nit', '') # Optional or derived
        forma_pago = data.get('forma_pago', 'Contado')
        descuento = data.get('descuento', 0)
        cantidad = data.get('cantidad', 0)
        precio_unitario = data.get('precio_unitario', 0)
        
        # Validation
        if not all([fecha, id_codigo, vendedor, cliente, cantidad, precio_unitario]):
            return jsonify({"success": False, "error": "Faltan campos obligatorios"}), 400

        # Calculations
        try:
            cant_float = float(cantidad)
            precio_float = float(precio_unitario)
            desc_float = float(descuento) / 100
            
            subtotal = cant_float * precio_float
            total = subtotal * (1 - desc_float)
            total = round(total, 2)
        except ValueError:
            return jsonify({"success": False, "error": "Error en valores numéricos"}), 400

        # ID Creation
        id_pedido = f"PED-{str(uuid.uuid4())[:8].upper()}"
        estado = "PENDIENTE"

        # Prepare Row
        row = [
            id_pedido,
            fecha,
            id_codigo,
            descripcion,
            vendedor,
            cliente,
            nit,
            forma_pago,
            f"{descuento}%",
            total,
            estado,
            cantidad,
            precio_unitario
        ]

        # Save to Sheets
        ws = sheets_client.get_or_create_worksheet(
            Hojas.PEDIDOS, 
            rows=1000, 
            cols=13
        )
        
        # Check headers if new (lazy check)
        existing_headers = ws.row_values(1)
        expected_headers = [
            "ID PEDIDO", "FECHA", "ID CODIGO", "DESCRIPCION", "VENDEDOR", 
            "CLIENTE", "NIT", "FORMA DE PAGO", "DESCUENTO %", "TOTAL", 
            "ESTADO", "CANTIDAD", "PRECIO UNITARIO"
        ]
        
        if not existing_headers:
             ws.append_row(expected_headers)
        
        ws.append_row(row)
        
        logger.info(f"✅ Pedido registrado: {id_pedido} - {cliente} - ${total}")
        
        return jsonify({
            "success": True, 
            "message": "Pedido registrado exitosamente",
            "id_pedido": id_pedido
        })

    except Exception as e:
        logger.error(f"Error registrando pedido: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
