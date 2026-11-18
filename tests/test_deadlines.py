"""Test "Upcoming deadlines": thông báo có ngày ghi trong tiêu đề, gần nhất trước."""
from datetime import date

import pytest

import app as app_module
import nthu_api
from calendar_logic import today_tw

TODAY = date(2026, 11, 19)


def item(title, day="", office="教務處"):
    return {"title": title, "date": day, "link": "https://example.com/" + title, "office": office,
            "language": "zh-tw", "category": nthu_api.classify(title)}


@pytest.fixture(autouse=True)
def clear_memo(monkeypatch):
    monkeypatch.setattr(nthu_api, "_dates_memo", {"key": None, "rows": []})


def test_upcoming_dates_sorted_and_windowed():
    items = [item("獎學金申請至12月5日止", "2026-11-10"), item("講座 11月25日"), item("Deadline Dec 1"),
             item("申請至2027年3月1日止"), item("宿舍修繕系統啟用", "2026-11-18"), item("報名截止 11月10日")]
    rows = nthu_api.upcoming_dates(items, TODAY, days=60)
    assert [r["due"] for r in rows] == ["2026-11-25", "2026-12-01", "2026-12-05"]   # quá 60 ngày, không ngày, đã qua: bỏ
    assert [r["days_left"] for r in rows] == [6, 12, 16]
    assert [r["is_deadline"] for r in rows] == [False, True, True]                  # "講座" chỉ là ngày diễn ra


def test_upcoming_dates_split_deadlines_and_events():
    items = [item("獎學金申請至12月5日止"), item("講座 11月25日"), item("(轉知)自即日起至115年11月20日止受理推薦")]
    assert [r["due"] for r in nthu_api.upcoming_dates(items, TODAY, kind="deadline")] == ["2026-11-20", "2026-12-05"]
    assert [r["due"] for r in nthu_api.upcoming_dates(items, TODAY, kind="event")] == ["2026-11-25"]


def test_upcoming_dates_today_counts_and_copies():
    items = [item("截止 11月19日")]
    rows = nthu_api.upcoming_dates(items, TODAY)
    assert rows[0]["days_left"] == 0 and "due" not in items[0]                      # bản sao, không sửa dữ liệu gốc


def test_upcoming_dates_memo_is_per_day():
    items = [item("截止 11月19日")]
    assert len(nthu_api.upcoming_dates(items, TODAY)) == 1
    assert nthu_api.upcoming_dates(items, date(2026, 11, 20)) == []                 # ngày khác thì tính lại


def fake_items():
    today = today_tw()
    soon = today.replace(day=1)
    talk = f"專題演講 {today.year}/{today.month}/{today.day}"          # chỉ là ngày diễn ra, hôm nay
    return [item(f"獎學金申請至{(today.month % 12) + 1}月1日止", "", "學務處"), item("宿舍公告", today.isoformat(), "學務處"),
            item("Old news", "2020-01-01"), item(talk, today.isoformat(), "理學院")], soon


def test_deadlines_view_page(make_browser, monkeypatch):
    items, _ = fake_items()
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, None))
    html = make_browser().client.get("/announcements?view=deadlines").get_data(as_text=True)
    assert "獎學金申請至" in html and "宿舍公告" not in html and "Old news" not in html
    assert "專題演講" not in html                                                # buổi nói chuyện không phải hạn chót
    assert "deadlines in the next" in html and 'name="view" value="deadlines"' in html
    assert "in " in html and "days" in html


def test_events_view_page(make_browser, monkeypatch):
    items, _ = fake_items()
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, None))
    html = make_browser().client.get("/announcements?view=events").get_data(as_text=True)
    assert "專題演講" in html and "獎學金申請至" not in html
    assert "Takes place" in html and "today" in html and 'name="view" value="events"' in html


def test_deadlines_view_keeps_filters_and_default_view(make_browser, monkeypatch):
    items, _ = fake_items()
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, None))
    client = make_browser().client
    assert "獎學金申請至" not in client.get("/announcements?view=deadlines&office=教務處").get_data(as_text=True)
    html = client.get("/announcements?view=bogus").get_data(as_text=True)
    assert "Old news" in html                                                    # giá trị lạ -> xem tất cả


def test_home_shows_upcoming_events_but_not_from_sample_data(make_browser, monkeypatch):
    items, _ = fake_items()
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, None))
    html = make_browser().client.get("/").get_data(as_text=True)
    block = html.split("Upcoming events")[1].split("Latest announcements")[0]
    assert "view=events" in block and "專題演講" in block
    assert "獎學金申請至" not in block                                     # hạn chót không hiện ở khối này
    monkeypatch.setattr(app_module, "fetch_announcements",
                        lambda: (nthu_api.SAMPLE_ANNOUNCEMENTS, {"kind": "sample", "reason": "x"}))
    assert "Upcoming events" not in make_browser().client.get("/").get_data(as_text=True)


def test_undated_announcement_with_title_date_can_be_saved(browser, monkeypatch):
    items, _ = fake_items()
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, None))
    html = browser.client.get("/announcements").get_data(as_text=True)
    assert 'data-save' in html and "date found in the title" in html


def test_deadlines_in_chinese(make_browser, monkeypatch):
    items, _ = fake_items()
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (items, None))
    html = make_browser().client.get("/announcements?view=deadlines", headers={"Accept-Language": "zh-TW"}).get_data(as_text=True)
    assert "截止期限" in html and "還有" in html
