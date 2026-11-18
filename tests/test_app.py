"""Test các route công khai (không cần đăng nhập). Dữ liệu API được thay bằng dữ liệu giả
trong conftest.py nên không cần mạng."""
import app as app_module

from conftest import FAKE_ITEMS


def test_home_shows_latest_announcements(app):
    html = app.test_client().get("/").get_data(as_text=True)
    assert "Latest announcements" in html
    assert "Scholarship news" in html


def test_home_hides_latest_when_api_fails(app, monkeypatch):
    monkeypatch.setattr(app_module, "fetch_announcements",
                        lambda: (FAKE_ITEMS, {"kind": "sample", "reason": "Could not reach the NTHU Data API."}))
    html = app.test_client().get("/").get_data(as_text=True)
    assert "Scholarship news" not in html
    assert "unavailable right now" in html


def test_announcements_filter_by_category(app):
    html = app.test_client().get("/announcements?cat=Dorm").get_data(as_text=True)
    assert "宿舍申請" in html
    assert "Scholarship news" not in html


def test_announcements_category_dropdown_has_counts(app):
    html = app.test_client().get("/announcements").get_data(as_text=True)
    assert "Scholarship (1)" in html
    assert "Dorm (1)" in html


def test_announcements_bad_page_number_does_not_crash(app):
    client = app.test_client()
    assert client.get("/announcements?page=abc").status_code == 200
    assert client.get("/announcements?page=999").status_code == 200


def test_api_returns_filtered_json(app):
    data = app.test_client().get("/api/announcements?lang=en&limit=1").get_json()
    assert len(data) == 1
    assert data[0]["title"] == "Scholarship news"


# ---------- trang lỗi và favicon ----------

def test_404_page_uses_site_layout(app):
    response = app.test_client().get("/does-not-exist")
    html = response.get_data(as_text=True)
    assert response.status_code == 404 and "Page not found" in html and 'id="menu-button"' in html


def test_404_page_in_chinese(app):
    html = app.test_client().get("/nope", headers={"Accept-Language": "zh-TW"}).get_data(as_text=True)
    assert "找不到這個頁面" in html


def test_api_404_is_json(app):
    response = app.test_client().get("/api/does-not-exist")
    assert response.status_code == 404 and response.get_json() == {"error": "not found"}


def test_500_page(app, monkeypatch):
    def broken():
        raise RuntimeError("boom")
    monkeypatch.setattr(app_module, "fetch_announcements", broken)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = app.test_client().get("/")
    assert response.status_code == 500 and "Something went wrong" in response.get_data(as_text=True)
    assert "boom" not in response.get_data(as_text=True)          # không lộ chi tiết lỗi cho người dùng


def test_favicon(app):
    client = app.test_client()
    response = client.get("/favicon.ico")
    assert response.status_code == 301 and response.headers["Location"].endswith("/static/favicon.svg")
    assert client.get("/static/favicon.svg").status_code == 200
    assert 'rel="icon"' in client.get("/").get_data(as_text=True)
