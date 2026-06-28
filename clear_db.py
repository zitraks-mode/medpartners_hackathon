import sys
import argparse

from sqlalchemy import text

from database import engine, Base
import models


def get_table_names() -> list[str]:
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