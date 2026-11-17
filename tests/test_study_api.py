"""Test API Study (môn học, việc, buổi học), trang Study và cô lập dữ liệu giữa người dùng."""
from datetime import date


def make_subject(b, name="Calculus", notes=""):
    return b.api("POST", "/api/subjects", {"name": name, "notes": notes}).get_json()


def make_task(b, **fields):
    return b.api("POST", "/api/tasks", dict({"title": "Task"}, **fields))


def other_user(make_browser, email="b@example.com"):
    other = make_browser()
    other.signup(email)
    return other


# ---------- đăng nhập, CSRF ----------

def test_study_requires_login(app):
    from conftest import Browser
    b = Browser(app)
    response = b.client.get("/study")
    assert response.status_code == 302 and "/login" in response.headers["Location"]
    for base in ("/api/subjects", "/api/tasks", "/api/sessions"):
        for method, url in [("GET", base), ("POST", base), ("PUT", base + "/1"), ("DELETE", base + "/1")]:
            assert b.api(method, url, {}).status_code == 401, (method, url)


def test_study_writes_need_csrf(browser):
    cases = [("/api/subjects", {"name": "x"}), ("/api/tasks", {"title": "x"}),
             ("/api/sessions", {"date": "2026-11-18", "minutes": 5})]
    for url, body in cases:
        for headers in ({}, {"X-CSRF-Token": ""}, {"X-CSRF-Token": "wrong"}):
            response = browser.client.post(url, json=body, headers=headers)
            assert response.status_code == 400
            assert response.get_json() == {"error": "Invalid or missing CSRF token"}
        assert browser.api("GET", url).get_json() == []


# ---------- subjects ----------

def test_subject_crud(browser):
    created = browser.api("POST", "/api/subjects", {"name": " Calculus ", "notes": "https://example.com/book"})
    assert created.status_code == 201
    subject = created.get_json()
    assert subject["name"] == "Calculus"

    updated = browser.api("PUT", f"/api/subjects/{subject['id']}", {"name": "Calc II", "notes": ""})
    assert updated.get_json()["name"] == "Calc II"
    assert [s["name"] for s in browser.api("GET", "/api/subjects").get_json()] == ["Calc II"]

    assert browser.api("DELETE", f"/api/subjects/{subject['id']}").status_code == 204
    assert browser.api("DELETE", f"/api/subjects/{subject['id']}").status_code == 404
    assert browser.api("POST", "/api/subjects", {"name": ""}).status_code == 400
    assert browser.api("PUT", "/api/subjects/999", {"name": "x"}).status_code == 404


def test_subjects_are_private(browser, make_browser):
    subject = make_subject(browser)
    other = other_user(make_browser)
    assert other.api("GET", "/api/subjects").get_json() == []
    assert other.api("PUT", f"/api/subjects/{subject['id']}", {"name": "hacked"}).status_code == 404
    assert other.api("DELETE", f"/api/subjects/{subject['id']}").status_code == 404
    assert browser.api("GET", "/api/subjects").get_json()[0]["name"] == "Calculus"


# ---------- tasks ----------

def test_task_crud_and_toggle_done(browser):
    subject = make_subject(browser)
    created = make_task(browser, title=" Report ", due_date="2026-11-20", subject_id=subject["id"])
    assert created.status_code == 201
    task = created.get_json()
    assert task == {"id": task["id"], "subject_id": subject["id"], "parent_id": None,
                    "title": "Report", "due_date": "2026-11-20", "done": False}

    done = browser.api("PUT", f"/api/tasks/{task['id']}",
                       {"title": "Report", "due_date": "2026-11-20", "subject_id": subject["id"], "done": True})
    assert done.get_json()["done"] is True

    assert browser.api("DELETE", f"/api/tasks/{task['id']}").status_code == 204
    assert browser.api("DELETE", f"/api/tasks/{task['id']}").status_code == 404
    assert browser.api("PUT", "/api/tasks/999", {"title": "x"}).status_code == 404


