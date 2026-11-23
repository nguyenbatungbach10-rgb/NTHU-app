"""Test đa ngôn ngữ (i18n.py) và nút chọn ngôn ngữ / giao diện (/settings)."""
import glob
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

import home_logic
import i18n  # noqa: E402
import map_logic  # noqa: E402
from calendar_logic import validate_event  # noqa: E402
from gpa_logic import validate_course, validate_goals  # noqa: E402
from schedule_logic import validate_class  # noqa: E402
from study_logic import validate_session, validate_subject, validate_task  # noqa: E402

CJK = re.compile(r"[一-鿿]")
KEY_RE = re.compile(r"""\b_\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")""")


def template_keys():
    """Mọi chuỗi viết thẳng trong _('...') ở các template."""
    keys = set()
    for path in glob.glob(os.path.join(ROOT, "templates", "*.html")):
        for m in KEY_RE.finditer(open(path, encoding="utf-8").read()):
            keys.add((m.group(1) if m.group(1) is not None else m.group(2)).replace("\\'", "'").replace('\\"', '"'))
    return keys


# Chuỗi được dịch qua biến (_(label), _(item.category)...) nên không quét được từ template
DYNAMIC_KEYS = {
    "Home", "Calendar", "Schedule", "Announcements", "Credits & GPA", "Study", "Campus map",   # menu
    "Light", "Dark", "Auto",
    "Scholarship", "Dorm", "Careers", "Registration", "Events", "Other",                       # nhóm thông báo
    "Admissions", "Exchange", "Campus notices",
    "Could not reach the NTHU Data API.", "The NTHU Data API returned no usable data.",
    "Welcome! Your account is ready.", "Invalid email or password.", "You have been logged out.",
    "Please enter a valid email address.", "Password must be 8 to 128 characters.",
    "Passwords do not match.", "That email is already registered.", "No subject",
    "Main campus", "Nanda campus",
    "All announcements", "Deadlines", "Talks & events",
    "Your account and all your data have been deleted.", "Tick the box to confirm that you want to delete your account.",
    "Your password has been changed. Other devices have been logged out.", "Your current password is wrong.",
    "Calendar sync is off. The old link no longer works.", "Calendar sync settings saved.",
    "Disconnected. Events from that calendar were removed from this app.", "That file is not a calendar (.ics) file.",
    "That link is too long.", "Paste a link that starts with https:// or webcal://.",
    "Only Google Calendar, iCloud and Outlook calendar links are supported.",
    "This server could not reach that calendar. Upload an .ics file instead.",
    "The calendar link did not work. Check that you copied the secret address in iCal format.",
    "That calendar is too big (over 3 MB).", "That link is not a calendar (.ics) file.",
    "You have a new calendar link. Add it again in your calendar app.",
    "{label}: {name}, {meters} m (about {minutes} min walk)", "Walking directions in Google Maps", "{n} floors",
} | {label for _, label, _ in map_logic.CATEGORIES} | {label for _, label, _ in home_logic.STEPS}


def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", text))


# ---------- bản dịch đầy đủ ----------

def test_every_template_string_has_a_translation():
    missing = sorted(k for k in template_keys() if k not in i18n.ZH)
    assert missing == []
    assert len(template_keys()) > 150


def test_dynamic_and_js_strings_have_translations():
    assert sorted(k for k in DYNAMIC_KEYS | set(i18n.JS_KEYS) if k not in i18n.ZH) == []


def test_flash_messages_in_app_are_covered():
    source = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    flashed = set(re.findall(r'flash\("([^"]+)"', source)) | set(re.findall(r'error = "([^"]+)"', source))
    assert flashed and flashed <= DYNAMIC_KEYS


def test_js_calls_use_known_keys():
    keys = set()
    for name in ("app.js", "map.js"):
        source = open(os.path.join(ROOT, "static", name), encoding="utf-8").read()
        for single, double in re.findall(r"""\bt\(\s*(?:'([^']*)'|"([^"]*)")""", source):
            keys.add(single or double)
    for noun in ("task", "subject", "session", "class"):                  # tên ghép trong crudDialog
        keys |= {f"Add {noun}", f"Edit {noun}", f"Delete this {noun}?"}
    keys |= {"Edit event", "Add event", "Edit course", "Add course", "Add step"}
    assert sorted(k for k in keys if k not in i18n.JS_KEYS) == []


def test_translations_keep_placeholders_and_are_chinese():
    for key, value in i18n.ZH.items():
        assert value.strip(), key
        assert placeholders(key) == placeholders(value), key
        assert CJK.search(value) or value == key, key


# ---------- translate ----------

