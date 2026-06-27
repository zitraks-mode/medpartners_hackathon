import pandas as pd
from typing import List, Dict, Any

def parse_xlsx(file_path: str) -> List[Dict[str, Any]]:
    """
    Парсит XLSX файл и возвращает список извлеченных позиций.
    """
    extracted_items = []
    try:
        # Читаем все листы из файла
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            # В Excel заголовок таблицы часто бывает не на первой строке.
            # Нам нужно найти строку, где есть слова вроде "услуга", "наименование" и "цена".
            header_row_index = -1
            
            # Проверяем первые 20 строк, чтобы найти заголовок
            for idx, row in df.head(20).iterrows():
                row_str = ' '.join(str(val).lower() for val in row.values)
                if ('услуга' in row_str or 'наименование' in row_str) and 'цена' in row_str:
                    header_row_index = idx
                    break
            
            # Если заголовок найден, читаем таблицу, начиная с этой строки
            if header_row_index != -1:
                # Перечитываем лист, указывая правильную строку с заголовками (header=индекс)
                df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row_index + 1)
            
            # Очищаем таблицу от полностью пустых строк и колонок
            df.dropna(how='all', inplace=True)
            df.dropna(axis=1, how='all', inplace=True)
            
            # Пытаемся найти нужные колонки
            # Приводим названия колонок к нижнему регистру для удобства поиска
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            service_col = None
            price_col = None
            
            for col in df.columns:
                if 'услуга' in col or 'наименование' in col or 'название' in col:
                    service_col = col
                elif 'цена' in col or 'стоимость' in col:
                    price_col = col
                    
            if service_col and price_col:
                for index, row in df.iterrows():
                    service_name = str(row[service_col]).strip()
                    price = row[price_col]
                    
                    # Простая валидация: пропускаем пустые услуги
                    if not service_name or service_name == 'nan':
                        continue
                        
                    # Пытаемся очистить цену (оставляем только цифры)
                    try:
                        # Убираем пробелы, запятые меняем на точки
                        clean_price = str(price).replace(' ', '').replace(',', '.')
                        # Оставляем только числа и точку
                        clean_price = ''.join(c for c in clean_price if c.isdigit() or c == '.')
                        numeric_price = float(clean_price) if clean_price else None
                    except (ValueError, TypeError):
                        numeric_price = None
                        
                    extracted_items.append({
                        "service_name_raw": service_name,
                        "price": numeric_price
                    })

    except Exception as e:
        print(f"Ошибка при парсинге {file_path}: {e}")
        # В идеале здесь нужно писать ошибку в parse_log документа
        
    return extracted_items

# docx файлы

from docx import Document

def parse_docx(file_path: str) -> List[Dict[str, Any]]:
    extracted_items = []
    doc = Document(file_path)
    
    # Парсим все таблицы в документе
    for table in doc.tables:
        for row in table.rows:
            # Превращаем ячейки строки в список текста
            cells = [cell.text.strip() for cell in row.cells]
            
            # Логика поиска: ищем строку, где есть "цена" и "услуга"
            # (предположим, что прайс — это таблица)
            row_str = " ".join(cells).lower()
            if 'цена' in row_str and ('услуга' in row_str or 'наименование' in row_str):
                continue # Это заголовок, пропускаем
                
            # Здесь нужно подставить индексы колонок, если структура фиксированная
            # Или сделать динамический поиск, как в XLSX
            if len(cells) >= 2:
                extracted_items.append({
                    "service_name_raw": cells[0], 
                    "price": cells[1] # Нужна очистка, как в XLSX
                })
    return extracted_items



import pdfplumber

def parse_pdf(file_path: str) -> List[Dict[str, Any]]:
    extracted_items = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    # Чистим данные от None
                    row = [str(cell) if cell else "" for cell in row]
                    # ... логика обработки строк ...
                    extracted_items.append({"service_name_raw": row[0], "price": row[1]})
    return extracted_items

import pytesseract
from pdf2image import convert_from_path

def parse_pdf_scan(file_path: str) -> List[Dict[str, Any]]:
    # Конвертируем PDF в картинки
    images = convert_from_path(file_path)
    extracted_items = []
    
    for img in images:
        # Распознаем текст с картинки
        text = pytesseract.image_to_string(img, lang='rus')
        # Дальше идет магия: регулярки для поиска строк типа "Услуга ... Цена"
        # Это будет самым слабым местом, поэтому здесь лучше использовать 
        # жесткие регулярные выражения под структуру прайса.
    return extracted_items

def parse_file(file_path: str):
    ext = file_path.lower().split('.')[-1]
    if ext == 'xlsx' or ext == 'xls':
        return parse_xlsx(file_path)
    elif ext == 'docx':
        return parse_docx(file_path)
    elif ext == 'pdf':
        # Можно добавить проверку: если текст внутри есть, то parse_pdf, 
        # если нет — parse_pdf_scan
        return parse_pdf(file_path)
    return []