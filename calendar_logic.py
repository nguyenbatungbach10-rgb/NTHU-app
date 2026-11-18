"""Logic thuần Python cho Calendar (không có Flask, không có database).

    validate_event()  -> kiểm tra dữ liệu một sự kiện do client gửi lên
    parse_month()     -> đọc "2026-11" thành (2026, 11)
    shift_month()     -> tháng trước / tháng sau
    month_bounds()    -> ngày đầu của tháng này và tháng sau (để truy vấn SQL)
    build_month()     -> dựng lưới các tuần để vẽ lịch tháng
    parse_year()      -> đọc "2026" thành 2026 (chỉ nhận năm hợp lý)
    year_bounds()     -> ngày đầu của năm này và năm sau (để truy vấn SQL)
    build_year()      -> dựng 12 lịch tháng thu nhỏ cho trang xem cả năm
    mark_saved()      -> đánh dấu thông báo nào đã được lưu vào Calendar
    today_tw()        -> ngày hôm nay theo giờ Đài Loan (máy chủ PythonAnywhere chạy giờ UTC)
"""
import calendar
import re
from datetime import date, datetime, timedelta, timezone

from deadline_logic import suggest_date

MAX_TITLE = 200
MAX_TEXT = 1000
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MIN_YEAR, MAX_YEAR = 1970, 2100   # khoảng năm cho phép xem (tránh năm vô lý như 0001 hay 9999)


def is_iso_date(text):
    """True nếu text đúng dạng YYYY-MM-DD và là một ngày có thật."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return False
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:  # ví dụ 2026-02-30
        return False
    return True


def is_hhmm(text):
    """True nếu text đúng dạng HH:MM (00:00 đến 23:59)."""
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        return False
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        return False
    return True


def validate_event(data):
    """Kiểm tra dữ liệu sự kiện từ client.

    Trả về (event_sạch, None) nếu hợp lệ, hoặc (None, thông_báo_lỗi) nếu sai.
    Không tin dữ liệu từ client: mọi trường đều được kiểm tra kiểu và độ dài.
    """
    if not isinstance(data, dict):
        return None, "JSON body must be an object"

    title = data.get("title")
    day = data.get("date")
    if not isinstance(title, str) or not title.strip() or not isinstance(day, str) or not day:
        return None, "title and date are required"
    title = title.strip()
    if len(title) > MAX_TITLE:
        return None, f"title must be at most {MAX_TITLE} characters"
    if not is_iso_date(day):
        return None, "date must be in YYYY-MM-DD format"

    time_text = data.get("time") or ""
    if not isinstance(time_text, str) or (time_text and not is_hhmm(time_text)):
        return None, "time must be in HH:MM format"

    description = data.get("description") or ""
    if not isinstance(description, str) or len(description) > MAX_TEXT:
        return None, f"description must be text of at most {MAX_TEXT} characters"

    source_url = data.get("source_url") or ""
    if not isinstance(source_url, str) or len(source_url) > MAX_TEXT:
        return None, "source_url must be a short text"
    # Chỉ nhận http/https: chặn "javascript:..." chèn vào thẻ <a href>
    if source_url and not source_url.startswith(("http://", "https://")):
        return None, "source_url must start with http:// or https://"

    return {
        "title": title,
        "date": day,
        "time": time_text,
        "description": description.strip(),
        "source_url": source_url,
    }, None


def parse_month(text):
    """"2026-11" -> (2026, 11). Sai định dạng hoặc None -> None."""
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}", text):
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m")
    except ValueError:
        return None
    return parsed.year, parsed.month


def shift_month(year, month, delta):
    """Dịch tháng đi delta tháng (âm = lùi), xử lý đúng khi qua năm."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_bounds(year, month):
    """Ngày đầu của tháng và ngày đầu của tháng sau, dạng chuỗi ISO."""
    next_year, next_month = shift_month(year, month, 1)
    return f"{year:04d}-{month:02d}-01", f"{next_year:04d}-{next_month:02d}-01"


def month_label(year, month):
    """Ví dụ "November 2026"."""
    return date(year, month, 1).strftime("%B %Y")


