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
    QFrame, QTextEdit, QProgressBar, QListWidget, QListWidgetItem, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPixmap, QColor, QImage

from catcatch_app.core.config import config
from catcatch_app.core.task_manager import task_manager
from catcatch_app.core.video_parser import parse_video_url, submit_series_downloads
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
            if res.get("success") or (res.get("series") and res["series"].get("has_series")):
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
        self.setMinimumWidth(760)
        self.resize(800, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._current_result = None
        self._current_series = None
        self._parse_thread = None

        self._init_ui()
        if initial_url:
            self.input_edit.setText(initial_url)
            QTimer.singleShot(50, self._start_parse)
        else:
            QTimer.singleShot(50, self._check_clipboard)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(22, 18, 22, 18)

        # 1. 顶部平台特性提示区 (现代渐变玻璃卡片风)
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111827, stop:1 #1e293b);
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 12px 16px;
            }
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(get_icon("zap", "#38bdf8", 18).pixmap(18, 18))
        title_lbl = QLabel(t("vp_banner_title"))
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_lbl.setStyleSheet("color: #f8fafc; border: none; background: transparent;")
        title_row.addWidget(title_icon)
        title_row.addWidget(title_lbl, 1)
        h_layout.addLayout(title_row)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        badges = [
            t("vp_badge_bilibili"),
            t("vp_badge_douyin"),
            t("vp_badge_kuaishou"),
            t("vp_badge_xiaohongshu"),
            t("vp_badge_web"),
            "同系列/合集连爬"
        ]
        chip_style = (
            "background-color: rgba(15, 23, 42, 0.75); "
            "border: 1px solid rgba(56, 189, 248, 0.25); "
            "border-radius: 12px; "
            "padding: 3px 10px; "
            "color: #cbd5e1; "
            "font-size: 11px; "
            "font-weight: 500;"
        )
        for idx, b_name in enumerate(badges):
            b_lbl = QLabel(b_name)
            if idx == len(badges) - 1:
                b_lbl.setStyleSheet(
                    "background-color: rgba(56, 189, 248, 0.16); "
                    "border: 1px solid rgba(56, 189, 248, 0.45); "
                    "border-radius: 12px; padding: 3px 10px; color: #38bdf8; font-size: 11px; font-weight: 600;"
                )
            else:
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
        self.input_edit.setMaximumHeight(66)
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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1);
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
            }
        """)
        self.parse_btn.clicked.connect(self._start_parse)

        self.browser_btn = QPushButton(t("vp_browser_btn"))
        self.browser_btn.setIcon(get_icon("globe", "#94a3b8", 16))
        self.browser_btn.setToolTip(t("vp_browser_tooltip"))
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
        self.cover_lbl.setFixedSize(148, 96)
        self.cover_lbl.setAlignment(Qt.AlignCenter)
        self.cover_lbl.setStyleSheet("background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: #64748b;")
        media_card.addWidget(self.cover_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel(t("vp_field_title")))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(t("vp_placeholder_title"))
        title_row.addWidget(self.title_edit, 1)
        info_col.addLayout(title_row)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel(t("vp_field_url")))
        self.url_display = QLineEdit()
        self.url_display.setPlaceholderText(t("vp_placeholder_url"))
        url_row.addWidget(self.url_display, 1)
        info_col.addLayout(url_row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        meta_chip_style = (
            "background-color: rgba(15, 23, 42, 0.85); "
            "border: 1px solid #334155; "
            "border-radius: 10px; "
            "padding: 2px 10px; "
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
        self.copy_link_btn.clicked.connect(self._copy_parsed_url)

        self.copy_b64_btn = QPushButton(t("vp_copy_base64"))
        self.copy_b64_btn.setEnabled(False)
        self.copy_b64_btn.setIcon(get_icon("code", "#38bdf8", 14))
        self.copy_b64_btn.clicked.connect(self._copy_parsed_b64_url)

        self.download_btn = QPushButton(t("vp_add_download"))
        self.download_btn.setIcon(get_icon("download", "#ffffff", 16))
        self.download_btn.setEnabled(False)
        self.download_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1);
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #475569;
                border: 1px solid #334155;
            }
        """)
        self.download_btn.clicked.connect(self._submit_to_downloader)

        btn_bar.addWidget(self.copy_link_btn)
        btn_bar.addWidget(self.copy_b64_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(self.download_btn)
        res_layout.addLayout(btn_bar)

        layout.addWidget(self.result_group)

        # 4. 同系列 / 合集选集批量爬取区 (仅检测到系列/合集时动态展开)
        self.series_group = QGroupBox("同系列 / 合集选集批量爬取")
        self.series_group.hide()
        ser_layout = QVBoxLayout(self.series_group)
        ser_layout.setSpacing(8)

        ser_top = QHBoxLayout()
        self.series_title_lbl = QLabel("合集列表")
        self.series_title_lbl.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 12px;")
        ser_top.addWidget(self.series_title_lbl, 1)

        btn_sel_all = QPushButton("全选")
        btn_sel_all.setFixedHeight(26)
        btn_sel_all.clicked.connect(lambda: self._series_toggle_all(True))
        btn_sel_none = QPushButton("全不选")
        btn_sel_none.setFixedHeight(26)
        btn_sel_none.clicked.connect(lambda: self._series_toggle_all(False))
        btn_sel_after = QPushButton("从当前往后选")
        btn_sel_after.setFixedHeight(26)
        btn_sel_after.clicked.connect(self._series_select_from_current)

        self.range_input = QLineEdit()
        self.range_input.setPlaceholderText("区间如 1-5")
        self.range_input.setFixedWidth(84)
        self.range_input.setFixedHeight(26)
        btn_range_apply = QPushButton("应用区间")
        btn_range_apply.setFixedHeight(26)
        btn_range_apply.clicked.connect(self._series_apply_range)

        ser_top.addWidget(btn_sel_all)
        ser_top.addWidget(btn_sel_none)
        ser_top.addWidget(btn_sel_after)
        ser_top.addWidget(self.range_input)
        ser_top.addWidget(btn_range_apply)
        ser_layout.addLayout(ser_top)

        self.series_list = QListWidget()
        self.series_list.setMinimumHeight(140)
        self.series_list.setMaximumHeight(200)
        self.series_list.setStyleSheet("""
            QListWidget {
                background-color: #0b1120;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 5px 8px;
                border-radius: 4px;
                color: #e2e8f0;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
            }
        """)
        self.series_list.itemChanged.connect(self._update_series_btn_count)
        ser_layout.addWidget(self.series_list)

        ser_bottom = QHBoxLayout()
        self.chk_series_subdir = QCheckBox("按合集名称创建子目录归档")
        self.chk_series_subdir.setChecked(True)
        self.chk_series_prefix = QCheckBox("自动添加序号前缀 (01 - 标题)")
        self.chk_series_prefix.setChecked(True)

        self.series_download_btn = QPushButton("一键爬取选中剧集 (0)")
        self.series_download_btn.setIcon(get_icon("download", "#ffffff", 15))
        self.series_download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0ea5e9, stop:1 #6366f1);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #818cf8);
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #475569;
            }
        """)
        self.series_download_btn.clicked.connect(self._submit_series_downloads)

        ser_bottom.addWidget(self.chk_series_subdir)
        ser_bottom.addWidget(self.chk_series_prefix)
        ser_bottom.addStretch()
        ser_bottom.addWidget(self.series_download_btn)
        ser_layout.addLayout(ser_bottom)

        layout.addWidget(self.series_group, 1)

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
        u = (res.get("url") or "").lower()
        orig = self.input_edit.toPlainText().lower()
        platform = "通用视频"
        if "douyin" in orig or "douyinvod" in u: platform = "抖音 (无水印)"
        elif "bilibili" in orig or "bilivideo" in u or "b23.tv" in orig: platform = "Bilibili"
        elif "kuaishou" in orig or "kwaicdn" in u: platform = "快手"
        elif "xiaohongshu" in orig or "xhscdn" in u: platform = "小红书"
        elif "youtube" in orig or "youtu.be" in orig: platform = "YouTube"

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

        has_single_url = bool(res.get("success") and res.get("url"))
        self.copy_link_btn.setEnabled(has_single_url)
        self.copy_b64_btn.setEnabled(has_single_url)
        self.download_btn.setEnabled(has_single_url)

        # 同系列 / 合集列表自动展开
        series = res.get("series")
        self._populate_series_panel(series)

        if has_single_url:
            if series and series.get("has_series"):
                self.status_lbl.setText(f"提取成功！同时检测到同系列合集共 {series.get('total', 0)} 集，可在下方一键选集全套爬取。")
            else:
                self.status_lbl.setText(t("vp_success_hint"))
            self.status_lbl.setStyleSheet("color: #4ade80; font-size: 11px;")
        elif series and series.get("has_series"):
            self.status_lbl.setText(res.get("error") or f"已识别同系列合集共 {series.get('total', 0)} 集，请在下方选集爬取。")
            self.status_lbl.setStyleSheet("color: #fbbf24; font-size: 11px;")

    def _populate_series_panel(self, series):
        self._current_series = series
        self.series_list.blockSignals(True)
        self.series_list.clear()

        if not series or not series.get("has_series") or not series.get("episodes"):
            self.series_list.blockSignals(False)
            self.series_group.hide()
            self.resize(800, 580)
            return

        episodes = series["episodes"]
        cur_idx = int(series.get("current_index") or 0)
        s_title = series.get("series_title") or "同系列合集"
        self.series_title_lbl.setText(f"合集: {s_title}  (共 {len(episodes)} 集)")

        for i, ep in enumerate(episodes):
            dur = int(ep.get("duration") or 0)
            dur_str = f"  [{dur // 60:02d}:{dur % 60:02d}]" if dur > 0 else ""
            cur_mark = "  [当前]" if i == cur_idx else ""
            label = f"{int(ep.get('index') or (i + 1)):02d}. {ep.get('title') or f'第{i+1}集'}{dur_str}{cur_mark}"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, ep)
            if i == cur_idx:
                item.setForeground(QColor("#38bdf8"))
            self.series_list.addItem(item)

        self.series_list.blockSignals(False)
        self.series_group.show()
        self._update_series_btn_count()
        self.resize(820, 760)

    def _series_toggle_all(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        self.series_list.blockSignals(True)
        for i in range(self.series_list.count()):
            self.series_list.item(i).setCheckState(state)
        self.series_list.blockSignals(False)
        self._update_series_btn_count()

    def _series_select_from_current(self):
        cur_idx = int((self._current_series or {}).get("current_index") or 0)
        self.series_list.blockSignals(True)
        for i in range(self.series_list.count()):
            self.series_list.item(i).setCheckState(Qt.Checked if i >= cur_idx else Qt.Unchecked)
        self.series_list.blockSignals(False)
        self._update_series_btn_count()

    def _series_apply_range(self):
        raw = self.range_input.text().strip()
        m = re.match(r'^(\d+)\s*[-~到]\s*(\d+)$', raw)
        if not m:
            QMessageBox.information(self, t("notice"), "请输入有效的集数区间，例如: 1-10")
            return
        start_idx = max(1, int(m.group(1))) - 1
        end_idx = min(self.series_list.count(), int(m.group(2))) - 1
        self.series_list.blockSignals(True)
        for i in range(self.series_list.count()):
            self.series_list.item(i).setCheckState(Qt.Checked if start_idx <= i <= end_idx else Qt.Unchecked)
        self.series_list.blockSignals(False)
        self._update_series_btn_count()

    def _update_series_btn_count(self):
        cnt = 0
        for i in range(self.series_list.count()):
            if self.series_list.item(i).checkState() == Qt.Checked:
                cnt += 1
        self.series_download_btn.setText(f"一键爬取选中剧集 ({cnt})")
        self.series_download_btn.setEnabled(cnt > 0)

    def _submit_series_downloads(self):
        if not self._current_series:
            return
        selected_eps = []
        for i in range(self.series_list.count()):
            it = self.series_list.item(i)
            if it.checkState() == Qt.Checked:
                ep = it.data(Qt.UserRole)
                if ep:
                    selected_eps.append(ep)
        if not selected_eps:
            return

        series_title = self._current_series.get("series_title") or self.title_edit.text().strip() or "合集系列"
        target_dir = submit_series_downloads(
            episodes=selected_eps,
            series_title=series_title,
            save_dir=config.get("save_dir"),
            create_subdir=self.chk_series_subdir.isChecked(),
            add_index_prefix=self.chk_series_prefix.isChecked(),
            proxy=config.get_effective_proxy(),
            extra_headers=(self._current_result or {}).get("headers") or {},
        )
        QMessageBox.information(
            self, t("notice"),
            f"已启动同系列批量爬取！\n\n合集名称: {series_title}\n选中剧集: {len(selected_eps)} 集\n保存位置: {target_dir}\n\n各分集正在后台极速解析并陆续加入主队列开始下载。"
        )
        self.accept()

    def _open_in_browser(self):
        text = self.input_edit.toPlainText().strip()
        m = re.search(r'https?://[^\s<>"]+', text)
        url = m.group(0) if m else text
        if not url.startswith("http"):
            QMessageBox.warning(self, t("notice"), "请在上方输入框输入或粘贴有效的网页链接！")
            return
        webbrowser.open(url)
        self.status_lbl.setText(t("vp_browser_hint"))
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")

    def _on_parse_failed(self, msg):
        self.parse_btn.setEnabled(True)
        self.pbar.hide()
        self._populate_series_panel(None)
        if "安全防护" in msg or "风控" in msg or "浏览器" in msg:
            self.status_lbl.setText(f"{t('notice')}: {msg}")
            self.status_lbl.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 500;")
        else:
            self.status_lbl.setText(f"{t('notice')}: {msg}")
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
                        scaled = pix.scaled(148, 96, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                        QTimer.singleShot(0, lambda: self.cover_lbl.setPixmap(scaled))
            except Exception:
                QTimer.singleShot(0, lambda: self.cover_lbl.setText(t("vp_no_cover")))
        import threading
        threading.Thread(target=_fetch, daemon=True).start()

    def _copy_parsed_url(self):
        url = self.url_display.text().strip()
        if url:
            QApplication.clipboard().setText(url)
            QMessageBox.information(self, t("notice"), t("vp_copy_success"))

    def _copy_parsed_b64_url(self):
        url = self.url_display.text().strip()
        if url:
            import base64
            b64_str = base64.b64encode(url.encode("utf-8")).decode("utf-8")
            QApplication.clipboard().setText(b64_str)
            QMessageBox.information(self, t("notice"), t("vp_copy_b64_success"))

    def _submit_to_downloader(self):
        if not self._current_result:
            return
        url = self.url_display.text().strip() or self._current_result.get("url")
        title = self.title_edit.text().strip() or self._current_result.get("title") or "video"
        audio_url = self._current_result.get("audio_url", "")
        media_type = self._current_result.get("media_type") or ("bili_dash" if audio_url else ("m3u8" if ".m3u8" in url else "video"))
        headers = self._current_result.get("headers", {})

        task_info = {
            "url": url,
            "audio_url": audio_url,
            "title": title,
            "save_name": title,
            "save_dir": config.get("save_dir"),
            "media_type": media_type,
            "resolution": self._current_result.get("resolution", ""),
            "duration": self._current_result.get("duration", 0),
            "format": "m4a" if media_type == "audio" else "mp4",
            "headers": headers,
            "thread_count": config.get("max_threads_per_task", 16),
            "proxy": config.get_effective_proxy()
        }

        task_manager.add_task(task_info, auto_start=True)
        QMessageBox.information(self, t("notice"), f"{t('pushed_queue')}:\n{title}")
        self.accept()
