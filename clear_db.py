"""
Скрипт полной очистки данных БД MedPartners.

Удаляет ВСЕ строки из ВСЕХ таблиц проекта, но сохраняет структуру
(таблицы, индексы, constraints) — после очистки можно сразу начинать
заливать данные заново (например, через load_catalog.py + upload-archive).

Использует TRUNCATE ... RESTART IDENTITY CASCADE одной командой на все
таблицы сразу — это:
  - сбрасывает все данные без учёта порядка foreign key (CASCADE сам
    разберётся с зависимостями price_items -> price_documents/partners/services);
  - сбрасывает автоинкрементные счётчики (для UUID PK значения не используются,
    но если в схему добавят serial/identity — счётчики тоже обнулятся);
  - выполняется в рамках одной транзакции — либо очищается всё, либо ничего.

ВНИМАНИЕ: операция безвозвратна. Скрипт всегда требует явного
подтверждения перед удалением (см. флаг --yes для неинтерактивного запуска).

Запуск:
    python clear_db.py            # спросит подтверждение
    python clear_db.py --yes      # без вопроса (для CI/скриптов)
"""

import sys
import argparse

from sqlalchemy import text

from database import engine, Base
import models  # noqa: F401 — нужен чтобы Base.metadata знал обо всех моделях


def get_table_names() -> list[str]:
    """Возвращает имена всех таблиц, зарегистрированных в Base.metadata."""
    return [table.name for table in Base.metadata.sorted_tables]


def clear_database(skip_confirm: bool = False) -> None:
    table_names = get_table_names()

    if not table_names:
        print("Не найдено ни одной таблицы в Base.metadata. Ничего не делаю.")
        return

    print("Будут очищены (TRUNCATE) следующие таблицы:")
    for name in table_names:
        print(f"  - {name}")

    if not skip_confirm:
        answer = input(
            "\nЭто удалит ВСЕ данные из БД без возможности восстановления. "
            "Продолжить? [yes/N]: "
        ).strip().lower()
        if answer != "yes":
            print("Отменено.")
            return

    # FIX: одна команда TRUNCATE ... CASCADE на все таблицы сразу избавляет
    # от необходимости вручную сортировать порядок удаления по foreign key
    # (price_items ссылается на price_documents, partners, services,
    # и сам на себя через superseded_by).
    quoted_names = ", ".join(f'"{name}"' for name in table_names)
    sql = f"TRUNCATE TABLE {quoted_names} RESTART IDENTITY CASCADE;"

    with engine.begin() as conn:
        conn.execute(text(sql))

    print(f"\nГотово: {len(table_names)} таблиц очищено, структура БД сохранена.")


def main():
    parser = argparse.ArgumentParser(description="Полная очистка данных БД MedPartners (TRUNCATE)")
    parser.add_argument(
        "--yes", action="store_true",
        help="Не спрашивать подтверждение (для неинтерактивного запуска / CI)",
    )
    args = parser.parse_args()

    try:
        clear_database(skip_confirm=args.yes)
    except Exception as e:
        print(f"Ошибка при очистке БД: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()