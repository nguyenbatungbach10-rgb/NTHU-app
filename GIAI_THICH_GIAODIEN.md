# Giải thích: lịch cả năm, chọn nhanh tháng, menu 3 gạch, giao diện mới

File này để cả nhóm đọc và trả lời được câu hỏi của TA về phần nâng cấp giao diện.

## 1. Lịch cả năm (`/calendar/year`)
- **calendar_logic.py** (Python quyết định):
  - `parse_year("2026")` đọc năm từ URL. Chỉ nhận đúng 4 chữ số và nằm trong 1970 đến 2100. Sai thì trả về `None`, trang tự dùng năm hiện tại (không bao giờ báo lỗi hay sập).
  - `year_bounds(2026)` trả về ngày 2026-01-01 và 2027-01-01, để SQL lấy cả năm bằng **một** câu truy vấn thay vì 12 câu.
  - `build_year(year, events, today, tasks)` dựng 12 tháng thu nhỏ. Mỗi ngày có `count` = số sự kiện + số việc cần làm (chưa xong) có hạn vào ngày đó. Hàm không sửa dữ liệu đầu vào.
- **app.py** `calendar_year_page()`: lấy sự kiện và việc cần làm **của người đang đăng nhập** (`g.user["id"]`), rồi gọi `build_year`. Cần đăng nhập (`@login_required`).
- **calendar_year.html**: vẽ 12 thẻ. Ngày có 1 mục tô nhạt, từ 2 mục trở lên tô đậm, hôm nay tô vàng. Cả thẻ tháng bấm được (link `::after` phủ kín thẻ) và dẫn tới `/calendar?month=YYYY-MM`.

## 2. Chọn nhanh tháng/năm ở lịch tháng
- Bấm vào tên tháng (ví dụ "December 2026") để mở bảng 12 tháng, mũi tên đổi năm, và nút "See all of 2026".
- Dùng thẻ `<details>` có sẵn của HTML, nên không cần JavaScript để mở/đóng. JavaScript chỉ thêm việc đóng bảng khi bấm ra ngoài hoặc nhấn Esc.
- Các link được tạo ở phía server (`url_for(...)`), không có logic ngày tháng trong JS.

## 3. Menu 3 gạch
- **base.html**: danh sách 6 trang nằm trong một biến `menu` rồi lặp bằng `{% for %}`, nên thêm trang mới chỉ thêm một dòng.
- `aria-current="page"` đánh dấu trang đang mở (trang lịch năm cũng tính là Calendar).
- **app.js**: chỉ đổi thuộc tính `aria-expanded` và `hidden`. Có Esc để đóng và bấm ra ngoài để đóng.
- Tên người dùng và nút Log out nằm trong menu.

## 4. Màu theo tính năng
- `<body class="theme-teal">`... được chọn trong base.html theo `request.endpoint`. CSS chỉ cần đổi 3 biến (`--accent`, `--accent-dark`, `--accent-soft`) là nút, tiêu đề, viền của cả trang đổi màu theo.
- Calendar tím, Schedule xanh ngọc, GPA xanh lá, Study cam đỏ, Announcements xanh dương. Màu vàng chỉ dành cho "hôm nay".

## 5. Khối "hôm nay" ở trang chủ
- **study_logic.due_today(tasks, today_iso, limit)**: lọc việc **chính** (không phải việc con) chưa xong, có hạn từ hôm nay trở về trước, xếp hạn cũ nhất trước, gắn `overdue`. Trả về bản sao.
- Các môn học hôm nay lấy bằng `schedule_logic.classes_on(classes, today.weekday())` (Thứ Hai = 0).
- Cả hai chỉ lấy dữ liệu của người đang đăng nhập; có test kiểm tra người khác không thấy.

## Giới hạn
- "Hôm nay" theo ngày của máy chủ (giờ UTC trên PythonAnywhere có thể lệch ngày vài giờ so với Đài Loan).
- Font Bricolage Grotesque và Figtree tải từ Google Fonts; không có mạng thì trình duyệt dùng font hệ thống, trang vẫn dùng bình thường.
- Mã HTML/CSS/JS tăng lên nên tỷ lệ Python giảm xuống còn khoảng 52% (yêu cầu của môn là ít nhất 50%).
