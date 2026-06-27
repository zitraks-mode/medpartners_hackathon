from parsers import parse_xlsx

# Вставь сюда путь к любому твоему тестовому XLSX файлу
test_file = "extracted\\Хакатон\\Хакатон\\Клиника 6 прайс 2026.xlsx" 

results = parse_xlsx(test_file)

print(f"Найдено позиций: {len(results)}")
for item in results[:5]:
    print(item)