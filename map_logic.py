"""Logic thuần Python cho bản đồ NTHU (không có Flask, không có database).

Dữ liệu lấy từ OpenStreetMap (data/nthu_osm.csv, tải bằng tools/fetch_map_data.py).
Các hàm chính:
    load_places()      -> đọc file CSV, bỏ dòng thừa, gộp dòng trùng, phân loại từng địa điểm
    classify()         -> đoán nhóm (tòa học, ký túc xá, ăn uống...) từ thẻ OSM và tên
    search()           -> tìm theo tên tiếng Trung / tiếng Anh / tên viết tắt / tên phòng
    match_room()       -> "Delta 205", "台達105", "綜三 B101" -> tòa nhà tương ứng
    distance_m()       -> khoảng cách đường chim bay giữa hai điểm (công thức haversine)
    nearest()          -> địa điểm gần nhất thuộc một nhóm (ví dụ chỗ ăn gần nhất)
    to_geojson()       -> định dạng mà thư viện bản đồ MapLibre đọc được
JavaScript chỉ vẽ bản đồ; mọi quyết định (lọc, phân loại, tìm, tính khoảng cách) nằm ở đây.
"""
import csv
import math
import re
import unicodedata
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "nthu_osm.csv"
MAIN_CAMPUS = (24.7916835, 120.9928891)   # tâm cơ sở chính (relation 3605515 trong OSM)
MAX_DISTANCE_M = 4000                     # bỏ địa điểm xa hơn 4 km (ví dụ cơ sở Cao Hùng)
DUPLICATE_M = 150                         # hai dòng cùng tên cách nhau dưới 150 m là một địa điểm
WALK_M_PER_MIN = 80                       # đi bộ khoảng 80 m mỗi phút (4.8 km/h)
DETOUR = 1.3                              # đường đi thật dài hơn đường chim bay khoảng 30% (vòng qua nhà, cầu thang)
LONG_BREAK = 60                           # nghỉ từ 60 phút trở lên: không cần nhắc số phút nghỉ
EARTH_RADIUS_M = 6371000

# Nhóm địa điểm: (mã, tên hiển thị, màu chấm trên bản đồ)
CATEGORIES = [
    ("academic", "Buildings", "#5b3cc4"),
    ("dorm", "Dorms & lodging", "#c2255c"),
    ("food", "Food & drink", "#d9480f"),
    ("services", "Shops & services", "#0b7285"),
    ("transport", "Bus, bikes & parking", "#1864ab"),
    ("sports", "Sports", "#2b8a3e"),
    ("landmark", "Lakes, gardens & landmarks", "#8a6100"),
    ("gate", "Gates", "#343a40"),
    ("other", "Other", "#868e96"),
]
CATEGORY_LABELS = {code: label for code, label, _ in CATEGORIES}
CATEGORY_COLORS = {code: color for code, _, color in CATEGORIES}
HIDDEN_BY_DEFAULT = {"other"}             # nhóm "Other" không hiện sẵn cho đỡ rối

FOOD = {"restaurant", "cafe", "fast_food", "food_court", "bar", "pub"}
SERVICES = {"atm", "post_office", "bank", "clinic", "doctors", "library", "pharmacy"}
TRANSPORT = {"bicycle_rental", "parking", "motorcycle_parking", "parking_entrance", "bus_station"}
SPORTS = {"pitch", "stadium", "sports_centre", "swimming_pool", "track", "fitness_centre"}
LANDMARK_TOURISM = {"artwork", "viewpoint", "attraction"}
LANDMARK_AMENITY = {"shelter", "place_of_worship", "clock"}
LANDMARK_LEISURE = {"garden", "park"}
SKIP_AMENITY = {"toilets", "parcel_locker"}
SKIP_TOURISM = {"information"}
SKIP_NAME = re.compile(r"→|往程|預定地|^\d+$|^AED$")   # tuyến xe buýt, đất dự kiến xây, tên chỉ có số


# ---------- đọc và làm sạch dữ liệu ----------

def normalize(text):
    """Chuẩn hóa để so sánh: chữ toàn khổ -> bình thường, chữ thường, bỏ khoảng trắng và dấu câu."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return "".join(ch for ch in text if ch.isalnum())


def distance_m(lat1, lon1, lat2, lon2):
    """Khoảng cách đường chim bay (mét) giữa hai tọa độ, công thức haversine."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def walk_minutes(meters):
    """Số phút đi bộ ước tính (làm tròn lên, ít nhất 1 phút)."""
    return max(1, math.ceil(meters / WALK_M_PER_MIN))


