# Kịch bản demo RoomCare AI — khoảng 5 phút

## Trước buổi demo

- Chạy ứng dụng local hoặc mở URL đã triển khai thực tế.
- Chuẩn bị hai trình duyệt/cửa sổ: một cho sinh viên, một cho chủ trọ.
- Dùng dữ liệu giả và ảnh đồ vật không chứa thông tin cá nhân.
- Nếu không có API key, nói rõ đây là chế độ demo quy tắc để trình diễn luồng. Không dùng kết quả đó làm minh chứng Gemini đã phân tích ảnh.
- Chạy `python scripts/seed_demo.py` với database demo để có phiếu minh họa. Không seed dữ liệu giả vào hệ thống đang dùng thật.

## 1. Sinh viên báo sự cố — 90 giây

Chọn phần báo sự cố, nhập phòng **203** và mô tả:

> Điều hòa phòng em bật lên nhưng không lạnh. Đèn trên máy nhấp nháy từ tối qua, hôm trước vẫn dùng bình thường.

Tải ảnh điều hòa nếu có. Thực hiện phân tích, đọc nhóm sự cố và tóm tắt. Nêu rõ AI chỉ hỗ trợ tiếp nhận và không kết luận chắc chắn bộ phận bị hỏng. Xem câu hỏi bổ sung rồi gửi phiếu.

Lưu **mã phiếu** và **mã tra cứu** do ứng dụng cấp. Mã thật được tạo mỗi lần gửi; không dùng một mã cố định từ tài liệu.

## 2. Chủ trọ tiếp nhận — 90 giây

Ở trình duyệt thứ hai, đăng nhập chủ trọ. Với demo local, tài khoản là `chu-tro` / `RoomCareDemo2026!`. Với website thật, dùng tài khoản riêng đã cấu hình.

Mở phiếu mới, đối chiếu ảnh và mô tả gốc. Đổi trạng thái sang **Đang xử lý**, thêm ghi chú:

> Đã tiếp nhận. Chủ trọ sẽ trao đổi thời gian kiểm tra với bạn.

Lưu thay đổi. Trình diễn bộ lọc theo phòng/trạng thái và thống kê nhóm sự cố. Tạo báo cáo tổng hợp; chỉ ra nhãn nguồn Gemini hoặc demo trên kết quả.

## 3. Sinh viên theo dõi — 45 giây

Quay lại trình duyệt sinh viên. Nhập mã phiếu và mã tra cứu đã lưu. Sau khi tra cứu/làm mới, trạng thái và ghi chú phải khớp với cập nhật của chủ trọ.

Thử một mã tra cứu sai: ứng dụng không hiển thị nội dung phiếu. Giải thích mã tra cứu là thông tin riêng của người gửi.

## 4. Tình huống nguy hiểm — 45 giây

Nhập mô tả giả:

> Ổ cắm trong phòng có khói và mùi khét.

Kết quả phải nâng mức khẩn cấp và nhắc tránh xa nguy hiểm, liên hệ người hỗ trợ ngay. Không cần thực hiện hoặc mô phỏng nguy hiểm ngoài đời. Không nói hệ thống đã gọi cứu hộ hoặc gửi thông báo nếu không có chức năng đó.

## 5. Kết luận demo — 30 giây

Trình bày luồng hoàn chỉnh: sinh viên gửi → hệ thống chuẩn hóa → chủ trọ xử lý → sinh viên tra cứu. Nêu công nghệ đang dùng và hai giới hạn chính: một nhà trọ cho mỗi lần triển khai; AI cần người kiểm tra lại.

Nếu mất mạng, dùng bản local với SQLite và chế độ demo. Ghi rõ việc chuyển sang demo; không trình bày nó như kết quả AI trực tuyến.
