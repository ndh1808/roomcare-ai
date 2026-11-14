# RoomCare AI

Ứng dụng web tiếng Việt giúp sinh viên báo sự cố phòng trọ và chủ trọ theo dõi việc xử lý. MVP dùng **Python + Streamlit**, **Gemini** và **SQLite / PostgreSQL (Supabase)**.

Repository GitHub: [ndh1808/roomcare-ai](https://github.com/ndh1808/roomcare-ai). Xem [hướng dẫn triển khai](docs/DEPLOYMENT.md) để tạo website từ repository này; một link repository không đồng nghĩa ứng dụng đã được triển khai.

## Chức năng

- Sinh viên nhập phòng, mô tả và ảnh; xem kết quả phân loại, mức ưu tiên, tóm tắt và câu hỏi bổ sung.
- Tạo phiếu có mã riêng và mã tra cứu ngẫu nhiên; xem trạng thái cùng lịch sử xử lý.
- Chủ trọ đăng nhập để xem, lọc, cập nhật phiếu và ghi chú.
- Dashboard tổng hợp số lượng theo loại sự cố, trạng thái và ưu tiên; tạo báo cáo ngắn bằng Gemini hoặc chế độ demo.
- Khi chưa có API key hoặc Gemini gặp lỗi, ứng dụng vẫn chạy với kết quả demo **được ghi rõ**. Demo phân loại bằng quy tắc từ mô tả, không tuyên bố đã hiểu ảnh.
- Có dữ liệu minh họa, kiểm thử tự động, cấu hình triển khai và hướng dẫn cho nhóm mới học lập trình.

Đã kiểm tra 84 tests trên Python 3.12, gồm luồng gửi phiếu → xác thực chủ trọ → cập nhật → tra cứu ở phiên mới. Xem [kết quả và giới hạn kiểm thử](docs/TESTING.md). Bộ 48 tình huống để thử quy tắc demo chạy bằng `python scripts/evaluate_demo.py`; chưa đo chất lượng Gemini thật khi không có key.

## Chạy nhanh trên máy cá nhân

Dùng Python 3.12. Mở terminal trong thư mục chứa `app.py`.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python scripts/seed_demo.py
.\.venv\Scripts\python -m streamlit run app.py
```

Nếu máy chỉ có một bản Python tương thích, thay `py -3.12` bằng `python`. Không cần kích hoạt môi trường ảo khi dùng đường dẫn Python như trên.

**macOS / Linux**

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
.venv/bin/python scripts/seed_demo.py
.venv/bin/python -m streamlit run app.py
```

Mở địa chỉ mà Streamlit in ra, thông thường là [http://localhost:8501](http://localhost:8501). Đây là địa chỉ chạy trên máy cá nhân, không phải website đã được xuất bản lên Internet.

Trong chế độ demo, tài khoản chủ trọ là:

| Trường | Giá trị |
| --- | --- |
| Tên đăng nhập | `chu-tro` |
| Mật khẩu | `RoomCareDemo2026!` |

Tài khoản trên chỉ dành cho dữ liệu giả khi `DEMO_MODE=true`. Khi dùng dữ liệu thật, chuyển sang `DEMO_MODE=false` và tạo mật khẩu riêng. Tạo phiếu mới để thử tra cứu; giữ lại cả mã phiếu lẫn mã tra cứu được cấp.

## Cấu hình

Sao chép `.env.example` thành `.env` khi chạy local. Khi dùng Streamlit Community Cloud, điền cấu hình vào **Advanced settings → Secrets**, theo mẫu `.streamlit/secrets.toml.example`. Không đẩy file chứa giá trị thật lên GitHub.

| Biến | Ý nghĩa |
| --- | --- |
| `DEMO_MODE` | `true` cho dữ liệu giả; `false` để bắt buộc mật khẩu quản trị riêng và PostgreSQL |
| `BUILDING_NAME` | Tên nhà trọ hiển thị |
| `DATABASE_URL` | SQLite trên máy; PostgreSQL dùng chung khi triển khai |
| `ADMIN_USERNAME` | Tên đăng nhập chủ trọ |
| `ADMIN_PASSWORD_HASH` | Mật khẩu đã băm, tạo bằng `python scripts/hash_password.py` |
| `GEMINI_API_KEY` | Để trống nếu muốn dùng phân tích demo |
| `GEMINI_MODEL` | Mặc định `gemini-2.5-flash`; có thể đổi theo model mà tài khoản được dùng |

Ảnh được kiểm tra (tối đa 5 MB, 12 megapixel), bỏ metadata, chuyển thành JPEG với cạnh dài tối đa 1.600 pixel và lưu cùng cơ sở dữ liệu để các thiết bị nhìn thấy cùng dữ liệu. Mã tra cứu được lưu dạng băm; người có cả mã phiếu và mã tra cứu có thể xem phiếu đó. Không chia sẻ mã tra cứu công khai.

## Kiến trúc

```text
Điện thoại / trình duyệt
        ↓
Streamlit: báo lỗi · tra cứu · đăng nhập · dashboard
        ├── roomcare/ai.py → Gemini (nếu có key) / demo
        ├── roomcare/images.py → kiểm tra và chuẩn hóa ảnh
        ├── roomcare/security.py → xác thực chủ trọ
        └── roomcare/db.py → SQLAlchemy → SQLite / PostgreSQL
```

Gemini và database chạy qua Python phía máy chủ. Trình duyệt không nhận API key hay chuỗi kết nối database. Các quy tắc nhận diện dấu hiệu nguy hiểm có thể nâng mức khẩn cấp dù AI trả ưu tiên thấp. AI không thay thế người kiểm tra thực tế.

## Kiểm tra

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

Xem [hướng dẫn kiểm thử](docs/TESTING.md) để thử luồng thực tế và đánh giá chất lượng AI. Kiểm thử Gemini giả lập giúp kiểm tra hành vi tích hợp nhưng không chứng minh chất lượng của model thật.

## Đưa lên GitHub và triển khai

Thực hiện theo [hướng dẫn triển khai](docs/DEPLOYMENT.md). Cấu hình khuyến nghị là **Streamlit Community Cloud + Supabase PostgreSQL**. SQLite phù hợp chạy local; file trên máy chủ tạm thời có thể mất khi ứng dụng khởi động lại hoặc được triển khai lại.

Repo có `Dockerfile` và `render.yaml` nếu muốn triển khai sang môi trường khác. Các file này là cấu hình sẵn, **không có nghĩa ứng dụng đã được deploy**. Chỉ xem là triển khai thành công khi dịch vụ trả URL và đã kiểm tra luồng trên URL đó.

## Phạm vi MVP

Phiên bản này phục vụ **một chủ trọ / một nhà trọ trong mỗi lần triển khai**. Chưa có đa tổ chức, tài khoản riêng cho từng sinh viên, gửi email/Zalo tự động, phân công thợ, thanh toán hoặc quản lý hợp đồng. Sinh viên tự mở trang tra cứu; ứng dụng không gửi thông báo chủ động.

Chỉ tải ảnh sự cố cần thiết, tránh khuôn mặt, giấy tờ và tài sản cá nhân. Khi chọn dùng Gemini, mô tả và ảnh cần thiết được gửi tới dịch vụ Google để phân tích. Chế độ demo không gửi dữ liệu tới Gemini. Những trường hợp có khói, cháy, mùi gas hoặc điện giật cần rời khỏi nơi nguy hiểm và liên hệ người hỗ trợ phù hợp ngay; không chờ phiếu được xử lý và không tự sửa thiết bị nguy hiểm theo suy đoán của AI.

MVP chưa có quy trình xóa dữ liệu theo yêu cầu, chống spam ở mức vận hành lớn hoặc giám sát sản xuất. Trước khi dùng rộng rãi với dữ liệu thật cần bổ sung các phần này, kiểm tra quyền database, sao lưu và thống nhất thời hạn lưu dữ liệu.

## Demo và phân công nhóm

[Kịch bản demo 5 phút](docs/DEMO_SCRIPT.md) có tình huống thường gặp, tình huống khẩn cấp và cập nhật từ hai trình duyệt.

| Thành viên | Phần phụ trách |
| --- | --- |
| 1 | Prompt, Gemini, bộ dữ liệu đánh giá |
| 2 | Giao diện sinh viên, tra cứu, trải nghiệm điện thoại |
| 3 | Database, xác thực, dashboard và triển khai |
| 4 | Kiểm thử, khảo sát người dùng, tài liệu và thuyết trình |

Trong 3–4 tuần, nhóm có thể dành tuần 1 để hiểu luồng và khảo sát; tuần 2 tùy chỉnh giao diện, phòng và prompt; tuần 3 thử người dùng và triển khai; tuần 4 đo kết quả, sửa lỗi và hoàn thiện báo cáo. Không dùng số liệu mục tiêu làm số liệu đã đạt.
