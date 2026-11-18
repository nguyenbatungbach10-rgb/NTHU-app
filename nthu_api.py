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
    upcoming_dates()       -> thông báo có ngày (hạn chót, ngày diễn ra) ghi trong tiêu đề sắp tới, gần nhất trước

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
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from deadline_logic import DEADLINE_WORDS, suggest_date

BASE_URL = "https://api.nthusa.tw"
CACHE_SECONDS = 300  # nhớ kết quả 5 phút để không gọi API liên tục
PER_PAGE = 20        # số thông báo mỗi trang

# Bản lưu thông báo thật, dùng khi server không gọi được API (ví dụ gói miễn phí của PythonAnywhere chặn
# api.nthusa.tw). Có 2 chỗ, web dùng bản nào MỚI HƠN:
#   data/announcements_snapshot.json      bản lưu tay (python tools/save_announcements.py), có trong git
#   instance/announcements_snapshot.json  bản GitHub Actions tự tải lên PythonAnywhere mỗi ngày
#                                         (.github/workflows/update-announcements.yml); không có trong git
SNAPSHOT_FILE = Path(__file__).parent / "data" / "announcements_snapshot.json"
LATEST_SNAPSHOT_FILE = Path(__file__).parent / "instance" / "announcements_snapshot.json"

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


# Chủ đề và từ khóa (tiếng Anh + tiếng Hoa). API không có trường chủ đề, nên ta đoán từ tiêu đề.
# Thứ tự quan trọng: chủ đề nào khớp trước thì được chọn (ví dụ "招生說明會" là Admissions, không phải Events).
# Danh sách được thử trên 4.527 thông báo thật (2026-11-18): nhóm "Other" giảm từ 71% xuống khoảng 40%.
CATEGORY_KEYWORDS = [
    ("Scholarship", ["scholarship", "scholarships", "fellowship", "grant", "grants", "financial aid",
                     "獎學金", "助學", "獎助", "補助", "獎勵金"]),
    ("Dorm", ["dorm", "dorms", "dormitory", "housing", "宿舍", "住宿"]),
    ("Careers", ["career", "careers", "internship", "intern", "recruit", "recruitment", "hiring", "job", "jobs",
                 "vacancy", "postdoc", "徵才", "招募", "實習", "求才", "就業", "誠徵", "徵聘", "工讀", "職缺", "博士後",
                 "兼任助理", "專任助理"]),
    ("Admissions", ["admission", "admissions", "招生", "入學", "甄試"]),
    ("Registration", ["registration", "add/drop", "course selection", "enrollment", "tuition", "graduation",
                      "credit transfer", "leave of absence", "選課", "加退選", "退選", "註冊", "學雜費", "畢業",
                      "學分", "學位", "抵免", "休學", "轉系", "輔系", "雙主修"]),
    ("Exchange", ["exchange", "study abroad", "交換", "出國", "海外", "雙聯"]),
    ("Campus notices", ["outage", "water supply", "water supplies", "construction", "maintenance", "disinfection",
                        "pruning", "closure", "parking", "shuttle", "停電", "停水", "施工", "修繕", "整修", "維修",
                        "消毒", "噴藥", "修剪", "管制", "封閉", "道路", "停車", "斷網", "網路中斷", "系統維護", "停機",
                        "水質", "公車", "機車證", "門禁"]),
    ("Events", ["event", "events", "lecture", "lectures", "talk", "talks", "workshop", "seminar", "competition",
                "contest", "concert", "exhibition", "festival", "forum", "symposium", "conference", "ceremony",
                "screening", "info session", "活動", "演講", "講座", "研討", "工作坊", "競賽", "比賽", "展覽", "音樂會",
                "說明會", "論壇", "營隊", "講堂", "典禮", "表演", "放映", "報名", "讀書會", "研習", "發表會"]),
]
OTHER = "Other"
CATEGORY_NAMES = [name for name, _ in CATEGORY_KEYWORDS] + [OTHER]


def _keyword_pattern(word):
    """Từ tiếng Anh phải khớp NGUYÊN TỪ ("camp" không được khớp "campus"); chữ Hán thì chỉ cần có trong tiêu đề."""
    if word.isascii():
        return re.compile(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])")
    return re.compile(re.escape(word))


