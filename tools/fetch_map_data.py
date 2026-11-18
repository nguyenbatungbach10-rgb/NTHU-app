"""Tải lại dữ liệu địa điểm NTHU từ OpenStreetMap (Overpass API) vào data/nthu_osm.csv.

Chạy trên máy có internet:   python tools/fetch_map_data.py
Sau đó chạy python -m pytest để chắc dữ liệu mới vẫn đọc được, rồi commit file CSV.
Dữ liệu OpenStreetMap theo giấy phép ODbL: phải ghi "© OpenStreetMap contributors" (trang /map đã ghi).
"""
import sys
from pathlib import Path

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUT_FILE = Path(__file__).resolve().parent.parent / "data" / "nthu_osm.csv"
HEADER = "@type|@id|name|name:en|building|amenity|shop|leisure|tourism|highway|natural|building:levels|@lat|@lon"

# Mọi thứ có tên nằm trong khuôn viên (amenity=university, tên có "清華"), trừ đường đi; thêm các trạm xe buýt.
QUERY = """[out:csv(::type,::id,name,"name:en",building,amenity,shop,leisure,tourism,highway,natural,"building:levels",::lat,::lon;true;"|")][timeout:90];
area[amenity=university][name~"清華"]->.c;
(
  wr[amenity=university][name~"清華"];
  nwr(area.c)[name][!highway];
  node(area.c)[highway=bus_stop][name];
);
out center;"""


def looks_valid(text):
    """True nếu câu trả lời đúng là file CSV mong đợi (đúng dòng tiêu đề và có ít nhất một dòng dữ liệu)."""
    lines = text.strip().splitlines()
    return len(lines) >= 2 and lines[0].strip() == HEADER


def fetch(timeout=120):
    """Gửi truy vấn bằng POST (Overpass từ chối một số yêu cầu GET) và trả về nội dung CSV."""
    response = requests.post(OVERPASS_URL, data={"data": QUERY}, timeout=timeout,
                             headers={"User-Agent": "NTHU-Campus-Assistant/1.0 (I2P student project)"})
    response.raise_for_status()
    return response.text


def main():
    """Tải, kiểm tra rồi mới ghi đè file cũ (lỗi thì giữ nguyên file cũ)."""
    try:
        text = fetch()
    except requests.RequestException as error:
        print(f"Could not reach Overpass: {error}. Nothing was changed.")
        return 1
    if not looks_valid(text):
        print("Unexpected answer from Overpass. Nothing was changed.")
        return 1
    OUT_FILE.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    print(f"Saved {len(text.strip().splitlines()) - 1} rows to {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
