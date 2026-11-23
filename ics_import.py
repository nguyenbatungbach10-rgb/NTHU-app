"""Đọc lịch từ Google Calendar (hoặc iCloud / Outlook) để hiện NGAY TRONG app (Python thuần, dễ test).

Google Calendar cho mỗi lịch một "Secret address in iCal format" (link bí mật dạng .ics). Người dùng dán link đó vào
trang Account; server tải file .ics về, đọc các sự kiện (kể cả sự kiện lặp lại) và hiện trên trang Calendar.
Nếu server không tải được (PythonAnywhere chặn), người dùng có thể tải file .ics lên.

File .ics là chữ, mỗi dòng "TÊN;tham số:giá trị", sự kiện nằm giữa BEGIN:VEVENT và END:VEVENT, ví dụ:
    BEGIN:VEVENT
    DTSTART;TZID=Asia/Taipei:20261119T080000     <- 08:00 ngày 19/11/2026 giờ Đài Loan
    RRULE:FREQ=WEEKLY;BYDAY=MO,TH;UNTIL=20270120T155959Z   <- lặp lại thứ 2 và thứ 5 hằng tuần
    SUMMARY:Calculus
    END:VEVENT
"""
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
except ImportError:                       # Python quá cũ: coi mọi giờ là giờ Đài Loan
    ZoneInfo = None

TAIPEI = timezone(timedelta(hours=8), "Asia/Taipei")
DAYS_BEFORE, DAYS_AFTER = 30, 180         # chỉ lấy sự kiện từ 30 ngày trước tới 180 ngày sau
MAX_EVENTS = 3000                         # file quá lớn thì cắt bớt (giữ web nhanh)
MAX_REPEATS = 1000                        # một sự kiện lặp lại tối đa 1000 lần trong cửa sổ
MAX_TITLE = 200
WEEKDAY_CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

# Chỉ tải link từ các dịch vụ lịch này. Nếu server tải link BẤT KỲ, kẻ xấu có thể bắt server gọi tới địa chỉ
# nội bộ / trang lạ thay họ (lỗi bảo mật gọi là SSRF).
ALLOWED_HOSTS = ("calendar.google.com", "outlook.office365.com", "outlook.live.com")
ALLOWED_SUFFIXES = (".icloud.com",)


# ---------- link ----------

def host_allowed(host):
    """Tên máy chủ có nằm trong danh sách dịch vụ lịch được phép không."""
    host = (host or "").lower()
    return host in ALLOWED_HOSTS or any(host.endswith(suffix) for suffix in ALLOWED_SUFFIXES)


def normalize_feed_url(text):
    """Kiểm tra link người dùng dán vào -> (url https, None) hoặc (None, câu báo lỗi tiếng Anh).

    webcal:// (link của Apple) đổi thành https://. Chỉ nhận https và các máy chủ trong ALLOWED_HOSTS.
    """
    url = (text or "").strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    if len(url) > 2000:
        return None, "That link is too long."
    parts = urlparse(url)
    if parts.scheme != "https" or not parts.hostname:
        return None, "Paste a link that starts with https:// or webcal://."
    if not host_allowed(parts.hostname) or parts.port not in (None, 443) or parts.username or parts.password:
        return None, "Only Google Calendar, iCloud and Outlook calendar links are supported."
    return url, None


# ---------- đọc file .ics ----------

def unfold(text):
    """Nối các dòng bị gập (dòng bắt đầu bằng dấu cách/tab là phần tiếp theo của dòng trước)."""
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def parse_line(line):
    """"DTSTART;TZID=Asia/Taipei:20261119T080000" -> ("DTSTART", {"TZID": "Asia/Taipei"}, "20261119T080000")."""
    head, _, value = line.partition(":")
    name, *params = head.split(";")
    options = {}
    for param in params:
        key, _, val = param.partition("=")
        options[key.upper()] = val.strip('"')
    return name.upper(), options, value


