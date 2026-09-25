# Kế hoạch Treo Server Online (Deploy) Đơn Giản Nhất

Dự án của bạn là một sự kết hợp giữa **Discord Bot** và **Web API**, đồng thời có sử dụng **Cơ sở dữ liệu SQLite** (file `data/app.db`).
Do có dùng SQLite (file vật lý lưu trên ổ cứng), bạn **bắt buộc** phải dùng những dịch vụ cho phép lưu trữ dữ liệu cố định (Persistent Storage). Nếu dùng các dịch vụ miễn phí thông thường (như Render free, Heroku free), mỗi khi server khởi động lại là data của bạn sẽ bị xóa sạch!

Dưới đây là 2 phương án ĐƠN GIẢN NHẤT dành cho bạn:

---

## Phương án 1: Dùng Railway.app (Khuyên dùng - Dễ nhất quả đất)
Railway là nền tảng dễ dùng nhất hiện nay, chỉ cần biết dùng Github là làm được. Chi phí rất rẻ (khoảng 1 - 2 đô / tháng cho bot nhỏ).

**Các bước thực hiện:**
1. **Đưa code lên Github:** Bạn đẩy toàn bộ thư mục code (nhớ loại bỏ file `.env`, `data/app.db` bằng file `.gitignore`) lên một repository Private (Kín) trên Github.
2. **Đăng nhập Railway:** Vào trang [railway.app](https://railway.app/), đăng nhập bằng tài khoản Github.
3. **Tạo Project mới:** Bấm `New Project` -> `Deploy from GitHub repo` -> Chọn repo của bạn.
4. **Cài đặt Môi trường (.env):** Trong giao diện Railway, vào tab **Variables**, dán toàn bộ nội dung của file `.env` vào (chữ thô).
5. **Thêm ổ cứng (Giữ lại data SQLite):** Vào cài đặt dịch vụ, thêm một **Volume** (Ổ đĩa) có đường dẫn là `/app/data` (để bảo vệ thư mục data không bị xóa khi bot update).
6. **Bấm Deploy:** Railway sẽ tự động đọc code Python, tự cài thư viện và chạy file `main.py` của bạn liên tục 24/7. Mỗi khi bạn sửa code và Push lên Github, nó tự động cập nhật!

---

## Phương án 2: Dùng VPS Miễn Phí của AWS hoặc Oracle (Miễn phí 100%, thủ công một chút)
Nếu bạn không muốn tốn đồng nào, hãy đăng ký một máy chủ ảo (VPS) miễn phí của Amazon (AWS EC2 - Free 1 năm) hoặc Oracle Cloud (Free trọn đời). 
Nó giống như việc bạn có 1 cái máy tính cắm điện chạy 24/24 trên mây, và bạn ném code lên đó chạy.

**Các bước thực hiện (Sau khi đã có VPS chạy Ubuntu):**
1. Mở Terminal (Command Prompt) kết nối vào VPS của bạn qua SSH.
2. Clone code từ Github về VPS.
3. Cài đặt Python 3, tạo môi trường ảo (venv) và cài thư viện y hệt như bạn đang làm trên máy tính.
4. Kéo file `.env`, `team.yaml` và ném vào VPS.
5. **Tuyệt chiêu treo 24/7 (Dùng `PM2` hoặc `Screen`):**
   - Thay vì gõ lệnh `python -m app.main` thông thường (tắt máy tính là bot sập).
   - Bạn dùng công cụ `screen`: Gõ `screen -S bot` (để tạo 1 cửa sổ ẩn).
   - Trong cửa sổ đó, bạn chạy lệnh `python -m app.main`.
   - Xong bạn bấm tổ hợp phím `Ctrl + A` rồi bấm phím `D`.
   - 🪄 *Xong! Cửa sổ đó đã được giấu đi và chạy ngầm. Bạn có thể tắt máy tính đi ngủ, bot vẫn sẽ online vĩnh viễn trên VPS.*

---

### Tóm lại:
- Nếu muốn **"Bấm 3 nút là xong, code up Github tự chạy, không phải gõ lệnh"**: Hãy chọn **Railway** (Tốn 1 ly cafe/tháng).
- Nếu muốn **"Miễn phí hoàn toàn, cảm giác giống hacker gõ gõ xíu"**: Hãy đăng ký **AWS EC2 / Oracle Cloud** và dùng lệnh `screen`.
