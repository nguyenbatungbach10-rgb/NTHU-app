# Giải thích: tài khoản, database và Calendar

File này giải thích phần đăng ký/đăng nhập, database SQLite và Calendar. Phần Announcements xem trong `GIAI_THICH.md`.

## 1. Bức tranh chung

| File | Vai trò |
|---|---|
| `db.py` | Mọi câu lệnh SQL (users, events). Không có logic khác. |
| `calendar_logic.py` | Python thuần: kiểm tra dữ liệu sự kiện, dựng lưới lịch tháng, đánh dấu thông báo đã lưu. |
| `app.py` | Route, đăng nhập, session, CSRF. Nối `db.py` và `calendar_logic.py` với template. |
| `templates/calendar.html`, `login.html`, `signup.html` | Giao diện Jinja. |
| `static/app.js` | JavaScript chỉ lo giao diện: gọi API, mở hộp thoại. Không chứa quy tắc nghiệp vụ. |

Nguyên tắc chia lớp: **Python quyết định, JavaScript chỉ hiển thị.** Mọi kiểm tra dữ liệu nằm ở Python, vì JavaScript chạy trên máy người dùng nên có thể bị bỏ qua. Cách chia này cũng giữ phần lớn code là Python (đề yêu cầu ≥ 50%).

## 2. Database SQLite

Hai bảng, quan hệ **một-nhiều** (một user có nhiều event):

```
users:  id, email (UNIQUE), password_hash, created_at
events: id, user_id -> users.id, title, date, time, description, source_url, created_at
```

- `PRIMARY KEY AUTOINCREMENT`: id tự tăng.
- `UNIQUE` trên email: database tự từ chối email trùng (Python bắt `sqlite3.IntegrityError`).
- `REFERENCES users(id) ON DELETE CASCADE`: xóa user thì sự kiện của họ tự xóa theo (cần `PRAGMA foreign_keys = ON`, đã bật trong `get_db()`).
- `INDEX (user_id, date)`: tìm sự kiện của một người theo tháng nhanh hơn.
- File database là `instance/app.db`, được tạo tự động ở lần chạy đầu. Thư mục `instance/` nằm trong `.gitignore` nên **không đưa lên GitHub**: mỗi người có database riêng trên máy mình.

**Hai quy tắc trong `db.py`:**
1. **Câu SQL tham số hóa**: `WHERE id = ?` rồi truyền giá trị riêng, không ghép chuỗi. Nhờ vậy người dùng không thể chèn SQL vào ô nhập (SQL injection).
2. **Mọi câu đụng tới sự kiện đều có `AND user_id = ?`**. Vì thế người này không đọc, sửa, xóa được sự kiện của người kia. Có test riêng cho việc này.

Muốn xem dữ liệu thật và thử câu **JOIN**:
```
python
>>> import sqlite3
>>> c = sqlite3.connect("instance/app.db")
>>> c.execute("SELECT u.email, e.title, e.date FROM events e JOIN users u ON u.id = e.user_id").fetchall()
```
`JOIN` ghép dòng của hai bảng dựa trên `e.user_id = u.id`: mỗi sự kiện kèm email của chủ sự kiện.

Reset database khi muốn làm lại từ đầu: tắt server rồi xóa file `instance\app.db`.

## 3. Đăng ký và đăng nhập

- **Băm mật khẩu**: `generate_password_hash` biến mật khẩu thành chuỗi băm (có "muối" ngẫu nhiên, thuật toán chậm). Database chỉ giữ chuỗi băm. Đăng nhập thì `check_password_hash` băm mật khẩu vừa nhập rồi so. Không ai, kể cả nhóm mình, đọc lại được mật khẩu gốc.
- **Session**: sau khi đăng nhập, `session["user_id"] = ...`. Flask lưu session trong **cookie được ký bằng `SECRET_KEY`**, nên người dùng không sửa được nội dung cookie. Mỗi request, `before_request` đọc `user_id` và nạp người dùng vào `g.user`.
- **`session.clear()` trước khi đặt `user_id`**: tạo phiên mới sau khi đăng nhập, tránh tấn công "session fixation".
- **Thông báo lỗi chung** "Invalid email or password" cho cả sai email lẫn sai mật khẩu, để không lộ email nào đã đăng ký.
- **`@login_required`**: bọc các route cần đăng nhập. Trang web thì chuyển tới `/login?next=...`; API thì trả `401` JSON.
- **`safe_next()`**: sau khi đăng nhập chỉ chuyển hướng tới đường dẫn nội bộ (`/calendar`), chặn `https://evil.com` hay `//evil.com` (open redirect).
- **Đăng xuất dùng POST** (kèm CSRF token) để một trang lạ không tự đăng xuất bạn được.
- Email được chuẩn hóa chữ thường: `User@X.com` và `user@x.com` là một tài khoản.

