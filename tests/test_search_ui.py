"""Test trang Announcements mới: tô vàng từ khóa, chip loại, bộ lọc gấp gọn."""
import app as app_module
import nthu_api

ITEMS = [
    {"title": "Taiwan Scholarship renewal", "link": "https://a", "date": "2026-11-18", "office": "Global Affairs",
     "language": "en", "category": "Scholarship"},
    {"title": "Dorm <b>repair</b> notice", "link": "https://b", "date": "2026-11-17", "office": "Housing",
     "language": "en", "category": "Dorm"},
]


def test_highlight():
    assert nthu_api.highlight("Taiwan Scholarship", "scholar") == [("Taiwan ", False), ("Scholar", True), ("ship", False)]
    assert nthu_api.highlight("A b a", "a") == [("A", True), (" b ", False), ("a", True)]
    assert nthu_api.highlight("abc", "") == [("abc", False)] and nthu_api.highlight("abc", "zz") == [("abc", False)]
    assert nthu_api.highlight("1+1=2", "+") == [("1", False), ("+", True), ("1=2", False)]   # ký tự đặc biệt của regex


def test_search_marks_keyword_and_escapes_html(app, monkeypatch):
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (ITEMS, None))
    client = app.test_client()
    html = client.get("/announcements?q=scholarship").get_data(as_text=True)
    assert "Taiwan <mark>Scholarship</mark> renewal" in html and "Dorm" not in html.split("cat-chips")[0][-200:]
    html = client.get("/announcements?q=repair").get_data(as_text=True)
    assert "Dorm &lt;b&gt;<mark>repair</mark>&lt;/b&gt; notice" in html     # chữ trong tiêu đề vẫn được escape


def test_chips_keep_search_and_view(app, monkeypatch):
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (ITEMS, None))
    html = app.test_client().get("/announcements?q=tai&view=deadlines").get_data(as_text=True)
    chips = html.split('class="cat-chips"')[1].split("</nav>")[0]
    assert "q=tai" in chips and "view=deadlines" in chips
    assert 'name="view" value="deadlines"' in html.split('class="search-bar"')[1].split("</form>")[0]
    assert "<details class=\"more-filters\" >" in html or 'class="more-filters"' in html
    assert "Clear all filters" in html
