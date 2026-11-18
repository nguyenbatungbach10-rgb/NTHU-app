"""Lấy và xử lý dữ liệu announcements từ NTHU Data API.

File này chỉ chứa logic Python (không có Flask) để dễ test và dễ giải thích:
    fetch_announcements()  -> gọi API, trả về (danh sách, trạng thái); API lỗi thì dùng bản lưu, rồi dữ liệu mẫu
    load_snapshot()        -> đọc bản lưu data/announcements_snapshot.json (tạo bằng tools/save_announcements.py)
    make_snapshot()        -> nội dung bản lưu: thời điểm lưu + JSON gốc của API
    normalize()            -> "dàn phẳng" JSON thành danh sách thông báo
    classify()             -> đoán chủ đề (Scholarship, Dorm...) từ tiêu đề
    filter_announcements() -> lọc theo office, từ khóa, ngôn ngữ, chủ đề
    paginate()             -> cắt danh sách thành từng trang
    list_offices()         -> danh sách office để đổ vào ô chọn
    category_counts()      -> số thông báo của từng chủ đề

Cấu trúc JSON thật của GET /announcements (mỗi phần tử là MỘT ĐƠN VỊ):
    [
      {
        "title": "最新消息",            <- tên mục tin của đơn vị (không dùng)
        "link": "https://...",           <- trang tin của đơn vị
        "language": "zh-tw",             <- "zh-tw" hoặc "en"
        "department": "教務處",           <- tên đơn vị (office)
        "articles": [                    <- các thông báo thật nằm ở đây
          {"title": "...", "link": "https://...", "date": "2026-10-30"}
        ]
      }
    ]
"""
import json
import math
import time
from pathlib import Path

import requests

BASE_URL = "https://api.nthusa.tw"
CACHE_SECONDS = 300  # nhớ kết quả 5 phút để không gọi API liên tục
PER_PAGE = 20        # số thông báo mỗi trang

# Bản lưu thông báo thật, dùng khi server không gọi được API (ví dụ gói miễn phí của PythonAnywhere chặn
# api.nthusa.tw). Tạo/cập nhật trên máy có mạng: python tools/save_announcements.py, rồi commit file này.
SNAPSHOT_FILE = Path(__file__).parent / "data" / "announcements_snapshot.json"

# Bộ nhớ tạm: kết quả lần gần nhất (kể cả khi phải dùng bản lưu) để không gọi API ở mọi request
_cache = {"time": 0.0, "items": [], "notice": None}

# Dữ liệu mẫu: hiện ra khi không gọi được API (mất mạng, API lỗi...)
# để trang vẫn chạy được lúc demo.
SAMPLE_ANNOUNCEMENTS = [
    {"title": "[Sample] Scholarship application for spring semester, deadline Dec 5",
     "link": "https://www.nthu.edu.tw/", "date": "2026-11-20",
     "office": "Office of Student Affairs", "language": "en"},
    {"title": "[Sample] Course add/drop period reminder (115.11.25)",
     "link": "https://www.nthu.edu.tw/", "date": "2026-11-18",
     "office": "Division of Registrar", "language": "en"},
    {"title": "[Sample] Dormitory application for next semester",
     "link": "https://www.nthu.edu.tw/", "date": "2026-11-15",
     "office": "Office of Student Housing", "language": "en"},
    {"title": "[Sample] Campus career fair registration open",
     "link": "https://www.nthu.edu.tw/", "date": "2026-11-12",
     "office": "Career Center", "language": "en"},
]


# Chủ đề và từ khóa (tiếng Anh + tiếng Hoa). API không có trường chủ đề,
# nên ta đoán từ tiêu đề. Thứ tự quan trọng: chủ đề nào khớp trước thì được chọn.
CATEGORY_KEYWORDS = [
    ("Scholarship", ["scholarship", "fellowship", "獎學金", "助學", "獎助"]),
    ("Dorm", ["dorm", "housing", "宿舍", "住宿"]),
    ("Careers", ["career", "internship", "recruit", "hiring",
                 "徵才", "招募", "實習", "求才", "就業"]),
    ("Registration", ["registration", "add/drop", "course selection", "enrollment",
                      "選課", "加退選", "退選", "註冊"]),
    ("Events", ["event", "lecture", "talk", "workshop", "seminar", "competition",
                "concert", "exhibition", "festival",
                "活動", "演講", "講座", "研討", "工作坊", "競賽", "比賽", "展覽", "音樂會"]),
]
OTHER = "Other"


def classify(title):
    """Đoán chủ đề của một thông báo từ tiêu đề. Không khớp từ khóa nào -> "Other"."""
    text = title.lower()  # tiếng Anh không phân biệt hoa/thường
    for category, words in CATEGORY_KEYWORDS:
        if any(word in text for word in words):
            return category
    return OTHER


# Gán chủ đề cho dữ liệu mẫu (định nghĩa SAMPLE_ANNOUNCEMENTS ở trên, classify ở đây)
for _item in SAMPLE_ANNOUNCEMENTS:
    _item["category"] = classify(_item["title"])


