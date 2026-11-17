"""Test API thời khóa biểu tuần, trang Schedule và cô lập dữ liệu giữa người dùng."""
from datetime import date

CLASS = {"name": "Calculus", "weekday": 0, "start": "10:10", "end": "12:00", "room": "R101"}


def other_user(make_browser, email="b@example.com"):
    other = make_browser()
    other.signup(email)
    return other


def test_schedule_requires_login(app):
    from conftest import Browser
    b = Browser(app)
    response = b.client.get("/schedule")
    assert response.status_code == 302 and "/login" in response.headers["Location"]
    for method, url in [("GET", "/api/classes"), ("POST", "/api/classes"),
                        ("PUT", "/api/classes/1"), ("DELETE", "/api/classes/1")]:
        assert b.api(method, url, {}).status_code == 401, (method, url)


def test_schedule_writes_need_csrf(browser):
    for headers in ({}, {"X-CSRF-Token": ""}, {"X-CSRF-Token": "wrong"}):
        response = browser.client.post("/api/classes", json=CLASS, headers=headers)
        assert response.status_code == 400
        assert response.get_json() == {"error": "Invalid or missing CSRF token"}
    assert browser.api("GET", "/api/classes").get_json() == []


def test_class_crud(browser):
    created = browser.api("POST", "/api/classes", CLASS)
    assert created.status_code == 201
    item = created.get_json()
    assert item == dict(CLASS, id=item["id"])           # cột "end" trả về đúng tên khóa "end"

    updated = browser.api("PUT", f"/api/classes/{item['id']}", dict(CLASS, name="Calc II", weekday=2, end="12:30"))
    assert updated.status_code == 200
    assert (updated.get_json()["name"], updated.get_json()["weekday"], updated.get_json()["end"]) == ("Calc II", 2, "12:30")

    assert [c["id"] for c in browser.api("GET", "/api/classes").get_json()] == [item["id"]]
    assert browser.api("DELETE", f"/api/classes/{item['id']}").status_code == 204
    assert browser.api("DELETE", f"/api/classes/{item['id']}").status_code == 404
    assert browser.api("PUT", "/api/classes/999", CLASS).status_code == 404


def test_class_validation_errors(browser):
    for bad in [{}, dict(CLASS, name=""), dict(CLASS, weekday=7), dict(CLASS, start="25:00"),
                dict(CLASS, start="12:00", end="10:00"), dict(CLASS, end="10:10"), dict(CLASS, room="r" * 101)]:
        response = browser.api("POST", "/api/classes", bad)
        assert response.status_code == 400 and "error" in response.get_json(), bad
    assert browser.api("GET", "/api/classes").get_json() == []


def test_classes_are_private(browser, make_browser):
    item = browser.api("POST", "/api/classes", CLASS).get_json()
    other = other_user(make_browser)
    assert other.api("GET", "/api/classes").get_json() == []
    assert other.api("PUT", f"/api/classes/{item['id']}", dict(CLASS, name="hacked")).status_code == 404
    assert other.api("DELETE", f"/api/classes/{item['id']}").status_code == 404
    assert browser.api("GET", "/api/classes").get_json()[0]["name"] == "Calculus"
    assert "Calculus" not in other.client.get("/schedule").data.decode()


def test_schedule_page_empty_state(browser):
    html = browser.client.get("/schedule").data.decode()
    assert "No classes yet" in html and "No classes today" in html


def test_schedule_page_shows_classes_and_conflicts(browser):
    browser.api("POST", "/api/classes", dict(CLASS, name="Calculus", weekday=0, start="09:00", end="11:00"))
    browser.api("POST", "/api/classes", dict(CLASS, name="Physics", weekday=0, start="10:00", end="12:00"))
    browser.api("POST", "/api/classes", dict(CLASS, name="Chemistry", weekday=2, start="13:00", end="14:00"))
    html = browser.client.get("/schedule").data.decode()
    assert "Calculus" in html and "Physics" in html and "Chemistry" in html
    assert html.count("overlaps another class") == 2          # chỉ hai môn trùng giờ bị cảnh báo
    assert "5h" in html                                         # 2h + 2h + 1h


def test_schedule_page_shows_todays_classes(browser):
    today = date.today().weekday()
    browser.api("POST", "/api/classes", dict(CLASS, name="TodayClass", weekday=today))
    browser.api("POST", "/api/classes", dict(CLASS, name="OtherDay", weekday=(today + 1) % 7))
    html = browser.client.get("/schedule").data.decode()
    today_section = html.split("Today &middot;")[1].split("</section>")[0]
    assert "TodayClass" in today_section and "OtherDay" not in today_section


def test_weekend_columns_only_when_needed(browser):
    assert "Saturday</span>" not in browser.client.get("/schedule").data.decode()
    browser.api("POST", "/api/classes", dict(CLASS, weekday=5))
    assert "Saturday</span>" in browser.client.get("/schedule").data.decode()


def test_schedule_page_escapes_user_text(browser):
    browser.api("POST", "/api/classes", dict(CLASS, name="<script>alert(1)</script>", room="<img src=x onerror=alert(2)>"))
    html = browser.client.get("/schedule").data.decode()
    assert "<script>alert(1)</script>" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html


def test_deleting_user_removes_classes(app, browser):
    import db
    browser.api("POST", "/api/classes", CLASS)
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM users")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0] == 0


def test_db_class_functions_are_scoped_to_owner(app, browser):
    import db
    item = browser.api("POST", "/api/classes", CLASS).get_json()
    with app.app_context():
        assert db.get_class(1, item["id"]) and db.get_class(2, item["id"]) is None
        assert db.update_class(2, item["id"], dict(CLASS, name="hacked")) is None
        assert db.delete_class(2, item["id"]) is False
        assert db.list_classes(2) == []
        assert db.get_class(1, item["id"])["name"] == "Calculus"
