"""
StarStream Downloader - Batch Media Converter Dialog (批量媒体格式转换中心)
支持音视频多文件/整目录批量重封装与转码，极速 -c copy 秒级转换，全矢量图标与工程级容错
"""
import os
import subprocess
import threading
import time
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QProgressBar, QGroupBox, QFileDialog, QMessageBox,
    QFrame, QWidget, QRadioButton, QButtonGroup, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QColor, QFont

from catcatch_app.core.config import config
from catcatch_app.core.download_file import format_size
from catcatch_app.core.ffmpeg_engine import (
    get_ffmpeg_path, is_ffmpeg_available, probe_media_info
)
from catcatch_app.ui.icons import get_icon, get_app_icon


SUPPORTED_MEDIA_EXTS = {
    ".mp4", ".mkv", ".ts", ".flv", ".mov", ".avi", ".webm",
    ".m4v", ".m4s", ".aac", ".mp3", ".wav", ".flac", ".ogg",
    ".m4a", ".wma", ".wmv", ".3gp"
}


class BatchWorker(QThread):
    """批量转换后台工作线程"""
    item_progress = pyqtSignal(int, float, str)     # (row_index, percent, speed_str)
    item_finished = pyqtSignal(int, bool, str, str) # (row_index, success, out_path, message)
    overall_progress = pyqtSignal(int, int, float)  # (completed_count, total_count, overall_pct)
    batch_done = pyqtSignal(int, int)               # (success_count, fail_count)
    log_emitted = pyqtSignal(str)

    def __init__(self, task_items, target_format, encode_mode, out_mode, custom_dir, del_src, faststart):
        super().__init__()
        self.task_items = list(task_items)  # [{'row': i, 'src': path, 'duration': float}]
        self.target_format = target_format.lower().lstrip(".")
        self.encode_mode = encode_mode
        self.out_mode = out_mode            # "same_dir" or "custom_dir"
        self.custom_dir = custom_dir
        self.del_src = del_src
        self.faststart = faststart
        self._is_cancelled = False
        self._current_proc = None

    def cancel(self):
        self._is_cancelled = True
        if self._current_proc:
            try:
                self._current_proc.terminate()
                time.sleep(0.2)
                if self._current_proc.poll() is None:
                    self._current_proc.kill()
            except Exception:
                pass

    def run(self):
        ff_exe = get_ffmpeg_path()
        if not ff_exe:
            for item in self.task_items:
                self.item_finished.emit(item["row"], False, "", "未检测到有效 FFmpeg 引擎")
            self.batch_done.emit(0, len(self.task_items))
            return

        total_tasks = len(self.task_items)
        success_count = 0
        fail_count = 0

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        for idx, item in enumerate(self.task_items):
            if self._is_cancelled:
                self.item_finished.emit(item["row"], False, "", "任务已取消")
                fail_count += 1
                continue

            row = item["row"]
            src_path = item["src"]
            total_dur = item.get("duration", 0.0)

            # 计算输出目标路径
            src_dir, src_file = os.path.split(src_path)
            src_name, src_ext = os.path.splitext(src_file)

            if self.out_mode == "same_dir":
                # 同级目录下若格式一致则追加 _converted
                if src_ext.lower().lstrip(".") == self.target_format:
                    out_filename = f"{src_name}_converted.{self.target_format}"
                else:
                    out_filename = f"{src_name}.{self.target_format}"
                target_dir = src_dir
            else:
                target_dir = self.custom_dir
                out_filename = f"{src_name}.{self.target_format}"

            os.makedirs(target_dir, exist_ok=True)
            out_path = os.path.join(target_dir, out_filename)

            # 构建转换命令行
            cmd = [ff_exe, "-y", "-i", src_path]

            is_audio_target = self.target_format in ["mp3", "m4a", "wav", "flac"]

            if is_audio_target:
                cmd.append("-vn")
                if self.target_format == "mp3":
                    cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
                elif self.target_format == "m4a":
                    cmd.extend(["-c:a", "aac", "-b:a", "256k"])
                elif self.target_format == "wav":
                    cmd.extend(["-c:a", "pcm_s16le"])
                elif self.target_format == "flac":
                    cmd.extend(["-c:a", "flac"])
            else:
                if self.encode_mode == "copy":
                    cmd.extend(["-c", "copy"])
                elif self.encode_mode == "h265":
                    cmd.extend(["-c:v", "libx265", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"])
                else:
                    # h264 default
                    cmd.extend(["-c:v", "libx264", "-crf", "22", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"])

            if self.faststart and self.target_format in ["mp4", "mov"]:
                cmd.extend(["-movflags", "+faststart"])

            cmd.append(out_path)

            self.item_progress.emit(row, 0.0, "开始转换...")

            try:
                self._current_proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    bufsize=1,
                    creationflags=creationflags
                )

                time_pat = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)")
                spd_pat = re.compile(r"speed=\s*([\d\.]+)x")

                while True:
                    if self._is_cancelled:
                        break
                    line = self._current_proc.stdout.readline()
                    if not line:
                        break

                    tm = time_pat.search(line)
                    sm = spd_pat.search(line)
                    if tm and total_dur > 0:
                        h, m, s = float(tm.group(1)), float(tm.group(2)), float(tm.group(3))
                        cur_sec = h * 3600 + m * 60 + s
                        pct = min(99.0, (cur_sec / total_dur) * 100.0)
                        spd_s = f"{sm.group(1)}x" if sm else ""
                        self.item_progress.emit(row, pct, spd_s)

                self._current_proc.stdout.close()
                ret = self._current_proc.wait()

                if self._is_cancelled:
                    if os.path.exists(out_path) and os.path.getsize(out_path) == 0:
                        try: os.remove(out_path)
                        except Exception: pass
                    self.item_finished.emit(row, False, "", "已手动取消")
                    fail_count += 1
                elif ret == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    self.item_progress.emit(row, 100.0, "完成")
                    self.item_finished.emit(row, True, out_path, "转换成功")
                    success_count += 1
                    # 自动删除源文件（若勾选）
                    if self.del_src and src_path != out_path:
                        try:
                            os.remove(src_path)
                        except Exception:
                            pass
                else:
                    # 如果 copy 失败，尝试 fallback 转码
                    self.item_finished.emit(row, False, "", f"转换异常 (退出码 {ret})")
                    fail_count += 1

            except Exception as e:
                self.item_finished.emit(row, False, "", f"异常: {e}")
                fail_count += 1

            done_so_far = success_count + fail_count
            overall_pct = (done_so_far / total_tasks) * 100.0
            self.overall_progress.emit(done_so_far, total_tasks, overall_pct)

        self.batch_done.emit(success_count, fail_count)


class BatchConvertDialog(QDialog):
    def __init__(self, parent=None, preset_files=None):
        super().__init__(parent)
        self.setWindowTitle("批量媒体格式转换中心 - 星流下载器 (StarStream)")
        self.setWindowIcon(get_app_icon())
        self.resize(880, 620)
        self.setMinimumSize(780, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.worker = None
        self.file_items = []  # [{'src': path, 'name': str, 'size': int, 'duration': float, 'fmt': str}]
        self.last_output_dir = ""

        self._init_ui()

        if preset_files:
            self.add_files(preset_files)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # 1. 顶部操作栏
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.btn_add_files = QPushButton("添加媒体文件...")
        self.btn_add_files.setIcon(get_icon("add", "#ffffff", 14))
        self.btn_add_files.setStyleSheet("background-color: #3875f6; color: white; font-weight: 600; padding: 6px 14px; border-radius: 4px;")
        self.btn_add_files.clicked.connect(self._on_add_files)
        top_bar.addWidget(self.btn_add_files)

        self.btn_add_dir = QPushButton("扫描添加文件夹...")
        self.btn_add_dir.setIcon(get_icon("folder", "#d4d4d8", 14))
        self.btn_add_dir.setStyleSheet("padding: 6px 14px; border-radius: 4px;")
        self.btn_add_dir.clicked.connect(self._on_add_dir)
        top_bar.addWidget(self.btn_add_dir)

        self.btn_remove_sel = QPushButton("移除选中")
        self.btn_remove_sel.setIcon(get_icon("delete", "#a1a1aa", 14))
        self.btn_remove_sel.clicked.connect(self._on_remove_selected)
        top_bar.addWidget(self.btn_remove_sel)

        self.btn_clear_all = QPushButton("清空列表")
        self.btn_clear_all.setIcon(get_icon("delete", "#f87171", 14))
        self.btn_clear_all.clicked.connect(self._on_clear_all)
        top_bar.addWidget(self.btn_clear_all)

        top_bar.addStretch()

        self.lbl_summary = QLabel("待处理文件: 0 个 | 总大小: 0 MB")
        self.lbl_summary.setStyleSheet("color: #a1a1aa; font-size: 12px; font-weight: 500;")
        top_bar.addWidget(self.lbl_summary)

        layout.addLayout(top_bar)

        # 2. 中间文件列表表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "序号", "源媒体名称", "源格式 / 大小", "时长", "目标格式", "转换进度", "状态"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().resizeSection(0, 50)
        self.table.horizontalHeader().resizeSection(2, 110)
        self.table.horizontalHeader().resizeSection(3, 80)
        self.table.horizontalHeader().resizeSection(4, 90)
        self.table.horizontalHeader().resizeSection(5, 140)
        self.table.horizontalHeader().resizeSection(6, 100)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #18181b;
                alternate-background-color: #202023;
                border: 1px solid #27272a;
                border-radius: 6px;
                gridline-color: #27272a;
            }
        """)
        layout.addWidget(self.table, 1)

        # 3. 转换参数设置面板
        opt_box = QGroupBox("转换参数与输出设置")
        opt_box.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3f3f46;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                font-weight: 600;
                color: #e4e4e7;
            }
        """)
        opt_layout = QVBoxLayout(opt_box)
        opt_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("目标容器格式:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems([
            "MP4 (标准通用容器, 兼容性最佳)",
            "MKV (Matroska 高清多音轨容器)",
            "TS (MPEG-TS 流媒体传输容器)",
            "MOV (Apple QuickTime 格式)",
            "AVI (传统视频格式)",
            "MP3 (提取高品质音频 320kbps)",
            "M4A (AAC 高品质音频 256kbps)",
            "WAV (无损原始音频)",
            "FLAC (无损高保真压缩音频)"
        ])
        self.combo_format.currentIndexChanged.connect(self._update_target_format_column)
        row1.addWidget(self.combo_format, 2)

        row1.addSpacing(15)
        row1.addWidget(QLabel("编码策略:"))
        self.combo_encode = QComboBox()
        self.combo_encode.addItems([
            "智能极速无损拷贝 (-c copy, 极速秒转, 原画原音不重编)",
            "H.264 / AAC 优质兼容模式 (CRF 22, 默认通用稳定)",
            "H.265 / HEVC 高压缩率模式 (体积减半, 高清压缩)"
        ])
        row1.addWidget(self.combo_encode, 3)
        opt_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.rb_same_dir = QRadioButton("保存在源文件同级目录")
        self.rb_same_dir.setChecked(True)
        self.rb_same_dir.toggled.connect(self._toggle_out_dir)
        row2.addWidget(self.rb_same_dir)

        self.rb_custom_dir = QRadioButton("统一保存至指定目录:")
        self.rb_custom_dir.toggled.connect(self._toggle_out_dir)
        row2.addWidget(self.rb_custom_dir)

        default_conv_dir = os.path.join(config.get("save_dir", "Downloads"), "Converted")
        self.edit_custom_dir = QPushButton(default_conv_dir)
        self.edit_custom_dir.setStyleSheet("text-align: left; padding: 4px 8px; border: 1px solid #3f3f46; border-radius: 4px; color: #38bdf8;")
        self.edit_custom_dir.clicked.connect(self._browse_custom_dir)
        self.edit_custom_dir.setEnabled(False)
        row2.addWidget(self.edit_custom_dir, 1)

        opt_layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.chk_faststart = QCheckBox("注入 FastStart 网页秒播索引 (针对 MP4/MOV, 优化播放)")
        self.chk_faststart.setChecked(True)
        row3.addWidget(self.chk_faststart)

        self.chk_del_src = QCheckBox("转换成功后自动删除源文件 (谨慎使用)")
        self.chk_del_src.setStyleSheet("color: #fca5a5;")
        self.chk_del_src.setChecked(False)
        row3.addWidget(self.chk_del_src)

        row3.addStretch()
        opt_layout.addLayout(row3)

        layout.addWidget(opt_box)

        # 4. 底部总体进度与执行按钮
        bottom_box = QFrame()
        bottom_box.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 8px;")
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setSpacing(6)

        prog_head = QHBoxLayout()
        self.lbl_overall_text = QLabel("总体进度: 待启动")
        self.lbl_overall_text.setStyleSheet("font-size: 12px; font-weight: 600; color: #f4f4f5;")
        prog_head.addWidget(self.lbl_overall_text)
        prog_head.addStretch()
        bottom_layout.addLayout(prog_head)

        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 100)
        self.overall_bar.setValue(0)
        self.overall_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3f3f46;
                border-radius: 4px;
                text-align: center;
                height: 18px;
                background-color: #27272a;
                color: #ffffff;
                font-size: 11px;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #38bdf8);
                border-radius: 3px;
            }
        """)
        bottom_layout.addWidget(self.overall_bar)

        act_row = QHBoxLayout()
        self.btn_open_out = QPushButton("打开输出目录")
        self.btn_open_out.setIcon(get_icon("folder", "#a1a1aa", 14))
        self.btn_open_out.clicked.connect(self._open_output_dir)
        self.btn_open_out.setEnabled(False)
        act_row.addWidget(self.btn_open_out)

        act_row.addStretch()

        self.btn_start = QPushButton("开始批量转换")
        self.btn_start.setIcon(get_icon("start", "#ffffff", 14))
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: white;
                font-weight: 700;
                font-size: 13px;
                padding: 7px 22px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #9ca3af;
            }
        """)
        self.btn_start.clicked.connect(self._start_batch)
        act_row.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("停止转换")
        self.btn_cancel.setIcon(get_icon("stop", "#f87171", 14))
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_batch)
        act_row.addWidget(self.btn_cancel)

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        act_row.addWidget(self.btn_close)

        bottom_layout.addLayout(act_row)
        layout.addWidget(bottom_box)

    def _get_target_format_code(self):
        txt = self.combo_format.currentText()
        if "MP4" in txt: return "mp4"
        if "MKV" in txt: return "mkv"
        if "TS" in txt: return "ts"
        if "MOV" in txt: return "mov"
        if "AVI" in txt: return "avi"
        if "MP3" in txt: return "mp3"
        if "M4A" in txt: return "m4a"
        if "WAV" in txt: return "wav"
        if "FLAC" in txt: return "flac"
        return "mp4"

    def _get_encode_mode_code(self):
        idx = self.combo_encode.currentIndex()
        if idx == 0: return "copy"
        if idx == 2: return "h265"
        return "h264"

    def _update_target_format_column(self):
        fmt = self._get_target_format_code().upper()
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 4)
            if it:
                it.setText(fmt)

    def _toggle_out_dir(self):
        self.edit_custom_dir.setEnabled(self.rb_custom_dir.isChecked())

    def _browse_custom_dir(self):
        init_dir = self.edit_custom_dir.text()
        d = QFileDialog.getExistingDirectory(self, "选择统一输出目录", init_dir)
        if d:
            self.edit_custom_dir.setText(os.path.abspath(d))

    def _on_add_files(self):
        filter_str = "多媒体音视频文件 (*.mp4 *.mkv *.ts *.flv *.mov *.avi *.webm *.m4v *.m4s *.aac *.mp3 *.wav *.flac);;所有文件 (*.*)"
        files, _ = QFileDialog.getOpenFileNames(self, "选择要批量转换的媒体文件", config.get("save_dir", ""), filter_str)
        if files:
            self.add_files(files)

    def _on_add_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择扫描目录", config.get("save_dir", ""))
        if not d:
            return
        found = []
        for root, _, fnames in os.walk(d):
            for fname in fnames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in SUPPORTED_MEDIA_EXTS:
                    found.append(os.path.join(root, fname))
        if found:
            self.add_files(found)
            QMessageBox.information(self, "扫描完毕", f"已从目录中成功识别并添加 {len(found)} 个媒体文件！")
        else:
            QMessageBox.information(self, "提示", "所选目录中未发现常见音视频媒体文件。")

    def add_files(self, file_paths):
        target_fmt = self._get_target_format_code().upper()
        added_count = 0

        for p in file_paths:
            if not os.path.isfile(p):
                continue
            if any(item["src"] == p for item in self.file_items):
                continue

            sz = os.path.getsize(p)
            ext = os.path.splitext(p)[1].upper().lstrip(".")
            fname = os.path.basename(p)

            # 简易异步或快速探测时长
            item_data = {
                "src": p,
                "name": fname,
                "size": sz,
                "fmt": ext,
                "duration": 0.0
            }
            self.file_items.append(item_data)

            row = self.table.rowCount()
            self.table.insertRow(row)

            # 0: 序号
            it_idx = QTableWidgetItem(str(row + 1))
            it_idx.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, it_idx)

            # 1: 文件名
            it_name = QTableWidgetItem(fname)
            it_name.setToolTip(p)
            self.table.setItem(row, 1, it_name)

            # 2: 格式与大小
            it_sz = QTableWidgetItem(f"{ext} | {format_size(sz)}")
            it_sz.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, it_sz)

            # 3: 时长
            it_dur = QTableWidgetItem("--")
            it_dur.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, it_dur)

            # 4: 目标格式
            it_tgt = QTableWidgetItem(target_fmt)
            it_tgt.setTextAlignment(Qt.AlignCenter)
            it_tgt.setForeground(QColor("#38bdf8"))
            it_tgt.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 4, it_tgt)

            # 5: 进度条
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(0)
            pbar.setStyleSheet("QProgressBar { height: 16px; text-align: center; font-size: 10px; }")
            self.table.setCellWidget(row, 5, pbar)

            # 6: 状态
            it_st = QTableWidgetItem("等待中")
            it_st.setTextAlignment(Qt.AlignCenter)
            it_st.setForeground(QColor("#fbbf24"))
            self.table.setItem(row, 6, it_st)

            added_count += 1

        self._update_summary()
        self._async_probe_durations()

    def _async_probe_durations(self):
        """后台轻量探测各媒体时长"""
        def run_probe():
            for idx, item in enumerate(self.file_items):
                if item["duration"] == 0.0:
                    try:
                        info = probe_media_info(item["src"])
                        dur = info.get("duration", 0.0)
                        dur_s = info.get("duration_str", "--")
                        item["duration"] = dur
                        it = self.table.item(idx, 3)
                        if it:
                            it.setText(dur_s)
                    except Exception:
                        pass
        t = threading.Thread(target=run_probe, daemon=True)
        t.start()

    def _update_summary(self):
        tot_cnt = len(self.file_items)
        tot_bytes = sum(item["size"] for item in self.file_items)
        self.lbl_summary.setText(f"待处理文件: {tot_cnt} 个 | 总大小: {format_size(tot_bytes)}")

    def _on_remove_selected(self):
        sel_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        for r in sel_rows:
            self.table.removeRow(r)
            if r < len(self.file_items):
                self.file_items.pop(r)

        # 重新排号
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it: it.setText(str(r + 1))
        self._update_summary()

    def _on_clear_all(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "提示", "转换进行中，请先停止任务！")
            return
        self.table.setRowCount(0)
        self.file_items.clear()
        self._update_summary()
        self.overall_bar.setValue(0)
        self.lbl_overall_text.setText("总体进度: 待启动")

    def _start_batch(self):
        if not self.file_items:
            QMessageBox.warning(self, "提示", "请先添加待转换的音视频文件！")
            return

        ok, msg = is_ffmpeg_available()
        if not ok:
            QMessageBox.critical(self, "FFmpeg 引擎未就绪", f"无法启动批量转换：{msg}\n请确认 ffmpeg.exe 位于程序根目录下。")
            return

        target_fmt = self._get_target_format_code()
        enc_mode = self._get_encode_mode_code()
        out_mode = "same_dir" if self.rb_same_dir.isChecked() else "custom_dir"
        custom_dir = self.edit_custom_dir.text()
        del_src = self.chk_del_src.isChecked()
        faststart = self.chk_faststart.isChecked()

        if out_mode == "custom_dir":
            os.makedirs(custom_dir, exist_ok=True)
            self.last_output_dir = custom_dir
        else:
            self.last_output_dir = os.path.dirname(self.file_items[0]["src"])

        tasks = []
        for i, item in enumerate(self.file_items):
            tasks.append({
                "row": i,
                "src": item["src"],
                "duration": item.get("duration", 0.0)
            })
            pbar = self.table.cellWidget(i, 5)
            if pbar: pbar.setValue(0)
            it_st = self.table.item(i, 6)
            if it_st:
                it_st.setText("排队中")
                it_st.setForeground(QColor("#a1a1aa"))

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_add_files.setEnabled(False)
        self.btn_add_dir.setEnabled(False)
        self.btn_remove_sel.setEnabled(False)
        self.btn_clear_all.setEnabled(False)
        self.btn_open_out.setEnabled(False)

        self.worker = BatchWorker(
            tasks, target_fmt, enc_mode, out_mode, custom_dir, del_src, faststart
        )
        self.worker.item_progress.connect(self._on_item_progress)
        self.worker.item_finished.connect(self._on_item_finished)
        self.worker.overall_progress.connect(self._on_overall_progress)
        self.worker.batch_done.connect(self._on_batch_done)
        self.worker.start()

    def _on_item_progress(self, row, pct, spd_str):
        pbar = self.table.cellWidget(row, 5)
        if pbar:
            pbar.setValue(int(pct))
        it_st = self.table.item(row, 6)
        if it_st:
            sp_txt = f" ({spd_str})" if spd_str else ""
            it_st.setText(f"转换中{sp_txt}")
            it_st.setForeground(QColor("#38bdf8"))

    def _on_item_finished(self, row, success, out_path, msg):
        pbar = self.table.cellWidget(row, 5)
        it_st = self.table.item(row, 6)
        if success:
            if pbar: pbar.setValue(100)
            if it_st:
                it_st.setText("已完成")
                it_st.setForeground(QColor("#4ade80"))
        else:
            if it_st:
                it_st.setText(f"失败: {msg}" if msg else "失败")
                it_st.setForeground(QColor("#f87171"))

    def _on_overall_progress(self, done_cnt, tot_cnt, pct):
        self.overall_bar.setValue(int(pct))
        self.lbl_overall_text.setText(f"总体进度: 已完成 {done_cnt}/{tot_cnt} ({pct:.1f}%)")

    def _on_batch_done(self, succ_cnt, fail_cnt):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_add_files.setEnabled(True)
        self.btn_add_dir.setEnabled(True)
        self.btn_remove_sel.setEnabled(True)
        self.btn_clear_all.setEnabled(True)
        self.btn_open_out.setEnabled(True)

        self.lbl_overall_text.setText(f"批量转换完毕！成功: {succ_cnt} 个，失败: {fail_cnt} 个")
        QMessageBox.information(
            self,
            "批量转换完成",
            f"🎉 批量格式转换已全部执行完成！\n\n• 成功: {succ_cnt} 个\n• 失败: {fail_cnt} 个\n\n您可点击下方【打开输出目录】立即查阅文件。"
        )

    def _cancel_batch(self):
        if self.worker and self.worker.isRunning():
            self.btn_cancel.setEnabled(False)
            self.lbl_overall_text.setText("正在安全停止当前转换任务...")
            self.worker.cancel()

    def _open_output_dir(self):
        out_d = self.last_output_dir or config.get("save_dir", "Downloads")
        if os.path.exists(out_d):
            try:
                os.startfile(out_d)
            except Exception as e:
                QMessageBox.warning(self, "提示", f"打开目录失败: {e}")
        else:
            QMessageBox.information(self, "提示", "输出目录尚未生成或不存在。")

