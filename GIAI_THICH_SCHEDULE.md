# Giải thích phần Weekly Schedule (thời khóa biểu tuần)

## 1. Vì sao có tính năng này
Biên bản gọi tính năng 1 là **"Personal Calendar & General Schedule"**. Calendar tháng chỉ chứa sự kiện một lần
theo ngày cụ thể (thi giữa kỳ, nộp bài). Còn **"General Schedule"** là lịch học lặp lại mỗi tuần
(ví dụ Calculus mỗi thứ Hai 10:10-12:00). Hai thứ khác bản chất nên tách thành hai trang:

| Trang | Dữ liệu | Ví dụ |
|---|---|---|
| `/calendar` | Sự kiện theo ngày cụ thể + hạn nộp việc từ trang Study | Midterm 11/20 |
| `/schedule` | Môn học lặp lại theo **thứ trong tuần** | Calculus, thứ Hai 10:10-12:00, R101 |

## 2. Các file
| File | Việc |
|---|---|
| `schedule_logic.py` | Kiểm tra dữ liệu, tìm môn trùng giờ, chia theo thứ, tính tổng giờ. Thuần Python. |
| `db.py` | Bảng `classes` và 5 hàm thêm/lấy/liệt kê/sửa/xóa (đều có `user_id`). |
| `app.py` | Route `/schedule` và `/api/classes`, `/api/classes/<id>`. |
| `templates/schedule.html` | Hiển thị: thống kê, phần "Today", các cột theo thứ. |
| `static/app.js` | Dùng lại `crudDialog()` đã viết cho trang Study, chỉ thêm khoảng 25 dòng. |

## 3. Database
```
classes(id, user_id, name, weekday, start, end, room)
```
- `weekday`: số nguyên 0 = Thứ Hai ... 6 = Chủ nhật (giống `date.weekday()` của Python, nên so với hôm nay rất tiện).
- `start`, `end`: chuỗi `HH:MM`.
- `end` là **từ khóa của SQL** (`CASE ... END`), nên trong câu SQL phải viết `"end"` (đặt trong ngoặc kép).
  Đây là chi tiết dễ làm hỏng: nếu quên thì SQLite báo lỗi cú pháp.

## 4. Phát hiện trùng giờ (phần Python đáng giải thích nhất)
Hai môn trùng giờ khi **cùng thứ** và hai khoảng giờ **chồng lên nhau**:

    A.start < B.end   VÀ   B.start < A.end

- Môn kết thúc 12:00 và môn bắt đầu 12:00 **không** tính là trùng (dấu `<` chứ không phải `<=`).
- Phải đổi giờ sang **số phút** (`to_minutes`: "10:30" -> 630) rồi mới so sánh. Không nên so sánh chuỗi
  hay ghép số kiểu `9:30` -> `930` vì sẽ sai khi so với `10:00`.
- `find_conflicts()` thử từng cặp môn, trả về tập id các môn bị trùng; giao diện tô đỏ và ghi "overlaps another class".

## 5. Các hàm khác trong `schedule_logic.py`
- `build_week()`: tạo 7 ngày, bỏ từng môn vào đúng ngày, xếp theo giờ bắt đầu. Làm trên **bản sao** (`dict(item, ...)`)
  để không sửa dữ liệu gốc.
- `visible_days()`: Thứ 2 đến Thứ 6 luôn hiện; Thứ 7 và Chủ nhật chỉ hiện khi có môn (đỡ rối với sinh viên không học cuối tuần).
- `weekly_minutes()`: tổng số phút trên lớp mỗi tuần, hiển thị bằng `format_minutes()` ("5h 30m").
- `validate_class()`: tên 1-100 ký tự, `weekday` 0-6, giờ đúng dạng `HH:MM`, giờ kết thúc phải **sau** giờ bắt đầu.
  `True/False` bị từ chối (trong Python `True` cũng là số 1).

## 6. API
| Method | Đường dẫn | Việc |
|---|---|---|
| GET / POST | `/api/classes` | Danh sách / thêm môn |
| PUT / DELETE | `/api/classes/<id>` | Sửa / xóa môn |

Lỗi dạng `{"error": "..."}`: 400 dữ liệu sai, 401 chưa đăng nhập, 404 không có hoặc **của người khác**.
Mọi POST/PUT/DELETE cần CSRF token.

## 7. Bảo mật
- Mọi câu SQL có `AND user_id = ?` (kể cả `update_class` và `delete_class`).
- Tên môn và phòng học được Jinja tự escape, nên chèn `<script>` không chạy được.
- Xóa tài khoản thì các môn bị xóa theo (`ON DELETE CASCADE`).

## 8. Câu TA có thể hỏi
- **Sao không lưu môn vào bảng `events` của Calendar?** Sự kiện gắn với một ngày cụ thể; môn học lặp lại mỗi tuần.
  Lưu từng buổi cho cả học kỳ sẽ tạo hàng trăm dòng và rất khó sửa.
- **Sao `weekday` dùng số 0-6?** Giống `date.weekday()` trong Python nên tìm "các môn hôm nay" chỉ là so một số.
- **Sao chỉ cảnh báo mà không chặn việc thêm môn trùng giờ?** Sinh viên có thể đang xếp thử hoặc có môn
  chỉ học nửa kỳ; cảnh báo cho họ biết mà vẫn cho tự quyết.
- **Test thế nào?** `tests/test_schedule_logic.py` (đúng/sai của trùng giờ, sắp xếp, kiểm tra dữ liệu) và
  `tests/test_schedule_api.py` (CRUD, CSRF, cô lập dữ liệu, XSS).

## 8b. Lưới theo tiết học NTHU (bảng thời khóa biểu)
- `PERIODS` trong schedule_logic.py là 14 tiết của NTHU: 1, 2, 3, 4, n, 5, 6, 7, 8, 9, a, b, c, d (08:00 đến 22:20).
- `class_periods(môn)` trả về (tiết đầu, tiết cuối) mà môn chạm vào, dùng lại quy tắc `overlaps`:
  10:10-12:00 chạm tiết 3 và 4 -> (2, 3). Môn không chạm tiết nào (ví dụ 06:30-07:30) trả về None
  và được liệt kê riêng ở mục "Outside the usual periods".
- `build_timetable()` thêm cho mỗi khối: `row` (tiết đầu), `span` (số tiết), `lane` và `lanes`.
  Hai môn chồng nhau được chia làn để đứng cạnh nhau (`_assign_lanes`: xếp theo tiết bắt đầu, mỗi môn
  lấy làn trống đầu tiên; một nhóm môn chồng nhau dùng chung số làn). CSS chỉ đặt khối theo các số đó.
- Bấm vào ô trống mở hộp thoại thêm môn, điền sẵn thứ và giờ của tiết đó.

## 9. Hạn chế đã biết
- Vẫn nhập giờ cụ thể khi thêm môn (bấm ô trống thì giờ của tiết được điền sẵn).
- Chưa phân biệt môn chỉ học nửa kỳ hoặc tuần chẵn/lẻ.
- Môn trong thời khóa biểu **chưa tự xuất hiện** trên lịch tháng (hai trang tách riêng).
- Chưa tự gắn với danh sách môn trong trang GPA hoặc Study (nhập tên môn riêng ở mỗi nơi).


## Nhập nhanh từ 校務資訊系統 và đường đi giữa hai tiết

Xem `GIAI_THICH_CAITIEN.md` mục 18 (đường đi giữa hai tiết trên trang chủ) và mục 19 (trang
"Import from 校務資訊系統": dán bảng 課表, xem trước, rồi nhập; code ở `timetable_import.py`).
