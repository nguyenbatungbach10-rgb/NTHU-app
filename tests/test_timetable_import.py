"""Test nhập thời khóa biểu từ 校務資訊系統 (chữ copy từ trang 課表)."""
from pathlib import Path

import db
import timetable_import as ti

# Chữ thật khi copy bảng 課表 bằng Chrome (dựng lại từ ảnh chụp thời khóa biểu 11510)
SAMPLE = (Path(__file__).parent / "nthu_timetable_copy.txt").read_text(encoding="utf-8")


def test_header_days():
    assert ti.header_days("時間\\星期\t星期一MON\t星期二TUE\t星期三WED") == [0, 1, 2]
    assert ti.header_days("Time\tTUE\tTHU") == [1, 3]
    assert ti.header_days("") == list(range(7))


def test_parse_cell():
    cell = "11510EE 231001\n計算機程式設計未亂數\nDELTA台達217\nIntroduction to Programming"
    assert ti.parse_cell(cell) == [{"code": "11510EE 231001", "name_zh": "計算機程式設計", "status": "未亂數",
                                    "room": "DELTA台達217", "name_en": "Introduction to Programming"}]
    pe = ti.parse_cell("11510PE 111025\n大一體育\nPhysical Education")[0]
    assert pe["room"] == "" and pe["name_en"] == "Physical Education" and pe["status"] == ""
    assert ti.parse_cell("") == [] and ti.parse_cell("\n") == []
    two = ti.parse_cell("11510CS 233601\n離散數學\nDELTA台達108\nDiscrete\n11510MATH103008\n微積分\nGEN IV綜四224\nCalculus I")
    assert [c["code"] for c in two] == ["11510CS 233601", "11510MATH103008"]


def test_real_timetable_sample():
    classes, skipped = ti.parse_timetable(SAMPLE)
    assert len(classes) == 13 and skipped == []
    first = classes[0]
    assert (first["name"], first["weekday"], first["start"], first["end"], first["room"]) == \
        ("計算機程式設計", 0, "08:00", "09:50", "DELTA台達217")           # 2 tiết liền nhau gộp lại
    wed = [(c["name"], c["start"], c["end"]) for c in classes if c["weekday"] == 2]
    assert wed == [("離散數學", "09:00", "09:50"), ("初級華語一", "13:20", "15:10"),
                   ("致命優雅: 自然界毒物之迷思、醫學與奧秘", "15:30", "17:20")]
    thu_calc = [c for c in classes if c["weekday"] == 3 and c["name"] == "微積分Ｂ一"]
    assert [(c["start"], c["end"]) for c in thu_calc] == [("10:10", "11:00")]
    assert next(c for c in classes if c["name"] == "大一體育")["room"] == ""


def test_english_names():
    classes, _ = ti.parse_timetable(SAMPLE, names="en")
    assert classes[0]["name"] == "Introduction to Programming"


def test_dropped_courses_are_skipped_and_gaps_not_merged():
    text = ("時間\t星期一MON\n08:00 -- 08:50\t11510CS 100100\n資料結構落選\nDELTA台達101\nData Structures\n"
            "09:00 -- 09:50\t\n10:10 -- 11:00\t11510EE 231001\n程式設計\nDELTA台達217\nProgramming\n"
            "11:10 -- 12:00\t\n13:20 -- 14:10\t11510EE 231001\n程式設計\nDELTA台達217\nProgramming\n")
    classes, skipped = ti.parse_timetable(text)
    assert [s["name"] for s in skipped] == ["資料結構"]
    assert [(c["start"], c["end"]) for c in classes] == [("10:10", "11:00"), ("13:20", "14:10")]   # không liền nhau


def test_nothing_found():
    assert ti.parse_timetable("hello") == ([], [])
    assert ti.parse_timetable(None) == ([], [])


def test_is_duplicate():
    item = {"name": "A", "weekday": 0, "start": "08:00", "end": "09:50"}
    assert ti.is_duplicate(item, [dict(item, id=1, room="x")])
    assert not ti.is_duplicate(item, [dict(item, start="10:10")])


# ---------- trang /schedule/import ----------

def post(b, action, **extra):
    data = {"text": SAMPLE, "names": "zh", "action": action, "csrf_token": b.token()}
    data.update(extra)
    return b.client.post("/schedule/import", data=data)


def count_classes(app):
    with app.app_context():
        return db.get_db().execute("SELECT COUNT(*) FROM classes").fetchone()[0]


def test_import_page_requires_login(make_browser):
    assert make_browser().client.get("/schedule/import").status_code == 302


def test_preview_saves_nothing_then_import_saves(app, browser):
    html = post(browser, "preview").get_data(as_text=True)
    assert "13 classes found" in html and "DELTA台達217" in html and count_classes(app) == 0
    assert post(browser, "import").status_code == 302
    assert count_classes(app) == 13
    page = browser.client.get("/schedule").get_data(as_text=True)
    assert "計算機程式設計" in page


def test_import_again_skips_duplicates_or_replaces(app, browser):
    post(browser, "import")
    html = post(browser, "preview").get_data(as_text=True)
    assert "13 classes are already in your timetable" in html
    post(browser, "import")
    assert count_classes(app) == 13                                    # không nhập trùng
    browser.api("POST", "/api/classes", {"name": "Old class", "weekday": 5, "start": "08:00", "end": "09:00"})
    post(browser, "import", replace="1")
    assert count_classes(app) == 13 and "Old class" not in browser.client.get("/schedule").get_data(as_text=True)


def test_import_only_touches_my_timetable(app, browser, make_browser):
    other = make_browser()
    other.signup("b@example.com")
    other.api("POST", "/api/classes", {"name": "Theirs", "weekday": 0, "start": "08:00", "end": "09:00"})
    post(browser, "import", replace="1")
    with app.app_context():
        names = [r[0] for r in db.get_db().execute("SELECT name FROM classes WHERE name = 'Theirs'")]
    assert names == ["Theirs"]


def test_bad_paste_and_csrf(browser):
    response = browser.client.post("/schedule/import", data={"text": "hello", "action": "import",
                                                            "csrf_token": browser.token()})
    assert response.status_code == 400 and "No classes found" in response.get_data(as_text=True)
    assert browser.client.post("/schedule/import", data={"text": SAMPLE, "action": "import"}).status_code == 400
