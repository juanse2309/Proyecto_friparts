import logging
import pyodbc
import os
from sqlalchemy import text
from datetime import datetime
from backend.models.sql_models import Pedido, DistribucionOpPedidos

logger = logging.getLogger(__name__)

def normalizar_llaves_dict(row_dict):
    """
    Parser para normalizar claves del payload/CSV para que reconozca indistintamente 
    variaciones (Sanitización).
    """
    mapped = {}
    for k, v in row_dict.items():
        if not k:
            continue
        key_lower = str(k).lower().strip()
        
        if key_lower in ('direccion', 'dirección', 'direccion_tercero', 'direccin'):
            mapped['direccion'] = v
        elif key_lower in ('forma_pago', 'forma_de_pago', 'formapago'):
            mapped['forma_pago'] = v
        elif key_lower in ('vendedor', 'nombres_tercero_interno', 'vendedor_interno', 'elaborado_vendedor'):
            if 'vendedor' not in mapped or not mapped['vendedor']: # Priorizar si hay multiples
                mapped['vendedor'] = v
        elif key_lower in ('ciudad', 'ciudad_encabezado', 'ciudad_destino'):
            mapped['ciudad'] = v
        elif key_lower in ('nit', 'nit_cliente', 'identificacion_tercero', 'identificacion'):
            mapped['nit'] = v
        elif key_lower in ('observaciones', 'nota', 'nota_cabecera'):
            mapped['observaciones'] = v
        elif key_lower in ('descripcion', 'nota_detalle'):
            mapped['descripcion'] = v
        elif key_lower in ('cliente', 'nombres', 'nombre_tercero_externo'):
            mapped['cliente'] = v
        elif key_lower in ('producto', 'productos', 'id_codigo', 'referencia'):
            mapped['productos'] = v
        else:
            mapped[key_lower] = v
    return mapped

def reiniciar_pedido_wo(id_pedido_numero, db_session):
    """
    Reinicia transaccionalmente un pedido consultando desde World Office,
    borrando los detalles anteriores y dejándolo en 0% de progreso con la 
    cabecera correctamente mapeada.
    """
    id_pedido_str = f"PED-{id_pedido_numero}"
    
    # Configuracion de la base de datos de World Office
    DB_SERVER   = os.environ.get("WO_SERVER", r"SERVERWO\WORLDOFFICE17")
    DB_DATABASE = os.environ.get("WO_DB", "FRIPARTS2021")
    DB_UID      = os.environ.get("WO_USER", "wo_cliente")
    DB_PWD      = os.environ.get("WO_PASSWORD", "wo_cliente")

    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        f"UID={DB_UID};"
        f"PWD={DB_PWD};"
        "Timeout=15;"
    )

    try:
        # Paso 1: Limpieza Transaccional Atómica
        logger.info(f"Limpiando detalles de alistamiento y lineas previas para {id_pedido_str}")
        db_session.query(Pedido).filter(Pedido.id_pedido == id_pedido_str).delete()
        db_session.query(DistribucionOpPedidos).filter(DistribucionOpPedidos.id_pedido == id_pedido_str).delete()
        
        # Paso 2: Re-ingesta Limpia desde WO
        logger.info(f"Conectando a World Office para extraer el pedido {id_pedido_numero}...")
        conn = pyodbc.connect(conn_str, timeout=15)
        cursor = conn.cursor()
        
        # Obtener mapeo
        cursor.execute("SELECT Autonumerico, Codigo_Producto FROM [FRIPARTS2021].[dbo].[Vista_Tabla_Inventarios]")
        mapping = {}
        for row in cursor.fetchall():
            mapping[str(row[0])] = row[1]
            
        # Extraer pedido con todos los metadatos comerciales
        sql = """
            SELECT 
                E.Fecha AS fecha,
                (E.prefijo + '-' + CAST(E.Numero_de_Documento AS VARCHAR)) AS documento,
                E.Nombre_tercero_externo AS nombres,
                E.Nombres_tercero_interno AS vendedor,
                E.Identificacion_Tercero AS nit,
                E.Direccion AS direccion,
                E.Ciudad_Encabezado AS ciudad,
                E.Forma_de_Pago AS forma_pago,
                E.Nota AS observaciones,
                D.Nota AS descripcion,
                D.Producto AS productos,
                CAST(D.Cantidad AS FLOAT) AS cantidad,
                CAST(D.Valor_Unitario AS FLOAT) AS precio_unitario
            FROM [FRIPARTS2021].[dbo].[Vista_Tabla_Encabezados] E
            INNER JOIN [FRIPARTS2021].[dbo].[Vista_Tabla_Movimientos_Inventario] D 
                ON E.Autonumerico = D.Pertenece_A
            WHERE E.Numero_de_Documento = ?
              AND E.Tipo_de_Documento = 'PED'
              AND E.Anulado = 0
              AND D.Cantidad > 0;
        """
        cursor.execute(sql, (id_pedido_numero,))
        columnas = [column[0] for column in cursor.description]
        
        filas = cursor.fetchall()
        if not filas:
            raise Exception(f"No se encontro el pedido {id_pedido_numero} en World Office.")
            
        items_insertados = 0
        hora_actual = datetime.now().strftime('%I:%M %p')
        cabecera_mapeada = None
        
        for row in filas:
            raw_dict = dict(zip(columnas, row))
            item = normalizar_llaves_dict(raw_dict)
            
            prod_id = str(item.get('productos', '')).strip()
            mapped_prod = str(mapping.get(prod_id, prod_id)).strip()
            
            # Formatear el codigo a FR- si es necesario
            if mapped_prod.startswith('9') and not mapped_prod.startswith('FR-'):
                mapped_prod = f"FR-{mapped_prod}"
                
            cantidad = float(item.get('cantidad', 0))
            precio = float(item.get('precio_unitario', 0))
            fecha_str = item.get('fecha')
            try:
                fecha_dt = datetime.strptime(str(fecha_str)[:10], '%Y-%m-%d').date()
            except:
                fecha_dt = datetime.now().date()
            
            if cabecera_mapeada is None:
                cabecera_mapeada = item
                
            # Creacion forzando progreso 0 y estado PENDIENTE con metadatos comerciales completos
            nuevo_registro = Pedido(
                id_pedido=id_pedido_str,
                fecha=fecha_dt,
                hora=hora_actual,
                cliente=str(item.get('cliente') or ''),
                nit=str(item.get('nit') or ''),
                direccion=str(item.get('direccion') or ''),
                ciudad=str(item.get('ciudad') or ''),
                vendedor=str(item.get('vendedor') or ''),
                forma_de_pago=str(item.get('forma_pago') or ''),
                observaciones=str(item.get('observaciones') or ''),
                id_codigo=mapped_prod,
                descripcion=str(item.get('descripcion') or ''),
                cantidad=cantidad,
                precio_unitario=precio,
                total=cantidad * precio,
                estado='PENDIENTE', 
                cant_alistada='0',
                progreso='0%'
            )
            db_session.add(nuevo_registro)
            items_insertados += 1
            
        conn.close()
        
        # Completar la transacción lógica en memoria
        db_session.flush()
        
        return items_insertados, cabecera_mapeada
        
    except Exception as e:
        logger.error(f"Error reiniciando pedido {id_pedido_numero}: {e}")
        db_session.rollback()
        raise e
