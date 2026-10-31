"""
CatCatch Downloader - FFmpeg Toolbox Dialog (内置 FFmpeg 视音频超级工具箱)
无 Emoji、全矢量图标、现代工程级界面设计
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QTabWidget, QWidget,
    QProgressBar, QTextEdit, QGroupBox, QMessageBox, QSpinBox,
    QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

from catcatch_app.core.config import config
from catcatch_app.core.ffmpeg_engine import (
    is_ffmpeg_available, probe_media_info, transcode,
    mux_video_audio, extract_audio, trim_media, repair_media
)
from catcatch_app.ui.icons import get_icon, get_app_icon
from catcatch_app.ui.batch_convert_dialog import BatchConvertDialog


class WorkerBridge(QObject):
    progress_sig = pyqtSignal(float, str, str)
    log_sig = pyqtSignal(str)
    finished_sig = pyqtSignal(bool, str)


class FFmpegToolboxDialog(QDialog):
    def __init__(self, parent=None, preset_file=""):
        super().__init__(parent)
        self.setWindowTitle("FFmpeg 多媒体专业处理工具箱 - 星流下载器")
        self.setWindowIcon(get_app_icon())
        self.resize(740, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.bridge = WorkerBridge()
        self.bridge.progress_sig.connect(self._on_progress)
        self.bridge.log_sig.connect(self._on_log)
        self.bridge.finished_sig.connect(self._on_finished)

        self.current_task = None
        self._init_ui(preset_file)
        self._check_ffmpeg_status()

    def _init_ui(self, preset_file):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 状态指示条
        self.status_banner = QLabel("正在检测 FFmpeg 引擎...")
        self.status_banner.setStyleSheet("padding: 6px 12px; background-color: #1a1b20; border: 1px solid #282b32; border-radius: 4px; font-weight: 500;")
        main_layout.addWidget(self.status_banner)

        # 选项卡
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_convert_tab(preset_file), "单文件转换")
        self.tabs.addTab(self._create_batch_tab(preset_file), "批量格式转换")
        self.tabs.addTab(self._create_mux_tab(preset_file), "音视频混流")
        self.tabs.addTab(self._create_extract_tab(preset_file), "提取音频")
        self.tabs.addTab(self._create_trim_tab(preset_file), "无损剪切")
        self.tabs.addTab(self._create_repair_tab(preset_file), "文件修复")
        self.tabs.addTab(self._create_probe_tab(preset_file), "媒体探查")
        main_layout.addWidget(self.tabs)

        # 底部执行输出
        exec_group = QGroupBox("执行进度与日志")
        exec_layout = QVBoxLayout(exec_group)

        prog_layout = QHBoxLayout()
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.spd_label = QLabel("")
        prog_layout.addWidget(self.prog_bar, 4)
        prog_layout.addWidget(self.spd_label, 1)
        exec_layout.addLayout(prog_layout)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(130)
        self.log_text.setStyleSheet("background-color: #141518; font-family: Consolas, monospace; font-size: 11px; border: 1px solid #23252a;")
        exec_layout.addWidget(self.log_text)

        btn_row = QHBoxLayout()
        self.open_dir_btn = QPushButton("打开输出目录")
        self.open_dir_btn.setIcon(get_icon("folder", "#a1a1aa", 16))
        self.open_dir_btn.clicked.connect(self._open_output_dir)
        self.open_dir_btn.setEnabled(False)
        self.cancel_btn = QPushButton("停止")
        self.cancel_btn.setIcon(get_icon("stop", "#a1a1aa", 16))
        self.cancel_btn.clicked.connect(self._cancel_task)
        self.cancel_btn.setEnabled(False)
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)

        btn_row.addWidget(self.open_dir_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.close_btn)
        exec_layout.addLayout(btn_row)

        main_layout.addWidget(exec_group)
        self.last_output_file = ""

    def _check_ffmpeg_status(self):
        ok, msg = is_ffmpeg_available()
        if ok:
            self.status_banner.setText(f"引擎状态: 已就绪 ({msg})")
            self.status_banner.setStyleSheet("padding: 6px 12px; background-color: #14241e; color: #4ade80; border: 1px solid #166534; border-radius: 4px; font-weight: 500;")
        else:
            self.status_banner.setText(f"引擎状态: 未就绪 ({msg})")
            self.status_banner.setStyleSheet("padding: 6px 12px; background-color: #2e171b; color: #f87171; border: 1px solid #991b1b; border-radius: 4px; font-weight: 500;")

    # 1. 批量转换 Tab
    def _create_batch_tab(self, preset_file):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        info_box = QFrame()
        info_box.setStyleSheet("background-color: #1c1d22; border: 1px solid #2e3038; border-radius: 8px; padding: 18px;")
        ib_layout = QVBoxLayout(info_box)
        ib_layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(get_icon("refresh", "#38bdf8", 18).pixmap(18, 18))
        title = QLabel("批量媒体格式转换中心")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f4f4f5;")
        title_row.addWidget(title_icon)
        title_row.addWidget(title, 1)
        ib_layout.addLayout(title_row)

        desc = QLabel(
            "• 支持批量选择多文件或一键扫描整个文件夹（支持 MP4、MKV、TS、FLV、MOV、AVI、MP3、M4A 等）\n"
            "• 提供智能极速无损拷贝 (-c copy，秒级无损封装转码)\n"
            "• 提供 H.264 / H.265 / 音频提取等多种工业级转换预设\n"
            "• 支持多任务排队顺序转换、单文件与总体双重进度条及一键输出"
        )
        desc.setStyleSheet("color: #a1a1aa; line-height: 1.6; font-size: 12px;")
        ib_layout.addWidget(desc)

        btn_open = QPushButton("立即打开批量转换中心...")
        btn_open.setIcon(get_icon("refresh", "#ffffff", 14))
        btn_open.setStyleSheet("""
            QPushButton {
                background-color: #3875f6;
                color: #ffffff;
                font-weight: 600;
                font-size: 13px;
                padding: 8px 22px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        def open_dialog():
            files = [preset_file] if preset_file and os.path.exists(preset_file) else None
            dlg = BatchConvertDialog(self, preset_files=files)
            dlg.exec_()
        btn_open.clicked.connect(open_dialog)
        ib_layout.addWidget(btn_open, 0, Qt.AlignLeft)

        layout.addWidget(info_box)
        layout.addStretch()
        return widget

    # 2. 单文件格式转换 Tab
    def _create_convert_tab(self, preset_file):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("输入文件:"))
        self.conv_in_edit = QLineEdit(preset_file)
        conv_browse_in = QPushButton("浏览...")
        conv_browse_in.setIcon(get_icon("folder", "#a1a1aa", 16))
        conv_browse_in.clicked.connect(lambda: self._choose_file(self.conv_in_edit))
        in_row.addWidget(self.conv_in_edit)
        in_row.addWidget(conv_browse_in)
        layout.addLayout(in_row)

        param_box = QGroupBox("参数设置")
        p_layout = QVBoxLayout(param_box)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("目标格式:"))
        self.conv_fmt_combo = QComboBox()
        self.conv_fmt_combo.addItems(["MP4 (通用推荐)", "MKV", "TS", "MOV", "FLV", "WebM"])
        r1.addWidget(self.conv_fmt_combo)

        r1.addWidget(QLabel("视频编码:"))
        self.conv_vcodec_combo = QComboBox()
        self.conv_vcodec_combo.addItems(["copy (极速无损封装)", "libx264 (H.264 高兼容)", "libx265 (HEVC 高压缩)"])
        r1.addWidget(self.conv_vcodec_combo)
        p_layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("音频编码:"))
        self.conv_acodec_combo = QComboBox()
        self.conv_acodec_combo.addItems(["copy (保持原音轨)", "aac (推荐)", "libmp3lame (MP3)"])
        r2.addWidget(self.conv_acodec_combo)

        r2.addWidget(QLabel("CRF 质量:"))
        self.conv_crf_spin = QSpinBox()
        self.conv_crf_spin.setRange(15, 35)
        self.conv_crf_spin.setValue(23)
        r2.addWidget(self.conv_crf_spin)
        p_layout.addLayout(r2)

        layout.addWidget(param_box)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("输出路径:"))
        self.conv_out_edit = QLineEdit()
        self.conv_in_edit.textChanged.connect(lambda t: self._auto_fill_out(t, self.conv_out_edit, ".mp4"))
        conv_browse_out = QPushButton("另存为...")
        conv_browse_out.clicked.connect(lambda: self._save_file(self.conv_out_edit))
        out_row.addWidget(self.conv_out_edit)
        out_row.addWidget(conv_browse_out)
        layout.addLayout(out_row)

        btn_row = QHBoxLayout()
        self.conv_start_btn = QPushButton("开始转换")
        self.conv_start_btn.setIcon(get_icon("play", "#ffffff", 16))
        self.conv_start_btn.setProperty("class", "primary")
        self.conv_start_btn.clicked.connect(self._start_convert)
        btn_row.addStretch()
        btn_row.addWidget(self.conv_start_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        if preset_file:
            self._auto_fill_out(preset_file, self.conv_out_edit, ".mp4")

        return widget

    # 2. 音视频混流 Tab
    def _create_mux_tab(self, preset_file):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("纯视频流/主视频:"))
        self.mux_v_edit = QLineEdit(preset_file)
        btn_v = QPushButton("浏览...")
        btn_v.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_v.clicked.connect(lambda: self._choose_file(self.mux_v_edit))
        r1.addWidget(self.mux_v_edit)
        r1.addWidget(btn_v)
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("纯音频流/音轨文件:"))
        self.mux_a_edit = QLineEdit()
        btn_a = QPushButton("浏览...")
        btn_a.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_a.clicked.connect(lambda: self._choose_file(self.mux_a_edit))
        r2.addWidget(self.mux_a_edit)
        r2.addWidget(btn_a)
        layout.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("合成输出路径:"))
        self.mux_out_edit = QLineEdit()
        self.mux_v_edit.textChanged.connect(lambda t: self._auto_fill_out(t, self.mux_out_edit, "_mux.mp4"))
        btn_out = QPushButton("另存为...")
        btn_out.clicked.connect(lambda: self._save_file(self.mux_out_edit))
        r3.addWidget(self.mux_out_edit)
        r3.addWidget(btn_out)
        layout.addLayout(r3)

        btn_row = QHBoxLayout()
        self.mux_start_btn = QPushButton("开始合成")
        self.mux_start_btn.setIcon(get_icon("play", "#ffffff", 16))
        self.mux_start_btn.setProperty("class", "primary")
        self.mux_start_btn.clicked.connect(self._start_mux)
        btn_row.addStretch()
        btn_row.addWidget(self.mux_start_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        return widget

    # 3. 提取音频 Tab
    def _create_extract_tab(self, preset_file):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("输入视频文件:"))
        self.ext_in_edit = QLineEdit(preset_file)
        btn_in = QPushButton("浏览...")
        btn_in.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_in.clicked.connect(lambda: self._choose_file(self.ext_in_edit))
        r1.addWidget(self.ext_in_edit)
        r1.addWidget(btn_in)
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("目标音频格式:"))
        self.ext_fmt_combo = QComboBox()
        self.ext_fmt_combo.addItems(["MP3", "M4A / AAC", "WAV", "FLAC", "原始音轨复制 (copy)"])
        self.ext_fmt_combo.currentIndexChanged.connect(self._on_extract_fmt_change)
        r2.addWidget(self.ext_fmt_combo)

        r2.addWidget(QLabel("比特率:"))
        self.ext_br_combo = QComboBox()
        self.ext_br_combo.addItems(["320k", "256k", "192k", "128k"])
        self.ext_br_combo.setCurrentIndex(2)
        r2.addWidget(self.ext_br_combo)
        layout.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("输出路径:"))
        self.ext_out_edit = QLineEdit()
        self.ext_in_edit.textChanged.connect(lambda t: self._auto_fill_out(t, self.ext_out_edit, ".mp3"))
        btn_out = QPushButton("另存为...")
        btn_out.clicked.connect(lambda: self._save_file(self.ext_out_edit))
        r3.addWidget(self.ext_out_edit)
        r3.addWidget(btn_out)
        layout.addLayout(r3)

        btn_row = QHBoxLayout()
        self.ext_start_btn = QPushButton("开始提取")
        self.ext_start_btn.setIcon(get_icon("play", "#ffffff", 16))
        self.ext_start_btn.setProperty("class", "primary")
        self.ext_start_btn.clicked.connect(self._start_extract)
        btn_row.addStretch()
        btn_row.addWidget(self.ext_start_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        return widget

    def _on_extract_fmt_change(self, idx):
        ext_map = {0: ".mp3", 1: ".m4a", 2: ".wav", 3: ".flac", 4: ".aac"}
        ext = ext_map.get(idx, ".mp3")
        self._auto_fill_out(self.ext_in_edit.text(), self.ext_out_edit, ext)

    # 4. 剪切 Tab
    def _create_trim_tab(self, preset_file):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("输入文件:"))
        self.trim_in_edit = QLineEdit(preset_file)
        btn_in = QPushButton("浏览...")
        btn_in.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_in.clicked.connect(lambda: self._choose_file(self.trim_in_edit))
        r1.addWidget(self.trim_in_edit)
        r1.addWidget(btn_in)
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("开始时间:"))
        self.trim_start_edit = QLineEdit("00:00:00")
        r2.addWidget(self.trim_start_edit)

        r2.addWidget(QLabel("结束时间:"))
        self.trim_end_edit = QLineEdit("00:01:00")
        r2.addWidget(self.trim_end_edit)
        layout.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("输出路径:"))
        self.trim_out_edit = QLineEdit()
        self.trim_in_edit.textChanged.connect(lambda t: self._auto_fill_out(t, self.trim_out_edit, "_cut.mp4"))
        btn_out = QPushButton("另存为...")
        btn_out.clicked.connect(lambda: self._save_file(self.trim_out_edit))
        r3.addWidget(self.trim_out_edit)
        r3.addWidget(btn_out)
        layout.addLayout(r3)

        btn_row = QHBoxLayout()
        self.trim_start_btn = QPushButton("开始剪切")
        self.trim_start_btn.setIcon(get_icon("play", "#ffffff", 16))
        self.trim_start_btn.setProperty("class", "primary")
        self.trim_start_btn.clicked.connect(self._start_trim)
        btn_row.addStretch()
        btn_row.addWidget(self.trim_start_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        return widget

    # 5. 修复 Tab
    def _create_repair_tab(self, preset_file):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        tip = QLabel("重建 MP4/TS 视频头索引 (moov faststart)，修复因意外中断导致不可播放的视频。")
        tip.setStyleSheet("color: #71717a; font-size: 12px;")
        layout.addWidget(tip)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("待修复文件:"))
        self.rep_in_edit = QLineEdit(preset_file)
        btn_in = QPushButton("浏览...")
        btn_in.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_in.clicked.connect(lambda: self._choose_file(self.rep_in_edit))
        r1.addWidget(self.rep_in_edit)
        r1.addWidget(btn_in)
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("修复后保存为:"))
        self.rep_out_edit = QLineEdit()
        self.rep_in_edit.textChanged.connect(lambda t: self._auto_fill_out(t, self.rep_out_edit, "_fixed.mp4"))
        btn_out = QPushButton("另存为...")
        btn_out.clicked.connect(lambda: self._save_file(self.rep_out_edit))
        r2.addWidget(self.rep_out_edit)
        r2.addWidget(btn_out)
        layout.addLayout(r2)

        btn_row = QHBoxLayout()
        self.rep_start_btn = QPushButton("开始修复")
        self.rep_start_btn.setIcon(get_icon("play", "#ffffff", 16))
        self.rep_start_btn.setProperty("class", "primary")
        self.rep_start_btn.clicked.connect(self._start_repair)
        btn_row.addStretch()
        btn_row.addWidget(self.rep_start_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        return widget

    # 6. 媒体探查 Tab
    def _create_probe_tab(self, preset_file):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("媒体文件:"))
        self.probe_in_edit = QLineEdit(preset_file)
        btn_in = QPushButton("浏览...")
        btn_in.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_in.clicked.connect(lambda: self._choose_file(self.probe_in_edit))
        btn_probe = QPushButton("解析信息")
        btn_probe.setIcon(get_icon("search", "#a1a1aa", 16))
        btn_probe.clicked.connect(self._probe_file)
        r1.addWidget(self.probe_in_edit)
        r1.addWidget(btn_in)
        r1.addWidget(btn_probe)
        layout.addLayout(r1)

        self.probe_info_text = QTextEdit()
        self.probe_info_text.setReadOnly(True)
        self.probe_info_text.setStyleSheet("background-color: #141518; font-family: Consolas, monospace; border: 1px solid #23252a;")
        layout.addWidget(self.probe_info_text)

        if preset_file:
            self._probe_file()

        return widget

    def _auto_fill_out(self, in_file, out_edit, suffix_or_ext):
        if not in_file:
            return
        base, ext = os.path.splitext(in_file)
        if suffix_or_ext.startswith("."):
            out_file = f"{base}_converted{suffix_or_ext}"
        else:
            out_file = f"{base}{suffix_or_ext}"
        out_edit.setText(out_file)

    def _choose_file(self, edit):
        f, _ = QFileDialog.getOpenFileName(self, "选择文件", config.get("save_dir"), "所有媒体 (*.*)")
        if f:
            edit.setText(f)

    def _save_file(self, edit):
        f, _ = QFileDialog.getSaveFileName(self, "保存文件", edit.text() or config.get("save_dir"))
        if f:
            edit.setText(f)

    def _before_task(self, output_file):
        self.last_output_file = output_file
        self.prog_bar.setValue(0)
        self.spd_label.setText("准备中...")
        self.log_text.clear()
        self.open_dir_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

    def _on_progress(self, pct, spd, time_str):
        self.prog_bar.setValue(int(pct))
        if spd:
            self.spd_label.setText(f"{spd} ({int(pct)}%)")

    def _on_log(self, line):
        self.log_text.append(line)

    def _on_finished(self, success, msg):
        self.cancel_btn.setEnabled(False)
        if success:
            self.prog_bar.setValue(100)
            self.spd_label.setText("完成")
            self.open_dir_btn.setEnabled(True)
            QMessageBox.information(self, "完成", f"任务已处理完毕！\n输出文件: {self.last_output_file}")
        else:
            self.spd_label.setText("异常")
            QMessageBox.critical(self, "失败", f"处理失败: {msg}")

    def _cancel_task(self):
        if self.current_task:
            self.current_task.cancel()
            self.cancel_btn.setEnabled(False)
            self.spd_label.setText("已停止")

    def _open_output_dir(self):
        if self.last_output_file and os.path.exists(os.path.dirname(self.last_output_file)):
            os.startfile(os.path.dirname(self.last_output_file))

    def _start_convert(self):
        inp = self.conv_in_edit.text().strip()
        out = self.conv_out_edit.text().strip()
        if not inp or not os.path.exists(inp):
            QMessageBox.warning(self, "提示", "请选择有效的输入文件！")
            return
        if not out:
            QMessageBox.warning(self, "提示", "请指定输出路径！")
            return

        vcodec_map = {0: "copy", 1: "libx264", 2: "libx265"}
        vcodec = vcodec_map.get(self.conv_vcodec_combo.currentIndex(), "copy")
        acodec_map = {0: "copy", 1: "aac", 2: "libmp3lame"}
        acodec = acodec_map.get(self.conv_acodec_combo.currentIndex(), "copy")

        self._before_task(out)
        self.current_task = transcode(
            inp, out, vcodec=vcodec, acodec=acodec, crf=self.conv_crf_spin.value(),
            on_progress=lambda p, s, t: self.bridge.progress_sig.emit(p, s, t),
            on_log=lambda l: self.bridge.log_sig.emit(l),
            on_finished=lambda s, m: self.bridge.finished_sig.emit(s, m)
        )

    def _start_mux(self):
        v = self.mux_v_edit.text().strip()
        a = self.mux_a_edit.text().strip()
        out = self.mux_out_edit.text().strip()
        if not v or not os.path.exists(v):
            QMessageBox.warning(self, "提示", "请选择主视频文件！")
            return
        if not a or not os.path.exists(a):
            QMessageBox.warning(self, "提示", "请选择音轨文件！")
            return
        if not out:
            QMessageBox.warning(self, "提示", "请指定输出路径！")
            return

        self._before_task(out)
        self.current_task = mux_video_audio(
            v, a, out,
            on_progress=lambda p, s, t: self.bridge.progress_sig.emit(p, s, t),
            on_log=lambda l: self.bridge.log_sig.emit(l),
            on_finished=lambda s, m: self.bridge.finished_sig.emit(s, m)
        )

    def _start_extract(self):
        inp = self.ext_in_edit.text().strip()
        out = self.ext_out_edit.text().strip()
        if not inp or not os.path.exists(inp):
            QMessageBox.warning(self, "提示", "请选择输入视频文件！")
            return
        if not out:
            QMessageBox.warning(self, "提示", "请指定音频输出路径！")
            return

        fmt_map = {0: "mp3", 1: "m4a", 2: "wav", 3: "flac", 4: "copy"}
        fmt_name = fmt_map.get(self.ext_fmt_combo.currentIndex(), "mp3")
        br = self.ext_br_combo.currentText().split()[0]

        self._before_task(out)
        self.current_task = extract_audio(
            inp, out, format_name=fmt_name, bitrate=br,
            on_progress=lambda p, s, t: self.bridge.progress_sig.emit(p, s, t),
            on_log=lambda l: self.bridge.log_sig.emit(l),
            on_finished=lambda s, m: self.bridge.finished_sig.emit(s, m)
        )

    def _start_trim(self):
        inp = self.trim_in_edit.text().strip()
        out = self.trim_out_edit.text().strip()
        s = self.trim_start_edit.text().strip()
        e = self.trim_end_edit.text().strip()
        if not inp or not os.path.exists(inp):
            QMessageBox.warning(self, "提示", "请选择输入视频文件！")
            return
        if not out:
            QMessageBox.warning(self, "提示", "请指定输出路径！")
            return

        self._before_task(out)
        self.current_task = trim_media(
            inp, out, s, e, is_duration=False, copy_codec=True,
            on_progress=lambda p, s, t: self.bridge.progress_sig.emit(p, s, t),
            on_log=lambda l: self.bridge.log_sig.emit(l),
            on_finished=lambda ok, m: self.bridge.finished_sig.emit(ok, m)
        )

    def _start_repair(self):
        inp = self.rep_in_edit.text().strip()
        out = self.rep_out_edit.text().strip()
        if not inp or not os.path.exists(inp):
            QMessageBox.warning(self, "提示", "请选择待修复文件！")
            return
        if not out:
            QMessageBox.warning(self, "提示", "请指定保存路径！")
            return

        self._before_task(out)
        self.current_task = repair_media(
            inp, out,
            on_progress=lambda p, s, t: self.bridge.progress_sig.emit(p, s, t),
            on_log=lambda l: self.bridge.log_sig.emit(l),
            on_finished=lambda ok, m: self.bridge.finished_sig.emit(ok, m)
        )

    def _probe_file(self):
        inp = self.probe_in_edit.text().strip()
        if not inp or not os.path.exists(inp):
            return
        info = probe_media_info(inp)
        res = f"=== 媒体信息解析 ===\n"
        res += f"时长: {info.get('duration_str')} ({info.get('duration')} 秒)\n"
        res += f"分辨率: {info.get('resolution')}\n"
        res += f"视频编码: {info.get('vcodec')}\n"
        res += f"音频编码: {info.get('acodec')}\n"
        res += f"帧率: {info.get('fps')} fps\n"
        res += f"码率: {info.get('bitrate')}\n\n"
        res += f"=== FFmpeg 原始探测日志 ===\n"
        res += info.get("raw", "")
        self.probe_info_text.setText(res)
