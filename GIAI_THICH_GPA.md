# Giải thích phần Credit & GPA

Tài liệu này giúp bạn trả lời TA: tính năng này làm gì, code nằm ở đâu, và vì sao viết như vậy.

## 1. Tính năng làm gì
Trang `/gpa` (cần đăng nhập) cho phép:
- Nhập các môn học theo học kỳ (ví dụ `115-1`): tên, số tín chỉ, điểm chữ.
- Để trống điểm = môn **đang học / dự định học**.
- Xem **GPA tích lũy**, **số tín chỉ đã đạt** so với số cần để tốt nghiệp, **số tín chỉ còn lại**.
- Đặt **GPA mục tiêu** và xem cần điểm trung bình bao nhiêu để đạt.

## 2. Các file và việc của từng file
| File | Việc |
|---|---|
| `gpa_logic.py` | Toàn bộ phép tính và kiểm tra dữ liệu. Thuần Python, không có Flask, không có database. |
| `db.py` | Bảng `courses` và `goals`; hàm thêm/sửa/xóa/lấy. Mọi câu SQL đều có `user_id`. |
| `app.py` | Route `/gpa` (trang) và `/api/courses`, `/api/goals` (API). |
| `templates/gpa.html` | Hiển thị. Chỉ in số mà Python đã tính. |
| `static/app.js` | Mở hộp thoại, gọi API, tải lại trang. Không tính toán gì. |

Quy tắc của cả dự án: **Python quyết định, JavaScript chỉ hiển thị.** Vì vậy JS không tự tính GPA.

## 3. Thang điểm (nguồn: Phòng Giáo vụ NTHU)
A+ = 4.3, A = 4.0, A- = 3.7, B+ = 3.3, B = 3.0, B- = 2.7, C+ = 2.3, C = 2.0, C- = 1.7, D = 1.0, E = 0, X = 0.

- Sinh viên đại học **đạt** môn từ C- trở lên. D, E, X là chưa đạt (không được tín chỉ).
- Môn **P** (pass/fail): được tín chỉ nhưng **không tính vào GPA**.
- Muốn đổi quy định, chỉ sửa `GRADE_POINTS` và `PASSING_POINTS` ở đầu `gpa_logic.py`.

## 4. Công thức

**GPA** là trung bình có trọng số theo tín chỉ:

    GPA = tổng(điểm số x tín chỉ) / tổng tín chỉ

Ví dụ: A (4.0) 3 tín chỉ và B+ (3.3) 3 tín chỉ -> (12 + 9.9) / 6 = **3.65**.
Chỉ tính môn có điểm chữ. Môn dự định và môn P bị bỏ qua. Môn E/X vẫn được tính (điểm 0) nên làm GPA giảm.

**Cần điểm trung bình bao nhiêu** (hàm `required_average`):
Gọi C0, P0 là tín chỉ và tổng điểm đã có; R là số tín chỉ sắp học; x là điểm trung bình cần đạt ở R tín chỉ đó.

    (P0 + x * R) / (C0 + R) = mục tiêu
    =>  x = (mục tiêu * (C0 + R) - P0) / R

Ví dụ: đã có 21.9 điểm trên 6 tín chỉ, muốn 3.7 sau 6 tín chỉ nữa:
x = (3.7 x 12 - 21.9) / 6 = **3.75**, tức là phải đạt **A** trở lên (A- chỉ có 3.7 là chưa đủ).

Kết quả có 4 trạng thái: `possible` (cần x điểm), `achieved` (chỉ cần qua môn), `impossible` (x > 4.3), `no_credits` (không còn tín chỉ).

Trang hiển thị hai con số: cho **các môn dự định** (R = tín chỉ chưa có điểm) và cho **toàn bộ tín chỉ còn lại** (R = số cần để tốt nghiệp - số đã đạt).

## 5. Học kỳ hiện tại
`current_semester()` đoán học kỳ để điền sẵn vào ô Semester. NTHU dùng năm Dân Quốc (năm dương lịch - 1911):
tháng 8-12 và tháng 1 là học kỳ 1, tháng 2-7 là học kỳ 2. Ví dụ tháng 11/2026 -> `115-1`.

## 6. Database
```
courses(id, user_id, name, credits, semester, grade, created_at)
goals(user_id PRIMARY KEY, target_gpa, credits_required)
```
- `goals` có `user_id` làm khóa chính nên mỗi người chỉ có một dòng. Lưu bằng "upsert": `INSERT ... ON CONFLICT(user_id) DO UPDATE`.
- `ON DELETE CASCADE`: xóa tài khoản thì môn học và mục tiêu đi theo.

## 7. API
| Method | Đường dẫn | Việc |
|---|---|---|
| GET / POST | `/api/courses` | Danh sách / thêm môn |
| PUT / DELETE | `/api/courses/<id>` | Sửa / xóa môn |
| GET / PUT | `/api/goals` | Xem / đặt mục tiêu |

Lỗi trả về dạng `{"error": "..."}`: 400 dữ liệu sai, 401 chưa đăng nhập, 404 môn không tồn tại **hoặc của người khác** (không tiết lộ là có tồn tại). Mọi POST/PUT/DELETE cần CSRF token như phần Calendar.

## 8. Bảo mật
- Mỗi câu SQL về môn học đều có `AND user_id = ?` -> người này không đọc/sửa/xóa được môn của người kia.
- Tên môn học được Jinja tự escape -> không chèn được `<script>` (XSS).
- Số tín chỉ phải là số nguyên 0-12; `True`/`False` bị từ chối (trong Python `True` cũng là số 1).

## 9. Câu TA có thể hỏi
- **Sao không tính GPA bằng JavaScript?** Để quy tắc chỉ nằm một chỗ (Python), dễ test, và người dùng không sửa được kết quả.
- **Môn chưa có điểm có tính vào GPA không?** Không. Nó chỉ được dùng để tính "cần điểm bao nhiêu".
- **Sao GPA trung bình có trọng số?** Môn 4 tín chỉ phải có ảnh hưởng nhiều hơn môn 1 tín chỉ.
- **Test thế nào?** `tests/test_gpa_logic.py` dùng số tính tay; `tests/test_gpa_api.py` kiểm tra API, CSRF, cách ly dữ liệu.

## 10. Hạn chế đã biết
- **128 tín chỉ tốt nghiệp chỉ là giá trị mặc định chưa kiểm chứng.** Mỗi ngành có yêu cầu riêng, hãy sửa theo ngành của bạn.
- "Số học kỳ còn lại" tính đơn giản từ 8 học kỳ; không tính học kỳ hè hay học lại.
- Không có quy tắc đặc biệt như học cải thiện điểm (điểm cũ bị thay), miễn môn, tín chỉ chuyển đổi.
- Điểm số phần trăm (0-100) chưa hỗ trợ; chỉ nhập điểm chữ.
