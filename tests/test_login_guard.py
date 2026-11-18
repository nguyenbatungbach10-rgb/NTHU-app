"""Test chống đoán mật khẩu: login_guard.py (logic thuần) và route /login."""
import app as app_module
import login_guard
from login_guard import MAX_PER_ACCOUNT, MAX_PER_IP, WINDOW_SECONDS, lockout_minutes, recent

NOW = 1_000_000.0


# ---------- logic thuần ----------

def test_recent_keeps_only_last_15_minutes():
    times = [NOW - WINDOW_SECONDS - 1, NOW - WINDOW_SECONDS, NOW - 60, NOW]
    assert recent(times, NOW) == [NOW - 60, NOW]


def test_no_lock_below_the_limit():
    assert lockout_minutes([NOW - 10] * (MAX_PER_ACCOUNT - 1), [], NOW) == 0


def test_lock_after_too_many_failures_for_one_account():
    times = [NOW - 60 * i for i in range(MAX_PER_ACCOUNT)]   # 0..4 phút trước
    # Lần sai cũ nhất (4 phút trước) hết hạn sau 11 phút nữa
    assert lockout_minutes(times, times, NOW) == 11


def test_old_failures_do_not_count():
    times = [NOW - WINDOW_SECONDS - 5] * 10
    assert lockout_minutes(times, times, NOW) == 0


def test_lock_after_too_many_failures_from_one_ip():
    ip_times = [NOW - 1] * MAX_PER_IP                       # nhiều email khác nhau
    assert lockout_minutes([], ip_times, NOW) == 15


def test_wait_is_at_least_one_minute():
    times = [NOW - WINDOW_SECONDS + 1] * MAX_PER_ACCOUNT    # còn 1 giây nữa là hết hạn
    assert lockout_minutes(times, [], NOW) == 1


# ---------- route /login ----------

def test_login_locks_after_five_wrong_passwords(make_browser):
    b = make_browser()
    b.signup()
    b.client.post("/logout", data={"csrf_token": b.token()})
    for _ in range(MAX_PER_ACCOUNT):
        assert b.login(password="wrong-password").status_code == 401
    # Bây giờ cả mật khẩu đúng cũng bị chặn tạm thời
    blocked = b.login()
    assert blocked.status_code == 429
    assert b"Too many failed attempts" in blocked.data
    with b.client.session_transaction() as session:
        assert "user_id" not in session


def test_lock_ends_after_the_window(make_browser, monkeypatch):
    b = make_browser()
    b.signup()
    b.client.post("/logout", data={"csrf_token": b.token()})
    for _ in range(MAX_PER_ACCOUNT):
        b.login(password="wrong-password")
    later = app_module.time.time() + WINDOW_SECONDS + 1
    monkeypatch.setattr(app_module.time, "time", lambda: later)
    assert b.login().status_code == 302


def test_successful_login_clears_failures(make_browser):
    b = make_browser()
    b.signup()
    b.client.post("/logout", data={"csrf_token": b.token()})
    for _ in range(MAX_PER_ACCOUNT - 1):
        b.login(password="wrong-password")
    assert b.login().status_code == 302                     # đúng -> xóa các lần sai
    b.client.post("/logout", data={"csrf_token": b.token()})
    for _ in range(MAX_PER_ACCOUNT - 1):
        assert b.login(password="wrong-password").status_code == 401
    assert b.login().status_code == 302


def test_other_accounts_are_not_locked(make_browser):
    b = make_browser()
    b.signup("b@example.com")
    b.client.post("/logout", data={"csrf_token": b.token()})
    for _ in range(MAX_PER_ACCOUNT):
        b.login("a@example.com", password="wrong-password")
    assert b.login("b@example.com").status_code == 302


def test_lock_message_is_translated(make_browser):
    b = make_browser()
    b.client.set_cookie("lang", "zh-TW")
    for _ in range(MAX_PER_ACCOUNT):
        b.login("nobody@example.com", password="x")
    blocked = b.login("nobody@example.com", password="x")
    assert blocked.status_code == 429
    assert "登入失敗次數過多" in blocked.get_data(as_text=True)


def test_cookies_are_not_secure_in_development(app):
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert login_guard.MAX_PER_ACCOUNT == 5


def test_cookies_are_secure_when_production(app, make_browser, monkeypatch):
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", True)
    b = make_browser()
    response = b.client.post("/settings", data={"csrf_token": b.token(), "lang": "en", "next": "/"},
                             base_url="https://localhost")
    cookies = response.headers.getlist("Set-Cookie")
    assert cookies and all("Secure" in c for c in cookies)
