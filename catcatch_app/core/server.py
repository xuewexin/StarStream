"""
CatCatch Downloader - Embedded HTTP IPC Server
提供本地 RESTful API 服务，与浏览器插件无缝双向互通
默认监听: 127.0.0.1:18910
"""
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from .config import config, detect_local_active_proxies, get_temp_segments_dir
from .task_manager import task_manager
from .ffmpeg_engine import is_ffmpeg_available, get_ffmpeg_path
from .cache_cleaner import get_fragment_folders, clean_all_fragment_folders


class CatCatchHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 屏蔽默认标准输出刷屏，避免干扰
        return

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def _send_json_response(self, code, data):
        self.send_response(code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status" or path == "/":
            ff_ok, ff_msg = is_ffmpeg_available()
            tasks = task_manager.get_all_tasks()
            active_count = sum(1 for t in tasks if t["status"] == "downloading")
            self._send_json_response(200, {
                "status": "ok",
                "app": "StarStream Downloader",
                "version": "2.2.0",
                "ffmpeg_available": ff_ok,
                "ffmpeg_info": ff_msg,
                "ffmpeg_path": get_ffmpeg_path(),
                "save_dir": config.get("save_dir"),
                "temp_segments_dir": get_temp_segments_dir(),
                "effective_proxy": config.get_effective_proxy(),
                "detected_proxies": detect_local_active_proxies(),
                "total_tasks": len(tasks),
                "active_tasks": active_count
            })
            return

        elif path == "/api/fragments":
            frags = get_fragment_folders()
            self._send_json_response(200, {
                "success": True,
                "temp_segments_dir": get_temp_segments_dir(),
                "count": len(frags),
                "folders": frags
            })
            return

        elif path == "/api/tasks":
            tasks = task_manager.get_all_tasks()
            self._send_json_response(200, {
                "success": True,
                "tasks": tasks[:50]
            })
            return

        self._send_json_response(404, {"error": "Not Found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        data = {}
        if body:
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                pass

        if path == "/api/tasks":
            try:
                # 批量或单任务添加
                if isinstance(data, list):
                    added_ids = []
                    for item in data:
                        t_id = self._process_single_task(item)
                        if t_id:
                            added_ids.append(t_id)
                    self._send_json_response(200, {
                        "success": True,
                        "count": len(added_ids),
                        "task_ids": added_ids,
                        "message": f"成功添加 {len(added_ids)} 个下载任务"
                    })
                else:
                    t_id = self._process_single_task(data)
                    self._send_json_response(200, {
                        "success": True,
                        "task_id": t_id,
                        "message": "任务已加入下载队列"
                    })
            except ValueError as ve:
                self._send_json_response(400, {
                    "success": False,
                    "error": str(ve)
                })
            return

        elif path.startswith("/api/tasks/") and path.endswith("/action"):
            # 控制动作
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                task_id = parts[1]
                action = data.get("action", "")
                if action == "start":
                    task_manager.start_task(task_id)
                elif action == "pause":
                    task_manager.pause_task(task_id)
                elif action == "delete":
                    task_manager.remove_task(task_id, delete_file=data.get("delete_file", False))
                self._send_json_response(200, {"success": True, "action": action})
                return

        self._send_json_response(404, {"error": "Not Found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/fragments":
            res = clean_all_fragment_folders()
            self._send_json_response(200, {
                "success": True,
                "freed_bytes": res["freed_bytes"],
                "deleted_count": res["deleted_count"],
                "message": f"已清空 {res['deleted_count']} 个残留分片文件夹"
            })
            return
        self._send_json_response(404, {"error": "Not Found"})

    def _process_single_task(self, item):
        url = (item.get("url") or "").strip()
        if not url:
            return None
        if url.startswith("blob:"):
            raise ValueError("无法下载 blob: 链接（此为浏览器临时内存对象，非网络地址）。请播放视频后在插件列表中选择实际嗅探到的 m3u8 地址！")
        
        # 整理字段以适应 task_manager
        title = item.get("title") or item.get("pageTitle") or item.get("name") or "video"
        media_type = item.get("mediaType") or item.get("type") or ""
        
        headers = item.get("headers", {})
        if "referer" in item and "Referer" not in headers:
            headers["Referer"] = item["referer"]
        if "userAgent" in item and "User-Agent" not in headers:
            headers["User-Agent"] = item["userAgent"]
        if "cookie" in item and "Cookie" not in headers:
            headers["Cookie"] = item["cookie"]

        # 优先级规则：
        # 1. 保存路径：优先使用插件显式传递的 save_dir/saveDir，若未设置则使用 exe 客户端当前配置 config.get("save_dir")
        custom_save_dir = (item.get("saveDir") or item.get("save_dir") or "").strip()
        save_dir = custom_save_dir if custom_save_dir else config.get("save_dir")

        # 2. 并发线程：优先使用插件显式传递的 threadCount/thread_count，若未设置则使用 exe 客户端配置
        custom_threads = item.get("threadCount") or item.get("thread_count")
        try:
            thread_count = int(custom_threads) if custom_threads else int(config.get("max_threads_per_task", 16))
        except (ValueError, TypeError):
            thread_count = int(config.get("max_threads_per_task", 16))

        # 3. 代理配置：
        # - 如果插件指定了 "direct" 或 "none"，表示强制直连；
        # - 如果插件指定了具体代理 (如 http://127.0.0.1:7890 或 socks5://...)，优先使用该代理；
        # - 如果插件未设置 (空或 "default")，则回退使用 exe 客户端当前的全局有效代理 config.get_effective_proxy()
        custom_proxy = (item.get("proxy") or "").strip()
        if custom_proxy in ["direct", "none"]:
            final_proxy = ""
        elif custom_proxy and custom_proxy != "default":
            final_proxy = custom_proxy
        else:
            final_proxy = config.get_effective_proxy()

        task_info = {
            "url": url,
            "title": title,
            "resolution": item.get("resolution", ""),
            "duration": item.get("duration", 0),
            "media_type": media_type,
            "save_dir": save_dir,
            "save_name": item.get("saveName", "") or item.get("save_name", ""),
            "headers": headers,
            "format": item.get("format", "mp4"),
            "proxy": final_proxy,
            "thread_count": thread_count
        }
        auto_start = config.get("auto_start_tasks", True)
        return task_manager.add_task(task_info, auto_start=auto_start)


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class LocalServer:
    def __init__(self):
        self.server = None
        self._thread = None
        self.is_running = False

    def start(self):
        host = config.get("server_host", "127.0.0.1")
        port = int(config.get("server_port", 18910))

        try:
            self.server = ReusableHTTPServer((host, port), CatCatchHTTPHandler)
            self.server.timeout = 0.5
            self.is_running = True
            self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            self.is_running = False
            return False

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.is_running = False


# 单例服务端
local_server = LocalServer()
