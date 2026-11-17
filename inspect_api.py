"""Script kiểm tra: xem NTHU Data API trả về JSON có cấu trúc thế nào.

Chạy:  python inspect_api.py
Script in tóm tắt ra màn hình và lưu cấu trúc rút gọn vào file api_sample.json.
Gửi file api_sample.json đó cho người viết code để chỉnh nthu_api.py.
"""
import json

import requests

URL = "https://api.nthusa.tw/announcements"


def shorten(obj, limit=3):
    """Giữ tối đa `limit` phần tử mỗi danh sách (kể cả danh sách lồng nhau)."""
    if isinstance(obj, list):
        return [shorten(x, limit) for x in obj[:limit]]
    if isinstance(obj, dict):
        return {k: shorten(v, limit) for k, v in obj.items()}
    return obj


response = requests.get(URL, timeout=20)
print("Status code:", response.status_code)

data = response.json()
print("Top-level type:", type(data).__name__)

if isinstance(data, dict):
    print("Top-level keys:", list(data.keys()))
    items = next((v for v in data.values() if isinstance(v, list)), [])
else:
    items = data

print("Number of items:", len(items))
if items and isinstance(items[0], dict):
    print("Keys of first item:", list(items[0].keys()))

# ensure_ascii=True: console không bao giờ lỗi vì chữ Hán
print(json.dumps(shorten(items[:1]), ensure_ascii=True, indent=2)[:2000])

with open("api_sample.json", "w", encoding="utf-8") as f:
    json.dump(shorten(data), f, ensure_ascii=False, indent=2)
print("Saved api_sample.json")