_CATEGORY_PATTERNS = [(name, [_keyword_pattern(w) for w in words]) for name, words in CATEGORY_KEYWORDS]


def classify(title):
    """Đoán chủ đề của một thông báo từ tiêu đề. Không khớp từ khóa nào -> "Other"."""
    text = title.lower()  # tiếng Anh không phân biệt hoa/thường
    for category, patterns in _CATEGORY_PATTERNS:
        if any(p.search(text) for p in patterns):
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


DATE_RE = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")


def clean_date(value):
    """Ngày đăng -> "YYYY-MM-DD", hoặc "" nếu không phải ngày thật.

    Có đơn vị gửi số thứ tự ("1", "8") vào trường ngày; nếu giữ lại, "8" > "2026-..." khi so sánh chữ
    nên bài cũ bị xếp lên đầu danh sách "mới nhất". Cũng nhận "2026/11/18", "2026.11.18".
    """
    match = DATE_RE.fullmatch(str(value or "").strip())
    if not match:
        return ""
    try:
        return date(int(match[1]), int(match[2]), int(match[3])).isoformat()
    except ValueError:
        return ""                                # ví dụ 2026-02-30


def normalize(data):
    """Dàn phẳng: mỗi bài trong articles của mỗi đơn vị thành một dòng.

    Kết quả: list các dict {title, link, date, office, language, category}, mới nhất trước.
    Bỏ bài trùng (cùng đơn vị, tiêu đề và ngày): API có đơn vị gửi một bài nhiều lần.
    """
    items, seen = [], set()
    for department in find_list(data):
        if not isinstance(department, dict):
            continue
        office = str(department.get("department") or "NTHU")
        language = department.get("language") or ""
        for article in department.get("articles") or []:
            if not isinstance(article, dict) or not article.get("title"):
                continue  # bỏ qua mục hỏng hoặc không có tiêu đề
            title = str(article["title"]).strip()
            day = clean_date(article.get("date"))
            key = (office, title, day)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "title": title,
                "link": article.get("link") or "",
                "date": day,
                "office": office,
                "language": language,
                "category": classify(title),
            })
    items.sort(key=lambda a: a["date"], reverse=True)  # ngày dạng ISO nên so sánh chữ là đúng; "" xuống cuối
    return items


def make_snapshot(data, now):
    """Nội dung file bản lưu: {"saved_at": "2026-11-18 11:40", "data": <JSON gốc của API>}."""
    return {"saved_at": now.strftime("%Y-%m-%d %H:%M"), "data": data}


def load_snapshot(path=None):
    """(items, saved_at) từ file bản lưu; chưa có file, file hỏng hoặc không có thông báo nào -> (None, None).

    Không truyền path: đọc cả 2 bản lưu (SNAPSHOT_FILE, LATEST_SNAPSHOT_FILE) và lấy bản mới hơn.
    """
    if path is None:
        return newest_snapshot([_read_snapshot(SNAPSHOT_FILE), _read_snapshot(LATEST_SNAPSHOT_FILE)])
    return _read_snapshot(Path(path))


def newest_snapshot(snapshots):
    """Trong các cặp (items, saved_at), chọn cặp có saved_at lớn nhất ("2026-11-19 06:17" so được như chữ)."""
    usable = [snap for snap in snapshots if snap[0]]
    if not usable:
        return None, None
    return max(usable, key=lambda snap: snap[1])


def _read_snapshot(path):
    """Đọc một file bản lưu -> (items, saved_at) hoặc (None, None)."""
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


STALE_HOURS = 48   # bản lưu cũ hơn 2 ngày = việc tự cập nhật (GitHub Actions) có vấn đề -> hiện cảnh báo vàng


def is_stale(saved_at, now, hours=STALE_HOURS):
    """True nếu bản lưu ghi lúc `saved_at` ("2026-11-19 06:17", giờ Đài Loan) đã cũ hơn `hours` giờ.

    now: datetime giờ Đài Loan, không kèm múi giờ. Không đọc được saved_at -> coi là cũ.
    """
    try:
        saved = datetime.strptime(saved_at or "", "%Y-%m-%d %H:%M")
    except ValueError:
        return True
    return now - saved > timedelta(hours=hours)


