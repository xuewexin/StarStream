"""
StarStream Downloader - Browser Helper
浏览器快速跳转与动态扩展路径智能探测工具
"""
import os
import subprocess
import winreg
import urllib.parse
import webbrowser

from catcatch_app.core.config import config, ROOT_DIR, APP_DIR


def is_valid_extension_dir(path):
    """验证目标目录是否包含有效的扩展 manifest.json"""
    if not path or not os.path.isdir(path):
        return False
    manifest_p = os.path.join(path, "manifest.json")
    if os.path.isfile(manifest_p):
        try:
            with open(manifest_p, "r", encoding="utf-8") as f:
                content = f.read(1024)
                if "manifest_version" in content:
                    return True
        except Exception:
            return True
    return False


def find_extension_dir(custom_path=None):
    """
    全盘与关联目录动态搜寻星流嗅探器扩展源码目录：
    1. 传入的自定义指定路径
    2. config.json 记忆的路径 (若仍有效)
    3. 项目根目录、APP 目录、当前工作目录、上级目录
    4. 根目录及相邻目录 1 层深度遍历探测 manifest.json
    5. 用户 Downloads / Desktop 目录
    """
    if custom_path and is_valid_extension_dir(custom_path):
        return os.path.abspath(custom_path)

    saved_p = config.get("extension_dir", "")
    if saved_p and is_valid_extension_dir(saved_p):
        return os.path.abspath(saved_p)

    # 常见标准候选相对路径 (由运行时动态计算，杜绝写死)
    candidates = [
        os.path.join(ROOT_DIR, "m3u8-sniffer-extension"),
        os.path.join(APP_DIR, "m3u8-sniffer-extension"),
        os.path.join(os.getcwd(), "m3u8-sniffer-extension"),
        os.getcwd(),
        os.path.join(os.path.dirname(ROOT_DIR), "m3u8-sniffer-extension"),
    ]
    for c in candidates:
        if is_valid_extension_dir(c):
            return os.path.abspath(c)

    # 动态扫描 ROOT_DIR 与 上级目录下的子文件夹
    scan_roots = [ROOT_DIR, os.path.dirname(ROOT_DIR)]
    for sr in scan_roots:
        if not sr or not os.path.isdir(sr):
            continue
        try:
            for item in os.listdir(sr):
                sub = os.path.join(sr, item)
                if os.path.isdir(sub) and is_valid_extension_dir(sub):
                    mf = os.path.join(sub, "manifest.json")
                    try:
                        with open(mf, "r", encoding="utf-8") as f:
                            text = f.read().lower()
                            if "sniffer" in text or "m3u8" in text or "星流" in text or "catcatch" in text:
                                return os.path.abspath(sub)
                    except Exception:
                        pass
        except Exception:
            continue

    # 扫描用户下载与桌面
    for user_dir in [os.path.join(os.path.expanduser("~"), "Downloads"), os.path.join(os.path.expanduser("~"), "Desktop")]:
        cand = os.path.join(user_dir, "m3u8-sniffer-extension")
        if is_valid_extension_dir(cand):
            return os.path.abspath(cand)

    # 默认兜底路径
    fallback = os.path.join(ROOT_DIR, "m3u8-sniffer-extension")
    return os.path.abspath(fallback)


def get_extension_dir():
    """获取扩展程序的物理目录 (完全动态定位)"""
    return find_extension_dir()


def set_custom_extension_dir(path):
    """保存用户自选的扩展目录"""
    if is_valid_extension_dir(path):
        p = os.path.abspath(path)
        config.set("extension_dir", p)
        return True, p
    return False, "该目录不存在或未包含 manifest.json"


def copy_to_clipboard(text):
    """复制文本到 Windows 剪贴板"""
    try:
        from PyQt5.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)
            return True
    except Exception:
        pass
    try:
        p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
        p.communicate(input=text.encode("utf-16"))
        return True
    except Exception:
        pass
    return False


def find_browser_exe(reg_key, common_paths):
    """查找浏览器安装路径"""
    for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        try:
            with winreg.OpenKey(root, reg_key) as k:
                val, _ = winreg.QueryValueEx(k, "")
                candidate = val.strip().strip('"')
                if os.path.exists(candidate):
                    return candidate
        except Exception:
            pass

    for p in common_paths:
        if os.path.exists(p):
            return p
    return ""


def get_guide_html_path():
    """获取本地 HTML 安装指引页面路径 (兼顾常规与 PyInstaller 打包运行)"""
    cand1 = os.path.abspath(os.path.join(APP_DIR, "resources", "extension_guide.html"))
    if os.path.exists(cand1):
        return cand1
    import sys
    _mei = getattr(sys, '_MEIPASS', '')
    if _mei:
        cand2 = os.path.abspath(os.path.join(_mei, "catcatch_app", "resources", "extension_guide.html"))
        if os.path.exists(cand2):
            return cand2
    return cand1


def open_browser_guide(browser_type="edge"):
    """
    唤起浏览器并打开扩展安装指南页面，同时自动复制对应的扩展页地址到剪贴板。
    巧妙解决 Chromium 禁止外部程序直接跳转 chrome:// 或 edge:// 内部页面的安全限制。
    """
    target_url = "edge://extensions" if browser_type == "edge" else "chrome://extensions"
    copy_to_clipboard(target_url)

    ext_p = get_extension_dir()
    guide_path = get_guide_html_path()
    
    # 构造携带参数的本地文件 URL
    param_ext = urllib.parse.quote(ext_p)
    file_url = f"file:///{guide_path.replace(os.sep, '/')}?browser={browser_type}&ext={param_ext}"

    if browser_type == "edge":
        exe = find_browser_exe(
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
            [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
            ]
        )
    else:
        exe = find_browser_exe(
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
            ]
        )

    # 优先启动目标浏览器打开指南页
    try:
        if exe and os.path.exists(exe):
            subprocess.Popen([exe, file_url])
            return True, f"已在 {browser_type.title()} 中打开安装指引，并自动复制了【{target_url}】到剪贴板！"
    except Exception:
        pass

    # 兜底使用 Windows 系统默认浏览器
    try:
        webbrowser.open(file_url)
        return True, f"已为您打开安装指引，并自动复制了【{target_url}】到剪贴板！"
    except Exception as e:
        return False, str(e)


def open_edge_extensions():
    """兼容旧接口：打开 Edge 安装指引"""
    return open_browser_guide("edge")


def open_chrome_extensions():
    """兼容旧接口：打开 Chrome 安装指引"""
    return open_browser_guide("chrome")


def open_extension_folder(custom_path=None):
    """在 Windows 资源管理器中打开并高亮扩展所在目录"""
    ext_p = find_extension_dir(custom_path)
    if os.path.exists(ext_p):
        try:
            os.startfile(ext_p)
            return True, "已在资源管理器中打开扩展文件夹"
        except Exception as e:
            return False, str(e)
    return False, "未找到扩展文件夹"
