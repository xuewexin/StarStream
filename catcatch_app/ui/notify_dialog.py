"""
CatCatch Downloader - Modern Desktop Popup Notification Dialog
提供下载完成与下载失败时屏幕右下角现代化桌面悬浮弹窗提醒
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QApplication, QWidget, QDesktopWidget
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QFont

from .icons import get_icon, get_app_icon
from .task_log_dialog import TaskLogDialog


class DownloadNotifyDialog(QDialog):
    """
    屏幕右下角任务完成/失败弹窗提醒框
    """
    def __init__(self, task_data, is_success=True, parent=None):
        super().__init__(parent)
        self.task = dict(task_data)
        self.is_success = is_success
        self.output_file = self.task.get("output_file", "")
        self._auto_close_seconds = 12

        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(380, 160)
        self._init_ui()
        self._position_bottom_right()

        # 倒计时自动关闭定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 核心阴影与圆角卡片
        self.card = QFrame()
        accent_color = "#22c55e" if self.is_success else "#ef4444"
        bg_color = "#18181b"
        border_color = "#2e7d32" if self.is_success else "#7f1d1d"

        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        # 1. 顶部标题栏
        top_row = QHBoxLayout()
        lbl_icon = QLabel()
        if self.is_success:
            lbl_icon.setPixmap(get_icon("check", "#22c55e", 20).pixmap(20, 20))
        else:
            lbl_icon.setPixmap(get_icon("alert", "#ef4444", 20).pixmap(20, 20))
        top_row.addWidget(lbl_icon)

        st_title = "下载已完成" if self.is_success else "下载失败提醒"
        lbl_header = QLabel(st_title)
        lbl_header.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {accent_color};")
        top_row.addWidget(lbl_header, 1)

        self.lbl_countdown = QLabel(f"{self._auto_close_seconds}s")
        self.lbl_countdown.setStyleSheet("color: #71717a; font-size: 11px;")
        top_row.addWidget(self.lbl_countdown)

        btn_close = QPushButton("×")
        btn_close.setFixedSize(18, 18)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #a1a1aa;
                font-size: 15px;
                font-weight: bold;
                line-height: 14px;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.close)
        top_row.addWidget(btn_close)
        card_layout.addLayout(top_row)

        # 2. 任务名称与诊断信息
        title_text = self.task.get("title") or "未命名媒体"
        lbl_task_title = QLabel(title_text)
        lbl_task_title.setWordWrap(True)
        lbl_task_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #f4f4f5;")
        card_layout.addWidget(lbl_task_title)

        if self.is_success:
            res_str = self.task.get("resolution") or ""
            dur_str = self.task.get("duration") or ""
            meta_parts = []
            if res_str:
                meta_parts.append(f"规格: {res_str}")
            if dur_str:
                meta_parts.append(f"时长: {dur_str}")
            meta_text = " | ".join(meta_parts) if meta_parts else "已成功转封装为标准 MP4"
            lbl_meta = QLabel(meta_text)
            lbl_meta.setStyleSheet("color: #a1a1aa; font-size: 11px;")
            card_layout.addWidget(lbl_meta)
        else:
            reason = self.task.get("error_reason") or self.task.get("error_msg") or "下载遇到异常"
            lbl_err = QLabel(f"原因: {reason}")
            lbl_err.setWordWrap(True)
            lbl_err.setStyleSheet("color: #fca5a5; font-size: 11px;")
            card_layout.addWidget(lbl_err)

        # 3. 底部快捷操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        if self.is_success:
            btn_play = QPushButton("立即播放")
            btn_play.setIcon(get_icon("play", "#ffffff", 12))
            btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #22c55e;
                    border: none;
                    border-radius: 4px;
                    color: #ffffff;
                    font-weight: 600;
                    font-size: 11px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #16a34a;
                }
            """)
            btn_play.clicked.connect(self._action_play)
            btn_row.addWidget(btn_play)

            btn_folder = QPushButton("打开目录")
            btn_folder.setIcon(get_icon("folder", "#d4d4d8", 12))
            btn_folder.setStyleSheet("""
                QPushButton {
                    background-color: #27272a;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                    color: #d4d4d8;
                    font-size: 11px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #3f3f46;
                    color: #ffffff;
                }
            """)
            btn_folder.clicked.connect(self._action_open_dir)
            btn_row.addWidget(btn_folder)
        else:
            btn_view_log = QPushButton("查看详细诊断与日志")
            btn_view_log.setIcon(get_icon("log", "#ffffff", 12))
            btn_view_log.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    border: none;
                    border-radius: 4px;
                    color: #ffffff;
                    font-weight: 600;
                    font-size: 11px;
                    padding: 4px 12px;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
            btn_view_log.clicked.connect(self._action_view_log)
            btn_row.addWidget(btn_view_log)

        btn_row.addStretch()

        btn_dismiss = QPushButton("知道了")
        btn_dismiss.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                color: #a1a1aa;
                font-size: 11px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: #27272a;
                color: #f4f4f5;
            }
        """)
        btn_dismiss.clicked.connect(self.close)
        btn_row.addWidget(btn_dismiss)

        card_layout.addLayout(btn_row)
        main_layout.addWidget(self.card)

    def _position_bottom_right(self):
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = rect.x() + rect.width() - self.width() - 20
            y = rect.y() + rect.height() - self.height() - 20
            self.move(x, y)

    def _on_tick(self):
        self._auto_close_seconds -= 1
        if self._auto_close_seconds <= 0:
            self._timer.stop()
            self.close()
        else:
            self.lbl_countdown.setText(f"{self._auto_close_seconds}s")

    def _action_play(self):
        out_p = self.output_file or self.task.get("output_file", "")
        if out_p and os.path.exists(out_p):
            try:
                os.startfile(out_p)
            except Exception:
                pass
        self.close()

    def _action_open_dir(self):
        out_p = self.output_file or self.task.get("output_file", "")
        if out_p and os.path.exists(out_p):
            try:
                subprocess.run(f'explorer /select,"{out_p}"', shell=True)
            except Exception:
                pass
        else:
            s_dir = self.task.get("save_dir", "")
            if s_dir and os.path.exists(s_dir):
                try:
                    os.startfile(s_dir)
                except Exception:
                    pass
        self.close()

    def _action_view_log(self):
        self.close()
        dlg = TaskLogDialog(self.task, self.parent())
        dlg.exec_()
