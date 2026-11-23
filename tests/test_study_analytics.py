"""Test thống kê học tập: cột theo ngày, so với kỳ trước, tỉ lệ theo môn, chuỗi ngày học."""
from datetime import date

import study_logic as sl

TODAY = date(2026, 11, 19)   # Thứ Năm
NAMES = {1: "Calculus", 2: "Physics"}


def s(day, minutes, subject=None):
    return {"date": day, "minutes": minutes, "subject_id": subject}


SESSIONS = [s("2026-11-16", 60, 1), s("2026-11-17", 120, 2), s("2026-11-18", 45, 1), s("2026-11-19", 30, 1),
            s("2026-11-10", 90, 2), s("2026-11-11", 60, None)]


def test_period_days():
    week = sl.period_days(TODAY, "week")
    assert [d.day for d in week] == [16, 17, 18, 19, 20, 21, 22]
    month = sl.period_days(TODAY, "month")
    assert len(month) == 30 and month[-1] == TODAY


def test_percent_change_and_streak():
    assert sl.percent_change(480, 360) == 33 and sl.percent_change(30, 60) == -50 and sl.percent_change(10, 0) is None
    assert sl.study_streak(SESSIONS, TODAY) == 4
    assert sl.study_streak(SESSIONS, date(2026, 11, 20)) == 4           # hôm nay chưa học: tính tới hôm qua
    assert sl.study_streak(SESSIONS, date(2026, 11, 25)) == 0
    assert sl.study_streak([], TODAY) == 0


def test_subject_shares_and_donut():
    shares = sl.subject_shares(SESSIONS, NAMES, "2026-11-16", "2026-11-23")
    assert [(r["name"], r["percent"], r["slot"]) for r in shares] == [("Calculus", 53, 1), ("Physics", 47, 2)]
    donut = sl.donut_gradient(shares)
    assert donut.startswith("conic-gradient(var(--c1) 0.0% 52.9%") and donut.endswith("100.0%)")
    assert sl.donut_gradient([]) == "none" and sl.subject_shares([], NAMES, "a", "z") == []
    many = [s("2026-11-16", 10 * (i + 1), i) for i in range(7)]
    shares = sl.subject_shares(many, {}, "2026-11-16", "2026-11-17")
    assert len(shares) == 6 and shares[-1]["name"] == "Other" and shares[-1]["minutes"] == 30   # 2 môn ít nhất gộp lại


def test_analytics_week_and_month():
    a = sl.analytics(SESSIONS, NAMES, TODAY, "week")
    assert a["total"] == 255 and a["previous"] == 150 and a["change"] == 70
    assert [b["minutes"] for b in a["bars"]] == [60, 120, 45, 30, 0, 0, 0]
    assert a["bars"][1]["percent"] == 100 and a["bars"][3]["is_today"] and a["bars"][4]["future"]
    assert a["streak"] == 4 and a["best_weekday"] == 1                  # thứ Ba học nhiều nhất
    month = sl.analytics(SESSIONS, NAMES, TODAY, "month")
    assert month["total"] == 405 and len(month["bars"]) == 30
    assert sl.analytics([], NAMES, TODAY, "bogus")["period"] == "week"


def test_study_page_shows_charts(browser):
    subject = browser.api("POST", "/api/subjects", {"name": "Calculus"}).get_json()
    import app as app_module                                       # ngày hôm nay (test không phụ thuộc ngày chạy)
    browser.api("POST", "/api/sessions", {"date": app_module.today_tw().isoformat(), "minutes": 45,
                                          "subject_id": subject["id"]})
    html = browser.client.get("/study").get_data(as_text=True)
    assert 'class="day-bars' in html and "conic-gradient(var(--c1)" in html and "Time by subject" in html
    assert browser.client.get("/study?period=month").status_code == 200
