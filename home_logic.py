"""Logic cho trang chủ và gợi ý chung (thuần Python, không có Flask hay database).

    onboarding()     -> hướng dẫn 4 bước cho người mới; tự ẩn khi đã làm đủ
    name_suggestions() -> tên môn để gợi ý khi gõ (lấy từ thời khóa biểu, môn học, môn GPA)
"""

# (khóa trong counts, câu hướng dẫn, trang cần mở). Thứ tự là thứ tự nên làm.
STEPS = [
    ("classes", "Add your classes", "schedule"),
    ("goals", "Set a GPA goal", "gpa"),
    ("events", "Save a deadline", "deadlines"),
    ("tasks", "Add a study task", "study"),
]


def onboarding(counts, hidden=False):
    """Các bước kèm `done` (đã có dữ liệu chưa). `show` = False khi đã xong cả 4 bước hoặc người dùng đã ẩn.

    `counts` là số dòng của người dùng trong từng bảng, ví dụ {"classes": 3, "goals": 0, ...}.
    """
    steps = [{"key": key, "label": label, "target": target, "done": counts.get(key, 0) > 0}
             for key, label, target in STEPS]
    done = sum(1 for step in steps if step["done"])
    return {"steps": steps, "done": done, "total": len(steps), "show": not hidden and done < len(steps)}


def name_suggestions(*groups, limit=50):
    """Gộp nhiều danh sách tên, bỏ trùng (không phân biệt hoa thường), bỏ ô trống, xếp A-Z."""
    seen, result = set(), []
    for group in groups:
        for name in group:
            name = (name or "").strip()
            if name and name.casefold() not in seen:
                seen.add(name.casefold())
                result.append(name)
    return sorted(result, key=str.casefold)[:limit]


# ---------- thanh tab dưới đáy màn hình (điện thoại) ----------

# (endpoint, chữ, biểu tượng). Tab "More" (mở menu đầy đủ) luôn ở cuối, do base.html vẽ.
TABS = [
    ("home", "Today", "home"),
    ("calendar_page", "Calendar", "calendar"),
    ("study_page", "Study", "study"),
    ("announcements", "Notices", "news"),
]
# Trang con thuộc tab nào (trang không có ở đây -> tab "More")
TAB_OF = {"calendar_year_page": "calendar_page", "gpa_page": "study_page", "notifications_page": "home"}


def current_tab(endpoint):
    """Tab đang sáng cho trang hiện tại: endpoint của một tab trong TABS, hoặc "more"."""
    endpoint = TAB_OF.get(endpoint, endpoint)
    return endpoint if any(endpoint == tab for tab, _, _ in TABS) else "more"


# ---------- chuông thông báo ----------

SOON_MINUTES = 60      # lớp bắt đầu trong 60 phút nữa thì nhắc


def _minutes(hhmm):
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def notifications(today, now_minutes, tasks, events, classes):
    """Những việc cần chú ý bây giờ, quan trọng nhất trước (Python quyết định, template chỉ hiện).

    tasks:   việc CHƯA XONG có hạn nộp tới hết ngày mai (gồm cả việc trễ hạn)
    events:  sự kiện hôm nay và ngày mai
    classes: các lớp của hôm nay
    Mỗi mục: {"kind": "overdue" | "due" | "class" | "event", "title", "when", "day", "urgent"}.
    when là giờ "HH:MM" hoặc "", day là "today" / "tomorrow" / ngày ISO (với việc trễ hạn).
    """
    today_iso = today.isoformat()
    items = []
    for t in tasks:
        if t["due_date"] < today_iso:
            items.append({"kind": "overdue", "title": t["title"], "when": "", "day": t["due_date"], "urgent": True})
        else:
            day = "today" if t["due_date"] == today_iso else "tomorrow"
            items.append({"kind": "due", "title": t["title"], "when": "", "day": day, "urgent": day == "today"})
    for c in classes:
        start = _minutes(c["start"])
        if 0 <= start - now_minutes <= SOON_MINUTES:
            items.append({"kind": "class", "title": c["name"], "when": c["start"], "day": "today",
                          "room": c.get("room", ""), "starts_in": start - now_minutes, "urgent": True})
    for e in events:
        if e["date"] == today_iso and e["time"] and _minutes(e["time"]) < now_minutes:
            continue                                   # sự kiện hôm nay đã qua giờ thì thôi nhắc
        day = "today" if e["date"] == today_iso else "tomorrow"
        items.append({"kind": "event", "title": e["title"], "when": e["time"], "day": day, "urgent": False})
    order = {"overdue": 0, "class": 1, "due": 2, "event": 3}
    items.sort(key=lambda i: (not i["urgent"], i["day"] != "today" and i["kind"] != "overdue", order[i["kind"]], i["when"]))
    return items
