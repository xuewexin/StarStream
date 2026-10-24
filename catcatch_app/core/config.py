"""
CatCatch Downloader - Configuration & Multi-Proxy Manager
支持无代理、跟随系统代理、以及多节点自定义代理池切换
"""
import os
import json
import sys
import uuid
import re
import urllib.request

if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(os.path.abspath(sys.executable))
    _MEI = getattr(sys, '_MEIPASS', '')
    if _MEI and os.path.exists(os.path.join(_MEI, "catcatch_app", "resources")):
        APP_DIR = os.path.join(_MEI, "catcatch_app")
    else:
        APP_DIR = os.path.join(ROOT_DIR, "catcatch_app")
    CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")
    TASKS_FILE = os.path.join(ROOT_DIR, "tasks.json")
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = os.path.dirname(SCRIPT_DIR)
    ROOT_DIR = os.path.dirname(APP_DIR)
    CONFIG_FILE = os.path.join(APP_DIR, "config.json")
    TASKS_FILE = os.path.join(APP_DIR, "tasks.json")

DEFAULT_PROXIES = [
    {"id": "clash", "name": "Clash / Clash Verge (7890)", "url": "http://127.0.0.1:7890"},
    {"id": "v2ray", "name": "v2rayN / Xray SOCKS5 (10808)", "url": "socks5://127.0.0.1:10808"},
    {"id": "v2ray_http", "name": "v2rayN HTTP (10809)", "url": "http://127.0.0.1:10809"}
]

DEFAULT_CONFIG = {
    # 路径配置 (默认均由运行时动态探测，不硬编码任何盘符路径)
    "save_dir": os.path.join(ROOT_DIR, "Downloads"),
    "ffmpeg_path": "",
    "re_cli_path": "",
    "v3_cli_path": "",
    "extension_dir": "",            # 浏览器扩展目录 (动态自适应或用户自定义)
    
    # 网络与服务配置
    "server_host": "127.0.0.1",
    "server_port": 18910,
    
    # 代理体系: "none" (直连/不使用代理), "system" (跟随系统代理), "manual" (手动选择代理)
    "proxy_mode": "none",
    "active_proxy_id": "clash",
    "proxies": DEFAULT_PROXIES,
    
    # 下载与格式核心设置
    "max_concurrent_tasks": 3,
    "max_threads_per_task": 16,
    "del_tmp_files": True,
    "auto_merge": True,
    "auto_convert_mp4": True,       # 自动转封装为标准 MP4 格式
    "attach_metadata": True,        # 下载的文件名自动标注 分辨率 与 时长 规格
    "stream_engine": "RE",          # "RE" or "V3" or "INTERNAL"
    
    # 界面设置
    "theme": "dark",
    "close_to_tray": True,
    "notify_on_complete": True,
    "auto_start_tasks": True,
}


# N_m3u8DL-RE 官方开源发布地址与镜像
NM3U8DL_RE_DOWNLOAD_URL = "https://github.com/nilaoda/N_m3u8DL-RE/releases"
NM3U8DL_RE_LATEST_RELEASE = "https://github.com/nilaoda/N_m3u8DL-RE/releases/latest"
NM3U8DL_RE_MIRROR_URL = "https://ghproxy.net/https://github.com/nilaoda/N_m3u8DL-RE/releases"


