"""
CatCatch Downloader - Advanced Vendor-Grade Floating Desktop Widget (大厂级多形态桌面挂件)
支持:
1. 星流 · 量子星核 (StarStream Quantum Core - 炫酷赛博全息能量球 / 动态轨道环 / HUD测控) [默认]
2. 迅雷/IDM 流光动态水球 (双正弦流体液面动态浪涌/亚克力玻璃质感环/高精网速百分比)
3. 极光赛博霓虹胶囊 (赛博朋克发光描边/极客状态指标)
4. DeepSeek 灵动大肥鱼 (微表情/动态鱼鳍摆动/实时吐泡泡/拟真对话气泡)
5. 用户自定义形象挂件 (支持导入任意 PNG/GIF/JPG/WebP/ICO 动漫宠物或大厂形象)
支持全量缩放调节 (80% ~ 150%)、拖拽移动、拖拽网址直连下载、全局置顶切换
支持单击弹出极速任务监控微面板与快捷文件格式转换工具中心
"""
import math
import os
import random
from PyQt5.QtWidgets import (
    QWidget, QMenu, QAction, QApplication, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QPoint, QRectF, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QPixmap
)

from catcatch_app.core.config import config
from catcatch_app.core.task_manager import task_manager
from catcatch_app.ui.icons import get_icon, get_app_icon


