"""
CatCatch Downloader - Task Log & Error Diagnostic Dialog
提供任务全生命周期控制台日志查看、出错原因深度诊断与排查建议
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QPlainTextEdit, QFrame, QApplication, QWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

from .icons import get_icon, get_app_icon
from ..core.logger import get_logs_dir, get_master_error_log_path, diagnose_error


class TaskLogDialog(QDialog):
    def __init__(self, task_data, parent=None):
        super().__init__(parent)
        self.task = dict(task_data)
        self.setWindowTitle(f"任务日志与诊断 - {self.task.get('title', '详细信息')[:30]}")
        self.setWindowIcon(get_app_icon())
        self.resize(800, 580)
        self.setMinimumSize(650, 450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. 顶部任务信息摘要卡片
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)

        # 标题栏与状态指示
        title_row = QHBoxLayout()
        lbl_icon = QLabel()
        status = self.task.get("status", "waiting")
        is_error = status == "error"
        if is_error:
            lbl_icon.setPixmap(get_icon("alert", "#f87171", 20).pixmap(20, 20))
        elif status == "completed":
            lbl_icon.setPixmap(get_icon("check", "#4ade80", 20).pixmap(20, 20))
        else:
            lbl_icon.setPixmap(get_icon("log", "#38bdf8", 20).pixmap(20, 20))
        title_row.addWidget(lbl_icon)

        title_text = self.task.get("title") or "未命名媒体任务"
        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #f4f4f5;")
        title_row.addWidget(lbl_title, 1)

        # 状态胶囊
        status_colors = {
            "completed": ("已完成", "#065f46", "#34d399"),
            "error": ("下载失败", "#7f1d1d", "#f87171"),
            "downloading": ("下载中", "#1e3a8a", "#60a5fa"),
            "waiting": ("等待中", "#78350f", "#fbbf24"),
            "paused": ("已暂停", "#374151", "#9ca3af")
        }
        st_text, bg_col, text_col = status_colors.get(status, (status, "#27272a", "#d4d4d8"))
        lbl_status_badge = QLabel(st_text)
        lbl_status_badge.setStyleSheet(f"""
            background-color: {bg_col};
            color: {text_col};
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 10px;
        """)
        title_row.addWidget(lbl_status_badge)
        info_layout.addLayout(title_row)

        # 详细参数
        url_val = self.task.get("url", "")
        media_t = self.task.get("media_type", "未知").upper()
        res_val = self.task.get("resolution") or "--"
        dur_val = self.task.get("duration") or "--"
        meta_row = QHBoxLayout()
        meta_lbl = QLabel(f"格式: {media_t} | 分辨率: {res_val} | 时长: {dur_val} | 任务ID: {self.task.get('id', '--')}")
        meta_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        meta_row.addWidget(meta_lbl, 1)

        btn_copy_url = QPushButton("复制网址")
        btn_copy_url.setIcon(get_icon("copy", "#a1a1aa", 12))
        btn_copy_url.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #52525b;
                border-radius: 4px;
                color: #d4d4d8;
                font-size: 11px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background: #3f3f46;
                color: #ffffff;
            }
        """)
        btn_copy_url.clicked.connect(self._copy_url)
        meta_row.addWidget(btn_copy_url)
        info_layout.addLayout(meta_row)

        layout.addWidget(info_frame)

        # 2. 智能错误诊断卡片 (仅当存在错误时展示)
        error_msg = self.task.get("error_msg", "")
        error_reason = self.task.get("error_reason", "")
        error_hint = self.task.get("error_hint", "")

        logs = self._get_task_logs()

        # 若此前未持久化诊断结果，进行实时推断
        if is_error and not error_reason:
            error_reason, error_hint = diagnose_error(logs, error_msg, url_val)

        if is_error or error_reason:
            diag_frame = QFrame()
            diag_frame.setStyleSheet("""
                QFrame {
                    background-color: #2a1215;
                    border: 1px solid #7f1d1d;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)
            diag_layout = QVBoxLayout(diag_frame)
            diag_layout.setContentsMargins(12, 10, 12, 10)
            diag_layout.setSpacing(6)

            diag_header = QHBoxLayout()
            lbl_warn_ico = QLabel()
            lbl_warn_ico.setPixmap(get_icon("alert", "#f87171", 16).pixmap(16, 16))
            diag_header.addWidget(lbl_warn_ico)

            lbl_diag_title = QLabel(f"出错原因诊断: {error_reason}")
            lbl_diag_title.setStyleSheet("font-weight: 700; color: #fca5a5; font-size: 13px;")
            diag_header.addWidget(lbl_diag_title, 1)
            diag_layout.addLayout(diag_header)

            if error_hint:
                lbl_hint = QLabel(error_hint)
                lbl_hint.setWordWrap(True)
                lbl_hint.setStyleSheet("color: #e4e4e7; font-size: 12px; line-height: 1.4;")
                diag_layout.addWidget(lbl_hint)

            if error_msg and error_msg != error_reason:
                lbl_raw = QLabel(f"系统原始错误: {error_msg}")
                lbl_raw.setWordWrap(True)
                lbl_raw.setStyleSheet("color: #a1a1aa; font-size: 11px; font-family: Consolas, monospace;")
                diag_layout.addWidget(lbl_raw)

            layout.addWidget(diag_frame)

        # 3. 运行日志区域
        log_header_row = QHBoxLayout()
        lbl_log_title = QLabel("控制台实时运行日志:")
        lbl_log_title.setStyleSheet("font-weight: 600; color: #d4d4d8; font-size: 12px;")
        log_header_row.addWidget(lbl_log_title, 1)

        self.lbl_toast = QLabel("")
        self.lbl_toast.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 600;")
        log_header_row.addWidget(self.lbl_toast)

        layout.addLayout(log_header_row)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #141416;
                color: #22c55e;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 10px;
                selection-background-color: #3f3f46;
                selection-color: #ffffff;
            }
        """)

        # 渲染日志内容
        if logs:
            self.log_text.setPlainText("\n".join(logs))
            self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        else:
            self.log_text.setPlainText("(该任务暂无控制台日志输出记录)")

        layout.addWidget(self.log_text, 1)

        # 4. 底部按钮工具栏
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # 复制全部日志
        btn_copy_log = QPushButton("复制诊断与日志")
        btn_copy_log.setIcon(get_icon("copy", "#f4f4f5", 14))
        btn_copy_log.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                color: #f4f4f5;
                font-size: 12px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        btn_copy_log.clicked.connect(self._copy_all_info)
        btn_row.addWidget(btn_copy_log)

        # 打开全局错误日志文件
        btn_open_err = QPushButton("打开错误汇总日志")
        btn_open_err.setIcon(get_icon("log", "#38bdf8", 14))
        btn_open_err.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                color: #38bdf8;
                font-size: 12px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        btn_open_err.clicked.connect(self._open_master_log)
        btn_row.addWidget(btn_open_err)

        # 打开日志文件夹
        btn_open_folder = QPushButton("打开日志目录")
        btn_open_folder.setIcon(get_icon("folder", "#a1a1aa", 14))
        btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                color: #d4d4d8;
                font-size: 12px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        btn_open_folder.clicked.connect(self._open_logs_dir)
        btn_row.addWidget(btn_open_folder)

        btn_row.addStretch()

        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #3875f6;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 20px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _get_task_logs(self):
        """优先从任务内存/持久化读取日志，若有单任务日志文件也一并读取"""
        logs = self.task.get("logs")
        if isinstance(logs, list) and logs:
            return logs

        # 尝试从 Logs/task_{task_id}.log 读取
        task_id = self.task.get("id")
        if task_id:
            p = os.path.join(get_logs_dir(), f"task_{task_id}.log")
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read().splitlines()
                except Exception:
                    pass

        return []

    def _copy_url(self):
        url = self.task.get("url", "")
        if url:
            QApplication.clipboard().setText(url)
            self._show_toast("下载网址已复制！")

    def _copy_all_info(self):
        """整合诊断报告与控制台日志复制到剪贴板"""
        title = self.task.get("title", "")
        url = self.task.get("url", "")
        task_id = self.task.get("id", "")
        err_reason = self.task.get("error_reason", "")
        err_hint = self.task.get("error_hint", "")
        err_msg = self.task.get("error_msg", "")
        log_content = self.log_text.toPlainText()

        report = [
            f"=== 星流 (StarStream) 任务诊断报告 ===",
            f"任务编号: {task_id}",
            f"任务名称: {title}",
            f"请求地址: {url}",
            f"当前状态: {self.task.get('status', '')}",
        ]
        if err_reason:
            report.append(f"出错诊断: {err_reason}")
        if err_hint:
            report.append(f"排查建议: {err_hint}")
        if err_msg:
            report.append(f"原始错误: {err_msg}")
        report.append("\n--- 控制台日志 ---")
        report.append(log_content)

        QApplication.clipboard().setText("\n".join(report))
        self._show_toast("诊断报告与完整日志已复制到剪贴板！")

    def _open_master_log(self):
        """在系统文本编辑器中打开 download_errors.log"""
        log_p = get_master_error_log_path()
        if not os.path.exists(log_p):
            # 若文件尚未生成，创建一个空模板
            try:
                with open(log_p, "w", encoding="utf-8") as f:
                    f.write("=== 星流 (StarStream) 下载错误日志 ===\n(暂无错误记录)\n")
            except Exception:
                pass
        try:
            os.startfile(log_p)
        except Exception as e:
            self._show_toast(f"打开日志失败: {e}")

    def _open_logs_dir(self):
        """打开 Logs 目录"""
        logs_dir = get_logs_dir()
        try:
            os.startfile(logs_dir)
        except Exception as e:
            self._show_toast(f"打开目录失败: {e}")

    def _show_toast(self, msg):
        self.lbl_toast.setText(msg)
        QTimer.singleShot(2500, lambda: self.lbl_toast.setText(""))
