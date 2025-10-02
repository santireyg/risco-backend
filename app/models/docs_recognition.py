# app/models/docs_recognition.py

from pydantic import BaseModel

class RecognizedInfo(BaseModel):
    is_balance_sheet: bool
    is_income_statement_sheet: bool
    is_appendix: bool
    original_orientation_degrees: int
    has_company_cuit: bool | None = None
    has_company_name: bool | None = None
    has_company_address: bool | None = None
    has_company_activity: bool | None = None
    audit_report: bool | None = None


class RecognizedInfoForLLM(BaseModel):
    is_balance_sheet: bool
    is_income_statement_sheet: bool
    is_appendix: bool
    original_orientation_degrees: int
    has_company_cuit: bool
    has_company_name: bool
    has_company_address: bool
    has_company_activity: bool
    audit_report: bool