class FloatingDashboardPanel(QWidget):
    """
    桌面挂件点击弹出的极速任务监控与快捷工具微面板 (浮动亚克力暗黑毛玻璃风格)
    显示当前下载任务实时进度、网速、控制按钮，以及批量格式转换/FFmpeg工具箱/短视频提取等快捷入口
    """
    request_show_main = pyqtSignal()
    request_open_batch_convert = pyqtSignal()
    request_open_ffmpeg_toolbox = pyqtSignal()
    request_open_video_parser = pyqtSignal()
    request_new_task = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(360)
        self.setFixedHeight(350)
        self._init_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_data)
        self._refresh_timer.start(1000)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame()
        self.card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f172a, stop:1 #090d16);
                border: 1.5px solid #38bdf8;
                border-radius: 14px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        # 1. 顶部标题栏
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        title_lbl = QLabel("星流 · 任务监控与工具中心")
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_lbl.setStyleSheet("color: #38bdf8; border: none;")
        top_row.addWidget(title_lbl)

        top_row.addStretch()

        self.speed_pill = QLabel("0.00 B/s")
        self.speed_pill.setStyleSheet("""
            background: #1e293b;
            color: #4ade80;
            font-size: 11px;
            font-weight: 600;
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        top_row.addWidget(self.speed_pill)

        close_btn = QPushButton()
        close_btn.setIcon(get_icon("close", "#94a3b8", 12))
        close_btn.setFixedSize(22, 22)
        close_btn.setToolTip("关闭监控面板")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #f87171;
            }
        """)
        close_btn.clicked.connect(self.hide)
        top_row.addWidget(close_btn)

        card_layout.addLayout(top_row)

        # 2. 实时任务监控区 (滚动容器)
        sec_title = QLabel("当前下载任务")
        sec_title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; border: none;")
        card_layout.addWidget(sec_title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(140)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #1e293b;
                border-radius: 8px;
                background: #090d16;
            }
            QScrollBar:vertical {
                border: none;
                background: #0f172a;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 3px;
            }
        """)

        self.task_list_widget = QWidget()
        self.task_list_layout = QVBoxLayout(self.task_list_widget)
        self.task_list_layout.setContentsMargins(6, 6, 6, 6)
        self.task_list_layout.setSpacing(6)
        self.task_list_layout.addStretch()
        self.scroll.setWidget(self.task_list_widget)
        card_layout.addWidget(self.scroll)

        # 3. 快捷文件转换与核心工具箱
        tools_lbl = QLabel("快捷工具与文件转换")
        tools_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; border: none; margin-top: 2px;")
        card_layout.addWidget(tools_lbl)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(6)

        btn_batch = QPushButton("批量格式转换")
        btn_batch.setIcon(get_icon("refresh", "#c084fc", 14))
        btn_batch.setToolTip("批量转换音视频格式 (MP4/MKV/TS/MP3/M4A/FLAC)")
        btn_batch.setStyleSheet("""
            QPushButton {
                background: #1e1b4b;
                color: #c084fc;
                border: 1px solid #4338ca;
                border-radius: 6px;
                padding: 6px 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #312e81;
                border-color: #a855f7;
                color: #ffffff;
            }
        """)
        btn_batch.clicked.connect(self._on_open_batch)

        btn_ffmpeg = QPushButton("FFmpeg 工具箱")
        btn_ffmpeg.setIcon(get_icon("toolbox", "#38bdf8", 14))
        btn_ffmpeg.setToolTip("音视频快速剪辑、提取音频、无损合并")
        btn_ffmpeg.setStyleSheet("""
            QPushButton {
                background: #0c4a6e;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 6px 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0369a1;
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)
        btn_ffmpeg.clicked.connect(self._on_open_ffmpeg)

        btn_parser = QPushButton("短视频提取")
        btn_parser.setIcon(get_icon("zap", "#fbbf24", 14))
        btn_parser.setToolTip("全网主流短视频无水印解析提取 (抖音/快手/B站4K/小红书)")
        btn_parser.setStyleSheet("""
            QPushButton {
                background: #451a03;
                color: #fbbf24;
                border: 1px solid #b45309;
                border-radius: 6px;
                padding: 6px 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #78350f;
                border-color: #f59e0b;
                color: #ffffff;
            }
        """)
        btn_parser.clicked.connect(self._on_open_parser)

        tools_row.addWidget(btn_batch)
        tools_row.addWidget(btn_ffmpeg)
        tools_row.addWidget(btn_parser)
        card_layout.addLayout(tools_row)

        # 4. 底部打开主程序大按钮
        main_btn = QPushButton("打开星流完整主程序")
        main_btn.setIcon(get_icon("monitor", "#ffffff", 14))
        main_btn.setFixedHeight(28)
        main_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #4338ca);
            }
        """)
        main_btn.clicked.connect(self._on_open_main)
        card_layout.addWidget(main_btn)

        root_layout.addWidget(self.card)

    def _on_open_batch(self):
        self.request_open_batch_convert.emit()
        self.hide()

    def _on_open_ffmpeg(self):
        self.request_open_ffmpeg_toolbox.emit()
        self.hide()

    def _on_open_parser(self):
        self.request_open_video_parser.emit()
        self.hide()

    def _on_open_main(self):
        self.request_show_main.emit()
        self.hide()

    def refresh_data(self):
        if not self.isVisible():
            return

        tasks = task_manager.get_all_tasks()
        active = [t for t in tasks if t.get("status") in ["downloading", "waiting"]]

        # 清除现有项目 (保留末尾的 stretch)
        while self.task_list_layout.count() > 1:
            child = self.task_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not active:
            empty_box = QWidget()
            empty_l = QVBoxLayout(empty_box)
            empty_l.setContentsMargins(0, 18, 0, 18)
            empty_l.setSpacing(6)

            lbl = QLabel("暂无正在进行的下载任务")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #64748b; font-size: 11px; border: none;")
            empty_l.addWidget(lbl)

            btn_new = QPushButton("+ 新建下载")
            btn_new.setFixedWidth(90)
            btn_new.setStyleSheet("""
                QPushButton {
                    background: #1e293b;
                    color: #38bdf8;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 3px 6px;
                    font-size: 11px;
                }
                QPushButton:hover { background: #334155; }
            """)
            btn_new.clicked.connect(lambda: (self.request_new_task.emit(), self.hide()))
            empty_l.addWidget(btn_new, 0, Qt.AlignCenter)

            self.task_list_layout.insertWidget(0, empty_box)
            self.speed_pill.setText("0.00 B/s")
            return

        # 展示活跃任务 (至多前 4 项)
        for t in active[:4]:
            t_row = QWidget()
            t_row.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 4px;")
            tl = QVBoxLayout(t_row)
            tl.setContentsMargins(6, 4, 6, 4)
            tl.setSpacing(4)

            # 行 1: 标题与速度
            r1 = QHBoxLayout()
            name = t.get("title") or t.get("save_name") or "未命名任务"
            if len(name) > 20:
                name = name[:18] + "..."
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: 500; border: none;")
            r1.addWidget(name_lbl, 1)

            spd = t.get("speed_str") or "0.00 B/s"
            spd_lbl = QLabel(spd)
            spd_lbl.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold; border: none;")
            r1.addWidget(spd_lbl)

            tl.addLayout(r1)

            # 行 2: 进度条与操作按键
            r2 = QHBoxLayout()
            pbar = QProgressBar()
            pbar.setFixedHeight(5)
            pbar.setTextVisible(False)
            pbar.setRange(0, 100)
            prog = int(float(t.get("progress") or 0))
            pbar.setValue(prog)
            pbar.setStyleSheet("""
                QProgressBar {
                    background: #1e293b;
                    border: none;
                    border-radius: 2px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #818cf8);
                    border-radius: 2px;
                }
            """)
            r2.addWidget(pbar, 1)

            pct_lbl = QLabel(f"{prog}%")
            pct_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; border: none; min-width: 28px;")
            r2.addWidget(pct_lbl)

            tid = t.get("id")
            if t.get("status") == "downloading":
                btn_act = QPushButton("暂停")
                btn_act.setStyleSheet("color: #f59e0b; font-size: 10px; background: transparent; border: 1px solid #78350f; border-radius: 3px; padding: 1px 4px;")
                btn_act.clicked.connect(lambda _, x=tid: task_manager.pause_task(x))
            else:
                btn_act = QPushButton("继续")
                btn_act.setStyleSheet("color: #4ade80; font-size: 10px; background: transparent; border: 1px solid #14532d; border-radius: 3px; padding: 1px 4px;")
                btn_act.clicked.connect(lambda _, x=tid: task_manager.start_task(x))
            r2.addWidget(btn_act)

            tl.addLayout(r2)
            self.task_list_layout.insertWidget(self.task_list_layout.count() - 1, t_row)


class FloatingWidget(QWidget):
    request_show_main = pyqtSignal()
    request_new_task_url = pyqtSignal(str)
    request_open_batch_convert = pyqtSignal()
    request_open_ffmpeg_toolbox = pyqtSignal()
    request_open_video_parser = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)

        self._drag_pos = QPoint()
        self._press_global_pos = QPoint()
        self._is_dragging = False

        # 核心形态与尺寸设置 (默认设置为星流量子星核主题)
        skin = config.get("floating_skin", "starstream_core")
        if skin in ["deepseek_fish", "custom_mascot"] and not config.get("floating_custom_image"):
            skin = "starstream_core"
            config.set("floating_skin", "starstream_core")
        self.skin = skin

        self.scale_factor = float(config.get("floating_scale", 1.0))
        self.custom_image_path = config.get("floating_custom_image", "")
        self._custom_pixmap = None

        # 实时下载数据缓存
        self.speed_str = "0.00 B/s"
        self.active_count = 0
        self.total_count = 0
        self.progress_pct = 0.0

        # 动态动画变量 (波浪、摇摆、泡泡)
        self._anim_tick = 0
        self._wave_phase = 0.0
        self._bubbles = []
        for _ in range(5):
            self._bubbles.append({
                "x": random.uniform(15, 65),
                "y": random.uniform(20, 80),
                "r": random.uniform(2, 4.5),
                "speed": random.uniform(0.6, 1.4),
                "alpha": random.uniform(120, 220)
            })

        # 初始化极速任务监控微面板
        self._dashboard = FloatingDashboardPanel()
        self._dashboard.request_show_main.connect(self.request_show_main.emit)
        self._dashboard.request_open_batch_convert.connect(self.request_open_batch_convert.emit)
        self._dashboard.request_open_ffmpeg_toolbox.connect(self.request_open_ffmpeg_toolbox.emit)
        self._dashboard.request_open_video_parser.connect(self.request_open_video_parser.emit)
        self._dashboard.request_new_task.connect(lambda: self.request_new_task_url.emit(""))

        self._load_custom_pixmap()
        self._update_widget_size()
        self._restore_position()

        # 高平滑度轻量定时动画 (约 30 FPS)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start(33)

    def _load_custom_pixmap(self):
        if self.custom_image_path and os.path.exists(self.custom_image_path):
            try:
                pix = QPixmap(self.custom_image_path)
                if not pix.isNull():
                    self._custom_pixmap = pix
            except Exception:
                self._custom_pixmap = None

    def _update_widget_size(self):
        """根据当前形象与缩放系数计算窗口宽高"""
        base_w, base_h = 168, 72
        if self.skin == "water_sphere":
            base_w, base_h = 100, 100
        elif self.skin == "neon_capsule":
            base_w, base_h = 176, 58
        elif self.skin == "deepseek_fish":
            base_w, base_h = 170, 105
        elif self.skin == "custom_mascot":
            base_w, base_h = 160, 110
        elif self.skin == "starstream_core":
            base_w, base_h = 168, 72

        w = int(base_w * self.scale_factor)
        h = int(base_h * self.scale_factor)
        self.setFixedSize(w, h)

    def update_stats(self, speed_str, active_count, total_count):
        """由主窗口定时器驱动更新网速和进度数据"""
        self.speed_str = speed_str if speed_str else "0.00 B/s"
        self.active_count = active_count
        self.total_count = total_count

        # 计算活跃任务整体平均下载进度
        active_tasks = [t for t in task_manager.get_all_tasks() if t.get("status") == "downloading"]
        if active_tasks:
            total_p = sum(float(t.get("progress") or 0.0) for t in active_tasks)
            self.progress_pct = max(0.0, min(100.0, total_p / len(active_tasks)))
        else:
            self.progress_pct = 0.0

        if self._dashboard.isVisible():
            self._dashboard.speed_pill.setText(self.speed_str)

    def _on_anim_tick(self):
        self._anim_tick = (self._anim_tick + 1) % 10000
        self._wave_phase += 0.08
        if self._wave_phase > 2 * math.pi:
            self._wave_phase -= 2 * math.pi

        # 仅在活跃下载时向上运动泡泡
        for b in self._bubbles:
            b["y"] -= b["speed"] * (1.5 if self.active_count > 0 else 0.4)
            if b["y"] < 5:
                b["y"] = random.uniform(65, 85)
                b["x"] = random.uniform(15, 65)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 坐标系全局缩放
        if self.scale_factor != 1.0:
            painter.scale(self.scale_factor, self.scale_factor)

        if self.skin == "starstream_core":
            self._draw_starstream_core(painter)
        elif self.skin == "deepseek_fish":
            self._draw_deepseek_fish(painter)
        elif self.skin == "water_sphere":
            self._draw_water_sphere(painter)
        elif self.skin == "custom_mascot":
            self._draw_custom_mascot(painter)
        else:
            self._draw_neon_capsule(painter)

        painter.end()

    # =========================================================================
    # 皮肤 1: 星流 · 量子星核 (StarStream Quantum Core - 赛博全息能量球与HUD测控)
    # =========================================================================
    def _draw_starstream_core(self, p: QPainter):
        cx, cy = 36, 36
        core_r = 26

        # 1. 外层全息 HUD 环与微刻度
        hud_rect = QRectF(cx - core_r - 4, cy - core_r - 4, (core_r + 4) * 2, (core_r + 4) * 2)
        p.setPen(QPen(QColor(51, 65, 85, 120), 1.5, Qt.DotLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(hud_rect)

        # 2. 动态下载进度光弧 (若无下载则自旋流光，下载中显示真实进度弧)
        p.setPen(Qt.NoPen)
        if self.active_count > 0:
            span_angle = int(-self.progress_pct * 3.6 * 16)
            start_angle = 90 * 16
        else:
            span_angle = 90 * 16
            start_angle = int(((self._anim_tick * 4) % 360) * 16)

        arc_pen = QPen(QColor(56, 189, 248), 2.5, Qt.SolidLine, Qt.RoundCap)
        p.setPen(arc_pen)
        p.drawArc(QRectF(cx - core_r - 2, cy - core_r - 2, (core_r + 2) * 2, (core_r + 2) * 2), start_angle, span_angle)

        # 3. 3D 旋转陀螺仪轨道光环 (Quantum Gyro Rings)
        rot_speed = 3.5 if self.active_count > 0 else 1.2
        ring_angle1 = (self._anim_tick * rot_speed) % 360
        ring_angle2 = (-self._anim_tick * rot_speed * 0.8) % 360

        # 轨道环 1 (青蓝)
        p.save()
        p.translate(cx, cy)
        p.rotate(35)
        p.rotate(ring_angle1)
        p.setPen(QPen(QColor(56, 189, 248, 160), 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(-22, -9, 44, 18))
        # 轨道光子 1
        p.setBrush(QColor(255, 255, 255, 240))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPoint(18, 0), 2, 2)
        p.restore()

        # 轨道环 2 (星云紫)
        p.save()
        p.translate(cx, cy)
        p.rotate(-45)
        p.rotate(ring_angle2)
        p.setPen(QPen(QColor(192, 132, 252, 160), 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(-20, -8, 40, 16))
        # 轨道光子 2
        p.setBrush(QColor(255, 255, 255, 240))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPoint(-16, 0), 2, 2)
        p.restore()

        # 4. 核心等离子能量球 (Pulsating Plasma Core)
        pulse = math.sin(self._anim_tick * 0.15) * (2.2 if self.active_count > 0 else 1.0)
        plasma_r = max(10.0, 14.0 + pulse)

        # 外层辉光光晕
        glow_grad = QRadialGradient(cx, cy, plasma_r + 8)
        glow_grad.setColorAt(0, QColor(56, 189, 248, 100))
        glow_grad.setColorAt(0.6, QColor(59, 130, 246, 50))
        glow_grad.setColorAt(1, QColor(30, 27, 75, 0))
        p.setBrush(glow_grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPoint(cx, cy), int(plasma_r + 8), int(plasma_r + 8))

        # 实体能量球核
        core_grad = QRadialGradient(cx - 3, cy - 3, plasma_r)
        core_grad.setColorAt(0, QColor(255, 255, 255))
        core_grad.setColorAt(0.25, QColor(147, 197, 253))
        core_grad.setColorAt(0.65, QColor(37, 99, 235))
        core_grad.setColorAt(1, QColor(15, 23, 42))
        p.setBrush(core_grad)
        p.drawEllipse(QPoint(cx, cy), int(plasma_r), int(plasma_r))

        # 5. 右侧赛博全息测控卡牌 (HUD Telemetry Card)
        card_rect = QRectF(66, 10, 96, 52)
        c_path = QPainterPath()
        c_path.addRoundedRect(card_rect, 10, 10)

        p.setBrush(QColor(11, 15, 25, 235))
        p.setPen(QPen(QColor(56, 189, 248, 140), 1.2))
        p.drawPath(c_path)

        # 顶部测控网速
        p.setPen(QColor(56, 189, 248) if self.active_count > 0 else QColor(148, 163, 184))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        text_speed = self.speed_str if self.active_count > 0 else "星流待命"
        p.drawText(QRectF(70, 14, 88, 18), Qt.AlignCenter, text_speed)

        # 中间状态文字
        p.setPen(QColor(226, 232, 240))
        p.setFont(QFont("Segoe UI", 8))
        text_sub = f"{self.active_count} 项极速下载" if self.active_count > 0 else f"{self.total_count} 项就绪"
        p.drawText(QRectF(70, 31, 88, 16), Qt.AlignCenter, text_sub)

        # 底部微型进度光条
        bar_x, bar_y, bar_w, bar_h = 74, 49, 80, 4
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(30, 41, 59))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self.progress_pct > 0:
            fill_w = max(4.0, bar_w * (self.progress_pct / 100.0))
            bar_grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            bar_grad.setColorAt(0, QColor(56, 189, 248))
            bar_grad.setColorAt(1, QColor(168, 85, 247))
            p.setBrush(bar_grad)
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

    # =========================================================================
    # 皮肤 2: DeepSeek 灵动大肥鱼 (官方萌鱼风格)
    # =========================================================================
    def _draw_deepseek_fish(self, p: QPainter):
        wiggle = math.sin(self._anim_tick * 0.12) * (2.8 if self.active_count > 0 else 1.2)
        tail_rot = math.sin(self._anim_tick * 0.18) * 8.0

        fish_ox, fish_oy = 46, 58 + wiggle

        for b in self._bubbles:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(147, 197, 253, int(b["alpha"] * 0.7)))
            p.drawEllipse(QPoint(int(b["x"]), int(b["y"])), int(b["r"]), int(b["r"]))
            p.setBrush(QColor(255, 255, 255, 180))
            p.drawEllipse(QPoint(int(b["x"] - b["r"] * 0.3), int(b["y"] - b["r"] * 0.3)), 1, 1)

        p.save()
        p.translate(fish_ox - 24, fish_oy + 4)
        p.rotate(tail_rot)
        tail_grad = QLinearGradient(-15, -12, 0, 12)
        tail_grad.setColorAt(0, QColor(96, 165, 250, 240))
        tail_grad.setColorAt(1, QColor(37, 99, 235, 240))
        p.setBrush(tail_grad)
        p.setPen(QPen(QColor(30, 58, 138, 120), 1))

        tail_path = QPainterPath()
        tail_path.moveTo(0, 0)
        tail_path.cubicTo(-14, -12, -22, -10, -20, 0)
        tail_path.cubicTo(-22, 10, -14, 12, 0, 0)
        p.drawPath(tail_path)
        p.restore()

        body_grad = QLinearGradient(fish_ox - 25, fish_oy - 25, fish_ox + 25, fish_oy + 25)
        body_grad.setColorAt(0, QColor(96, 165, 250))
        body_grad.setColorAt(0.6, QColor(59, 130, 246))
        body_grad.setColorAt(1, QColor(29, 78, 216))

        p.setPen(QPen(QColor(30, 64, 175, 180), 1.2))
        p.setBrush(body_grad)
        p.drawEllipse(QPoint(int(fish_ox), int(fish_oy)), 26, 20)

        belly_path = QPainterPath()
        belly_path.moveTo(fish_ox - 18, fish_oy + 5)
        belly_path.cubicTo(fish_ox - 10, fish_oy + 18, fish_ox + 12, fish_oy + 18, fish_ox + 20, fish_oy + 4)
        belly_path.cubicTo(fish_ox + 10, fish_oy + 10, fish_ox - 8, fish_oy + 10, fish_ox - 18, fish_oy + 5)
        p.setBrush(QColor(239, 246, 255, 210))
        p.setPen(Qt.NoPen)
        p.drawPath(belly_path)

        fin_rot = math.sin(self._anim_tick * 0.15 + 1.0) * 12.0
        p.save()
        p.translate(fish_ox + 2, fish_oy + 6)
        p.rotate(fin_rot)
        p.setBrush(QColor(147, 197, 253, 230))
        p.setPen(QPen(QColor(37, 99, 235, 120), 1))
        fin_path = QPainterPath()
        fin_path.moveTo(0, 0)
        fin_path.cubicTo(10, 2, 14, 8, 4, 11)
        fin_path.cubicTo(0, 10, -2, 4, 0, 0)
        p.drawPath(fin_path)
        p.restore()

        eye_x, eye_y = int(fish_ox + 14), int(fish_oy - 4)
        p.setBrush(QColor(244, 114, 182, 140))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPoint(eye_x - 3, eye_y + 9), 5, 3)

        is_blinking = (self._anim_tick % 120) < 6
        if is_blinking:
            p.setPen(QPen(QColor(15, 23, 42), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(eye_x - 4, eye_y, eye_x + 4, eye_y)
        else:
            p.setBrush(QColor(15, 23, 42))
            p.drawEllipse(QPoint(eye_x, eye_y), 4, 4)
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(QPoint(eye_x - 1, eye_y - 1), 2, 2)

        mouth_path = QPainterPath()
        mouth_path.moveTo(fish_ox + 22, fish_oy + 1)
        mouth_path.quadTo(fish_ox + 24, fish_oy + 5, fish_ox + 21, fish_oy + 7)
        p.setPen(QPen(QColor(30, 58, 138), 1.4, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPath(mouth_path)

        bubble_rect = QRectF(78, 16, 84, 48)
        b_path = QPainterPath()
        b_path.addRoundedRect(bubble_rect, 10, 10)
        b_path.moveTo(78, 40)
        b_path.lineTo(70, 48)
        b_path.lineTo(78, 46)

        p.setPen(QPen(QColor(59, 130, 246, 180), 1.2))
        p.setBrush(QColor(15, 23, 42, 230))
        p.drawPath(b_path)

        p.setPen(QColor(56, 189, 248) if self.active_count > 0 else QColor(148, 163, 184))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        text_speed = self.speed_str if self.active_count > 0 else "空闲游弋中"
        p.drawText(QRectF(82, 20, 76, 20), Qt.AlignCenter, text_speed)

        p.setPen(QColor(203, 213, 225))
        p.setFont(QFont("Segoe UI", 8))
        text_sub = f"{self.active_count} 项下载中" if self.active_count > 0 else f"{self.total_count} 项就绪"
        p.drawText(QRectF(82, 38, 76, 20), Qt.AlignCenter, text_sub)

    # =========================================================================
    # 皮肤 3: 迅雷/IDM 流光动态水球 (液面浪涌风格)
    # =========================================================================
    def _draw_water_sphere(self, p: QPainter):
        cx, cy, r = 50, 50, 42
        sphere_rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 23, 42, 230))
        p.drawEllipse(sphere_rect)

        clip_path = QPainterPath()
        clip_path.addEllipse(sphere_rect)
        p.save()
        p.setClipPath(clip_path)

        pct = self.progress_pct if self.active_count > 0 else 25.0
        water_y = (cy + r) - (pct / 100.0) * (r * 2)

        wave_path = QPainterPath()
        wave_path.moveTo(cx - r - 5, cy + r + 5)
        step = 4
        x = cx - r - 5
        while x <= cx + r + 5:
            y = water_y + math.sin(x * 0.1 + self._wave_phase) * 3.5 + math.cos(x * 0.06 - self._wave_phase * 0.8) * 2.0
            wave_path.lineTo(x, y)
            x += step
        wave_path.lineTo(cx + r + 5, cy + r + 5)
        wave_path.closeSubpath()

        water_grad = QLinearGradient(cx, water_y - 10, cx, cy + r)
        if self.active_count > 0:
            water_grad.setColorAt(0, QColor(56, 189, 248, 220))
            water_grad.setColorAt(1, QColor(37, 99, 235, 240))
        else:
            water_grad.setColorAt(0, QColor(52, 211, 153, 190))
            water_grad.setColorAt(1, QColor(16, 185, 129, 220))

        p.setBrush(water_grad)
        p.setPen(Qt.NoPen)
        p.drawPath(wave_path)

        p.restore()
        glass_grad = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
        glass_grad.setColorAt(0, QColor(255, 255, 255, 90))
        glass_grad.setColorAt(0.4, QColor(255, 255, 255, 10))
        glass_grad.setColorAt(0.8, QColor(0, 0, 0, 40))
        glass_grad.setColorAt(1, QColor(56, 189, 248, 120))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(glass_grad, 2.5))
        p.drawEllipse(sphere_rect)

        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        speed_txt = self.speed_str if self.active_count > 0 else "0.0 B/s"
        p.drawText(QRectF(cx - r, cy - 14, r * 2, 16), Qt.AlignCenter, speed_txt)

        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(224, 242, 254) if self.active_count > 0 else QColor(167, 243, 208))
        status_txt = f"{self.progress_pct:.0f}%" if self.active_count > 0 else "READY"
        p.drawText(QRectF(cx - r, cy + 4, r * 2, 14), Qt.AlignCenter, status_txt)

    # =========================================================================
    # 皮肤 4: 极光赛博霓虹胶囊 (现代 Cyberpunk 风格)
    # =========================================================================
    def _draw_neon_capsule(self, p: QPainter):
        rect = QRectF(2, 2, 172, 54)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 17, 23, 235))
        p.drawRoundedRect(rect, 16, 16)

        neon_grad = QLinearGradient(0, 0, 176, 58)
        color_shift = (self._anim_tick * 2) % 360
        neon_c1 = QColor.fromHsv(color_shift, 200, 255, 220)
        neon_c2 = QColor.fromHsv((color_shift + 120) % 360, 220, 255, 220)
        neon_grad.setColorAt(0, neon_c1)
        neon_grad.setColorAt(1, neon_c2)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(neon_grad, 1.6))
        p.drawRoundedRect(rect, 16, 16)

        core_cx, core_cy = 30, 29
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(30, 41, 59))
        p.drawEllipse(QPoint(core_cx, core_cy), 18, 18)

        p.setPen(QPen(neon_c1, 2.0))
        span = int(self.progress_pct * 3.6 * 16) if self.active_count > 0 else int(((self._anim_tick * 5) % 360) * 16)
        p.drawArc(QRectF(core_cx - 16, core_cy - 16, 32, 32), 90 * 16, -span)

        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        core_lbl = f"{int(self.progress_pct)}%" if self.active_count > 0 else "IDLE"
        p.drawText(QRectF(core_cx - 16, core_cy - 8, 32, 16), Qt.AlignCenter, core_lbl)

        p.setPen(QColor(56, 189, 248) if self.active_count > 0 else QColor(148, 163, 184))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        spd_text = self.speed_str if self.active_count > 0 else "星流极客"
        p.drawText(QRectF(54, 10, 114, 18), Qt.AlignLeft | Qt.AlignVCenter, spd_text)

        p.setPen(QColor(148, 163, 184))
        p.setFont(QFont("Segoe UI", 8))
        status_txt = f"{self.active_count} 项正在下载" if self.active_count > 0 else f"共计 {self.total_count} 项任务"
        p.drawText(QRectF(54, 30, 114, 16), Qt.AlignLeft | Qt.AlignVCenter, status_txt)

    # =========================================================================
    # 皮肤 5: 用户自定义桌面形象挂件
    # =========================================================================
    def _draw_custom_mascot(self, p: QPainter):
        img_rect = QRectF(10, 15, 65, 65)
        if self._custom_pixmap and not self._custom_pixmap.isNull():
            scaled = self._custom_pixmap.scaled(
                65, 65, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            ox = int(10 + (65 - scaled.width()) / 2)
            oy = int(15 + (65 - scaled.height()) / 2)
            p.drawPixmap(ox, oy, scaled)
        else:
            p.setPen(QPen(QColor(148, 163, 184), 1, Qt.DashLine))
            p.setBrush(QColor(30, 41, 59, 180))
            p.drawRoundedRect(img_rect, 8, 8)
            p.setPen(QColor(226, 232, 240))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(img_rect, Qt.AlignCenter, "点击导入\n形象图片")

        bubble_rect = QRectF(80, 28, 74, 46)
        b_path = QPainterPath()
        b_path.addRoundedRect(bubble_rect, 10, 10)
        b_path.moveTo(80, 48)
        b_path.lineTo(74, 54)
        b_path.lineTo(80, 52)

        p.setPen(QPen(QColor(99, 102, 241, 180), 1.2))
        p.setBrush(QColor(15, 23, 42, 225))
        p.drawPath(b_path)

        p.setPen(QColor(56, 189, 248) if self.active_count > 0 else QColor(148, 163, 184))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        text_speed = self.speed_str if self.active_count > 0 else "就绪"
        p.drawText(QRectF(82, 32, 70, 18), Qt.AlignCenter, text_speed)

        p.setPen(QColor(203, 213, 225))
        p.setFont(QFont("Segoe UI", 7))
        text_sub = f"{self.active_count} 项正在下" if self.active_count > 0 else "星流挂件"
        p.drawText(QRectF(82, 48, 70, 18), Qt.AlignCenter, text_sub)

    # --- 鼠标拖拽移动与微面板弹出交互 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_global_pos = event.globalPos()
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._is_dragging = False
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if (event.globalPos() - self._press_global_pos).manhattanLength() > 5:
                self._is_dragging = True
                new_pos = event.globalPos() - self._drag_pos
                self.move(new_pos)
                if self._dashboard.isVisible():
                    self._reposition_dashboard()
                event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._is_dragging:
                # 纯粹单击: 切换展开/关闭监控与快捷工具面板
                self._toggle_dashboard()
            else:
                self._is_dragging = False
                config.set("floating_widget_x", self.x())
                config.set("floating_widget_y", self.y())

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.request_show_main.emit()

    def _toggle_dashboard(self):
        if self._dashboard.isVisible():
            self._dashboard.hide()
        else:
            self._reposition_dashboard()
            self._dashboard.refresh_data()
            self._dashboard.show()

    def _reposition_dashboard(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        panel_w = self._dashboard.width()
        panel_h = self._dashboard.height()

        if self.x() + self.width() + panel_w + 10 <= geo.right():
            target_x = self.x() + self.width() + 10
        elif self.x() - panel_w - 10 >= geo.left():
            target_x = self.x() - panel_w - 10
        else:
            target_x = geo.right() - panel_w - 20

        target_y = min(max(geo.top() + 10, self.y() - 20), geo.bottom() - panel_h - 10)
        self._dashboard.move(target_x, target_y)

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        # 皮肤形象切换子菜单
        skin_menu = menu.addMenu(get_icon("palette", "#38bdf8", 14), "挂件外观形象")

        act_core = skin_menu.addAction("星流 · 量子星核 (默认炫酷主题)")
        act_core.setCheckable(True)
        act_core.setChecked(self.skin == "starstream_core")
        act_core.triggered.connect(lambda: self._set_skin("starstream_core"))

        act_sphere = skin_menu.addAction("流光动态水球 (迅雷/IDM风格)")
        act_sphere.setCheckable(True)
        act_sphere.setChecked(self.skin == "water_sphere")
        act_sphere.triggered.connect(lambda: self._set_skin("water_sphere"))

        act_neon = skin_menu.addAction("极光赛博胶囊 (极简科技风格)")
        act_neon.setCheckable(True)
        act_neon.setChecked(self.skin == "neon_capsule")
        act_neon.triggered.connect(lambda: self._set_skin("neon_capsule"))

        act_fish = skin_menu.addAction("灵动大肥鱼 (萌宠风格)")
        act_fish.setCheckable(True)
        act_fish.setChecked(self.skin == "deepseek_fish")
        act_fish.triggered.connect(lambda: self._set_skin("deepseek_fish"))

        act_custom = skin_menu.addAction("自定义挂件形象...")
        act_custom.setCheckable(True)
        act_custom.setChecked(self.skin == "custom_mascot")
        act_custom.triggered.connect(lambda: self._set_skin("custom_mascot"))

        act_import = menu.addAction(get_icon("folder", "#a855f7", 14), "导入自定义挂件图片...")
        act_import.triggered.connect(self._action_import_custom_image)

        # 缩放倍率子菜单
        scale_menu = menu.addMenu(get_icon("monitor", "#38bdf8", 14), "挂件缩放比例")
        for sc, label in [(0.8, "小 (80%)"), (1.0, "标准 (100%)"), (1.2, "大 (120%)"), (1.5, "特大 (150%)")]:
            act_sc = scale_menu.addAction(label)
            act_sc.setCheckable(True)
            act_sc.setChecked(abs(self.scale_factor - sc) < 0.05)
            act_sc.triggered.connect(lambda checked, s=sc: self._set_scale(s))

        menu.addSeparator()

        act_panel = menu.addAction(get_icon("monitor", "#38bdf8", 14), "显示极速监控微面板")
        act_panel.triggered.connect(self._toggle_dashboard)

        act_top = menu.addAction(get_icon("check", "#38bdf8", 14), "窗口保持置顶")
        act_top.setCheckable(True)
        is_on_top = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        act_top.setChecked(is_on_top)
        act_top.triggered.connect(self._toggle_always_on_top)

        act_show = menu.addAction(get_icon("play", "#3875f6", 14), "打开星流主界面")
        act_show.triggered.connect(self.request_show_main.emit)

        menu.addSeparator()

        act_start_all = menu.addAction(get_icon("play", "#4ade80", 14), "全部开始下载")
        act_start_all.triggered.connect(self._action_start_all)

        act_pause_all = menu.addAction(get_icon("pause", "#f59e0b", 14), "全部暂停下载")
        act_pause_all.triggered.connect(self._action_pause_all)

        menu.addSeparator()

        act_hide = menu.addAction(get_icon("delete", "#f87171", 14), "关闭桌面悬浮窗")
        act_hide.triggered.connect(self.hide)

        menu.exec_(event.globalPos())

    def _set_skin(self, skin_name):
        self.skin = skin_name
        config.set("floating_skin", skin_name)
        self._update_widget_size()
        self.update()

    def _set_scale(self, scale_val):
        self.scale_factor = scale_val
        config.set("floating_scale", scale_val)
        self._update_widget_size()
        self.update()

    def _toggle_always_on_top(self):
        cur_flags = self.windowFlags()
        if cur_flags & Qt.WindowStaysOnTopHint:
            self.setWindowFlags(cur_flags & ~Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(cur_flags | Qt.WindowStaysOnTopHint)
        self.show()

    def _action_import_custom_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择您喜欢的桌面挂件形象 (推荐透明底 PNG/GIF/WebP)",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.ico);;所有文件 (*.*)"
        )
        if file_path and os.path.exists(file_path):
            self.custom_image_path = file_path
            config.set("floating_custom_image", file_path)
            self._load_custom_pixmap()
            self._set_skin("custom_mascot")
            QMessageBox.information(self, "导入成功", "已成功更换为您导入的挂件形象！")

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
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                self.move(geo.width() - 220, geo.height() // 2 - 60)
