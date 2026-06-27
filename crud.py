from sqlalchemy.orm import Session
from models import PriceDocument, PriceItem
from uuid import UUID

def get_document_by_id(db: Session, doc_id: UUID):
    return db.query(PriceDocument).filter(PriceDocument.doc_id == doc_id).first()

def create_document(db: Session, file_name: str, status: str):
    doc = PriceDocument(file_name=file_name, parse_status=status)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

def count_items_by_doc(db: Session, doc_id: UUID):
    return db.query(PriceItem).filter(PriceItem.doc_id == doc_id).count()