def build_month(year, month, events, today, tasks=()):
    """Dựng lưới lịch tháng: list các tuần, mỗi tuần 7 ô (Thứ 2 đến Chủ nhật).

    Ô ngoài tháng là None. Ô trong tháng là dict:
        {"day", "iso", "events": [...], "tasks": [...], "is_today"}
    Sự kiện trong một ngày xếp theo giờ (sự kiện cả ngày trước).
    `tasks` là các việc cần làm CHƯA XONG có hạn nộp (từ trang Study); mỗi việc được
    thêm `overdue` = hạn nộp đã qua. Việc chỉ để xem, sửa ở trang Study.
    """
    by_day = {}
    for event in events:
        by_day.setdefault(event["date"], []).append(event)

    tasks_by_day = {}
    for task in tasks:
        item = dict(task, overdue=task["due_date"] < today.isoformat())  # copy, không sửa bản gốc
        tasks_by_day.setdefault(task["due_date"], []).append(item)

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:  # ô trống ở đầu hoặc cuối tháng
                row.append(None)
                continue
            iso = date(year, month, day).isoformat()
            day_events = sorted(by_day.get(iso, []), key=lambda e: (e["time"], e["id"]))
            row.append({
                "day": day,
                "iso": iso,
                "events": day_events,
                "tasks": sorted(tasks_by_day.get(iso, []), key=lambda t: t["id"]),
                "is_today": iso == today.isoformat(),
            })
        weeks.append(row)
    return weeks


TAIWAN_TZ = timezone(timedelta(hours=8), "Asia/Taipei")   # Đài Loan không đổi giờ mùa hè


def today_tw(now=None):
    """Ngày hôm nay ở Đài Loan (UTC+8), dù máy chủ đặt ở múi giờ nào.

    Máy chủ PythonAnywhere chạy giờ UTC: nếu dùng date.today() thì từ 0:00 đến 8:00 sáng ở Đài Loan
    web vẫn tưởng là hôm qua. `now` để test truyền một thời điểm cố định.
    """
    now = now or datetime.now(timezone.utc)
    return now.astimezone(TAIWAN_TZ).date()


def parse_year(text):
    """"2026" -> 2026. Sai định dạng, None hoặc ngoài khoảng MIN_YEAR..MAX_YEAR -> None."""
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}", text):
        return None
    year = int(text)
    return year if MIN_YEAR <= year <= MAX_YEAR else None


def year_bounds(year):
    """Ngày đầu của năm và ngày đầu của năm sau, dạng chuỗi ISO."""
    return f"{year:04d}-01-01", f"{year + 1:04d}-01-01"


def build_year(year, events, today, tasks=()):
    """Dựng 12 lịch tháng thu nhỏ của một năm.

    Mỗi tháng: {"month", "name", "iso" ("2026-03"), "weeks", "count", "is_current"}.
    Mỗi ô ngày trong `weeks`: {"day", "iso", "count", "is_today"}, với `count` là số sự kiện
    cộng số việc cần làm (chưa xong) có hạn trong ngày đó. Ô ngoài tháng là None.
    `count` của tháng là tổng của các ngày. Không sửa dữ liệu đầu vào.
    """
    per_day = {}
    for item in events:
        per_day[item["date"]] = per_day.get(item["date"], 0) + 1
    for task in tasks:
        per_day[task["due_date"]] = per_day.get(task["due_date"], 0) + 1

    today_iso = today.isoformat()
    months = []
    for month in range(1, 13):
        weeks, total = [], 0
        for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
            row = []
            for day in week:
                if day == 0:
                    row.append(None)
                    continue
                iso = date(year, month, day).isoformat()
                count = per_day.get(iso, 0)
                total += count
                row.append({"day": day, "iso": iso, "count": count, "is_today": iso == today_iso})
            weeks.append(row)
        months.append({
            "month": month,
            "name": date(year, month, 1).strftime("%B"),
            "iso": f"{year:04d}-{month:02d}",
            "weeks": weeks,
            "count": total,
            "is_current": (year, month) == (today.year, today.month),
        })
    return months


def shorten_title(title):
    """Cắt tiêu đề thông báo cho vừa giới hạn tiêu đề sự kiện."""
    if len(title) <= MAX_TITLE:
        return title
    return title[:MAX_TITLE - 1] + "…"


