"""Lưu thông báo thật từ NTHU Data API vào data/announcements_snapshot.json.

Vì sao cần: gói miễn phí của PythonAnywhere chỉ cho server gọi ra một danh sách trang, và api.nthusa.tw
không có trong đó. Khi server không gọi được API, web hiện thông báo từ bản lưu này (kèm ngày lưu).

Chạy trên máy có mạng (máy của bạn):
    python tools/save_announcements.py
    git add data/announcements_snapshot.json
    git commit -m "Update announcements snapshot"
    git push
rồi trên PythonAnywhere: cd ~/NTHU-app && git pull  (dữ liệu mới hiện sau tối đa 5 phút, hoặc bấm Reload).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nthu_api  # noqa: E402


def main():
    """Tải, kiểm tra có thông báo dùng được, rồi mới ghi file (lỗi thì giữ nguyên bản lưu cũ)."""
    try:
        response = requests.get(f"{nthu_api.BASE_URL}/announcements", timeout=30)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        print(f"Could not get announcements: {error}. Nothing was changed.")
        return 1
    items = nthu_api.normalize(data)
    if not items:
        print("The API returned no usable announcements. Nothing was changed.")
        return 1
    snapshot = nthu_api.make_snapshot(data, datetime.now())
    nthu_api.SNAPSHOT_FILE.parent.mkdir(exist_ok=True)
    nthu_api.SNAPSHOT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    # chỉ in chữ ASCII: cửa sổ PowerShell không bị lỗi vì chữ Hán
    print(f"Saved {len(items)} announcements to {nthu_api.SNAPSHOT_FILE} at {snapshot['saved_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
