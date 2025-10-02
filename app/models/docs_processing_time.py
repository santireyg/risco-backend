# app/models/docs_processing_time.py

from pydantic import BaseModel, Field
from typing import Optional

class ProcessingTime(BaseModel):
    upload_convert: Optional[float] = Field(default=None, description="Tiempo en segundos para carga y conversión")
    recognize: Optional[float] = Field(default=None, description="Tiempo en segundos para reconocimiento")
    extract: Optional[float] = Field(default=None, description="Tiempo en segundos para extracción")
    validation: Optional[float] = Field(default=None, description="Tiempo en segundos para validación")
    total: Optional[float] = Field(default=None, description="Tiempo total en segundos")

    def calculate_total(self) -> Optional[float]:
        """Calcula el tiempo total sumando los tiempos de las etapas que no son None"""
        times = [
            self.upload_convert,
            self.recognize,
            self.extract,
            self.validation
        ]
        # Filtrar valores None y convertir a 0 si es necesario
        valid_times = [t for t in times if t is not None and t >= 0]
        
        if valid_times:
            return sum(valid_times)
        return None

    def update_total(self):
        """Actualiza el campo total con la suma de las etapas"""
        self.total = self.calculate_total()