## 4. CSRF là gì và cách chặn

**Tình huống tấn công:** bạn đang đăng nhập web mình. Bạn mở một trang lạ có sẵn form ẩn tự gửi `POST /api/events` tới web mình. Trình duyệt tự gắn cookie đăng nhập của bạn, server tưởng chính bạn làm.

**Cách chặn trong code:**
1. Mỗi phiên có một `csrf` token ngẫu nhiên lưu trong session.
2. Form có `<input type="hidden" name="csrf_token" value="...">`; `fetch` gửi header `X-CSRF-Token` (đọc từ thẻ `<meta name="csrf-token">`).
3. `before_request` kiểm tra mọi request POST/PUT/DELETE: token gửi lên phải khớp token trong session, nếu không trả `400`. Trang lạ không biết token nên không giả mạo được.
4. Thêm `SESSION_COOKIE_SAMESITE = "Lax"`: trình duyệt không gửi cookie kèm request POST từ trang khác. Hai lớp bảo vệ cùng lúc.

So sánh token dùng `hmac.compare_digest` (so sánh thời gian không đổi), và token rỗng không bao giờ được coi là khớp (có test).

## 5. Chống XSS

- Jinja **tự escape** HTML: tiêu đề sự kiện `<script>alert(1)</script>` hiện thành chữ chứ không chạy (có test).
- `source_url` được dùng trong thẻ `<a href>`, nên server chỉ nhận URL bắt đầu bằng `http://` hoặc `https://`. Chặn `javascript:...`.

## 6. Calendar API

| Method và đường dẫn | Việc | Thành công | Lỗi |
|---|---|---|---|
| `POST /api/events` | Tạo sự kiện | `201` + sự kiện có `id` | `400` dữ liệu sai, `401` chưa đăng nhập |
| `GET /api/events?month=YYYY-MM` | Danh sách (lọc tháng tùy chọn) | `200` | `400` month sai, `401` |
| `PUT /api/events/<id>` | Sửa | `200` | `400`, `401`, `404` |
| `DELETE /api/events/<id>` | Xóa | `204` | `401`, `404` |

- `404` cũng trả về khi sự kiện **thuộc người khác**: không để lộ rằng sự kiện đó có tồn tại.
- Mọi dữ liệu đi qua `validate_event()`: bắt buộc `title` và `date` (YYYY-MM-DD hợp lệ, ví dụ `2026-02-30` bị từ chối), `time` dạng HH:MM, giới hạn độ dài, `source_url` chỉ http/https.
- Ngoài ra có `GET /api/announcements` (công khai) từ phần Announcements.

## 7. Giao diện Calendar

- **Lưới tháng dựng ở phía Python**: `build_month()` dùng module `calendar` có sẵn để chia tháng thành các tuần (Thứ 2 đến Chủ nhật), gắn sự kiện vào đúng ngày, xếp theo giờ. Template chỉ việc lặp qua kết quả.
- `?month=2026-11` chọn tháng; `shift_month()` xử lý tháng trước/sau kể cả khi qua năm; tháng sai thì rơi về tháng hiện tại.
- **JavaScript** chỉ: mở thẻ `<dialog>` có sẵn của HTML, gọi `fetch` tới API, rồi `location.reload()` để vẽ lại từ dữ liệu mới.

**Luồng "Save to Calendar":**
1. Bấm nút → `app.js` gửi `POST /api/events` với `{title, date, description: office, source_url: link}`, kèm CSRF header.
2. Server kiểm tra đăng nhập, CSRF, `validate_event()`, rồi `INSERT` với `user_id` của bạn.
3. Nút đổi thành "Saved ✓". Lần sau mở trang, `saved_keys()` lấy các cặp `(title, date)` đã lưu và `mark_saved()` đánh dấu sẵn.
4. `mark_saved()` trả về **bản sao** của danh sách. Danh sách thông báo nằm trong cache dùng chung cho mọi người; nếu sửa trực tiếp, trạng thái "đã lưu" của người này có thể lộ sang người khác.

Hiện tại nút dùng **ngày đăng** của thông báo làm ngày sự kiện. Đọc hạn chót (deadline) từ tiêu đề là bước cải tiến tiếp theo.