def find_executable(name, search_dirs=None):
    """
    全盘与常用目录智能探测可执行文件 (如 ffmpeg.exe)
    支持大小写不敏感匹配以及多候选路径遍历 (优先识别 PyInstaller 内置打包的核心)
    """
    if search_dirs is None:
        search_dirs = [
            ROOT_DIR,
            APP_DIR,
            os.getcwd(),
            os.path.join(ROOT_DIR, "bin"),
            os.path.join(ROOT_DIR, "tools"),
            os.path.join(ROOT_DIR, "ffmpeg"),
            os.path.dirname(ROOT_DIR),
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.path.join(os.path.expanduser("~"), "Desktop"),
        ]
        _MEI = getattr(sys, '_MEIPASS', '')
        if _MEI:
            search_dirs.insert(0, _MEI)
            search_dirs.insert(1, os.path.join(_MEI, "bin"))

        for p in os.environ.get("PATH", "").split(os.pathsep):
            if p and p not in search_dirs:
                search_dirs.append(p)
    
    target_lower = name.lower()
    for d in search_dirs:
        if not d:
            continue
        if isinstance(d, list):
            candidates_dirs = d
        else:
            candidates_dirs = [d]

        for sub_d in candidates_dirs:
            if not sub_d or not os.path.isdir(sub_d):
                continue
            try:
                # 1. 尝试直接精确匹配
                cand = os.path.join(sub_d, name)
                if os.path.isfile(cand):
                    return os.path.abspath(cand)
                # 2. 尝试不区分大小写遍历
                for fn in os.listdir(sub_d):
                    if fn.lower() == target_lower:
                        cand_found = os.path.join(sub_d, fn)
                        if os.path.isfile(cand_found):
                            return os.path.abspath(cand_found)
            except Exception:
                continue
    return ""


