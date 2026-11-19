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
    chips = html.split('class="cat-chips"')[1].split("</nav>")[0]
    assert "Scholarship <small>1</small>" in chips and "Dorm <small>1</small>" in chips
    assert 'cat=Scholarship' in chips and 'aria-current="page">All<' in chips


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
    assert response.status_code == 301 and "/static/favicon.svg?v=" in response.headers["Location"]
    assert client.get("/static/favicon.svg").status_code == 200
    assert 'rel="icon"' in client.get("/").get_data(as_text=True)



def test_static_files_are_versioned_and_cached_for_a_year(app):
    """Link tới /static/ có ?v=<thời điểm sửa file>; có ?v thì trình duyệt được nhớ 1 năm, không có thì phải hỏi lại."""
    import re
    client = app.test_client()
    html = client.get("/login").get_data(as_text=True)
    css = re.search(r'/static/style\.css\?v=(\d+)', html)
    assert css and re.search(r'/static/app\.js\?v=\d+', html)
    cached = client.get(css[0])
    assert cached.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert "immutable" not in client.get("/static/style.css").headers.get("Cache-Control", "")
    assert "immutable" not in client.get("/").headers.get("Cache-Control", "")      # trang HTML không bị nhớ


def test_fonts_do_not_block_rendering(app):
    html = app.test_client().get("/login").get_data(as_text=True)
    assert 'media="print" onload="this.media=\'all\'"' in html and "<noscript>" in html


def test_warm_caches_runs_without_errors(capsys):
    import app as app_module
    app_module.warm_caches()
    assert "[warm_caches]" not in capsys.readouterr().out


def test_speculation_rules_are_valid_json_and_skip_unsafe_links(app):
    import json
    html = app.test_client().get("/login").get_data(as_text=True)
    rules = json.loads(html.split('<script type="speculationrules">')[1].split("</script>")[0])
    where = rules["prerender"][0]["where"]["and"]
    excluded = where[1]["not"]["href_matches"]
    assert "/logout" in excluded and "/calendar/feed/*" in excluded and "/static/*" in excluded
    assert rules["prerender"][0]["eagerness"] == "moderate"
