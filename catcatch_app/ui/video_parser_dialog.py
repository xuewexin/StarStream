"""
CatCatch Downloader - Universal Video Parser Workbench (全网短视频一键提取工作台)
支持 B站、抖音无水印、快手、小红书、通用 HTML5 视频页面快速逆向解析与高清下载
"""
import os
import re
import webbrowser
import urllib.request
from io import BytesIO
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QGroupBox, QApplication, QMessageBox,
    QFrame, QTextEdit, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPixmap, QColor, QImage

from catcatch_app.core.config import config
from catcatch_app.core.task_manager import task_manager
from catcatch_app.core.video_parser import parse_video_url
from catcatch_app.ui.icons import get_icon, get_app_icon
from catcatch_app.core.i18n import t


class AsyncParseThread(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, raw_input, proxy=""):
        super().__init__()
        self.raw_input = raw_input
        self.proxy = proxy

    def run(self):
        try:
            res = parse_video_url(self.raw_input, proxy=self.proxy)
            if res.get("success"):
                self.finished.emit(res)
            else:
                self.failed.emit(res.get("error") or "未能从该链接解析出有效视频")
        except Exception as e:
            self.failed.emit(str(e))


class VideoParserDialog(QDialog):
    def __init__(self, parent=None, initial_url=""):
        super().__init__(parent)
        self.setWindowTitle(t("vp_window_title"))
        self.setWindowIcon(get_app_icon())
        self.setMinimumWidth(720)
        self.resize(760, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._current_result = None
        self._parse_thread = None

        self._init_ui()
        if initial_url:
            self.input_edit.setText(initial_url)
            QTimer.singleShot(50, self._start_parse)
        else:
            QTimer.singleShot(50, self._check_clipboard)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 18, 22, 18)

        # 1. 顶部平台特性提示区 (沉稳暗色 slate 风格，消除杂乱配色)
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(get_icon("zap", "#38bdf8", 18).pixmap(18, 18))
        title_lbl = QLabel(t("vp_banner_title"))
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_lbl.setStyleSheet("color: #f8fafc;")
        title_row.addWidget(title_icon)
        title_row.addWidget(title_lbl, 1)
        h_layout.addLayout(title_row)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        badges = [
            "B站 (Bilibili)",
            "抖音 (无水印)",
            "快手 (高清)",
            "小红书 (原画)",
            "通用网页 (H5/M3U8)"
        ]
        chip_style = (
            "background-color: #0f172a; "
            "border: 1px solid #334155; "
            "border-radius: 4px; "
            "padding: 2px 8px; "
            "color: #94a3b8; "
            "font-size: 11px; "
            "font-weight: 500;"
        )
        for b_name in badges:
            b_lbl = QLabel(b_name)
            b_lbl.setStyleSheet(chip_style)
            badge_row.addWidget(b_lbl)
        badge_row.addStretch()
        h_layout.addLayout(badge_row)
        layout.addWidget(header_frame)

        # 2. 粘贴输入区域
        input_group = QGroupBox(t("vp_input_group"))
        in_layout = QVBoxLayout(input_group)
        in_layout.setSpacing(8)

        self.input_edit = QTextEdit()
        self.input_edit.setMaximumHeight(70)
        self.input_edit.setPlaceholderText(t("vp_placeholder"))
        in_layout.addWidget(self.input_edit)

        action_row = QHBoxLayout()
        paste_btn = QPushButton(t("vp_paste"))
        paste_btn.setIcon(get_icon("copy", "#a1a1aa", 14))
        paste_btn.clicked.connect(self._paste_clipboard)

        clear_btn = QPushButton(t("vp_clear"))
        clear_btn.clicked.connect(lambda: self.input_edit.clear())

        self.parse_btn = QPushButton(t("vp_parse_btn"))
        self.parse_btn.setIcon(get_icon("zap", "#ffffff", 16))
        self.parse_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
            }
        """)
        self.parse_btn.clicked.connect(self._start_parse)

        self.browser_btn = QPushButton(t("vp_browser_btn"))
        self.browser_btn.setIcon(get_icon("globe", "#94a3b8", 16))
        self.browser_btn.setToolTip("在系统默认浏览器中打开该视频页面，由星流媒体嗅探器插件直接捕获最高画质无水印直链")
        self.browser_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.browser_btn.clicked.connect(self._open_in_browser)

        action_row.addWidget(paste_btn)
        action_row.addWidget(clear_btn)
        action_row.addStretch()
        action_row.addWidget(self.browser_btn)
        action_row.addWidget(self.parse_btn)
        in_layout.addLayout(action_row)

        layout.addWidget(input_group)

        # 进度与状态条
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 0)
        self.pbar.setFixedHeight(3)
        self.pbar.setTextVisible(False)
        self.pbar.hide()
        layout.addWidget(self.pbar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")
        layout.addWidget(self.status_lbl)

        # 3. 解析结果卡片展示区
        self.result_group = QGroupBox(t("vp_result_group"))
        res_layout = QVBoxLayout(self.result_group)
        res_layout.setSpacing(10)

        media_card = QHBoxLayout()
        self.cover_lbl = QLabel(t("vp_no_cover"))
        self.cover_lbl.setFixedSize(140, 95)
        self.cover_lbl.setAlignment(Qt.AlignCenter)
        self.cover_lbl.setStyleSheet("background: #18181b; border: 1px dashed #3f3f46; border-radius: 8px; color: #71717a;")
        media_card.addWidget(self.cover_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel(t("vp_field_title")))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("解析成功后将自动填入真实视频标题")
        title_row.addWidget(self.title_edit, 1)
        info_col.addLayout(title_row)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel(t("vp_field_url")))
        self.url_display = QLineEdit()
        self.url_display.setPlaceholderText("提取出的真实无水印 MP4 直链或 M3U8 清单")
        url_row.addWidget(self.url_display, 1)
        info_col.addLayout(url_row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        meta_chip_style = (
            "background-color: #0f172a; "
            "border: 1px solid #334155; "
            "border-radius: 4px; "
            "padding: 2px 8px; "
            "color: #94a3b8; "
            "font-size: 11px;"
        )
        self.tag_platform = QLabel(f"{t('vp_tag_platform')} --")
        self.tag_platform.setStyleSheet(meta_chip_style)
        self.tag_res = QLabel(f"{t('vp_tag_quality')} --")
        self.tag_res.setStyleSheet(meta_chip_style)
        self.tag_dur = QLabel(f"{t('vp_tag_duration')} --")
        self.tag_dur.setStyleSheet(meta_chip_style)

        meta_row.addWidget(self.tag_platform)
        meta_row.addWidget(self.tag_res)
        meta_row.addWidget(self.tag_dur)
        meta_row.addStretch()
        info_col.addLayout(meta_row)

        media_card.addLayout(info_col, 1)
        res_layout.addLayout(media_card)

        # 底部下载与复制操作栏
        btn_bar = QHBoxLayout()
        self.copy_link_btn = QPushButton(t("vp_copy_url"))
        self.copy_link_btn.setEnabled(False)
        self.copy_link_btn.setIcon(get_icon("copy", "#a1a1aa", 14))
        self.copy_link_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #0f172a;
                color: #475569;
                border-color: #1e293b;
            }
        """)
        self.copy_link_btn.clicked.connect(self._copy_parsed_url)

        self.download_btn = QPushButton(t("vp_add_download"))
        self.download_btn.setIcon(get_icon("download", "#ffffff", 16))
        self.download_btn.setEnabled(False)
        self.download_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #475569;
                border: 1px solid #334155;
            }
        """)
        self.download_btn.clicked.connect(self._submit_to_downloader)

        btn_bar.addWidget(self.copy_link_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(self.download_btn)
        res_layout.addLayout(btn_bar)

        layout.addWidget(self.result_group, 1)

    def _check_clipboard(self):
        cb = QApplication.clipboard()
        text = cb.text().strip()
        if any(k in text for k in ["bilibili.com", "b23.tv", "douyin.com", "v.douyin.com", "kuaishou.com", "xiaohongshu.com"]):
            self.input_edit.setText(text)
            self._start_parse()

    def _paste_clipboard(self):
        cb = QApplication.clipboard()
        self.input_edit.setText(cb.text().strip())

    def _start_parse(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先输入或粘贴需要解析的视频链接或分享文本！")
            return

        self.parse_btn.setEnabled(False)
        self.pbar.show()
        self.status_lbl.setText(t("vp_parsing_hint"))
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")

        eff_proxy = config.get_effective_proxy()
        self._parse_thread = AsyncParseThread(text, proxy=eff_proxy)
        self._parse_thread.finished.connect(self._on_parse_success)
        self._parse_thread.failed.connect(self._on_parse_failed)
        self._parse_thread.start()

    def _on_parse_success(self, res):
        self.parse_btn.setEnabled(True)
        self.pbar.hide()
        self._current_result = res

        self.title_edit.setText(res.get("title", ""))
        self.url_display.setText(res.get("url", ""))

        # 平台识别
        u = res.get("url", "").lower()
        orig = self.input_edit.toPlainText().lower()
        platform = "通用视频"
        if "douyin" in orig or "douyinvod" in u: platform = "抖音 (无水印)"
        elif "bilibili" in orig or "bilivideo" in u: platform = "Bilibili"
        elif "kuaishou" in orig or "kwaicdn" in u: platform = "快手"
        elif "xiaohongshu" in orig or "xhscdn" in u: platform = "小红书"

        self.tag_platform.setText(f"{t('vp_tag_platform')} {platform}")
        self.tag_res.setText(f"{t('vp_tag_quality')} {res.get('resolution') or '原画/1080P'}")
        dur = res.get("duration", 0)
        self.tag_dur.setText(f"{t('vp_tag_duration')} {dur // 60:02d}:{dur % 60:02d}" if dur > 0 else f"{t('vp_tag_duration')} --")

        # 异步加载封面
        cover_url = res.get("cover")
        if cover_url:
            self._load_cover(cover_url)
        else:
            self.cover_lbl.setText(t("vp_no_cover"))

        self.copy_link_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.status_lbl.setText(t("vp_success_hint"))
        self.status_lbl.setStyleSheet("color: #4ade80; font-size: 11px;")

    def _open_in_browser(self):
        text = self.input_edit.toPlainText().strip()
        m = re.search(r'https?://[^\s<>"]+', text)
        url = m.group(0) if m else text
        if not url.startswith("http"):
            QMessageBox.warning(self, "提示", "请在上方输入框输入或粘贴有效的网页链接！")
            return
        webbrowser.open(url)
        self.status_lbl.setText(t("vp_browser_hint"))
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")

    def _on_parse_failed(self, msg):
        self.parse_btn.setEnabled(True)
        self.pbar.hide()
        if "安全防护" in msg or "风控" in msg or "浏览器" in msg:
            self.status_lbl.setText(f"提示: {msg}")
            self.status_lbl.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 500;")
        else:
            self.status_lbl.setText(f"解析提示: {msg}")
            self.status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")

    def _load_cover(self, url):
        def _fetch():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = resp.read()
                    pix = QPixmap()
                    pix.loadFromData(data)
                    if not pix.isNull():
                        scaled = pix.scaled(140, 95, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                        self.cover_lbl.setPixmap(scaled)
            except Exception:
                self.cover_lbl.setText(t("vp_no_cover"))
        import threading
        threading.Thread(target=_fetch, daemon=True).start()

    def _copy_parsed_url(self):
        url = self.url_display.text().strip()
        if url:
            QApplication.clipboard().setText(url)
            QMessageBox.information(self, "提示", t("vp_copy_success"))

    def _submit_to_downloader(self):
        if not self._current_result:
            return
        url = self.url_display.text().strip() or self._current_result.get("url")
        title = self.title_edit.text().strip() or self._current_result.get("title") or "video"
        media_type = self._current_result.get("media_type") or ("m3u8" if ".m3u8" in url else "video")
        headers = self._current_result.get("headers", {})

        task_info = {
            "url": url,
            "title": title,
            "save_name": title,
            "save_dir": config.get("save_dir"),
            "media_type": media_type,
            "format": "mp4",
            "headers": headers,
            "thread_count": config.get("max_threads_per_task", 16),
            "proxy": config.get_effective_proxy()
        }

        task_manager.add_task(task_info, auto_start=True)
        QMessageBox.information(self, "提示", f"已加入下载队列:\n{title}")
        self.accept()
