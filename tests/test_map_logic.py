"""Test logic bản đồ trên dữ liệu OpenStreetMap thật (data/nthu_osm.csv)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import map_logic as m  # noqa: E402


@pytest.fixture(scope="module")
def data():
    return m.load_places()


@pytest.fixture(scope="module")
def places(data):
    return data[0]


def by_name(places, name):
    found = [p for p in places if p["name"] == name]
    assert len(found) == 1, f"{name}: {len(found)} matches"
    return found[0]


def row(**kw):
    base = {"type": "way", "name": "x", "amenity": "", "building": "", "tourism": "", "leisure": "",
            "shop": "", "highway": "", "natural": ""}
    return dict(base, **kw)


# ---------- đọc dữ liệu ----------

def test_loads_places_and_two_hsinchu_campuses(data):
    places, campuses = data
    assert 150 < len(places) < 300
    assert [c["label"] for c in campuses] == ["Main campus", "Nanda campus"]   # cơ sở chính đứng đầu


def test_ids_unique_and_coordinates_near_campus(places):
    assert len({p["id"] for p in places}) == len(places)
    for p in places:
        assert m.distance_m(*m.MAIN_CAMPUS, p["lat"], p["lon"]) <= m.MAX_DISTANCE_M
        assert p["id"][0] in "nwr" and p["id"][1:].isdigit()
        assert p["osm_url"].startswith("https://www.openstreetmap.org/")


def test_far_away_and_noise_rows_are_dropped(places):
    names = {p["name"] for p in places}
    assert "清華大學高雄校區" not in names and "進修中心一館" not in names          # Cao Hùng, xa 100 km
    assert not any("→" in n for n in names)                                          # tuyến xe buýt
    assert not names & {"光明里", "綠水里", "仙宮里", "AED", "901", "男廁所", "女廁所", "榕樹"}
    assert not any("預定地" in n for n in names)                                     # đất dự kiến xây
    assert "國立清華大學" not in names                                               # cả khuôn viên -> campuses


def test_duplicates_are_merged(places):
    names = [p["name"] for p in places]
    for name in ["清華大學南門", "綜二館站", "台積館站", "CSC Lab", "小吃部", "梅園", "大草坪"]:
        assert names.count(name) == 1, name
    # "楓林小徑(女宿)站" và "楓林小徑（女宿）站" (ngoặc toàn khổ) là một trạm
    assert sum(1 for n in names if m.normalize(n) == m.normalize("楓林小徑(女宿)站")) == 1
    # cùng tên nhưng ở hai cơ sở khác nhau thì giữ cả hai
    assert names.count("7-Eleven") == 2


def test_merge_keeps_row_with_english_name(places):
    assert by_name(places, "大草坪")["name_en"] == "University Green"
    assert by_name(places, "梅園")["name_en"] == "Plum Gardens"


# ---------- phân loại ----------

@pytest.mark.parametrize("name,category", [
    ("台達館", "academic"), ("第二綜合大樓", "academic"), ("總圖書館", "academic"),
    ("碩齋", "dorm"), ("鳴鳳樓", "dorm"), ("清齋10樓", "dorm"),
    ("水木生活中心", "food"), ("麥當勞", "food"), ("風雲樓", "food"),
    ("清大水木百貨", "services"), ("清華大學郵局", "services"),
    ("醫輔中心", "services"), ("綜二館站", "transport"), ("立體機車停車場 (機車塔)", "transport"),
    ("游泳池", "sports"), ("校友體育館", "sports"), ("室內網球場", "sports"),
    ("成功湖", "landmark"), ("梅貽琦之墓", "landmark"), ("八角亭", "landmark"), ("球場花園", "landmark"),
    ("國立清華大學北大門", "gate"), ("清華大學南門", "gate"),
])
def test_known_places_classified(places, name, category):
    assert by_name(places, name)["category"] == category


def test_classify_rules_order():
    assert m.classify(row(name="生醫工程與環境科學館", building="university")) == "academic"   # "醫" trong tên khoa
    assert m.classify(row(name="奕園停車場站", highway="bus_stop")) == "transport"              # trạm xe thắng "園"
    assert m.classify(row(name="警衛亭")) == "other"                                           # 亭 không có thẻ shelter
    assert m.classify(row(name="女廁所", amenity="toilets")) is None
    assert m.classify(row(name="光明里", type="relation")) is None
    assert m.classify(row(name="Some Lab")) == "academic"


def test_public_fields(places):
    delta = by_name(places, "台達館")
    assert delta["levels"] == 9 and delta["category_label"] == "Buildings"
    assert delta["color"] == m.CATEGORY_COLORS["academic"]
    assert by_name(places, "樹德樓")["levels"] is None          # building:levels = 0 -> không hiện


# ---------- khoảng cách ----------

def test_distance_and_walk_time():
    assert m.distance_m(24.0, 121.0, 24.0, 121.0) == 0
    assert abs(m.distance_m(24.0, 121.0, 25.0, 121.0) - 111195) < 50           # 1 độ vĩ ~ 111.2 km
    assert m.distance_m(24.79, 120.99, 24.80, 121.0) == m.distance_m(24.80, 121.0, 24.79, 120.99)
    assert m.walk_minutes(0) == 1 and m.walk_minutes(80) == 1 and m.walk_minutes(81) == 2 and m.walk_minutes(800) == 10


def test_nearest_excludes_self_and_sorts(places):
    delta = by_name(places, "台達館")
    rows = m.nearest(delta, places, "food", limit=3)
    assert len(rows) == 3 and [r["meters"] for r in rows] == sorted(r["meters"] for r in rows)
    assert all(r["place"]["category"] == "food" for r in rows)
    lake = by_name(places, "成功湖")
    assert all(r["place"]["id"] != lake["id"] for r in m.nearest(lake, places, "landmark", limit=50))


def test_details_has_nearby_and_directions(places):
    d = m.details(by_name(places, "台達館"), places)
    assert set(d["nearby"]) == {"food", "transport", "services"}
    assert d["nearby"]["transport"]["name"] == "清華大學(台達館)"          # trạm YouBike ngay cạnh
    assert d["directions_url"].startswith("https://www.google.com/maps/dir/?api=1")
    assert "24.7957488,120.9919946" in d["directions_url"]


# ---------- tên gọi khác và phòng học ----------

def test_aliases_rules(places):
    assert {"台達館", "台達", "deltabuilding", "delta"} <= m.aliases(by_name(places, "台達館"))
    assert {"綜三", "綜合三館", "generalbuildingiii", "general3"} <= m.aliases(by_name(places, "第三綜合大樓"))
    assert {"工一", "工程一"} <= m.aliases(by_name(places, "工程一館"))
    assert {"人社"} <= m.aliases(by_name(places, "人文社會館"))
    assert {"材料科技館", "工程四館", "工四"} <= m.aliases(by_name(places, "材料科技館: 工程四館"))
    assert {"綜一", "行政大樓"} <= m.aliases(by_name(places, "第一綜合大樓: 行政大樓"))


@pytest.mark.parametrize("room,expected", [
    ("Delta 205", "台達館"), ("台達館 105", "台達館"), ("台達105", "台達館"), ("DELTA-310", "台達館"),
    ("綜三 B101", "第三綜合大樓"), ("綜合三館 201", "第三綜合大樓"), ("General Building II 101", "第二綜合大樓"),
    ("General Building III 101", "第三綜合大樓"), ("工一 101", "工程一館"), ("工四 210", "材料科技館: 工程四館"),
    ("化工館 201", "化工館"), ("化學館 201", "化學館"), ("人社 C310", "人文社會館"), ("Physics 101", "物理館"),
    ("台積館 1F", "台積館"), ("ＤＥＬＴＡ２０５", "台達館"),
])
def test_match_room(places, room, expected):
    assert m.match_room(room, places)["name"] == expected


@pytest.mark.parametrize("room", ["", "   ", "R101", "Somewhere 9", "Online", "B101"])
def test_match_room_none(places, room):
    assert m.match_room(room, places) is None


def test_match_room_name_must_come_first(places):
    # tên tòa nhà phải ở ĐẦU: "Biophysics" có chứa "physics" nhưng không phải 物理館
    assert m.match_room("Biophysics 101", places) is None
    assert m.match_room("Physics 101", places)["name"] == "物理館"


def test_match_room_only_buildings(places):
    # "小吃部 2F" là chỗ ăn, không phải tòa học -> không ghép làm phòng học
    assert m.match_room("小吃部 2F", places) is None


def test_class_stops(places):
    stops = m.class_stops([{"name": "A", "room": "Delta 205"}, {"name": "B", "room": ""}, {"name": "C"}], places)
    assert stops[0]["place"]["name"] == "台達館" and stops[1]["place"] is None and stops[2]["place"] is None
    assert stops[0]["item"]["name"] == "A"


# ---------- tìm kiếm ----------

def test_search_exact_beats_contains(places):
    results = m.search("台達館", places)
    assert results[0]["name"] == "台達館"
    assert "清華大學(台達館)" in [p["name"] for p in results]            # trạm xe có chứa chữ, xếp sau


def test_search_english_case_and_fullwidth(places):
    assert m.search("delta", places)[0]["name"] == "台達館"
    assert m.search("DELTA", places)[0]["name"] == "台達館"
    assert m.search("ｄｅｌｔａ", places)[0]["name"] == "台達館"
    assert m.search("main library", places)[0]["name"] == "總圖書館"


def test_search_abbreviation_and_room(places):
    assert m.search("綜三", places)[0]["name"] == "第三綜合大樓"
    assert m.search("Delta 205", places)[0]["name"] == "台達館"          # tên phòng cũng tìm được
    assert m.search("工一 101", places)[0]["name"] == "工程一館"


def test_search_empty_and_no_match(places):
    assert m.search("", places) == [] and m.search("  ", places) == [] and m.search("!!!", places) == []
    assert m.search("zzzz-nothing", places) == []


def test_search_limit_and_order(places):
    results = m.search("齋", places, limit=5)
    assert len(results) == 5
    assert results[0]["name"] == "齋丘"                           # bắt đầu bằng "齋" (80 điểm) đứng trước
    assert all(p["category"] == "dorm" for p in results[1:])      # các ký túc xá chỉ "có chứa" (60 điểm)


# ---------- dữ liệu cho trang ----------

def test_category_summary(places):
    summary = m.category_summary(places)
    codes = [c["code"] for c in summary]
    assert codes[0] == "academic" and "other" in codes
    assert sum(c["count"] for c in summary) == len(places)
    assert {c["code"]: c["on"] for c in summary}["other"] is False


def test_geojson(places):
    gj = m.to_geojson(places)
    assert gj["type"] == "FeatureCollection" and len(gj["features"]) == len(places)
    f = next(f for f in gj["features"] if f["properties"]["name"] == "台達館")
    assert f["geometry"]["coordinates"] == [120.9919946, 24.7957488]      # kinh độ trước, vĩ độ sau


def test_load_from_custom_file(tmp_path):
    csv_text = ("@type|@id|name|name:en|building|amenity|shop|leisure|tourism|highway|natural|building:levels|@lat|@lon\n"
                "way|1|測試館|Test Building|university|||||||3|24.7950|120.9920\n"
                "node|2|測試館||||||||||24.7951|120.9921\n"
                "node|4|壞行|||||||||||\n"
                "node|3|遠方站|||||||bus_stop|||25.5|121.5\n")
    path = tmp_path / "osm.csv"
    path.write_text(csv_text, encoding="utf-8")
    places, campuses = m.load_places(path)
    # dòng trùng tên gộp lại, dòng xa 100 km và dòng thiếu tọa độ bị bỏ
    assert [p["name"] for p in places] == ["測試館"] and places[0]["levels"] == 3 and campuses == []


# ---------- script tải dữ liệu ----------

def test_fetch_script_validation_and_query():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools"))
    import fetch_map_data as f
    real = open(m.DATA_FILE, encoding="utf-8").read()
    assert f.looks_valid(real)
    assert not f.looks_valid("") and not f.looks_valid(f.HEADER) and not f.looks_valid("<html>error</html>\nx")
    assert 'name~"清華"' in f.QUERY and "out center" in f.QUERY
