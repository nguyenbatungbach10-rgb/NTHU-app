"""Cấu hình chung cho các test: mỗi test dùng một database tạm riêng và dữ liệu API giả."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module  # noqa: E402

FAKE_ITEMS = [
    {"title": "Scholarship news", "link": "http://a", "date": "2026-11-20",
     "office": "Student Affairs", "language": "en", "category": "Scholarship"},
    {"title": "宿舍申請", "link": "http://b", "date": "2026-11-18",
     "office": "Housing", "language": "zh-tw", "category": "Dorm"},
    {"title": "Registration reminder", "link": "http://c", "date": "2026-11-10",
     "office": "Registrar", "language": "en", "category": "Registration"},
]


@pytest.fixture(autouse=True)
def reset_announcement_state(monkeypatch):
    """Mỗi test bắt đầu sạch: chưa có lần gọi API thất bại nào, chưa nhớ file bản lưu nào."""
    import nthu_api
    monkeypatch.setattr(nthu_api, "_api_state", {"failed_at": 0.0})
    monkeypatch.setattr(nthu_api, "_snapshot_files", {})


@pytest.fixture(autouse=True)
def fake_announcements(monkeypatch):
    """Thay lệnh gọi NTHU Data API bằng dữ liệu giả: test chạy nhanh, không cần mạng."""
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (FAKE_ITEMS, None))


@pytest.fixture
def app(tmp_path):
    """Ứng dụng Flask dùng một file database tạm (xóa sau mỗi test)."""
    app_module.app.config.update(DATABASE=str(tmp_path / "test.db"), TESTING=True)
    return app_module.app


class Browser:
    """Giả lập một trình duyệt (có cookie riêng) để test đăng ký, đăng nhập, gọi API."""

    def __init__(self, app):
        self.client = app.test_client()

    def token(self):
        """Lấy CSRF token của phiên hiện tại (mở một trang để server tạo token)."""
        self.client.get("/login")
        with self.client.session_transaction() as session:
            return session["csrf"]

    def signup(self, email="a@example.com", password="password123", confirm=None):
        return self.client.post("/signup", data={
            "email": email, "password": password,
            "confirm": password if confirm is None else confirm,
            "csrf_token": self.token(),
        })

    def login(self, email="a@example.com", password="password123", next_url=""):
        return self.client.post("/login", data={
            "email": email, "password": password, "next": next_url,
            "csrf_token": self.token(),
        })

    def api(self, method, url, json=None):
        """Gọi API như JavaScript: kèm header X-CSRF-Token."""
        return self.client.open(url, method=method, json=json,
                                headers={"X-CSRF-Token": self.token()})


@pytest.fixture
def browser(app):
    """Một người dùng đã đăng ký và đang đăng nhập."""
    b = Browser(app)
    assert b.signup().status_code == 302
    return b


@pytest.fixture
def make_browser(app):
    """Tạo thêm trình duyệt khác (người dùng khác) để test cô lập dữ liệu."""
    return lambda: Browser(app)
