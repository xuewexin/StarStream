"""
CatCatch Downloader - Software Update Check & Hot Overwrite Dialog
检测 GitHub Releases 最新版本，提示更新日志，支持暂不更新与一键覆盖式热更新
"""
import os
import sys
import json
import time
import urllib.request
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from catcatch_app.core.config import config, ROOT_DIR, APP_VERSION
from catcatch_app.ui.icons import get_icon, get_app_icon
from catcatch_app.core.download_file import format_size


def compare_versions(v1: str, v2: str) -> int:
    """比较语义化版本号，例如 v3.1.2 与 v3.1.1。v1 > v2 返回 1, v1 == v2 返回 0, v1 < v2 返回 -1"""
    clean_v1 = [int(x) for x in re.findall(r'\d+', v1)]
    clean_v2 = [int(x) for x in re.findall(r'\d+', v2)]
    max_len = max(len(clean_v1), len(clean_v2))
    clean_v1.extend([0] * (max_len - len(clean_v1)))
    clean_v2.extend([0] * (max_len - len(clean_v2)))
    for a, b in zip(clean_v1, clean_v2):
        if a > b:
            return 1
        elif a < b:
            return -1
    return 0


import re


class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str, str, str)  # tag, title, body, download_url
    check_finished = pyqtSignal(bool, str)

    def run(self):
        url = "https://api.github.com/repos/xuewexin/StarStream/releases/latest"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "StarStream-App", "Accept": "application/vnd.github.v3+json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    tag = data.get("tag_name", "").strip()
                    title = data.get("name") or tag
                    body = data.get("body", "")

                    download_url = ""
                    for asset in data.get("assets", []):
                        aname = asset.get("name", "").lower()
                        if aname.endswith(".zip") and "portable" in aname:
                            download_url = asset.get("browser_download_url", "")
                            break
                    if not download_url:
                        for asset in data.get("assets", []):
                            if asset.get("name", "").lower().endswith(".zip"):
                                download_url = asset.get("browser_download_url", "")
                                break

                    # 检查是否有更新
                    if tag and compare_versions(tag, APP_VERSION) > 0:
                        self.update_available.emit(tag, title, body, download_url)
                        self.check_finished.emit(True, f"检测到新版本: {tag}")
                    else:
                        self.check_finished.emit(False, f"当前已是最新版本 ({APP_VERSION})")
        except Exception as e:
            self.check_finished.emit(False, str(e))


class DownloadUpdateThread(QThread):
    progress = pyqtSignal(int, str)  # percent, status_str
    finished = pyqtSignal(bool, str)  # success, file_path_or_msg

    def __init__(self, download_url, dest_path):
        super().__init__()
        self.download_url = download_url
        self.dest_path = dest_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "StarStream-App"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                last_time = time.time()
                last_downloaded = 0

                with open(self.dest_path, "wb") as f:
                    while True:
                        if self._is_cancelled:
                            return
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if now - last_time >= 0.3:
                            speed = (downloaded - last_downloaded) / (now - last_time)
                            last_time = now
                            last_downloaded = downloaded

                            pct = int((downloaded / total_size) * 100) if total_size > 0 else 50
                            status_str = f"{format_size(downloaded)} / {format_size(total_size)} ({format_size(speed)}/s)"
                            self.progress.emit(pct, status_str)

            self.progress.emit(100, f"下载完成 ({format_size(downloaded)})")
            self.finished.emit(True, self.dest_path)
        except Exception as e:
            self.finished.emit(False, str(e))


