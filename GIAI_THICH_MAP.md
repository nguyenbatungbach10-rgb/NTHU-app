# Giải thích: Bản đồ NTHU (2D và 3D)

Trang `/map`. Ai cũng xem được, không cần đăng nhập. Nếu đã đăng nhập thì trang còn hiện các môn học hôm nay
và tòa nhà của từng môn.

## 1. Dữ liệu lấy từ đâu
- **Danh sách địa điểm** (tên, tọa độ, loại): lấy từ **OpenStreetMap** (bản đồ mở do cộng đồng vẽ),
  qua Overpass API, lưu trong `data/nthu_osm.csv`. File có 271 dòng, mỗi dòng một địa điểm có tên,
  nằm trong khuôn viên NTHU (gồm cả cơ sở chính 光復 và cơ sở Nanda 南大).
- **Câu truy vấn** nằm trong `tools/fetch_map_data.py`. Muốn cập nhật dữ liệu thì chạy
  `python tools/fetch_map_data.py` trên máy có mạng, chạy lại `python -m pytest`, rồi commit file CSV.
- **Ảnh nền bản đồ** (đường, nhà, chiều cao nhà cho 3D): trình duyệt tải trực tiếp từ **OpenFreeMap**
  (miễn phí, không cần API key, cho phép dùng thương mại). Thư viện vẽ bản đồ là **MapLibre GL JS 5.24.0**,
  tải từ unpkg.
- **Giấy phép**: dữ liệu OpenStreetMap theo ODbL, bắt buộc ghi "© OpenStreetMap contributors".
  Dòng ghi công này nằm dưới bản đồ, **không được xóa**.

## 2. Python làm gì (map_logic.py)
Đúng quy tắc của dự án: Python quyết định, JavaScript chỉ vẽ.

| Hàm | Việc làm |
| --- | --- |
| `load_places()` | Đọc CSV, bỏ dòng xa hơn 4 km (ví dụ cơ sở Cao Hùng), bỏ dòng thừa, gộp dòng trùng, phân loại |
| `classify(row)` | Đoán nhóm từ thẻ OSM rồi từ tên. Quy tắc đứng trước thắng |
| `aliases(place)` | Các cách gọi khác: 台達館 → 台達, delta; 第三綜合大樓 → 綜三; 工程一館 → 工一 |
| `match_room(room)` | "Delta 205" → 台達館. Tên phòng phải **bắt đầu** bằng một cách gọi; nhiều tòa khớp thì chọn cách gọi dài nhất |
| `search(q)` | Trùng hẳn 100 điểm, khớp phần đầu 80, có chứa 60; tên phòng khớp được 90 |
| `distance_m()` | Khoảng cách đường chim bay bằng công thức haversine (Trái Đất bán kính 6371 km) |
| `nearest()` / `details()` | Chỗ ăn, trạm xe, cửa hàng gần nhất; phút đi bộ = mét / 80, làm tròn lên |
| `to_geojson()` | Định dạng GeoJSON cho thư viện bản đồ (chú ý: **kinh độ trước, vĩ độ sau**) |

### Bỏ dòng nào, gộp dòng nào
- Bỏ: tuyến xe buýt (tên có "→"), ranh giới phường (relation tên kết thúc bằng 里), "預定地" (đất dự kiến xây),
  tên chỉ có số, nhà vệ sinh, tủ nhận hàng, biển thông tin, cây.
- Gộp: hai dòng **cùng tên** (sau khi chuẩn hóa) cách nhau **dưới 150 m**. Ví dụ trạm "綜二館站" có hai điểm
  cho hai chiều xe; "楓林小徑(女宿)站" và "楓林小徑（女宿）站" khác nhau ở dấu ngoặc toàn khổ.
  Giữ dòng có tên tiếng Anh, rồi ưu tiên vùng (way/relation) hơn điểm (node).
- Hai cửa hàng 7-Eleven ở hai cơ sở cách nhau gần 3 km nên vẫn giữ cả hai.

### Chuẩn hóa chữ (`normalize`)
`unicodedata.normalize("NFKC")` đổi chữ toàn khổ (ＤＥＬＴＡ, （ ）) thành chữ thường, rồi `casefold()` và bỏ
khoảng trắng, dấu câu. Nhờ vậy "Delta 205", "DELTA-205" và "ＤＥＬＴＡ２０５" đều tìm ra 台達館.

