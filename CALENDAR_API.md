# Calendar API contract (Bach <-> Manh <-> Nhan)

Mục đích: thống nhất sớm giao diện giữa 3 phần để làm song song.
Nút **Save to Calendar** trên trang Announcements (phần của Bach) sẽ gọi API này.
Manh làm API, Nhan làm trang Calendar. Nếu Manh đã làm khác, chỉ cần sửa file này cho khớp.

## Dữ liệu một sự kiện (event)

| Trường | Kiểu | Bắt buộc | Ví dụ |
|---|---|---|---|
| `id` | số nguyên | server tự tạo | `12` |
| `title` | chuỗi | có | `"Scholarship application deadline"` |
| `date` | chuỗi ISO `YYYY-MM-DD` | có | `"2026-11-30"` |
| `time` | chuỗi `HH:MM` | không | `"23:59"` |
| `description` | chuỗi | không | `"Office of Student Affairs"` |
| `source_url` | chuỗi | không | `"https://..."` (link bài thông báo gốc) |

Sự kiện luôn thuộc về **người dùng đang đăng nhập** (lấy từ session, client không gửi `user_id`).
Nếu Manh không muốn thêm cột `source_url`, Bach sẽ nhét link vào cuối `description`.

## Các endpoint

### POST /api/events: tạo sự kiện
Body JSON:
```json
{"title": "Scholarship application deadline", "date": "2026-11-30",
 "description": "Office of Student Affairs",
 "source_url": "https://example.nthu.edu.tw/p/..."}
```
- `201 Created`: trả về sự kiện vừa tạo (có `id`).
- `400 Bad Request`: `{"error": "title and date are required"}` hoặc ngày sai định dạng.
- `401 Unauthorized`: `{"error": "login required"}` khi chưa đăng nhập.

### GET /api/events: danh sách sự kiện của người dùng
- `200 OK`: mảng các sự kiện, xếp theo `date` tăng dần.
- Tuỳ chọn `?month=2026-11` để chỉ lấy một tháng.

### DELETE /api/events/<id>: xoá sự kiện
- `204 No Content` khi xoá được; `404` nếu không có hoặc không thuộc người dùng này.

## Cách nút "Save to Calendar" sẽ dùng (Bach làm sau khi API có)
Mỗi thông báo gửi `{title, date, description: <office>, source_url: <link>}` tới `POST /api/events`.
`date` lấy từ ngày đăng thông báo; về sau có thể đổi thành hạn chót (deadline) nếu đọc được từ tiêu đề.

## Việc cần Manh xác nhận
1. Tên endpoint và các trường ở trên có khớp với cái đã làm chưa?
2. Có thêm cột `source_url` được không?
3. Đăng nhập dùng session cookie của Flask phải không? (Bach sẽ gọi bằng `fetch(..., {credentials: "same-origin"})`.)
