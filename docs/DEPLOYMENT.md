# Triển khai RoomCare AI

Hướng dẫn này cung cấp thao tác triển khai thực tế. Mã nguồn và file cấu hình không tự tạo tài khoản hosting, database hay website. Chỉ ghi link web sau khi dịch vụ hoàn tất và đã mở kiểm tra.

## 1. Chuẩn bị repository GitHub

Repository dự án đã được tạo tại [ndh1808/roomcare-ai](https://github.com/ndh1808/roomcare-ai). Khi mở repo, kiểm tra nhánh có `app.py`, `requirements.txt` và README trước khi triển khai. Nếu mã nguồn đã được đẩy lên, bỏ qua bước tạo mới và upload bên dưới.

Nếu chưa có repository:

1. Đăng nhập [GitHub](https://github.com/) và mở [tạo repository](https://github.com/new).
2. Đặt tên `roomcare-ai`. Chọn Public nếu muốn công khai mã nguồn đồ án, hoặc Private theo nhu cầu. Không đưa dữ liệu thật vào repo dù chọn Private.
3. Tạo repo trống, không thêm README nếu thư mục local đã có README.
4. Mở terminal **trong thư mục `roomcare-ai`**, kiểm tra `.gitignore`, rồi chạy các lệnh dưới đây. Các lệnh dùng repository đã tạo cho tài khoản `ndh1808`; nếu triển khai bằng tài khoản khác, thay URL remote tương ứng.

```bash
git init -b main
git add .
git status --short
git diff --cached --stat
git commit -m "Build RoomCare AI MVP"
git remote add origin https://github.com/ndh1808/roomcare-ai.git
git push -u origin main
```

Nếu thư mục đã được khởi tạo Git hoặc đã có remote, không chạy lại thao tác tạo; kiểm tra `git remote -v` và dùng remote hiện có. Xác thực bằng giao diện đăng nhập GitHub hoặc Git Credential Manager. Không đặt token trong lệnh, URL remote hoặc file nguồn.

Trước khi commit, danh sách file không được có `.env`, `.streamlit/secrets.toml`, database, ảnh người dùng hoặc bản sao lưu. Các file `.example` chứa placeholder được phép commit.

## 2. Tạo database dùng chung trên Supabase

1. Đăng nhập [Supabase Dashboard](https://supabase.com/dashboard), tạo project cho đồ án và lưu mật khẩu database riêng.
2. Trong project, chọn **Connect → Session pooler**. Sao chép chuỗi kết nối mà giao diện cung cấp; không tự đoán hostname theo vùng.
3. Thay mật khẩu trong chuỗi bằng mật khẩu database. Nếu có ký tự đặc biệt, percent-encode phần mật khẩu. Không dùng anon key hoặc service-role API key thay mật khẩu PostgreSQL.
4. Với RoomCare, chuỗi sử dụng driver `postgresql+psycopg://`, giữ đúng username/host/port đã sao chép, thêm `?sslmode=require` nếu chưa có cấu hình SSL. Ví dụ minh họa:

```text
postgresql+psycopg://ROLE.PROJECT_REF:ENCODED_PASSWORD@POOLER_HOST:5432/postgres?sslmode=require
```

Các chữ in hoa ở trên là placeholder, không phải thông tin của một database có thật. Session pooler phù hợp kết nối từ mạng IPv4; tham khảo [tài liệu kết nối Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres). Nếu cần xác minh chứng chỉ đầy đủ, cấu hình `sslmode=verify-full` và chứng chỉ gốc theo tài liệu đó.

Ứng dụng kết nối PostgreSQL từ máy chủ, tự tạo schema riêng `roomcare` và các bảng `rooms`, `tickets`, `ticket_events`, `login_attempts` khi khởi động. Tài khoản kết nối cần quyền tạo và quản lý schema/bảng vì bước khởi tạo chạy lại khi ứng dụng khởi động. **Không thêm schema `roomcare` vào Exposed schemas của Supabase Data API.** Dùng project riêng cho MVP, không ghép vào database có dữ liệu quan trọng. Đọc thêm phần bảo vệ database bên dưới.

## 3. Tạo thông tin chủ trọ

Trong môi trường Python đã cài thư viện, chạy:

```bash
python scripts/hash_password.py
```

Nhập mật khẩu riêng khi được hỏi. Sao chép chuỗi băm mà công cụ in ra vào `ADMIN_PASSWORD_HASH`. Không đưa mật khẩu gốc vào mã nguồn, tài liệu, ảnh chụp hoặc GitHub. Dùng `DEMO_MODE=false` khi đưa dữ liệu thật lên mạng.

Nếu muốn Gemini thật, tạo API key trong [Google AI Studio](https://aistudio.google.com/apikey) bằng tài khoản của bạn, kiểm tra hạn mức phù hợp và đặt vào `GEMINI_API_KEY`. Nếu để trống, ứng dụng dùng phân tích demo có nhãn rõ ràng.

## 4. Streamlit Community Cloud

1. Đăng nhập [Streamlit Community Cloud](https://share.streamlit.io/) và liên kết GitHub khi dịch vụ yêu cầu.
2. Chọn **Create app**, chọn repository `roomcare-ai`, nhánh chứa bản hoàn chỉnh (ví dụ `main`) và **Main file path: `app.py`**.
3. Chọn **Advanced settings**, chọn **Python 3.12** và mở phần Secrets.
4. Sao chép nội dung `.streamlit/secrets.toml.example`, thay toàn bộ placeholder bằng giá trị riêng. Đặt tối thiểu `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `DEMO_MODE=false`. `GEMINI_API_KEY` là tùy chọn.
5. Chọn **Save**, rồi **Deploy**. Chờ build hoàn tất, theo dõi log trong giao diện dịch vụ.
6. Mở URL `streamlit.app` do dịch vụ trả về và thực hiện các kiểm tra ở phần 6. Ghi lại URL đó cho nhóm; không tự đoán subdomain.

File secrets thật không được commit; Community Cloud có giao diện lưu secrets riêng. Các thao tác và nơi chọn Python được mô tả trong [hướng dẫn deploy chính thức](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) và [hướng dẫn secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

Khi sửa mã nguồn, commit/push lên nhánh đã chọn. Khi sửa key hoặc mật khẩu, cập nhật Secrets của ứng dụng rồi khởi động lại nếu cần. Không đổi database sang SQLite để che lỗi kết nối PostgreSQL: kiểm tra đúng host, user, mật khẩu, SSL và trạng thái project.

## 5. Lựa chọn khác: Render hoặc Docker

### Render

Repo có `render.yaml` cho một web service và không tự cấp database trả phí. Đăng nhập [Render Dashboard](https://dashboard.render.com/), tạo Blueprint từ repo, kiểm tra lựa chọn gói đang có và điền các giá trị môi trường còn thiếu. Nếu không dùng Blueprint, tạo Python Web Service với:

```text
Build command: pip install -r requirements.txt
Start command: python -m streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT
Health check: /_stcore/health
```

Repo có `.python-version` là `3.12` để Render chọn bản vá mới nhất tương ứng, theo [hướng dẫn phiên bản Python của Render](https://render.com/docs/python-version). Dùng PostgreSQL bên ngoài. Trước khi tạo dịch vụ, tự kiểm tra gói và chi phí hiển thị trong tài khoản. Không dùng ổ đĩa tạm của hosting để lưu dữ liệu thật.

### Docker trên máy hoặc máy chủ riêng

```bash
docker build -t roomcare-ai .
docker run --rm -p 8501:8501 --env-file .env roomcare-ai
```

File `.env` phải đặt cấu hình database và mật khẩu phù hợp. Với Docker, mặc định `DEMO_MODE=false`; `.env` có thể ghi đè biến này. Nếu chạy demo SQLite trong container, dữ liệu sẽ mất khi xóa container trừ khi cấu hình volume. Cách đơn giản để triển khai nhiều thiết bị là dùng PostgreSQL dùng chung. Docker không tự cung cấp tên miền, HTTPS hoặc hosting.

## 6. Xác nhận sau triển khai

- Mở URL bằng điện thoại hoặc cửa sổ trình duyệt mới; giao diện không báo lỗi cấu hình.
- Trình duyệt A tạo phiếu thử với ảnh và lưu mã tra cứu.
- Trình duyệt B đăng nhập chủ trọ; nhìn thấy đúng phiếu vừa tạo, đổi sang **Đang xử lý** và ghi chú.
- Trình duyệt A tra cứu, thấy cập nhật sau khi làm mới.
- Nhập mã tra cứu sai: không thấy nội dung phiếu.
- Đăng xuất: dashboard và ảnh không còn truy cập được qua giao diện quản trị.
- Khởi động lại dịch vụ; phiếu vẫn tồn tại trong PostgreSQL.
- Nếu có API key, thử một lượt phân tích và xác nhận nhãn nguồn Gemini. Nếu chưa có key, thấy nhãn demo.

Chỉ sau các bước này mới báo “đã triển khai và chạy thử”. Kiểm tra tự động local không thay thế kiểm tra database/hosting thật.

## 7. Bảo vệ dữ liệu và giới hạn

Một lần triển khai phục vụ một nhà trọ. Database credential chỉ nằm trong secrets phía máy chủ. Mỗi phiếu dùng mã tra cứu ngẫu nhiên; không phát hành danh sách mã tra cứu qua API công khai.

Supabase Data API và kết nối SQL trực tiếp là hai cơ chế khác nhau. RLS không thay thế đăng nhập chủ trọ trong ứng dụng; role chủ sở hữu database có thể vượt RLS. Trước khi sử dụng dữ liệu thật, kiểm tra schema của RoomCare không nằm trong danh sách schema công khai của Data API, không cấp quyền truy cập cho `anon`/`authenticated`, và dùng role máy chủ có quyền tối thiểu phù hợp. Nếu thay đổi sang schema công khai hoặc thêm Data API, cần thiết kế RLS và kiểm thử quyền trước. Xem [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).

Chủ trọ cần thống nhất thời hạn lưu ảnh/phiếu, phương án xóa dữ liệu và sao lưu. Bản MVP chưa bao gồm công cụ phục hồi backup hoặc quản trị nhiều nhà trọ.
