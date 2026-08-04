"""
Servicio de inventario.
Contiene la lógica de negocio para operaciones de inventario.
"""
import re
import time
from typing import Dict, Tuple, List
from sqlalchemy import text
from backend.core.sql_database import db
from backend.models.sql_models import Molde, FichaMaestra, Producto, ProduccionInyeccion, ProduccionPulido
from backend.repositories.producto_repository import producto_repo
from backend.repositories.inventario_repository import inventario_repo
from backend.core.exceptions import ProductoNoEncontrado, DatosInvalidos, MoldeNoEncontrado, CavidadesExcedidas
from backend.utils.validators import Validator
from backend.utils.formatters import to_int, normalizar_codigo, preservar_o_normalizar_prefijo
import logging

logger = logging.getLogger(__name__)

# Caches de lectura de catálogo de productos, migrados desde app.py tal cual.
# NOTA (hallazgo de migración): `PRODUCTOS_CACHE` y `PRODUCTOS_LISTAR_CACHE` no
# tienen ningún productor que los llene con datos reales en el código actual
# — /api/productos/listar (productos_routes.py) no las usa y crear_producto()
# tampoco invalida nada en la práctica — así que hoy son "caches de mentira"
# (mismo patrón que _mes_cache en el dominio de Programación). Se preservan
# íntegros para no cambiar comportamiento; PRODUCTOS_V2_CACHE sí es real y la
# usa activamente listar_productos_v2().
PRODUCTOS_CACHE_TTL = 300  # igual al CACHE_TTL_MEDIUM que usaba app.py

PRODUCTOS_CACHE = {"data": None, "timestamp": 0}
PRODUCTOS_LISTAR_CACHE = {"data": None, "timestamp": 0}
PRODUCTOS_V2_CACHE = {"data": None, "timestamp": 0}


