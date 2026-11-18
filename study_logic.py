"""Logic thuần Python cho Study planning (không có Flask, không có database).

Ba loại dữ liệu:
    môn học (subject)   : tên + ghi chú tài liệu (link, sách...)
    việc cần làm (task) : có hạn nộp, tick xong, và có thể chia nhỏ thành việc con (subtask)
    buổi học (session)  : ngày, số phút, môn nào -> để theo dõi thời gian học

Các hàm chính:
    validate_subject / validate_task / validate_session -> kiểm tra dữ liệu từ client
    build_task_tree()    -> xếp việc cha/con, đánh dấu quá hạn, đếm việc con đã xong
    week_bounds()        -> thứ Hai của tuần này và thứ Hai tuần sau
    minutes_by_subject() -> tổng phút học theo từng môn
    overview()           -> các số liệu cho đầu trang
    format_minutes()     -> 90 -> "1h 30m"
    due_today()          -> việc chưa xong đến hạn hôm nay hoặc đã quá hạn (cho trang chủ)
"""
from datetime import date, timedelta

from calendar_logic import is_iso_date

MAX_SUBJECT_NAME = 100
MAX_NOTES = 1000
MAX_TASK_TITLE = 200
MAX_SESSION_NOTE = 300
MAX_SESSION_MINUTES = 24 * 60   # một buổi học không dài hơn một ngày


# ---------- kiểm tra dữ liệu từ client ----------

def _is_int(value):
    """True nếu là số nguyên thật (bool cũng là int trong Python nên phải loại ra)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _optional_id(value):
    """None hoặc số nguyên dương. Trả về (giá_trị, hợp_lệ)."""
    if value is None or value == "":
        return None, True
    if _is_int(value) and value >= 1:
        return value, True
    return None, False


def _text(value, limit):
    """Chuỗi đã bỏ khoảng trắng hai đầu, hoặc None nếu không phải chuỗi / quá dài."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if len(value) <= limit else None


def validate_subject(data):
    """Kiểm tra một môn học. Trả về (môn_sạch, None) hoặc (None, lỗi)."""
    if not isinstance(data, dict):
        return None, "JSON body must be an object"
    name = _text(data.get("name"), MAX_SUBJECT_NAME)
    if not name:
        return None, f"name is required (at most {MAX_SUBJECT_NAME} characters)"
    notes = _text(data.get("notes"), MAX_NOTES)
    if notes is None:
        return None, f"notes must be at most {MAX_NOTES} characters"
    return {"name": name, "notes": notes}, None


def validate_task(data):
    """Kiểm tra một việc cần làm. Chưa kiểm tra subject_id / parent_id có thuộc về người dùng không
    (việc đó cần database nên làm ở app.py)."""
    if not isinstance(data, dict):
        return None, "JSON body must be an object"
    title = _text(data.get("title"), MAX_TASK_TITLE)
    if not title:
        return None, f"title is required (at most {MAX_TASK_TITLE} characters)"

    due = data.get("due_date") or ""
    if not isinstance(due, str) or (due and not is_iso_date(due)):
        return None, "due_date must be empty or a real date like 2026-11-20"

    done = data.get("done", False)
    if not isinstance(done, bool):
        return None, "done must be true or false"

    subject_id, ok_subject = _optional_id(data.get("subject_id"))
    parent_id, ok_parent = _optional_id(data.get("parent_id"))
    if not ok_subject or not ok_parent:
        return None, "subject_id and parent_id must be positive whole numbers or empty"

    return {"title": title, "due_date": due, "done": done,
            "subject_id": subject_id, "parent_id": parent_id}, None


def validate_session(data):
    """Kiểm tra một buổi học."""
    if not isinstance(data, dict):
        return None, "JSON body must be an object"
    day = data.get("date")
    if not isinstance(day, str) or not is_iso_date(day):
        return None, "date must be a real date like 2026-11-20"

    minutes = data.get("minutes")
    if not _is_int(minutes) or not 1 <= minutes <= MAX_SESSION_MINUTES:
        return None, f"minutes must be a whole number from 1 to {MAX_SESSION_MINUTES}"

    subject_id, ok = _optional_id(data.get("subject_id"))
    if not ok:
        return None, "subject_id must be a positive whole number or empty"
    note = _text(data.get("note"), MAX_SESSION_NOTE)
    if note is None:
        return None, f"note must be at most {MAX_SESSION_NOTE} characters"
    return {"date": day, "minutes": minutes, "subject_id": subject_id, "note": note}, None


# ---------- việc cần làm ----------

