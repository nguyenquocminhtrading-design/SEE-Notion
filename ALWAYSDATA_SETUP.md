# Hướng Dẫn Deploy Bot Lên AlwaysData Miễn Phí 100%

AlwaysData là một dịch vụ tuyệt vời cho bot nhỏ vì nó **miễn phí vĩnh viễn**, cho phép lưu dữ liệu cố định (ổ cứng 100MB) và hỗ trợ chạy ngầm 24/7.
*Lưu ý quan trọng: Bạn chỉ có 100MB dung lượng, nên phải làm đúng từng bước dưới đây để tiết kiệm bộ nhớ, nếu không sẽ bị đầy ổ đĩa.*

---

## Bước 1: Đăng ký tài khoản và User SSH
1. Tạo tài khoản AlwaysData và tạo User SSH thành công (tên user là `seecodenotion`).

---

## Bước 2: Kết nối SSH và Tải Code
1. Mở CMD (Command Prompt) trên máy tính Windows của bạn và kết nối vào máy chủ bằng lệnh:
   ```bash
   ssh seecodenotion@ssh-seecodenotion.alwaysdata.net
   ```
2. Nhập mật khẩu SSH (lúc nhập sẽ không hiện chữ, cứ gõ rồi Enter).
3. Đăng nhập thành công, bạn di chuyển vào thư mục code mà bạn vừa clone về:
   ```bash
   cd /home/seecodenotion/SEE-Notion
   ```
4. **Cực kỳ quan trọng:** Bạn cần tạo file `.env` và `team.yaml` trên này (vì Github không cho phép đẩy file `.env` lên). 
   Dùng lệnh `nano .env` để tạo và dán nội dung `.env` từ máy tính vào, sau đó bấm `Ctrl + X`, nhấn `Y`, nhấn `Enter` để lưu. 
   Làm tương tự với file `team.yaml`: gõ `nano team.yaml`.

---

## Bước 3: Cài đặt thư viện (Chiến thuật siêu tiết kiệm dung lượng)
Đảm bảo bạn vẫn đang ở trong thư mục `/home/seecodenotion/SEE-Notion`. Hãy chạy lần lượt 3 lệnh sau:

1. Tạo môi trường ảo (venv):
   ```bash
   python3 -m venv venv
   ```
2. Kích hoạt môi trường ảo:
   ```bash
   source venv/bin/activate
   ```
3. Cài thư viện với cờ `--no-cache-dir` (Cờ này giúp cài xong là xóa rác ngay, không lưu cache làm tốn 100MB ổ cứng):
   ```bash
   pip install --no-cache-dir -r requirements.txt
   ```
*(Ngồi đợi nó cài xong, hy vọng là không vượt quá 100MB!)*

---

## Bước 4: Thiết lập "Services" để bot chạy ngầm vĩnh viễn
Điểm ăn tiền nhất của AlwaysData là tính năng này. Nếu bot sập, máy chủ sẽ tự động gọi nó dậy!

1. Quay lại trang **Dashboard** của AlwaysData (trên trình duyệt web).
2. Ở thanh menu bên trái, tìm mục **Advanced** -> chọn **Services**.
3. Bấm nút **Add a service** (Thêm dịch vụ).
4. Điền chính xác các thông tin sau:
   - **Name:** `SEE_Notion_Bot` (Tên gì cũng được)
   - **Working directory:** `/home/seecodenotion/SEE-Notion`
   - **Command:** `/home/seecodenotion/SEE-Notion/venv/bin/python -m app.main`
   *(Lưu ý: Không dùng lệnh `cd` trong Command vì Alwaysdata chạy qua `exec` trực tiếp, không hỗ trợ shell built-in `cd`)*
5. Bấm **Submit** (Lưu lại).

🪄 **BÙM! HOÀN TẤT!** 
AlwaysData sẽ lập tức chạy cái câu lệnh kia ở dưới nền (background). Bạn có thể đóng CMD, tắt máy tính đi ngủ, con bot của bạn bây giờ đã chạy 24/7 mãi mãi!
