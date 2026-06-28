import os
from database import SessionLocal
from models import PriceDocument, PriceItem, ParseStatusEnum
from parsers import parse_file

# Обновленная фоновая задача
def process_document_task(doc_id: str, extract_dir: str):
    db = SessionLocal()
    try:
        doc = db.query(PriceDocument).filter(PriceDocument.doc_id == doc_id).first()
        if not doc: return
        
        doc.parse_status = ParseStatusEnum.processing
        db.commit()
        
        all_items = []
        
        # МАГИЯ ЗДЕСЬ: Проходимся по всем файлам в распакованной папке
        for root, dirs, files in os.walk(extract_dir):
            for file_name in files:
                # Пропускаем скрытые файлы (например, .DS_Store на Mac)
                if file_name.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file_name)
                
                # Парсим каждый найденный файл
                items = parse_file(file_path)
                all_items.extend(items)
        
        # Сохраняем все найденные позиции в базу
        for item in all_items:
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
        print(f"Ошибка парсинга: {e}") # Выводим ошибку в терминал
    finally:
        db.close()