def is_overdue(task, today_iso):
    """Quá hạn = chưa xong, có hạn nộp, và hạn nộp đã qua (hôm nay vẫn chưa tính là quá hạn)."""
    return not task["done"] and bool(task["due_date"]) and task["due_date"] < today_iso


def _sort_key(task):
    """Việc chưa xong lên trước; trong mỗi nhóm: hạn gần trước, không có hạn thì cuối."""
    return (task["done"], task["due_date"] == "", task["due_date"], task["id"])


def build_task_tree(tasks, today_iso, subject_names=None):
    """Xếp danh sách phẳng thành cây: mỗi việc cha có danh sách `children`.

    Mỗi việc nhận thêm: overdue, subject_name (việc con lấy môn của việc cha),
    subtasks_total, subtasks_done.
    """
    subject_names = subject_names or {}
    children_of = {}
    parents = []
    for task in tasks:
        item = dict(task)                       # copy: không sửa dữ liệu gốc
        item["overdue"] = is_overdue(task, today_iso)
        if task["parent_id"] is None:
            item["subject_name"] = subject_names.get(task["subject_id"], "")
            parents.append(item)
        else:
            children_of.setdefault(task["parent_id"], []).append(item)

    for parent in parents:
        kids = sorted(children_of.get(parent["id"], []), key=_sort_key)
        for kid in kids:
            kid["subject_name"] = parent["subject_name"]
        parent["children"] = kids
        parent["subtasks_total"] = len(kids)
        parent["subtasks_done"] = sum(1 for kid in kids if kid["done"])
    return sorted(parents, key=_sort_key)


def due_today(tasks, today_iso, limit=5):
    """Việc CHÍNH chưa xong có hạn nộp từ hôm nay trở về trước, hạn cũ nhất trước (tối đa `limit`).

    Mỗi việc là một BẢN SAO có thêm `overdue`. Việc con không đếm (chỉ là bước nhỏ của việc cha).
    """
    rows = [dict(t, overdue=is_overdue(t, today_iso)) for t in tasks
            if t["parent_id"] is None and not t["done"] and t["due_date"] and t["due_date"] <= today_iso]
    rows.sort(key=lambda t: (t["due_date"], t["id"]))
    return rows[:limit]


# ---------- thời gian học ----------

def week_bounds(today):
    """(thứ Hai tuần này, thứ Hai tuần sau) dạng YYYY-MM-DD; tuần tính từ thứ Hai."""
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat(), (monday + timedelta(days=7)).isoformat()


def total_minutes(sessions, start=None, end=None):
    """Tổng phút của các buổi có ngày từ start đến TRƯỚC end (bỏ trống = không giới hạn)."""
    return sum(
        s["minutes"] for s in sessions
        if (start is None or s["date"] >= start) and (end is None or s["date"] < end)
    )


def minutes_by_subject(sessions, subject_names, start=None, end=None):
    """Tổng phút theo môn, nhiều nhất trước. Buổi học không gắn môn nào vào nhóm "No subject"."""
    totals = {}
    for s in sessions:
        if (start is not None and s["date"] < start) or (end is not None and s["date"] >= end):
            continue
        totals[s["subject_id"]] = totals.get(s["subject_id"], 0) + s["minutes"]
    rows = [{"subject_id": sid, "name": subject_names.get(sid, "No subject"), "minutes": minutes}
            for sid, minutes in totals.items()]
    return sorted(rows, key=lambda row: (-row["minutes"], row["name"].lower()))


def format_minutes(minutes):
    """90 -> "1h 30m", 60 -> "1h", 45 -> "45m", 0 -> "0m"."""
    hours, rest = divmod(int(minutes), 60)
    if hours and rest:
        return f"{hours}h {rest}m"
    return f"{hours}h" if hours else f"{rest}m"


def overview(tasks, sessions, today):
    """Số liệu đầu trang Study."""
    today_iso = today.isoformat()
    week_start, week_end = week_bounds(today)
    # Chỉ đếm việc "chính"; việc con chỉ là các bước nhỏ của việc cha
    top = [t for t in tasks if t["parent_id"] is None]
    return {
        "open": sum(1 for t in top if not t["done"]),
        "done": sum(1 for t in top if t["done"]),
        "overdue": sum(1 for t in top if is_overdue(t, today_iso)),
        "today_minutes": total_minutes(sessions, today_iso, (today + timedelta(days=1)).isoformat()),
        "week_minutes": total_minutes(sessions, week_start, week_end),
        "days_studied_this_week": len({s["date"] for s in sessions if week_start <= s["date"] < week_end}),
    }


