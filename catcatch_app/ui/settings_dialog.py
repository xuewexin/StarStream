"""
CatCatch Downloader - Settings Dialog (系统与多代理池配置中心)
包含：路径设置、并发引擎、无代理/系统代理/多节点手动代理配置管理与测速
"""
import os
import time
import urllib.request
import subprocess
import webbrowser
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QSpinBox, QCheckBox,
    QGroupBox, QMessageBox, QRadioButton, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QInputDialog
)
from PyQt5.QtCore import Qt

from catcatch_app.core.config import (
    config, ROOT_DIR, detect_system_proxy,
    get_nm3u8dl_status, NM3U8DL_RE_DOWNLOAD_URL
)
from catcatch_app.core.browser_helper import (
    get_extension_dir, set_custom_extension_dir, is_valid_extension_dir
)
from catcatch_app.core.ffmpeg_engine import is_ffmpeg_available, get_ffmpeg_path
from catcatch_app.ui.icons import get_icon, get_app_icon
from catcatch_app.ui.cache_clean_dialog import CacheCleanDialog
from catcatch_app.ui.extension_tutorial_dialog import ExtensionTutorialDialog


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统与多节点代理设置 - 星流下载器")
        self.setWindowIcon(get_app_icon())
        self.setMinimumWidth(680)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._load_values()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. 存储与外部工具
        path_group = QGroupBox("路径与执行核心")
        path_layout = QVBoxLayout(path_group)

        # 保存目录
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("下载目录:"))
        self.save_edit = QLineEdit()
        btn_save = QPushButton("浏览...")
        btn_save.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_save.clicked.connect(self._browse_save_dir)
        r1.addWidget(self.save_edit)
        r1.addWidget(btn_save)
        path_layout.addLayout(r1)

        # FFmpeg
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("FFmpeg 路径:"))
        self.ff_edit = QLineEdit()
        btn_ff = QPushButton("浏览...")
        btn_ff.setIcon(get_icon("toolbox", "#a1a1aa", 16))
        btn_ff.clicked.connect(self._browse_ffmpeg)
        btn_test_ff = QPushButton("校验")
        btn_test_ff.setIcon(get_icon("check", "#a1a1aa", 16))
        btn_test_ff.clicked.connect(self._test_ffmpeg)
        r2.addWidget(self.ff_edit)
        r2.addWidget(btn_ff)
        r2.addWidget(btn_test_ff)
        path_layout.addLayout(r2)

        # M3U8 CLI 引擎选择与路径
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("流媒体下载引擎:"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItems([
            "N_m3u8DL-RE (推荐)",
            "N_m3u8DL-CLI v3.0.2",
            "内置 Python 原生并发引擎"
        ])
        r3.addWidget(self.engine_combo, 1)

        btn_rescan_tools = QPushButton("重新全盘探测引擎")
        btn_rescan_tools.setIcon(get_icon("refresh", "#a1a1aa", 16))
        btn_rescan_tools.clicked.connect(self._rescan_tools)
        r3.addWidget(btn_rescan_tools)
        path_layout.addLayout(r3)

        # N_m3u8DL-RE 路径与官方获取
        r4 = QHBoxLayout()
        r4.addWidget(QLabel("N_m3u8DL-RE 路径:"))
        self.re_edit = QLineEdit()
        self.re_edit.setPlaceholderText("自动搜寻或手动指定 N_m3u8DL-RE.exe")
        btn_re = QPushButton("浏览...")
        btn_re.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_re.clicked.connect(self._browse_re)
        btn_dl_re = QPushButton("🌐 获取最新版本 N_m3u8DL-RE")
        btn_dl_re.setStyleSheet("background-color: #1e3a8a; color: #93c5fd; font-weight: 500;")
        btn_dl_re.clicked.connect(self._download_nm3u8dl)
        r4.addWidget(self.re_edit, 1)
        r4.addWidget(btn_re)
        r4.addWidget(btn_dl_re)
        path_layout.addLayout(r4)

        layout.addWidget(path_group)

        # 2. 代理网络管理 (核心功能：不用代理 / 跟随系统 / 手动多节点)
        proxy_group = QGroupBox("网络与代理配置")
        proxy_layout = QVBoxLayout(proxy_group)

        # 代理模式单选
        mode_row = QHBoxLayout()
        self.btn_group = QButtonGroup(self)
        self.radio_none = QRadioButton("不使用代理 (直连)")
        self.radio_system = QRadioButton("跟随系统代理")
        self.radio_manual = QRadioButton("手动选择代理节点")

        self.btn_group.addButton(self.radio_none, 0)
        self.btn_group.addButton(self.radio_system, 1)
        self.btn_group.addButton(self.radio_manual, 2)

        mode_row.addWidget(self.radio_none)
        mode_row.addWidget(self.radio_system)
        mode_row.addWidget(self.radio_manual)
        mode_row.addStretch()
        proxy_layout.addLayout(mode_row)

        # 系统代理实时探测提示
        self.lbl_system_proxy_info = QLabel()
        self.lbl_system_proxy_info.setStyleSheet("color: #71717a; font-size: 11px;")
        proxy_layout.addWidget(self.lbl_system_proxy_info)

        # 手动代理表格与控制区
        self.manual_widget = QWidget()
        manual_layout = QVBoxLayout(self.manual_widget)
        manual_layout.setContentsMargins(0, 4, 0, 0)
        manual_layout.setSpacing(6)

        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("当前活动代理节点:"))
        self.active_proxy_combo = QComboBox()
        self.active_proxy_combo.currentIndexChanged.connect(self._on_active_proxy_changed)
        sel_row.addWidget(self.active_proxy_combo, 1)
        btn_test_active = QPushButton("测试当前代理")
        btn_test_active.clicked.connect(self._test_active_proxy)
        sel_row.addWidget(btn_test_active)
        manual_layout.addLayout(sel_row)

        # 代理节点列表
        self.proxy_table = QTableWidget()
        self.proxy_table.setColumnCount(3)
        self.proxy_table.setHorizontalHeaderLabels(["节点名称", "代理地址 (HTTP/SOCKS5)", "操作"])
        self.proxy_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.proxy_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.proxy_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.proxy_table.setColumnWidth(0, 180)
        self.proxy_table.setColumnWidth(2, 90)
        self.proxy_table.verticalHeader().setVisible(False)
        self.proxy_table.setMaximumHeight(130)
        manual_layout.addWidget(self.proxy_table)

        btn_proxy_row = QHBoxLayout()
        self.btn_add_proxy = QPushButton("添加新代理...")
        self.btn_add_proxy.setIcon(get_icon("add", "#a1a1aa", 16))
        self.btn_add_proxy.clicked.connect(self._add_proxy)
        self.btn_del_proxy = QPushButton("删除选中")
        self.btn_del_proxy.setIcon(get_icon("delete", "#a1a1aa", 16))
        self.btn_del_proxy.clicked.connect(self._del_proxy)
        btn_proxy_row.addWidget(self.btn_add_proxy)
        btn_proxy_row.addWidget(self.btn_del_proxy)
        btn_proxy_row.addStretch()
        manual_layout.addLayout(btn_proxy_row)

        proxy_layout.addWidget(self.manual_widget)
        self.radio_none.toggled.connect(self._update_proxy_ui_state)
        self.radio_system.toggled.connect(self._update_proxy_ui_state)
        self.radio_manual.toggled.connect(self._update_proxy_ui_state)

        layout.addWidget(proxy_group)

        # 3. 并发性能与扩展端口
        perf_group = QGroupBox("并发调度与端口")
        perf_layout = QVBoxLayout(perf_group)

        p_row = QHBoxLayout()
        p_row.addWidget(QLabel("最大并发任务数:"))
        self.max_tasks_spin = QSpinBox()
        self.max_tasks_spin.setRange(1, 10)
        p_row.addWidget(self.max_tasks_spin)

        p_row.addWidget(QLabel("单任务并发线程数:"))
        self.max_threads_spin = QSpinBox()
        self.max_threads_spin.setRange(1, 64)
        p_row.addWidget(self.max_threads_spin)

        p_row.addWidget(QLabel("通信监听端口:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        p_row.addWidget(self.port_spin)
        perf_layout.addLayout(p_row)

        c_row = QHBoxLayout()
        self.del_tmp_cb = QCheckBox("下载完成后自动清理临时分片目录")
        self.auto_start_cb = QCheckBox("插件推送任务后自动开始下载")
        c_row.addWidget(self.del_tmp_cb)
        c_row.addWidget(self.auto_start_cb)
        perf_layout.addLayout(c_row)

        layout.addWidget(perf_group)

        # 4. 媒体默认选项与缓存清理
        media_group = QGroupBox("媒体处理与自动命名配置")
        media_layout = QVBoxLayout(media_group)

        self.auto_convert_mp4_cb = QCheckBox("自动将下载的视频/流媒体转为标准 MP4 格式 (集成 FFmpeg + faststart 极速起播)")
        self.attach_metadata_cb = QCheckBox("保存文件名自动附带媒体规格信息 (格式: 视频名称 [分辨率] [时长].mp4)")

        media_layout.addWidget(self.auto_convert_mp4_cb)
        media_layout.addWidget(self.attach_metadata_cb)

        cache_row = QHBoxLayout()
        cache_row.addWidget(QLabel("磁盘缓存与临时碎片:"))
        btn_clean_cache = QPushButton("扫描并清理缓存...")
        btn_clean_cache.setIcon(get_icon("clean", "#a1a1aa", 16))
        btn_clean_cache.clicked.connect(self._open_clean_dialog)
        cache_row.addWidget(btn_clean_cache)
        cache_row.addStretch()
        media_layout.addLayout(cache_row)

        ext_row = QHBoxLayout()
        ext_row.addWidget(QLabel("星流嗅探扩展目录:"))
        self.ext_edit = QLineEdit()
        self.ext_edit.setPlaceholderText("自动识别插件文件夹路径 (支持自定义)")
        btn_browse_ext = QPushButton("浏览...")
        btn_browse_ext.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_browse_ext.clicked.connect(self._browse_extension_dir)
        btn_ext = QPushButton("安装教学与安全跳转指引...")
        btn_ext.setIcon(get_icon("extension", "#38bdf8", 16))
        btn_ext.clicked.connect(self._open_extension_tutorial)
        ext_row.addWidget(self.ext_edit, 1)
        ext_row.addWidget(btn_browse_ext)
        ext_row.addWidget(btn_ext)
        media_layout.addLayout(ext_row)

        layout.addWidget(media_group)

        # 底部操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存设置")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self._save_settings)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _load_values(self):
        self.save_edit.setText(config.get("save_dir", ""))
        self.ff_edit.setText(get_ffmpeg_path())
        self.re_edit.setText(config.get("re_cli_path", ""))
        self.ext_edit.setText(get_extension_dir())

        eng = config.get("stream_engine", "RE")
        if eng == "V3":
            self.engine_combo.setCurrentIndex(1)
        elif eng == "INTERNAL":
            self.engine_combo.setCurrentIndex(2)
        else:
            self.engine_combo.setCurrentIndex(0)

        # 加载代理模式
        mode = config.get("proxy_mode", "none")
        if mode == "system":
            self.radio_system.setChecked(True)
        elif mode == "manual":
            self.radio_manual.setChecked(True)
        else:
            self.radio_none.setChecked(True)

        sys_p = detect_system_proxy()
        if sys_p:
            self.lbl_system_proxy_info.setText(f"检测到系统代理: {sys_p}")
        else:
            self.lbl_system_proxy_info.setText("当前系统未启用全局代理 (直连)")

        self._refresh_proxy_table()
        self._update_proxy_ui_state()

        self.max_tasks_spin.setValue(config.get("max_concurrent_tasks", 3))
        self.max_threads_spin.setValue(config.get("max_threads_per_task", 16))
        self.port_spin.setValue(int(config.get("server_port", 18910)))
        self.del_tmp_cb.setChecked(config.get("del_tmp_files", True))
        self.auto_start_cb.setChecked(config.get("auto_start_tasks", True))
        self.auto_convert_mp4_cb.setChecked(config.get("auto_convert_mp4", True))
        self.attach_metadata_cb.setChecked(config.get("attach_metadata", True))

    def _update_proxy_ui_state(self):
        is_manual = self.radio_manual.isChecked()
        self.manual_widget.setEnabled(is_manual)

    def _refresh_proxy_table(self):
        proxies = config.get_proxies_list()
        self.proxy_table.setRowCount(len(proxies))
        self.active_proxy_combo.clear()

        active_id = config.get("active_proxy_id")
        active_idx = 0

        for r, p in enumerate(proxies):
            self.proxy_table.setItem(r, 0, QTableWidgetItem(p.get("name", "")))
            self.proxy_table.setItem(r, 1, QTableWidgetItem(p.get("url", "")))
            
            btn_test = QPushButton("测试")
            btn_test.clicked.connect(lambda _, url=p.get("url", ""): self._test_single_proxy(url))
            self.proxy_table.setCellWidget(r, 2, btn_test)

            self.active_proxy_combo.addItem(f"{p.get('name')} ({p.get('url')})", p.get("id"))
            if p.get("id") == active_id:
                active_idx = r

        if proxies:
            self.active_proxy_combo.setCurrentIndex(active_idx)

    def _on_active_proxy_changed(self, idx):
        if idx >= 0:
            pid = self.active_proxy_combo.itemData(idx)
            config.set("active_proxy_id", pid)

    def _add_proxy(self):
        name, ok1 = QInputDialog.getText(self, "添加代理节点", "请输入代理节点备注名称 (如 Clash / v2rayN):")
        if not ok1 or not name.strip():
            return
        url, ok2 = QInputDialog.getText(self, "添加代理节点", "请输入代理地址 (如 http://127.0.0.1:7890 或 socks5://127.0.0.1:10808):")
        if not ok2 or not url.strip():
            return
        config.add_proxy(name.strip(), url.strip())
        self._refresh_proxy_table()

    def _del_proxy(self):
        cur_row = self.proxy_table.currentRow()
        if cur_row < 0:
            QMessageBox.information(self, "提示", "请先在表格中选中要删除的代理节点！")
            return
        proxies = config.get_proxies_list()
        if cur_row < len(proxies):
            pid = proxies[cur_row].get("id")
            config.delete_proxy(pid)
            self._refresh_proxy_table()

    def _test_active_proxy(self):
        eff = config.get_effective_proxy()
        if not eff:
            QMessageBox.information(self, "代理测试", "当前未选定有效代理地址！")
            return
        self._test_single_proxy(eff)

    def _test_single_proxy(self, proxy_url):
        t0 = time.time()
        try:
            handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
            opener = urllib.request.build_opener(handler)
            req = urllib.request.Request("http://www.google.com/generate_204", headers={'User-Agent': 'Mozilla/5.0'})
            with opener.open(req, timeout=3.5) as resp:
                cost = int((time.time() - t0) * 1000)
                QMessageBox.information(self, "代理连通性测试", f"连接成功！\n代理: {proxy_url}\n响应延迟: {cost} ms")
                return
        except Exception:
            pass

        # 尝试国内备用目标
        try:
            handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
            opener = urllib.request.build_opener(handler)
            req = urllib.request.Request("http://www.baidu.com", headers={'User-Agent': 'Mozilla/5.0'})
            with opener.open(req, timeout=3.5) as resp:
                cost = int((time.time() - t0) * 1000)
                QMessageBox.information(self, "代理连通性测试", f"连接成功！(通过百度验证)\n代理: {proxy_url}\n响应延迟: {cost} ms")
                return
        except Exception as e:
            QMessageBox.warning(self, "代理测试失败", f"无法通过该代理访问网络:\n{proxy_url}\n\n错误提示: {e}")

    def _browse_save_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择默认下载目录", self.save_edit.text())
        if d:
            self.save_edit.setText(d)

    def _browse_ffmpeg(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 ffmpeg.exe", self.ff_edit.text() or ROOT_DIR, "ffmpeg.exe (ffmpeg.exe)")
        if f:
            self.ff_edit.setText(f)

    def _test_ffmpeg(self):
        path = self.ff_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "FFmpeg 校验", "指定的文件路径不存在！")
            return
        try:
            p = subprocess.run([path, "-version"], stdout=subprocess.PIPE, text=True, timeout=5)
            if p.returncode == 0:
                first = p.stdout.splitlines()[0]
                QMessageBox.information(self, "FFmpeg 校验成功", f"有效引擎:\n{first}")
            else:
                QMessageBox.warning(self, "FFmpeg 校验失败", f"返回错误代码: {p.returncode}")
        except Exception as e:
            QMessageBox.critical(self, "FFmpeg 校验异常", str(e))

    def _browse_re(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 N_m3u8DL-RE.exe", self.re_edit.text() or ROOT_DIR, "Executable (*.exe);;All Files (*)")
        if f:
            self.re_edit.setText(f)

    def _download_nm3u8dl(self):
        webbrowser.open(NM3U8DL_RE_DOWNLOAD_URL)

    def _rescan_tools(self):
        st = config.rescan_tools()
        self.ff_edit.setText(config.get("ffmpeg_path", ""))
        self.re_edit.setText(config.get("re_cli_path", ""))
        if st["found"]:
            QMessageBox.information(self, "探测成功", f"全盘扫描成功找到 N_m3u8DL 引擎:\n{st['active_path']}")
        else:
            QMessageBox.warning(self, "未找到引擎", "全盘扫描未能在常见目录或 PATH 中检测到 N_m3u8DL-RE.exe。\n请点击「获取最新版本」前往 GitHub 下载官方发布包。")

    def _browse_extension_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择扩展源码目录 (包含 manifest.json)", self.ext_edit.text() or ROOT_DIR)
        if d:
            if is_valid_extension_dir(d):
                self.ext_edit.setText(d)
                set_custom_extension_dir(d)
                QMessageBox.information(self, "设置成功", f"已更新扩展目录为:\n{d}")
            else:
                reply = QMessageBox.question(
                    self, "确认选择",
                    f"所选目录中未检测到 manifest.json 扩展清单文件：\n{d}\n\n是否仍将其作为扩展目录？",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.ext_edit.setText(d)
                    set_custom_extension_dir(d)

    def _save_settings(self):
        eng_idx = self.engine_combo.currentIndex()
        engine_str = "RE" if eng_idx == 0 else ("V3" if eng_idx == 1 else "INTERNAL")

        mode = "none"
        if self.radio_system.isChecked():
            mode = "system"
        elif self.radio_manual.isChecked():
            mode = "manual"

        config.update({
            "save_dir": self.save_edit.text().strip(),
            "ffmpeg_path": self.ff_edit.text().strip(),
            "re_cli_path": self.re_edit.text().strip(),
            "extension_dir": self.ext_edit.text().strip(),
            "stream_engine": engine_str,
            "proxy_mode": mode,
            "max_concurrent_tasks": self.max_tasks_spin.value(),
            "max_threads_per_task": self.max_threads_spin.value(),
            "del_tmp_files": self.del_tmp_cb.isChecked(),
            "auto_start_tasks": self.auto_start_cb.isChecked(),
            "auto_convert_mp4": self.auto_convert_mp4_cb.isChecked(),
            "attach_metadata": self.attach_metadata_cb.isChecked(),
            "server_port": self.port_spin.value()
        })
        self.accept()

    def _open_clean_dialog(self):
        dlg = CacheCleanDialog(self)
        dlg.exec_()

    def _open_extension_tutorial(self):
        dlg = ExtensionTutorialDialog(self)
        dlg.exec_()