def test_task_validation_errors(browser):
    for bad in [{}, {"title": ""}, {"title": "x", "due_date": "2026-02-30"}, {"title": "x", "done": "yes"},
                {"title": "x", "subject_id": "abc"}]:
        response = browser.api("POST", "/api/tasks", bad)
        assert response.status_code == 400 and "error" in response.get_json(), bad
    assert make_task(browser, subject_id=12345).status_code == 400            # môn không tồn tại
    assert make_task(browser, parent_id=12345).status_code == 400             # việc cha không tồn tại


def test_subtasks_rules(browser):
    subject = make_subject(browser)
    parent = make_task(browser, title="Project", subject_id=subject["id"]).get_json()
    child = make_task(browser, title="Step 1", parent_id=parent["id"], subject_id=subject["id"]).get_json()
    assert child["parent_id"] == parent["id"]
    assert child["subject_id"] is None                      # việc con không có môn riêng

    grandchild = make_task(browser, title="Too deep", parent_id=child["id"])
    assert grandchild.status_code == 400                    # chỉ một cấp việc con

    # sửa việc con: parent_id không đổi được, môn vẫn bị bỏ qua
    edited = browser.api("PUT", f"/api/tasks/{child['id']}",
                         {"title": "Step 1b", "subject_id": subject["id"], "parent_id": None, "done": True}).get_json()
    assert edited["parent_id"] == parent["id"] and edited["subject_id"] is None and edited["done"] is True


def test_deleting_parent_deletes_subtasks(browser):
    parent = make_task(browser, title="Project").get_json()
    make_task(browser, title="Step", parent_id=parent["id"])
    browser.api("DELETE", f"/api/tasks/{parent['id']}")
    assert browser.api("GET", "/api/tasks").get_json() == []


def test_deleting_subject_keeps_tasks_and_sessions(browser):
    subject = make_subject(browser)
    make_task(browser, title="Keep me", subject_id=subject["id"])
    browser.api("POST", "/api/sessions", {"date": "2026-11-18", "minutes": 30, "subject_id": subject["id"]})
    browser.api("DELETE", f"/api/subjects/{subject['id']}")
    assert browser.api("GET", "/api/tasks").get_json()[0]["subject_id"] is None
    assert browser.api("GET", "/api/sessions").get_json()[0]["subject_id"] is None


def test_tasks_are_private(browser, make_browser):
    task = make_task(browser, title="Secret").get_json()
    other = other_user(make_browser)
    assert other.api("GET", "/api/tasks").get_json() == []
    body = {"title": "hacked", "done": True}
    assert other.api("PUT", f"/api/tasks/{task['id']}", body).status_code == 404
    assert other.api("DELETE", f"/api/tasks/{task['id']}").status_code == 404
    assert browser.api("GET", "/api/tasks").get_json()[0]["title"] == "Secret"


def test_cannot_attach_to_another_users_subject_or_task(browser, make_browser):
    """Lỗ hổng cần chặn: dùng id của người khác trong subject_id / parent_id."""
    victim_subject = make_subject(browser, "Victim subject")
    victim_task = make_task(browser, title="Victim task").get_json()

    attacker = other_user(make_browser)
    # tạo việc / buổi học gắn vào môn của người khác
    assert make_task(attacker, subject_id=victim_subject["id"]).status_code == 400
    assert attacker.api("POST", "/api/sessions",
                        {"date": "2026-11-18", "minutes": 5, "subject_id": victim_subject["id"]}).status_code == 400
    # tạo việc con dưới việc cha của người khác
    assert make_task(attacker, parent_id=victim_task["id"]).status_code == 400
    # sửa việc / buổi học của mình để trỏ sang môn của người khác
    mine = make_task(attacker, title="mine").get_json()
    assert attacker.api("PUT", f"/api/tasks/{mine['id']}",
                        {"title": "mine", "subject_id": victim_subject["id"]}).status_code == 400
    my_session = attacker.api("POST", "/api/sessions", {"date": "2026-11-18", "minutes": 5}).get_json()
    assert attacker.api("PUT", f"/api/sessions/{my_session['id']}",
                        {"date": "2026-11-18", "minutes": 5, "subject_id": victim_subject["id"]}).status_code == 400

    # nạn nhân không bị ảnh hưởng
    assert len(browser.api("GET", "/api/tasks").get_json()) == 1
    assert browser.api("GET", "/api/sessions").get_json() == []


