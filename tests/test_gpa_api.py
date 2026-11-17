"""Test API môn học, mục tiêu, trang GPA và việc cô lập dữ liệu giữa người dùng."""

COURSE = {"name": "Calculus", "credits": 3, "semester": "115-1", "grade": "A"}


def test_gpa_pages_require_login(app):
    from conftest import Browser
    b = Browser(app)
    response = b.client.get("/gpa")
    assert response.status_code == 302 and "/login" in response.headers["Location"]
    for method, url in [("GET", "/api/courses"), ("POST", "/api/courses"),
                        ("PUT", "/api/courses/1"), ("DELETE", "/api/courses/1"),
                        ("GET", "/api/goals"), ("PUT", "/api/goals")]:
        assert b.api(method, url, {}).status_code == 401, (method, url)


def test_create_list_update_delete_course(browser):
    created = browser.api("POST", "/api/courses", COURSE)
    assert created.status_code == 201
    course = created.get_json()
    assert course["id"] >= 1 and course["name"] == "Calculus"

    assert [c["id"] for c in browser.api("GET", "/api/courses").get_json()] == [course["id"]]

    updated = browser.api("PUT", f"/api/courses/{course['id']}", dict(COURSE, grade="B+", credits=4))
    assert updated.status_code == 200
    assert updated.get_json()["grade"] == "B+" and updated.get_json()["credits"] == 4

    assert browser.api("DELETE", f"/api/courses/{course['id']}").status_code == 204
    assert browser.api("GET", "/api/courses").get_json() == []
    assert browser.api("DELETE", f"/api/courses/{course['id']}").status_code == 404


def test_course_validation_returns_400(browser):
    for payload in [{}, dict(COURSE, credits=99), dict(COURSE, semester="bad"), dict(COURSE, grade="Z")]:
        response = browser.api("POST", "/api/courses", payload)
        assert response.status_code == 400 and "error" in response.get_json()
    assert browser.api("PUT", "/api/courses/999", COURSE).status_code == 404


def test_users_cannot_touch_each_others_courses(browser, make_browser):
    course = browser.api("POST", "/api/courses", COURSE).get_json()

    other = make_browser()
    other.signup("b@example.com")
    assert other.api("GET", "/api/courses").get_json() == []
    assert other.api("PUT", f"/api/courses/{course['id']}", dict(COURSE, grade="E")).status_code == 404
    assert other.api("DELETE", f"/api/courses/{course['id']}").status_code == 404

    mine = browser.api("GET", "/api/courses").get_json()
    assert mine[0]["grade"] == "A"          # không bị sửa
    assert b"Calculus" not in other.client.get("/gpa").data


def test_goals_default_set_and_update(browser):
    assert browser.api("GET", "/api/goals").get_json() == {"target_gpa": 3.5, "credits_required": 128}
    put = browser.api("PUT", "/api/goals", {"target_gpa": 3.8, "credits_required": 130})
    assert put.status_code == 200 and put.get_json() == {"target_gpa": 3.8, "credits_required": 130}
    browser.api("PUT", "/api/goals", {"target_gpa": 3.9, "credits_required": 132})   # upsert: ghi đè
    assert browser.api("GET", "/api/goals").get_json() == {"target_gpa": 3.9, "credits_required": 132}
    assert browser.api("PUT", "/api/goals", {"target_gpa": 9, "credits_required": 128}).status_code == 400


def test_goals_are_per_user(browser, make_browser):
    browser.api("PUT", "/api/goals", {"target_gpa": 4.0, "credits_required": 140})
    other = make_browser()
    other.signup("b@example.com")
    assert other.api("GET", "/api/goals").get_json() == {"target_gpa": 3.5, "credits_required": 128}


def test_gpa_writes_need_csrf_token(browser):
    cases = [("POST", "/api/courses", COURSE),
             ("PUT", "/api/goals", {"target_gpa": 3.9, "credits_required": 140})]
    for method, url, body in cases:
        for headers in ({}, {"X-CSRF-Token": ""}, {"X-CSRF-Token": "wrong"}):
            response = browser.client.open(url, method=method, json=body, headers=headers)
            assert response.status_code == 400
            assert response.get_json() == {"error": "Invalid or missing CSRF token"}
    # không có gì bị ghi vào database
    assert browser.api("GET", "/api/courses").get_json() == []
    assert browser.api("GET", "/api/goals").get_json() == {"target_gpa": 3.5, "credits_required": 128}


def test_gpa_page_empty_state_and_numbers(browser):
    page = browser.client.get("/gpa")
    assert page.status_code == 200
    assert b"No courses yet" in page.data and b"128" in page.data

    browser.api("POST", "/api/courses", COURSE)                                         # A, 3 tc
    browser.api("POST", "/api/courses", dict(COURSE, name="Physics", grade="B+"))       # B+, 3 tc
    browser.api("POST", "/api/courses", dict(COURSE, name="Chem", grade=""))            # dự định
    html = browser.client.get("/gpa").data.decode()
    assert "3.65" in html                   # GPA tích lũy
    assert "Semester 115-1" in html
    assert "Planned" in html and "aim" in html


def test_gpa_page_escapes_course_names(browser):
    browser.api("POST", "/api/courses", dict(COURSE, name="<script>alert(1)</script>"))
    html = browser.client.get("/gpa").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_deleting_user_removes_courses_and_goals(app, browser):
    """ON DELETE CASCADE: xóa tài khoản thì môn học và mục tiêu đi theo."""
    import db
    browser.api("POST", "/api/courses", COURSE)
    browser.api("PUT", "/api/goals", {"target_gpa": 3.5, "credits_required": 128})
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM users")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0


def test_db_get_course_is_scoped_to_owner(app, browser):
    """get_course không được trả môn của người khác (kiểm tra thẳng ở tầng db)."""
    import db
    course = browser.api("POST", "/api/courses", COURSE).get_json()
    with app.app_context():
        assert db.get_course(1, course["id"])["name"] == "Calculus"
        assert db.get_course(2, course["id"]) is None