def find_list(data):
    """Lấy danh sách đơn vị từ JSON (list thẳng, hoặc nằm trong một dict)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return value
    return []


def normalize(data):
    """Dàn phẳng: mỗi bài trong articles của mỗi đơn vị thành một dòng.

    Kết quả: list các dict {title, link, date, office, language}, mới nhất trước.
    """
    items = []
    for department in find_list(data):
        if not isinstance(department, dict):
            continue
        office = str(department.get("department") or "NTHU")
        language = department.get("language") or ""
        for article in department.get("articles") or []:
            if not isinstance(article, dict) or not article.get("title"):
                continue  # bỏ qua mục hỏng hoặc không có tiêu đề
            items.append({
                "title": str(article["title"]),
                "link": article.get("link") or "",
                "date": article.get("date") or "",
                "office": office,
                "language": language,
                "category": classify(str(article["title"])),
            })
    items.sort(key=lambda a: a["date"], reverse=True)  # ngày dạng ISO nên so sánh chữ là đúng
    return items


def make_snapshot(data, now):
    """Nội dung file bản lưu: {"saved_at": "2026-11-18 11:40", "data": <JSON gốc của API>}."""
    return {"saved_at": now.strftime("%Y-%m-%d %H:%M"), "data": data}


def load_snapshot(path=None):
    """(items, saved_at) từ file bản lưu; chưa có file, file hỏng hoặc không có thông báo nào -> (None, None)."""
    path = Path(path) if path else SNAPSHOT_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    items = normalize(payload.get("data"))
    saved_at = payload.get("saved_at")
    if not items:
        return None, None
    return items, saved_at if isinstance(saved_at, str) else ""


def _remember(items, notice, now):
    """Lưu vào bộ nhớ tạm rồi trả về (items, notice)."""
    _cache.update(time=now, items=items, notice=notice)
    return items, notice


def fetch_announcements():
    """Lấy thông báo. Trả về (items, notice):
        notice = None                                    -> dữ liệu trực tiếp từ API
        notice = {"kind": "snapshot", "saved_at", "reason"} -> API lỗi, dùng bản lưu (vẫn là thông báo thật)
        notice = {"kind": "sample", "reason"}             -> API lỗi và chưa có bản lưu: dữ liệu mẫu
    Kết quả được nhớ CACHE_SECONDS giây, kể cả khi lỗi, để không gọi API (và chờ lỗi) ở mọi request.
    """
    now = time.time()
    if _cache["items"] and now - _cache["time"] < CACHE_SECONDS:
        return _cache["items"], _cache["notice"]

    try:
        response = requests.get(f"{BASE_URL}/announcements", timeout=15)
        response.raise_for_status()          # lỗi 4xx/5xx -> ném exception
        items = normalize(response.json())   # JSON -> list các dict
        reason = "The NTHU Data API returned no usable data."
    except (requests.RequestException, ValueError) as exc:
        print("[nthu_api] API error:", exc)  # chi tiết lỗi hiện trong terminal / error log
        items, reason = [], "Could not reach the NTHU Data API."

    if items:
        return _remember(items, None, now)
    saved, saved_at = load_snapshot()
    if saved:
        return _remember(saved, {"kind": "snapshot", "saved_at": saved_at, "reason": reason}, now)
    return _remember(SAMPLE_ANNOUNCEMENTS, {"kind": "sample", "reason": reason}, now)


def is_sample(notice):
    """True nếu đang hiện dữ liệu mẫu (không phải thông báo thật)."""
    return isinstance(notice, dict) and notice.get("kind") == "sample"


def filter_announcements(items, office="", q="", lang="", category=""):
    """Lọc theo office (khớp chính xác), từ khóa q (trong tiêu đề hoặc office),
    ngôn ngữ và chủ đề. Tham số nào để trống thì không lọc theo tham số đó."""
    q = q.lower().strip()
    result = []
    for item in items:
        if office and item["office"] != office:
            continue
        if lang and item["language"] != lang:
            continue
        if category and item.get("category") != category:
            continue
        if q and q not in item["title"].lower() and q not in item["office"].lower():
            continue
        result.append(item)
    return result


def list_offices(items):
    """Danh sách office không trùng, xếp A-Z."""
    return sorted({item["office"] for item in items})


def category_counts(items):
    """Trả về [(chủ đề, số thông báo), ...] theo thứ tự cố định, bỏ chủ đề có 0 mục."""
    names = [name for name, _ in CATEGORY_KEYWORDS] + [OTHER]
    counts = {name: 0 for name in names}
    for item in items:
        name = item.get("category", OTHER)
        counts[name] = counts.get(name, 0) + 1
    return [(name, counts[name]) for name in names if counts[name]]


def paginate(items, page, per_page=PER_PAGE):
    """Cắt danh sách thành trang. Trả về (các mục của trang, số trang hợp lệ, tổng số trang)."""
    total_pages = max(1, math.ceil(len(items) / per_page))
    page = min(max(page, 1), total_pages)  # ép page nằm trong khoảng 1..total_pages
    start = (page - 1) * per_page
    return items[start:start + per_page], page, total_pages
