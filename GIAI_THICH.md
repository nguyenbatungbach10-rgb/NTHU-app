# Giải thích code (để hiểu và trả lời TA)

## 1. Chạy thử trên Windows (PowerShell, trong thư mục NTHU-app)

```
python -m venv venv
Set-ExecutionPolicy -Scope Process Bypass
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Mở http://127.0.0.1:5000 trên trình duyệt. Dừng server: nhấn Ctrl + C.

- Dòng `Set-ExecutionPolicy` chỉ có hiệu lực trong cửa sổ terminal hiện tại, và phải gõ lại mỗi lần mở terminal mới trước khi bật venv.
- `venv` là "môi trường ảo": thư viện cài vào đây, không lẫn với máy. Dòng `(venv)` đầu terminal nghĩa là đang bật. Thư mục này đã nằm trong `.gitignore`.

## 2. Cấu trúc JSON thật của NTHU Data API

Chạy `python inspect_api.py` để lưu mẫu JSON vào `api_sample.json`. Kết quả của `GET /announcements`:

```
[
  {
    "title": "最新消息",             <- tên mục tin của đơn vị (không dùng)
    "link": "https://...",           <- trang tin của đơn vị
    "language": "zh-tw",             <- "zh-tw" hoặc "en"
    "department": "教務處",           <- tên đơn vị -> ta gọi là "office"
    "articles": [                    <- các thông báo thật nằm ở đây
      {"title": "...", "link": "https://...", "date": "2026-10-30"},
      ...
    ]
  },
  ...
]
```

Điểm quan trọng: **mỗi phần tử ngoài cùng là một đơn vị, không phải một thông báo.** Thông báo thật nằm trong danh sách `articles` lồng bên trong. Vì vậy hàm `normalize()` phải "dàn phẳng": lặp qua từng đơn vị, rồi lặp qua từng bài trong `articles`, tạo ra một danh sách phẳng các thông báo `{title, link, date, office, language}`.

## 3. Một request đi qua code như thế nào

Người dùng mở `/announcements?lang=en&q=pruning&page=1`:

1. Trình duyệt gửi request tới Flask.
2. Flask thấy đường dẫn `/announcements` khớp với `@app.route("/announcements")` trong `app.py`, nên chạy hàm `announcements()`.
3. `request.args.get(...)` đọc các tham số `lang`, `q`, `office`, `page` trên URL.
4. `fetch_announcements()` (trong `nthu_api.py`) gọi `requests.get(...)` để lấy JSON từ NTHU Data API. Kết quả được nhớ 5 phút (cache).
5. `normalize()` dàn phẳng JSON thành list thông báo, xếp mới nhất trước.
6. `filter_announcements()` giữ lại các mục khớp office, từ khóa, ngôn ngữ.
7. `paginate()` cắt lấy 20 mục của trang hiện tại.
8. `render_template("announcements.html", items=...)` đưa dữ liệu vào template.
9. Jinja2 lặp qua `items` bằng `{% for %}`, tạo ra HTML và gửi về trình duyệt.

## 4. Từng file

| File | Làm gì |
|---|---|
| `app.py` | Khai báo các route (URL nào chạy hàm nào). Không chứa logic xử lý dữ liệu, chỉ nối các phần với nhau. |
| `nthu_api.py` | Toàn bộ logic Python: gọi API, dàn phẳng JSON, lọc, phân trang, lấy danh sách office. Không import Flask nên test độc lập được. |
| `templates/base.html` | Khung chung (thanh menu, footer). Các trang khác `{% extends "base.html" %}` và chỉ điền phần `{% block content %}`. |
| `templates/announcements.html` | Form lọc + danh sách + nút chuyển trang. |
| `static/style.css` | Giao diện tím. |
| `inspect_api.py` | Script lưu mẫu JSON thật vào `api_sample.json`. |
| `tests/test_nthu_api.py` | 8 test tự động cho `nthu_api.py`. |
| `tests/api_sample.json` | Mẫu JSON thật dùng cho test. |

## 5. Khái niệm chính

- **Route**: `@app.route("/x")` gắn một URL với một hàm Python.
- **Template inheritance**: `base.html` giữ phần chung; trang con chỉ viết phần riêng. Sửa menu một chỗ, mọi trang đổi theo.
- **Jinja2**: `{{ biến }}` in giá trị, `{% for %}` / `{% if %}` điều khiển. Jinja tự escape HTML nên tiêu đề lạ không chèn được mã độc (XSS).
- **JSON lồng nhau**: dữ liệu có danh sách nằm trong danh sách. `response.json()` đổi nó thành list/dict của Python, rồi dùng vòng lặp lồng nhau để dàn phẳng.
- **Query string**: phần `?office=...&q=...` sau URL. Form `method="get"` tự tạo ra nó khi bấm Filter.
- **Phân trang**: 384 đơn vị cho hàng nghìn bài nên chỉ hiện 20 bài mỗi trang. `items[start:start + 20]` cắt đúng trang; trang số quá lớn hoặc không hợp lệ được ép về khoảng 1..tổng số trang.
- **timeout + try/except**: nếu API chậm hoặc lỗi, web không treo mà hiện dữ liệu mẫu.
- **Cache**: nhớ kết quả API 5 phút trong một dict, đỡ gọi lại mỗi lần mở trang.
- **jsonify**: route `/api/announcements` trả JSON để Calendar hoặc JavaScript dùng sau này.

## 6. Câu hỏi TA có thể hỏi (và gợi ý trả lời)

1. **Dữ liệu announcements đến từ đâu?** Từ NTHU Data API (`/announcements`), định dạng JSON.
2. **JSON đó có cấu trúc thế nào, bạn xử lý ra sao?** Mỗi phần tử là một đơn vị, bên trong có danh sách `articles`. Em lặp hai tầng để dàn phẳng thành danh sách thông báo, mỗi thông báo kèm tên đơn vị và ngôn ngữ.
3. **Vì sao tách `nthu_api.py` khỏi `app.py`?** Để `app.py` chỉ lo route, logic dữ liệu để riêng cho dễ test, dễ đọc, và tính vào phần Python.
4. **Nếu API chết thì sao?** `try/except` bắt lỗi, trang hiện dữ liệu mẫu kèm cảnh báo.
5. **Cache dùng để làm gì?** Không gọi API mỗi lần có người mở trang; nhớ kết quả 5 phút cho nhanh và đỡ tải cho server NTHU.
6. **Lọc hoạt động ra sao?** Form gửi `?office=&q=&lang=` bằng GET; Flask đọc bằng `request.args`; hàm `filter_announcements` duyệt list và giữ mục khớp.
7. **Vì sao dùng GET cho form lọc?** Lọc chỉ đọc dữ liệu, không thay đổi gì; GET cho phép chia sẻ/đánh dấu đường link đã lọc.
8. **Vì sao phải phân trang?** Có hàng nghìn thông báo, hiện hết một lần thì trang nặng và khó đọc. Mỗi trang 20 mục, mới nhất trước.
9. **Jinja2 làm gì?** Biến dữ liệu Python thành HTML bằng vòng lặp và điều kiện.
10. **Bước tiếp theo là gì?** Nút "Save to Calendar" gọi Calendar API của Manh để lưu deadline; hiển thị vài thông báo mới nhất trên dashboard.

## 7. Bài tập để thật sự hiểu code (nên tự làm)

1. Đổi `CACHE_SECONDS` thành 10, mở lại trang và xem hành vi thay đổi thế nào.
2. Đổi `PER_PAGE` thành 5 và xem số trang thay đổi.
3. Thêm bộ lọc "chỉ hiện thông báo từ ngày X trở đi" trong `filter_announcements`.
4. Thêm test mới trong `tests/test_nthu_api.py` cho bộ lọc bạn vừa thêm.
5. Đổi màu `--purple` trong `style.css` và xem trang đổi theo.

## 8. Đưa code lên GitHub

```
git add .
git commit -m "Announcements: flatten API data, language filter, pagination"
git push
```

Sau đó Manh và Nhan chạy `git pull` để cùng có bản mới.
