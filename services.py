import os
from datetime import datetime, date
from typing import Optional
from database import SessionLocal
from models import PriceDocument, PriceItem, ParseStatusEnum
from parsers import parse_file
import crud

# Порог для автоматического сопоставления
MATCH_THRESHOLD = 0.85

# Курсы валют (заглушка; в продакшене — запрос к API НБ РК)
EXCHANGE_RATES = {
    "USD": 450.0,
    "RUB": 5.0,
    "KZT": 1.0,
}


def _convert_to_kzt(price: Optional[float], currency: str) -> Optional[float]:
    """Конвертирует цену в KZT по фиксированному курсу."""
    if price is None:
        return None
    rate = EXCHANGE_RATES.get(currency, 1.0)
    return round(price * rate, 2)


def _normalize_items(db, doc, all_items: list):
    """Сопоставление позиций со справочником через RapidFuzz."""
    try:
        from rapidfuzz import process, fuzz
        from models import Service

        services = db.query(Service).filter(Service.is_active == True).all()
        if not services:
            return

        candidates = []
        for svc in services:
            candidates.append((str(svc.service_id), svc.service_name))
            if svc.synonyms:
                for syn in svc.synonyms:
                    candidates.append((str(svc.service_id), syn))

        candidate_names = [c[1] for c in candidates]

        for item in all_items:
            raw = item.get('service_name_raw', '')
            if not raw:
                continue

            result = process.extractOne(raw, candidate_names, scorer=fuzz.WRatio, score_cutoff=70)
            if result:
                matched_name, score, idx = result
                service_id = candidates[idx][0]
                item['service_id'] = service_id
                item['match_score'] = score
                if score < MATCH_THRESHOLD * 100:
                    item['needs_review'] = True
            else:
                item['service_id'] = None
                item['needs_review'] = True

    except ImportError:
        print("[normalize] rapidfuzz не установлен, нормализация пропущена")
    except Exception as e:
        print(f"[normalize] Ошибка нормализации: {e}")


def _validate_item(item: dict, doc_id, partner_id, effective_date=None):
    """
    Валидирует одну позицию прайса.
    Возвращает (item_kwargs | None, warning_message | None).
    FIX: добавлены проверки даты, аномалии цены, конвертации валюты.
    """
    warnings = []

    service_name = item.get('service_name_raw', '').strip()
    if not service_name:
        return None, "Пропущена строка: пустое название услуги"

    price = item.get('price')
    needs_review = item.get('needs_review', False)

    if price is None or price <= 0:
        warnings.append(f"Некорректная цена ({price}) для '{service_name}'")
        needs_review = True

    price_resident = item.get('price_resident')
    price_nonresident = item.get('price_nonresident')

    if price_resident and price_nonresident and price_nonresident < price_resident:
        warnings.append(
            f"Цена нерезидента ({price_nonresident}) < цены резидента ({price_resident}) для '{service_name}'"
        )
        needs_review = True

    # FIX: проверка даты прайса — не в будущем
    if effective_date and isinstance(effective_date, date) and effective_date > date.today():
        warnings.append(f"Дата прайса {effective_date} в будущем для '{service_name}'")
        needs_review = True

    # FIX: конвертация валюты в KZT
    currency = item.get('currency', 'KZT')
    price_resident_kzt = price_resident
    price_nonresident_kzt = price_nonresident
    price_original = price_resident

    if currency != 'KZT':
        price_resident_kzt = _convert_to_kzt(price_resident, currency)
        price_nonresident_kzt = _convert_to_kzt(price_nonresident, currency)
        warnings.append(f"Конвертировано из {currency} в KZT (курс: {EXCHANGE_RATES.get(currency, 1.0)})")

    # FIX: флаг аномалии цены > 50% от предыдущей
    price_anomaly = False
    prev_price = item.get('prev_price_resident_kzt')
    if prev_price and price_resident_kzt:
        diff_pct = abs(price_resident_kzt - prev_price) / prev_price * 100
        if diff_pct > 50:
            price_anomaly = True
            warnings.append(
                f"Аномалия цены: изменение на {diff_pct:.0f}% (было {prev_price}, стало {price_resident_kzt}) для '{service_name}'"
            )
            needs_review = True

    kwargs = dict(
        doc_id=doc_id,
        partner_id=partner_id,
        service_name_raw=service_name,
        service_id=item.get('service_id'),
        price_original=price_original,
        price_resident_kzt=price_resident_kzt,
        price_nonresident_kzt=price_nonresident_kzt,
        currency_original=currency,
        prev_price_resident_kzt=prev_price,
        price_anomaly=price_anomaly,
        is_verified=False,
        verification_note='; '.join(warnings) if warnings else None,
        effective_date=effective_date,
        is_active=True,
    )

    warning_msg = '; '.join(warnings) if warnings else None
    return kwargs, warning_msg


def _extract_date_from_filename(file_name: str) -> Optional[date]:
    """Пытается извлечь дату из имени файла форматов YYYY-MM-DD, DD.MM.YYYY и т.п."""
    import re
    patterns = [
        r'(\d{4})[.\-_](\d{2})[.\-_](\d{2})',  # 2024-03-15
        r'(\d{2})[.\-_](\d{2})[.\-_](\d{4})',  # 15.03.2024
    ]
    for pat in patterns:
        m = re.search(pat, file_name)
        if m:
            g = m.groups()
            try:
                if len(g[0]) == 4:
                    return date(int(g[0]), int(g[1]), int(g[2]))
                else:
                    return date(int(g[2]), int(g[1]), int(g[0]))
            except ValueError:
                continue
    return None


