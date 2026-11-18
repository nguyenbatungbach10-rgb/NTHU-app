"""Test trang /map và các API địa điểm."""
from datetime import date

CLASS = {"name": "Calculus", "start": "10:10", "end": "12:00", "room": "Delta 205"}


def test_map_page_public(make_browser):
    html = make_browser().client.get("/map").get_data(as_text=True)
    assert "Campus map" in html and 'data-mode="3d"' in html and "OpenStreetMap contributors" in html
    assert 'data-category="academic"' in html and "Main campus" in html and "Nanda campus" in html
    assert "Today's classes" not in html
    assert "theme-amber" in html and 'aria-current="page"' in html


def test_map_page_search_without_javascript(make_browser):
    html = make_browser().client.get("/map?q=綜三").get_data(as_text=True)
    assert "第三綜合大樓" in html and 'data-focus="w180522503"' in html


def test_map_page_room_query_focuses_building(make_browser):
    html = make_browser().client.get("/map?q=Delta 205").get_data(as_text=True)
    assert 'data-focus="r3815072"' in html


def test_map_page_place_param_and_unknown(make_browser):
    client = make_browser().client
    assert 'data-focus="w180522500"' in client.get("/map?place=w180522500").get_data(as_text=True)
    html = client.get("/map?place=nope&q=zzzz").get_data(as_text=True)
    assert 'data-focus=""' in html and 'No place matches "zzzz"' in html


def test_map_page_escapes_query(make_browser):
    html = make_browser().client.get("/map?q=<script>alert(1)</script>").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html


def test_api_places_geojson(make_browser):
    data = make_browser().client.get("/api/places").get_json()
    assert data["type"] == "FeatureCollection" and len(data["features"]) > 150
    props = data["features"][0]["properties"]
    assert set(props) == {"id", "name", "name_en", "category", "color"}


def test_api_search(make_browser):
    client = make_browser().client
    assert client.get("/api/places/search?q=delta").get_json()[0]["name"] == "台達館"
    assert client.get("/api/places/search?q=").get_json() == []
    assert client.get("/api/places/search").get_json() == []


def test_api_place_details_and_404(make_browser):
    client = make_browser().client
    d = client.get("/api/places/r3815072").get_json()
    assert d["name"] == "台達館" and "food" in d["nearby"] and d["directions_url"].startswith("https://")
    response = client.get("/api/places/nope")
    assert response.status_code == 404 and response.get_json() == {"error": "place not found"}


def test_todays_classes_on_map(browser):
    browser.api("POST", "/api/classes", dict(CLASS, weekday=date.today().weekday()))
    browser.api("POST", "/api/classes", dict(CLASS, name="Mystery", room="Somewhere 9", weekday=date.today().weekday()))
    browser.api("POST", "/api/classes", dict(CLASS, name="Tomorrow", weekday=(date.today().weekday() + 1) % 7))
    html = browser.client.get("/map").get_data(as_text=True)
    assert "Today's classes" in html and 'data-place="r3815072"' in html
    assert "Somewhere 9: building not found" in html and "Tomorrow" not in html


def test_todays_classes_are_private(browser, make_browser):
    browser.api("POST", "/api/classes", dict(CLASS, name="Secret class", weekday=date.today().weekday()))
    other = make_browser()
    other.signup("b@example.com")
    assert "Secret class" not in other.client.get("/map").get_data(as_text=True)


def test_home_links_todays_class_to_map(browser):
    browser.api("POST", "/api/classes", dict(CLASS, weekday=date.today().weekday()))
    html = browser.client.get("/").get_data(as_text=True)
    assert "/map?place=r3815072" in html


def test_menu_has_map(make_browser):
    assert 'href="/map"' in make_browser().client.get("/").get_data(as_text=True)
