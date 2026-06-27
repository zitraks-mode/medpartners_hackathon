from fastapi import FastAPI, UploadFile, File, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
import crud, schemas, services
import os
import shutil
import zipfile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MedPartners API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.post("/upload-archive")
def upload_archive(bg_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Только ZIP")
    
    zip_path = os.path.join("uploads", file.filename)
    extract_path = os.path.join("extracted", file.filename.replace('.zip', ''))
    
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    
    new_doc = crud.create_document(db, file.filename, "pending")
    
    bg_tasks.add_task(services.run_parsing_task, new_doc.doc_id, extract_path)
    
    return {"doc_id": new_doc.doc_id}

@app.get("/documents/{doc_id}/status", response_model=schemas.DocumentStatusResponse)
def get_status(doc_id: str, db: Session = Depends(get_db)):
    doc = crud.get_document_by_id(db, doc_id)
    if not doc: raise HTTPException(status_code=404)
    return {
        "status": doc.parse_status.value,
        "items_extracted": crud.count_items_by_doc(db, doc_id),
        "log": doc.parse_log
    }