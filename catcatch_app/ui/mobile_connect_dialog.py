"""
CatCatch Downloader - Mobile LAN Connect & QR Code Dialog (手机局域网互联与扫码推流)
生成高清晰度二维码与局域网 IP 直达链接，支持手机跨端无线提交视频下载任务
"""
import socket
import webbrowser
from io import BytesIO
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QApplication, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont

from catcatch_app.core.config import config
from catcatch_app.ui.icons import get_icon, get_app_icon


def get_local_lan_ip():
    """获取本机当前在局域网 Wi-Fi / 有线连接中的真实 IPv4 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MobileConnectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("手机无线推流 & 局域网控制台 - 星流 (StarStream)")
        self.setWindowIcon(get_app_icon())
        self.setFixedWidth(440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.lan_ip = get_local_lan_ip()
        self.port = int(config.get("server_port", 18910))
        self.mobile_url = f"http://{self.lan_ip}:{self.port}"

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # 头部说明
        title_row = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(get_icon("phone", "#22c55e", 20).pixmap(20, 20))
        title_lbl = QLabel("手机扫码推流 (局域网互联)")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_lbl.setStyleSheet("color: #f4f4f5;")
        title_row.addWidget(title_icon)
        title_row.addWidget(title_lbl, 1)
        layout.addLayout(title_row)

        desc_lbl = QLabel("请确保手机与电脑连接在同一个 WiFi 局域网下。\n使用手机微信、浏览器或系统相机扫码，即可打开移动端工作台！")
        desc_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px; line-height: 1.4;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # 二维码展示容器
        qr_frame = QFrame()
        qr_frame.setStyleSheet("""
            QFrame {
                background: #18181b;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setAlignment(Qt.AlignCenter)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self._render_qr_code()
        qr_layout.addWidget(self.qr_label)

        layout.addWidget(qr_frame)

        # 访问链接展示卡片
        url_box = QFrame()
        url_box.setStyleSheet("""
            QFrame {
                background: #090a0f;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        url_row = QHBoxLayout(url_box)
        url_row.setContentsMargins(4, 4, 4, 4)

        self.lbl_url = QLabel(self.mobile_url)
        self.lbl_url.setFont(QFont("Consolas", 11, QFont.Bold))
        self.lbl_url.setStyleSheet("color: #38bdf8;")
        url_row.addWidget(self.lbl_url, 1)

        copy_btn = QPushButton("复制")
        copy_btn.setFixedWidth(54)
        copy_btn.clicked.connect(self._copy_url)
        url_row.addWidget(copy_btn)

        layout.addWidget(url_box)

        # 底部功能按钮
        btn_row = QHBoxLayout()
        open_browser_btn = QPushButton("在电脑浏览器中打开")
        open_browser_btn.setIcon(get_icon("globe", "#38bdf8", 14))
        open_browser_btn.clicked.connect(lambda: webbrowser.open(self.mobile_url))

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(open_browser_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _render_qr_code(self):
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(self.mobile_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#38bdf8", back_color="#18181b")
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)

            pix = QPixmap()
            pix.loadFromData(buf.getvalue(), "PNG")
            self.qr_label.setPixmap(pix)
        except Exception as e:
            self.qr_label.setText(f"[二维码生成失败: {e}]\n请直接在手机浏览器访问上方链接")
            self.qr_label.setStyleSheet("color: #f87171; font-size: 11px;")

    def _copy_url(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.mobile_url)
        QMessageBox.information(self, "复制成功", f"无线推流地址已复制到剪贴板:\n{self.mobile_url}")
