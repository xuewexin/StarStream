import os
import sys
import ctypes
from datetime import datetime

# 1. 确保在 PyInstaller 打包 (console=False) 下 stdout / stderr 安全，防止 print 抛出 NoneType.write 异常
class SafeStream:
    def write(self, s):
        pass
    def flush(self):
        pass

if sys.stdout is None:
    sys.stdout = SafeStream()
if sys.stderr is None:
    sys.stderr = SafeStream()

# 2. 定位程序运行工作目录
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 3. 确保 PyInstaller 解压环境下的 Qt5 平台插件路径被正确识别，防止出现平台插件缺失与 qFatal 闪退
if getattr(sys, 'frozen', False):
    mei_pass = getattr(sys, '_MEIPASS', '')
    if mei_pass:
        qt_plugins_dir = os.path.join(mei_pass, 'PyQt5', 'Qt5', 'plugins')
        if os.path.exists(qt_plugins_dir):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(qt_plugins_dir, 'platforms')
            try:
                from PyQt5.QtCore import QCoreApplication
                QCoreApplication.addLibraryPath(qt_plugins_dir)
            except Exception:
                pass

# 4. 全局未捕获异常守护与日志持久化
def global_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    import traceback
    err_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        log_dir = os.path.join(BASE_DIR, "Logs")
        os.makedirs(log_dir, exist_ok=True)
        crash_log = os.path.join(log_dir, "startup_crash.log")
        with open(crash_log, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 崩溃异常:\n{err_text}\n")
    except Exception:
        pass

    if os.name == 'nt':
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"星流媒体下载器启动出现异常:\n\n{exc_type.__name__}: {exc_value}\n\n已记录详细堆栈至 Logs/startup_crash.log",
                "星流媒体下载器 - 启动异常",
                0x10 | 0x10000  # MB_ICONERROR | MB_SETFOREGROUND
            )
        except Exception:
            pass

sys.excepthook = global_excepthook

# 5. Windows 单实例互斥体 (防止重复运行、端口冲突与多实例僵尸挂起)
_single_instance_mutex = None

def check_single_instance():
    global _single_instance_mutex
    if os.name != 'nt':
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        mutex_name = "Global\\StarStream_SingleInstance_Mutex_v2"
        _single_instance_mutex = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()
        ERROR_ALREADY_EXISTS = 183

        if last_error == ERROR_ALREADY_EXISTS:
            # 已有运行中的实例，尝试唤醒并置顶其窗口
            user32 = ctypes.windll.user32
            found_hwnds = []

            def enum_proc(hwnd, lparam):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if "星流" in buff.value or "StarStream" in buff.value:
                        found_hwnds.append(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

            if found_hwnds:
                h = found_hwnds[0]
                user32.ShowWindow(h, 9)  # SW_RESTORE
                user32.SetForegroundWindow(h)
            return False
    except Exception:
        pass
    return True


if __name__ == "__main__":
    if not check_single_instance():
        sys.exit(0)

    from catcatch_app.main import main
    main()
