from fastapi import FastAPI, UploadFile, File, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Optional, List
import os, shutil, zipfile

from database import SessionLocal
import crud, schemas, services

app = FastAPI(title="MedPartners API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════
#  Дашборд
# ═══════════════════════════════════════════════

@app.get("/dashboard/stats", response_model=schemas.DashboardStats, summary="Статистика для дашборда")
def dashboard_stats(db: Session = Depends(get_db)):
    return crud.get_dashboard_stats(db)


# ═══════════════════════════════════════════════
#  Загрузка архива
# ═══════════════════════════════════════════════

@app.post("/upload-archive", summary="Загрузить ZIP-архив с прайсами")
def upload_archive(
    bg_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Принимаются только ZIP-архивы")

    os.makedirs("uploads", exist_ok=True)
    os.makedirs("extracted", exist_ok=True)

    zip_path = os.path.join("uploads", file.filename)
    extract_path = os.path.join("extracted", file.filename.replace('.zip', ''))

    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

    new_doc = crud.create_document(db, file.filename, "pending")
    bg_tasks.add_task(services.process_document_task, str(new_doc.doc_id), extract_path)

    return {"doc_id": str(new_doc.doc_id), "file_name": file.filename}


@app.get(
    "/documents/{doc_id}/status",
    response_model=schemas.DocumentStatusResponse,
    summary="Статус обработки документа",
)
def get_status(doc_id: str, db: Session = Depends(get_db)):
    doc = crud.get_document_by_id(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return {
        "status": doc.parse_status.value,
        "items_extracted": crud.count_items_by_doc(db, doc_id),
        "log": doc.parse_log,
    }


# ═══════════════════════════════════════════════
#  Справочник услуг
# ═══════════════════════════════════════════════

@app.get("/services", response_model=List[schemas.ServiceOut], summary="Список услуг справочника")
def list_services(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return crud.get_services(db, category=category, skip=skip, limit=limit)


@app.get(
    "/services/{service_id}/partners",
    response_model=List[schemas.PriceItemOut],
    summary="Партнёры, оказывающие услугу, с ценами",
)
def service_partners(service_id: str, db: Session = Depends(get_db)):
    svc = crud.get_service_by_id(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    return crud.get_partners_for_service(db, service_id)


@app.post("/services", response_model=schemas.ServiceOut, summary="Создать услугу в справочнике")
def create_service(body: schemas.ServiceCreate, db: Session = Depends(get_db)):
    return crud.create_service(db, body.model_dump())


@app.post(
    "/catalog/upload",
    response_model=schemas.CatalogUploadResponse,
    summary="Массовая загрузка справочника услуг (JSON)",
)
def upload_catalog(entries: List[schemas.CatalogEntry], db: Session = Depends(get_db)):
    result = crud.load_service_catalog(db, [e.model_dump() for e in entries])
    return result


# ═══════════════════════════════════════════════
#  Партнёры
# ═══════════════════════════════════════════════

@app.get("/partners", response_model=List[schemas.PartnerOut], summary="Список партнёров")
def list_partners(
    city: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return crud.get_partners(db, city=city, is_active=is_active, skip=skip, limit=limit)


@app.get(
    "/partners/{partner_id}/services",
    response_model=List[schemas.PriceItemOut],
    summary="Все услуги партнёра с ценами",
)
def partner_services(partner_id: str, db: Session = Depends(get_db)):
    partner = crud.get_partner_by_id(db, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Партнёр не найден")
    return crud.get_services_for_partner(db, partner_id)


# ═══════════════════════════════════════════════
#  Поиск
# ═══════════════════════════════════════════════

@app.get("/search", response_model=schemas.SearchResponse, summary="Полнотекстовый поиск")
def search(q: str, db: Session = Depends(get_db)):
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Запрос слишком короткий")
    return crud.search_all(db, q)


# ═══════════════════════════════════════════════
#  Верификация / несопоставленные
# ═══════════════════════════════════════════════

@app.get(
    "/unmatched",
    response_model=List[schemas.PriceItemOut],
    summary="Несопоставленные позиции прайса",
)
def get_unmatched(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_unmatched_items(db, skip=skip, limit=limit)


@app.post("/match", response_model=schemas.PriceItemOut, summary="Ручное сопоставление позиции с услугой")
def match_item(body: schemas.MatchRequest, db: Session = Depends(get_db)):
    result = crud.match_item(db, body.item_id, body.service_id, body.note)
    if not result:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    return result


# Запуск: uvicorn main:app --host 0.0.0.0 --port 8080 --reload
