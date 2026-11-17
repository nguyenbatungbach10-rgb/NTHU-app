"""Logic thuần Python cho Calendar (không có Flask, không có database).

    validate_event()  -> kiểm tra dữ liệu một sự kiện do client gửi lên
    parse_month()     -> đọc "2026-11" thành (2026, 11)
    shift_month()     -> tháng trước / tháng sau
    month_bounds()    -> ngày đầu của tháng này và tháng sau (để truy vấn SQL)
    build_month()     -> dựng lưới các tuần để vẽ lịch tháng
    mark_saved()      -> đánh dấu thông báo nào đã được lưu vào Calendar
"""
import calendar
import re
from datetime import date, datetime

MAX_TITLE = 200
MAX_TEXT = 1000
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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


def shorten_title(title):
    """Cắt tiêu đề thông báo cho vừa giới hạn tiêu đề sự kiện."""
    if len(title) <= MAX_TITLE:
        return title
    return title[:MAX_TITLE - 1] + "…"


def mark_saved(items, saved):
    """Trả về BẢN SAO của items, thêm `event_title` và `saved` cho mỗi thông báo.

    `saved` là tập các cặp (tiêu đề sự kiện, ngày) mà người dùng đã lưu.
    Phải copy (dict(item, ...)) vì danh sách gốc nằm trong cache dùng chung
    cho mọi người dùng; sửa trực tiếp sẽ làm lộ trạng thái của người này sang người khác.
    """
    result = []
    for item in items:
        event_title = shorten_title(item["title"])
        result.append(dict(
            item,
            event_title=event_title,
            saved=(event_title, item["date"]) in saved,
        ))
    return result
