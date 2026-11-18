"""Test đường đi giữa hai tiết học và trạng thái Now / Next trên trang chủ."""
import app as app_module
import map_logic
from schedule_logic import break_minutes, class_states

PLACES, _ = map_logic.load_places()


def place(name):
    return next(p for p in PLACES if p["name"] == name)


def cls(name, start, end, room="", weekday=0, id=1):
    return {"id": id, "name": name, "weekday": weekday, "start": start, "end": end, "room": room}


def test_room_codes_from_course_system():
    for room, building in [("DELTA台達217", "台達館"), ("PHYS物 019", "物理館"), ("GEN IV綜四224", "第四綜合大樓"),
                           ("GEN II綜二110", "第二綜合大樓"), ("EDU教 310", "教育館"), ("Delta 205", "台達館")]:
        assert map_logic.match_room(room, PLACES)["name"] == building
    assert map_logic.match_room("XYZ 101", PLACES) is None and map_logic.match_room("", PLACES) is None


def test_walk_leg():
    delta, edu = place("台達館"), place("教育館")
    same = map_logic.walk_leg(delta, delta, 10)
    assert same["same"] and same["minutes"] == 0 and not same["late"]
    leg = map_logic.walk_leg(delta, edu, 10)
    straight = map_logic.distance_m(delta["lat"], delta["lon"], edu["lat"], edu["lon"])
    assert leg["meters"] == round(straight * map_logic.DETOUR) and leg["minutes"] == map_logic.walk_minutes(leg["meters"])
    assert leg["late"] == (leg["minutes"] > 10)
    assert map_logic.walk_leg(delta, edu, 0)["late"]                    # không có giờ nghỉ -> chắc chắn muộn
    assert map_logic.walk_leg(None, edu, 10) is None
    assert not leg["long"] and map_logic.walk_leg(delta, edu, 80)["long"]


def test_day_route_adds_leg_to_next_class():
    classes = [cls("A", "08:00", "09:50", "DELTA台達217"), cls("B", "10:10", "12:00", "EDU教 310"),
               cls("C", "11:00", "12:30", "PHYS物 019"), cls("D", "13:20", "15:10", "XYZ 1")]
    route = map_logic.day_route(map_logic.class_stops(classes, PLACES), break_minutes)
    assert route[0]["leg"]["gap"] == 20 and route[0]["leg"]["place"]["name"] == "教育館"
    assert route[1]["leg"] is None                                      # B và C trùng giờ
    assert route[2]["leg"] is None                                      # D không có trên bản đồ
    assert route[3]["leg"] is None                                      # môn cuối cùng
    assert "leg" not in classes[0]                                      # không sửa dữ liệu gốc


def test_class_states():
    classes = [cls("A", "08:00", "09:50"), cls("B", "10:10", "12:00"), cls("C", "13:20", "15:10")]
    assert [s["state"] for s in class_states(classes, 7 * 60)] == ["next", "later", "later"]
    assert [s["state"] for s in class_states(classes, 9 * 60)] == ["now", "later", "later"]
    states = class_states(classes, 10 * 60)                             # giờ nghỉ 09:50 - 10:10
    assert [s["state"] for s in states] == ["done", "next", "later"] and states[1]["starts_in"] == 10
    assert [s["state"] for s in class_states(classes, 16 * 60)] == ["done", "done", "done"]


def test_home_shows_walk_between_classes(browser, monkeypatch):
    weekday = app_module.today_tw().weekday()
    browser.api("POST", "/api/classes", {"name": "Programming", "weekday": weekday, "start": "08:00",
                                         "end": "09:50", "room": "DELTA台達217"})
    browser.api("POST", "/api/classes", {"name": "Poisons", "weekday": weekday, "start": "10:00",
                                         "end": "11:00", "room": "PHYS物 019"})
    html = browser.client.get("/").get_data(as_text=True)
    assert "min walk to 物理館" in html and "10 min break" in html
    browser.api("POST", "/api/classes", {"name": "Lab", "weekday": weekday, "start": "11:00",
                                         "end": "12:00", "room": "EDU教 310"})
    html = browser.client.get("/").get_data(as_text=True)
    assert "but only 0 min break" in html and 'class="leg late"' in html


def test_home_long_break_shows_only_walk(browser):
    weekday = app_module.today_tw().weekday()
    browser.api("POST", "/api/classes", {"name": "A", "weekday": weekday, "start": "08:00", "end": "09:00", "room": "DELTA台達217"})
    browser.api("POST", "/api/classes", {"name": "B", "weekday": weekday, "start": "13:20", "end": "14:10", "room": "PHYS物 019"})
    html = browser.client.get("/").get_data(as_text=True)
    assert "min walk to 物理館" in html and "min break" not in html
