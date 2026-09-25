# Hướng Dẫn Deploy Bot Lên AlwaysData Miễn Phí 100%

AlwaysData là một dịch vụ tuyệt vời cho bot nhỏ vì nó **miễn phí vĩnh viễn**, cho phép lưu dữ liệu cố định (ổ cứng 100MB) và hỗ trợ chạy ngầm 24/7.
*Lưu ý quan trọng: Bạn chỉ có 100MB dung lượng, nên phải làm đúng từng bước dưới đây để tiết kiệm bộ nhớ, nếu không sẽ bị đầy ổ đĩa.*

---

## Bước 1: Đăng ký tài khoản
1. Truy cập [alwaysdata.com](https://www.alwaysdata.com/) và tạo 1 tài khoản (Profile).
2. Khi đăng ký thành công, họ sẽ cấp cho bạn một tên tài khoản, ví dụ: `tencuaban` (tài khoản này cũng là tên miền của bạn luôn).
3. Truy cập vào giao diện quản lý (Dashboard).

---

## Bước 2: Bật SSH và tải code lên
1. Trong Dashboard, nhìn thanh menu bên trái, chọn **SSH / Web terminal** -> click vào nút **Web terminal** (Đây là cái màn hình đen để gõ lệnh).
2. Khi giao diện terminal mở ra, bạn clone code từ Github về (bạn phải đẩy code lên Github trước nha):
   ```bash
   git clone https://github.com/ten-cua-ban/ten-repo-cua-ban.git bot_project
   ```
   *(Đổi link github thành link kho code của bạn).*
3. Di chuyển vào thư mục code:
   ```bash
   cd bot_project
   ```
4. **Cực kỳ quan trọng:** Bạn cần tạo file `.env` và `team.yaml` trên này (vì Github không chứa file `.env` của bạn). Dùng lệnh `nano .env` để tạo và dán nội dung vào, sau đó bấm `Ctrl + X`, nhấn `Y`, nhấn `Enter` để lưu. Tương tự với file `team.yaml`.

---

## Bước 3: Cài đặt thư viện (Chiến thuật siêu tiết kiệm dung lượng)
Vì chỉ có 100MB, chúng ta tuyệt đối không được tải file dư thừa!
1. Tạo môi trường ảo (venv):
   ```bash
   python3 -m venv venv
   ```
2. Kích hoạt môi trường ảo:
   ```bash
   source venv/bin/activate
   ```
3. Cài thư viện với cờ `--no-cache-dir` (Cờ này giúp cài xong là xóa rác ngay, không lưu cache làm tốn 100MB):
   ```bash
   pip install --no-cache-dir -r requirements.txt
   ```
*(Ngồi đợi nó cài xong, hy vọng là không vượt quá 100MB!)*

---

## Bước 4: Thiết lập "User Program" để bot chạy ngầm vĩnh viễn
Điểm ăn tiền nhất của AlwaysData là tính năng này. Nó sẽ tự động kích hoạt bot của bạn lên, nếu bot sập nó tự động gọi dậy!
1. Quay lại trang **Dashboard** của AlwaysData (giao diện web).
2. Bên thanh menu trái, chọn **Advanced** -> **User programs**.
3. Bấm **Add a program**.
4. Điền các thông tin sau:
   - **Name:** SEE_Notion_Bot
   - **Command:** `cd $HOME/bot_project && source venv/bin/activate && python -m app.main`
   - **Working directory:** Cứ để trống.
5. Bấm **Submit** (Lưu lại).

🪄 **BÙM! HOÀN TẤT!** 
AlwaysData sẽ lập tức chạy cái Command kia ở dưới nền (background). Bạn có thể tắt máy tính đi ngủ, con bot của bạn bây giờ đã có một "ngôi nhà" nhỏ 100MB trên internet và sẽ chạy 24/7 mãi mãi!
