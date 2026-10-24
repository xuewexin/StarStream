"""
StarStream Pro - Application Main Entrypoint (星流媒体下载器)
"""
import sys
import os
import ctypes

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(APP_DIR)

for p in [ROOT_DIR, APP_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from catcatch_app.core.config import config
from catcatch_app.core.server import local_server
from catcatch_app.core.task_manager import task_manager
from catcatch_app.ui.main_window import MainWindow
from catcatch_app.ui.icons import get_app_icon


def main():
    # 注册 Windows 专属应用 ID，确保任务栏精准显示官方星流 Logo
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("StarStream.Pro.Downloader.2.0")
        except Exception:
            pass

    # 启用高 DPI 缩放支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("星流媒体下载器 (StarStream Pro)")
    app.setOrganizationName("StarStream")
    app.setWindowIcon(get_app_icon())

    # 启动本地与插件通信服务端 (127.0.0.1:18910)
    local_server.start()

    # 创建并展示主窗口
    window = MainWindow()
    window.show()

    # 退出钩子
    exit_code = app.exec_()
    
    # 清理并持久化数据
    local_server.stop()
    task_manager.save_tasks()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
