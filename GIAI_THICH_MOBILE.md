# Giải thích: giao diện điện thoại giống mockup (bản 21)

So với mockup dùng trong slide pitch, web được sửa ở 7 chỗ. Logic nằm trong Python; template và CSS chỉ hiển thị.

## 1. Thanh tab dưới đáy (`home_logic.TABS`, `current_tab`; `base.html`)
- Màn hình hẹp hơn 720px (điện thoại): hiện thanh 5 tab **Today · Calendar · Study · Notices · More**, ẩn nút ☰ ở trên và
  ẩn 6 ô giới thiệu ở trang chủ (thanh tab đã thay cho chúng). Tên web rút gọn thành "NTHU App".
- Tab nào sáng do Python quyết định: `current_tab("gpa_page")` → `"study_page"` (trang con thuộc tab Study),
  trang không thuộc tab nào (Schedule, Map, Account) → `"more"`.
- Tab **More** mở cùng một menu như nút ☰ (bảng nổi phía trên thanh tab). JavaScript chỉ đóng/mở.
- Lỗi đã gặp: thanh trên dùng `backdrop-filter` (làm mờ nền), khiến bảng menu `position: fixed` bên trong bị tính vị trí
  theo thanh đó và nằm ngoài màn hình → trên điện thoại bỏ `backdrop-filter`.
- Trang Study và GPA có nút chuyển nhanh "Study planning | Credits & GPA" (mockup gộp hai trang vào tab Study).

## 2. Calendar: dải tuần + lịch trong ngày (`calendar_logic.week_strip`, `day_agenda`, `agenda_summary`)
- Lưới tháng 7 cột bị cắt trên điện thoại (chỉ thấy Thứ 2–4). Giờ điện thoại hiện:
  dải 7 ngày (chấm tím = lớp, cam = sự kiện, đỏ = hạn chót) → chip "2 classes · 2 events · 1 deadline" →
  danh sách **mọi thứ của ngày đã chọn** gộp lại: lớp (từ thời khóa biểu), sự kiện, việc cần làm tới hạn.
- `day_agenda`: sự kiện cả ngày trước, rồi các mục có giờ theo giờ, hạn chót cuối cùng.
- Chọn ngày bằng link `?day=2026-11-20` (không cần JavaScript); mũi tên ‹ › nhảy ±7 ngày. Nút + tròn để thêm sự kiện.
- Máy tính vẫn dùng lưới tháng như cũ.

## 3. Announcements (`nthu_api.highlight`; `announcements.html`)
- Ô tìm kiếm ở trên cùng, chip loại cuộn ngang (bấm là lọc), bộ lọc ít dùng (đơn vị, ngôn ngữ) gấp trong "More filters".
- **Tô vàng từ khóa**: `highlight("Taiwan Scholarship", "scholar")` → `[("Taiwan ", False), ("Scholar", True), ("ship", False)]`;
  template in đoạn khớp trong `<mark>`. Jinja vẫn escape từng đoạn nên tiêu đề có `<b>` cũng không chạy được HTML.
  `re.escape` để từ khóa như "1+1" không bị hiểu là biểu thức regex.
- Bấm "Save to Calendar" → nút thành **✓ Added** (màu xanh) và hiện thông báo nổi "Deadline added to your calendar"
  (hoặc "Added to your calendar" nếu tiêu đề không có chữ báo hạn chót).

## 4. GPA (`gpa_logic.goal_status`, `grades_needed`, `year_targets`, `credits_by_year`)
- Thẻ **GPA goal**: mục tiêu (số to), GPA hiện tại, nhãn **On track** (GPA ≥ mục tiêu) / **Almost there** (thiếu ≤ 0.15) /
  **Below target**. Thanh kéo chọn mục tiêu (JavaScript chỉ đồng bộ thanh kéo với ô số; Python kiểm tra khi lưu).
  "Projected" trong mockup ở đây là GPA hiện tại (nếu giữ phong độ), vì web không đoán trước điểm.
- **Grades you need**: mỗi môn chưa có điểm kèm điểm chữ cần đạt (từ `required_average`).
- Thẻ **Graduation credits**: tổng tín chỉ và từng năm. Năm học lấy từ mã học kỳ ("115-1" → năm 115); năm 1 = năm sớm
  nhất có môn. `year_targets(128)` chia đều 4 năm (32 mỗi năm, phần dư cho các năm đầu).
