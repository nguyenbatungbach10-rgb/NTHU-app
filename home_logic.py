"""Logic cho trang chủ và gợi ý chung (thuần Python, không có Flask hay database).

    onboarding()     -> hướng dẫn 4 bước cho người mới; tự ẩn khi đã làm đủ
    name_suggestions() -> tên môn để gợi ý khi gõ (lấy từ thời khóa biểu, môn học, môn GPA)
"""

# (khóa trong counts, câu hướng dẫn, trang cần mở). Thứ tự là thứ tự nên làm.
STEPS = [
    ("classes", "Add your weekly classes", "schedule"),
    ("goals", "Set your graduation credits and target GPA", "gpa"),
    ("events", "Save an upcoming deadline to your calendar", "deadlines"),
    ("tasks", "Add a study task", "study"),
]


def onboarding(counts):
    """Các bước kèm `done` (đã có dữ liệu chưa). `show` = False khi đã xong cả 4 bước.

    `counts` là số dòng của người dùng trong từng bảng, ví dụ {"classes": 3, "goals": 0, ...}.
    """
    steps = [{"key": key, "label": label, "target": target, "done": counts.get(key, 0) > 0}
             for key, label, target in STEPS]
    done = sum(1 for step in steps if step["done"])
    return {"steps": steps, "done": done, "total": len(steps), "show": done < len(steps)}


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
