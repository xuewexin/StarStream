"""
CatCatch Downloader - New Task Dialog (新建下载任务)
采用矢量图标、无 Emoji 设计，支持为单个任务快速指定独立代理节点
"""
import os
import re
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QSpinBox, QGroupBox,
    QApplication, QMessageBox
)
from PyQt5.QtCore import Qt

from catcatch_app.core.config import config
from catcatch_app.core.task_manager import task_manager
from catcatch_app.ui.icons import get_icon, get_app_icon


class NewTaskDialog(QDialog):
    def __init__(self, parent=None, initial_url="", initial_title=""):
        super().__init__(parent)
        self.setWindowTitle("新建下载任务 - 星流下载器")
        self.setWindowIcon(get_app_icon())
        self.setMinimumWidth(580)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui(initial_url, initial_title)
        self._check_clipboard(initial_url)

    def _init_ui(self, initial_url, initial_title):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. 链接输入
        url_layout = QVBoxLayout()
        url_label = QLabel("下载链接 (URL / M3U8 / MPD / 视音频直链):")
        self.url_edit = QLineEdit(initial_url)
        self.url_edit.setPlaceholderText("https://...")
        self.url_edit.textChanged.connect(self._on_url_changed)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_edit)
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
        disclaimer_lbl = QLabel("⚖️ 免责声明：本软件仅供个人合法学习交流与离线备份，严禁用于商业牟利或盗版侵权。")
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
        if text.startswith("http://") or text.startswith("https://"):
            self.url_edit.setText(text)

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
