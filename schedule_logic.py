"""Logic thuần Python cho thời khóa biểu tuần (các môn học lặp lại mỗi tuần).

Khác với Calendar (sự kiện một lần theo ngày cụ thể), mỗi "class" ở đây lặp lại
vào một thứ cố định trong tuần, ví dụ "Calculus, thứ Hai 10:10-12:00, phòng R101".

Các hàm chính:
    validate_class()      -> kiểm tra dữ liệu từ client
    find_conflicts()      -> tìm các môn bị trùng giờ trong cùng một ngày
    build_week()          -> chia các môn theo thứ, xếp theo giờ, đánh dấu trùng giờ
    visible_days()        -> cột nào hiện trên trang (Thứ 2 đến Thứ 6, cuối tuần chỉ hiện khi có môn)
    classes_on()          -> các môn của một ngày cụ thể (để hiện "Today")
    weekly_minutes()      -> tổng số phút học trên lớp mỗi tuần
"""
from calendar_logic import is_hhmm

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MAX_NAME = 100
MAX_ROOM = 100


# ---------- kiểm tra dữ liệu từ client ----------

def _is_int(value):
    """True nếu là số nguyên thật (bool cũng là int trong Python nên phải loại ra)."""
    return isinstance(value, int) and not isinstance(value, bool)


def to_minutes(hhmm):
    """"10:30" -> 630 (số phút tính từ 00:00). Dùng để so sánh giờ cho đúng."""
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def validate_class(data):
    """Kiểm tra một môn trong thời khóa biểu. Trả về (môn_sạch, None) hoặc (None, lỗi)."""
    if not isinstance(data, dict):
        return None, "JSON body must be an object"

    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME:
        return None, f"name is required (at most {MAX_NAME} characters)"

    weekday = data.get("weekday")
    if not _is_int(weekday) or not 0 <= weekday <= 6:
        return None, "weekday must be a whole number from 0 (Monday) to 6 (Sunday)"

    start, end = data.get("start"), data.get("end")
    if not isinstance(start, str) or not isinstance(end, str) or not is_hhmm(start) or not is_hhmm(end):
        return None, "start and end must be times like 10:10"
    if to_minutes(end) <= to_minutes(start):
        return None, "end must be later than start"

    room = data.get("room") or ""
    if not isinstance(room, str) or len(room.strip()) > MAX_ROOM:
        return None, f"room must be at most {MAX_ROOM} characters"

    return {"name": name.strip(), "weekday": weekday, "start": start, "end": end,
            "room": room.strip()}, None


# ---------- trùng giờ ----------

def overlaps(a, b):
    """Hai khoảng giờ có chồng nhau không. Môn kết thúc 12:00 và môn bắt đầu 12:00 KHÔNG trùng."""
    return to_minutes(a["start"]) < to_minutes(b["end"]) and to_minutes(b["start"]) < to_minutes(a["end"])


def find_conflicts(classes):
    """Tập id của các môn bị trùng giờ với một môn khác trong cùng một thứ."""
    conflicting = set()
    for i, first in enumerate(classes):
        for second in classes[i + 1:]:
            if first["weekday"] == second["weekday"] and overlaps(first, second):
                conflicting.add(first["id"])
                conflicting.add(second["id"])
    return conflicting


# ---------- dựng tuần ----------

def build_week(classes):
    """Danh sách 7 ngày (Thứ 2 đến Chủ nhật): {"weekday", "name", "classes": [...]}.

    Các môn trong ngày xếp theo giờ bắt đầu; mỗi môn được thêm `conflict` (trùng giờ hay không).
    Làm trên bản sao, không sửa dữ liệu gốc.
    """
    conflicts = find_conflicts(classes)
    days = [{"weekday": i, "name": name, "classes": []} for i, name in enumerate(WEEKDAYS)]
    for item in classes:
        days[item["weekday"]]["classes"].append(dict(item, conflict=item["id"] in conflicts))
    for day in days:
        day["classes"].sort(key=lambda c: (to_minutes(c["start"]), to_minutes(c["end"]), c["id"]))
    return days


def visible_days(days):
    """Thứ 2 đến Thứ 6 luôn hiện; Thứ 7 và Chủ nhật chỉ hiện khi có môn."""
    return [day for day in days if day["weekday"] < 5 or day["classes"]]


def classes_on(classes, weekday):
    """Các môn của một thứ (0 = Thứ 2), xếp theo giờ."""
    return sorted((c for c in classes if c["weekday"] == weekday),
                  key=lambda c: (to_minutes(c["start"]), c["id"]))


def weekly_minutes(classes):
    """Tổng số phút học trên lớp mỗi tuần."""
    return sum(to_minutes(c["end"]) - to_minutes(c["start"]) for c in classes)
