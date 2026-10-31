"""
CatCatch Downloader - Main Window (现代专业 IDM 风格主控程序)
彻底去除 Emoji 符号，采用全矢量高精度 SVG 图标，集成全局多节点代理实时指示与切换
"""
import os
import re
import subprocess
import webbrowser
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QToolBar, QAction, QStatusBar, QLabel, QLineEdit, QMenu,
    QMessageBox, QHeaderView, QProgressBar, QSystemTrayIcon,
    QApplication, QPushButton, QDialog, QFileDialog, QToolButton,
    QSlider, QInputDialog, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QColor, QFont, QPainter, QPixmap

from catcatch_app.core.config import (
    config, get_nm3u8dl_status, NM3U8DL_RE_DOWNLOAD_URL,
    detect_local_active_proxies
)
from catcatch_app.core.task_manager import task_manager
from catcatch_app.core.server import local_server
from catcatch_app.core.ffmpeg_engine import is_ffmpeg_available, get_ffmpeg_path
from catcatch_app.core.download_file import format_size
from catcatch_app.ui.styles import DARK_THEME, THEMES, get_theme_stylesheet
from catcatch_app.ui.icons import get_icon, get_app_icon
from catcatch_app.ui.new_task_dialog import NewTaskDialog
from catcatch_app.ui.ffmpeg_toolbox_dialog import FFmpegToolboxDialog
from catcatch_app.ui.settings_dialog import SettingsDialog
from catcatch_app.ui.cache_clean_dialog import CacheCleanDialog
from catcatch_app.ui.fragments_dialog import FragmentsDialog
from catcatch_app.ui.batch_convert_dialog import BatchConvertDialog
from catcatch_app.ui.extension_tutorial_dialog import ExtensionTutorialDialog
from catcatch_app.ui.task_log_dialog import TaskLogDialog
from catcatch_app.ui.video_parser_dialog import VideoParserDialog
from catcatch_app.ui.notify_dialog import DownloadNotifyDialog
from catcatch_app.ui.floating_widget import FloatingWidget
from catcatch_app.ui.shutdown_dialog import ShutdownDialog
from catcatch_app.ui.mobile_connect_dialog import MobileConnectDialog
from catcatch_app.core.preview_engine import play_task_preview
from catcatch_app.core.logger import get_logs_dir, get_master_error_log_path


