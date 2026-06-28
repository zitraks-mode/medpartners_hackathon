# MedPartners / MedArchive

Система управления прайс-листами медицинских партнёров.

---

## Содержание

1. [Обзор](#1-обзор)
2. [Требования](#2-требования)
3. [Настройка PostgreSQL](#3-настройка-postgresql)
4. [Инициализация БД](#4-инициализация-бд)
5. [Запуск сервера](#5-запуск-сервера)
6. [Веб-интерфейс](#6-веб-интерфейс)
7. [Работа с системой](#7-работа-с-системой)
8. [Управление БД](#8-управление-бд)
9. [Архитектура обработки](#9-архитектура-обработки)
10. [Решение проблем](#10-решение-проблем)

---

## 1. Обзор

| Файл | Назначение |
|------|------------|
| `main.py` | FastAPI-приложение, REST API |
| `parsers.py` | Парсеры XLSX / DOCX / PDF / OCR |
| `services.py` | Бизнес-логика обработки документов |
| `crud.py` | Операции с БД через SQLAlchemy |
| `models.py` | ORM-модели (Partner, Service, PriceItem, PriceDocument) |
| `schemas.py` | Pydantic-схемы запросов и ответов |
| `database.py` | Подключение к PostgreSQL |
| `index.html` + `script.js` | Веб-интерфейс (vanilla JS) |

---

## 2. Требования

**Системное ПО:**

| ПО | Версия | Назначение |
|----|--------|------------|
| Python | 3.10+ | Основной язык |
| PostgreSQL | 14+ | База данных |
| Tesseract OCR | 5.x | Распознавание сканированных PDF |
| Poppler | любая | pdf2image (конвертация PDF → изображения) |

**Python-зависимости:**

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-multipart
pip install pandas openpyxl python-docx pdfplumber pdf2image pytesseract
pip install rapidfuzz
```

> `rapidfuzz` используется для нечёткого сопоставления позиций прайса со справочником. Без него нормализация пропускается, но парсинг продолжается.

---

## 3. Настройка PostgreSQL

```sql
psql -U postgres

CREATE DATABASE medpartners_db;

-- Опционально: отдельный пользователь
CREATE USER meduser WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE medpartners_db TO meduser;
```

Строка подключения задаётся в `database.py`:

```python
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:password@localhost:5432/medpartners_db"
```

Измените логин/пароль при необходимости.

---

## 4. Инициализация БД

```bash
python init_db.py
# Таблицы созданы!
```

Загрузка справочника медицинских услуг (нужен запущенный сервер — см. шаг 5):

```bash
python load_catalog.py
```

---

## 5. Запуск сервера

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

- API: http://localhost:8080
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

> `--reload` включает автоперезагрузку при изменении кода. Для продакшена уберите флаг.

---

## 6. Веб-интерфейс

Откройте `index.html` напрямую в браузере или через HTTP-сервер:

```bash
python -m http.server 3000
# http://localhost:3000/index.html
```

Возможности интерфейса:
- Дашборд со статистикой (документы, позиции, партнёры, услуги)
- Загрузка ZIP-архива с прайс-листами
- Просмотр статуса обработки документов
- Поиск по услугам и партнёрам
- Ручное сопоставление несопоставленных позиций

---

## 7. Работа с системой

### 7.1 Загрузка прайс-листов

Упакуйте файлы в ZIP и загрузите:

```bash
zip prices.zip clinic_2024-01-15.xlsx hospital_2024-02.docx lab.pdf

curl -X POST http://localhost:8080/upload-archive \
  -F "file=@prices.zip"
```

> Система автоматически извлекает дату (форматы `YYYY-MM-DD` или `DD.MM.YYYY`) и название партнёра из имени файла.  
> Пример: `clinic_name_2024-03-15.xlsx`

### 7.2 Поддерживаемые форматы

| Формат | Парсер | Требования |
|--------|--------|------------|
| XLSX / XLS | pandas + openpyxl | Таблица с колонками услуга/цена |
| DOCX | python-docx | Таблицы в документе Word |
| PDF (текстовый) | pdfplumber | Встроенный текстовый слой |
| PDF (скан) | pytesseract + pdf2image | Tesseract OCR + Poppler |

### 7.3 Мониторинг обработки

```bash
curl http://localhost:8080/documents/{doc_id}/status
```

Возможные статусы:

| Статус | Описание |
|--------|----------|
| `pending` | Ожидает обработки |
| `processing` | Обрабатывается |
| `done` | Успешно завершено |
| `needs_review` | Завершено, но >50% позиций требуют ревью |
| `error` | Ошибка обработки |

### 7.4 Основные эндпоинты API

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/dashboard/stats` | Статистика системы |
| POST | `/upload-archive` | Загрузка ZIP с прайсами |
| GET | `/documents/{id}/status` | Статус обработки |
| GET | `/services` | Список услуг справочника |
| GET | `/partners` | Список партнёров |
| GET | `/search?q=...` | Полнотекстовый поиск |
| GET | `/unmatched` | Несопоставленные позиции |
| POST | `/match` | Ручное сопоставление |
| POST | `/catalog/upload` | Массовая загрузка справочника |

---

## 8. Управление БД

Полная очистка всех таблиц (структура сохраняется):

```bash
python clear_db.py

# Без подтверждения (для CI)
python clear_db.py --yes
```

Пересоздание с нуля:

```bash
python clear_db.py --yes && python init_db.py && python load_catalog.py
```

---

## 9. Архитектура обработки

Загруженный ZIP обрабатывается в фоновом потоке (`BackgroundTasks`):

1. ZIP распаковывается в директорию `extracted/`
2. Каждый файл определяется по расширению и типу (скан vs текст для PDF)
3. Парсер извлекает строки: название услуги, цена резидента, цена нерезидента
4. Из имени файла извлекаются дата прайса и название партнёра
5. Нормализация: нечёткое сопоставление со справочником через rapidfuzz (порог 85%)
6. Дедупликация: если позиция уже есть — старая архивируется, создаётся новая версия
7. Валидация: проверка цены, даты, аномалий (изменение >50%), конвертация валют
8. Статус документа обновляется: `done` / `needs_review` / `error`

---

## 10. Решение проблем

| Проблема | Решение |
|----------|---------|
| Ошибка подключения к PostgreSQL | Проверьте `SQLALCHEMY_DATABASE_URL` в `database.py` и что PostgreSQL запущен |
| PDF (скан): нуль позиций | Проверьте установку Tesseract и Poppler: `tesseract --version`, `pdftoppm -v` |
| DOCX: нуль позиций | Парсер ищет таблицы с колонками `наименование/услуга` и `цена/стоимость` — проверьте заголовки |
| rapidfuzz не установлен | `pip install rapidfuzz`. Без него нормализация пропускается, позиции сохраняются без `service_id` |
| Статус `error` после загрузки | Смотрите `parse_log` через `GET /documents/{id}/status` — там детальный лог по каждому файлу |
| `load_catalog.py` — Connection refused | Сначала запустите uvicorn (шаг 5), потом запускайте `load_catalog.py` |

---

## Быстрый старт (чеклист)

```bash
# 1. Зависимости
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-multipart \
  pandas openpyxl python-docx pdfplumber pdf2image pytesseract rapidfuzz

# 2. Tesseract + Poppler (Ubuntu/Debian)
sudo apt install tesseract-ocr tesseract-ocr-rus poppler-utils

# 3. База данных
psql -U postgres -c "CREATE DATABASE medpartners_db;"

# 4. Таблицы
python init_db.py

# 5. Сервер
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# 6. Справочник (в отдельном терминале)
python load_catalog.py

# 7. Открыть index.html в браузере и загрузить ZIP с прайсами
```
