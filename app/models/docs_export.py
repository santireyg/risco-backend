# app/models/docs_export.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

class ExportData(BaseModel):
    export_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exported_at: Optional[datetime] = None
    event_type: str = "CREATE"  # "CREATE" o "MODIFY"
    last_export_attempt: Optional[datetime] = None
    export_success: bool = False
    external_response: Optional[str] = None  # Para guardar respuesta de la API externa
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