LANDMARK_NAME = re.compile(r"草坪|草原|草地|草皮|園|湖|池|島|墓|碑|步道|廣場|頂|塔")
BUILDING_NAME = re.compile(r"館|大樓|中心|實驗室|研究所|Lab", re.I)
SPORTS_NAME = re.compile(r"體育|球場|游泳|泳池")
SERVICES_NAME = re.compile(r"醫輔|診所|衛保")


def classify(row):
    """Đoán nhóm của một dòng OSM. Trả về mã nhóm, hoặc None nếu nên bỏ dòng này.

    Xét lần lượt, quy tắc trước thắng: thẻ OSM rõ ràng (trạm xe, quán ăn, cửa hàng...) trước,
    rồi đến tên (齋 = ký túc xá, 門 = cổng, 館 = tòa nhà...).
    """
    name, amenity, building = row["name"], row["amenity"], row["building"]
    leisure, tourism = row["leisure"], row["tourism"]
    if SKIP_NAME.search(name) or amenity in SKIP_AMENITY or tourism in SKIP_TOURISM or row["natural"] == "tree":
        return None
    if row["type"] == "relation" and name.endswith("里") and not building:
        return None                                  # ranh giới phường (里), không phải địa điểm
    if row["highway"] == "bus_stop" or amenity in TRANSPORT:
        return "transport"
    if amenity in FOOD:
        return "food"
    if row["shop"] or amenity in SERVICES or SERVICES_NAME.search(name):
        return "services"
    if building == "dormitory" or tourism in {"guest_house", "hostel"} or "宿舍" in name or name.endswith("齋"):
        return "dorm"
    if name.endswith("門"):
        return "gate"
    if leisure in SPORTS:
        return "sports"
    if tourism in LANDMARK_TOURISM or amenity in LANDMARK_AMENITY or leisure in LANDMARK_LEISURE \
            or row["natural"] == "water":
        return "landmark"
    if SPORTS_NAME.search(name):
        return "sports"
    if building or BUILDING_NAME.search(name):
        return "academic"
    if LANDMARK_NAME.search(name):
        return "landmark"
    return "other"


def _is_campus(row):
    """Dòng này là cả một khuôn viên trường (amenity=university, không phải một tòa nhà)."""
    return row["amenity"] == "university" and not row["building"]


def _read_rows(path):
    """Đọc file CSV của Overpass (phân cách bằng |) thành danh sách dict với tên cột dễ dùng."""
    with open(path, encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f, delimiter="|"):
            try:
                lat, lon = float(raw["@lat"]), float(raw["@lon"])
            except (TypeError, ValueError):
                continue                                  # dòng hỏng (thiếu tọa độ): bỏ qua
            yield {
                "type": raw["@type"], "osm_id": raw["@id"], "name": raw["name"].strip(),
                "name_en": raw["name:en"].replace("_", " ").strip(),
                "building": raw["building"], "amenity": raw["amenity"], "shop": raw["shop"],
                "leisure": raw["leisure"], "tourism": raw["tourism"], "highway": raw["highway"],
                "natural": raw["natural"], "levels": raw["building:levels"],
                "lat": lat, "lon": lon,
            }


def _better(a, b):
    """Trong hai dòng trùng nhau, giữ dòng có tên tiếng Anh, rồi ưu tiên vùng (way/relation) hơn điểm (node)."""
    def score(p):
        return (bool(p["name_en"]), p["type"] != "node")
    return a if score(a) >= score(b) else b


def _campus_label(row):
    """"Main campus" cho cơ sở chính; cơ sở khác lấy phần cuối tên tiếng Anh ("Nanda Campus")."""
    if distance_m(*MAIN_CAMPUS, row["lat"], row["lon"]) < 100:
        return "Main campus"
    label = row["name_en"].replace("National Tsing Hua University", "").strip()
    return label.replace("Campus", "campus") or row["name"]


