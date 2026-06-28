from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from models import PriceDocument, PriceItem, Service, Partner, ParseStatusEnum
from typing import Optional


# ─── Documents ───

def get_document_by_id(db: Session, doc_id):
    return db.query(PriceDocument).filter(PriceDocument.doc_id == str(doc_id)).first()

def create_document(db: Session, file_name: str, status: str, file_format=None):
    doc = PriceDocument(file_name=file_name, parse_status=ParseStatusEnum[status], file_format=file_format)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

def count_items_by_doc(db: Session, doc_id) -> int:
    return db.query(PriceItem).filter(PriceItem.doc_id == str(doc_id)).count()


# ─── Dashboard stats ───

def get_dashboard_stats(db: Session) -> dict:
    total_docs = db.query(PriceDocument).count()
    done_docs = db.query(PriceDocument).filter(PriceDocument.parse_status == ParseStatusEnum.done).count()
    error_docs = db.query(PriceDocument).filter(PriceDocument.parse_status == ParseStatusEnum.error).count()
    needs_review_docs = db.query(PriceDocument).filter(PriceDocument.parse_status == ParseStatusEnum.needs_review).count()
    total_items = db.query(PriceItem).filter(PriceItem.is_active == True).count()
    # FIX: используем .is_(None) вместо == None
    unmatched_items = db.query(PriceItem).filter(
        PriceItem.service_id.is_(None), PriceItem.is_active == True
    ).count()
    verified_items = db.query(PriceItem).filter(
        PriceItem.is_verified == True, PriceItem.is_active == True
    ).count()
    total_partners = db.query(Partner).filter(Partner.is_active == True).count()
    total_services = db.query(Service).filter(Service.is_active == True).count()

    normalization_pct = 0
    if total_items > 0:
        matched = total_items - unmatched_items
        normalization_pct = round(matched / total_items * 100, 1)

    return {
        "total_docs": total_docs,
        "done_docs": done_docs,
        "error_docs": error_docs,
        "needs_review_docs": needs_review_docs,
        "total_items": total_items,
        "unmatched_items": unmatched_items,
        "verified_items": verified_items,
        "total_partners": total_partners,
        "total_services": total_services,
        "normalization_pct": normalization_pct,
    }


# ─── Services ───

def get_services(db: Session, category: Optional[str] = None, skip: int = 0, limit: int = 100):
    q = db.query(Service).filter(Service.is_active == True)
    if category:
        q = q.filter(Service.category == category)
    return q.offset(skip).limit(limit).all()

def get_service_by_id(db: Session, service_id: str):
    return db.query(Service).filter(Service.service_id == service_id).first()

def get_partners_for_service(db: Session, service_id: str):
    return (
        db.query(PriceItem)
        .filter(PriceItem.service_id == service_id, PriceItem.is_active == True)
        .all()
    )

def create_service(db: Session, data: dict):
    svc = Service(**data)
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


# ─── Partners ───

def get_partners(db: Session, city: Optional[str] = None, is_active: Optional[bool] = None,
                 skip: int = 0, limit: int = 100):
    q = db.query(Partner)
    if city:
        q = q.filter(Partner.city == city)
    if is_active is not None:
        q = q.filter(Partner.is_active == is_active)
    return q.offset(skip).limit(limit).all()

def get_partner_by_id(db: Session, partner_id: str):
    return db.query(Partner).filter(Partner.partner_id == partner_id).first()

def get_services_for_partner(db: Session, partner_id: str):
    return (
        db.query(PriceItem)
        .filter(PriceItem.partner_id == partner_id, PriceItem.is_active == True)
        .all()
    )


# ─── Unmatched / Match ───

def get_unmatched_items(db: Session, skip: int = 0, limit: int = 100):
    # FIX: .is_(None) вместо == None
    return (
        db.query(PriceItem)
        .filter(PriceItem.service_id.is_(None), PriceItem.is_active == True)
        .offset(skip).limit(limit).all()
    )

def match_item(db: Session, item_id: str, service_id: str, note: Optional[str] = None):
    item = db.query(PriceItem).filter(PriceItem.item_id == item_id).first()
    if not item:
        return None
    item.service_id = service_id
    item.is_verified = True
    item.verification_note = note
    db.commit()
    db.refresh(item)
    return item


# ─── Search ───

def search_all(db: Session, q: str, limit: int = 50):
    term = f"%{q}%"
    services = db.query(Service).filter(Service.service_name.ilike(term)).limit(limit).all()
    partners = db.query(Partner).filter(Partner.name.ilike(term)).limit(limit).all()
    items = (
        db.query(PriceItem)
        .filter(PriceItem.service_name_raw.ilike(term), PriceItem.is_active == True)
        .limit(limit).all()
    )
    return {"services": services, "partners": partners, "price_items": items}


# ─── Каталог ───

def load_service_catalog(db: Session, entries: list):
    created = 0
    updated = 0
    for entry in entries:
        existing = db.query(Service).filter(Service.service_name == entry.get('service_name')).first()
        if existing:
            for k, v in entry.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(Service(**entry))
            created += 1
    db.commit()
    return {"created": created, "updated": updated}


# ─── Версионирование: архивация старой позиции при дублировании ───

def archive_old_item(db: Session, old_item: PriceItem, new_item_id) -> None:
    """Архивирует старую позицию, проставляя ссылку на новую версию."""
    old_item.is_active = False
    old_item.superseded_by = new_item_id
    db.add(old_item)


def find_existing_active_item(db: Session, partner_id, service_name_raw: str, effective_date=None):
    """Ищет активную позицию с таким же названием для данного партнёра."""
    q = db.query(PriceItem).filter(
        PriceItem.partner_id == partner_id,
        PriceItem.service_name_raw == service_name_raw,
        PriceItem.is_active == True,
    )
    if effective_date:
        q = q.filter(PriceItem.effective_date == effective_date)
    return q.first()
