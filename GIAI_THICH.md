# Giải thích code (để hiểu và trả lời TA)

> File này giải thích phần **Announcements**. Phần đăng ký/đăng nhập, database SQLite và
> Calendar nằm trong `GIAI_THICH_ACCOUNT_CALENDAR.md`.

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
5. `normalize()` dàn phẳng JSON thành list thông báo, xếp mới nhất trước, và gắn chủ đề cho từng thông báo bằng `classify()`.
6. `filter_announcements()` giữ lại các mục khớp office, từ khóa, ngôn ngữ, chủ đề.
7. `paginate()` cắt lấy 20 mục của trang hiện tại.
8. `render_template("announcements.html", items=...)` đưa dữ liệu vào template.
9. Jinja2 lặp qua `items` bằng `{% for %}`, tạo ra HTML và gửi về trình duyệt.

## 4. Từng file

| File | Làm gì |
|---|---|
| `app.py` | Khai báo các route (URL nào chạy hàm nào), đăng nhập và bảo mật. Logic dữ liệu nằm ở các file khác, `app.py` chỉ nối chúng lại. |
| `nthu_api.py` | Toàn bộ logic Python: gọi API, dàn phẳng JSON, lọc, phân trang, lấy danh sách office. Không import Flask nên test độc lập được. |
| `templates/base.html` | Khung chung (thanh menu, footer). Các trang khác `{% extends "base.html" %}` và chỉ điền phần `{% block content %}`. |
| `templates/announcements.html` | Form lọc + danh sách + nút chuyển trang. |
| `static/style.css` | Giao diện tím. |
| `inspect_api.py` | Script lưu mẫu JSON thật vào `api_sample.json`. |
| `templates/_macros.html` | Chứa macro `announcement(item)`: một thẻ thông báo dùng chung cho trang chủ và trang Announcements. |
| `tests/test_nthu_api.py` | Test cho logic trong `nthu_api.py` (dàn phẳng, phân loại, lọc, phân trang). |
| `tests/test_app.py` | Test các route Flask, thay dữ liệu API bằng dữ liệu giả nên không cần mạng. |
| `CALENDAR_API.md` | Hợp đồng giữa 3 thành viên: nút "Save to Calendar" sẽ gọi API nào. |
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
- **Phân loại bằng từ khóa**: API không có trường chủ đề, nên `classify()` đoán từ tiêu đề: duyệt danh sách chủ đề theo thứ tự, chủ đề nào có từ khóa nằm trong tiêu đề thì được chọn; không khớp thì là "Other". Cách này đơn giản, không cần AI, và sửa được bằng cách thêm từ khóa. Hạn chế: có thể phân loại sai khi tiêu đề mơ hồ.
- **Jinja macro**: giống một hàm trong Jinja (`{% macro announcement(item) %}`). Viết thẻ thông báo một lần, dùng ở cả hai trang bằng `{% from "_macros.html" import announcement %}`.
- **Test route Flask**: `app.test_client()` giả lập trình duyệt gửi request; `monkeypatch` thay `fetch_announcements` bằng dữ liệu giả để test chạy nhanh và không phụ thuộc mạng.

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
10. **Chủ đề của thông báo từ đâu ra?** API không có, nên em phân loại bằng từ khóa tiếng Anh và tiếng Hoa trong tiêu đề (`classify()`). Chủ đề nào khớp trước trong danh sách thì được chọn, không khớp thì là "Other".
11. **Phân loại bằng từ khóa có hạn chế gì?** Có thể sai khi tiêu đề mơ hồ hoặc không chứa từ khóa. Hướng cải thiện: thêm từ khóa, hoặc đọc nội dung bài thay vì chỉ tiêu đề.
12. **Làm sao phần của bạn nối với phần của Manh?** Hai bên thống nhất trước một hợp đồng API (`CALENDAR_API.md`): `POST /api/events` với `title`, `date`... Nút "Save to Calendar" sẽ gửi dữ liệu của thông báo tới đó.
13. **Bước tiếp theo là gì?** Nối nút "Save to Calendar" với Calendar API; đọc hạn chót (deadline) từ tiêu đề thay vì dùng ngày đăng.

## 7. Bài tập để thật sự hiểu code (nên tự làm)

1. Đổi `CACHE_SECONDS` thành 10, mở lại trang và xem hành vi thay đổi thế nào.
2. Đổi `PER_PAGE` thành 5 và xem số trang thay đổi.
3. Thêm bộ lọc "chỉ hiện thông báo từ ngày X trở đi" trong `filter_announcements`.
4. Thêm test mới trong `tests/test_nthu_api.py` cho bộ lọc bạn vừa thêm.
5. Đổi màu `--purple` trong `style.css` và xem trang đổi theo.
6. Thêm chủ đề mới (ví dụ "Sports") vào `CATEGORY_KEYWORDS` và viết một test `classify` cho nó.
7. Tìm một thông báo bị phân loại sai trên trang thật, thêm từ khóa để sửa, rồi chạy lại test.

## 8. Đưa code lên GitHub

```
git add .
git commit -m "Announcements: flatten API data, language filter, pagination"
git push
```

Sau đó Manh và Nhan chạy `git pull` để cùng có bản mới.

## Bản lưu thông báo (khi server không gọi được API)
- **Vấn đề:** gói miễn phí của PythonAnywhere chỉ cho server gọi ra một danh sách trang được duyệt, và `api.nthusa.tw`
  không có trong đó. Trên web online, server không lấy được thông báo; trên máy của nhóm thì vẫn được.
- **Cách giải quyết:** `tools/save_announcements.py` chạy trên máy có mạng, tải JSON gốc của API và lưu vào
  `data/announcements_snapshot.json` dạng `{"saved_at": "2026-11-18 11:40", "data": <JSON gốc>}`. Commit file này lên GitHub.
- **Thứ tự `fetch_announcements()` thử:**
  1. Gọi API trực tiếp. Được thì trả về `(items, None)`.
  2. Không được: đọc bản lưu (`load_snapshot()`, vẫn dùng `normalize()` và `classify()` như dữ liệu thật) và trả về
     `(items, {"kind": "snapshot", "saved_at": ..., "reason": ...})`. Trang ghi rõ "saved on <ngày>".
  3. Chưa có bản lưu: dữ liệu mẫu `(SAMPLE_ANNOUNCEMENTS, {"kind": "sample", ...})`. Trang chủ không hiện dữ liệu mẫu.
- Kết quả, kể cả khi lỗi, được nhớ 5 phút, để server không gọi lại API (và chờ lỗi) ở mọi lượt mở trang.
- Script chỉ ghi file khi tải được và có thông báo dùng được; lỗi thì giữ nguyên bản lưu cũ.
- **Cập nhật dữ liệu:** chạy lại script trên máy, commit, push, rồi `git pull` trên PythonAnywhere.
- Test: `tests/test_snapshot.py` (API thắng bản lưu, bản lưu thắng dữ liệu mẫu, file hỏng, nhớ tạm khi lỗi, script).