## 3. API
| Đường dẫn | Trả về |
| --- | --- |
| `GET /api/places` | Mọi địa điểm dạng GeoJSON |
| `GET /api/places/search?q=...` | Danh sách địa điểm khớp, tối đa 20 |
| `GET /api/places/<id>` | Chi tiết + chỗ gần nhất + link chỉ đường Google Maps; id sai trả về 404 `{"error": ...}` |

Dữ liệu chỉ đọc 1 lần rồi giữ trong bộ nhớ (`@lru_cache` trong app.py), vì file không đổi khi web đang chạy.
Các API này chỉ có GET và không đụng dữ liệu người dùng, nên không cần đăng nhập hay CSRF.

## 4. JavaScript làm gì (static/map.js)
- Tạo bản đồ, vẽ chấm màu (lớp `circle`) và tên (lớp `symbol`) từ `/api/places`.
- **2D**: góc nghiêng 0, không cho xoay, chiều cao nhà = 0 (nhà phẳng).
- **3D**: nghiêng 60 độ, xoay -20 độ, trả lại chiều cao nhà gốc của kiểu bản đồ (lớp `fill-extrusion`).
  Nếu kiểu bản đồ không có lớp nhà 3D thì tự thêm một lớp dựa trên `render_height` của OpenMapTiles.
- Bấm chấm hoặc kết quả tìm kiếm thì gọi `/api/places/<id>` rồi mở khung chi tiết. Mọi chữ lấy từ dữ liệu được
  gán bằng `textContent`, nên một cái tên có HTML lạ cũng không chạy được.
- Không tải được thư viện hoặc nền bản đồ (mất mạng, máy không có WebGL): hiện thông báo; tìm kiếm và chi tiết
  vẫn chạy, chi tiết hiện ở cột bên trái.
- Form tìm kiếm vẫn chạy khi tắt JavaScript: trang tải lại với `?q=...` và Python trả kết quả.

## 5. Nối với thời khóa biểu
- Trang `/map` và khối "Classes today" ở trang chủ dùng `class_stops()` để ghép phòng học của từng môn với tòa nhà.
- Trang chủ hiện link "Map" cạnh môn có phòng khớp, dẫn tới `/map?place=<id>`.
- `/map?q=Delta 205` mở sẵn tòa nhà của phòng đó.

## 6. Câu TA có thể hỏi
- **Tọa độ có đúng không?** Lấy từ OpenStreetMap, là tâm của hình chữ nhật bao quanh tòa nhà (Overpass `out center`).
  Không có tọa độ nào tự nghĩ ra.
- **Vì sao không dùng Google Maps?** Google Maps cần API key và thẻ thanh toán. OpenFreeMap và OpenStreetMap miễn phí,
  không cần đăng ký.
- **Khoảng cách tính thế nào?** Haversine: đường chim bay trên mặt cầu. Đường đi bộ thật dài hơn, nên trang ghi
  "straight-line estimates" và có link chỉ đường thật của Google Maps.
- **Sao phải chuẩn hóa NFKC?** Tiếng Trung hay dùng dấu và số toàn khổ; không chuẩn hóa thì "（" và "(" bị coi là khác nhau.
- **Test thế nào?** `tests/test_map_logic.py` chạy trên dữ liệu thật (phân loại, gộp trùng, tìm kiếm, phòng học,
  khoảng cách, GeoJSON). `tests/test_map_api.py` kiểm tra trang, API, 404 và việc người khác không thấy môn học của bạn.

## 7. Hạn chế đã biết
- Một số tòa nhà **chưa có tên trên OpenStreetMap**, ví dụ 資電館, nên không tìm được. Có thể tự thêm tên trên
  openstreetmap.org rồi chạy lại `tools/fetch_map_data.py`.
- Chiều cao nhà trong 3D lấy từ OpenStreetMap; nhà không ghi chiều cao thì dùng giá trị ước đoán.
- Ghép phòng học là cách đoán theo quy tắc: tên tòa nhà phải đứng đầu ("Delta 205" được, "205 Delta" không).
  Một số tên ngắn có thể khớp nhầm (ví dụ "教育學院大樓 101" khớp 教育館).
- Bản đồ cần mạng để tải nền và thư viện; trên máy không có WebGL thì chỉ còn danh sách.
- Thời gian đi bộ là ước tính theo đường chim bay, 80 m mỗi phút.