def is_sample(notice):
    """True nếu đang hiện dữ liệu mẫu (không phải thông báo thật)."""
    return isinstance(notice, dict) and notice.get("kind") == "sample"


GROUP_PREFIX = "group:"        # giá trị ô chọn "cả nhóm", ví dụ "group:教務處"


def filter_announcements(items, office="", q="", lang="", category=""):
    """Lọc theo office (khớp chính xác, hoặc "group:教務處" = mọi đơn vị thuộc 教務處), từ khóa q
    (trong tiêu đề hoặc office), ngôn ngữ và chủ đề. Tham số nào để trống thì không lọc theo tham số đó."""
    q = q.lower().strip()
    group = office[len(GROUP_PREFIX):] if office.startswith(GROUP_PREFIX) else None
    result = []
    for item in items:
        if group is not None and office_group(item["office"]) != group:
            continue
        if office and group is None and item["office"] != office:
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


UNIT_ENDINGS = re.compile(r"處|院|室|中心")


def office_group(office):
    """Đơn vị lớn của một đơn vị: cắt sau chữ 處 / 院 / 室 / 中心 đầu tiên.

    "教務處註冊組" -> "教務處", "電機資訊學院光電工程研究所" -> "電機資訊學院",
    "國際產學營運總中心NVIDIA-..." -> "國際產學營運總中心". Không có các chữ đó (ví dụ tên tiếng Anh) -> giữ nguyên.
    """
    match = UNIT_ENDINGS.search(office)
    return office[:match.end()] if match else office


def group_offices(offices):
    """[{"name": đơn vị lớn, "offices": [các đơn vị con]}], xếp A-Z, để làm <optgroup> cho 100+ đơn vị."""
    groups = {}
    for office in offices:
        groups.setdefault(office_group(office), []).append(office)
    return [{"name": name, "offices": sorted(members)} for name, members in sorted(groups.items())]


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


# ---------- hạn chót / ngày sắp tới đọc từ tiêu đề ----------

_dates_memo = {"key": None, "rows": []}


def _all_title_dates(items, today):
    """Mọi thông báo có ngày trong tiêu đề từ hôm nay trở đi (tính một lần cho mỗi danh sách và mỗi ngày)."""
    key = (id(items), len(items), today)
    if _dates_memo["key"] == key:
        return _dates_memo["rows"]
    start = today.isoformat()
    rows = []
    for item in items:
        found = suggest_date(item["title"], item["date"] or start)   # không có ngày đăng -> hôm nay làm mốc
        if found["from_title"] and found["date"] >= start:
            due = date.fromisoformat(found["date"])
            rows.append(dict(item, due=found["date"], days_left=(due - today).days,
                             is_deadline=bool(DEADLINE_WORDS.search(item["title"]))))
    rows.sort(key=lambda r: (r["due"], r["title"]))
    _dates_memo.update(key=key, rows=rows)
    return rows


def upcoming_dates(items, today, days=60, kind=None):
    """Thông báo có ngày ghi trong tiêu đề nằm trong [hôm nay, hôm nay + days], ngày gần nhất trước.

    Mỗi kết quả là BẢN SAO có thêm: due (YYYY-MM-DD), days_left (còn mấy ngày),
    is_deadline (tiêu đề có chữ 截止 / 期限 / 日止 / deadline...: đây là HẠN CHÓT, ví dụ hạn nộp đơn).
    Không có các chữ đó thì ngày trong tiêu đề chỉ là ngày diễn ra (buổi nói chuyện, hội thảo...).

    kind: None = cả hai, "deadline" = chỉ hạn chót, "event" = chỉ sự kiện.
    """
    end = (today + timedelta(days=days)).isoformat()
    wanted = {"deadline": True, "event": False}.get(kind)
    return [row for row in _all_title_dates(items, today)
            if row["due"] <= end and (wanted is None or row["is_deadline"] == wanted)]