def test_translate_basics():
    assert i18n.translate("Calendar", "en") == "Calendar"
    assert i18n.translate("Calendar", "zh-TW") == "行事曆"
    assert i18n.translate("Not in the table", "zh-TW") == "Not in the table"        # thiếu bản dịch: giữ tiếng Anh
    assert i18n.translate("Page {page} of {pages}", "en", page=2, pages=5) == "Page 2 of 5"
    assert i18n.translate("Page {page} of {pages}", "zh-TW", page=2, pages=5) == "第 2 頁，共 5 頁"
    assert i18n.translate(None, "zh-TW") is None


def collect_validation_errors():
    bad = [validate_event({}), validate_event({"title": "a", "date": "x"}), validate_event({"title": "a" * 201, "date": "2026-01-01"}),
           validate_event({"title": "a", "date": "2026-01-01", "time": "99"}),
           validate_event({"title": "a", "date": "2026-01-01", "description": "x" * 1001}),
           validate_event({"title": "a", "date": "2026-01-01", "source_url": "javascript:x"}),
           validate_class("x"), validate_class({}), validate_class({"name": "a", "weekday": 9}),
           validate_class({"name": "a", "weekday": 1, "start": "x", "end": "y"}),
           validate_class({"name": "a", "weekday": 1, "start": "10:00", "end": "09:00"}),
           validate_class({"name": "a", "weekday": 1, "start": "09:00", "end": "10:00", "room": "r" * 101}),
           validate_subject({}), validate_subject({"name": "a", "notes": "n" * 1001}),
           validate_task({}), validate_task({"title": "a", "due_date": "bad"}), validate_task({"title": "a", "done": "yes"}),
           validate_task({"title": "a", "subject_id": -1}),
           validate_session({}), validate_session({"date": "2026-01-01", "minutes": 0}),
           validate_session({"date": "2026-01-01", "minutes": 5, "subject_id": "x"}),
           validate_session({"date": "2026-01-01", "minutes": 5, "note": "n" * 301}),
           validate_course({}), validate_course({"name": "a", "credits": 99, "semester": "115-1"}),
           validate_course({"name": "a", "credits": 3, "semester": "bad"}),
           validate_course({"name": "a", "credits": 3, "semester": "115-1", "grade": "Z"}),
           validate_goals({"target_gpa": 9, "credits_required": 128}), validate_goals({"target_gpa": 3, "credits_required": 0})]
    return {error for value, error in bad if error}


def test_every_validation_error_is_translated():
    errors = collect_validation_errors()
    assert len(errors) > 20
    for message in errors:
        translated = i18n.translate_error(message, "zh-TW")
        assert translated != message and CJK.search(translated), message
        assert i18n.translate_error(message, "en") == message


def test_translate_error_patterns_keep_numbers():
    assert i18n.translate_error("title is required (at most 200 characters)", "zh-TW") == "標題必須填寫（最多 200 個字）"
    assert i18n.translate_error("minutes must be a whole number from 1 to 1440", "zh-TW") == "分鐘數必須是 1 到 1440 的整數"
    assert "A+" in i18n.translate_error("grade must be empty (planned), P, or one of A+, A", "zh-TW")
    assert i18n.translate_error("something new", "zh-TW") == "something new"
    assert i18n.translate_error(None, "zh-TW") is None


# ---------- chọn ngôn ngữ / giao diện ----------

@pytest.mark.parametrize("cookie,header,expected", [
    ("zh-TW", "en-US", "zh-TW"), ("en", "zh-TW", "en"),
    (None, "zh-TW,zh;q=0.9,en;q=0.8", "zh-TW"), (None, "zh-CN", "zh-TW"), (None, "en-US,en;q=0.9", "en"),
    (None, "vi-VN,vi;q=0.9", "en"), (None, "en;q=0.5, zh;q=0.9", "zh-TW"), (None, "", "en"), (None, None, "en"),
    ("fr", "zh-TW", "zh-TW"), (None, "zh;q=abc, en", "en"),
])
def test_detect_lang(cookie, header, expected):
    assert i18n.detect_lang(cookie, header) == expected


def test_normalize_theme():
    assert [i18n.normalize_theme(v) for v in ("light", "dark", "auto", "pink", None)] == ["light", "dark", "auto", "auto", "auto"]


def test_dates_and_durations():
    assert i18n.month_label(2026, 11, "en") == "November 2026" and i18n.month_label(2026, 11, "zh-TW") == "2026年11月"
    assert i18n.month_short(1, "en") == "Jan" and i18n.month_short(1, "zh-TW") == "1月"
    assert i18n.month_long(12, "en") == "December" and i18n.month_long(12, "zh-TW") == "12月"
    assert i18n.weekday_long(0, "zh-TW") == "星期一" and i18n.weekday_long(6, "en") == "Sunday"
    assert i18n.weekday_short("zh-TW")[6] == "週日" and i18n.weekday_short("en")[0] == "Mon"
    assert i18n.weekday_initials("zh-TW") == list("一二三四五六日")
    assert i18n.format_minutes(90, "en") == "1h 30m" and i18n.format_minutes(90, "zh-TW") == "1小時30分"
    assert i18n.format_minutes(60, "zh-TW") == "1小時" and i18n.format_minutes(45, "zh-TW") == "45分"
    assert i18n.format_minutes(0, "zh-TW") == "0分"