def find_nm3u8dl(prefer="RE"):
    """
    智能自动探测电脑上的 N_m3u8DL-RE 或 N_m3u8DL-CLI 执行程序。
    支持在 PyInstaller 打包环境、项目根目录、子目录、用户下载目录及 PATH 中动态搜寻。
    返回: (exe_path, engine_type) 如 ("E:/.../N_m3u8DL-RE.exe", "RE")；未找到返回 ("", "")
    """
    search_dirs = [
        ROOT_DIR,
        APP_DIR,
        os.getcwd(),
        os.path.join(ROOT_DIR, "bin"),
        os.path.join(ROOT_DIR, "tools"),
        os.path.join(ROOT_DIR, "engine"),
        os.path.join(ROOT_DIR, "engines"),
        os.path.join(ROOT_DIR, "cli"),
        os.path.dirname(ROOT_DIR),
        os.path.join(os.path.expanduser("~"), "Downloads"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
    ]
    _MEI = getattr(sys, '_MEIPASS', '')
    if _MEI:
        search_dirs.insert(0, _MEI)
        search_dirs.insert(1, os.path.join(_MEI, "bin"))
        search_dirs.insert(2, os.path.join(_MEI, "engine"))

    for p in os.environ.get("PATH", "").split(os.pathsep):
        if p and p not in search_dirs:
            search_dirs.append(p)

    re_candidates = []
    v3_candidates = []

    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        try:
            for f in os.listdir(d):
                fl = f.lower()
                if not fl.endswith(".exe"):
                    continue
                full_p = os.path.abspath(os.path.join(d, f))
                if not os.path.isfile(full_p):
                    continue
                if "n_m3u8dl-re" in fl or "n-m3u8dl-re" in fl or ("m3u8dl" in fl and "re" in fl):
                    if full_p not in re_candidates:
                        re_candidates.append(full_p)
                elif "n_m3u8dl-cli" in fl or "m3u8dl" in fl:
                    if full_p not in v3_candidates:
                        v3_candidates.append(full_p)
        except Exception:
            continue

    if prefer == "RE":
        if re_candidates:
            return re_candidates[0], "RE"
        if v3_candidates:
            return v3_candidates[0], "V3"
    else:
        if v3_candidates:
            return v3_candidates[0], "V3"
        if re_candidates:
            return re_candidates[0], "RE"

    return "", ""


def get_nm3u8dl_status():
    """获取当前 N_m3u8DL 下载核心的就绪状态与官方更新/下载地址"""
    re_path = config.get("re_cli_path", "")
    v3_path = config.get("v3_cli_path", "")
    
    re_exists = bool(re_path and os.path.exists(re_path))
    v3_exists = bool(v3_path and os.path.exists(v3_path))
    
    # 若缓存记录失效，实时动态重扫
    if not re_exists:
        found_re, _ = find_nm3u8dl(prefer="RE")
        if found_re:
            config.set("re_cli_path", found_re)
            re_path = found_re
            re_exists = True

    if not v3_exists:
        found_v3, _ = find_nm3u8dl(prefer="V3")
        if found_v3:
            config.set("v3_cli_path", found_v3)
            v3_path = found_v3
            v3_exists = True

    found = re_exists or v3_exists
    active_path = re_path if re_exists else (v3_path if v3_exists else "")
    engine = "RE" if re_exists else ("V3" if v3_exists else "")

    return {
        "found": found,
        "re_path": re_path if re_exists else "",
        "v3_path": v3_path if v3_exists else "",
        "active_path": active_path,
        "engine": engine,
        "download_url": NM3U8DL_RE_DOWNLOAD_URL,
        "latest_url": NM3U8DL_RE_LATEST_RELEASE,
        "mirror_url": NM3U8DL_RE_MIRROR_URL
    }


def normalize_proxy_url(url: str) -> str:
    """标准化代理 URL，若无协议前缀则补全 http://"""
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        return f"http://{url}"
    return url


def detect_system_proxy():
    """获取 Windows 当前系统代理"""
    try:
        proxies = urllib.request.getproxies()
        if "http" in proxies:
            return normalize_proxy_url(proxies["http"])
        if "https" in proxies:
            return normalize_proxy_url(proxies["https"])
        if "all" in proxies:
            return normalize_proxy_url(proxies["all"])
    except Exception:
        pass
    return ""


def clean_filename(name):
    """过滤 Windows 文件名非法字符"""
    if not name:
        return "video"
    return re.sub(r'[\\/*?:"<>|]', '_', str(name)).strip()


def format_resolution(res):
    """格式化分辨率标识 (如 1280x720 -> 720P, 1920x1080 -> 1080P)"""
    if not res:
        return ""
    r = str(res).lower()
    if "1080" in r:
        return "1080P"
    elif "720" in r:
        return "720P"
    elif "2160" in r or "4k" in r:
        return "4K"
    elif "480" in r:
        return "480P"
    elif "360" in r:
        return "360P"
    return str(res).upper()


def format_duration(dur):
    """格式化时长标识 (如 5120 秒 -> 01h25m20s)"""
    if not dur:
        return ""
    try:
        sec = int(float(dur))
        if sec <= 0:
            return ""
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        if h > 0:
            return f"{h:02d}h{m:02d}m{s:02d}s"
        return f"{m:02d}m{s:02d}s"
    except Exception:
        return str(dur)


def build_save_name(title, resolution="", duration=""):
    """根据视频名称、分辨率、时长智能生成规整的保存文件名"""
    base_title = clean_filename(title)
    if not config.get("attach_metadata", True):
        return base_title

    parts = [base_title]
    res_tag = format_resolution(resolution)
    dur_tag = format_duration(duration)

    if res_tag and f"[{res_tag}]" not in base_title:
        parts.append(f"[{res_tag}]")
    if dur_tag and f"[{dur_tag}]" not in base_title:
        parts.append(f"[{dur_tag}]")

    return " ".join(parts)


class Config:
    def __init__(self):
        self._config = dict(DEFAULT_CONFIG)
        self.load()
        self._auto_detect_tools()

    def _auto_detect_tools(self):
        # 1. FFmpeg 自动探测
        if not self._config.get("ffmpeg_path") or not os.path.exists(self._config.get("ffmpeg_path")):
            self._config["ffmpeg_path"] = find_executable("ffmpeg.exe")
        
        # 2. N_m3u8DL-RE 动态寻找
        if not self._config.get("re_cli_path") or not os.path.exists(self._config.get("re_cli_path")):
            found_re, _ = find_nm3u8dl(prefer="RE")
            if found_re:
                self._config["re_cli_path"] = found_re
            
        # 3. N_m3u8DL-CLI v3 动态寻找
        if not self._config.get("v3_cli_path") or not os.path.exists(self._config.get("v3_cli_path")):
            found_v3, _ = find_nm3u8dl(prefer="V3")
            if found_v3:
                self._config["v3_cli_path"] = found_v3

        # 4. 下载目录校验与自动初始化
        save_dir = self._config.get("save_dir")
        if not save_dir or not os.path.exists(os.path.abspath(save_dir)):
            self._config["save_dir"] = os.path.join(ROOT_DIR, "Downloads")
        try:
            os.makedirs(self._config["save_dir"], exist_ok=True)
        except Exception:
            pass

    def rescan_tools(self):
        """强制重新全盘探测 FFmpeg 与 N_m3u8DL 引擎并更新配置"""
        self._config["ffmpeg_path"] = find_executable("ffmpeg.exe")
        found_re, _ = find_nm3u8dl(prefer="RE")
        self._config["re_cli_path"] = found_re
        found_v3, _ = find_nm3u8dl(prefer="V3")
        self._config["v3_cli_path"] = found_v3
        self.save()
        return get_nm3u8dl_status()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # 关键防御：校验保存的绝对路径。如果因移动文件夹、换电脑或临时解压目录导致路径失效，
                    # 立即丢弃无效配置，由动态探测算法按当前环境自动重新搜寻，坚决避免使用硬编码死路径。
                    for path_key in ["ffmpeg_path", "re_cli_path", "v3_cli_path", "extension_dir"]:
                        if path_key in saved and saved[path_key]:
                            val = str(saved[path_key])
                            if "_MEI" in val or "AppData\\Local\\Temp" in val or not os.path.exists(val):
                                del saved[path_key]
                    if "save_dir" in saved and saved["save_dir"]:
                        if not os.path.exists(saved["save_dir"]):
                            saved["save_dir"] = os.path.join(ROOT_DIR, "Downloads")
                    self._config.update(saved)
            except Exception as e:
                print(f"[Config] 加载配置文件失败: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            dump_data = dict(self._config)
            # 任何 PyInstaller 打包环境产生的临时解压路径 (_MEI) 绝不写入持久化配置文件
            for path_key in ["ffmpeg_path", "re_cli_path", "v3_cli_path"]:
                val = str(dump_data.get(path_key, ""))
                if "_MEI" in val or "AppData\\Local\\Temp" in val:
                    dump_data[path_key] = ""
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] 保存配置文件失败: {e}")

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def update(self, d):
        self._config.update(d)
        self.save()

    @property
    def all(self):
        return dict(self._config)

    # 代理控制辅助方法
    def get_effective_proxy(self):
        """解析并返回当前生效的有效代理 URL，返回空字符串表示直连"""
        mode = self._config.get("proxy_mode", "none")
        if mode == "none":
            return ""
        elif mode == "system":
            return detect_system_proxy()
        elif mode == "manual":
            active_id = self._config.get("active_proxy_id")
            for p in self._config.get("proxies", []):
                if p.get("id") == active_id:
                    return normalize_proxy_url(p.get("url", ""))
        return ""

    def get_proxies_list(self):
        return self._config.get("proxies", [])

    def add_proxy(self, name, url):
        pid = str(uuid.uuid4())[:6]
        proxies = self._config.get("proxies", [])
        proxies.append({"id": pid, "name": name, "url": normalize_proxy_url(url)})
        self._config["proxies"] = proxies
        self.save()
        return pid

    def update_proxy(self, pid, name, url):
        proxies = self._config.get("proxies", [])
        for p in proxies:
            if p.get("id") == pid:
                p["name"] = name
                p["url"] = normalize_proxy_url(url)
                break
        self._config["proxies"] = proxies
        self.save()

    def delete_proxy(self, pid):
        proxies = [p for p in self._config.get("proxies", []) if p.get("id") != pid]
        self._config["proxies"] = proxies
        if self._config.get("active_proxy_id") == pid and proxies:
            self._config["active_proxy_id"] = proxies[0]["id"]
        self.save()


config = Config()
