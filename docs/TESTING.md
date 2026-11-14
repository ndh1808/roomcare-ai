# Kiểm thử và đánh giá

## Kết quả kiểm tra bản MVP — 14/11/2026

- 84 kiểm thử tự động đạt trên Python 3.12.14; gồm backend, xác thực, ảnh, Gemini giả lập và luồng giao diện Streamlit.
- Giao diện đã được kiểm tra ở chiều rộng 390 px và màn hình desktop.
- Chưa gọi Gemini thật hoặc kết nối Supabase thật vì chưa cấu hình thông tin truy cập.
- Bộ `data/evaluation_cases.json` có 48 tình huống tiếng Việt giả lập. Chạy `python scripts/evaluate_demo.py` để tính lại kết quả demo: phân loại đúng 46/48, ưu tiên đúng 44/48, 9 ca nguy hiểm được nhận diện, 1 cảnh báo nhầm, 0 ca bỏ sót trong tập này.
- Tập trên đã dùng để phát triển quy tắc, **không phải tập kiểm tra độc lập và không phải độ chính xác Gemini**. Nhóm cần bổ sung ca độc lập và ảnh thực tế được phép sử dụng trước khi báo cáo chất lượng GenAI.

## Chạy kiểm thử tự động

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

Tests dùng dữ liệu tạm và Gemini giả lập, không cần API key thật. GitHub Actions chạy kiểm tra trên Python 3.12 khi push hoặc tạo pull request. Kết quả của từng lần chạy cần lấy từ terminal hoặc Actions; tài liệu này không tự khẳng định mọi môi trường đã được kiểm thử.

## Các hành vi cần kiểm tra

| Nhóm | Kết quả mong đợi |
| --- | --- |
| Tạo phiếu | Mã riêng, trạng thái ban đầu, thông tin đúng với đầu vào |
| Tra cứu | Chỉ cặp mã phiếu + mã tra cứu đúng trả nội dung |
| Lưu trữ | Phiếu tồn tại sau khi khởi động lại ứng dụng |
| Cập nhật | Trạng thái và ghi chú thay đổi, có lịch sử |
| Xác thực | Sai mật khẩu không vào dashboard, đăng xuất chặn truy cập |
| Giới hạn đăng nhập | Nhiều lần sai liên tiếp bị giới hạn tạm thời |
| Ảnh | Ảnh hợp lệ được chuẩn hóa; file giả/ảnh vượt giới hạn bị từ chối |
| Gemini | JSON hợp lệ được dùng; timeout/lỗi/schema sai chuyển sang demo có nhãn |
| Khẩn cấp | Dấu hiệu nguy hiểm không bị AI hạ xuống ưu tiên thấp |
| Báo cáo | Số liệu dựa trên phiếu thực tế; không bịa lịch sửa chữa |
| Hai thiết bị | Sinh viên gửi trên A, chủ trọ thấy và cập nhật trên B |
| Điện thoại | Form, nút và bảng đủ đọc; không cần cuộn ngang để gửi phiếu |

Không dùng hình ảnh hoặc dữ liệu riêng tư thật trong test. Với PostgreSQL, dùng database kiểm thử riêng; không xóa bảng hay reset database đang sử dụng.

## Kiểm tra thủ công trước bảo vệ

1. Làm theo [kịch bản demo](DEMO_SCRIPT.md) bằng hai trình duyệt.
2. Thử mô tả trống, chỉ có khoảng trắng, mô tả quá dài, phòng trống và file sai định dạng.
3. Tra cứu mã sai, đăng nhập sai, đăng xuất rồi quay lại dashboard.
4. Thử Gemini không có key, key không hợp lệ và key hợp lệ nếu nhóm có tài khoản.
5. Kiểm tra cùng phiếu trước và sau khi dịch vụ khởi động lại.
6. Xác nhận repo không có secrets hoặc database thật.

## Đánh giá GenAI cho báo cáo môn học

Tạo ít nhất **40 tình huống độc lập** có nhãn do nhóm thống nhất trước, phân bố trên sáu nhóm: Điện, Nước, Điều hòa, Internet, Nội thất và Khác. Thêm trường hợp mô tả thiếu thông tin, viết không dấu, từ ngữ đời thường và dấu hiệu nguy hiểm. Không dùng nguyên bộ dữ liệu đánh giá để chỉnh prompt rồi báo đó là kết quả kiểm tra độc lập.

Với mỗi tình huống, ghi mô tả, nhãn đúng, ưu tiên mong đợi, có/không nguy hiểm, nhãn AI, nguồn Gemini/demo, thời gian xử lý và ghi chú người chấm. Chấm theo cùng một tiêu chí cho cả nhóm.

Các phép đo đề xuất:

- **Độ chính xác phân loại:** số nhãn đúng / tổng tình huống; kèm bảng nhầm lẫn giữa nhóm.
- **Khả năng nhận diện nguy hiểm:** số ca nguy hiểm được đánh dấu / tổng ca nguy hiểm; báo riêng cảnh báo nhầm.
- **Multimodal:** với cùng tình huống, so sánh chỉ văn bản và văn bản + ảnh khi dùng Gemini thật.
- **Tính hữu ích:** cho người thử làm cùng nhiệm vụ có/không AI; đo thời gian, mức đầy đủ thông tin và nhận xét.
- **Độ ổn định:** ghi số lần lỗi API, fallback, JSON sai và thời gian đáp ứng; tách demo khỏi kết quả Gemini.

Mốc 80% độ chính xác và không bỏ sót ca nguy hiểm trong bộ test là **mục tiêu**, không phải thành tích đã xác nhận. Không suy rộng “an toàn tuyệt đối” từ một tập tình huống nhỏ. AI vẫn có thể hiểu nhầm ảnh hoặc mô tả ngoài bộ test.