def test_js_strings():
    assert i18n.js_strings("en") == {}
    zh = i18n.js_strings("zh-TW")
    assert set(zh) == set(i18n.JS_KEYS) and zh["Added"] == "已加入"


# ---------- route /settings và trang theo ngôn ngữ ----------

def settings(browser, **data):
    return browser.client.post("/settings", data=dict(data, csrf_token=browser.token()))


def test_settings_sets_cookies_and_redirects_back(browser):
    response = settings(browser, lang="zh-TW", next="/study")
    assert response.status_code == 302 and response.headers["Location"].endswith("/study")
    cookies = response.headers.getlist("Set-Cookie")
    assert any(c.startswith("lang=zh-TW") and "HttpOnly" in c and "SameSite=Lax" in c for c in cookies)
    response = settings(browser, theme="dark")
    assert any(c.startswith("theme=dark") for c in response.headers.getlist("Set-Cookie"))


def test_settings_requires_csrf(make_browser):
    response = make_browser().client.post("/settings", data={"lang": "zh-TW"})
    assert response.status_code == 400 and not response.headers.getlist("Set-Cookie")


def test_settings_ignores_bad_values_and_external_next(make_browser):
    b = make_browser()
    response = settings(b, lang="xx", theme="pink", next="https://evil.example/")
    assert not response.headers.getlist("Set-Cookie")
    assert "evil.example" not in response.headers["Location"]


def test_pages_render_in_chinese(browser):
    settings(browser, lang="zh-TW", theme="dark")
    home = browser.client.get("/").get_data(as_text=True)
    assert '<html lang="zh-TW" data-theme="dark">' in home
    assert "今天的課" in home and "行事曆" in home and "登出" in home
    assert '"Added": "已加入"' in home or '"Added":"已加入"' in home or "\\u5df2\\u52a0\\u5165" in home
    pages = {"/calendar?month=2026-12": "2026年12月", "/calendar/year?year=2026": "1月", "/schedule": "星期一",
             "/gpa": "GPA 目標", "/study": "讀書計畫", "/announcements": "校園公告", "/map": "校園地圖"}
    for url, text in pages.items():
        assert text in browser.client.get(url).get_data(as_text=True), url


def test_accept_language_header_picks_chinese_without_cookie(make_browser):
    html = make_browser().client.get("/login", headers={"Accept-Language": "zh-TW,zh;q=0.9"}).get_data(as_text=True)
    assert '<html lang="zh-TW"' in html and "登入" in html


def test_english_is_default(make_browser):
    html = make_browser().client.get("/login").get_data(as_text=True)
    assert '<html lang="en" data-theme="auto">' in html and "Log in" in html


def test_api_errors_and_flash_translated(browser, make_browser):
    settings(browser, lang="zh-TW")
    response = browser.api("POST", "/api/events", {"title": "", "date": ""})
    assert response.status_code == 400 and response.get_json()["error"] == "標題和日期都必須填寫"
    assert browser.api("GET", "/api/places/nope").get_json()["error"] == "找不到這個地點"
    visitor = make_browser()
    settings(visitor, lang="zh-TW")
    response = visitor.client.post("/login", data={"email": "x@example.com", "password": "wrong",
                                                    "csrf_token": visitor.token()})
    assert "電子郵件或密碼錯誤。" in response.get_data(as_text=True)


def test_api_errors_stay_english_by_default(browser):
    response = browser.api("POST", "/api/events", {"title": "", "date": ""})
    assert response.get_json()["error"] == "title and date are required"


def test_map_details_translated(make_browser):
    b = make_browser()
    settings(b, lang="zh-TW")
    d = b.client.get("/api/places/r3815072").get_json()
    assert d["category_label"] == "建築" and d["floors_text"] == "9 層樓"
    assert "公尺" in d["nearby"]["food"]["text"] and d["directions_label"].startswith("用 Google")


def test_no_duplicate_keys_in_translation_tables():
    """Khóa trùng trong dict Python thì bản sau đè bản trước mà không báo lỗi (từng làm "Next" dịch sai)."""
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).resolve().parent.parent / "i18n.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            assert len(keys) == len(set(keys)), {k for k in keys if keys.count(k) > 1}