## 8. Hạn chế đã biết (nói thật với TA)

- Chưa giới hạn số lần đăng nhập sai (brute force), chưa có quên mật khẩu hay xác minh email.
- `SECRET_KEY` mặc định chỉ dùng để phát triển. Khi deploy phải đặt biến môi trường `SECRET_KEY` và bật HTTPS (khi đó thêm `SESSION_COOKIE_SECURE = True`).
- SQLite là một file, hợp với dự án học tập và ít người dùng, không hợp tải lớn hay nhiều máy chủ.
- "Hôm nay" lấy theo giờ của máy chạy server.
- Chưa có Study planning và GPA tracking.

## 9. Câu hỏi TA có thể hỏi (và gợi ý trả lời)

1. **Mật khẩu lưu thế nào?** Chỉ lưu bản băm có muối bằng `generate_password_hash`; đăng nhập so bản băm, không bao giờ có mật khẩu gốc.
2. **Session hoạt động ra sao?** Sau đăng nhập, `user_id` được lưu trong cookie session do Flask ký bằng `SECRET_KEY`. Mỗi request, server đọc cookie đó để biết bạn là ai; sửa cookie thì chữ ký sai và bị bỏ.
3. **Làm sao người này không xem được sự kiện của người kia?** Mọi câu SQL đều có `AND user_id = ?` lấy từ session, không lấy từ dữ liệu client gửi. Có test hai người dùng.
4. **SQL injection là gì, em chống thế nào?** Chèn SQL qua ô nhập. Em dùng câu lệnh tham số hóa (`?`) nên giá trị người dùng luôn là dữ liệu, không bao giờ là câu lệnh.
5. **CSRF là gì?** Trang lạ lợi dụng cookie đăng nhập của bạn để gửi request. Em chặn bằng token trong session kèm SameSite cookie.
6. **XSS là gì?** Chèn mã JavaScript qua dữ liệu hiển thị. Jinja tự escape, và server chỉ nhận URL http/https.
7. **Vì sao kiểm tra dữ liệu ở server khi JavaScript cũng kiểm tra?** Người dùng có thể bỏ qua JavaScript, gọi thẳng API. Server là nơi duy nhất đáng tin.
8. **Vì sao `404` khi sửa sự kiện của người khác thay vì `403`?** Không cho biết sự kiện đó có tồn tại.
9. **Vì sao dùng SQLite?** Có sẵn trong Python, không cần cài server, một file, đủ cho quy mô dự án. Hạn chế: không hợp tải lớn.
10. **`ON DELETE CASCADE` để làm gì?** Xóa user thì database tự xóa sự kiện của họ, không để lại dữ liệu mồ côi.
11. **Vì sao dựng lưới lịch ở Python thay vì JavaScript?** Giữ logic ở Python (đề yêu cầu ≥ 50%), test được bằng pytest, và JavaScript chỉ lo tương tác.
12. **Em kiểm tra code bằng cách nào?** Có 57 test tự động (pytest): logic, đăng nhập, CSRF, API, và cô lập dữ liệu giữa hai người dùng. Em có thể thử cố tình phá một kiểm tra bảo mật (ví dụ bỏ `AND user_id = ?`) để cho thấy test báo đỏ.

## 10. Bài tập để thật sự hiểu code (nên tự làm)

1. Mở `instance/app.db` bằng đoạn `sqlite3` ở mục 2, chạy câu JOIN và đối chiếu với những gì thấy trên web.
2. Đổi mật khẩu tối thiểu từ 8 thành 10 ký tự trong `app.py` và trong `signup.html`, rồi sửa test cho khớp.
3. Thêm trường `location` cho sự kiện: sửa `SCHEMA`, `validate_event`, các hàm trong `db.py`, hộp thoại và test. Chú ý file `app.db` cũ không tự thêm cột, nên xóa nó khi thử.
4. Thêm nút "Today" luôn hiện trên trang Calendar, hoặc tô màu sự kiện theo giờ.
5. Viết một test mới: người dùng chưa đăng nhập gọi `GET /api/events?month=2026-11` phải nhận `401`.

## 11. Chạy và kiểm tra

```
python -m pytest        # 57 test, vài giây
python app.py           # http://127.0.0.1:5000
```

Lần đầu: đăng ký một tài khoản trên `/signup`, mở `/calendar`, thêm một sự kiện, rồi vào `/announcements` thử nút "Save to Calendar".