class InventarioService:
    """Servicio de inventario con lógica de negocio."""
    
    def registrar_entrada(self, datos: Dict) -> Dict:
        """
        Registra una entrada de inventario con validaciones.
        
        Args:
            datos: {
                "codigo_producto": str,
                "cantidad": int,
                "almacen_destino": str,
                "observaciones": str (opcional)
            }
        
        Returns:
            Dict con status y mensaje
        """
        try:
            # Validar campos requeridos
            valido, errores = Validator.validar_requeridos(
                datos, 
                ["codigo_producto", "cantidad", "almacen_destino"]
            )
            if not valido:
                raise DatosInvalidos(errores)
            
            # Validar cantidad
            valido, errores = Validator.validar_cantidad(datos["cantidad"])
            if not valido:
                raise DatosInvalidos(errores)
            
            # Validar almacén
            valido, errores = Validator.validar_almacen(datos["almacen_destino"])
            if not valido:
                raise DatosInvalidos(errores)
            
            # Verificar que el producto existe
            producto = producto_repo.buscar_por_codigo(datos["codigo_producto"])
            if not producto:
                raise ProductoNoEncontrado(datos["codigo_producto"])
            
            # Registrar entrada
            exito, mensaje = inventario_repo.registrar_entrada(
                codigo=datos["codigo_producto"],
                cantidad=int(datos["cantidad"]),
                almacen=datos["almacen_destino"]
            )
            
            if exito:
                return {
                    "status": "success",
                    "message": mensaje,
                    "producto": {
                        "codigo": producto.get("CODIGO SISTEMA"),
                        "descripcion": producto.get("DESCRIPCION")
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": mensaje
                }
                
        except (DatosInvalidos, ProductoNoEncontrado) as e:
            logger.error(f"Error en entrada: {e.mensaje}")
            return {
                "status": "error",
                "message": e.mensaje
            }
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return {
                "status": "error",
                "message": "Error interno del servidor"
            }
    
    def registrar_salida(self, datos: Dict) -> Dict:
        """
        Registra una salida de inventario con validaciones.
        
        Args:
            datos: {
                "codigo_producto": str,
                "cantidad": int,
                "almacen_origen": str,
                "observaciones": str (opcional)
            }
        
        Returns:
            Dict con status y mensaje
        """
        try:
            # Validar campos requeridos
            valido, errores = Validator.validar_requeridos(
                datos, 
                ["codigo_producto", "cantidad", "almacen_origen"]
            )
            if not valido:
                raise DatosInvalidos(errores)
            
            # Validar cantidad
            valido, errores = Validator.validar_cantidad(datos["cantidad"])
            if not valido:
                raise DatosInvalidos(errores)
            
            # Validar almacén
            valido, errores = Validator.validar_almacen(datos["almacen_origen"])
            if not valido:
                raise DatosInvalidos(errores)
            
            # Verificar que el producto existe
            producto = producto_repo.buscar_por_codigo(datos["codigo_producto"])
            if not producto:
                raise ProductoNoEncontrado(datos["codigo_producto"])
            
            # Registrar salida
            exito, mensaje = inventario_repo.registrar_salida(
                codigo=datos["codigo_producto"],
                cantidad=int(datos["cantidad"]),
                almacen=datos["almacen_origen"]
            )
            
            if exito:
                return {
                    "status": "success",
                    "message": mensaje,
                    "producto": {
                        "codigo": producto.get("CODIGO SISTEMA"),
                        "descripcion": producto.get("DESCRIPCION")
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": mensaje
                }
                
        except (DatosInvalidos, ProductoNoEncontrado) as e:
            logger.error(f"Error en salida: {e.mensaje}")
            return {
                "status": "error",
                "message": e.mensaje
            }
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return {
                "status": "error",
                "message": "Error interno del servidor"
            }
    
    def obtener_detalle_producto(self, codigo: str) -> Dict:
        """
        Obtiene el detalle completo de un producto con stock.
        
        Args:
            codigo: Código del producto
        
        Returns:
            Dict con información del producto
        """
        try:
            producto = producto_repo.buscar_por_codigo(codigo)
            if not producto:
                raise ProductoNoEncontrado(codigo)
            
            # Calcular stock total
            stock_por_pulir = producto_repo.obtener_stock(codigo, "POR PULIR")
            stock_terminado = producto_repo.obtener_stock(codigo, "P. TERMINADO")
            stock_ensamblado = producto_repo.obtener_stock(codigo, "PRODUCTO ENSAMBLADO")
            stock_comprometido = to_int(producto.get("COMPROMETIDO", 0))
            stock_disponible = stock_terminado - stock_comprometido
            stock_cliente = producto_repo.obtener_stock(codigo, "CLIENTE")
            
            stock_total = stock_por_pulir + stock_terminado + stock_ensamblado
            
            return {
                "status": "success",
                "producto": {
                    "codigo_sistema": producto.get("CODIGO SISTEMA"),
                    "id_codigo": producto.get("ID CODIGO"),
                    "descripcion": producto.get("DESCRIPCION"),
                    "descripcion_larga": producto.get("DESCRIPCION LARGA", ""),
                    "marca": producto.get("MARCA", ""),
                    "categoria": producto.get("CATEGORIA", ""),
                    "stock_total": stock_total,
                    "stock_por_pulir": stock_por_pulir,
                    "stock_terminado": stock_terminado,
                    "stock_comprometido": stock_comprometido,
                    "stock_disponible": stock_disponible,
                    "stock_ensamblado": stock_ensamblado,
                    "stock_cliente": stock_cliente,
                    "stock_minimo": int(producto.get("STOCK MINIMO", 10) or 10),
                    "imagen": producto.get("IMAGEN", ""),
                    "activo": True
                }
            }
            
        except ProductoNoEncontrado as e:
            return {
                "status": "error",
                "message": e.mensaje
            }
        except Exception as e:
            logger.error(f"Error obteniendo detalle: {e}")
            msg = str(e) if "Servidor saturado" in str(e) else "Error interno del servidor"
            return {
                "status": "error",
                "message": msg
            }

    # ------------------------------------------------------------------
    # Catálogo / Fichas / Moldes / Cache — migrado desde backend/app.py
    # ------------------------------------------------------------------

    @staticmethod
    def obtener_ficha_tecnica(id_codigo: str) -> Dict:
        """
        Traduce id_codigo al código real del sistema y resuelve el buje de
        origen y la cantidad unitaria desde FichaMaestra. Nunca lanza: ante
        cualquier error responde con el mismo id_codigo de entrada como
        fallback (comportamiento heredado de app.py).
        """
        try:
            codigo_sis = normalizar_codigo(id_codigo)
            ficha = FichaMaestra.query.filter(FichaMaestra.producto.ilike(f"%{codigo_sis}%")).first()
            if ficha:
                buje_origen = str(ficha.subproducto).strip()
                qty_unitaria = float(ficha.cantidad or 1)
            else:
                buje_origen, qty_unitaria = codigo_sis, 1.0

            return {"buje_origen": buje_origen, "qty_unitaria": qty_unitaria, "codigo_sistema": codigo_sis}
        except Exception as e:
            logger.error(f"Error en InventarioService.obtener_ficha_tecnica: {e}")
            return {"buje_origen": id_codigo, "qty_unitaria": 1, "codigo_sistema": id_codigo}

    @staticmethod
    def obtener_producto_resumen(codigo: str) -> Dict:
        """
        Traduce el código y devuelve codigoSistema/codigoEnsamble para un producto.
        NOTA: `codigoEnsamble` se preserva vacío a propósito — el lookup legacy del
        que viene esta ruta nunca incluyó esa clave en su diccionario de resultados,
        así que en producción esa clave siempre fue "" (comportamiento heredado, no
        una regresión de esta migración).
        """
        codigo_norm = normalizar_codigo(codigo)
        producto = Producto.query.filter(
            (Producto.codigo_sistema == codigo_norm) | (Producto.id_codigo == codigo_norm)
        ).first()
        if not producto:
            raise ProductoNoEncontrado(codigo_norm)
        return {"codigoSistema": producto.codigo_sistema, "codigoEnsamble": ""}

    @staticmethod
    def obtener_moldes_activos() -> List[Dict]:
        """Lista de moldes activos, ordenados por nombre."""
        moldes = db.session.query(Molde).filter(Molde.activo == True).order_by(Molde.nombre).all()
        return [{
            'id': m.id,
            'nombre': m.nombre,
            'cavidades_max': m.cavidades_max,
            'descripcion': m.descripcion
        } for m in moldes]

    @staticmethod
    def validar_molde(nombre_molde: str, cavidades: int) -> None:
        """Valida que las cavidades solicitadas no superen el máximo del molde."""
        molde = db.session.query(Molde).filter(Molde.nombre == nombre_molde).first()
        if not molde:
            raise MoldeNoEncontrado(nombre_molde)
        if cavidades > molde.cavidades_max:
            raise CavidadesExcedidas(nombre_molde, molde.cavidades_max)

    @staticmethod
    def obtener_fichas_tecnicas() -> List[Dict]:
        """Todas las fichas técnicas (nueva_ficha_maestra)."""
        fichas_db = FichaMaestra.query.all()
        return [{
            'id_codigo': f.producto,
            'buje_ensamble': f.subproducto or '',
            'qty': float(f.cantidad or 1)
        } for f in fichas_db]

    @staticmethod
    def _calcular_metricas_semaforo(stock_total, p_min, p_reorden, p_max) -> Dict:
        """Reglas de colores del inventario: green/yellow/red/dark (NO success/danger/warning)."""
        tiene_config = (p_max is not None and p_max > 0 and p_max != 999999)

        if stock_total <= 0:
            estado, color, mensaje = "AGOTADO", "dark", "Sin Stock"
        elif stock_total <= (p_reorden or 0):
            estado, color, mensaje = "CRÍTICO", "red", f"Bajo Punto Reorden ({p_reorden})"
        elif stock_total < (p_min or 0):
            estado, color, mensaje = "POR PEDIR", "yellow", f"Bajo Mínimo ({p_min})"
        else:
            estado, color, mensaje = "STOCK OK", "green", "Stock Saludable"

        if not tiene_config and stock_total > 0:
            mensaje = ""

        return {"estado": estado, "color": color, "mensaje": mensaje, "configurado": tiene_config}

    @staticmethod
    def _corregir_url_imagen(url) -> str:
        """Convierte URLs de Google Drive o IDs sueltos al formato de proxy `/imagenes/proxy/<id>`."""
        if not url:
            return ''
        url = str(url).strip()

        if '/imagenes/proxy/' in url:
            return url
        if (url.endswith('.jpg') or url.endswith('.png') or url.endswith('.jpeg') or
                url.startswith('/imagenes/') or url.startswith('imagenes/')):
            return ''

        file_id = None
        if 'id=' in url:
            match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
            if match:
                file_id = match.group(1)
        elif 'drive.google.com' in url:
            match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
            if match:
                file_id = match.group(1)
        elif len(url) > 15 and not url.startswith('http') and not url.startswith('/') and '.' not in url:
            file_id = url

        if file_id:
            return f"/imagenes/proxy/{file_id}"
        return url

    @staticmethod
    def listar_productos_v2() -> List[Dict]:
        """Catálogo de inventario con semáforos, con cache en memoria de PRODUCTOS_CACHE_TTL segundos."""
        current_time = time.time()
        if PRODUCTOS_V2_CACHE["data"] and (current_time - PRODUCTOS_V2_CACHE["timestamp"] < PRODUCTOS_CACHE_TTL):
            return PRODUCTOS_V2_CACHE["data"]

        productos_sql = producto_repo.get_productos_all()

        lista_final = []
        filas_corruptas = 0
        for p in productos_sql:
            try:
                def _sf(v):
                    try:
                        return float(v or 0)
                    except Exception:
                        return 0.0

                terminado = _sf(p.get('P. TERMINADO', p.get('p_terminado', 0)))
                por_pulir = _sf(p.get('POR PULIR', p.get('por_pulir', 0)))
                comprometido = _sf(p.get('COMPROMETIDO', p.get('comprometido', 0)))

                p_min = _sf(p.get('STOCK MINIMO', p.get('stock_minimo', 0)))
                p_reorden = _sf(p.get('PUNTO REORDEN', p.get('punto_reorden', 0)))
                p_max = _sf(p.get('STOCK MAXIMO', p.get('stock_maximo', 100))) or 100

                stock_global = (terminado + por_pulir) - comprometido
                semaforo = InventarioService._calcular_metricas_semaforo(stock_global, p_min, p_reorden, p_max)

                lista_final.append({
                    "codigo": p.get('CODIGO SISTEMA', p.get('codigo_sistema', '')),
                    "id_codigo": p.get('ID CODIGO', p.get('id_codigo', '')),
                    "descripcion": p.get('DESCRIPCION', p.get('descripcion', '')),
                    "imagen": InventarioService._corregir_url_imagen(str(p.get('IMAGEN', p.get('imagen', '')) or '')),
                    "precio": _sf(p.get('PRECIO', p.get('precio', 0))),
                    "stock_por_pulir": por_pulir,
                    "stock_terminado": terminado,
                    "stock_comprometido": comprometido,
                    "stock_disponible": terminado - comprometido,
                    "existencias_totales": terminado + por_pulir,
                    "metricas": {"min": p_min, "max": p_max, "reorden": p_reorden},
                    "semaforo": semaforo
                })
            except Exception as e_fila:
                filas_corruptas += 1
                codigo_err = p.get('CODIGO SISTEMA', p.get('codigo_sistema', '?')) if isinstance(p, dict) else '?'
                logger.error(f"[listar_v2] Fila corrupta ignorada ({codigo_err}): {e_fila}")
                continue

        if filas_corruptas:
            logger.warning(f"[listar_v2] {filas_corruptas} filas ignoradas por datos corruptos. Ver logs anteriores.")

        PRODUCTOS_V2_CACHE["data"] = lista_final
        PRODUCTOS_V2_CACHE["timestamp"] = current_time
        return lista_final

    @staticmethod
    def crear_producto(id_codigo: str, codigo_sistema_raw: str, descripcion: str, precio, stock_inicial) -> None:
        """Registra un nuevo producto en db_productos."""
        try:
            id_codigo = str(id_codigo or '').strip().upper()
            codigo_sistema = preservar_o_normalizar_prefijo(codigo_sistema_raw or id_codigo)
            descripcion = str(descripcion or '').strip()

            if not id_codigo or not descripcion:
                raise ValueError("ID Código y Descripción son obligatorios")

            db.session.add(Producto(
                id_codigo=id_codigo,
                codigo_sistema=codigo_sistema,
                descripcion=descripcion,
                precio=precio,
                p_terminado=stock_inicial
            ))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            if not isinstance(e, ValueError):
                logger.error(f"Error en InventarioService.crear_producto: {e}")
            raise

    @staticmethod
    def invalidar_cache_productos() -> None:
        """Limpia el cache de /api/productos/listar (comportamiento heredado: solo PRODUCTOS_LISTAR_CACHE)."""
        PRODUCTOS_LISTAR_CACHE["data"] = None
        PRODUCTOS_LISTAR_CACHE["timestamp"] = 0
        logger.info("♻️ Cache de productos invalidado.")

    @staticmethod
    def obtener_estado_cache() -> Dict:
        """Estado de PRODUCTOS_CACHE (nunca poblada por ningún productor real — ver nota de módulo)."""
        ahora = time.time()
        tiempo_transcurrido = ahora - PRODUCTOS_CACHE["timestamp"]
        restante = max(0, PRODUCTOS_CACHE_TTL - tiempo_transcurrido)
        return {
            'data_presente': PRODUCTOS_CACHE["data"] is not None,
            'timestamp': PRODUCTOS_CACHE["timestamp"],
            'tiempo_transcurrido': round(tiempo_transcurrido, 1),
            'ttl_restante': round(restante, 1),
            'ttl_total': PRODUCTOS_CACHE_TTL,
            'vencido': tiempo_transcurrido > PRODUCTOS_CACHE_TTL
        }

    @staticmethod
    def limpiar_cache_productos() -> None:
        """Limpia PRODUCTOS_CACHE manualmente."""
        PRODUCTOS_CACHE["data"] = None
        PRODUCTOS_CACHE["timestamp"] = 0

    @staticmethod
    def obtener_historial_producto(codigo: str) -> Dict:
        """Historial de movimientos (Inyección + Pulido + Ventas) de un producto."""
        codigo_norm = normalizar_codigo(codigo)
        movimientos = []

        iny = ProduccionInyeccion.query.filter_by(id_codigo=codigo_norm).order_by(ProduccionInyeccion.fecha_inicia.desc()).limit(50).all()
        for m in iny:
            movimientos.append({
                'fecha': m.fecha_inicia.strftime('%Y-%m-%d') if m.fecha_inicia else 'S/F',
                'proceso': 'Inyección',
                'responsable': m.responsable,
                'maquina': m.maquina,
                'cantidad': float(m.cantidad_real or 0),
                'estado': m.estado
            })

        pul = ProduccionPulido.query.filter_by(codigo=codigo_norm).order_by(ProduccionPulido.fecha.desc()).limit(50).all()
        for m in pul:
            movimientos.append({
                'fecha': m.fecha.strftime('%Y-%m-%d') if m.fecha else 'S/F',
                'proceso': 'Pulido',
                'responsable': m.responsable,
                'maquina': 'N/A',
                'cantidad': float(m.cantidad_real or 0),
                'estado': 'Completado'
            })

        sql_ven = text("""
            SELECT id, fecha, productos, nombres, cantidad, documento, clasificacion, total_ingresos
            FROM db_ventas
            WHERE productos ILIKE :o
            LIMIT 50
        """)
        ven = db.session.execute(sql_ven, {"o": f"%{codigo_norm}%"}).mappings().all()
        for m in ven:
            f_dt = m['fecha']
            movimientos.append({
                'fecha': f_dt.strftime('%Y-%m-%d') if hasattr(f_dt, 'strftime') else str(f_dt or 'S/F'),
                'proceso': 'Venta',
                'responsable': m['nombres'],
                'maquina': m['documento'],
                'cantidad': float(m['cantidad'] or 0),
                'total_ingresos': float(m['total_ingresos'] or 0),
                'estado': 'Facturado'
            })

        movimientos.sort(key=lambda x: x['fecha'], reverse=True)

        return {
            'movimientos': movimientos,
            'total': len(movimientos),
            'producto': codigo_norm
        }

    @staticmethod
    def buscar_alternativas(interno: str) -> List[Dict]:
        """Productos que comparten el mismo ID CODIGO (INTERNO)."""
        interno_buscado = str(interno).strip().upper()
        productos = db.session.query(Producto).filter(
            db.func.upper(Producto.id_codigo) == interno_buscado
        ).all()

        return [{
            'CODIGO': p.codigo_sistema,
            'ID CODIGO': p.id_codigo,
            'DESCRIPCION': p.descripcion,
            'STOCK': float(p.p_terminado or 0),
            'IMAGEN': p.imagen
        } for p in productos]


# Instancia única
inventario_service = InventarioService()