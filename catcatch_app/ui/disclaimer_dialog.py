"""
CatCatch Downloader - Legal Disclaimer Dialog (高对比度免责声明弹窗)
彻底修复文本发黑看不清的问题，提供深色高对比度、清晰易读的合规提示
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from catcatch_app.ui.icons import get_icon, get_app_icon
from catcatch_app.core.config import config
from catcatch_app.ui.styles import THEMES


class DisclaimerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("免责声明与合法使用规范 - 星流媒体下载器")
        self.setWindowIcon(get_app_icon())
        self.setFixedSize(620, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cur_theme = THEMES.get(config.get("theme", "dark"), THEMES["dark"])
        self.is_light = cur_theme.get("is_light", False)

        bg_col = "#ffffff" if self.is_light else "#0f172a"
        text_col = "#0f172a" if self.is_light else "#f8fafc"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_col};
                color: {text_col};
            }}
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)

        title_col = "#0284c7" if self.is_light else "#38bdf8"
        card_bg = "#f8fafc" if self.is_light else "#1e293b"
        card_border = "#cbd5e1" if self.is_light else "#334155"
        body_text_col = "#1e293b" if self.is_light else "#f1f5f9"

        # 头部标题区
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("info", title_col, 32).pixmap(32, 32))
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel("星流媒体下载器 (StarStream Pro) 免责声明")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {title_col}; font-weight: bold;")
        header_layout.addWidget(title_lbl, 1)

        layout.addLayout(header_layout)

        # 核心内容卡片 (高对比度、字号适中、高可读性)
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
                padding: 14px 18px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        items = [
            ("1", "本软件仅供计算机网络协议研究、技术交流以及个人合法离线备份之用。"),
            ("2", "请使用者自觉遵守国家法律法规，充分尊重原创作者与版权所有方的合法权益。严禁将下载内容用于商业盈利、非法分发或侵权盗版活动！"),
            ("3", "本软件不托管、不提供亦不转播任何媒体资源，因用户违规下载使用而引发的任何版权纠纷与法律责任，均由使用者独立承担，开发者不承担任何直接或连带责任。"),
            ("4", "若测试下载的音视频涉及版权争议，请在下载后 24 小时内自觉删除。")
        ]

        badge_bg = "#e2e8f0" if self.is_light else "#334155"
        badge_text = "#0284c7" if self.is_light else "#38bdf8"

        for num, text in items:
            item_row = QHBoxLayout()
            item_row.setSpacing(10)
            item_row.setAlignment(Qt.AlignTop)

            badge = QLabel(f" {num} ")
            badge.setStyleSheet(f"""
                background-color: {badge_bg};
                color: {badge_text};
                font-weight: bold;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            """)
            badge.setFixedHeight(22)
            item_row.addWidget(badge)

            text_lbl = QLabel(text)
            text_lbl.setWordWrap(True)
            text_lbl.setFont(QFont("Segoe UI", 10))
            text_lbl.setStyleSheet(f"color: {body_text_col}; font-weight: 500; line-height: 1.6;")
            item_row.addWidget(text_lbl, 1)

            card_layout.addLayout(item_row)

        layout.addWidget(card)

        # 底部按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton("我已阅读并知悉")
        ok_btn.setFixedSize(140, 36)
        ok_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3875f6, stop:1 #6366f1);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f87ff, stop:1 #7a7eff);
            }
            QPushButton:pressed {
                background: #2563eb;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)
