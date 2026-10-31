"""
CatCatch Downloader - New Task Dialog (新建下载任务)
采用矢量图标、无 Emoji 设计，支持为单个任务快速指定独立代理节点
内置全网视频一键解析能力 (Bilibili, 抖音无水印, 快手, 小红书, 通用HTML5视频)
"""
import os
import re
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QSpinBox, QGroupBox,
    QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from catcatch_app.core.config import config
from catcatch_app.core.task_manager import task_manager
from catcatch_app.core.video_parser import parse_video_url
from catcatch_app.ui.icons import get_icon, get_app_icon


class VideoParseWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, url, proxy=""):
        super().__init__()
        self.url = url
        self.proxy = proxy

    def run(self):
        try:
            res = parse_video_url(self.url, proxy=self.proxy)
            if res.get("success"):
                self.finished.emit(res)
            else:
                self.failed.emit(res.get("error") or "未能从该地址解析出有效视频")
        except Exception as e:
            self.failed.emit(str(e))


class NewTaskDialog(QDialog):
    def __init__(self, parent=None, initial_url="", initial_title=""):
        super().__init__(parent)
        self.setWindowTitle("新建下载任务 - 星流下载器")
        self.setWindowIcon(get_app_icon())
        self.setMinimumWidth(620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._parse_worker = None
        self._init_ui(initial_url, initial_title)
        self._check_clipboard(initial_url)

    def _init_ui(self, initial_url, initial_title):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. 链接输入与全网一键解析
        url_layout = QVBoxLayout()
        url_label = QLabel("下载链接 (URL / M3U8 / MPD / 视音频直链 / 网页视频分享文本):")
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit(initial_url)
        self.url_edit.setPlaceholderText("可粘贴视频直链、M3U8、或 B站 / 抖音 / 快手 / 小红书等网页分享链接...")
        self.url_edit.textChanged.connect(self._on_url_changed)

        self.parse_btn = QPushButton("全网一键解析")
        self.parse_btn.setIcon(get_icon("zap", "#38bdf8", 14))
        self.parse_btn.setToolTip("一键逆向解析目标网页，提取真实原画 MP4 直链或 M3U8 清单")
        self.parse_btn.clicked.connect(self._trigger_parse)

        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.parse_btn)
        url_layout.addWidget(url_label)
        url_layout.addLayout(url_row)

        self.parse_status_lbl = QLabel("")
        self.parse_status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; margin-top: 2px;")
        url_layout.addWidget(self.parse_status_lbl)
        layout.addLayout(url_layout)

        # 2. 文件名与格式类型
        row2 = QHBoxLayout()
        name_layout = QVBoxLayout()
        name_label = QLabel("保存文件名:")
        self.name_edit = QLineEdit(initial_title)
        self.name_edit.setPlaceholderText("留空自动解析")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)
        row2.addLayout(name_layout, 3)

        type_layout = QVBoxLayout()
        type_label = QLabel("资源类型:")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["自动识别", "M3U8 流媒体", "普通视频 (MP4/WebM)", "音频 (MP3/AAC)", "常规文件"])
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_combo)
        row2.addLayout(type_layout, 2)
        layout.addLayout(row2)

        # 3. 保存路径
        path_layout = QVBoxLayout()
        path_label = QLabel("保存目录:")
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(config.get("save_dir"))
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setIcon(get_icon("folder", "#a1a1aa", 16))
        self.browse_btn.clicked.connect(self._browse_dir)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.browse_btn)
        path_layout.addWidget(path_label)
        path_layout.addLayout(path_row)
        layout.addLayout(path_layout)

        # 4. 高级参数 (防盗链 / Referer / 代理选择)
        self.adv_group = QGroupBox("网络与代理设置")
        adv_layout = QVBoxLayout(self.adv_group)

        # 代理模式选择
        p_row = QHBoxLayout()
        p_row.addWidget(QLabel("下载代理:"))
        self.proxy_combo = QComboBox()
        self._populate_proxy_combo()
        p_row.addWidget(self.proxy_combo, 1)

        p_row.addWidget(QLabel("并发线程:"))
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 64)
        self.thread_spin.setValue(config.get("max_threads_per_task", 16))
        p_row.addWidget(self.thread_spin)
        adv_layout.addLayout(p_row)

        ref_layout = QHBoxLayout()
        ref_label = QLabel("Referer:")
        ref_label.setFixedWidth(60)
        self.ref_edit = QLineEdit()
        self.ref_edit.setPlaceholderText("可选，来源防盗链网址")
        ref_layout.addWidget(ref_label)
        ref_layout.addWidget(self.ref_edit)
        adv_layout.addLayout(ref_layout)

        cookie_layout = QHBoxLayout()
        cookie_label = QLabel("Cookie:")
        cookie_label.setFixedWidth(60)
        self.cookie_edit = QLineEdit()
        self.cookie_edit.setPlaceholderText("可选，登录鉴权凭证")
        cookie_layout.addWidget(cookie_label)
        cookie_layout.addWidget(self.cookie_edit)
        adv_layout.addLayout(cookie_layout)

        layout.addWidget(self.adv_group)

        # 免责声明小贴士
        disclaimer_lbl = QLabel("免责声明：本软件仅供个人合法学习交流与离线备份，严禁用于商业牟利或盗版侵权。")
        disclaimer_lbl.setStyleSheet("color: #71717a; font-size: 11px; margin-top: 4px;")
        layout.addWidget(disclaimer_lbl)

        # 5. 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setIcon(get_icon("download", "#ffffff", 16))
        self.download_btn.setProperty("class", "primary")
        self.download_btn.clicked.connect(self._start_download)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.download_btn)
        layout.addLayout(btn_layout)

    def _populate_proxy_combo(self):
        self.proxy_combo.clear()
        
        # 默认项：跟随全局配置
        eff = config.get_effective_proxy()
        eff_desc = f"全局设置 (当前: {eff if eff else '直连'})"
        self.proxy_combo.addItem(eff_desc, "__DEFAULT__")
        self.proxy_combo.addItem("强制直连 (不使用任何代理)", "__NONE__")
        self.proxy_combo.addItem("跟随 Windows 系统代理", "__SYSTEM__")

        # 追加自定义代理列表
        for p in config.get_proxies_list():
            self.proxy_combo.addItem(f"节点: {p.get('name')} ({p.get('url')})", p.get("url"))

    def _check_clipboard(self, initial_url):
        if initial_url:
            return
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text.startswith("http://") or text.startswith("https://") or "v.douyin.com" in text or "b23.tv" in text:
            self.url_edit.setText(text)
            if any(k in text for k in ["bilibili.com", "b23.tv", "douyin.com", "kuaishou.com", "xiaohongshu.com"]):
                self._trigger_parse()

    def _trigger_parse(self):
        raw_text = self.url_edit.text().strip()
        if not raw_text:
            self.parse_status_lbl.setText("请输入要解析的视频链接或分享文本")
            return

        proxy_val = self.proxy_combo.currentData()
        eff_p = config.get_effective_proxy() if proxy_val == "__DEFAULT__" else (str(proxy_val) if proxy_val not in ["__NONE__", "__SYSTEM__"] else "")

        self.parse_btn.setEnabled(False)
        self.parse_status_lbl.setText("正在从目标站点深度逆向提取视频流直链，请稍候...")
        self.parse_status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")

        self._parse_worker = VideoParseWorker(raw_text, proxy=eff_p)
        self._parse_worker.finished.connect(self._on_parse_success)
        self._parse_worker.failed.connect(self._on_parse_failed)
        self._parse_worker.start()

    def _on_parse_success(self, res):
        self.parse_btn.setEnabled(True)
        self.url_edit.setText(res.get("url", ""))
        
        title = res.get("title", "")
        if title:
            self.name_edit.setText(title)

        mtype = res.get("media_type", "video")
        if mtype == "m3u8":
            self.type_combo.setCurrentIndex(1)
        elif mtype == "video":
            self.type_combo.setCurrentIndex(2)

        hdrs = res.get("headers", {})
        if "Referer" in hdrs:
            self.ref_edit.setText(hdrs["Referer"])

        res_desc = res.get("resolution") or "自适应"
        self.parse_status_lbl.setText(f"解析成功！已提取 [{res_desc}] 视频直链: {title[:36]}")
        self.parse_status_lbl.setStyleSheet("color: #4ade80; font-size: 11px;")

    def _on_parse_failed(self, err_msg):
        self.parse_btn.setEnabled(True)
        self.parse_status_lbl.setText(f"解析提示: {err_msg} (已保留原链接，可直接尝试下载)")
        self.parse_status_lbl.setStyleSheet("color: #f59e0b; font-size: 11px;")

    def _on_url_changed(self, text):
        text = text.strip()
        if not self.name_edit.text() and text:
            base = text.split("?")[0].split("/")[-1]
            if base and "." in base:
                clean_name = os.path.splitext(base)[0]
                self.name_edit.setText(clean_name)
        
        lower = text.lower()
        if ".m3u8" in lower or ".mpd" in lower:
            self.type_combo.setCurrentIndex(1)
        elif any(lower.endswith(ext) for ext in [".mp4", ".flv", ".webm", ".mkv"]):
            self.type_combo.setCurrentIndex(2)
        elif any(lower.endswith(ext) for ext in [".mp3", ".m4a", ".aac", ".wav"]):
            self.type_combo.setCurrentIndex(3)

    def _browse_dir(self):
        cur_dir = self.path_edit.text() or config.get("save_dir")
        selected = QFileDialog.getExistingDirectory(self, "选择保存目录", cur_dir)
        if selected:
            self.path_edit.setText(selected)

    def _start_download(self):
        try:
            url = self.url_edit.text().strip()
            if not url:
                QMessageBox.warning(self, "提示", "请输入有效的下载链接！")
                return

            name = self.name_edit.text().strip() or "video"
            save_dir = self.path_edit.text().strip() or config.get("save_dir")
            
            type_idx = self.type_combo.currentIndex()
            media_type = ""
            if type_idx == 1:
                media_type = "m3u8"
            elif type_idx == 2:
                media_type = "video"
            elif type_idx == 3:
                media_type = "audio"
            elif type_idx == 4:
                media_type = "file"

            headers = {}
            if self.ref_edit.text().strip():
                headers["Referer"] = self.ref_edit.text().strip()
            if self.cookie_edit.text().strip():
                headers["Cookie"] = self.cookie_edit.text().strip()

            # 解析代理选择
            proxy_val = self.proxy_combo.currentData()
            final_proxy = ""
            if proxy_val == "__DEFAULT__":
                final_proxy = config.get_effective_proxy()
            elif proxy_val == "__NONE__":
                final_proxy = ""
            elif proxy_val == "__SYSTEM__":
                from catcatch_app.core.config import detect_system_proxy
                final_proxy = detect_system_proxy()
            else:
                final_proxy = str(proxy_val)

            task_info = {
                "url": url,
                "title": name,
                "save_name": name,
                "save_dir": save_dir,
                "media_type": media_type,
                "headers": headers,
                "thread_count": self.thread_spin.value(),
                "proxy": final_proxy
            }

            task_manager.add_task(task_info, auto_start=True)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "添加任务失败", f"创建下载任务时发生异常:\n{e}")