- Ô "Credits to graduate" nằm ở thẻ khác nhưng có `form="goal-form"` nên vẫn gửi chung form mục tiêu.

## 5. Thống kê học tập (`study_logic.analytics` và các hàm nhỏ)
- Cột theo ngày (tuần này Thứ 2 → CN, hoặc 30 ngày gần nhất), tổng giờ, **% so với kỳ trước** (`percent_change`),
  biểu đồ tròn theo môn (`subject_shares`: 5 môn nhiều nhất + "Other"), **chuỗi ngày học liên tiếp** (`study_streak`),
  thứ trong tuần học nhiều nhất (`best_weekday`).
- Biểu đồ vẽ bằng CSS, không cần thư viện: cột là `height: X%`; biểu đồ tròn là `conic-gradient(...)` do Python tạo
  (`donut_gradient`). Màu từng môn là biến `--c1`…`--c6`.
- Mockup ghi "You focus best between 20:00 and 22:00": web không lưu giờ học trong ngày (chỉ lưu ngày + số phút),
  nên thay bằng "You study most on Tuesday".

## 6. Đồng bộ lịch (`ics_export.py`; `/account` → Calendar sync; `/calendar/feed/<token>.ics`)
- Bật trong Account (hoặc nút "Sync to phone" ở Calendar): chọn đồng bộ lớp học / sự kiện + hạn chót đã lưu / việc học.
- Web tạo một **link bí mật** (`secrets.token_urlsafe`, lưu ở bảng `calendar_feeds`). Google Calendar ("From URL") hoặc
  iPhone (`webcal://`) tải link này định kỳ. Link không cần đăng nhập, nên ai có link đều xem được → giữ kín;
  "New link" đổi link (link cũ hết dùng), "Turn off" xóa.
- File `.ics` (chuẩn iCalendar): lớp học lặp mỗi tuần (`RRULE:FREQ=WEEKLY;UNTIL=` hết học kỳ, ước lượng 20/1 hoặc 30/6),
  giờ đổi từ giờ Đài Loan sang UTC (trừ 8 tiếng), ký tự `, ; \` được thoát, dòng dài quá 75 byte được gập
  (chữ Hán 3 byte, không cắt giữa chữ). Test kiểm tra file bằng thư viện `icalendar` chuẩn.
- **Giới hạn (nói thật khi demo)**: đồng bộ MỘT CHIỀU (web → ứng dụng lịch). Google tự quyết định bao lâu tải lại link
  (thường vài tiếng), nên không có "synced 2 min ago" hay đồng bộ hai chiều như mockup.

## 7. Chuông thông báo (`home_logic.notifications`; `/notifications`)
- Số trên chuông = việc trễ hạn + việc tới hạn hôm nay/ngày mai + lớp bắt đầu trong 60 phút + sự kiện hôm nay (chưa qua giờ)
  và ngày mai. Xếp theo mức gấp. Không phải thông báo đẩy (push): chỉ hiện khi bạn mở web.

## Lỗi phát hiện thêm khi làm
- Khóa dịch "Next" bị trùng: chip "Next" của trang chủ hiện thành 下個月 (tháng sau). Đổi sang khóa "Up next" và thêm test
  `test_no_duplicate_keys_in_translation_tables` để từ giờ khóa trùng bị báo lỗi ngay.

## Câu hỏi TA có thể hỏi
1. **Vì sao đồng bộ lịch không cần đăng nhập?** Ứng dụng lịch của Google/Apple không đăng nhập vào web mình được; link chứa
   một chuỗi ngẫu nhiên 32 ký tự (khó đoán như mật khẩu) đóng vai trò chìa khóa, và có thể đổi bất cứ lúc nào.
2. **Biểu đồ tròn vẽ thế nào khi không dùng thư viện?** CSS `conic-gradient` tô màu theo góc: môn 1 từ 0% đến 46%, môn 2
   từ 46% đến 78%... Python tính các mốc phần trăm.
3. **Sao điện thoại và máy tính khác giao diện?** Cùng một HTML; CSS `@media (max-width: 720px)` chọn phần hiện ra.
