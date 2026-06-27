from database import SessionLocal
from models import PriceDocument, PriceItem, ParseStatusEnum
from parsers import parse_file

def run_parsing_task(doc_id: str, file_path: str):
    db = SessionLocal()
    try:
        doc = db.query(PriceDocument).filter(PriceDocument.doc_id == doc_id).first()
        if not doc: return
        
        doc.parse_status = ParseStatusEnum.processing
        db.commit()
        
        items = parse_file(file_path)
        
        for item in items:
            new_item = PriceItem(
                doc_id=doc.doc_id,
                partner_id=doc.partner_id,
                service_name_raw=item.get('service_name_raw'),
                price_original=item.get('price')
            )
            db.add(new_item)
        
        doc.parse_status = ParseStatusEnum.done
        db.commit()
    except Exception as e:
        doc.parse_status = ParseStatusEnum.error
        doc.parse_log = str(e)
        db.commit()
    finally:
        db.close()