# ---------- Thống kê học tập (biểu đồ giống mockup) ----------

PERIODS = {"week": 7, "month": 30}       # số ngày của mỗi khoảng xem
SUBJECT_SLOTS = 5                        # 5 màu cho 5 môn nhiều nhất, còn lại gộp "Other"


def _daily_minutes(sessions):
    """{"2026-11-18": 45, ...}: tổng phút mỗi ngày."""
    totals = {}
    for s in sessions:
        totals[s["date"]] = totals.get(s["date"], 0) + s["minutes"]
    return totals


def period_days(today, period):
    """Các ngày của khoảng đang xem: "week" = Thứ 2 -> CN tuần này, "month" = 30 ngày tới hôm nay."""
    if period == "week":
        monday = today - timedelta(days=today.weekday())
        return [monday + timedelta(days=i) for i in range(7)]
    return [today - timedelta(days=PERIODS["month"] - 1 - i) for i in range(PERIODS["month"])]


def percent_change(now, before):
    """Thay đổi so với kỳ trước, làm tròn %: 8h so với 6h -> 33. Kỳ trước bằng 0 -> None (không so được)."""
    return round((now - before) * 100 / before) if before else None


def study_streak(sessions, today):
    """Số ngày liên tiếp có học, tính tới hôm nay (hôm nay chưa học thì tính tới hôm qua)."""
    days = {s["date"] for s in sessions if s["minutes"] > 0}
    day = today if today.isoformat() in days else today - timedelta(days=1)
    streak = 0
    while day.isoformat() in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def subject_shares(sessions, subject_names, start, end):
    """Phần trăm thời gian theo môn trong [start, end): 5 môn nhiều nhất, còn lại gộp thành "Other".

    Mỗi dòng {"name", "minutes", "percent", "slot"}; slot 1..6 chọn màu (6 = Other).
    """
    rows = minutes_by_subject(sessions, subject_names, start, end)
    total = sum(r["minutes"] for r in rows)
    if not total:
        return []
    top, rest = rows[:SUBJECT_SLOTS], rows[SUBJECT_SLOTS:]
    if rest:
        top.append({"subject_id": "other", "name": "Other", "minutes": sum(r["minutes"] for r in rest)})
    return [dict(r, percent=round(r["minutes"] * 100 / total), slot=i + 1) for i, r in enumerate(top)]


def donut_gradient(shares):
    """CSS conic-gradient cho biểu đồ tròn: "conic-gradient(var(--c1) 0% 32%, var(--c2) 32% 57%, ...)"."""
    if not shares:
        return "none"
    total = sum(s["minutes"] for s in shares)
    parts, start = [], 0.0
    for s in shares:
        end = start + s["minutes"] * 100 / total
        parts.append(f"var(--c{s['slot']}) {start:.1f}% {end:.1f}%")
        start = end
    return "conic-gradient(" + ", ".join(parts) + ")"


def best_weekday(sessions):
    """Thứ trong tuần học nhiều nhất (0 = Thứ 2); chưa có buổi học nào -> None."""
    totals = [0] * 7
    for s in sessions:
        totals[date.fromisoformat(s["date"]).weekday()] += s["minutes"]
    return totals.index(max(totals)) if any(totals) else None


def analytics(sessions, subject_names, today, period="week"):
    """Mọi số liệu cho thẻ thống kê: cột theo ngày, tổng, so với kỳ trước, tỉ lệ theo môn, chuỗi ngày học."""
    period = period if period in PERIODS else "week"
    days = period_days(today, period)
    start, end = days[0], days[-1] + timedelta(days=1)
    length = end - start
    daily = _daily_minutes(sessions)
    peak = max([daily.get(d.isoformat(), 0) for d in days] + [1])
    bars = [{"date": d.isoformat(), "weekday": d.weekday(), "day": d.day, "minutes": daily.get(d.isoformat(), 0),
             "percent": round(daily.get(d.isoformat(), 0) * 100 / peak), "is_today": d == today,
             "future": d > today} for d in days]
    total = total_minutes(sessions, start.isoformat(), end.isoformat())
    before = total_minutes(sessions, (start - length).isoformat(), start.isoformat())
    shares = subject_shares(sessions, subject_names, start.isoformat(), end.isoformat())
    return {"period": period, "bars": bars, "total": total, "previous": before,
            "change": percent_change(total, before), "shares": shares, "donut": donut_gradient(shares),
            "streak": study_streak(sessions, today), "best_weekday": best_weekday(sessions),
            "from": start.isoformat(), "to": days[-1].isoformat()}
