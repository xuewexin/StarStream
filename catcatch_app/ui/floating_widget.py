"""
CatCatch Downloader - Floating Desktop Mini Widget (极简桌面悬浮小窗)
支持全局置顶、拖拽吸附移动、实时网速监控、双击呼出主界面、拖拽链接一键下载
"""
import os
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu, QAction, QApplication
)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush

from catcatch_app.core.config import config
from catcatch_app.core.task_manager import task_manager
from catcatch_app.core.download_file import format_size
from catcatch_app.ui.icons import get_icon, get_app_icon
from catcatch_app.ui.styles import THEMES


class FloatingWidget(QWidget):
    request_show_main = pyqtSignal()
    request_new_task_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setFixedSize(176, 58)

        self._drag_pos = QPoint()
        self._is_dragging = False

        self._init_ui()
        self._restore_position()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 图标容器
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(28, 28)
        self.icon_lbl.setPixmap(get_icon("download", "#3875f6", 24).pixmap(24, 24))
        layout.addWidget(self.icon_lbl)

        # 文本信息
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 2, 0, 2)

        self.lbl_speed = QLabel("0.00 B/s")
        self.lbl_speed.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_speed.setStyleSheet("color: #38bdf8;")

        self.lbl_status = QLabel("空闲")
        self.lbl_status.setFont(QFont("Segoe UI", 9))
        self.lbl_status.setStyleSheet("color: #a1a1aa;")

        text_layout.addWidget(self.lbl_speed)
        text_layout.addWidget(self.lbl_status)
        layout.addLayout(text_layout, 1)

    def update_stats(self, speed_str, active_count, total_count):
        """主界面定时同步悬浮窗实时网速与任务状态"""
        cur_theme = THEMES.get(config.get("theme", "dark"), THEMES["dark"])
        accent = cur_theme.get("accent", "#3875f6")

        if active_count > 0:
            self.lbl_speed.setText(speed_str if speed_str else "下载中...")
            self.lbl_speed.setStyleSheet(f"color: {accent}; font-weight: bold;")
            self.lbl_status.setText(f"{active_count} 项正在下载")
            self.icon_lbl.setPixmap(get_icon("download", accent, 24).pixmap(24, 24))
        else:
            self.lbl_speed.setText("0.00 B/s")
            self.lbl_speed.setStyleSheet("color: #a1a1aa;")
            self.lbl_status.setText(f"总计 {total_count} 项任务")
            self.icon_lbl.setPixmap(get_icon("check", "#4ade80", 24).pixmap(24, 24))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cur_theme = THEMES.get(config.get("theme", "dark"), THEMES["dark"])
        is_light = cur_theme.get("is_light", False)

        # 背景胶囊圆角阴影框
        rect = self.rect().adjusted(1, 1, -1, -1)
        bg_color = QColor(255, 255, 255, 235) if is_light else QColor(24, 25, 30, 230)
        border_color = QColor(226, 232, 240, 200) if is_light else QColor(48, 52, 62, 200)

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1.2))
        painter.drawRoundedRect(rect, 14, 14)
        painter.end()

    # --- 鼠标拖拽移动与交互 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() == Qt.LeftButton:
            new_pos = event.globalPos() - self._drag_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        config.set("floating_widget_x", self.x())
        config.set("floating_widget_y", self.y())

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.request_show_main.emit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_show = menu.addAction(get_icon("play", "#3875f6", 14), "显示主界面")
        act_show.triggered.connect(self.request_show_main.emit)

        menu.addSeparator()

        act_start_all = menu.addAction(get_icon("play", "#4ade80", 14), "全部开始")
        act_start_all.triggered.connect(self._action_start_all)

        act_pause_all = menu.addAction(get_icon("pause", "#f59e0b", 14), "全部暂停")
        act_pause_all.triggered.connect(self._action_pause_all)

        menu.addSeparator()

        act_hide = menu.addAction(get_icon("delete", "#f87171", 14), "隐藏悬浮窗")
        act_hide.triggered.connect(self.hide)

        menu.exec_(event.globalPos())

    def _action_start_all(self):
        for t in task_manager.get_all_tasks():
            if t.get("status") in ["paused", "error", "waiting"]:
                task_manager.start_task(t["id"])

    def _action_pause_all(self):
        for t in task_manager.get_all_tasks():
            if t.get("status") == "downloading":
                task_manager.pause_task(t["id"])

    # --- 拖拽 URL 一键下载 ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            text = event.mimeData().text().strip()
            if text.startswith("http://") or text.startswith("https://"):
                event.acceptProposedAction()

    def dropEvent(self, event):
        url = event.mimeData().text().strip()
        if url.startswith("http://") or url.startswith("https://"):
            self.request_new_task_url.emit(url)
            event.acceptProposedAction()

    def _restore_position(self):
        x = config.get("floating_widget_x", -1)
        y = config.get("floating_widget_y", -1)
        if x > 0 and y > 0:
            self.move(x, y)
        else:
            # 默认停靠在屏幕右侧居中
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                self.move(geo.width() - 200, geo.height() // 2 - 50)
