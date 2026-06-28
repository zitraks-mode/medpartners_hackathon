import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Date, ForeignKey, Numeric, Text, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from database import Base


class FileFormatEnum(enum.Enum):
    pdf = "pdf"
    docx = "docx"
    xlsx = "xlsx"
    scan_pdf = "scan_pdf"


class ParseStatusEnum(enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    error = "error"
    needs_review = "needs_review"


class CurrencyEnum(enum.Enum):
    KZT = "KZT"
    USD = "USD"
    RUB = "RUB"


class Partner(Base):
    __tablename__ = "partners"

    partner_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    city = Column(String)
    address = Column(String)
    bin = Column(String(12), unique=True, index=True)
    contact_email = Column(String)
    contact_phone = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("PriceDocument", back_populates="partner")


class Service(Base):
    __tablename__ = "services"

    service_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String, nullable=False)
    synonyms = Column(JSONB)
    category = Column(String)
    icd_code = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class PriceDocument(Base):
    __tablename__ = "price_documents"

    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.partner_id"), nullable=True)
    file_name = Column(String, nullable=False)
    file_format = Column(Enum(FileFormatEnum), nullable=True)
    effective_date = Column(Date, nullable=True)
    parsed_at = Column(DateTime, nullable=True)
    parse_status = Column(Enum(ParseStatusEnum), default=ParseStatusEnum.pending)
    parse_log = Column(Text, nullable=True)
    raw_content = Column(Text, nullable=True)

    partner = relationship("Partner", back_populates="documents")
    items = relationship("PriceItem", back_populates="document")


class PriceItem(Base):
    __tablename__ = "price_items"

    item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("price_documents.doc_id"))
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.partner_id"), nullable=True)

    service_name_raw = Column(String, nullable=False)
    service_code_source = Column(String, nullable=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.service_id"), nullable=True)

    price_resident_kzt = Column(Numeric, nullable=True)
    price_nonresident_kzt = Column(Numeric, nullable=True)
    price_original = Column(Numeric, nullable=True)
    currency_original = Column(Enum(CurrencyEnum), default=CurrencyEnum.KZT)

    # FIX: добавлена предыдущая цена для детектирования аномалий > 50%
    prev_price_resident_kzt = Column(Numeric, nullable=True)
    price_anomaly = Column(Boolean, default=False)

    is_verified = Column(Boolean, default=False)
    verification_note = Column(String, nullable=True)
    effective_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)

    # FIX: версионирование — ссылка на предыдущую версию позиции
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("price_items.item_id"), nullable=True)

    document = relationship("PriceDocument", back_populates="items")
    service = relationship("Service")