class UpdateDialog(QDialog):
    def __init__(self, latest_tag, title, body, download_url, parent=None):
        super().__init__(parent)
        self.latest_tag = latest_tag
        self.release_title = title
        self.release_body = body
        self.download_url = download_url
        self.download_thread = None

        self.setWindowTitle("软件版本更新 - 星流下载器")
        self.setWindowIcon(get_app_icon())
        self.resize(540, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 头部
        header = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("download", "#38bdf8", 32).pixmap(32, 32))
        header.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        v_title = QLabel(f"发现新版本: {self.latest_tag}")
        v_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        v_title.setStyleSheet("color: #38bdf8;")

        sub_title = QLabel(f"当前版本: {APP_VERSION}  |  推荐升级以获得最新功能与修复")
        sub_title.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_box.addWidget(v_title)
        title_box.addWidget(sub_title)
        header.addLayout(title_box, 1)

        layout.addLayout(header)

        # 更新日志卡片
        log_lbl = QLabel("更新内容说明:")
        log_lbl.setStyleSheet("color: #e2e8f0; font-weight: 600; font-size: 12px;")
        layout.addWidget(log_lbl)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlainText(self.release_body or "暂无详细更新日志。包含性能优化与常规错误修复。")
        self.log_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.log_edit, 1)

        # 进度条区 (初始隐藏)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #0f172a;
                text-align: center;
                color: #ffffff;
                height: 18px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3875f6, stop:1 #6366f1);
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_download_status = QLabel("")
        self.lbl_download_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_download_status.setVisible(False)
        layout.addWidget(self.lbl_download_status)

        # 底部操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_skip = QPushButton("暂不更新")
        self.btn_skip.setIcon(get_icon("close", "#94a3b8", 14))
        self.btn_skip.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
            }
        """)
        self.btn_skip.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_skip)

        self.btn_update = QPushButton("覆盖式一键更新")
        self.btn_update.setIcon(get_icon("download", "#ffffff", 16))
        self.btn_update.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 22px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1);
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
        """)
        self.btn_update.clicked.connect(self._start_update)
        btn_layout.addWidget(self.btn_update)

        layout.addLayout(btn_layout)

    def _start_update(self):
        if not self.download_url:
            QMessageBox.information(
                self,
                "提示",
                f"当前新版本 ({self.latest_tag}) 尚未上传便携包安装文件，请稍后重试或前往 GitHub Releases 页面查看。"
            )
            return

        self.btn_update.setEnabled(False)
        self.btn_update.setText("正在下载更新...")
        self.btn_skip.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_download_status.setVisible(True)
        self.lbl_download_status.setText("正在建立高速下载通道...")

        dest_zip = os.path.join(ROOT_DIR, "StarStream_Update.zip")
        self.download_thread = DownloadUpdateThread(self.download_url, dest_zip)
        self.download_thread.progress.connect(self._on_download_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.start()

    def _on_download_progress(self, percent, status_str):
        self.progress_bar.setValue(percent)
        self.lbl_download_status.setText(status_str)

    def _on_download_finished(self, success, result):
        if not success:
            QMessageBox.critical(self, "更新下载失败", f"下载新版本安装包失败:\n{result}\n\n请检查网络连接后重试。")
            self.btn_update.setEnabled(True)
            self.btn_update.setText("重试覆盖式更新")
            self.btn_skip.setEnabled(True)
            return

        self.lbl_download_status.setText("更新包下载完成，正在准备执行覆盖式热替换...")

        # 生成 Windows 自动覆盖与重启批处理脚本
        bat_path = os.path.join(ROOT_DIR, "update_and_restart.bat")
        zip_path = result
        try:
            with open(bat_path, "w", encoding="ansi", errors="ignore") as f:
                f.write("@echo off\r\n")
                f.write("chcp 65001 >nul\r\n")
                f.write("echo ========================================\r\n")
                f.write("echo 正在执行星流媒体下载器覆盖式热更新...\r\n")
                f.write("echo ========================================\r\n")
                f.write("timeout /t 2 /nobreak >nul\r\n")
                f.write(f'tar -xf "{zip_path}" -C "{ROOT_DIR}"\r\n')
                f.write(f'if exist "{zip_path}" del /f /q "{zip_path}"\r\n')
                f.write("echo 更新解压完成，正在启动新版本星流客户端...\r\n")
                f.write(f'start "" "{os.path.join(ROOT_DIR, "StarStream.exe")}"\r\n')
                f.write('del "%~f0"\r\n')
                f.write("exit\r\n")

            # 启动批处理并退出当前客户端
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen(["cmd.exe", "/c", bat_path], cwd=ROOT_DIR, creationflags=creationflags)
            QApplication.instance().quit()
        except Exception as e:
            QMessageBox.warning(self, "启动更新脚本失败", f"无法启动覆盖脚本: {e}\n\n已下载更新包位于:\n{zip_path}")
            self.btn_update.setEnabled(True)
            self.btn_skip.setEnabled(True)
