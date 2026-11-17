"""Đọc ngày hạn / ngày diễn ra từ TIÊU ĐỀ thông báo (thuần Python, không có Flask hay database).

Tiêu đề thông báo của NTHU viết ngày theo nhiều kiểu, ví dụ (lấy từ dữ liệu thật):
    本室於115年10月08日(星期四)辦理經費報支說明講習        -> 2026-10-08   (năm Dân Quốc 115)
    Outdoor disinfection operations on Nanda campus(115.03.21)  -> 2026-03-21
    Three pruning Notice on Nanda campus.(114/12/09-114/12/11)  -> 2025-12-09 (một khoảng ngày)
Cũng đọc được: 2026-11-20, 2026/11/20, 2026年11月20日, 11月20日, November 20, 2026, 20 Nov.

Hàm chính:
    extract_dates(title, posted)  -> các ngày tìm thấy trong tiêu đề, theo thứ tự xuất hiện
    suggest_date(title, posted)   -> ngày nên lưu vào lịch: ngày trong tiêu đề, hoặc ngày đăng nếu không có

Đây là cách đoán (heuristic), không phải cam kết đúng 100%. Nên giao diện luôn ghi rõ
"ngày lấy từ tiêu đề" để người dùng tự kiểm tra.
"""
import re
from datetime import date, timedelta

ROC_OFFSET = 1911          # năm Dân Quốc + 1911 = năm dương lịch (115 -> 2026)
GRACE_DAYS = 7             # ngày cũ hơn ngày đăng quá 7 ngày bị coi là ngày "tham chiếu", không phải hạn/ngày diễn ra

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_MONTH_NAMES = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

# Mỗi mẫu có tên để biết cách đọc các nhóm (group) bắt được. Thứ tự RẤT quan trọng:
# mẫu dài/cụ thể (có năm) chạy trước, rồi che phần đã khớp để mẫu ngắn không khớp lại.
_SEP = r"\s*[-/.]\s*"
_PATTERNS = [
    # 2026-11-20, 2026/11/20, 2026.11.20, 2026年11月20日
    ("full_ad", re.compile(r"(?<!\d)(20\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})(?!\d)")),
    # 115年10月08日, 115.03.21, 114/12/09  (năm Dân Quốc 3 chữ số, 100-199)
    ("full_roc", re.compile(r"(?<!\d)(1\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})(?!\d)")),
    # 11月20日, 11月20號 (không có năm)
    ("md_zh", re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日號号]")),
    # November 20, 2026 / Nov. 20 / Nov 20th
    ("md_en", re.compile(_MONTH_NAMES + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?!\d)(?:\s*,?\s*(20\d{2}))?", re.I)),
    # 20 November 2026 / 20th Nov
    ("dm_en", re.compile(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s+" + _MONTH_NAMES + r"\b\.?(?:\s*,?\s*(20\d{2}))?", re.I)),
]

# Từ gợi ý "đây là hạn chót". Khi tiêu đề có nhiều ngày (một khoảng) mà có từ này thì lấy ngày CUỐI.
DEADLINE_WORDS = re.compile(r"截止|期限|日止|止$|deadline|\bdue\b|until|no later than|\bclos(?:e|es|ing)\b", re.I)


def _is_iso(text):
    """True nếu text là ngày dạng YYYY-MM-DD có thật."""
    try:
        date.fromisoformat(text)
    except (TypeError, ValueError):
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", text))


def _make_date(year, month, day):
    """Tạo date nếu hợp lệ (loại 2月30日...), ngược lại None."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _closest_year(month, day, posted):
    """Ngày không ghi năm: chọn năm (năm đăng -1, năm đăng, năm đăng +1) cho ngày gần ngày đăng nhất.

    Ví dụ đăng 2026-12-20, "1月15日" -> 2027-01-15 (gần hơn 2026-01-15).
    """
    candidates = [d for d in (_make_date(posted.year + k, month, day) for k in (-1, 0, 1)) if d]
    return min(candidates, key=lambda d: abs(d - posted)) if candidates else None


def _month_number(name):
    return MONTHS[name[:3].lower()]


def _read_match(kind, match, posted):
    """Đổi một kết quả khớp thành date (hoặc None nếu không hợp lệ)."""
    groups = match.groups()
    if kind == "full_ad":
        return _make_date(int(groups[0]), int(groups[1]), int(groups[2]))
    if kind == "full_roc":
        return _make_date(int(groups[0]) + ROC_OFFSET, int(groups[1]), int(groups[2]))
    if kind == "md_zh":
        month, day, year = int(groups[0]), int(groups[1]), None
    elif kind == "md_en":
        month, day, year = _month_number(groups[0]), int(groups[1]), groups[2]
    else:  # dm_en
        day, month, year = int(groups[0]), _month_number(groups[1]), groups[2]
    if year:
        return _make_date(int(year), month, day)
    return _closest_year(month, day, posted)


def extract_dates(title, posted):
    """Các ngày (YYYY-MM-DD) tìm thấy trong tiêu đề, theo thứ tự xuất hiện, không trùng.

    `posted` là ngày đăng (YYYY-MM-DD). Bỏ qua:
      - ngày không có thật (2月30日)
      - ngày xa năm đăng hơn 1 năm
      - ngày cũ hơn ngày đăng quá GRACE_DAYS (thường là ngày tham chiếu: "theo thông báo ngày ...")
    """
    if not isinstance(title, str) or not _is_iso(posted):
        return []
    posted_date = date.fromisoformat(posted)
    earliest = posted_date - timedelta(days=GRACE_DAYS)

    found = []                  # (vị trí trong chuỗi, date)
    working = title             # bản làm việc: phần đã khớp bị thay bằng dấu cách để mẫu sau không khớp lại
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(working):
            value = _read_match(kind, match, posted_date)
            if value is not None:
                found.append((match.start(), value))
        working = pattern.sub(lambda m: " " * len(m.group(0)), working)

    result = []
    for _, value in sorted(found):
        iso = value.isoformat()
        if abs(value.year - posted_date.year) > 1 or value < earliest or iso in result:
            continue
        result.append(iso)
    return result


def suggest_date(title, posted):
    """Ngày nên lưu vào lịch cho một thông báo.

    Trả về {"date": ..., "from_title": True/False}.
      - Không tìm thấy ngày trong tiêu đề -> dùng ngày đăng, from_title = False.
      - Một ngày -> ngày đó.
      - Nhiều ngày (một khoảng): có từ "hạn chót" -> ngày cuối; không có -> ngày đầu.
    """
    dates = extract_dates(title, posted)
    if not dates:
        return {"date": posted, "from_title": False}
    chosen = dates[-1] if len(dates) > 1 and DEADLINE_WORDS.search(title) else dates[0]
    return {"date": chosen, "from_title": True}