def _get_or_create_partner(db, partner_name: str):
    """Finds or creates a Partner by name extracted from filename."""
    from models import Partner
    name = partner_name.strip()
    if not name:
        return None
    existing = db.query(Partner).filter(Partner.name == name).first()
    if existing:
        return existing
    partner = Partner(name=name, is_active=True)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


def _extract_partner_name_from_filename(file_name: str) -> str:
    """Extracts a clinic name from a filename by stripping dates and extensions."""
    import re
    base = os.path.splitext(file_name)[0]
    # Remove date patterns
    base = re.sub(r'\d{4}[.\-_]\d{2}[.\-_]\d{2}', '', base)
    base = re.sub(r'\d{2}[.\-_]\d{2}[.\-_]\d{4}', '', base)
    # Replace separators with spaces
    base = re.sub(r'[_\-]+', ' ', base)
    return base.strip()


def _get_file_format(file_name: str, is_scan: bool = False):
    """Returns FileFormatEnum value string."""
    ext = file_name.lower().rsplit('.', 1)[-1]
    if ext == 'pdf':
        return 'scan_pdf' if is_scan else 'pdf'
    elif ext == 'docx':
        return 'docx'
    elif ext in ('xlsx', 'xls'):
        return 'xlsx'
    return None


def process_document_task(doc_id: str, extract_dir: str):
    db = SessionLocal()
    doc = None
    logs = []

    try:
        doc = db.query(PriceDocument).filter(PriceDocument.doc_id == doc_id).first()
        if not doc:
            return

        doc.parse_status = ParseStatusEnum.processing
        db.commit()

        all_items = []
        all_raw_content = []

        for root, dirs, files in os.walk(extract_dir):
            for file_name in files:
                if file_name.startswith('.'):
                    continue

                file_path = os.path.join(root, file_name)

                try:
                    # Determine file format
                    from parsers import _is_scanned_pdf
                    ext = file_name.lower().rsplit('.', 1)[-1]
                    is_scan = ext == 'pdf' and _is_scanned_pdf(file_path)
                    fmt = _get_file_format(file_name, is_scan)

                    items = parse_file(file_path)
                    # FIX: извлечение даты и партнёра из имени файла
                    eff_date = _extract_date_from_filename(file_name)
                    partner_name = _extract_partner_name_from_filename(file_name)
                    partner = _get_or_create_partner(db, partner_name) if partner_name else None

                    for it in items:
                        it['effective_date'] = eff_date
                        it['partner_id'] = str(partner.partner_id) if partner else None
                    all_items.extend(items)

                    # Save raw content for audit
                    raw_repr = '\n'.join(f"{it['service_name_raw']} | {it.get('price_resident')}" for it in items)
                    all_raw_content.append(f"=== {file_name} ===\n{raw_repr}")

                    # Set file_format and partner on document (use first file's data)
                    if fmt and not doc.file_format:
                        from models import FileFormatEnum
                        doc.file_format = FileFormatEnum[fmt]
                    if partner and not doc.partner_id:
                        doc.partner_id = partner.partner_id

                    logs.append(f"[OK] {file_name}: {len(items)} позиций" + (f" (партнёр: {partner_name})" if partner_name else ""))
                except Exception as e:
                    logs.append(f"[ERR] {file_name}: {e}")

        # Save raw content
        doc.raw_content = '\n\n'.join(all_raw_content) if all_raw_content else None

        if not all_items:
            doc.parse_status = ParseStatusEnum.error
            doc.parse_log = "Не найдено ни одной позиции в архиве."
            db.commit()
            return

        _normalize_items(db, doc, all_items)

        needs_review_count = 0
        skipped = 0
        new_items = []

        for item in all_items:
            eff_date = item.get('effective_date')
            # Use per-item partner_id (from filename) falling back to doc's partner_id
            item_partner_id = item.get('partner_id') or (str(doc.partner_id) if doc.partner_id else None)
            kwargs, warning = _validate_item(item, doc.doc_id, item_partner_id, eff_date)

            if kwargs is None:
                skipped += 1
                if warning:
                    logs.append(f"[SKIP] {warning}")
                continue

            if warning:
                logs.append(f"[WARN] {warning}")

            # FIX: дедупликация — ищем существующую активную позицию
            if item_partner_id:
                existing = crud.find_existing_active_item(
                    db, item_partner_id, kwargs['service_name_raw'], eff_date
                )
                if existing:
                    # Сохраняем предыдущую цену для сравнения аномалий
                    kwargs['prev_price_resident_kzt'] = float(existing.price_resident_kzt) if existing.price_resident_kzt else None
                    new_item = PriceItem(**kwargs)
                    db.add(new_item)
                    db.flush()  # получаем item_id
                    # FIX: архивируем старую версию
                    crud.archive_old_item(db, existing, new_item.item_id)
                    new_items.append(new_item)
                    logs.append(f"[VERSION] Обновлена позиция '{kwargs['service_name_raw']}'")
                    continue

            new_item = PriceItem(**kwargs)
            db.add(new_item)
            new_items.append(new_item)

            if item.get('needs_review'):
                needs_review_count += 1

        # FIX: единый commit после всех операций
        if needs_review_count > len(all_items) * 0.5:
            doc.parse_status = ParseStatusEnum.needs_review
        else:
            doc.parse_status = ParseStatusEnum.done

        doc.parsed_at = datetime.utcnow()
        logs.append(f"Итого: {len(all_items)} позиций, пропущено {skipped}, на ревью {needs_review_count}")
        doc.parse_log = '\n'.join(logs)
        db.commit()

    except Exception as e:
        if doc:
            doc.parse_status = ParseStatusEnum.error
            doc.parse_log = '\n'.join(logs + [f"FATAL: {e}"])
            db.commit()
        print(f"[process_document_task] Ошибка: {e}")
    finally:
        db.close()
