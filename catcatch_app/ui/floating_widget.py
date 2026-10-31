"""
CatCatch Downloader - Advanced Vendor-Grade Floating Desktop Widget (大厂级多形态桌面挂件)
支持:
1. DeepSeek 灵动大肥鱼 (微表情/动态鱼鳍摆动/实时吐泡泡/拟真对话气泡)
2. 迅雷/IDM 流光动态水球 (双正弦流体液面动态浪涌/亚克力玻璃质感环/高精网速百分比)
3. 极光赛博霓虹胶囊 (赛博朋克发光描边/极客状态指标)
4. 用户自定义形象挂件 (支持导入任意 PNG/GIF/JPG/WebP/ICO 动漫宠物或大厂形象)
支持全量缩放调节 (80% ~ 150%)、拖拽移动、拖拽网址直连下载、全局置顶切换
"""
import math
import os
import random
from PyQt5.QtWidgets import (
    QWidget, QMenu, QAction, QApplication, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QPoint, QRectF, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QPixmap
)

from catcatch_app.core.config import config
from catcatch_app.core.task_manager import task_manager
from catcatch_app.ui.icons import get_icon, get_app_icon


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

        self._drag_pos = QPoint()
        self._is_dragging = False

        # 核心形态与尺寸设置
        self.skin = config.get("floating_skin", "deepseek_fish")
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

        self._load_custom_pixmap()
        self._update_widget_size()
        self._restore_position()

        # 高平滑度轻量定时动画 (约 30 FPS，仅纯数学计算重绘)
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
        base_w, base_h = 160, 95
        if self.skin == "water_sphere":
            base_w, base_h = 100, 100
        elif self.skin == "neon_capsule":
            base_w, base_h = 176, 58
        elif self.skin == "deepseek_fish":
            base_w, base_h = 170, 105
        elif self.skin == "custom_mascot":
            base_w, base_h = 160, 110

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

        if self.skin == "deepseek_fish":
            self._draw_deepseek_fish(painter)
        elif self.skin == "water_sphere":
            self._draw_water_sphere(painter)
        elif self.skin == "custom_mascot":
            self._draw_custom_mascot(painter)
        else:
            self._draw_neon_capsule(painter)

        painter.end()

    # =========================================================================
    # 皮肤 1: 🐳 DeepSeek 灵动大肥鱼 (官方萌鱼风格)
    # =========================================================================
    def _draw_deepseek_fish(self, p: QPainter):
        # 鱼身体摆动微位移
        wiggle = math.sin(self._anim_tick * 0.12) * (2.8 if self.active_count > 0 else 1.2)
        tail_rot = math.sin(self._anim_tick * 0.18) * 8.0

        fish_ox, fish_oy = 46, 58 + wiggle

        # 1. 动态气泡 (闲置少量漂浮，下载时大量吐出)
        for b in self._bubbles:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(147, 197, 253, int(b["alpha"] * 0.7)))
            p.drawEllipse(QPoint(int(b["x"]), int(b["y"])), int(b["r"]), int(b["r"]))
            # 高光点
            p.setBrush(QColor(255, 255, 255, 180))
            p.drawEllipse(QPoint(int(b["x"] - b["r"] * 0.3), int(b["y"] - b["r"] * 0.3)), 1, 1)

        # 2. 尾鳍 (带摆动角度变换)
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

        # 3. 肥鱼主躯干 (圆滚滚饱满椭圆)
        body_grad = QLinearGradient(fish_ox - 25, fish_oy - 25, fish_ox + 25, fish_oy + 25)
        body_grad.setColorAt(0, QColor(96, 165, 250))     # 天蓝色
        body_grad.setColorAt(0.6, QColor(59, 130, 246))   # 经典 DeepSeek 蓝
        body_grad.setColorAt(1, QColor(29, 78, 216))     # 深海蓝

        p.setPen(QPen(QColor(30, 64, 175, 180), 1.2))
        p.setBrush(body_grad)
        p.drawEllipse(QPoint(int(fish_ox), int(fish_oy)), 26, 20)

        # 4. 软乎乎白肚皮
        belly_path = QPainterPath()
        belly_path.moveTo(fish_ox - 18, fish_oy + 5)
        belly_path.cubicTo(fish_ox - 10, fish_oy + 18, fish_ox + 12, fish_oy + 18, fish_ox + 20, fish_oy + 4)
        belly_path.cubicTo(fish_ox + 10, fish_oy + 10, fish_ox - 8, fish_oy + 10, fish_ox - 18, fish_oy + 5)
        p.setBrush(QColor(239, 246, 255, 210))
        p.setPen(Qt.NoPen)
        p.drawPath(belly_path)

        # 5. 侧鱼鳍 (随波划动)
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

        # 6. 大肥鱼萌系大眼睛与可爱腮红
        eye_x, eye_y = int(fish_ox + 14), int(fish_oy - 4)
        # 腮红
        p.setBrush(QColor(244, 114, 182, 140))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPoint(eye_x - 3, eye_y + 9), 5, 3)

        # 眨眼逻辑 (每隔一段时间眨一下)
        is_blinking = (self._anim_tick % 120) < 6
        if is_blinking:
            p.setPen(QPen(QColor(15, 23, 42), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(eye_x - 4, eye_y, eye_x + 4, eye_y)
        else:
            p.setBrush(QColor(15, 23, 42))  # 瞳孔
            p.drawEllipse(QPoint(eye_x, eye_y), 4, 4)
            p.setBrush(QColor(255, 255, 255))  # 高光
            p.drawEllipse(QPoint(eye_x - 1, eye_y - 1), 2, 2)

        # 微笑小嘴巴
        mouth_path = QPainterPath()
        mouth_path.moveTo(fish_ox + 22, fish_oy + 1)
        mouth_path.quadTo(fish_ox + 24, fish_oy + 5, fish_ox + 21, fish_oy + 7)
        p.setPen(QPen(QColor(30, 58, 138), 1.4, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPath(mouth_path)

        # 7. 拟真对话气泡 (实时显示下载网速或空闲状态)
        bubble_rect = QRectF(78, 16, 84, 48)
        b_path = QPainterPath()
        b_path.addRoundedRect(bubble_rect, 10, 10)
        # 气泡尖角指向小鱼嘴巴
        b_path.moveTo(78, 40)
        b_path.lineTo(70, 48)
        b_path.lineTo(78, 46)

        p.setPen(QPen(QColor(59, 130, 246, 180), 1.2))
        p.setBrush(QColor(15, 23, 42, 230))
        p.drawPath(b_path)

        # 气泡内文字
        p.setPen(QColor(56, 189, 248) if self.active_count > 0 else QColor(148, 163, 184))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        text_speed = self.speed_str if self.active_count > 0 else "空闲游弋中"
        p.drawText(QRectF(82, 20, 76, 20), Qt.AlignCenter, text_speed)

        p.setPen(QColor(203, 213, 225))
        p.setFont(QFont("Segoe UI", 8))
        text_sub = f"{self.active_count} 项下载中" if self.active_count > 0 else f"{self.total_count} 项就绪"
        p.drawText(QRectF(82, 38, 76, 20), Qt.AlignCenter, text_sub)

    # =========================================================================
    # 皮肤 2: 🌊 迅雷/IDM 流光动态水球 (液面浪涌风格)
    # =========================================================================
    def _draw_water_sphere(self, p: QPainter):
        cx, cy, r = 50, 50, 42
        sphere_rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        # 外层深色科技底座与外发光
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 23, 42, 230))
        p.drawEllipse(sphere_rect)

        # 创建圆形裁切区，让内部波浪在球体内
        clip_path = QPainterPath()
        clip_path.addEllipse(sphere_rect)
        p.save()
        p.setClipPath(clip_path)

        # 计算水位高度 (下载时按平均进度或默认中位，空闲时低水位微晃)
        pct = self.progress_pct if self.active_count > 0 else 25.0
        water_y = (cy + r) - (pct / 100.0) * (r * 2)

        # 动态双正弦液浪波形
        wave_path = QPainterPath()
        wave_path.moveTo(cx - r - 5, cy + r + 5)
        step = 4
        x = cx - r - 5
        while x <= cx + r + 5:
            # 复合正弦波产生极自然的流体感
            y = water_y + math.sin(x * 0.1 + self._wave_phase) * 3.5 + math.cos(x * 0.06 - self._wave_phase * 0.8) * 2.0
            wave_path.lineTo(x, y)
            x += step
        wave_path.lineTo(cx + r + 5, cy + r + 5)
        wave_path.closeSubpath()

        # 水流渐变
        water_grad = QLinearGradient(cx, water_y - 10, cx, cy + r)
        if self.active_count > 0:
            water_grad.setColorAt(0, QColor(56, 189, 248, 220))   # 青蓝
            water_grad.setColorAt(1, QColor(37, 99, 235, 240))   # 靛蓝
        else:
            water_grad.setColorAt(0, QColor(52, 211, 153, 190))   # 翡翠绿 (就绪)
            water_grad.setColorAt(1, QColor(16, 185, 129, 220))

        p.setBrush(water_grad)
        p.setPen(Qt.NoPen)
        p.drawPath(wave_path)

        # 玻璃镜面弧光
        p.restore()
        glass_grad = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
        glass_grad.setColorAt(0, QColor(255, 255, 255, 90))
        glass_grad.setColorAt(0.4, QColor(255, 255, 255, 10))
        glass_grad.setColorAt(0.8, QColor(0, 0, 0, 40))
        glass_grad.setColorAt(1, QColor(56, 189, 248, 120))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(glass_grad, 2.5))
        p.drawEllipse(sphere_rect)

        # 球体中心网速与进度文字
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        speed_txt = self.speed_str if self.active_count > 0 else "0.0 B/s"
        p.drawText(QRectF(cx - r, cy - 14, r * 2, 16), Qt.AlignCenter, speed_txt)

        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(224, 242, 254) if self.active_count > 0 else QColor(167, 243, 208))
        status_txt = f"{self.progress_pct:.0f}%" if self.active_count > 0 else "READY"
        p.drawText(QRectF(cx - r, cy + 4, r * 2, 14), Qt.AlignCenter, status_txt)

    # =========================================================================
    # 皮肤 3: 💊 极光赛博霓虹胶囊 (现代 Cyberpunk 风格)
    # =========================================================================
    def _draw_neon_capsule(self, p: QPainter):
        rect = QRectF(2, 2, 172, 54)

        # 半透明磨砂深色底板
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 17, 23, 235))
        p.drawRoundedRect(rect, 16, 16)

        # 动态霓虹流动边框
        neon_grad = QLinearGradient(0, 0, 176, 58)
        color_shift = (self._anim_tick * 2) % 360
        neon_c1 = QColor.fromHsv(color_shift, 200, 255, 220)
        neon_c2 = QColor.fromHsv((color_shift + 120) % 360, 220, 255, 220)
        neon_grad.setColorAt(0, neon_c1)
        neon_grad.setColorAt(1, neon_c2)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(neon_grad, 1.6))
        p.drawRoundedRect(rect, 16, 16)

        # 左侧动态科技光环小图标
        icon_cx, icon_cy = 28, 29
        p.setBrush(QColor(30, 41, 59, 200))
        p.setPen(QPen(neon_c1, 1.2))
        p.drawEllipse(QPoint(icon_cx, icon_cy), 14, 14)

        # 呼吸光点
        glow_r = 4 + math.sin(self._anim_tick * 0.15) * 1.5
        p.setBrush(neon_c2)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPoint(icon_cx, icon_cy), int(glow_r), int(glow_r))

        # 右侧数值
        p.setPen(QColor(241, 245, 249))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(QRectF(52, 10, 115, 18), Qt.AlignLeft | Qt.AlignVCenter, self.speed_str)

        p.setPen(QColor(148, 163, 184))
        p.setFont(QFont("Segoe UI", 8))
        status_txt = f"⚡ {self.active_count} 个任务运行中" if self.active_count > 0 else f"✔ 总计 {self.total_count} 项"
        p.drawText(QRectF(52, 28, 115, 18), Qt.AlignLeft | Qt.AlignVCenter, status_txt)

    # =========================================================================
    # 皮肤 4: 🖼️ 自定义挂件形象 (用户导入图片/GIF/PNG)
    # =========================================================================
    def _draw_custom_mascot(self, p: QPainter):
        # 形象微摇动呼吸动画
        bob = math.sin(self._anim_tick * 0.1) * (2.2 if self.active_count > 0 else 1.0)
        img_rect = QRectF(10, 24 + bob, 64, 64)

        if self._custom_pixmap and not self._custom_pixmap.isNull():
            p.drawPixmap(img_rect.toRect(), self._custom_pixmap)
        else:
            # 提示未导入图片或图片无效时的占位绘制
            p.setPen(QPen(QColor(148, 163, 184), 1.2, Qt.DashLine))
            p.setBrush(QColor(30, 41, 59, 180))
            p.drawRoundedRect(img_rect, 10, 10)
            p.setPen(QColor(203, 213, 225))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(img_rect, Qt.AlignCenter, "点击导入\n形象图片")

        # 旁边挂载的亚克力气泡牌
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

        # 皮肤形象切换子菜单
        skin_menu = menu.addMenu(get_icon("palette", "#38bdf8", 14), "挂件外观形象")

        act_fish = skin_menu.addAction("🐳 灵动大肥鱼 (DeepSeek萌鱼风格)")
        act_fish.setCheckable(True)
        act_fish.setChecked(self.skin == "deepseek_fish")
        act_fish.triggered.connect(lambda: self._set_skin("deepseek_fish"))

        act_sphere = skin_menu.addAction("🌊 流光动态水球 (迅雷/IDM风格)")
        act_sphere.setCheckable(True)
        act_sphere.setChecked(self.skin == "water_sphere")
        act_sphere.triggered.connect(lambda: self._set_skin("water_sphere"))

        act_neon = skin_menu.addAction("💊 极光赛博胶囊 (极简科技风格)")
        act_neon.setCheckable(True)
        act_neon.setChecked(self.skin == "neon_capsule")
        act_neon.triggered.connect(lambda: self._set_skin("neon_capsule"))

        act_custom = skin_menu.addAction("🖼️ 自定义挂件形象...")
        act_custom.setCheckable(True)
        act_custom.setChecked(self.skin == "custom_mascot")
        act_custom.triggered.connect(lambda: self._set_skin("custom_mascot"))

        act_import = menu.addAction(get_icon("image", "#a855f7", 14), "导入自定义挂件图片...")
        act_import.triggered.connect(self._action_import_custom_image)

        # 缩放倍率子菜单
        scale_menu = menu.addMenu(get_icon("monitor", "#38bdf8", 14), "挂件缩放比例")
        for sc, label in [(0.8, "小 (80%)"), (1.0, "标准 (100%)"), (1.2, "大 (120%)"), (1.5, "特大 (150%)")]:
            act_sc = scale_menu.addAction(label)
            act_sc.setCheckable(True)
            act_sc.setChecked(abs(self.scale_factor - sc) < 0.05)
            act_sc.triggered.connect(lambda checked, s=sc: self._set_scale(s))

        menu.addSeparator()

        act_top = menu.addAction("📌 窗口保持置顶")
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
