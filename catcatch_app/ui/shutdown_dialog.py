"""
CatCatch Downloader - Auto Shutdown Countdown Dialog (计划电源管理)
所有任务下载合并完成后，弹出倒计时防误触关机提醒
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from .icons import get_icon, get_app_icon


class ShutdownDialog(QDialog):
    def __init__(self, parent=None, timeout_seconds=60, is_sleep=False):
        super().__init__(parent)
        self.setWindowTitle("计划任务完成 - 准备关机")
        self.setWindowIcon(get_app_icon())
        self.setFixedSize(450, 220)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)

        self.remaining = timeout_seconds
        self.total = timeout_seconds
        self.is_sleep = is_sleep

        self._init_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 标题与提醒图标
        title_row = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("alert", "#f59e0b", 32).pixmap(32, 32))
        title_row.addWidget(icon_lbl)

        action_name = "睡眠" if self.is_sleep else "关机"
        self.lbl_title = QLabel(f"所有任务已下载完成，系统即将{action_name}")
        self.lbl_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_title.setStyleSheet("color: #f4f4f5;")
        title_row.addWidget(self.lbl_title, 1)
        layout.addLayout(title_row)

        # 倒计时文本
        self.lbl_countdown = QLabel(f"将在 {self.remaining} 秒后自动执行{action_name}，若需继续使用电脑请点击取消。")
        self.lbl_countdown.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        layout.addWidget(self.lbl_countdown)

        # 进度条
        self.pbar = QProgressBar()
        self.pbar.setRange(0, self.total)
        self.pbar.setValue(self.remaining)
        self.pbar.setTextVisible(False)
        self.pbar.setStyleSheet("""
            QProgressBar {
                background: #27272a;
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background: #f59e0b;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.pbar)

        # 底部操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("取消关机")
        self.btn_cancel.setProperty("class", "primary")
        self.btn_cancel.clicked.connect(self._cancel_shutdown)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_now = QPushButton(f"立即{action_name}")
        self.btn_now.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold;")
        self.btn_now.clicked.connect(self._do_shutdown)
        btn_layout.addWidget(self.btn_now)

        layout.addLayout(btn_layout)

    def _on_tick(self):
        self.remaining -= 1
        self.pbar.setValue(self.remaining)
        action_name = "睡眠" if self.is_sleep else "关机"
        self.lbl_countdown.setText(f"将在 {self.remaining} 秒后自动执行{action_name}，若需继续使用电脑请点击取消。")

        if self.remaining <= 0:
            self.timer.stop()
            self._do_shutdown()

    def _cancel_shutdown(self):
        self.timer.stop()
        self.reject()

    def _do_shutdown(self):
        self.timer.stop()
        self.accept()
        if os.name == "nt":
            try:
                if self.is_sleep:
                    # Windows 休眠/睡眠调用
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
                else:
                    # Windows 关机调用
                    subprocess.run(["shutdown", "/s", "/t", "0"])
            except Exception as e:
                print(f"[Shutdown] 执行关机失败: {e}")