def mark_saved(items, saved, today=None):
    """Trả về BẢN SAO của items, thêm `event_title`, `event_date`, `date_from_title`, `saved`.

    `event_date` là ngày sẽ lưu vào lịch: ngày đọc được từ tiêu đề (deadline_logic), hoặc ngày đăng.
    Thông báo KHÔNG có ngày đăng (khoảng 60% dữ liệu thật) vẫn lưu được nếu tiêu đề có ngày: khi đó
    dùng `today` làm mốc để đoán năm. Không có ngày nào thì `event_date` = "" (nút lưu bị khóa).
    `saved` là tập các cặp (tiêu đề sự kiện, ngày) mà người dùng đã lưu.
    Phải copy (dict(item, ...)) vì danh sách gốc nằm trong cache dùng chung
    cho mọi người dùng; sửa trực tiếp sẽ làm lộ trạng thái của người này sang người khác.
    """
    result = []
    for item in items:
        event_title = shorten_title(item["title"])
        if item["date"]:
            suggestion = suggest_date(item["title"], item["date"])
        else:
            suggestion = suggest_date(item["title"], today.isoformat()) if today else {"from_title": False}
            if not suggestion["from_title"]:
                suggestion = {"date": "", "from_title": False}
        result.append(dict(
            item,
            event_title=event_title,
            event_date=suggestion["date"],
            date_from_title=suggestion["from_title"],
            saved=(event_title, suggestion["date"]) in saved,
        ))
    return result


# ---------- Tuần + lịch trong ngày (giao diện điện thoại, giống mockup) ----------

def parse_day(text):
    """"2026-11-20" -> date; sai định dạng hoặc ngoài MIN_YEAR..MAX_YEAR -> None."""
    if not is_iso_date(text or ""):
        return None
    day = date.fromisoformat(text)
    return day if MIN_YEAR <= day.year <= MAX_YEAR else None


def week_start(day):
    """Thứ Hai của tuần chứa `day`."""
    return day - timedelta(days=day.weekday())


def day_counts(day, classes, events, tasks):
    """Đếm lớp / sự kiện / hạn chót của một ngày -> {"class": n, "event": n, "deadline": n}."""
    iso = day.isoformat()
    return {"class": sum(1 for c in classes if c["weekday"] == day.weekday()),
            "event": sum(1 for e in events if e["date"] == iso),
            "deadline": sum(1 for t in tasks if t["due_date"] == iso)}


def week_strip(selected, today, classes, events, tasks):
    """7 ngày (Thứ 2 -> CN) của tuần chứa `selected`, mỗi ngày kèm số lớp / sự kiện / hạn chót (để vẽ chấm màu)."""
    first = week_start(selected)
    days = []
    for offset in range(7):
        day = first + timedelta(days=offset)
        days.append({"iso": day.isoformat(), "day": day.day, "weekday": day.weekday(),
                     "is_today": day == today, "is_selected": day == selected,
                     "counts": day_counts(day, classes, events, tasks)})
    return days


def day_agenda(day, classes, events, tasks):
    """Mọi thứ của một ngày trong MỘT danh sách (giống "Today's schedule" của mockup).

    Mỗi mục: {"kind": "class" | "event" | "deadline", "start", "end", "title", "sub", "data"}.
    Thứ tự: sự kiện cả ngày trước, rồi các mục có giờ theo giờ, hạn chót (việc cần làm) cuối cùng.
    """
    iso = day.isoformat()
    timed, all_day, due = [], [], []
    for c in classes:
        if c["weekday"] == day.weekday():
            timed.append({"kind": "class", "start": c["start"], "end": c["end"], "title": c["name"],
                          "sub": c.get("room", ""), "data": c})
    for e in events:
        if e["date"] == iso:
            item = {"kind": "event", "start": e["time"], "end": "", "title": e["title"],
                    "sub": e.get("description", ""), "data": e}
            (timed if e["time"] else all_day).append(item)
    for t in tasks:
        if t["due_date"] == iso:
            due.append({"kind": "deadline", "start": "", "end": "", "title": t["title"], "sub": "", "data": t})
    timed.sort(key=lambda item: (item["start"], item["kind"] != "class", item["title"]))
    return all_day + timed + due


def agenda_summary(agenda):
    """Số mục theo loại cho các chip "3 classes · 2 events · 1 deadline" (bỏ loại có 0 mục)."""
    counts = {"class": 0, "event": 0, "deadline": 0}
    for item in agenda:
        counts[item["kind"]] += 1
    return [(kind, n) for kind, n in counts.items() if n]
