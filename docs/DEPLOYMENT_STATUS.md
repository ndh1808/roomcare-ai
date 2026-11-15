# Trạng thái bàn giao — cập nhật 15/11/2026

- Repository: https://github.com/ndh1808/roomcare-ai
- Web demo đã triển khai: https://roomcare-ai-ndh1808.streamlit.app/
- Hosting: Streamlit Community Cloud, Python 3.12, nhánh `main`, entrypoint `app.py`.
- Kiểm thử GitHub Actions bản MVP thành công: https://github.com/ndh1808/roomcare-ai/actions/runs/43611644402
- Chế độ hiện tại: `DEMO_MODE=true`, Gemini chưa có API key, SQLite trên máy chủ hosting.

## Dùng bản demo

Mở website, gửi một sự cố giả lập và lưu thông tin tra cứu. Tại mục **Chủ trọ**, dùng `chu-tro` / `RoomCareDemo2026!`. Có nút **Nạp dữ liệu demo** để thêm 8 phiếu mẫu, bấm lại không tạo bản sao.

Đây là tài khoản demo công khai; chỉ dùng dữ liệu giả. SQLite được chia sẻ giữa các phiên trên cùng máy chủ nhưng không bảo đảm lưu bền vững khi hosting khởi động lại, ngủ hoặc triển khai lại.

Nếu Streamlit hiện màn hình **Zzzz**, bấm **Yes, get this app back up!** và chờ ứng dụng khởi động. Bản hosting demo có thể ngủ khi không có người truy cập.

## Bật sử dụng thực tế

1. Chuẩn bị Supabase PostgreSQL theo [hướng dẫn](DEPLOYMENT.md).
2. Trong Streamlit **Manage app → Settings → Secrets**, đặt `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `DEMO_MODE="false"`.
3. Muốn Gemini phân tích văn bản và ảnh, thêm `GEMINI_API_KEY`; kiểm tra model trong `GEMINI_MODEL` còn được tài khoản hỗ trợ.
4. Lưu, khởi động lại và thử toàn bộ luồng trên hai thiết bị trước khi dùng dữ liệu thật. Không đưa mật khẩu hoặc key vào GitHub.

Supabase và Gemini thật chưa được kiểm chứng kết nối trong lần bàn giao vì chưa có thông tin truy cập. Các tests AI dùng phản hồi giả lập; fallback demo đã được kiểm thử.
