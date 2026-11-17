"""Logic thuần Python cho Credit & GPA tracking (không có Flask, không có database).

    validate_course() / validate_goals() -> kiểm tra dữ liệu từ client
    gpa()                -> GPA tích lũy (trung bình có trọng số theo tín chỉ)
    credits_earned()     -> số tín chỉ đã đạt
    required_average()   -> cần điểm trung bình bao nhiêu để đạt mục tiêu GPA
    semester_summary()   -> thống kê từng học kỳ
    overview()           -> tất cả số liệu cho trang GPA
    current_semester()   -> học kỳ hiện tại theo lịch NTHU (ví dụ "115-1")

Thang điểm lấy từ văn bản của Phòng Giáo vụ NTHU (registra.site.nthu.edu.tw), bảng 2 và 3:
A+ = 4.3 ... C- = 1.7, D = 1.0, E = 0, X = 0. Sinh viên đại học đạt từ C- (60 điểm) trở lên;
D, E, X là chưa đạt. Môn pass/fail (P) được tín chỉ nhưng không tính vào GPA.
Nếu quy định thay đổi, chỉ cần sửa GRADE_POINTS và PASSING_POINTS ở dưới.
"""
import math
import re

# Dict giữ nguyên thứ tự thêm vào: từ điểm cao xuống thấp
GRADE_POINTS = {
    "A+": 4.3, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D": 1.0, "E": 0.0, "X": 0.0,
}
LETTERS = list(GRADE_POINTS)
PASS_GRADE = "P"            # môn pass/fail đã đạt: có tín chỉ, không tính GPA
PASSING_POINTS = 1.7        # từ C- trở lên là đạt (sinh viên đại học)
MAX_POINTS = 4.3

DEFAULT_TARGET_GPA = 3.5
DEFAULT_CREDITS_REQUIRED = 128   # chỉ là giá trị mặc định: mỗi ngành có yêu cầu riêng
TOTAL_SEMESTERS = 8              # 4 năm x 2 học kỳ
MAX_COURSE_CREDITS = 12
MAX_NAME = 100


# ---------- kiểm tra dữ liệu từ client ----------

