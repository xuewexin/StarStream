"""
StarStream Downloader - Fragments Manager Dialog
专用临时分片文件夹管理中心 (查看、整理、打开与批量删除切片文件)
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QWidget
)
from PyQt5.QtCore import Qt

from catcatch_app.core.config import get_temp_segments_dir
from catcatch_app.core.cache_cleaner import (
    get_fragment_folders, delete_fragment_folder, clean_all_fragment_folders
)
from catcatch_app.core.download_file import format_size
from catcatch_app.ui.icons import get_icon, get_app_icon


class FragmentsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("分片存储与整理管理 - 星流下载器")
        self.setWindowIcon(get_app_icon())
        self.resize(760, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self.refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 顶部提示与目录路径
        top_box = QWidget()
        top_layout = QVBoxLayout(top_box)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(get_icon("folder", "#38bdf8", 18).pixmap(18, 18))
        title_lbl = QLabel("专用分片存储文件夹 (Temp_Segments)")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        title_row.addWidget(title_icon)
        title_row.addWidget(title_lbl, 1)
        top_layout.addLayout(title_row)

        dir_row = QHBoxLayout()
        self.lbl_path = QLabel(get_temp_segments_dir())
        self.lbl_path.setStyleSheet("color: #a1a1aa; font-family: monospace; background: #27272a; padding: 6px 10px; border-radius: 4px;")
        dir_row.addWidget(self.lbl_path, 1)

        btn_open = QPushButton("打开文件夹")
        btn_open.setIcon(get_icon("folder", "#ffffff", 16))
        btn_open.clicked.connect(self._open_in_explorer)
        dir_row.addWidget(btn_open)

        btn_rescan = QPushButton("刷新列表")
        btn_rescan.setIcon(get_icon("refresh", "#ffffff", 16))
        btn_rescan.clicked.connect(self.refresh_list)
        dir_row.addWidget(btn_rescan)

        top_layout.addLayout(dir_row)
        layout.addWidget(top_box)

        # 状态总览
        self.lbl_stats = QLabel("正在扫描分片切片...")
        self.lbl_stats.setStyleSheet("color: #e4e4e7; font-size: 13px; font-weight: 500;")
        layout.addWidget(self.lbl_stats)

        # 分片表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["分片文件夹名称", "切片文件数", "占用大小", "更新时间", "存储状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        layout.addWidget(self.table)

        # 底部操作栏
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_del_selected = QPushButton("删除选中分片")
        self.btn_del_selected.setIcon(get_icon("delete", "#ffffff", 16))
        self.btn_del_selected.setStyleSheet("background-color: #be123c; color: white; padding: 6px 14px;")
        self.btn_del_selected.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_del_selected)

        self.btn_clear_all = QPushButton("一键清空全部残留分片")
        self.btn_clear_all.setIcon(get_icon("clean", "#ffffff", 16))
        self.btn_clear_all.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; padding: 6px 16px;")
        self.btn_clear_all.clicked.connect(self._clear_all)
        btn_row.addWidget(self.btn_clear_all)

        btn_row.addStretch()

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def refresh_list(self):
        self.lbl_path.setText(get_temp_segments_dir())
        folders = get_fragment_folders()
        self.table.setRowCount(len(folders))

        total_bytes = sum(f["size"] for f in folders)
        total_ts = sum(f["ts_count"] for f in folders)

        self.lbl_stats.setText(f"当前共找到 {len(folders)} 个分片文件夹 | 切片文件: {total_ts} 个 | 占用空间: {format_size(total_bytes)}")

        for row, f in enumerate(folders):
            item_name = QTableWidgetItem(f["name"])
            item_name.setData(Qt.UserRole, f["path"])
            item_name.setToolTip(f["path"])

            item_cnt = QTableWidgetItem(f"{f['ts_count']} 个")
            item_cnt.setTextAlignment(Qt.AlignCenter)

            item_sz = QTableWidgetItem(format_size(f["size"]))
            item_sz.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            item_time = QTableWidgetItem(f["mod_time"])
            item_time.setTextAlignment(Qt.AlignCenter)

            state_str = "根目录遗留 (待清理)" if f.get("is_orphan") else "分片目录"
            item_state = QTableWidgetItem(state_str)
            item_state.setTextAlignment(Qt.AlignCenter)
            if f.get("is_orphan"):
                item_state.setForeground(Qt.red)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_cnt)
            self.table.setItem(row, 2, item_sz)
            self.table.setItem(row, 3, item_time)
            self.table.setItem(row, 4, item_state)

    def _open_in_explorer(self):
        d = get_temp_segments_dir()
        try:
            if os.name == "nt":
                os.startfile(d)
            else:
                subprocess.Popen(["xdg-open", d])
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件夹: {e}")

    def _delete_selected(self):
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "提示", "请先在列表中选中要删除的分片文件夹！")
            return

        if QMessageBox.question(
            self,
            "确认删除",
            f"确定要彻底删除选中的 {len(selected_rows)} 个分片文件夹吗？此操作无法撤销。",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        deleted_count = 0
        for r in selected_rows:
            item = self.table.item(r, 0)
            if item:
                path = item.data(Qt.UserRole)
                if path and delete_fragment_folder(path):
                    deleted_count += 1

        self.refresh_list()
        QMessageBox.information(self, "清理完成", f"已成功删除 {deleted_count} 个分片文件夹。")

    def _clear_all(self):
        folders = get_fragment_folders()
        if not folders:
            QMessageBox.information(self, "提示", "当前分片目录干净，无任何残留分片。")
            return

        if QMessageBox.question(
            self,
            "确认清空",
            f"确定要一键清空全部 {len(folders)} 个残留分片文件夹吗？\n所有未完成的临时 TS/M4S 切片将被永久删除。",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        res = clean_all_fragment_folders()
        self.refresh_list()
        QMessageBox.information(self, "清空完成", f"已清空 {res['deleted_count']} 个分片文件夹，共释放空间: {format_size(res['freed_bytes'])}")