def unescape(value):
    """Bỏ ký tự thoát của iCalendar: \\n -> xuống dòng, \\, -> , ..."""
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m[1] in "nN" else m[1], value)


def _zone(tzid):
    """Múi giờ theo tên ("Asia/Taipei", "America/New_York"); không biết -> giờ Đài Loan."""
    if tzid and ZoneInfo is not None:
        try:
            return ZoneInfo(tzid)
        except Exception:                 # noqa: BLE001 - tên lạ, hoặc Windows không có dữ liệu múi giờ
            pass
    return TAIPEI


def parse_when(value, options):
    """Giá trị DTSTART / DTEND -> (datetime giờ Đài Loan không kèm múi giờ, cả_ngày). Sai định dạng -> (None, False)."""
    value = value.strip()
    try:
        if options.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
            return datetime.strptime(value[:8], "%Y%m%d"), True
        moment = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    except ValueError:
        return None, False
    if value.endswith("Z"):
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.replace(tzinfo=_zone(options.get("TZID")))   # không có TZID: coi là giờ Đài Loan
    return moment.astimezone(TAIPEI).replace(tzinfo=None), False


def parse_duration(value):
    """"PT1H30M" / "P1D" -> timedelta; sai -> None."""
    m = re.fullmatch(r"([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value.strip())
    if not m:
        return None
    weeks, days, hours, minutes, seconds = (int(x or 0) for x in m.groups()[1:])
    return timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)


def parse_rrule(value):
    """"FREQ=WEEKLY;BYDAY=MO,TH;COUNT=10" -> {"FREQ": "WEEKLY", "BYDAY": "MO,TH", "COUNT": "10"}."""
    return {k.upper(): v for k, _, v in (part.partition("=") for part in value.split(";")) if k}


def read_events(lines):
    """Các khối VEVENT -> list dict thô {name: [(options, value), ...]} (bỏ qua VTIMEZONE, VALARM...)."""
    events, current, depth = [], None, 0
    for line in lines:
        name, options, value = parse_line(line)
        if name == "BEGIN" and value.upper() == "VEVENT":
            current, depth = {}, 0
        elif current is not None and name == "BEGIN":
            depth += 1                    # khối con (VALARM) bên trong sự kiện
        elif current is not None and name == "END" and value.upper() == "VEVENT":
            events.append(current)
            current = None
        elif current is not None and name == "END":
            depth -= 1
        elif current is not None and depth == 0:
            current.setdefault(name, []).append((options, value))
    return events


# ---------- lặp lại (RRULE) ----------

def _add_months(moment, months):
    """Cộng tháng, giữ ngày; ngày không tồn tại (31/2) -> None."""
    year, month = divmod(moment.month - 1 + months, 12)
    try:
        return moment.replace(year=moment.year + year, month=month + 1)
    except ValueError:
        return None


def occurrences(start, rule, window_end, exdates):
    """Các lần diễn ra (datetime giờ Đài Loan) của một sự kiện lặp lại, tới window_end.

    Hỗ trợ FREQ=DAILY/WEEKLY/MONTHLY/YEARLY, INTERVAL, COUNT, UNTIL, BYDAY (với WEEKLY) và EXDATE (ngày bỏ).
    """
    freq = rule.get("FREQ", "").upper()
    interval = max(1, int(rule.get("INTERVAL", "1") or 1)) if rule.get("INTERVAL", "1").isdigit() else 1
    count = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    until = parse_when(rule["UNTIL"], {})[0] if rule.get("UNTIL") else None
    last = min(window_end, until) if until else window_end
    if freq == "WEEKLY":
        days = [WEEKDAY_CODES.index(d[-2:]) for d in rule.get("BYDAY", "").split(",") if d[-2:] in WEEKDAY_CODES]
        days = sorted(set(days)) or [start.weekday()]
    result, made, step = [], 0, 0
    while made < MAX_REPEATS:
        if freq == "DAILY":
            batch = [start + timedelta(days=step * interval)]
        elif freq == "WEEKLY":
            week = start - timedelta(days=start.weekday()) + timedelta(weeks=step * interval)
            batch = [week + timedelta(days=d) for d in days]
        elif freq == "MONTHLY":
            batch = [_add_months(start, step * interval)]
        elif freq == "YEARLY":
            batch = [_add_months(start, 12 * step * interval)]
        else:
            return [start]                # kiểu lặp không hỗ trợ: chỉ lấy lần đầu
        step += 1
        for moment in batch:
            if moment is None or moment < start:
                continue
            if moment > last or (count is not None and made >= count):
                return result
            made += 1
            if moment not in exdates:
                result.append(moment)
    return result


