"""Test các route công khai (không cần đăng nhập). Dữ liệu API được thay bằng dữ liệu giả
trong conftest.py nên không cần mạng."""
import app as app_module

from conftest import FAKE_ITEMS


def test_home_shows_latest_announcements(app):
    html = app.test_client().get("/").get_data(as_text=True)
    assert "Latest announcements" in html
    assert "Scholarship news" in html


def test_home_hides_latest_when_api_fails(app, monkeypatch):
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (FAKE_ITEMS, "error"))
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
