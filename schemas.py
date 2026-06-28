from pydantic import BaseModel
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime, date



class DocumentStatusResponse(BaseModel):
    status: str
    items_extracted: int
    log: Optional[str]

    class Config:
        from_attributes = True



class DashboardStats(BaseModel):
    total_docs: int
    done_docs: int
    error_docs: int
    needs_review_docs: int
    total_items: int
    unmatched_items: int
    verified_items: int
    total_partners: int
    total_services: int
    normalization_pct: float



class ServiceOut(BaseModel):
    service_id: UUID
    service_name: str
    category: Optional[str]
    icd_code: Optional[str]
    synonyms: Optional[Any]
    is_active: bool

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    service_name: str
    category: Optional[str] = None
    icd_code: Optional[str] = None
    synonyms: Optional[List[str]] = None



class PartnerOut(BaseModel):
    partner_id: UUID
    name: str
    city: Optional[str]
    address: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True



class PriceItemOut(BaseModel):
    item_id: UUID
    service_name_raw: str
    service_id: Optional[UUID]
    price_original: Optional[float]
    price_resident_kzt: Optional[float]
    price_nonresident_kzt: Optional[float]
    currency_original: Optional[str]
    is_verified: bool
    verification_note: Optional[str]
    effective_date: Optional[date]
    partner_id: Optional[UUID]
    doc_id: Optional[UUID]
    price_anomaly: Optional[bool] = False

    class Config:
        from_attributes = True



class SearchResponse(BaseModel):
    services: List[ServiceOut]
    partners: List[PartnerOut]
    price_items: List[PriceItemOut]



class MatchRequest(BaseModel):
    item_id: str
    service_id: str
    note: Optional[str] = None



class CatalogEntry(BaseModel):
    service_name: str
    category: Optional[str] = None
    icd_code: Optional[str] = None
    synonyms: Optional[List[str]] = None


class CatalogUploadResponse(BaseModel):
    created: int
    updated: int