def parse_speed_to_bytes(spd_str):
    if not spd_str:
        return 0.0
    s = str(spd_str).strip()
    # 严格校验: 必须明确含有速率时间分母 /s, ps 或 bps，绝不可将纯文件大小 (如 1.60GB) 算作速率！
    if not re.search(r"(?:/s|ps|bps)", s, re.I):
        return 0.0
    m = re.search(r"([\d\.]+)\s*([KMGkmg]?)(?:i?[Bb])(?:/s|ps)", s, re.I)
    if m:
        try:
            val = float(m.group(1))
            unit = m.group(2).upper()
            factors = {"": 1, "K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}
            return val * factors.get(unit, 1)
        except Exception:
            return 0.0
    m2 = re.search(r"([\d\.]+)\s*(kbps|mbps|gbps|bps)", s, re.I)
    if m2:
        try:
            val = float(m2.group(1))
            unit = m2.group(2).lower()
            if unit == "kbps":
                return val / 8 * 1024
            elif unit == "mbps":
                return val / 8 * 1024 * 1024
            elif unit == "gbps":
                return val / 8 * 1024 * 1024 * 1024
            return val / 8
        except Exception:
            return 0.0
    return 0.0
    return 0.0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("星流媒体下载器 (StarStream Pro) v3.1.1 旗舰版")
        self.setWindowIcon(get_app_icon())
        self.resize(1180, 720)
        self._cached_bg_pixmap = None

        self.current_category = "all"
        self.search_keyword = ""
        self._active_notifiers = []

        self._init_ui()
        self._init_tray()
        self._connect_signals()
        self.apply_theme()

        self.refresh_table()

        # 初始化桌面极简悬浮小窗与手机扫码推流
        self.floating_widget = FloatingWidget(self)
        self.floating_widget.request_show_main.connect(self._restore_from_floating)
        self.floating_widget.request_new_task_url.connect(self._on_floating_new_task)
        self.floating_widget.request_open_batch_convert.connect(self._action_batch_convert)
        self.floating_widget.request_open_ffmpeg_toolbox.connect(self._action_ffmpeg_toolbox)
        self.floating_widget.request_open_video_parser.connect(self._action_open_video_parser)
        if config.get("show_floating_widget", False):
            self.floating_widget.show()

        # 启动后异步刷新底层引擎与代理状态，避免主线程初始化网络阻塞卡死
        QTimer.singleShot(0, self._async_init_status)

        self.speed_timer = QTimer(self)
        self.speed_timer.timeout.connect(self._update_status_stats)
        self.speed_timer.start(1000)

    def _async_init_status(self):
        self._update_ffmpeg_label()
        self._update_nm3u8dl_label()
        self._update_proxy_label()

    def _init_ui(self):
        # 1. 顶部专业工具栏
        self._create_toolbar()

        # 2. 中央主体分栏
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧导航分类树
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setFixedWidth(220)
        self._build_tree_nodes()
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_tree_item_clicked)
        splitter.addWidget(self.tree)

        # 右侧任务表格区域
        right_container = QWidget()
        right_container.setObjectName("rightContainer")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(6)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "序号", "任务名称", "规格/分辨率", "时长", "类型", "文件大小", "下载进度", "实时速度", "剩余时间", "状态", "添加时间"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 48)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 75)
        self.table.setColumnWidth(5, 95)
        self.table.setColumnWidth(6, 170)
        self.table.setColumnWidth(7, 95)
        self.table.setColumnWidth(8, 75)
        self.table.setColumnWidth(9, 85)
        self.table.setColumnWidth(10, 135)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        right_layout.addWidget(self.table)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter)
        self.setCentralWidget(central_widget)

        # 3. 底部状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lbl_server_status = QLabel("通信服务: 端口 18910 就绪")
        self.lbl_server_status.setStyleSheet("color: #4ade80; font-weight: 500; margin-left: 8px;")
        self.status_bar.addWidget(self.lbl_server_status)

        self.lbl_ffmpeg_status = QLabel("FFmpeg: 检测中...")
        self.lbl_ffmpeg_status.setStyleSheet("color: #71717a; margin-left: 14px;")
        self.status_bar.addWidget(self.lbl_ffmpeg_status)

        # N_m3u8DL 引擎状态指示交互按钮 (未检测到时醒目提示并一键直达下载)
        self.btn_nm3u8dl_status = QPushButton("下载引擎: 检测中...")
        self.btn_nm3u8dl_status.clicked.connect(self._on_nm3u8dl_status_clicked)
        self.status_bar.addWidget(self.btn_nm3u8dl_status)

        # 代理状态指示交互按钮
        self.btn_proxy_status = QPushButton("代理: 检测中...")
        self.btn_proxy_status.setIcon(get_icon("globe", "#9ca3af", 14))
        self.btn_proxy_status.setStyleSheet("border: none; background: transparent; color: #9ca3af; padding: 2px 6px; font-size: 12px;")
        self.btn_proxy_status.clicked.connect(self._action_settings)
        self.status_bar.addWidget(self.btn_proxy_status)

        self.lbl_stats = QLabel("任务: 0 项")
        self.lbl_stats.setStyleSheet("color: #71717a; margin-left: 12px;")
        self.status_bar.addWidget(self.lbl_stats)

        self.status_bar.addPermanentWidget(QLabel())

        # 计划电源管理: 全部完成后自动关机
        self.chk_auto_shutdown = QCheckBox("全部完成后自动关机")
        self.chk_auto_shutdown.setStyleSheet("color: #a1a1aa; font-size: 12px; margin-right: 14px;")
        self.chk_auto_shutdown.setChecked(config.get("auto_shutdown_on_finish", False))
        self.chk_auto_shutdown.toggled.connect(lambda v: config.set("auto_shutdown_on_finish", v))
        self.status_bar.addPermanentWidget(self.chk_auto_shutdown)

        self.lbl_global_speed = QLabel("0.00 KB/s")
        self.lbl_global_speed.setStyleSheet("color: #3875f6; font-weight: 600; font-size: 13px; margin-right: 12px;")
        self.status_bar.addPermanentWidget(self.lbl_global_speed)

    def _create_toolbar(self):
        toolbar = QToolBar("主操作栏")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        # 新建
        self.act_new = QAction(get_icon("add", "#f4f4f5", 18), "新建任务", self)
        self.act_new.setShortcut("Ctrl+N")
        self.act_new.triggered.connect(self._action_new_task)
        toolbar.addAction(self.act_new)

        # 全网短视频提取工作台
        self.act_parser = QAction(get_icon("zap", "#f59e0b", 18), "短视频提取", self)
        self.act_parser.setToolTip("全网主流短视频无水印解析提取 (抖音/快手/B站4K/小红书/网页视频等)")
        self.act_parser.triggered.connect(self._action_open_video_parser)
        toolbar.addAction(self.act_parser)

        toolbar.addSeparator()

        # 开始 / 暂停 / 删除
        self.act_start = QAction(get_icon("play", "#3875f6", 18), "开始", self)
        self.act_start.triggered.connect(self._action_start_selected)
        toolbar.addAction(self.act_start)

        self.act_pause = QAction(get_icon("pause", "#d4d4d8", 18), "暂停", self)
        self.act_pause.triggered.connect(self._action_pause_selected)
        toolbar.addAction(self.act_pause)

        self.act_delete = QAction(get_icon("delete", "#f87171", 18), "删除", self)
        self.act_delete.setShortcut("Delete")
        self.act_delete.triggered.connect(self._action_delete_selected)
        toolbar.addAction(self.act_delete)

        toolbar.addSeparator()

        # 打开所在文件夹
        self.act_open_dir = QAction(get_icon("folder", "#d4d4d8", 18), "打开目录", self)
        self.act_open_dir.triggered.connect(self._action_open_dir)
        toolbar.addAction(self.act_open_dir)

        # 临时分片文件夹管理
        self.act_fragments = QAction(get_icon("stream", "#38bdf8", 18), "分片管理", self)
        self.act_fragments.setToolTip("查看和整理临时分片存放文件夹 (Temp_Segments)，支持查看与删除残留切片")
        self.act_fragments.triggered.connect(self._action_manage_fragments)
        toolbar.addAction(self.act_fragments)

        # FFmpeg 工具箱
        self.act_ffmpeg = QAction(get_icon("toolbox", "#d4d4d8", 18), "FFmpeg 工具箱", self)
        self.act_ffmpeg.triggered.connect(self._action_ffmpeg_toolbox)
        toolbar.addAction(self.act_ffmpeg)

        # 批量格式转换
        self.act_batch = QAction(get_icon("refresh", "#38bdf8", 18), "批量转换", self)
        self.act_batch.setToolTip("批量媒体格式转换中心 (支持 MP4/MKV/TS/MP3/M4A 等多格式批量互转与极速无损封装)")
        self.act_batch.triggered.connect(self._action_batch_convert)
        toolbar.addAction(self.act_batch)

        # 清理缓存
        self.act_clean = QAction(get_icon("clean", "#d4d4d8", 18), "清理缓存", self)
        self.act_clean.triggered.connect(self._action_clean_cache)
        toolbar.addAction(self.act_clean)

        # 错误日志
        self.act_view_errors = QAction(get_icon("log", "#38bdf8", 18), "错误日志", self)
        self.act_view_errors.setToolTip("查看下载错误汇总日志与排查诊断 (Logs/download_errors.log)")
        self.act_view_errors.triggered.connect(self._action_open_master_error_log)
        toolbar.addAction(self.act_view_errors)

        # 浏览器扩展安装教学
        self.act_ext = QAction(get_icon("extension", "#38bdf8", 18), "插件安装教学", self)
        self.act_ext.setToolTip("查看星流媒体嗅探器在 Chrome / Edge 等浏览器中的安装与配置教学")
        self.act_ext.triggered.connect(self._action_extension_tutorial)
        toolbar.addAction(self.act_ext)

        # 桌面极简悬浮小窗
        self.act_floating = QAction(get_icon("monitor", "#38bdf8", 18), "桌面悬浮窗", self)
        self.act_floating.setToolTip("开启/关闭桌面极简下载悬浮小窗 (支持拖拽链接直接下载)")
        self.act_floating.triggered.connect(self._toggle_floating_widget)
        toolbar.addAction(self.act_floating)

        # 手机无线推流
        self.act_mobile = QAction(get_icon("phone", "#22c55e", 18), "手机扫码推流", self)
        self.act_mobile.setToolTip("显示手机局域网扫码推流二维码与控制台网页")
        self.act_mobile.triggered.connect(self._action_show_mobile_connect)
        toolbar.addAction(self.act_mobile)

        # 视频下载免责声明
        self.act_disclaimer = QAction(get_icon("info", "#d4d4d8", 18), "免责声明", self)
        self.act_disclaimer.setToolTip("查看视频下载合法合规使用与免责声明")
        self.act_disclaimer.triggered.connect(self._action_show_disclaimer)
        toolbar.addAction(self.act_disclaimer)

        toolbar.addSeparator()

        # 主题皮肤与背景壁纸
        self.btn_theme = QToolButton(self)
        self.btn_theme.setIcon(get_icon("palette", "#38bdf8", 18))
        self.btn_theme.setText("主题皮肤")
        self.btn_theme.setToolTip("快速切换界面主题风格与自定义背景壁纸")
        self.btn_theme.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_theme.setPopupMode(QToolButton.InstantPopup)
        self.btn_theme.setMenu(self._create_theme_menu())
        toolbar.addWidget(self.btn_theme)

        toolbar.addSeparator()

        # 设置
        self.act_settings = QAction(get_icon("settings", "#d4d4d8", 18), "设置", self)
        self.act_settings.triggered.connect(self._action_settings)
        toolbar.addAction(self.act_settings)

        # 搜索框
        spacer = QWidget()
        spacer.setFixedWidth(20)
        toolbar.addWidget(spacer)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索任务名称或网址...")
        self.search_edit.setFixedWidth(220)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self.search_edit)

    def _build_tree_nodes(self):
        self.tree.clear()

        # 分类大项
        cat_root = QTreeWidgetItem(self.tree, ["任务分类"])
        cat_root.setIcon(0, get_icon("folder", "#71717a", 16))
        cat_root.setExpanded(True)

        self.node_all = QTreeWidgetItem(cat_root, ["全部任务", "all"])
        self.node_all.setIcon(0, get_icon("file", "#a1a1aa", 16))

        self.node_downloading = QTreeWidgetItem(cat_root, ["正在下载", "downloading"])
        self.node_downloading.setIcon(0, get_icon("download", "#3875f6", 16))

        self.node_completed = QTreeWidgetItem(cat_root, ["已完成", "completed"])
        self.node_completed.setIcon(0, get_icon("check", "#4ade80", 16))

        self.node_paused = QTreeWidgetItem(cat_root, ["已暂停", "paused"])
        self.node_paused.setIcon(0, get_icon("pause", "#a1a1aa", 16))

        self.node_error = QTreeWidgetItem(cat_root, ["下载失败", "error"])
        self.node_error.setIcon(0, get_icon("alert", "#f87171", 16))

        # 格式媒体大项
        type_root = QTreeWidgetItem(self.tree, ["媒体类型"])
        type_root.setIcon(0, get_icon("toolbox", "#71717a", 16))
        type_root.setExpanded(True)

        self.node_m3u8 = QTreeWidgetItem(type_root, ["流媒体 (M3U8 / DASH)", "m3u8"])
        self.node_m3u8.setIcon(0, get_icon("stream", "#a1a1aa", 16))

        self.node_video = QTreeWidgetItem(type_root, ["视频文件 (MP4 / WebM)", "video"])
        self.node_video.setIcon(0, get_icon("video", "#a1a1aa", 16))

        self.node_audio = QTreeWidgetItem(type_root, ["音频文件 (MP3 / AAC)", "audio"])
        self.node_audio.setIcon(0, get_icon("audio", "#a1a1aa", 16))

        self.node_file = QTreeWidgetItem(type_root, ["常规文件", "file"])
        self.node_file.setIcon(0, get_icon("file", "#a1a1aa", 16))

        # 便捷工具大项
        tools_root = QTreeWidgetItem(self.tree, ["常用工具"])
        tools_root.setIcon(0, get_icon("toolbox", "#71717a", 16))
        tools_root.setExpanded(True)

        self.node_parser = QTreeWidgetItem(tools_root, ["短视频提取工作台", "tool_parser"])
        self.node_parser.setIcon(0, get_icon("zap", "#f59e0b", 16))

        self.node_batch = QTreeWidgetItem(tools_root, ["批量格式转换", "tool_batch"])
        self.node_batch.setIcon(0, get_icon("refresh", "#38bdf8", 16))

        self.node_ffmpeg = QTreeWidgetItem(tools_root, ["FFmpeg 工具箱", "tool_ffmpeg"])
        self.node_ffmpeg.setIcon(0, get_icon("toolbox", "#d4d4d8", 16))

        self.tree.setCurrentItem(self.node_all)

    def _init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(get_app_icon())
        self.tray.setToolTip("星流媒体下载器 (StarStream Pro)")

        tray_menu = QMenu()
        act_show = QAction("显示主界面", self)
        act_show.triggered.connect(self._restore_and_activate)
        act_new = QAction("新建下载...", self)
        act_new.triggered.connect(self._action_new_task)
        act_clean = QAction("清理缓存...", self)
        act_clean.triggered.connect(self._action_clean_cache)
        act_ff = QAction("FFmpeg 工具箱", self)
        act_ff.triggered.connect(self._action_ffmpeg_toolbox)
        act_quit = QAction("退出程序", self)
        act_quit.triggered.connect(self.quit_app)

        tray_menu.addAction(act_show)
        tray_menu.addAction(act_new)
        tray_menu.addAction(act_clean)
        act_ext = QAction("插件安装与使用教学...", self)
        act_ext.triggered.connect(self._action_extension_tutorial)
        tray_menu.addAction(act_ext)
        tray_menu.addAction(act_ff)
        tray_menu.addSeparator()
        tray_menu.addAction(act_quit)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _restore_and_activate(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._restore_and_activate()

    def closeEvent(self, event):
        if config.get("close_to_tray", True):
            event.ignore()
            self.hide()
            if hasattr(self, 'tray') and self.tray.isVisible():
                self.tray.showMessage(
                    "星流媒体下载器",
                    "程序已最小化到系统托盘，双击托盘图标可重新打开",
                    QSystemTrayIcon.Information,
                    2000
                )
        else:
            event.accept()
            self.quit_app()

    def quit_app(self):
        """安全彻底退出应用，确保保存所有状态并释放端口"""
        try:
            local_server.stop()
        except Exception:
            pass
        try:
            task_manager.save_tasks()
        except Exception:
            pass
        QApplication.instance().quit()

    def _connect_signals(self):
        task_manager.task_added.connect(self._on_task_added)
        task_manager.task_updated.connect(self._on_task_updated)
        task_manager.task_status_changed.connect(self._on_task_status_changed)
        task_manager.task_completed.connect(self._on_task_completed)
        task_manager.task_failed.connect(self._on_task_failed)
        task_manager.task_removed.connect(self._on_task_removed)

    def _update_ffmpeg_label(self):
        ok, msg = is_ffmpeg_available()
        if ok:
            self.lbl_ffmpeg_status.setText("FFmpeg: 就绪")
            self.lbl_ffmpeg_status.setStyleSheet("color: #4ade80; margin-left: 14px;")
        else:
            self.lbl_ffmpeg_status.setText("FFmpeg: 未就绪")
            self.lbl_ffmpeg_status.setStyleSheet("color: #f87171; margin-left: 14px;")

    def _update_nm3u8dl_label(self):
        status = get_nm3u8dl_status()
        if status["found"]:
            eng = status["engine"] or "RE"
            self.btn_nm3u8dl_status.setText(f"✓ N_m3u8DL: 就绪 ({eng})")
            self.btn_nm3u8dl_status.setStyleSheet(
                "border: none; background: transparent; color: #4ade80; font-weight: 500; margin-left: 14px; padding: 2px 6px; font-size: 12px;"
            )
            self.btn_nm3u8dl_status.setToolTip(f"当前下载引擎路径:\n{status['active_path']}\n点击可在设置中切换或查看详情")
        else:
            self.btn_nm3u8dl_status.setText("⚠️ 未检测到 N_m3u8DL 引擎 (点击下载最新版)")
            self.btn_nm3u8dl_status.setStyleSheet(
                "border: 1px solid #f59e0b; background: rgba(245, 158, 11, 0.15); color: #fbbf24; font-weight: 600; border-radius: 4px; margin-left: 14px; padding: 2px 8px; font-size: 12px;"
            )
            self.btn_nm3u8dl_status.setToolTip("星流下载器未检测到 N_m3u8DL 外部流媒体下载引擎！\n点击立即前往 GitHub 获取最新版发布包或手动指定路径。")

    def _on_nm3u8dl_status_clicked(self):
        status = get_nm3u8dl_status()
        if not status["found"]:
            self._show_nm3u8dl_download_dialog(status)
        else:
            self._action_settings()

    def _show_nm3u8dl_download_dialog(self, status=None):
        if status is None:
            status = get_nm3u8dl_status()
        dlg = QDialog(self)
        dlg.setWindowTitle("获取最新版本 N_m3u8DL-RE 引擎 - 星流下载器")
        dlg.setWindowIcon(get_app_icon())
        dlg.setFixedWidth(560)
        l = QVBoxLayout(dlg)
        l.setSpacing(12)

        t_lbl = QLabel("未检测到 N_m3u8DL 外部流媒体下载引擎")
        t_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #f59e0b;")
        l.addWidget(t_lbl)

        d_lbl = QLabel(
            "星流媒体下载器推荐搭配由 nilaoda 开发的开源高性能切片下载引擎 N_m3u8DL-RE。\n\n"
            "官方最新发布包原生支持多线程分片抓取、实时速率上报与高质量音频画面混流封装。\n"
            "下载解压后，请将 N_m3u8DL-RE.exe 放入软件根目录，或点击下方「指定已有程序」即可！"
        )
        d_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.5;")
        l.addWidget(d_lbl)

        btn_row = QHBoxLayout()
        btn_github = QPushButton("🌐 前往 GitHub 下载最新版 (N_m3u8DL-RE)")
        btn_github.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: 600; padding: 8px 16px;")
        btn_github.clicked.connect(lambda: webbrowser.open(NM3U8DL_RE_DOWNLOAD_URL))
        btn_row.addWidget(btn_github)

        btn_mirror = QPushButton("⚡ 加速镜像站")
        btn_mirror.setStyleSheet("background-color: #1e293b; color: #38bdf8; border: 1px solid #334155; padding: 8px 12px;")
        btn_mirror.clicked.connect(lambda: webbrowser.open(status.get("mirror_url", NM3U8DL_RE_DOWNLOAD_URL)))
        btn_row.addWidget(btn_mirror)
        l.addLayout(btn_row)

        action_box = QHBoxLayout()
        btn_pick = QPushButton("📂 我已下载，指定 exe 路径...")
        btn_pick.setStyleSheet("background-color: #334155; color: #ffffff; padding: 6px 14px;")
        
        def _pick_file():
            f, _ = QFileDialog.getOpenFileName(dlg, "选择 N_m3u8DL 可执行程序", os.getcwd(), "Executable (*.exe);;All Files (*)")
            if f and os.path.exists(f):
                if "RE" in os.path.basename(f).upper():
                    config.set("re_cli_path", f)
                    config.set("stream_engine", "RE")
                else:
                    config.set("v3_cli_path", f)
                    config.set("stream_engine", "V3")
                self._update_nm3u8dl_label()
                QMessageBox.information(dlg, "配置成功", f"已成功指定下载引擎:\n{f}")
                dlg.accept()

        btn_pick.clicked.connect(_pick_file)
        action_box.addWidget(btn_pick)

        btn_scan = QPushButton("🔄 重新扫描全盘")
        def _do_rescan():
            new_st = config.rescan_tools()
            self._update_nm3u8dl_label()
            if new_st["found"]:
                QMessageBox.information(dlg, "扫描结果", f"成功找到 N_m3u8DL 引擎:\n{new_st['active_path']}")
                dlg.accept()
            else:
                QMessageBox.warning(dlg, "未找到", "全盘扫描未能在常见目录或 PATH 中找到 N_m3u8DL-RE.exe 或 N_m3u8DL-CLI.exe。\n请点击上方按钮前往 GitHub 下载。")

        btn_scan.clicked.connect(_do_rescan)
        action_box.addWidget(btn_scan)
        l.addLayout(action_box)

        btn_close = QPushButton("稍后处理 (使用内置 Python 引擎下载)")
        btn_close.clicked.connect(dlg.reject)
        l.addWidget(btn_close)

        dlg.exec_()

    def _update_proxy_label(self):
        mode = config.get("proxy_mode", "none")
        if mode == "none":
            self.btn_proxy_status.setText("代理: 直连")
        elif mode == "system":
            self.btn_proxy_status.setText("代理: 跟随系统")
        else:
            active_p = config.get_effective_proxy(validate=False)
            self.btn_proxy_status.setText(f"代理: {active_p if active_p else '直连'}")

    def _on_tree_item_clicked(self, item, col):
        code = item.text(1)
        if not code:
            return
        if code == "tool_parser":
            self._action_open_video_parser()
            return
        elif code == "tool_batch":
            self._action_batch_convert()
            return
        elif code == "tool_ffmpeg":
            self._action_ffmpeg_toolbox()
            return
        self.current_category = code
        self.refresh_table()

    def _on_search_text_changed(self, text):
        self.search_keyword = text.strip().lower()
        self.refresh_table()

    def _filter_task(self, t):
        status = t.get("status")
        media = t.get("media_type")

        if self.current_category == "all":
            pass
        elif self.current_category in ["downloading", "completed", "paused", "error"]:
            if status != self.current_category:
                return False
        elif self.current_category in ["m3u8", "video", "audio", "file"]:
            if media != self.current_category:
                return False

        if self.search_keyword:
            name = (t.get("title") or "").lower()
            url = (t.get("url") or "").lower()
            if self.search_keyword not in name and self.search_keyword not in url:
                return False

        return True

    def refresh_table(self):
        tasks = task_manager.get_all_tasks()
        filtered = [t for t in tasks if self._filter_task(t)]

        self.table.setRowCount(len(filtered))
        for row, t in enumerate(filtered):
            self._render_row(row, t)

    def _render_row(self, row, t):
        # 0. 序号
        item_id = QTableWidgetItem(str(row + 1))
        item_id.setTextAlignment(Qt.AlignCenter)
        item_id.setData(Qt.UserRole, t["id"])
        self.table.setItem(row, 0, item_id)

        # 1. 任务名称
        title = t.get("title") or t.get("save_name") or "未命名"
        item_title = QTableWidgetItem(title)
        item_title.setToolTip(t.get("url", ""))
        self.table.setItem(row, 1, item_title)

        # 2. 规格/分辨率
        res = t.get("resolution", "")
        item_res = QTableWidgetItem(res if res else "-")
        item_res.setTextAlignment(Qt.AlignCenter)
        if "4K" in res or "2160" in res:
            item_res.setForeground(QColor("#f43f5e"))
            item_res.setFont(QFont("Segoe UI", 9, QFont.Bold))
        elif "1080" in res:
            item_res.setForeground(QColor("#a855f7"))
            item_res.setFont(QFont("Segoe UI", 9, QFont.Bold))
        elif "720" in res:
            item_res.setForeground(QColor("#38bdf8"))
        else:
            item_res.setForeground(QColor("#9ca3af"))
        self.table.setItem(row, 2, item_res)

        # 3. 视频时长
        dur = t.get("duration", "")
        item_dur = QTableWidgetItem(dur if dur else "-")
        item_dur.setTextAlignment(Qt.AlignCenter)
        item_dur.setForeground(QColor("#cbd5e1"))
        self.table.setItem(row, 3, item_dur)

        # 4. 类型
        mtype = t.get("media_type", "file").upper()
        item_type = QTableWidgetItem(f"[{mtype}]")
        item_type.setTextAlignment(Qt.AlignCenter)
        if mtype == "M3U8":
            item_type.setForeground(QColor("#a78bfa"))
        elif mtype in ["VIDEO", "MP4"]:
            item_type.setForeground(QColor("#3875f6"))
        elif mtype in ["AUDIO", "MP3"]:
            item_type.setForeground(QColor("#34d399"))
        self.table.setItem(row, 4, item_type)

        # 5. 文件大小
        tot = t.get("total_bytes", 0)
        cur = t.get("downloaded_bytes", 0)
        cur_p = t.get("cur_parts", 0)
        tot_p = t.get("tot_parts", 0)
        st_val = t.get("status", "waiting")

        if st_val == "downloading" and cur > 0:
            p_info = f" ({cur_p}/{tot_p})" if tot_p > 0 else ""
            if tot > cur:
                size_str = f"{format_size(cur)} / ~{format_size(tot)}{p_info}"
            else:
                size_str = f"{format_size(cur)}{p_info}"
        elif tot > 0:
            size_str = format_size(tot)
        else:
            size_str = "未知"

        item_size = QTableWidgetItem(size_str)
        item_size.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 5, item_size)

        # 6. 下载进度条
        prog = float(t.get("progress", 0.0))
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(prog))
        pbar.setFormat(f"{prog:.1f}%")
        pbar.setTextVisible(True)
        self.table.setCellWidget(row, 6, pbar)

        # 7. 实时下载速度
        spd_str = t.get("speed", "")
        item_spd = QTableWidgetItem(spd_str)
        item_spd.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item_spd.setForeground(QColor("#38bdf8"))
        self.table.setItem(row, 7, item_spd)

        # 8. 剩余时间
        item_eta = QTableWidgetItem(t.get("eta", ""))
        item_eta.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 8, item_eta)

        # 9. 状态
        status = t.get("status", "waiting")
        status_map = {
            "waiting": ("等待中", "#fbbf24"),
            "downloading": ("下载中", "#3875f6"),
            "paused": ("已暂停", "#9ca3af"),
            "completed": ("已完成", "#4ade80"),
            "error": ("失败", "#f87171")
        }
        text_status, color_status = status_map.get(status, (status, "#e4e4e7"))
        item_st = QTableWidgetItem(text_status)
        item_st.setTextAlignment(Qt.AlignCenter)
        item_st.setForeground(QColor(color_status))

        if status == "error":
            err_title = t.get("error_reason") or t.get("error_msg") or "下载异常"
            err_hint = t.get("error_hint", "")
            tip = f"【失败原因】\n{err_title}"
            if err_hint:
                tip += f"\n\n【排查建议】\n{err_hint}"
            tip += "\n\n(双击此任务或右键菜单可查看详细运行日志与诊断)"
            item_st.setToolTip(tip)
        else:
            item_st.setToolTip("")

        self.table.setItem(row, 9, item_st)

        # 10. 添加时间
        item_time = QTableWidgetItem(t.get("created_at", ""))
        item_time.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 10, item_time)

    def _find_row_by_task_id(self, task_id):
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.data(Qt.UserRole) == task_id:
                return r
        return -1

    def _get_selected_task_ids(self):
        selected_rows = set()
        for idx in self.table.selectedIndexes():
            selected_rows.add(idx.row())
        ids = []
        for r in sorted(selected_rows):
            it = self.table.item(r, 0)
            if it:
                ids.append(it.data(Qt.UserRole))
        return ids

    def _on_task_added(self, task):
        self.refresh_table()

    def _on_task_updated(self, task_id, task):
        row = self._find_row_by_task_id(task_id)
        if row >= 0:
            # 6: 进度条
            pbar = self.table.cellWidget(row, 6)
            if pbar:
                prog = float(task.get("progress", 0.0))
                pbar.setValue(int(prog))
                pbar.setFormat(f"{prog:.1f}%")
            
            # 7: 实时速度
            it_spd = self.table.item(row, 7)
            if it_spd:
                it_spd.setText(task.get("speed", ""))
            
            # 8: 剩余时间
            it_eta = self.table.item(row, 8)
            if it_eta:
                it_eta.setText(task.get("eta", ""))

            # 5: 文件大小
            tot = task.get("total_bytes", 0)
            cur = task.get("downloaded_bytes", 0)
            cur_p = task.get("cur_parts", 0)
            tot_p = task.get("tot_parts", 0)
            it_sz = self.table.item(row, 5)
            if it_sz:
                st_val = task.get("status", "waiting")
                if st_val == "downloading" and cur > 0:
                    p_info = f" ({cur_p}/{tot_p})" if tot_p > 0 else ""
                    if tot > cur:
                        it_sz.setText(f"{format_size(cur)} / ~{format_size(tot)}{p_info}")
                    else:
                        it_sz.setText(f"{format_size(cur)}{p_info}")
                elif tot > 0:
                    it_sz.setText(format_size(tot))

            # 2: 规格/分辨率
            res = task.get("resolution", "")
            if res:
                it_res = self.table.item(row, 2)
                if it_res and it_res.text() in ["-", ""]:
                    it_res.setText(res)
                    if "4K" in res or "2160" in res:
                        it_res.setForeground(QColor("#f43f5e"))
                        it_res.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    elif "1080" in res:
                        it_res.setForeground(QColor("#a855f7"))
                        it_res.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    elif "720" in res:
                        it_res.setForeground(QColor("#38bdf8"))

            # 3: 视频时长
            dur = task.get("duration", "")
            if dur:
                it_dur = self.table.item(row, 3)
                if it_dur and it_dur.text() in ["-", ""]:
                    it_dur.setText(dur)

    def _on_task_status_changed(self, task_id, new_status):
        self.refresh_table()

    def _on_task_completed(self, task_id, output_path):
        self.refresh_table()
        task = task_manager.get_task(task_id)
        title = task.get("title") if task else "任务"

        if config.get("notify_on_complete", True):
            self.tray.showMessage(
                "星流 - 下载完成",
                f"{title} 已成功下载并合并完毕",
                QSystemTrayIcon.Information,
                4000
            )

        # 屏幕右下角现代化桌面弹窗提醒
        if task:
            try:
                notifier = DownloadNotifyDialog(task, is_success=True, parent=self)
                self._active_notifiers.append(notifier)
                notifier.show()
            except Exception as e:
                print(f"[Notifier] 弹窗展示异常: {e}")

        # 检查是否全部下载完成并触发计划关机
        if hasattr(self, "chk_auto_shutdown") and self.chk_auto_shutdown.isChecked():
            all_ts = task_manager.get_all_tasks()
            active_or_waiting = [t for t in all_ts if t.get("status") in ["downloading", "waiting"]]
            if not active_or_waiting:
                try:
                    sd = ShutdownDialog(self)
                    sd.exec_()
                except Exception as e:
                    print(f"[AutoShutdown] 触发异常: {e}")

    def _on_task_failed(self, task_id, error_msg):
        self.refresh_table()
        task = task_manager.get_task(task_id)
        title = task.get("title") if task else "任务"
        err_reason = task.get("error_reason") or error_msg or "下载遇到异常"

        if config.get("notify_on_error", True):
            self.tray.showMessage(
                "星流 - 下载失败",
                f"{title}\n原因: {err_reason}",
                QSystemTrayIcon.Warning,
                5000
            )

        # 屏幕右下角现代化桌面弹窗提醒
        if task:
            try:
                notifier = DownloadNotifyDialog(task, is_success=False, parent=self)
                self._active_notifiers.append(notifier)
                notifier.show()
            except Exception as e:
                print(f"[Notifier] 弹窗展示异常: {e}")

    def _on_task_removed(self, task_id):
        self.refresh_table()

    def _update_status_stats(self):
        tasks = task_manager.get_all_tasks()
        total_tasks = len(tasks)
        downloading_tasks = [t for t in tasks if t["status"] == "downloading"]
        active_count = len(downloading_tasks)
        completed_count = sum(1 for t in tasks if t["status"] == "completed")

        self.lbl_stats.setText(f"总计: {total_tasks} | 下载中: {active_count} | 已完成: {completed_count}")

        total_speed_bytes = sum(parse_speed_to_bytes(t.get("speed", "")) for t in downloading_tasks)
        if total_speed_bytes > 0:
            sp_display = f"总下载速度: {format_size(total_speed_bytes)}/s"
            self.lbl_global_speed.setText(sp_display)
        else:
            speeds = [t.get("speed", "") for t in downloading_tasks if t.get("speed")]
            if speeds:
                sp_display = f"总下载速度: {' + '.join(speeds[:2])}"
                self.lbl_global_speed.setText(sp_display)
            else:
                sp_display = "0.00 KB/s"
                self.lbl_global_speed.setText("0.00 KB/s")

        # 同步悬浮窗实时网速与任务统计
        if hasattr(self, "floating_widget") and self.floating_widget.isVisible():
            self.floating_widget.update_stats(sp_display.replace("总下载速度: ", ""), active_count, total_tasks)

    def _show_context_menu(self, pos):
        ids = self._get_selected_task_ids()
        if not ids:
            return

        menu = QMenu(self)
        act_run = menu.addAction(get_icon("play", "#3875f6", 14), "立即开始 / 恢复")
        act_run.triggered.connect(self._action_start_selected)

        act_pau = menu.addAction(get_icon("pause", "#d4d4d8", 14), "暂停任务")
        act_pau.triggered.connect(self._action_pause_selected)

        menu.addSeparator()

        # --- 针对选中任务的独立代理切换子菜单 ---
        menu_proxy = menu.addMenu(get_icon("globe", "#38bdf8", 14), "切换下载代理节点")

        act_direct = menu_proxy.addAction(get_icon("check", "#a1a1aa", 12), "直连 (不使用任何代理)")
        act_direct.triggered.connect(lambda: self._set_proxy_for_selected(ids, "DIRECT"))

        eff_p = config.get_effective_proxy()
        eff_desc = f"跟随全局设置 ({eff_p if eff_p else '直连'})"
        act_global = menu_proxy.addAction(get_icon("settings", "#a1a1aa", 12), eff_desc)
        act_global.triggered.connect(lambda: self._set_proxy_for_selected(ids, "GLOBAL"))

        menu_proxy.addSeparator()

        proxies_list = config.get_proxies_list()
        for p in proxies_list:
            p_name = p.get("name", "代理")
            p_url = p.get("url", "")
            act_p = menu_proxy.addAction(get_icon("link", "#38bdf8", 12), f"{p_name} ({p_url})")
            act_p.triggered.connect(lambda checked=False, u=p_url: self._set_proxy_for_selected(ids, u))

        actives = detect_local_active_proxies()
        if actives:
            menu_proxy.addSeparator()
            for act in actives:
                if not any(p.get("url") == act["url"] for p in proxies_list):
                    act_local = menu_proxy.addAction(get_icon("zap", "#22c55e", 12), f"在线: {act['name']} ({act['url']})")
                    act_local.triggered.connect(lambda checked=False, u=act["url"]: self._set_proxy_for_selected(ids, u))

        menu_proxy.addSeparator()
        act_custom = menu_proxy.addAction(get_icon("edit", "#f59e0b", 12), "输入自定义代理地址...")
        act_custom.triggered.connect(lambda: self._prompt_custom_proxy_for_selected(ids))

        menu.addSeparator()

        # --- 边下边播实时画面预览 (针对下载中/有临时分片未完成的任务) ---
        act_preview = menu.addAction(get_icon("play", "#38bdf8", 14), "边下边播 (实时画面快速预览)")
        act_preview.triggered.connect(self._action_preview_selected)

        menu.addSeparator()

        act_open_f = menu.addAction(get_icon("video", "#d4d4d8", 14), "打开播放文件")
        act_open_f.triggered.connect(self._action_play_file)

        act_open_d = menu.addAction(get_icon("folder", "#d4d4d8", 14), "打开所在目录")
        act_open_d.triggered.connect(self._action_open_dir)

        menu.addSeparator()

        act_ff = menu.addAction(get_icon("toolbox", "#d4d4d8", 14), "FFmpeg 视音频处理 (转码/提取/修复)")
        act_ff.triggered.connect(self._action_ffmpeg_toolbox_for_selected)

        act_batch = menu.addAction(get_icon("refresh", "#38bdf8", 14), "批量格式转换选中的媒体...")
        act_batch.triggered.connect(self._action_batch_convert_for_selected)

        act_copy = menu.addAction(get_icon("copy", "#d4d4d8", 14), "复制下载链接")
        act_copy.triggered.connect(self._action_copy_url)

        menu.addSeparator()

        act_log = menu.addAction(get_icon("log", "#38bdf8", 14), "查看任务日志与错误诊断...")
        act_log.triggered.connect(self._action_view_task_log)

        menu.addSeparator()

        act_del = menu.addAction(get_icon("delete", "#f87171", 14), "从列表中删除")
        act_del.triggered.connect(lambda: self._delete_tasks(ids, delete_file=False))

        act_del_all = menu.addAction(get_icon("delete", "#f87171", 14), "删除任务及文件")
        act_del_all.triggered.connect(lambda: self._delete_tasks(ids, delete_file=True))

        menu.exec_(self.table.mapToGlobal(pos))

    def _on_cell_double_clicked(self, row, col):
        it = self.table.item(row, 0)
        if it:
            t_id = it.data(Qt.UserRole)
            task = task_manager.get_task(t_id)
            if task:
                if task.get("status") == "completed" and task.get("output_file"):
                    out_p = task["output_file"]
                    if os.path.exists(out_p):
                        os.startfile(out_p)
                elif task.get("status") == "downloading":
                    ok, msg = play_task_preview(t_id)
                    if not ok:
                        self._show_task_log(task)
                else:
                    self._show_task_log(task)

    def _restore_from_floating(self):
        self.showNormal()
        self.activateWindow()

    def _on_floating_new_task(self, url):
        self.showNormal()
        self.activateWindow()
        dlg = NewTaskDialog(self, initial_url=url)
        dlg.exec_()

    def _toggle_floating_widget(self):
        if self.floating_widget.isVisible():
            self.floating_widget.hide()
            config.set("show_floating_widget", False)
            self.statusBar().showMessage("桌面悬浮窗已隐藏", 2000)
        else:
            self.floating_widget.show()
            config.set("show_floating_widget", True)
            self.statusBar().showMessage("桌面悬浮窗已开启 (支持拖拽链接快速下载)", 3000)

    def _action_show_mobile_connect(self):
        dlg = MobileConnectDialog(self)
        dlg.exec_()

    def _action_preview_selected(self):
        ids = self._get_selected_task_ids()
        if not ids:
            return
        task_id = ids[0]
        ok, msg = play_task_preview(task_id)
        if ok:
            self.statusBar().showMessage(f"已在默认播放器中启动即时画面预览: {msg}", 4000)
        else:
            QMessageBox.information(
                self, "边下边播提示",
                f"暂时无法生成即时画面预览:\n{msg}\n\n建议等待几秒钟、分片有更多落盘后再试。"
            )

    def _action_view_task_log(self):
        ids = self._get_selected_task_ids()
        if not ids:
            return
        task = task_manager.get_task(ids[0])
        if task:
            self._show_task_log(task)

    def _show_task_log(self, task):
        dlg = TaskLogDialog(task, self)
        dlg.exec_()

    def _action_open_master_error_log(self):
        log_p = get_master_error_log_path()
        if not os.path.exists(log_p):
            try:
                with open(log_p, "w", encoding="utf-8") as f:
                    f.write("=== 星流 (StarStream) 下载错误日志 ===\n(暂无下载失败记录)\n")
            except Exception:
                pass
        try:
            os.startfile(log_p)
        except Exception as e:
            QMessageBox.warning(self, "打开日志提示", f"无法直接打开错误日志文件:\n{e}\n\n日志路径:\n{log_p}")

    def _action_open_video_parser(self):
        dlg = VideoParserDialog(self)
        dlg.exec_()
        self.refresh_table()

    def _action_new_task(self):
        dlg = NewTaskDialog(self)
        dlg.exec_()

    def _action_start_selected(self):
        for t_id in self._get_selected_task_ids():
            task_manager.start_task(t_id)

    def _action_pause_selected(self):
        for t_id in self._get_selected_task_ids():
            task_manager.pause_task(t_id)

    def _set_proxy_for_selected(self, ids, proxy_str):
        for t_id in ids:
            task_manager.update_task_proxy(t_id, proxy_str, restart_if_active=True)
        self.refresh_table()
        proxy_desc = "直连" if proxy_str == "DIRECT" else ("跟随全局" if proxy_str == "GLOBAL" else proxy_str)
        self.statusBar().showMessage(f"已为选中的 {len(ids)} 个任务更新代理为: {proxy_desc}", 3500)

    def _prompt_custom_proxy_for_selected(self, ids):
        if not ids:
            return
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(
            self, "自定义下载代理",
            "请输入 HTTP / SOCKS5 代理地址 (例如 http://127.0.0.1:7890 或 socks5://127.0.0.1:10808):",
            text="http://127.0.0.1:1080"
        )
        if ok and text.strip():
            self._set_proxy_for_selected(ids, text.strip())

    def _action_delete_selected(self):
        ids = self._get_selected_task_ids()
        if not ids:
            return
        ret = QMessageBox.question(
            self, "确认删除", f"确定要删除选中的 {len(ids)} 个任务吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if ret == QMessageBox.Yes:
            self._delete_tasks(ids, delete_file=False)

    def _delete_tasks(self, ids, delete_file=False):
        for t_id in ids:
            task_manager.remove_task(t_id, delete_file=delete_file)

    def _action_open_dir(self):
        ids = self._get_selected_task_ids()
        target_dir = config.get("save_dir")
        if ids:
            task = task_manager.get_task(ids[0])
            if task and task.get("save_dir") and os.path.exists(task.get("save_dir")):
                target_dir = task.get("save_dir")
        if os.path.exists(target_dir):
            os.startfile(target_dir)

    def _action_play_file(self):
        ids = self._get_selected_task_ids()
        if not ids:
            return
        task = task_manager.get_task(ids[0])
        if task and task.get("output_file") and os.path.exists(task.get("output_file")):
            os.startfile(task.get("output_file"))
        else:
            QMessageBox.information(self, "提示", "文件尚在下载中或已被移动！")

    def _action_ffmpeg_toolbox(self):
        dlg = FFmpegToolboxDialog(self)
        dlg.exec_()

    def _action_ffmpeg_toolbox_for_selected(self):
        ids = self._get_selected_task_ids()
        preset = ""
        if ids:
            t = task_manager.get_task(ids[0])
            if t and t.get("output_file") and os.path.exists(t.get("output_file")):
                preset = t.get("output_file")
        dlg = FFmpegToolboxDialog(self, preset_file=preset)
        dlg.exec_()

    def _action_batch_convert(self):
        dlg = BatchConvertDialog(self)
        dlg.exec_()

    def _action_batch_convert_for_selected(self):
        ids = self._get_selected_task_ids()
        selected_files = []
        for tid in ids:
            t = task_manager.get_task(tid)
            if t and t.get("output_file") and os.path.exists(t.get("output_file")):
                selected_files.append(t.get("output_file"))
        dlg = BatchConvertDialog(self, preset_files=selected_files)
        dlg.exec_()

    def _action_copy_url(self):
        ids = self._get_selected_task_ids()
        if not ids:
            return
        task = task_manager.get_task(ids[0])
        if task and task.get("url"):
            QApplication.clipboard().setText(task["url"])
            self.statusBar().showMessage("链接已复制", 2000)

    def _action_manage_fragments(self):
        dlg = FragmentsDialog(self)
        dlg.exec_()

    def _action_clean_cache(self):
        dlg = CacheCleanDialog(self)
        if dlg.exec_() == CacheCleanDialog.Accepted:
            self.refresh_table()

    def _action_extension_tutorial(self):
        dlg = ExtensionTutorialDialog(self)
        dlg.exec_()

    def _action_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec_() == SettingsDialog.Accepted:
            self._update_ffmpeg_label()
            self._update_nm3u8dl_label()
            self._update_proxy_label()
            self.refresh_table()

    def _action_show_disclaimer(self):
        from catcatch_app.ui.disclaimer_dialog import DisclaimerDialog
        dlg = DisclaimerDialog(self)
        dlg.exec_()

    def paintEvent(self, event):
        bg_path = config.get("custom_background_image", "")
        if bg_path and os.path.exists(bg_path):
            painter = QPainter(self)
            pix = getattr(self, "_cached_bg_pixmap", None)
            if pix is None:
                pix = QPixmap(bg_path)
                self._cached_bg_pixmap = pix

            if pix and not pix.isNull():
                scaled = pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)

                opacity = float(config.get("background_opacity", 0.45))
                opacity = max(0.05, min(0.95, opacity))
                theme_name = config.get("theme", "dark")
                is_light = (theme_name == "light")
                mask_rgb = (255, 255, 255) if is_light else (0, 0, 0)
                mask_color = QColor(*mask_rgb, int(opacity * 255))
                painter.fillRect(self.rect(), mask_color)
            painter.end()
        super().paintEvent(event)

    def apply_theme(self, theme_key=None):
        if theme_key:
            config.set("theme", theme_key)

        qss = get_theme_stylesheet()
        self.setStyleSheet(qss)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

        self._cached_bg_pixmap = None
        self._update_toolbar_icons()
        if hasattr(self, "btn_theme"):
            self.btn_theme.setMenu(self._create_theme_menu())
        self.update()

    def _update_toolbar_icons(self):
        cur_theme = THEMES.get(config.get("theme", "dark"), THEMES["dark"])
        accent = cur_theme["accent"]
        btn_icon_col = "#475569" if cur_theme["is_light"] else "#d4d4d8"
        text_col = cur_theme["text"]

        if hasattr(self, "act_new"):
            self.act_new.setIcon(get_icon("add", text_col, 18))
        if hasattr(self, "act_start"):
            self.act_start.setIcon(get_icon("play", accent, 18))
        if hasattr(self, "act_pause"):
            self.act_pause.setIcon(get_icon("pause", btn_icon_col, 18))
        if hasattr(self, "act_delete"):
            self.act_delete.setIcon(get_icon("delete", "#f87171", 18))
        if hasattr(self, "act_open_dir"):
            self.act_open_dir.setIcon(get_icon("folder", btn_icon_col, 18))
        if hasattr(self, "act_fragments"):
            self.act_fragments.setIcon(get_icon("stream", accent, 18))
        if hasattr(self, "act_ffmpeg"):
            self.act_ffmpeg.setIcon(get_icon("toolbox", btn_icon_col, 18))
        if hasattr(self, "act_batch"):
            self.act_batch.setIcon(get_icon("refresh", accent, 18))
        if hasattr(self, "act_clean"):
            self.act_clean.setIcon(get_icon("clean", btn_icon_col, 18))
        if hasattr(self, "act_view_errors"):
            self.act_view_errors.setIcon(get_icon("log", accent, 18))
        if hasattr(self, "act_ext"):
            self.act_ext.setIcon(get_icon("extension", accent, 18))
        if hasattr(self, "act_floating"):
            self.act_floating.setIcon(get_icon("monitor", accent, 18))
        if hasattr(self, "act_mobile"):
            self.act_mobile.setIcon(get_icon("phone", "#22c55e", 18))
        if hasattr(self, "act_disclaimer"):
            self.act_disclaimer.setIcon(get_icon("info", btn_icon_col, 18))
        if hasattr(self, "btn_theme"):
            self.btn_theme.setIcon(get_icon("palette", accent, 18))
        if hasattr(self, "act_settings"):
            self.act_settings.setIcon(get_icon("settings", btn_icon_col, 18))

    def _create_theme_menu(self):
        menu = QMenu(self)
        cur_theme_id = config.get("theme", "dark")

        # 1. 预设多主题选择
        for k, v in THEMES.items():
            prefix = "✓ " if k == cur_theme_id else "   "
            act = menu.addAction(get_icon("palette", v["accent"], 14), f"{prefix}{v['name']}")
            act.triggered.connect(lambda checked=False, tid=k: self._on_theme_selected(tid))

        menu.addSeparator()

        # 2. 自定义背景壁纸选项
        has_bg = bool(config.get("custom_background_image") and os.path.exists(config.get("custom_background_image")))
        act_set_bg = menu.addAction(get_icon("image", "#38bdf8", 14), "设置自定义背景图片...")
        act_set_bg.triggered.connect(self._action_set_custom_background)

        act_op = menu.addAction(get_icon("settings", "#a1a1aa", 14), "调节背景遮罩透明度...")
        act_op.triggered.connect(self._action_adjust_background_opacity)

        if has_bg:
            act_clear_bg = menu.addAction(get_icon("delete", "#f87171", 14), "清除自定义背景图片")
            act_clear_bg.triggered.connect(self._action_clear_custom_background)

        menu.addSeparator()
        act_more = menu.addAction(get_icon("settings", "#a1a1aa", 14), "外观与个性化设置中心...")
        act_more.triggered.connect(self._action_settings)

        return menu

    def _on_theme_selected(self, theme_id):
        self.apply_theme(theme_id)
        theme_name = THEMES.get(theme_id, {}).get("name", theme_id)
        self.statusBar().showMessage(f"已切换主题为: {theme_name}", 3000)

    def _action_set_custom_background(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择自定义背景图片", "",
            "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp);;所有文件 (*.*)"
        )
        if file_path:
            config.set("custom_background_image", file_path)
            self.apply_theme()
            self.statusBar().showMessage("已成功设置自定义背景图片！已自动应用通透毛玻璃视觉效果", 4000)

    def _action_clear_custom_background(self):
        config.set("custom_background_image", "")
        self.apply_theme()
        self.statusBar().showMessage("已清除自定义背景，恢复为纯净主题风格", 3000)

    def _action_adjust_background_opacity(self):
        cur_op = int(config.get("background_opacity", 0.45) * 100)
        val, ok = QInputDialog.getInt(
            self, "调节背景遮罩浓度",
            "请输入背景遮罩浓度百分比 (10% - 90%)：\n(数值越低背景越通透，数值越高文字越清晰)",
            value=cur_op, min=10, max=90, step=5
        )
        if ok:
            config.set("background_opacity", val / 100.0)
            self.apply_theme()
            self.statusBar().showMessage(f"背景遮罩浓度已更新为: {val}%", 3000)