def load_places(path=DATA_FILE):
    """Đọc dữ liệu và trả về (places, campuses).

    places: list địa điểm đã phân loại, đã gộp trùng, chỉ trong bán kính MAX_DISTANCE_M quanh cơ sở chính.
    campuses: các khuôn viên (cơ sở chính, Nanda) để có nút bay tới.
    """
    rows = list(_read_rows(path))
    near = [r for r in rows if distance_m(*MAIN_CAMPUS, r["lat"], r["lon"]) <= MAX_DISTANCE_M]
    campuses = sorted(({"id": f"{r['type'][0]}{r['osm_id']}", "name": r["name"], "name_en": r["name_en"],
                        "lat": r["lat"], "lon": r["lon"], "label": _campus_label(r)}
                       for r in near if _is_campus(r)),
                      key=lambda c: distance_m(*MAIN_CAMPUS, c["lat"], c["lon"]))

    kept = []
    for row in near:
        if _is_campus(row):
            continue
        category = classify(row)
        if category is None:
            continue
        key = normalize(row["name"])
        twin = next((i for i, p in enumerate(kept) if normalize(p["name"]) == key
                     and distance_m(p["lat"], p["lon"], row["lat"], row["lon"]) < DUPLICATE_M), None)
        place = dict(row, category=category)
        if twin is None:
            kept.append(place)
        else:
            kept[twin] = _better(kept[twin], place)
    return [_public(p) for p in kept], campuses


def _public(p):
    """Chỉ giữ các trường cần cho trang web; id dạng "w180522501" (w = way, n = node, r = relation)."""
    return {
        "id": f"{p['type'][0]}{p['osm_id']}", "name": p["name"], "name_en": p["name_en"],
        "category": p["category"], "category_label": CATEGORY_LABELS[p["category"]],
        "color": CATEGORY_COLORS[p["category"]], "lat": round(p["lat"], 7), "lon": round(p["lon"], 7),
        "levels": int(p["levels"]) if p["levels"].isdigit() and int(p["levels"]) > 0 else None,
        "osm_url": f"https://www.openstreetmap.org/{p['type']}/{p['osm_id']}",
    }


# ---------- tên gọi khác (để tìm kiếm và nối với tên phòng học) ----------

ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5"}
ZH_DIGITS = "一二三四五六七八九"


def aliases(place):
    """Các cách gọi khác của một địa điểm (đã chuẩn hóa), ví dụ 台達館 -> 台達; 第三綜合大樓 -> 綜三.

    Quy tắc:
      - tên đầy đủ (Trung và Anh), và từng phần nếu tên có dấu ":" ("材料科技館: 工程四館")
      - bỏ đuôi 館 / 大樓 (nếu còn ít nhất 2 chữ): 台達館 -> 台達
      - 第X綜合大樓 -> 綜X, 綜合X館;  工程X館 -> 工X;  生命科學X館 -> 生科X;  人文社會館 -> 人社
      - tiếng Anh: bỏ chữ "building", số La Mã -> số thường ("General Building II" -> "general 2")
    """
    names = [place["name"], place["name_en"]]
    names += [part for n in names for part in re.split(r"[:：]", n) if ":" in n or "：" in n]
    result = set()
    for name in filter(None, (n.strip() for n in names)):
        result.add(normalize(name))
        short = re.sub(r"(館|大樓)$", "", name)
        if len(short) >= 2:
            result.add(normalize(short))
        if m := re.fullmatch(rf"第?([{ZH_DIGITS}])綜合大樓", name):
            result |= {normalize("綜" + m[1]), normalize(f"綜合{m[1]}館")}
        if m := re.fullmatch(rf"工程([{ZH_DIGITS}])館", name):
            result.add(normalize("工" + m[1]))
        if m := re.fullmatch(rf"生命科學([{ZH_DIGITS}])館", name):
            result.add(normalize("生科" + m[1]))
        if name == "人文社會館":
            result.add(normalize("人社"))
        words = name.casefold().split()
        if "building" in words:
            plain = [ROMAN.get(w, w) for w in words if w != "building"]
            result |= {normalize(" ".join(plain)), normalize(" ".join(w for w in words if w != "building"))}
    result.discard("")
    return result