# ---------- kết quả cho trang Calendar ----------

def _first(raw, name):
    """Giá trị đầu tiên của một trường (options, value) hoặc ({}, "")."""
    return raw.get(name, [({}, "")])[0]


def event_rows(raw, window_start, window_end, skip):
    """Một sự kiện thô -> các dòng {date, time, end_time, title, location} trong cửa sổ thời gian."""
    if _first(raw, "STATUS")[1].upper() == "CANCELLED":
        return []
    start, all_day = parse_when(*reversed(_first(raw, "DTSTART")))
    if start is None:
        return []
    end_opts, end_value = _first(raw, "DTEND")
    end = parse_when(end_value, end_opts)[0] if end_value else None
    if end is None and raw.get("DURATION"):
        length = parse_duration(_first(raw, "DURATION")[1])
        end = start + length if length else None
    title = unescape(_first(raw, "SUMMARY")[1]).strip()[:MAX_TITLE] or "(no title)"
    location = unescape(_first(raw, "LOCATION")[1]).replace("\n", " ").strip()[:MAX_TITLE]
    exdates = set()
    for options, value in raw.get("EXDATE", []):
        for part in value.split(","):
            moment = parse_when(part, options)[0]
            if moment is not None:
                exdates.add(moment)
    rule = _first(raw, "RRULE")[1]
    times = occurrences(start, parse_rrule(rule), window_end, exdates | skip) if rule else [start]
    length = (end - start) if end and end > start else None
    rows = []
    for moment in times:
        if window_start <= moment <= window_end:
            finish = moment + length if length and not all_day else None
            rows.append({"date": moment.date().isoformat(), "time": "" if all_day else moment.strftime("%H:%M"),
                         "end_time": finish.strftime("%H:%M") if finish and finish.date() == moment.date() else "",
                         "title": title, "location": location})
    return rows


def parse_calendar(text, today):
    """Nội dung file .ics -> list sự kiện (đã mở rộng các lần lặp) trong [today - 30 ngày, today + 180 ngày].

    Lần sửa riêng của một sự kiện lặp lại (có RECURRENCE-ID) thay cho lần gốc tương ứng.
    """
    raw_events = read_events(unfold(text or ""))
    window_start = datetime.combine(today - timedelta(days=DAYS_BEFORE), datetime.min.time())
    window_end = datetime.combine(today + timedelta(days=DAYS_AFTER), datetime.max.time())
    replaced = {}                         # UID -> các lần gốc đã có bản sửa riêng
    for raw in raw_events:
        if raw.get("RECURRENCE-ID"):
            moment = parse_when(*reversed(_first(raw, "RECURRENCE-ID")))[0]
            if moment is not None:
                replaced.setdefault(_first(raw, "UID")[1], set()).add(moment)
    rows = []
    for raw in raw_events:
        skip = set() if raw.get("RECURRENCE-ID") else replaced.get(_first(raw, "UID")[1], set())
        rows.extend(event_rows(raw, window_start, window_end, skip))
        if len(rows) >= MAX_EVENTS:
            break
    rows.sort(key=lambda r: (r["date"], r["time"], r["title"]))
    return rows[:MAX_EVENTS]


def looks_like_calendar(text):
    """File có phải lịch iCalendar không (để báo lỗi rõ ràng khi người dùng dán nhầm link / tải nhầm file)."""
    return "BEGIN:VCALENDAR" in (text or "")[:2000].upper()
