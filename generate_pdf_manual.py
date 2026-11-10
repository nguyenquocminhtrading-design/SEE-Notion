"""Script build PDF Sổ tay Hướng dẫn Discord Bot bằng ReportLab với Palette màu:
- Primary: Deep Blue #0F2B48
- Secondary: Slate Blue #2A4D69 / Steel #5C768D
- Neutral Light: Soft Grey-Blue #EAF0F6 / #F4F7FA
- Neutral Dark / Text: #1E293B
- Pure White: #FFFFFF
- Accent: Emerald #10B981, Amber #F59E0B
Hỗ trợ đầy đủ Tiếng Việt Unicode qua Windows Arial TTF.
"""

import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 1. Đăng ký Font tiếng Việt Arial từ Windows
FONT_REGULAR = "Arial"
FONT_BOLD = "Arial-Bold"
FONT_ITALIC = "Arial-Italic"
FONT_BOLD_ITALIC = "Arial-BoldItalic"

font_dir = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(font_dir / "arial.ttf")))
pdfmetrics.registerFont(TTFont(FONT_BOLD, str(font_dir / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont(FONT_ITALIC, str(font_dir / "ariali.ttf")))
pdfmetrics.registerFont(TTFont(FONT_BOLD_ITALIC, str(font_dir / "arialbi.ttf")))

# 2. Định nghĩa Palette màu sắc (Clean Modern Palette)
COLOR_PRIMARY = colors.HexColor("#0F2B48")      # Xanh đậm chủ đạo
COLOR_SECONDARY = colors.HexColor("#2A4D69")    # Xanh slate
COLOR_STEEL = colors.HexColor("#5C768D")        # Xám xanh trung tính
COLOR_BG_LIGHT = colors.HexColor("#F4F7FA")     # Nền xám xanh nhạt
COLOR_CARD_BG = colors.HexColor("#EAF0F6")      # Nền card
COLOR_TEXT = colors.HexColor("#1E293B")         # Chữ xám than đậm
COLOR_TEXT_MUTED = colors.HexColor("#64748B")   # Chữ phụ
COLOR_WHITE = colors.HexColor("#FFFFFF")        # Trắng tinh
COLOR_ACCENT = colors.HexColor("#10B981")       # Xanh ngọc
COLOR_WARNING = colors.HexColor("#F59E0B")      # Vàng hổ phách
COLOR_BORDER = colors.HexColor("#CBD5E1")       # Viền mảnh


class NumberedCanvas(canvas.Canvas):
    """Canvas 2-pass để vẽ Header/Footer và tính chuẩn xác tổng số trang Trang X/Y."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        page_num = self._pageNumber
        width, height = A4

        # Trang 1 là Cover Page nên không vẽ Header/Footer lặp
        if page_num > 1:
            # Header
            self.saveState()
            self.setFont(FONT_REGULAR, 8)
            self.setFillColor(COLOR_TEXT_MUTED)
            self.drawString(40, height - 28, "SEE NOTION — SỔ TAY HƯỚNG DẪN SỬ DỤNG DISCORD BOT")
            self.drawRightString(width - 40, height - 28, "CLB SUSTAINABLE ENGINEERING EDGE")
            
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(40, height - 34, width - 40, height - 34)

            # Footer
            self.line(40, 36, width - 40, 36)
            self.setFont(FONT_REGULAR, 8)
            self.setFillColor(COLOR_TEXT_MUTED)
            self.drawString(40, 24, "Phiên bản v2.1-production • Lưu hành nội bộ")
            self.drawRightString(width - 40, 24, f"Trang {page_num} / {total_pages}")
            self.restoreState()


def build_pdf(filename="docs/DISCORD_BOT_MANUAL.pdf"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=46,
    )

    styles = getSampleStyleSheet()

    # Custom Typography Styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=24,
        leading=30,
        textColor=COLOR_PRIMARY,
        alignment=0,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=12,
        leading=16,
        textColor=COLOR_STEEL,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=14,
        leading=18,
        textColor=COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=11,
        leading=15,
        textColor=COLOR_SECONDARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=13,
        textColor=COLOR_TEXT,
        spaceAfter=5,
    )

    body_bold = ParagraphStyle(
        "CustomBodyBold",
        parent=body_style,
        fontName=FONT_BOLD,
    )

    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8.5,
        leading=11,
        textColor=COLOR_PRIMARY,
    )

    callout_style = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName=FONT_ITALIC,
        fontSize=8.5,
        leading=12,
        textColor=COLOR_SECONDARY,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=11,
        textColor=COLOR_WHITE,
        alignment=0,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=11,
        textColor=COLOR_TEXT,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=table_cell_style,
        fontName=FONT_BOLD,
        textColor=COLOR_PRIMARY,
    )

    story = []

    # ================= COVER BANNER =================
    banner_content = [
        [
            Paragraph("HƯỚNG DẪN VẬN HÀNH & SỬ DỤNG DISCORD BOT", subtitle_style),
        ],
        [
            Paragraph("SEE NOTION MANAGEMENT SYSTEM", title_style),
        ],
        [
            Paragraph(
                "Tài liệu hướng dẫn trực quan 8 chức năng Discord Bot • Quản trị Task Notion • Nhắc Deadline tự động",
                subtitle_style,
            ),
        ],
    ]
    banner_table = Table(banner_content, colWidths=[515])
    banner_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_CARD_BG),
            ("BOX", (0, 0), (-1, -1), 1.5, COLOR_PRIMARY),
            ("PADDING", (0, 0), (-1, -1), 16),
            ("TOPPADDING", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
        ])
    )
    story.append(banner_table)
    story.append(Spacer(1, 12))

    # Meta Info Row
    meta_data = [
        [
            Paragraph("<b>Đơn vị:</b> Ban Điều hành CLB SEE", table_cell_style),
            Paragraph("<b>Phân loại:</b> Sổ tay Vận hành v2.1", table_cell_style),
            Paragraph("<b>Môi trường:</b> Discord + Notion Cloud", table_cell_style),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[171, 171, 173])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # ================= PHẦN 1: TỔNG QUAN & RBAC =================
    story.append(Paragraph("1. TỔNG QUAN VÀ CHU TRÌNH VẬN HÀNH AN TOÀN", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceBefore=2, spaceAfter=6))
    story.append(
        Paragraph(
            "SEE-Notion Bot tiếp nhận lệnh ngôn ngữ tự nhiên từ Discord, phân tích thông minh bằng LLM và đồng bộ hai chiều với Notion Database. Hệ thống vận hành theo quy tắc <b>Preview ➔ Confirm 2 bước</b>:",
            body_style,
        )
    )

    flow_box = [
        [
            Paragraph("<b>Bước 1: Ra lệnh</b><br/>Gõ slash command hoặc chat tự nhiên trên Discord.", table_cell_style),
            Paragraph("<b>Bước 2: Xem trước (Preview)</b><br/>Bot tạo card tóm tắt kèm nút [Xác nhận ✅] [Hủy ❌].", table_cell_style),
            Paragraph("<b>Bước 3: Đồng bộ & Nhắc nhở</b><br/>Ghi dữ liệu vào Notion và tự động gửi email/DM nhắc hạn.", table_cell_style),
        ]
    ]
    flow_table = Table(flow_box, colWidths=[171, 171, 173])
    flow_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(flow_table)
    story.append(Spacer(1, 8))

    # Phân quyền RBAC Callout
    rbac_content = [
        [
            Paragraph(
                "<b>🛡️ QUY TẮC BẢO MẬT PHÂN QUYỀN (RBAC):</b><br/>"
                "• <b>Admin:</b> Toàn quyền quản trị, sửa/hoàn thành/archive mọi task; cấu hình danh bạ team.<br/>"
                "• <b>Member:</b> Chỉ được chỉnh sửa hoặc hoàn thành task do <i>chính mình tạo</i> hoặc <i>được phân công (Assignee)</i>. Mọi hành vi can thiệp task người khác sẽ bị bot chặn và báo lỗi <code>NotAuthorized</code>.",
                callout_style,
            )
        ]
    ]
    rbac_table = Table(rbac_content, colWidths=[515])
    rbac_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_CARD_BG),
            ("LEFTPADDING", (0, 0), (0, -1), 10),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_SECONDARY),
            ("LINELEFT", (0, 0), (0, -1), 3, COLOR_PRIMARY),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(rbac_table)
    story.append(Spacer(1, 12))

    # ================= PHẦN 2: CÁC LỆNH THAO TÁC TASK =================
    story.append(Paragraph("2. BẢNG HƯỚNG DẪN 5 LỆNH THAO TÁC TASK (MEMBER & ADMIN)", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceBefore=2, spaceAfter=6))

    cmd_data = [
        [
            Paragraph("Lệnh", table_header_style),
            Paragraph("Tham số (Arguments)", table_header_style),
            Paragraph("Mô tả chức năng", table_header_style),
            Paragraph("Ví dụ minh họa", table_header_style),
        ],
        [
            Paragraph("<b>/create</b>", table_cell_bold),
            Paragraph("• <code>name</code> (bắt buộc)<br/>• <code>due_date</code> (bắt buộc)<br/>• <code>assignees</code><br/>• <code>priority</code>", table_cell_style),
            Paragraph("Tạo task mới trên Notion với form nhập liệu trực quan, tính toán ngày và map Notion User ID.", table_cell_style),
            Paragraph("<code>/create name: Báo cáo tài chính due_date: 30/11 assignees: Cường, Hân</code>", code_style),
        ],
        [
            Paragraph("<b>/my</b>", table_cell_bold),
            Paragraph("<i>(Không tham số)</i>", table_cell_style),
            Paragraph("Liệt kê tối đa 15 task đang mở (Not started, In progress) được phân công cho tài khoản của bạn.", table_cell_style),
            Paragraph("<code>/my</code>", code_style),
        ],
        [
            Paragraph("<b>/update</b>", table_cell_bold),
            Paragraph("• <code>text</code> (bắt buộc): Câu lệnh tự nhiên tiếng Việt", table_cell_style),
            Paragraph("Dời deadline, thay đổi người làm, đổi trạng thái task bằng ngôn ngữ tự nhiên (áp dụng RBAC).", table_cell_style),
            Paragraph("<code>/update text: Dời TSK-012 sang ngày 25/11 và assign thêm Quý</code>", code_style),
        ],
        [
            Paragraph("<b>/complete</b>", table_cell_bold),
            Paragraph("• <code>text</code> (tùy chọn mã task)", table_cell_style),
            Paragraph("Đánh dấu task sang Done. Nếu bỏ trống tham số, bot mở Select Menu để chọn nhiều task cùng lúc.", table_cell_style),
            Paragraph("<code>/complete text: TSK-008</code><br/>hoặc gõ <code>/complete</code> chọn từ menu", code_style),
        ],
        [
            Paragraph("<b>/bulk-create</b>", table_cell_bold),
            Paragraph("• <code>file</code> (.docx, .csv, .txt)<br/>• <code>text</code> (dán text trực tiếp)<br/>• <code>format</code>, <code>layout</code>", table_cell_style),
            Paragraph("Trích xuất bảng Action Items trong Biên bản họp (Word/CSV) để tạo hàng loạt task Notion tức thì.", table_cell_style),
            Paragraph("Đính kèm file <code>Meeting_Minutes.docx</code> và chọn lệnh <code>/bulk-create</code>", code_style),
        ],
    ]

    cmd_table = Table(cmd_data, colWidths=[70, 135, 145, 165])
    cmd_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_WHITE, COLOR_BG_LIGHT]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(cmd_table)
    story.append(Spacer(1, 12))

    # ================= PHẦN 3: CÁC LỆNH ADMIN =================
    story.append(Paragraph("3. BẢNG HƯỚNG DẪN 3 LỆNH QUẢN TRỊ DANH BẠ (ADMIN ONLY)", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceBefore=2, spaceAfter=6))
    story.append(
        Paragraph(
            "Các lệnh này được bảo vệ nghiêm ngặt: chỉ tài khoản có <code>role: admin</code> trong <code>team.yaml</code> mới thực hiện được.",
            body_style,
        )
    )

    admin_data = [
        [
            Paragraph("Lệnh Admin", table_header_style),
            Paragraph("Tham số (Arguments)", table_header_style),
            Paragraph("Mục đích & Cách hoạt động", table_header_style),
            Paragraph("Cú pháp mẫu", table_header_style),
        ],
        [
            Paragraph("<b>/link-user</b>", table_cell_bold),
            Paragraph("• <code>target</code>: Tag @User hoặc paste Discord ID<br/>• <code>email</code>: Email sinh viên VGU (Có gợi ý tự động)", table_cell_style),
            Paragraph("Liên kết Discord Account vào Email sinh viên. Tự động cập nhật tức thì vào SQLite và ghi an toàn vào file <code>team.yaml</code>.", table_cell_style),
            Paragraph("<code>/link-user target: @Quý email: 104240232@student.vgu.edu.vn</code>", code_style),
        ],
        [
            Paragraph("<b>/link-batch</b>", table_cell_bold),
            Paragraph("• <code>text</code>: Danh sách nhiều dòng dạng <code>email discord_id</code>", table_cell_style),
            Paragraph("Nạp hàng loạt ID Discord cho nhiều thành viên một lúc mà không cần gõ từng người.", table_cell_style),
            Paragraph("<code>/link-batch text:<br/>104240232@... 66174876...<br/>10426079@... @ThảoNguyên</code>", code_style),
        ],
        [
            Paragraph("<b>/sync-team</b>", table_cell_bold),
            Paragraph("<i>(Không tham số)</i>", table_cell_style),
            Paragraph("Đọc lại toàn bộ file <code>team.yaml</code> và nạp lại vào DB SQLite ngay lập tức trong 0.05s (không cần restart máy chủ).", table_cell_style),
            Paragraph("<code>/sync-team</code>", code_style),
        ],
    ]

    admin_table = Table(admin_data, colWidths=[75, 135, 155, 150])
    admin_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_SECONDARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_WHITE, COLOR_BG_LIGHT]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(admin_table)
    story.append(Spacer(1, 12))

    # ================= PHẦN 4: CƠ CHẾ NHẮC HẸN & TROUBLESHOOTING =================
    keep_block = []
    keep_block.append(Paragraph("4. CƠ CHẾ NHẮC DEADLINE & XỬ LÝ SỰ CỐ THƯỜNG GẶP", h1_style))
    keep_block.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceBefore=2, spaceAfter=6))

    trouble_data = [
        [
            Paragraph("Tình huống / Sự cố", table_header_style),
            Paragraph("Nguyên nhân cốt lõi", table_header_style),
            Paragraph("Giải pháp xử lý nhanh", table_header_style),
        ],
        [
            Paragraph("<b>Nhắc hạn tự động (Cron 5p)</b>", table_cell_bold),
            Paragraph("Quét task mở định kỳ mỗi 5 phút tính theo giờ ICT (Asia/Ho_Chi_Minh).", table_cell_style),
            Paragraph("Tự động gửi thông báo qua <b>Discord DM</b> và <b>Email</b> tại các mốc: Trước 3 ngày, trước 1 ngày, đúng ngày và khi quá hạn (chống gửi trùng).", table_cell_style),
        ],
        [
            Paragraph("<b>Lỗi: Chưa có trong danh bạ</b>", table_cell_bold),
            Paragraph("Tài khoản Discord chưa được liên kết với email trong <code>team.yaml</code>.", table_cell_style),
            Paragraph("Nhờ Admin chạy lệnh: <code>/link-user target: @bạn email: &lt;email_vgu&gt;</code>.", table_cell_style),
        ],
        [
            Paragraph("<b>Lỗi: Không có quyền sửa task</b>", table_cell_bold),
            Paragraph("Bạn không phải người tạo task và cũng không nằm trong danh sách Assignee.", table_cell_style),
            Paragraph("Liên hệ người phụ trách task đó hoặc nhờ Admin can thiệp xử lý.", table_cell_style),
        ],
        [
            Paragraph("<b>Lỗi: Assignee chưa link Notion</b>", table_cell_bold),
            Paragraph("Thành viên chưa tham gia Workspace Notion nên Notion không có User ID.", table_cell_style),
            Paragraph("Mời thành viên vào Workspace Notion, lấy User ID điền vào <code>team.yaml</code> và gõ <code>/sync-team</code>.", table_cell_style),
        ],
    ]

    trouble_table = Table(trouble_data, colWidths=[120, 185, 210])
    trouble_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_WHITE, COLOR_BG_LIGHT]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    keep_block.append(trouble_table)
    story.append(KeepTogether(keep_block))

    # Xây dựng file PDF với canvas custom 2-pass
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Build PDF thành công tại: {filename}")


if __name__ == "__main__":
    build_pdf()
