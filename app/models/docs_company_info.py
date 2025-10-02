from pydantic import BaseModel, Field
from typing import Optional

class CompanyInfo(BaseModel):
    company_cuit: Optional[str] = Field(
        None,
        pattern=r'^\d{11}$',
        description='CUIT de 11 dígitos numéricos'
    )
    company_name: str
    company_activity: str | None = None
    company_address: str | None = None