# ---------- sessions ----------

def test_session_crud(browser):
    subject = make_subject(browser)
    created = browser.api("POST", "/api/sessions",
                          {"date": "2026-11-18", "minutes": 90, "subject_id": subject["id"], "note": " ch.3 "})
    assert created.status_code == 201
    session = created.get_json()
    assert session["minutes"] == 90 and session["note"] == "ch.3"

    updated = browser.api("PUT", f"/api/sessions/{session['id']}",
                          {"date": "2026-11-19", "minutes": 45, "subject_id": None})
    assert updated.get_json()["minutes"] == 45 and updated.get_json()["subject_id"] is None

    assert browser.api("DELETE", f"/api/sessions/{session['id']}").status_code == 204
    assert browser.api("DELETE", f"/api/sessions/{session['id']}").status_code == 404
    assert browser.api("PUT", "/api/sessions/999", {"date": "2026-11-18", "minutes": 5}).status_code == 404
    for bad in [{}, {"date": "2026-11-18", "minutes": 0}, {"date": "bad", "minutes": 5},
                {"date": "2026-11-18", "minutes": 5000}]:
        assert browser.api("POST", "/api/sessions", bad).status_code == 400


def test_sessions_are_private_and_newest_first(browser, make_browser):
    browser.api("POST", "/api/sessions", {"date": "2026-11-10", "minutes": 10})
    newest = browser.api("POST", "/api/sessions", {"date": "2026-11-17", "minutes": 20}).get_json()
    assert [s["date"] for s in browser.api("GET", "/api/sessions").get_json()] == ["2026-11-17", "2026-11-10"]

    other = other_user(make_browser)
    assert other.api("GET", "/api/sessions").get_json() == []
    assert other.api("PUT", f"/api/sessions/{newest['id']}", {"date": "2026-11-17", "minutes": 1}).status_code == 404
    assert other.api("DELETE", f"/api/sessions/{newest['id']}").status_code == 404


# ---------- trang Study ----------

def test_study_page_empty_state(browser):
    html = browser.client.get("/study").data.decode()
    assert "No tasks yet" in html and "No subjects yet" in html and "No study time logged yet" in html


def test_study_page_shows_data_and_numbers(browser):
    today = date.today().isoformat()
    subject = make_subject(browser, "Physics")
    parent = make_task(browser, title="Lab report", subject_id=subject["id"], due_date="2020-01-01").get_json()
    make_task(browser, title="Write intro", parent_id=parent["id"])
    browser.api("POST", "/api/sessions", {"date": today, "minutes": 90, "subject_id": subject["id"]})
    html = browser.client.get("/study").data.decode()
    assert "Lab report" in html and "Write intro" in html and "Physics" in html
    assert "Overdue" in html                       # hạn 2020 đã quá
    assert "1h 30m" in html                        # 90 phút
    assert "0/1 steps" in html


def test_study_page_escapes_user_text_and_links_only_http(browser):
    subject = make_subject(browser, "<script>alert(1)</script>",
                           "see https://example.com/notes and javascript:alert(2) <b>x</b>")
    make_task(browser, title="<img src=x onerror=alert(3)>", subject_id=subject["id"])
    html = browser.client.get("/study").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x" not in html and "<b>x</b>" not in html
    assert 'href="https://example.com/notes"' in html          # link http(s) được biến thành thẻ a
    assert 'rel="noopener noreferrer"' in html
    assert 'href="javascript:' not in html                     # javascript: không bao giờ thành link


def test_study_page_is_private(browser, make_browser):
    make_task(browser, title="Private task")
    make_subject(browser, "Private subject")
    other = other_user(make_browser)
    html = other.client.get("/study").data.decode()
    assert "Private task" not in html and "Private subject" not in html


