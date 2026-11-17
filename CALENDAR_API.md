# Calendar API contract

**Trạng thái: đã cài đặt** trong `app.py` (route), `db.py` (SQL) và `calendar_logic.py` (kiểm tra dữ liệu).
Có test trong `tests/test_calendar_api.py`. Nếu thay đổi API, sửa file này, code và test cùng lúc.

Tất cả endpoint cần **đăng nhập** (session cookie). Mỗi sự kiện thuộc về người dùng đang đăng nhập;
client không gửi `user_id`.

Các request POST/PUT/DELETE phải kèm header **`X-CSRF-Token`** (lấy từ `<meta name="csrf-token">`),
nếu không server trả `400 {"error": "Invalid or missing CSRF token"}`.

## Dữ liệu một sự kiện

| Trường | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `id` | số nguyên | server tự tạo | |
| `title` | chuỗi, tối đa 200 ký tự | có | |
| `date` | `YYYY-MM-DD` | có | phải là ngày có thật (`2026-02-30` bị từ chối) |
| `time` | `HH:MM` | không | rỗng `""` nghĩa là cả ngày |
| `description` | chuỗi, tối đa 1000 ký tự | không | |
| `source_url` | chuỗi bắt đầu bằng `http://` hoặc `https://` | không | link tới thông báo gốc |

## Endpoint

### POST /api/events: tạo sự kiện
```json
{"title": "Scholarship deadline", "date": "2026-11-30", "time": "23:59",
 "description": "Office of Student Affairs", "source_url": "https://example.nthu.edu.tw/p/..."}
```
- `201 Created`: trả về sự kiện vừa tạo (có `id`).
- `400`: `{"error": "title and date are required"}`, `"date must be in YYYY-MM-DD format"`, `"time must be in HH:MM format"`, ...
- `401`: `{"error": "login required"}`.

### GET /api/events: danh sách sự kiện của bạn
- `200`: mảng sự kiện, xếp theo ngày rồi giờ.
- `?month=2026-11` chỉ lấy một tháng; `month` sai định dạng trả `400`.

### PUT /api/events/<id>: sửa sự kiện
- Body giống POST (gửi đủ các trường, thay thế toàn bộ).
- `200`: sự kiện sau khi sửa. `400`: dữ liệu sai. `404`: không có sự kiện hoặc không thuộc bạn.

### DELETE /api/events/<id>: xóa sự kiện
- `204 No Content` khi xóa được. `404` nếu không có hoặc không thuộc bạn (không phân biệt hai trường hợp).

## Nút "Save to Calendar" (trang Announcements)
Gửi `POST /api/events` với `{title, date: <ngày đăng>, description: <office>, source_url: <link>}`.
Tiêu đề dài hơn 200 ký tự được cắt bớt. Về sau có thể đổi `date` thành hạn chót nếu đọc được từ tiêu đề.

## Ví dụ gọi từ JavaScript
```js
await fetch("/api/events", {
  method: "POST",
  headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken},
  credentials: "same-origin",
  body: JSON.stringify({title: "Quiz", date: "2026-11-25"}),
});
```
(`static/app.js` có sẵn hàm `api()` làm việc này.)
