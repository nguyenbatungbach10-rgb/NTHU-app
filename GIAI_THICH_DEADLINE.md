# Giải thích phần đọc ngày hạn từ tiêu đề thông báo

## 1. Vấn đề
Tên tính năng 4 là "Announcements & **Deadline Tracker**". Nhưng dữ liệu của NTHU API chỉ có **ngày đăng**,
không có ngày hạn. Trước đây nút "Save to Calendar" lưu sự kiện vào ngày đăng, nên lịch hiện sai ngày
(thông báo đăng 11/1 nhưng hạn nộp 11/20).

Ngày hạn thường nằm ngay trong **tiêu đề**, ví dụ (tiêu đề thật):
- `本室於115年10月08日(星期四)辦理經費報支說明講習` -> 8/10/2026
- `Outdoor disinfection operations on Nanda campus(115.03.21)` -> 21/3/2026
- `Three pruning Notice on Nanda campus.(114/12/09-114/12/11)` -> một khoảng ngày

## 2. File nào làm gì
| File | Việc |
|---|---|
| `deadline_logic.py` | Đọc ngày từ tiêu đề. Thuần Python. Hàm chính: `extract_dates()` và `suggest_date()`. |
| `calendar_logic.py` | `mark_saved()` gọi `suggest_date()` để mỗi thông báo có thêm `event_date` và `date_from_title`. |
| `templates/_macros.html` | Nút Save dùng `event_date`; hiện dòng "Will be saved on ... (date found in the title)". |

## 3. Năm Dân Quốc (ROC)
Đài Loan đếm năm từ 1912, nên **năm dương lịch = năm Dân Quốc + 1911** (115 -> 2026). Thông báo của trường
dùng cách này rất nhiều. `115年10月08日` và `115.03.21` đều được đổi sang năm dương lịch.
`114學年度` (năm học 114) **không** bị đọc nhầm thành ngày vì nó không có tháng và ngày.

## 4. Biểu thức chính quy (regex) và thứ tự các mẫu
Có 5 mẫu, chạy theo thứ tự:
1. `full_ad`: 2026-11-20, 2026/11/20, 2026.11.20, 2026年11月20日
2. `full_roc`: 115年10月08日, 115.03.21, 114/12/09 (năm 3 chữ số bắt đầu bằng 1)
3. `md_zh`: 11月20日, 11月20號 (không có năm)
4. `md_en`: November 20, 2026 / Nov. 20 / Nov 20th
5. `dm_en`: 20 November 2026 / 20th Nov

**Thứ tự quan trọng.** Sau mỗi mẫu, phần đã khớp bị **thay bằng dấu cách** (che đi) để mẫu sau không đọc lại.
Nếu không che, `2025年12月28日` sẽ bị mẫu `md_zh` đọc lần hai như "12月28日" và đoán sai năm.
`(?<!\d)` ("không có chữ số đứng ngay trước") giúp `2115.03.21` không bị cắt thành `115.03.21`.

## 5. Ngày không ghi năm: đoán năm
Với `11月20日` hay `Nov 20` không có năm, `_closest_year()` thử 3 năm (năm đăng -1, năm đăng, năm đăng +1) và chọn
năm cho ngày **gần ngày đăng nhất**. Ví dụ đăng 2026-12-20, "1月15日前繳交" -> 2027-01-15 (gần hơn 2026-01-15).

## 6. Các ngày bị bỏ qua
- Ngày không có thật (2月30日, Feb 30): bắt bằng `date(năm, tháng, ngày)` báo lỗi `ValueError`.
- Ngày cách năm đăng hơn 1 năm (ví dụ 2099): chắc là số khác.
- Ngày **cũ hơn ngày đăng quá 7 ngày** (`GRACE_DAYS`): thường là ngày tham chiếu
  ("theo thông báo ngày 2026/01/05..."), không phải hạn hay ngày diễn ra.
- Số phiên bản như `1.2.3`: không khớp mẫu nào (cần năm 20xx hoặc 1xx).

## 7. Chọn ngày nào để lưu (`suggest_date`)
- Không tìm thấy ngày -> dùng ngày đăng như cũ (`from_title = False`).
- Một ngày -> ngày đó.
- Nhiều ngày (một khoảng, ví dụ 12/09-12/11): nếu tiêu đề có từ chỉ **hạn chót** (截止, 期限, 日止, deadline, due, until,
  closes...) thì lấy ngày **cuối**; không có thì lấy ngày **đầu** (thường là ngày bắt đầu sự kiện).
- Từ `due` dùng `\bdue\b` nên không khớp nhầm trong `residue` hay `overdue`.

## 8. Vì sao giao diện nói rõ "date found in the title"
Đây là cách **đoán**, không đúng 100%. Dòng chữ "Will be saved on 2026-11-20 (date found in the title)" cho người
dùng thấy và tự kiểm tra trước khi lưu. Ngày hiển thị bên phải thẻ vẫn là ngày đăng.

## 9. Liên hệ với phần "đã lưu"
Trạng thái "Saved ✓" so khớp theo cặp (tiêu đề, **ngày sẽ lưu**). Nên cùng một thông báo, lưu xong thì lần sau
vào trang vẫn hiện "Saved". Sự kiện đã lưu từ phiên bản cũ (theo ngày đăng) sẽ không còn được nhận là đã lưu
nếu tiêu đề có ngày khác; người dùng chỉ cần lưu lại hoặc xóa sự kiện cũ trên Calendar.

## 10. Câu TA có thể hỏi
- **Sao không nhờ API cung cấp ngày hạn?** API chỉ trả tiêu đề, link, ngày đăng. Ngày hạn chỉ có trong chữ.
- **Sao không dùng AI/NLP?** Quy tắc nhỏ dễ giải thích, dễ test và chạy tức thì; không cần thêm thư viện.
- **Có đọc sai không?** Có thể. Vì vậy có dòng ghi chú rõ và người dùng bấm lưu mới có sự kiện; không tự lưu.
- **Test thế nào?** `tests/test_deadline_logic.py` dùng chính các tiêu đề thật, cộng các ca khó
  (ngày không có thật, số phiên bản, ngày tham chiếu cũ, năm cuối năm); `tests/test_announcement_dates.py` kiểm tra nút Save.

## 11. Hạn chế đã biết
- Chưa đọc ngày dạng chỉ số kiểu `11/20` hoặc `11/1~11/20` (dễ nhầm với phân số, số hiệu).
- Chưa đọc giờ trong tiêu đề (sự kiện luôn là cả ngày).
- Chưa đọc "next Friday", "tuần sau"...
- Tiêu đề không có ngày thì vẫn dùng ngày đăng, giống trước đây.