def test_deleting_user_removes_study_data(app, browser):
    import db
    subject = make_subject(browser)
    parent = make_task(browser, subject_id=subject["id"]).get_json()
    make_task(browser, parent_id=parent["id"])
    browser.api("POST", "/api/sessions", {"date": "2026-11-18", "minutes": 5})
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM users")
        conn.commit()
        for table in ("subjects", "tasks", "study_sessions"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


def test_db_getters_are_scoped_to_owner(app, browser):
    """Kiểm tra thẳng ở tầng db: các hàm get_* không trả dữ liệu của người khác."""
    import db
    subject = make_subject(browser)
    task = make_task(browser).get_json()
    session = browser.api("POST", "/api/sessions", {"date": "2026-11-18", "minutes": 5}).get_json()
    with app.app_context():
        assert db.get_subject(1, subject["id"]) and db.get_subject(2, subject["id"]) is None
        assert db.get_task(1, task["id"]) and db.get_task(2, task["id"]) is None
        assert db.get_session(1, session["id"]) and db.get_session(2, session["id"]) is None


def test_db_updates_are_scoped_to_owner(app, browser):
    """update_task / update_session tự kiểm tra user_id, không chỉ dựa vào route."""
    import db
    task = make_task(browser, title="Mine").get_json()
    session = browser.api("POST", "/api/sessions", {"date": "2026-11-18", "minutes": 5}).get_json()
    with app.app_context():
        hacked_task = {"title": "hacked", "due_date": "", "done": True, "subject_id": None}
        assert db.update_task(2, task["id"], hacked_task) is None
        hacked_session = {"date": "2026-01-01", "minutes": 999, "subject_id": None, "note": "x"}
        assert db.update_session(2, session["id"], hacked_session) is None
        assert db.get_task(1, task["id"])["title"] == "Mine"
        assert db.get_session(1, session["id"])["minutes"] == 5


# ---------- hạn nộp hiện trên Calendar ----------

def test_calendar_shows_open_tasks_with_due_date_in_that_month(browser):
    make_task(browser, title="Open task", due_date="2026-11-20")
    make_task(browser, title="Next month task", due_date="2026-12-05")
    make_task(browser, title="No due date")
    done = make_task(browser, title="Finished task", due_date="2026-11-21").get_json()
    browser.api("PUT", f"/api/tasks/{done['id']}", {"title": "Finished task", "due_date": "2026-11-21", "done": True})

    html = browser.client.get("/calendar?month=2026-11").data.decode()
    assert "Open task" in html
    assert "Next month task" not in html and "No due date" not in html
    assert "Finished task" not in html                               # việc đã xong không hiện
    assert 'href="/study"' in html and "task-pill" in html
    assert "Next month task" in browser.client.get("/calendar?month=2026-12").data.decode()


def test_calendar_shows_subtask_due_dates_and_marks_overdue(browser):
    parent = make_task(browser, title="Project").get_json()
    make_task(browser, title="Old step", parent_id=parent["id"], due_date="2020-03-01")
    html = browser.client.get("/calendar?month=2020-03").data.decode()
    assert "Old step" in html and "task-pill overdue" in html


def test_calendar_does_not_show_other_users_tasks(browser, make_browser):
    make_task(browser, title="Private task", due_date="2026-11-20")
    other = other_user(make_browser)
    assert "Private task" not in other.client.get("/calendar?month=2026-11").data.decode()


def test_calendar_escapes_task_titles(browser):
    make_task(browser, title="<script>alert(1)</script>", due_date="2026-11-20")
    html = browser.client.get("/calendar?month=2026-11").data.decode()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_db_list_tasks_due_is_scoped_and_ranged(app, browser):
    import db
    make_task(browser, title="In", due_date="2026-11-20")
    make_task(browser, title="Edge", due_date="2026-12-01")          # end không tính
    with app.app_context():
        assert [t["title"] for t in db.list_tasks_due(1, "2026-11-01", "2026-12-01")] == ["In"]
        assert db.list_tasks_due(2, "2026-11-01", "2026-12-01") == []
