import requests
import json
import os

API_BASE = "http://127.0.0.1:8080"

# catalog_data.json должен лежать рядом с этим скриптом
data_path = os.path.join(os.path.dirname(__file__), "catalog_data.json")
with open(data_path, encoding="utf-8") as f:
    entries = json.load(f)

print(f"Загружаем {len(entries)} услуг...")

BATCH = 100
total_created = 0
total_updated = 0

for i in range(0, len(entries), BATCH):
    batch = entries[i:i+BATCH]
    res = requests.post(f"{API_BASE}/catalog/upload", json=batch, timeout=30)
    if res.status_code == 200:
        d = res.json()
        total_created += d.get("created", 0)
        total_updated += d.get("updated", 0)
        print(f"Батч {i//BATCH+1}/{(len(entries)-1)//BATCH+1}: +{d.get('created')} создано, {d.get('updated')} обновлено")
    else:
        print(f"Ошибка батч {i//BATCH+1}: {res.text[:200]}")

print(f"\nГотово: {total_created} создано, {total_updated} обновлено")
