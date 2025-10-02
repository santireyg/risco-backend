# app/models/docs.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone, date
from bson import ObjectId

from app.models.docs_recognition import RecognizedInfo
from app.models.docs_report import AIReport
from app.models.docs_validation import Validation
from app.models.docs_company_info import CompanyInfo
from app.models.docs_processing_time import ProcessingTime
from app.models.docs_export import ExportData


class Page(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")  # ID único para cada página
    name: str
    number: int
    image_path: str
    recognized_info: Optional[RecognizedInfo] = Field(default=None)
    rotation_degrees: int = 0
    company_info: Optional[bool] = Field(default=False) # Indica si la página pertenece a company_info
    # is_income_statement_sheet: bool = False   ---> quizas se use en el futuro
    # is_balance_sheet: bool = False            ---> quizas se use en el futuro

class DocFile(BaseModel):
    name: str
    status: str = "En cola"
    upload_path: Optional[str] = None
    progress: Optional[float] = 0.0
    pages: List[Page] = []
    page_count: Optional[int] = None
    upload_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    uploaded_by: str
    balance_date: Optional[datetime] = None
    balance_date_previous: Optional[datetime] = None
    income_statement_data: Optional[Dict[str, Any]] = None  # Estructura dinámica por tenant
    balance_data: Optional[Dict[str, Any]] = None  # Estructura dinámica por tenant
    validation: Optional["Validation"] = Field(default_factory=Validation)
    ai_report: Optional["AIReport"] = None
    company_info: Optional["CompanyInfo"] = None
    processing_time: Optional["ProcessingTime"] = Field(default=None, description="Tiempos de procesamiento por etapa")
    export_data: Optional["ExportData"] = None
    tenant_id: str = "default"  # Tenant propietario del documento

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