# Mã tòa nhà trong 校務資訊系統 (phòng ghi kiểu "PHYS物 019", "GEN IV綜四224", "EDU教 310") -> tên trên bản đồ.
# Chỉ ghi những mã chắc chắn; mã khác vẫn có thể khớp nhờ phần chữ Hán phía sau ("綜四224" -> 綜四).
ROOM_CODES = {
    "delta": "台達館", "phys": "物理館", "edu": "教育館", "chem": "化學館",
    "geni": "第一綜合大樓: 行政大樓", "genii": "第二綜合大樓", "geniii": "第三綜合大樓", "geniv": "第四綜合大樓",
    "tsmc": "台積館", "hss": "人文社會館",
}
ROOM_CODE_RE = re.compile(r"^\s*([A-Za-z]+(?:\s+[IVX]+)?)")


def _match_code(room, places):
    """Phòng kiểu 校務資訊系統: thử mã chữ Latinh ở đầu (ROOM_CODES), rồi thử phần còn lại ("綜四224")."""
    m = ROOM_CODE_RE.match(room or "")
    if not m:
        return None
    name = ROOM_CODES.get(normalize(m[1]))
    if name:
        return next((p for p in places if p["name"] == name), None)
    rest = room[m.end():]
    return match_room(rest, places) if normalize(rest) != normalize(room) else None


def match_room(room, places):
    """Tìm tòa nhà của một phòng học, ví dụ "Delta 205" -> 台達館. Không tìm thấy -> None.

    Cách làm: tên phòng (đã chuẩn hóa) phải BẮT ĐẦU bằng một tên gọi của tòa nhà; nếu nhiều tòa khớp
    thì chọn tên gọi dài nhất ("generalbuilding2" thắng "general"). Chỉ xét các tòa học.
    Không khớp thì thử kiểu mã phòng của 校務資訊系統 (_match_code).
    """
    text = normalize(room)
    if not text:
        return None
    best, best_len = None, 0
    for place in places:
        if place["category"] != "academic":
            continue
        for alias in aliases(place):
            if text.startswith(alias) and len(alias) > best_len:
                best, best_len = place, len(alias)
    return best or _match_code(room, places)


# ---------- tìm kiếm ----------

def _score(query, place):
    """Điểm khớp: trùng hẳn 100, đầu tên 80, có chứa 60, không khớp 0."""
    best = 0
    for alias in aliases(place):
        if alias == query:
            return 100
        if alias.startswith(query):
            best = max(best, 80)
        elif query in alias:
            best = max(best, 60)
    return best


def search(query, places, limit=20):
    """Tìm địa điểm theo tên (Trung/Anh/viết tắt) hoặc tên phòng. Điểm cao trước, rồi theo tên."""
    q = normalize(query)
    if not q:
        return []
    order = [code for code, _, _ in CATEGORIES]
    scored = [(_score(q, p), p) for p in places]
    room = match_room(query, places)
    if room is not None:
        scored = [(max(s, 90) if p is room else s, p) for s, p in scored]
    hits = [(s, p) for s, p in scored if s > 0]
    hits.sort(key=lambda sp: (-sp[0], order.index(sp[1]["category"]), sp[1]["name"]))
    return [p for _, p in hits[:limit]]


# ---------- khoảng cách ----------

def nearest(place, places, category, limit=1):
    """Các địa điểm gần `place` nhất thuộc `category` (không tính chính nó): [{place, meters, minutes}]."""
    rows = []
    for other in places:
        if other["category"] != category or other["id"] == place["id"]:
            continue
        meters = distance_m(place["lat"], place["lon"], other["lat"], other["lon"])
        rows.append({"place": other, "meters": round(meters), "minutes": walk_minutes(meters)})
    rows.sort(key=lambda r: r["meters"])
    return rows[:limit]


# ---------- vị trí của người dùng ("My location") ----------

NEAR_ME_CATEGORIES = ("academic", "food", "transport", "services")   # mỗi nhóm lấy chỗ gần nhất
ON_CAMPUS_M = 1500            # cách tâm cơ sở chính dưới 1,5 km: coi là đang ở trong / sát trường


