"""Xuất lịch ra file .ics (chuẩn iCalendar, RFC 5545) để Google Calendar / Apple Calendar tự đồng bộ.

Cách hoạt động: mỗi người có một link bí mật /calendar/feed/<token>.ics. Dán link vào Google Calendar
("Add calendar > From URL") hoặc bấm trên iPhone (webcal://...), ứng dụng lịch sẽ tự tải lại link này
định kỳ (Google: vài tiếng một lần, Apple: tùy cài đặt). Đây là đồng bộ MỘT CHIỀU: web -> ứng dụng lịch.

File .ics là chữ thường, mỗi dòng "TÊN:giá trị", ví dụ:
    BEGIN:VEVENT
    UID:class-3@nthu-campus-assistant
    DTSTART:20261119T000000Z          <- 08:00 giờ Đài Loan = 00:00 giờ UTC
    RRULE:FREQ=WEEKLY;UNTIL=...       <- lặp lại mỗi tuần (lớp học)
    SUMMARY:計算機程式設計
    END:VEVENT
"""
from datetime import date, datetime, timedelta

PRODUCT = "-//NTHU Campus Assistant//I2P Final Project//EN"
UID_DOMAIN = "nthu-campus-assistant"
TAIPEI_OFFSET = timedelta(hours=8)        # Đài Loan luôn là UTC+8 (không đổi giờ mùa hè)
EVENT_LENGTH = timedelta(hours=1)         # sự kiện có giờ nhưng không có giờ kết thúc: coi là 1 tiếng
MAX_LINE = 75                             # chuẩn iCalendar: mỗi dòng tối đa 75 byte, dài hơn thì gập dòng


def escape_text(text):
    """Thoát ký tự đặc biệt của iCalendar: \\ ; , và xuống dòng."""
    return (str(text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def fold_line(line):
    """Gập dòng dài: cắt theo BYTE UTF-8 (chữ Hán 3 byte) không cắt giữa một chữ; dòng sau bắt đầu bằng dấu cách."""
    parts, current = [], ""
    for char in line:
        limit = MAX_LINE if not parts else MAX_LINE - 1     # dòng tiếp theo có thêm 1 dấu cách ở đầu
        if len((current + char).encode("utf-8")) > limit:
            parts.append(current)
            current = char
        else:
            current += char
    parts.append(current)
    return "\r\n ".join(parts)


def utc_stamp(day, hhmm):
    """Ngày + giờ Đài Loan -> chuỗi UTC "20261119T000000Z"."""
    hour, minute = (int(x) for x in hhmm.split(":"))
    moment = datetime(day.year, day.month, day.day, hour, minute) - TAIPEI_OFFSET
    return moment.strftime("%Y%m%dT%H%M%SZ")


def semester_end(today):
    """Ngày cuối (ước lượng) của học kỳ hiện tại để lớp học ngừng lặp lại.

    Học kỳ 1 (tháng 8 -> tháng 1): tới 20/1. Học kỳ 2 (tháng 2 -> tháng 7): tới 30/6.
    Đây chỉ là ước lượng; sang học kỳ mới thì nhập lại thời khóa biểu là xong.
    """
    if today.month >= 8:
        return date(today.year + 1, 1, 20)
    if today.month == 1:
        return date(today.year, 1, 20)
    return date(today.year, 6, 30)


def first_class_day(today, weekday):
    """Ngày đầu tiên đưa lên lịch của một lớp: thứ `weekday` trong tuần hiện tại."""
    return today - timedelta(days=today.weekday()) + timedelta(days=weekday)


def class_event(item, today, stamp):
    """Một lớp học -> VEVENT lặp lại mỗi tuần tới hết học kỳ."""
    day = first_class_day(today, item["weekday"])
    until = semester_end(today)
    return [
        "BEGIN:VEVENT", f"UID:class-{item['id']}@{UID_DOMAIN}", f"DTSTAMP:{stamp}",
        f"DTSTART:{utc_stamp(day, item['start'])}", f"DTEND:{utc_stamp(day, item['end'])}",
        f"RRULE:FREQ=WEEKLY;UNTIL={until.strftime('%Y%m%d')}T155959Z",
        f"SUMMARY:{escape_text(item['name'])}",
        *([f"LOCATION:{escape_text(item['room'])}"] if item.get("room") else []),
        "END:VEVENT",
    ]


def calendar_event(item, stamp):
    """Một sự kiện của trang Calendar -> VEVENT (cả ngày nếu không có giờ)."""
    day = date.fromisoformat(item["date"])
    if item.get("time"):
        start = datetime.strptime(f"{item['date']} {item['time']}", "%Y-%m-%d %H:%M") - TAIPEI_OFFSET
        when = [f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTEND:{(start + EVENT_LENGTH).strftime('%Y%m%dT%H%M%SZ')}"]
    else:
        when = [f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}"]
    return [
        "BEGIN:VEVENT", f"UID:event-{item['id']}@{UID_DOMAIN}", f"DTSTAMP:{stamp}", *when,
        f"SUMMARY:{escape_text(item['title'])}",
        *([f"DESCRIPTION:{escape_text(item['description'])}"] if item.get("description") else []),
        *([f"URL:{item['source_url']}"] if item.get("source_url", "").startswith(("http://", "https://")) else []),
        "END:VEVENT",
    ]


def task_event(item, stamp, label):
    """Một việc cần làm có hạn nộp -> sự kiện cả ngày vào ngày hạn. label ví dụ "Due: {title}"."""
    day = date.fromisoformat(item["due_date"])
    return [
        "BEGIN:VEVENT", f"UID:task-{item['id']}@{UID_DOMAIN}", f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{escape_text(label.format(title=item['title']))}",
        "END:VEVENT",
    ]


def build_calendar(name, today, now_utc, classes=(), events=(), tasks=(), task_label="Due: {title}"):
    """Toàn bộ nội dung file .ics (chuỗi, xuống dòng CRLF như chuẩn yêu cầu)."""
    stamp = now_utc.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODUCT}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{escape_text(name)}", "X-WR-TIMEZONE:Asia/Taipei",
             "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H"]
    for item in classes:
        lines += class_event(item, today, stamp)
    for item in events:
        lines += calendar_event(item, stamp)
    for item in tasks:
        lines += task_event(item, stamp, task_label)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"
