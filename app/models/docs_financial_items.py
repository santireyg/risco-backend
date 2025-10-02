from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DocumentGeneralInformation(BaseModel):
    empresa: str
    periodo_actual: datetime
    periodo_anterior: Optional[datetime] = None

class SheetItem(BaseModel):
    concepto: str
    monto_actual: float
    monto_anterior: float