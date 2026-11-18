"""Test chuông thông báo: việc trễ hạn, sắp tới hạn, lớp sắp bắt đầu, sự kiện hôm nay / ngày mai."""
from datetime import date

import app as app_module
import home_logic

TODAY = date(2026, 11, 19)
NOW = 9 * 60 + 30            # 09:30


def test_notifications_order_and_rules():
    tasks = [{"title": "Old lab", "due_date": "2026-11-17"}, {"title": "Lab 7", "due_date": "2026-11-19"},
             {"title": "HW 8", "due_date": "2026-11-20"}]
    events = [{"title": "Morning talk", "date": "2026-11-19", "time": "08:00"},      # đã qua giờ -> bỏ
              {"title": "Club", "date": "2026-11-19", "time": "18:30"},
              {"title": "Holiday", "date": "2026-11-20", "time": ""}]
    classes = [{"name": "Calculus", "start": "10:10", "room": "GEN IV綜四224"},           # 40 phút nữa
               {"name": "Physics", "start": "13:20", "room": ""}]                        # còn lâu -> bỏ
    items = home_logic.notifications(TODAY, NOW, tasks, events, classes)
    assert [(i["kind"], i["title"]) for i in items] == [
        ("overdue", "Old lab"), ("class", "Calculus"), ("due", "Lab 7"),
        ("event", "Club"), ("due", "HW 8"), ("event", "Holiday")]
    assert items[1]["starts_in"] == 40 and items[2]["day"] == "today" and items[4]["day"] == "tomorrow"
    assert home_logic.notifications(TODAY, NOW, [], [], []) == []


def test_bell_badge_and_page(browser, monkeypatch):
    today = app_module.today_tw()
    assert 'class="badge"' not in browser.client.get("/").get_data(as_text=True)
    browser.api("POST", "/api/tasks", {"title": "Lab 7", "due_date": today.isoformat()})
    browser.api("POST", "/api/events", {"title": "All-day thing", "date": today.isoformat(), "time": ""})
    html = browser.client.get("/").get_data(as_text=True)
    assert '<span class="badge">2</span>' in html and "Notifications: 2" in html
    page = browser.client.get("/notifications").get_data(as_text=True)
    assert "Lab 7" in page and "Due today" in page and "All-day thing" in page


def test_bell_only_for_logged_in(make_browser):
    client = make_browser().client
    assert "/notifications" not in client.get("/").get_data(as_text=True)
    assert client.get("/notifications").status_code == 302
