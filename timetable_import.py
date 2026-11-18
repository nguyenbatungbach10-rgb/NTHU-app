"""Đọc thời khóa biểu copy từ 校務資訊系統 (trang 課表) thành danh sách môn học (Python thuần, dễ test).

Khi bôi đen bảng 課表 rồi Ctrl+C, trình duyệt cho ra chữ kiểu:

    時間\\星期<TAB>星期一MON<TAB>星期二TUE ...                 <- hàng tiêu đề: thứ tự các cột
    08:00 -- 08:50<TAB>11510EE 231001                         <- mỗi hàng bắt đầu bằng khung giờ
    計算機程式設計未亂數                                         <- trong một ô: mã môn, tên Trung,
    DELTA台達217                                                 phòng, tên Anh (mỗi thứ một dòng)
    Introduction to Programming<TAB><TAB>11510EE 231001 ...    <- TAB = sang ô (thứ) kế tiếp

Cách đọc:
  1. Tìm các khung giờ "08:00 -- 08:50"; chữ giữa hai khung giờ là một hàng.
  2. Tách hàng theo TAB -> từng ô; ô thứ i thuộc thứ (weekday) ở cột i của hàng tiêu đề.
  3. Trong ô: dòng có mã môn (11510EE 231001), dòng kế là tên Trung, dòng có mã tòa nhà + số là phòng,
     dòng còn lại là tên Anh.
  4. Gộp các tiết liền nhau của cùng một môn trong cùng một ngày thành một buổi (08:00-09:50).
"""
import re

TIME_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[-~－–—]+\s*(\d{1,2}):(\d{2})")
COURSE_CODE = re.compile(r"\b\d{5}[A-Z]{2,5}\s*\d{6}\b")
# Phòng: bắt đầu bằng mã tòa nhà viết HOA ("DELTA", "GEN IV", "PHYS") và có số phòng
ROOM_LINE = re.compile(r"^[A-Z]{2,}.*\d")
# Chữ trạng thái màu đỏ dính sau tên môn (rút thăm chưa chạy, trúng, trượt...)
STATUS = re.compile(r"(未亂數|已亂數|亂數中選|亂數落選|中選|落選|停修|退選)\s*$")
SKIP_STATUS = {"落選", "亂數落選", "停修", "退選"}   # môn không học nữa -> không nhập
DAY_WORDS = [("MON", "一"), ("TUE", "二"), ("WED", "三"), ("THU", "四"), ("FRI", "五"), ("SAT", "六"), ("SUN", "日")]
MERGE_GAP = 20      # hai tiết cách nhau <= 20 phút (giờ nghỉ) là liền nhau
MAX_TEXT = 50000    # dán quá dài thì không đọc


def _hhmm(hour, minute):
    return f"{int(hour):02d}:{minute}"


def _minutes(hhmm):
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def header_days(header):
    """Thứ tự các cột ngày trong hàng tiêu đề -> list weekday (0 = Thứ 2). Không đọc được -> Thứ 2..CN."""
    days = []
    for cell in header.split("\t"):
        upper = cell.upper()
        for weekday, (en, zh) in enumerate(DAY_WORDS):
            if en in upper or f"星期{zh}" in cell or f"週{zh}" in cell:
                days.append(weekday)
                break
    return days or list(range(7))


def parse_cell(text):
    """Một ô -> list môn {code, name_zh, name_en, room, status} (thường 1 môn; 2 môn nếu trùng giờ)."""
    courses = []
    starts = [m.start() for m in COURSE_CODE.finditer(text)]
    for i, start in enumerate(starts):
        chunk = text[start: starts[i + 1] if i + 1 < len(starts) else len(text)]
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        code = re.sub(r"\s+", " ", COURSE_CODE.match(lines[0])[0])
        rest = lines[1:]
        name_zh, status = "", ""
        if rest:
            name_zh = rest.pop(0)
            if m := STATUS.search(name_zh):
                status, name_zh = m[1], name_zh[:m.start()].strip()
        room = next((line for line in rest if ROOM_LINE.match(line)), "")
        others = [line for line in rest if line != room]
        courses.append({"code": code, "name_zh": name_zh, "name_en": " ".join(others),
                        "room": room, "status": status})
    return courses


def parse_slots(text):
    """Chữ copy từ trang 課表 -> list tiết học {weekday, start, end, code, name_zh, name_en, room, status}."""
    text = (text or "")[:MAX_TEXT].replace("\r\n", "\n").replace("\r", "\n")
    times = list(TIME_RANGE.finditer(text))
    if not times:
        return []
    days = header_days(text[:times[0].start()].strip().split("\n")[-1])
    slots = []
    for i, m in enumerate(times):
        row = text[m.end(): times[i + 1].start() if i + 1 < len(times) else len(text)]
        cells = row.split("\t")[1:]          # phần trước TAB đầu tiên là chính ô khung giờ
        for column, cell in enumerate(cells):
            if column >= len(days):
                break
            for course in parse_cell(cell):
                slots.append(dict(course, weekday=days[column],
                                  start=_hhmm(m[1], m[2]), end=_hhmm(m[3], m[4])))
    return slots


def merge_slots(slots):
    """Gộp các tiết liền nhau của cùng môn, cùng ngày: [08:00-08:50, 09:00-09:50] -> 08:00-09:50."""
    merged = []
    for slot in sorted(slots, key=lambda s: (s["code"], s["weekday"], s["start"])):
        last = merged[-1] if merged else None
        if (last and last["code"] == slot["code"] and last["weekday"] == slot["weekday"]
                and 0 <= _minutes(slot["start"]) - _minutes(last["end"]) <= MERGE_GAP):
            last["end"] = slot["end"]
        else:
            merged.append(dict(slot))
    return sorted(merged, key=lambda s: (s["weekday"], s["start"]))


def parse_timetable(text, names="zh"):
    """Kết quả cuối cùng cho trang Import: (classes, skipped).

    classes: list {name, room, weekday, start, end, code, status} sẵn sàng cho schedule_logic.validate_class.
    skipped: các môn bỏ qua vì đã trượt / rút (落選, 停修...), để báo cho người dùng.
    names: "zh" dùng tên Trung, "en" dùng tên Anh (thiếu thì dùng tên còn lại).
    """
    classes, skipped = [], []
    for slot in merge_slots(parse_slots(text)):
        first, second = (slot["name_en"], slot["name_zh"]) if names == "en" else (slot["name_zh"], slot["name_en"])
        item = {"name": (first or second or slot["code"])[:100], "room": slot["room"][:100],
                "weekday": slot["weekday"], "start": slot["start"], "end": slot["end"],
                "code": slot["code"], "status": slot["status"]}
        (skipped if slot["status"] in SKIP_STATUS else classes).append(item)
    return classes, skipped


def is_duplicate(item, existing):
    """Đã có môn cùng tên, cùng thứ, cùng giờ trong thời khóa biểu chưa (để không nhập trùng khi dán lại)."""
    return any(c["name"] == item["name"] and c["weekday"] == item["weekday"]
               and c["start"] == item["start"] and c["end"] == item["end"] for c in existing)
