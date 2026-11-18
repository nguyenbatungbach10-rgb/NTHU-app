"""Test header bảo mật, "Remember me", đổi mật khẩu và xóa tài khoản."""
import account_logic
import app as app_module
import db


# ---------- logic thuần ----------

def test_password_error():
    assert account_logic.password_error("short", "short") == "Password must be 8 to 128 characters."
    assert account_logic.password_error("x" * 129, "x" * 129) == "Password must be 8 to 128 characters."
    assert account_logic.password_error("password123", "password124") == "Passwords do not match."
    assert account_logic.password_error("password123", "password123") is None


def test_auth_tag_changes_with_password_and_key():
    tag = account_logic.auth_tag("key", "hash-1")
    assert len(tag) == 16 and tag == account_logic.auth_tag("key", "hash-1")
    assert tag != account_logic.auth_tag("key", "hash-2") and tag != account_logic.auth_tag("other", "hash-1")
    assert account_logic.same_tag(tag, tag) and not account_logic.same_tag(None, tag)


# ---------- header bảo mật ----------

def test_security_headers_on_pages_and_api(make_browser):
    client = make_browser().client
    for url in ("/", "/login", "/api/announcements", "/no-such-page"):
        headers = client.get(url).headers
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert "Strict-Transport-Security" not in headers          # chỉ có trên server thật (PRODUCTION + HTTPS)


def test_hsts_only_in_production_over_https(make_browser, monkeypatch):
    monkeypatch.setattr(app_module, "PRODUCTION", True)
    client = make_browser().client
    assert "Strict-Transport-Security" not in client.get("/").headers
    assert client.get("/", base_url="https://localhost").headers["Strict-Transport-Security"] == "max-age=31536000"


# ---------- Remember me ----------

def session_cookie(response):
    return next(c for c in response.headers.getlist("Set-Cookie") if c.startswith("session="))


def test_remember_me_keeps_session_for_30_days(make_browser):
    b = make_browser()
    b.signup()
    b.client.post("/logout", data={"csrf_token": b.token()})
    plain = b.login()
    assert "Expires=" not in session_cookie(plain)               # cookie hết khi đóng trình duyệt
    b.client.post("/logout", data={"csrf_token": b.token()})
    remembered = b.client.post("/login", data={"email": "a@example.com", "password": "password123",
                                               "remember": "1", "csrf_token": b.token()})
    assert remembered.status_code == 302 and "Expires=" in session_cookie(remembered)
    assert app_module.app.config["PERMANENT_SESSION_LIFETIME"].days == 30


def test_login_page_has_remember_checkbox(make_browser):
    assert 'name="remember"' in make_browser().client.get("/login").get_data(as_text=True)


# ---------- trang Account ----------

def test_account_page_requires_login(make_browser, browser):
    assert make_browser().client.get("/account").status_code == 302
    html = browser.client.get("/account").get_data(as_text=True)
    assert "Change password" in html and "Delete account" in html and "a@example.com" in html
    assert "pbkdf2" not in html and "scrypt" not in html          # không lộ bản băm mật khẩu


def change(b, current="password123", new="newpassword1", confirm=None):
    return b.client.post("/account/password", data={
        "current_password": current, "new_password": new,
        "confirm": new if confirm is None else confirm, "csrf_token": b.token()})


def test_change_password_needs_current_password_and_valid_new_one(browser):
    assert change(browser, current="wrong-password").status_code == 400
    assert change(browser, new="short").status_code == 400
    assert change(browser, confirm="different1").status_code == 400
    assert browser.client.post("/account/password", data={"current_password": "password123",
                                                           "new_password": "newpassword1", "confirm": "newpassword1"}).status_code == 400
    assert change(browser).status_code == 302                     # đúng -> đổi xong


def test_change_password_logs_out_other_devices_but_not_this_one(app, make_browser):
    phone, laptop = make_browser(), make_browser()
    phone.signup()
    laptop.login()
    assert laptop.client.get("/account").status_code == 200
    assert change(phone).status_code == 302
    assert phone.client.get("/account").status_code == 200       # máy vừa đổi vẫn đăng nhập
    assert laptop.client.get("/account").status_code == 302      # máy kia bị đăng xuất
    assert laptop.login().status_code == 401                     # mật khẩu cũ hết dùng được
    assert laptop.login(password="newpassword1").status_code == 302


def test_delete_account_removes_all_data(app, browser, make_browser):
    browser.api("POST", "/api/events", {"title": "Exam", "date": "2026-12-01"})
    browser.api("POST", "/api/classes", {"name": "Calculus", "weekday": 0, "start": "10:10", "end": "12:00"})
    other = make_browser()
    other.signup("b@example.com")
    other.api("POST", "/api/events", {"title": "Other's event", "date": "2026-12-02"})

    def delete(password="password123", tick="1"):
        data = {"current_password": password, "csrf_token": browser.token()}
        if tick:
            data["confirm_delete"] = tick
        return browser.client.post("/account/delete", data=data)

    assert delete(password="wrong").status_code == 400
    assert delete(tick=None).status_code == 400
    assert delete().status_code == 302
    assert browser.client.get("/calendar").status_code == 302    # đã bị đăng xuất
    assert browser.login().status_code == 401                    # tài khoản không còn
    with app.app_context():
        conn = db.get_db()
        assert conn.execute("SELECT COUNT(*) FROM users WHERE email = 'a@example.com'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0] == 0
        assert [r[0] for r in conn.execute("SELECT title FROM events")] == ["Other's event"]   # người khác không bị ảnh hưởng


def test_account_forms_need_csrf(browser):
    assert browser.client.post("/account/delete", data={"current_password": "password123",
                                                        "confirm_delete": "1"}).status_code == 400
    assert browser.client.get("/account").status_code == 200      # vẫn còn tài khoản