def valid_position(lat, lon):
    """Tọa độ hợp lệ (số, trong khoảng của Trái Đất) -> (lat, lon) kiểu float; sai -> None."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or lat != lat or lon != lon:   # lat != lat: NaN
        return None
    return lat, lon


def near_me(lat, lon, places):
    """Chỗ gần vị trí (lat, lon) nhất trong từng nhóm NEAR_ME_CATEGORIES, gần nhất trước.

    Trả về {"on_campus", "campus_m", "items": [{place, category, meters, minutes}]}.
    Ở xa trường (> ON_CAMPUS_M) thì items rỗng: chỉ báo khoảng cách tới trường.
    """
    campus_m = round(distance_m(lat, lon, *MAIN_CAMPUS))
    if campus_m > ON_CAMPUS_M:
        return {"on_campus": False, "campus_m": campus_m, "items": []}
    items = []
    for category in NEAR_ME_CATEGORIES:
        best = min((p for p in places if p["category"] == category),
                   key=lambda p: distance_m(lat, lon, p["lat"], p["lon"]), default=None)
        if best is not None:
            meters = round(distance_m(lat, lon, best["lat"], best["lon"]) * DETOUR)
            items.append({"place": best, "category": category, "meters": meters, "minutes": walk_minutes(meters)})
    items.sort(key=lambda row: row["meters"])
    return {"on_campus": True, "campus_m": campus_m, "items": items}


def details(place, places):
    """Thông tin cho khung chi tiết: nhóm, chỗ ăn / trạm xe / cửa hàng gần nhất, link chỉ đường."""
    near = {}
    for category in ("food", "transport", "services"):
        found = nearest(place, places, category)
        if found:
            near[category] = {"name": found[0]["place"]["name"], "id": found[0]["place"]["id"],
                              "meters": found[0]["meters"], "minutes": found[0]["minutes"],
                              "label": CATEGORY_LABELS[category]}
    return dict(
        place,
        nearby=near,
        directions_url=("https://www.google.com/maps/dir/?api=1&travelmode=walking"
                        f"&destination={place['lat']},{place['lon']}"),
    )


# ---------- dữ liệu cho trang web ----------

def category_summary(places):
    """Các nhóm có ít nhất một địa điểm, kèm số lượng, màu và có hiện sẵn hay không."""
    counts = {}
    for p in places:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    return [{"code": code, "label": label, "color": color, "count": counts[code],
             "on": code not in HIDDEN_BY_DEFAULT}
            for code, label, color in CATEGORIES if counts.get(code)]


def to_geojson(places):
    """Chuyển danh sách địa điểm sang GeoJSON (kinh độ trước, vĩ độ sau theo chuẩn GeoJSON)."""
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
            "properties": {"id": p["id"], "name": p["name"], "name_en": p["name_en"],
                           "category": p["category"], "color": p["color"]},
        } for p in places],
    }


def class_stops(classes, places):
    """Ghép mỗi môn học với tòa nhà theo tên phòng. Trả về [{item, place}] (place có thể là None)."""
    return [{"item": c, "place": match_room(c.get("room", ""), places)} for c in classes]


# ---------- đường đi giữa hai tiết học ----------

def walk_leg(here, there, gap):
    """Đường đi từ tòa nhà `here` sang tòa nhà `there`, khi có `gap` phút nghỉ giữa hai môn.

    Trả về {place, same, meters, minutes, gap, late, long} hoặc None nếu không biết một trong hai tòa nhà.
    late = True khi đi bộ lâu hơn thời gian nghỉ (sẽ đến muộn nếu không đi ngay).
    long = True khi nghỉ từ LONG_BREAK phút trở lên (chỉ cần nói số phút đi bộ).
    """
    if here is None or there is None:
        return None
    leg = {"place": there, "gap": gap, "long": gap >= LONG_BREAK}
    if here["id"] == there["id"]:
        return dict(leg, same=True, meters=0, minutes=0, late=False)
    meters = round(distance_m(here["lat"], here["lon"], there["lat"], there["lon"]) * DETOUR)
    minutes = walk_minutes(meters)
    return dict(leg, same=False, meters=meters, minutes=minutes, late=minutes > gap)


def day_route(stops, gap_minutes):
    """Thêm "leg" (đường đi tới môn KẾ TIẾP) vào bản sao của mỗi stop (kết quả của class_stops).

    gap_minutes(a, b): số phút nghỉ giữa môn a và môn b (app.py truyền hàm của schedule_logic vào,
    để file này không phải biết cách tính giờ). Hai môn trùng giờ (gap < 0) thì không có leg.
    """
    route = []
    for i, stop in enumerate(stops):
        leg = None
        if i + 1 < len(stops):
            nxt = stops[i + 1]
            gap = gap_minutes(stop["item"], nxt["item"])
            if gap >= 0:
                leg = walk_leg(stop["place"], nxt["place"], gap)
        route.append(dict(stop, leg=leg))
    return route
