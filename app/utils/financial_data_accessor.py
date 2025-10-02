# app/utils/financial_data_accessor.py
"""
Helper para acceder a datos financieros con compatibilidad hacia atrás.

Soporta tanto la estructura antigua (campos planos) como la nueva (lista directa).
"""

from typing import Optional, Dict, Any, Union, List


class FinancialDataAccessor:
    """
    Proporciona acceso unificado a datos financieros independientemente de su estructura.
    
    Estructura antigua:
        {
            "activo_total_actual": 1000.0,
            "activo_total_anterior": 900.0,
            ...
        }
    
    Estructura nueva (lista directa):
        [
            {
                "concepto_code": "activo_total",
                "concepto": "Activo Total",
                "monto_actual": 1000.0,
                "monto_anterior": 900.0
            },
            ...
        ]
    """
    
    def __init__(self, data):
        """
        Inicializa el accessor con los datos financieros.
        
        Args:
            data: Diccionario con datos financieros (estructura antigua) o lista (estructura nueva)
        """
        self.data = data
        self._is_new_structure = isinstance(data, list)
        self._items_cache = {}
        
        if self._is_new_structure:
            # Construir cache para acceso rápido
            for item in data:
                concepto = item.get("concepto_code")
                if concepto:
                    self._items_cache[concepto] = item
    
    def get(self, concepto: str, periodo: str = "actual") -> Optional[float]:
        """
        Obtiene un valor del concepto especificado para el período dado.
        
        Args:
            concepto: Nombre del concepto (ej: 'activo_total')
            periodo: 'actual' o 'anterior'
        
        Returns:
            float: Valor del concepto, o None si no existe
        
        Ejemplo:
            >>> accessor = FinancialDataAccessor(balance_data)
            >>> activo = accessor.get('activo_total', 'actual')
        """
        if self._is_new_structure:
            # Estructura nueva: buscar en items
            item = self._items_cache.get(concepto)
            if item:
                return item.get(f"monto_{periodo}")
            return None
        else:
            # Estructura antigua: acceso directo
            field_name = f"{concepto}_{periodo}"
            return self.data.get(field_name)
    
    def has(self, concepto: str) -> bool:
        """
        Verifica si existe un concepto en los datos.
        
        Args:
            concepto: Nombre del concepto
        
        Returns:
            bool: True si el concepto existe
        """
        if self._is_new_structure:
            return concepto in self._items_cache
        else:
            # En estructura antigua, verificar si existen los campos _actual y _anterior
            return f"{concepto}_actual" in self.data or f"{concepto}_anterior" in self.data
    
    def get_all_conceptos(self) -> list:
        """
        Retorna lista de todos los conceptos disponibles.
        
        Returns:
            list: Lista de nombres de conceptos
        """
        if self._is_new_structure:
            return list(self._items_cache.keys())
        else:
            # Extraer conceptos de estructura antigua
            conceptos = set()
            for key in self.data.keys():
                if key.endswith("_actual"):
                    concepto = key.replace("_actual", "")
                    conceptos.add(concepto)
                elif key.endswith("_anterior"):
                    concepto = key.replace("_anterior", "")
                    conceptos.add(concepto)
            return list(conceptos)
    
    def is_new_structure(self) -> bool:
        """Retorna True si usa la estructura nueva."""
        return self._is_new_structure


def create_accessor(data) -> FinancialDataAccessor:
    """
    Factory para crear un FinancialDataAccessor.
    
    Args:
        data: Diccionario con datos financieros (estructura antigua) o lista (estructura nueva)
    
    Returns:
        FinancialDataAccessor: Accessor para los datos
    """
    return FinancialDataAccessor(data)
