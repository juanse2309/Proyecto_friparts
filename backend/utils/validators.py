"""
Validadores reutilizables para formularios y datos.
Elimina validaciones duplicadas en endpoints.
"""
from typing import Dict, List, Tuple, Any
from backend.config.settings import Almacenes


class Validator:
    """Validador de datos de entrada."""
    
    @staticmethod
    def validar_requeridos(data: Dict, campos: List[str]) -> Tuple[bool, List[str]]:
        """Valida que los campos requeridos estén presentes."""
        errores = []
        for campo in campos:
            valor = data.get(campo)
            if not valor or str(valor).strip() == "":
                errores.append(f"El campo '{campo}' es obligatorio")
        return len(errores) == 0, errores
    
    @staticmethod
    def validar_cantidad(cantidad: Any, nombre_campo: str = "cantidad") -> Tuple[bool, List[str]]:
        """Valida que una cantidad sea válida (entero positivo)."""
        errores = []
        try:
            cantidad_int = int(cantidad)
            if cantidad_int <= 0:
                errores.append(f"{nombre_campo} debe ser mayor a 0")
        except (ValueError, TypeError):
            errores.append(f"{nombre_campo} debe ser un número válido")
        return len(errores) == 0, errores
    
    @staticmethod
    def validar_almacen(almacen: str) -> Tuple[bool, List[str]]:
        """Valida que un almacén sea válido."""
        errores = []
        if not Almacenes.es_valido(almacen):
            almacenes_validos = ', '.join(Almacenes.MAPEO.keys())
            errores.append(f"Almacén inválido. Válidos: {almacenes_validos}")
        return len(errores) == 0, errores
