"""Test các route của Flask (không cần mạng: thay fetch_announcements bằng dữ liệu giả)."""
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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (FAKE_ITEMS, None))
    return app_module.app.test_client()


def test_home_shows_latest_announcements(client):
    html = client.get("/").get_data(as_text=True)
    assert "Latest announcements" in html
    assert "Scholarship news" in html


def test_home_hides_latest_when_api_fails(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (FAKE_ITEMS, "error"))
    html = app_module.app.test_client().get("/").get_data(as_text=True)
    assert "Scholarship news" not in html
    assert "unavailable right now" in html


def test_announcements_filter_by_category(client):
    html = client.get("/announcements?cat=Dorm").get_data(as_text=True)
    assert "宿舍申請" in html
    assert "Scholarship news" not in html


def test_announcements_category_dropdown_has_counts(client):
    html = client.get("/announcements").get_data(as_text=True)
    assert "Scholarship (1)" in html
    assert "Dorm (1)" in html


def test_announcements_bad_page_number_does_not_crash(client):
    assert client.get("/announcements?page=abc").status_code == 200
    assert client.get("/announcements?page=999").status_code == 200


def test_api_returns_filtered_json(client):
    data = client.get("/api/announcements?lang=en&limit=1").get_json()
    assert len(data) == 1
    assert data[0]["title"] == "Scholarship news"
