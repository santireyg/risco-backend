# app/models/docs_validation.py

from pydantic import BaseModel
from typing import List

class Validation(BaseModel):
    status: str = "no disponible"
    message: List[str] = ["Aún no se ha ejecutado la validación."]
