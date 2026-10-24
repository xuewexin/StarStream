"""
StarStream Downloader - Cache Clean Dialog
下载缓存与临时分块文件清理交互窗口
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QGroupBox, QMessageBox,
    QProgressBar, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from catcatch_app.core.cache_cleaner import scan_cache, clean_cache
from catcatch_app.core.download_file import format_size
from catcatch_app.ui.icons import get_icon, get_app_icon


class CacheCleanDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("清理缓存与临时文件 - 星流下载器")
        self.setWindowIcon(get_app_icon())
        self.setFixedWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._refresh_scan()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # 顶部统计总览
        self.info_box = QGroupBox("缓存占用统计")
        info_layout = QVBoxLayout(self.info_box)
        info_layout.setSpacing(6)

        self.lbl_size = QLabel("正在扫描中...")
        self.lbl_size.setStyleSheet("font-size: 16px; font-weight: 700; color: #38bdf8; margin: 4px 0;")
        info_layout.addWidget(self.lbl_size)

        self.lbl_detail = QLabel()
        self.lbl_detail.setStyleSheet("color: #9ca3af; font-size: 12px;")
        info_layout.addWidget(self.lbl_detail)

        layout.addWidget(self.info_box)

        # 清理选项
        opt_box = QGroupBox("选择清理项目")
        opt_layout = QVBoxLayout(opt_box)
        opt_layout.setSpacing(10)

        self.cb_temp_files = QCheckBox("清理所有分片临时缓存与碎片文件 (.tmp / .part / 临时目录)")
        self.cb_temp_files.setChecked(True)
        opt_layout.addWidget(self.cb_temp_files)

        self.cb_error_tasks = QCheckBox("清理下载失败的历史任务记录")
        self.cb_error_tasks.setChecked(True)
        opt_layout.addWidget(self.cb_error_tasks)

        self.cb_completed_tasks = QCheckBox("清理已完成的任务列表记录 (仅清除列表项，不删除视频文件)")
        self.cb_completed_tasks.setChecked(False)
        opt_layout.addWidget(self.cb_completed_tasks)

        layout.addWidget(opt_box)

        # 底部按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_rescan = QPushButton("重新扫描")
        btn_rescan.setIcon(get_icon("stream", "#a1a1aa", 16))
        btn_rescan.clicked.connect(self._refresh_scan)
        btn_layout.addWidget(btn_rescan)

        btn_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self.btn_clean = QPushButton("立即清理")
        self.btn_clean.setIcon(get_icon("clean", "#ffffff", 16))
        self.btn_clean.setProperty("class", "primary")
        self.btn_clean.setStyleSheet("background-color: #f43f5e; color: #ffffff; font-weight: 600; padding: 6px 16px;")
        self.btn_clean.clicked.connect(self._execute_clean)
        btn_layout.addWidget(self.btn_clean)

        layout.addLayout(btn_layout)

    def _refresh_scan(self):
        stats = scan_cache()
        total_sz = format_size(stats["total_bytes"])
        self.lbl_size.setText(f"临时缓存占用: {total_sz}")

        f_cnt = len(stats["temp_files"])
        d_cnt = len(stats["temp_dirs"])
        err_cnt = stats.get("error_tasks", 0)
        done_cnt = stats.get("completed_tasks", 0)

        self.lbl_detail.setText(
            f"检测到临时碎片文件: {f_cnt} 个 | 临时目录: {d_cnt} 个\n"
            f"失败任务记录: {err_cnt} 条 | 已完成任务: {done_cnt} 条"
        )

        if stats["total_bytes"] == 0 and err_cnt == 0:
            self.btn_clean.setText("暂无残留缓存")
        else:
            self.btn_clean.setText("立即清理")

    def _execute_clean(self):
        del_files = self.cb_temp_files.isChecked()
        del_error = self.cb_error_tasks.isChecked()
        del_done = self.cb_completed_tasks.isChecked()

        if not del_files and not del_error and not del_done:
            QMessageBox.information(self, "提示", "请至少勾选一项需要清理的项目！")
            return

        res = clean_cache(
            clean_temp_files=del_files,
            clean_completed_tasks=del_done,
            clean_error_tasks=del_error
        )

        freed_str = format_size(res["freed_bytes"])
        msg = f"缓存清理完成！\n\n已成功删除 {res['deleted_files_count']} 个临时碎片文件\n释放存储空间: {freed_str}"
        if res["cleared_tasks_count"] > 0:
            msg += f"\n已清理 {res['cleared_tasks_count']} 条任务记录"

        QMessageBox.information(self, "清理成功", msg)
        self.accept()
