"""Logic thuần Python cho thời khóa biểu tuần (các môn học lặp lại mỗi tuần).

Khác với Calendar (sự kiện một lần theo ngày cụ thể), mỗi "class" ở đây lặp lại
vào một thứ cố định trong tuần, ví dụ "Calculus, thứ Hai 10:10-12:00, phòng R101".

Các hàm chính:
    validate_class()      -> kiểm tra dữ liệu từ client
    find_conflicts()      -> tìm các môn bị trùng giờ trong cùng một ngày
    build_week()          -> chia các môn theo thứ, xếp theo giờ, đánh dấu trùng giờ
    build_timetable()     -> như build_week nhưng xếp các môn vào các tiết học của NTHU (1, 2, 3, 4, n, 5...)
    visible_days()        -> cột nào hiện trên trang (Thứ 2 đến Thứ 6, cuối tuần chỉ hiện khi có môn)
    classes_on()          -> các môn của một ngày cụ thể (để hiện "Today")
    weekly_minutes()      -> tổng số phút học trên lớp mỗi tuần
"""
from calendar_logic import is_hhmm

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# Các tiết học của NTHU (mã tiết, giờ bắt đầu, giờ kết thúc). Đây là dữ liệu cố định của trường.
PERIODS = [
    {"id": "1", "start": "08:00", "end": "08:50"},
    {"id": "2", "start": "09:00", "end": "09:50"},
    {"id": "3", "start": "10:10", "end": "11:00"},
    {"id": "4", "start": "11:10", "end": "12:00"},
    {"id": "n", "start": "12:10", "end": "13:00"},
    {"id": "5", "start": "13:20", "end": "14:10"},
    {"id": "6", "start": "14:20", "end": "15:10"},
    {"id": "7", "start": "15:30", "end": "16:20"},
    {"id": "8", "start": "16:30", "end": "17:20"},
    {"id": "9", "start": "17:30", "end": "18:20"},
    {"id": "a", "start": "18:30", "end": "19:20"},
    {"id": "b", "start": "19:30", "end": "20:20"},
    {"id": "c", "start": "20:30", "end": "21:20"},
    {"id": "d", "start": "21:30", "end": "22:20"},
]
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


def class_periods(item):
    """(tiết đầu, tiết cuối) mà môn này chạm vào, đánh số từ 0; None nếu không rơi vào tiết nào.

    Một tiết "bị chạm" khi giờ của môn chồng lên giờ của tiết (cùng quy tắc overlaps).
    Ví dụ 10:10-12:00 chạm tiết 3 và 4 -> (2, 3).
    """
    hit = [i for i, period in enumerate(PERIODS) if overlaps(item, period)]
    return (hit[0], hit[-1]) if hit else None


def _assign_lanes(blocks):
    """Gán `lane` (làn) và `lanes` (số làn) cho các khối trong một ngày để khối chồng nhau đứng cạnh nhau.

    Các khối chồng nhau theo hàng (liên tiếp) thành một cụm; mỗi cụm chia đều chiều rộng cho số làn của nó.
    """
    blocks.sort(key=lambda b: (b["row"], -b["span"], b["id"]))
    cluster, cluster_end = [], -1

    def close(group):
        lanes = max((b["lane"] for b in group), default=-1) + 1
        for b in group:
            b["lanes"] = lanes

    lane_ends = []                          # lane_ends[i] = hàng cuối cùng đang bị làn i chiếm
    for block in blocks:
        if cluster and block["row"] > cluster_end:      # khối này không chạm cụm trước -> đóng cụm
            close(cluster)
            cluster, lane_ends = [], []
        lane = next((i for i, end in enumerate(lane_ends) if end < block["row"]), len(lane_ends))
        if lane == len(lane_ends):
            lane_ends.append(-1)
        lane_ends[lane] = block["row"] + block["span"] - 1
        block["lane"] = lane
        cluster.append(block)
        cluster_end = max(cluster_end, lane_ends[lane])
    close(cluster)


def build_timetable(classes):
    """Như build_week, nhưng mỗi ngày có thêm:
        "short"   : tên ngắn ("Mon")
        "blocks"  : các môn nằm trong lưới tiết, mỗi khối có row (tiết đầu), span (số tiết), lane, lanes
        "outside" : các môn không rơi vào tiết nào (ví dụ 07:00-07:50), để hiện riêng
    Làm trên bản sao, không sửa dữ liệu gốc.
    """
    days = build_week(classes)
    for day in days:
        day["short"] = day["name"][:3]
        blocks, outside = [], []
        for item in day["classes"]:
            span = class_periods(item)
            if span is None:
                outside.append(item)
            else:
                blocks.append(dict(item, row=span[0], span=span[1] - span[0] + 1, lane=0, lanes=1))
        _assign_lanes(blocks)
        day["blocks"], day["outside"] = blocks, outside
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
