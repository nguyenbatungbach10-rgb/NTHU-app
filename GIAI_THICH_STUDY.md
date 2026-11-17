# Giải thích phần Study planning

## 1. Tính năng làm gì
Trang `/study` (cần đăng nhập) gồm ba phần, đúng như biên bản họp 10/16:
1. **Việc cần làm (tasks)**: có hạn nộp, tick "xong", và có thể **chia nhỏ** thành các bước (subtask).
2. **Môn học và tài liệu (subjects)**: mỗi môn có ô ghi chú để để link, tên sách, ghi chú.
3. **Thời gian học (sessions)**: ghi "hôm nay học 90 phút môn Calculus", trang tự cộng theo tuần và theo môn.

## 2. Các file
| File | Việc |
|---|---|
| `study_logic.py` | Kiểm tra dữ liệu, dựng cây việc cha/con, tính tuần, cộng phút. Thuần Python. |
| `db.py` | Bảng `subjects`, `tasks`, `study_sessions` và các hàm thêm/sửa/xóa/lấy. |
| `app.py` | Route `/study` và 6 route API. |
| `templates/study.html` | Hiển thị (một macro `task_row` dùng cho cả việc cha lẫn việc con). |
| `static/app.js` | Mở hộp thoại, gọi API. Hàm `crudDialog()` dùng chung cho cả 3 hộp thoại. |

Vẫn là quy tắc cũ: **Python quyết định, JavaScript chỉ hiển thị.**

## 3. Database
```
subjects(id, user_id, name, notes)
tasks(id, user_id, subject_id, parent_id, title, due_date, done)
study_sessions(id, user_id, subject_id, date, minutes, note)
```
- `tasks.parent_id` trỏ tới chính bảng `tasks`: việc con là một dòng có `parent_id` = id của việc cha.
  Việc cha có `parent_id` rỗng (NULL).
- `ON DELETE CASCADE` ở `parent_id`: **xóa việc cha thì các bước con bị xóa theo**.
- `ON DELETE SET NULL` ở `subject_id`: **xóa môn học thì việc và buổi học vẫn còn**, chỉ mất tên môn.
- `done` lưu 0/1 (SQLite không có kiểu true/false); `db.py` đổi lại thành `True/False`.

## 4. Quy tắc việc con
- Chỉ **một cấp**: việc con không có việc con riêng (API trả 400 nếu thử).
- Việc con **không có môn riêng**, dùng môn của việc cha (nên đổi môn của việc cha là các bước tự đổi theo).
- `parent_id` **không đổi được** sau khi tạo (tránh việc tạo vòng lặp cha-con).
- Số liệu "Open / Done / Overdue" chỉ đếm việc cha; việc con chỉ hiện dạng `1/2 steps`.

## 5. Các phép tính trong `study_logic.py`
- **Quá hạn** (`is_overdue`): chưa xong, có hạn nộp, và hạn nộp **trước** hôm nay. Đúng hôm nay chưa tính là quá hạn.
- **Thứ tự** (`build_task_tree`): việc chưa xong trước, trong đó hạn gần xếp trước, không hạn xếp cuối; việc đã xong xuống cuối.
- **Tuần** (`week_bounds`): tính từ thứ Hai. Khoảng ngày kiểu "từ thứ Hai đến TRƯỚC thứ Hai sau" nên không bị tính trùng ngày.
- **Cộng phút theo môn** (`minutes_by_subject`): buổi học không gắn môn nằm trong nhóm "No subject".
- Một buổi học tối đa 1440 phút (một ngày).

## 6. API
| Đường dẫn | Method | Việc |
|---|---|---|
| `/api/subjects`, `/api/subjects/<id>` | GET/POST, PUT/DELETE | Môn học |
| `/api/tasks`, `/api/tasks/<id>` | GET/POST, PUT/DELETE | Việc (kèm `parent_id` khi thêm việc con) |
| `/api/sessions`, `/api/sessions/<id>` | GET/POST, PUT/DELETE | Buổi học |

Lỗi dạng `{"error": "..."}`: 400 dữ liệu sai, 401 chưa đăng nhập, 404 không có hoặc của người khác.
Mọi POST/PUT/DELETE cần CSRF token.

## 7. Bảo mật (phần TA dễ hỏi nhất)
- **Lỗ hổng đặc trưng của tính năng này:** client gửi `subject_id` hoặc `parent_id`. Nếu server tin luôn,
  người dùng A có thể gắn việc của mình vào môn của B (và đọc tên môn đó qua trang), hoặc chèn việc con vào việc của B.
  Vì vậy `app.py` luôn kiểm tra id đó **thuộc về người đang đăng nhập** (`subject_exists()`, `db.get_task(user_id, ...)`)
  và trả 400 nếu không.
- Mọi câu SQL đều có `AND user_id = ?`, kể cả `get_*` và `update_*`.
- Ghi chú môn học được hiển thị bằng bộ lọc `urlize` của Jinja: link `http(s)` thành thẻ `<a>`
  (có `rel="noopener noreferrer"`), mọi ký tự khác vẫn được escape nên `<script>` không chạy được, và
  `javascript:...` không bao giờ thành link.
- Số phút phải là số nguyên 1-1440; `true/false` bị từ chối (trong Python `True` cũng là số 1).

## 7b. Hạn nộp hiện trên Calendar
- Trang `/calendar` đọc thêm các việc **chưa xong** có hạn nộp trong tháng (`db.list_tasks_due`) và truyền cho
  `build_month(..., tasks)`. Mỗi ô ngày có thêm danh sách `tasks`.
- Dữ liệu **không bị nhân đôi**: việc vẫn chỉ nằm ở bảng `tasks`, lịch chỉ đọc ra để vẽ. Nên tick xong ở trang Study
  thì thẻ tự biến mất khỏi lịch.
- Thẻ việc có viền (khác thẻ sự kiện tô tím đặc); quá hạn thì màu đỏ. Đúng hôm nay chưa tính quá hạn.
- Bước con (subtask) có hạn nộp cũng hiện.

## 8. Cách test
- `tests/test_study_logic.py`: số tính tay (tuần, quá hạn, cộng phút, thứ tự, kiểm tra dữ liệu).
- `tests/test_study_api.py`: CRUD, CSRF, cô lập dữ liệu, thử tấn công bằng id của người khác, xóa dây chuyền, XSS.
- Đã thử **phá code cố ý** (bỏ `user_id` khỏi từng câu SQL, bỏ bước kiểm tra môn, bỏ luật một cấp...) để chắc chắn test thật sự bắt được.

## 9. Hạn chế đã biết
- Việc trên Calendar chỉ để **xem** (bấm vào sẽ sang trang Study để sửa); không kéo thả đổi ngày hạn.
- Chưa có đồng hồ bấm giờ: phải tự nhập số phút sau khi học.
- Việc con chỉ một cấp, không kéo thả đổi thứ tự.
- "Hôm nay" và "tuần này" tính theo giờ của máy chạy server, không theo múi giờ từng người dùng.
- Danh sách buổi học chỉ hiện 15 buổi gần nhất (API `/api/sessions` trả đủ).
