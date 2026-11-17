"""Test đăng ký, đăng nhập, đăng xuất, CSRF và chuyển hướng an toàn."""
import sqlite3


def test_signup_logs_user_in_and_stores_hashed_password(app, make_browser):
    b = make_browser()
    response = b.signup("new@example.com", "password123")
    assert response.status_code == 302
    assert "new" in b.client.get("/").get_data(as_text=True)  # tên hiện trên thanh menu

    conn = sqlite3.connect(app.config["DATABASE"])
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    conn.close()
    assert stored != "password123" and "password123" not in stored


def test_signup_normalizes_email_and_rejects_duplicates(make_browser):
    assert make_browser().signup("User@Example.com").status_code == 302
    second = make_browser().signup("user@example.com")  # cùng email, khác hoa/thường
    assert second.status_code == 400
    assert "already registered" in second.get_data(as_text=True)


def test_signup_validates_input(make_browser):
    assert make_browser().signup("not-an-email").status_code == 400
    assert make_browser().signup("a@b.com", password="short").status_code == 400
    assert make_browser().signup("a@b.com", password="password123", confirm="different1").status_code == 400


def test_login_success_and_wrong_password(make_browser):
    first = make_browser()
    first.signup("a@example.com", "password123")

    other = make_browser()
    bad = other.login("a@example.com", "wrong-password")
    assert bad.status_code == 401
    assert "Invalid email or password" in bad.get_data(as_text=True)
    unknown = other.login("nobody@example.com", "password123")
    assert unknown.status_code == 401  # cùng một lỗi, không lộ email nào có thật

    good = other.login("a@example.com", "password123")
    assert good.status_code == 302


def test_logout_requires_post_and_ends_session(browser):
    assert browser.client.get("/logout").status_code == 405
    assert browser.client.get("/calendar").status_code == 200
    response = browser.client.post("/logout", data={"csrf_token": browser.token()})
    assert response.status_code == 302
    assert browser.client.get("/calendar").status_code == 302  # lại bị chặn


def test_protected_page_redirects_to_login_and_back(make_browser):
    b = make_browser()
    response = b.client.get("/calendar?month=2026-11")
    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("/login") and "next=" in location

    b.client.post("/signup", data={"email": "a@example.com", "password": "password123",
                                   "confirm": "password123", "csrf_token": b.token()})
    # đăng nhập lại với next -> quay về trang đang xem
    b2 = make_browser()
    done = b2.login("a@example.com", "password123", next_url="/calendar?month=2026-11")
    assert done.headers["Location"] == "/calendar?month=2026-11"


def test_login_does_not_redirect_to_other_sites(make_browser):
    make_browser().signup("a@example.com", "password123")
    for evil in ("https://evil.com", "//evil.com", "/\\evil.com", "javascript:alert(1)"):
        response = make_browser().login("a@example.com", "password123", next_url=evil)
        assert response.headers["Location"] == "/"


def test_post_without_csrf_token_is_rejected(make_browser):
    b = make_browser()
    b.client.get("/login")  # có session và token, nhưng ta không gửi kèm
    response = b.client.post("/login", data={"email": "a@example.com", "password": "x"})
    assert response.status_code == 400
    wrong = b.client.post("/login", data={"email": "a@example.com", "password": "x",
                                          "csrf_token": "not-the-token"})
    assert wrong.status_code == 400


def test_post_with_no_session_at_all_is_rejected(app):
    client = app.test_client()  # chưa từng mở trang nào -> chưa có token
    response = client.post("/signup", data={"email": "a@example.com", "password": "password123",
                                            "confirm": "password123", "csrf_token": ""})
    assert response.status_code == 400  # token rỗng không được coi là khớp


def test_api_requires_login(make_browser):
    b = make_browser()
    for method, url in (("GET", "/api/events"), ("POST", "/api/events"),
                        ("PUT", "/api/events/1"), ("DELETE", "/api/events/1")):
        response = b.api(method, url, json={"title": "x", "date": "2026-11-30"})
        assert response.status_code == 401
        assert response.get_json() == {"error": "login required"}