def _is_number(value):
    """True nếu là số thật (bool cũng là int trong Python nên phải loại ra)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_course(data):
    """Kiểm tra dữ liệu một môn học. Trả về (môn_sạch, None) hoặc (None, lỗi)."""
    if not isinstance(data, dict):
        return None, "JSON body must be an object"

    name = data.get("name")
    credits = data.get("credits")
    semester = data.get("semester")
    if not isinstance(name, str) or not name.strip() or credits is None or not semester:
        return None, "name, credits and semester are required"
    name = name.strip()
    if len(name) > MAX_NAME:
        return None, f"name must be at most {MAX_NAME} characters"

    if not _is_number(credits) or credits != int(credits) or not 0 <= credits <= MAX_COURSE_CREDITS:
        return None, f"credits must be a whole number from 0 to {MAX_COURSE_CREDITS}"

    if not isinstance(semester, str) or not re.fullmatch(r"\d{3}-[1-3]", semester):
        return None, "semester must look like 115-1 (academic year, then 1, 2 or 3)"

    grade = data.get("grade") or ""
    if not isinstance(grade, str) or (grade and grade not in GRADE_POINTS and grade != PASS_GRADE):
        return None, "grade must be empty (planned), P, or one of " + ", ".join(LETTERS)

    return {"name": name, "credits": int(credits), "semester": semester, "grade": grade}, None


def validate_goals(data):
    """Kiểm tra mục tiêu: GPA mong muốn và số tín chỉ cần để tốt nghiệp."""
    if not isinstance(data, dict):
        return None, "JSON body must be an object"

    target = data.get("target_gpa")
    required = data.get("credits_required")
    if not _is_number(target) or not 0 <= target <= MAX_POINTS:
        return None, f"target_gpa must be a number from 0 to {MAX_POINTS}"
    if not _is_number(required) or required != int(required) or not 1 <= required <= 300:
        return None, "credits_required must be a whole number from 1 to 300"
    return {"target_gpa": round(float(target), 2), "credits_required": int(required)}, None


# ---------- tính GPA và tín chỉ ----------

def is_passed(grade):
    """Môn đã đạt: P, hoặc điểm chữ từ C- trở lên."""
    return grade == PASS_GRADE or (grade in GRADE_POINTS and GRADE_POINTS[grade] >= PASSING_POINTS)


def gpa_totals(courses):
    """(tổng tín chỉ, tổng điểm x tín chỉ) của các môn có điểm chữ và tín chỉ > 0.

    Môn chưa có điểm (dự định) và môn P không được tính.
    """
    credits = points = 0
    for course in courses:
        if course["grade"] in GRADE_POINTS and course["credits"] > 0:
            credits += course["credits"]
            points += GRADE_POINTS[course["grade"]] * course["credits"]
    return credits, points


def gpa(courses):
    """GPA = tổng(điểm x tín chỉ) / tổng tín chỉ. Chưa có môn nào có điểm -> None."""
    credits, points = gpa_totals(courses)
    return points / credits if credits else None


def credits_earned(courses):
    """Tổng tín chỉ của các môn đã đạt."""
    return sum(c["credits"] for c in courses if is_passed(c["grade"]))


def credits_planned(courses):
    """Tổng tín chỉ của các môn chưa có điểm (đang học hoặc dự định)."""
    return sum(c["credits"] for c in courses if c["grade"] == "")


def letter_for(points):
    """Điểm chữ THẤP NHẤT (và đạt) có số điểm >= points."""
    passing = [letter for letter in reversed(LETTERS) if GRADE_POINTS[letter] >= PASSING_POINTS]
    for letter in passing:  # từ C- lên A+
        if GRADE_POINTS[letter] >= points - 1e-9:
            return letter
    return None


def required_average(courses, target, remaining_credits):
    """Cần điểm trung bình bao nhiêu trên `remaining_credits` tín chỉ tới để GPA đạt `target`.

    Gọi (C0, P0) là tín chỉ và điểm đã có, R là tín chỉ sắp học, cần trung bình x:
        (P0 + x * R) / (C0 + R) = target   =>   x = (target * (C0 + R) - P0) / R
    Trả về {"status", "needed", "letter"}:
        "no_credits": không còn tín chỉ nào để tính
        "achieved":   cần ít hơn mức đạt tối thiểu, tức là chỉ cần qua môn
        "possible":   cần `needed` điểm, tức là ít nhất điểm chữ `letter`
        "impossible": cần hơn 4.3, không thể đạt
    """
    if remaining_credits <= 0:
        return {"status": "no_credits", "needed": None, "letter": None}

    done_credits, done_points = gpa_totals(courses)
    needed = (target * (done_credits + remaining_credits) - done_points) / remaining_credits
    needed = round(needed, 2)

    if needed > MAX_POINTS:
        return {"status": "impossible", "needed": needed, "letter": None}
    if needed <= PASSING_POINTS:
        return {"status": "achieved", "needed": max(needed, 0.0), "letter": letter_for(PASSING_POINTS)}
    return {"status": "possible", "needed": needed, "letter": letter_for(needed)}


def semester_summary(courses):
    """Thống kê từng học kỳ, cũ nhất trước: GPA học kỳ, GPA tích lũy đến học kỳ đó, tín chỉ."""
    groups = {}
    for course in courses:
        groups.setdefault(course["semester"], []).append(course)

    summary = []
    seen = []
    for semester in sorted(groups):  # "115-1" < "115-2" < "116-1" (so sánh chuỗi là đủ)
        group = groups[semester]
        seen.extend(group)
        summary.append({
            "semester": semester,
            "courses": sorted(group, key=lambda c: (c["name"].lower(), c["id"])),
            "gpa": gpa(group),
            "cumulative_gpa": gpa(seen),
            "credits_earned": credits_earned(group),
            "credits_planned": credits_planned(group),
        })
    return summary


def overview(courses, target, credits_required):
    """Mọi số liệu cho trang GPA."""
    earned = credits_earned(courses)
    planned = credits_planned(courses)
    remaining = max(0, credits_required - earned)

    # Học kỳ "đã xong" = học kỳ có môn và mọi môn đều đã có điểm
    by_semester = {}
    for course in courses:
        by_semester.setdefault(course["semester"], []).append(course)
    finished = sum(1 for group in by_semester.values() if all(c["grade"] != "" for c in group))
    semesters_left = max(0, TOTAL_SEMESTERS - finished)

    return {
        "gpa": gpa(courses),
        "credits_earned": earned,
        "credits_planned": planned,
        "credits_required": credits_required,
        "credits_remaining": remaining,
        "progress_percent": min(100, round(earned * 100 / credits_required)) if credits_required else 0,
        "semesters_left": semesters_left,
        "credits_per_semester": math.ceil(remaining / semesters_left) if semesters_left else None,
        # Cần bao nhiêu điểm trung bình ở các môn dự định để GPA SAU học kỳ này đạt mục tiêu
        "needed_term": required_average(courses, target, planned),
        # Cần bao nhiêu điểm trung bình ở toàn bộ tín chỉ còn lại để đạt mục tiêu khi tốt nghiệp
        "needed_overall": required_average(courses, target, remaining),
    }


def current_semester(today):
    """Học kỳ hiện tại theo lịch NTHU: tháng 8-12 và tháng 1 là học kỳ 1, tháng 2-7 là học kỳ 2.

    Năm học tính theo lịch Trung Hoa Dân Quốc (năm dương lịch - 1911): tháng 11/2026 -> "115-1".
    """
    roc_year = today.year - 1911
    if today.month >= 8:
        return f"{roc_year}-1"
    if today.month == 1:
        return f"{roc_year - 1}-1"
    return f"{roc_year - 1}-2"
