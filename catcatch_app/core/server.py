"""
CatCatch Downloader - Embedded HTTP IPC & Mobile WebUI Server
提供本地 RESTful API 服务，与浏览器插件无缝双向互通
支持手机局域网无线连接、扫码推流与远程任务控制
默认监听: 0.0.0.0:18910
"""
import json
import threading
import socketserver
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from .config import config, detect_local_active_proxies, get_temp_segments_dir
from .task_manager import task_manager
from .ffmpeg_engine import is_ffmpeg_available, get_ffmpeg_path
from .cache_cleaner import get_fragment_folders, clean_all_fragment_folders


MOBILE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>星流 (StarStream) - 手机无线推流工作台</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
body { background: #090a0f; color: #f4f4f5; padding: 16px; min-height: 100vh; }
.header { display: flex; align-items: center; justify-content: space-between; padding-bottom: 16px; border-bottom: 1px solid #27272a; margin-bottom: 20px; }
.brand { display: flex; align-items: center; gap: 10px; }
.logo-icon { width: 34px; height: 34px; background: linear-gradient(135deg, #38bdf8, #818cf8); border-radius: 9px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #fff; font-size: 18px; box-shadow: 0 2px 8px rgba(56, 189, 248, 0.4); }
.brand-name { font-size: 19px; font-weight: 700; background: linear-gradient(135deg, #38bdf8, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.badge { background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; box-shadow: 0 0 6px #22c55e; }
.card { background: #18181b; border: 1px solid #27272a; border-radius: 14px; padding: 18px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
.card-title { font-size: 15px; font-weight: 600; color: #e4e4e7; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.input-group { margin-bottom: 12px; }
.input-label { display: block; font-size: 12px; color: #a1a1aa; margin-bottom: 6px; }
input[type="text"] { width: 100%; background: #090a0f; border: 1px solid #3f3f46; border-radius: 8px; padding: 12px 14px; color: #fff; font-size: 14px; outline: none; transition: border 0.2s; }
input[type="text"]:focus { border-color: #38bdf8; }
.btn { width: 100%; padding: 13px; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: transform 0.1s, opacity 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; }
.btn-primary { background: linear-gradient(135deg, #3875f6, #6366f1); color: #fff; box-shadow: 0 4px 12px rgba(56, 117, 246, 0.3); }
.btn-primary:active { transform: scale(0.98); opacity: 0.9; }
.toast { display: none; padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-top: 10px; text-align: center; }
.toast.success { display: block; background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }
.toast.error { display: block; background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.task-item { background: #121316; border: 1px solid #27272a; border-radius: 10px; padding: 14px; margin-bottom: 10px; }
.task-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.task-title { font-size: 14px; font-weight: 600; color: #f4f4f5; max-width: 75%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.status-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.st-downloading { background: rgba(56, 117, 246, 0.2); color: #60a5fa; }
.st-completed { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
.st-error { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.st-waiting { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
.st-paused { background: rgba(161, 161, 170, 0.2); color: #a1a1aa; }
.progress-bar-bg { width: 100%; height: 6px; background: #27272a; border-radius: 3px; overflow: hidden; margin-bottom: 8px; }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8); border-radius: 3px; transition: width 0.3s; }
.task-meta { display: flex; justify-content: space-between; font-size: 12px; color: #a1a1aa; }
.task-actions { margin-top: 8px; display: flex; justify-content: flex-end; gap: 8px; }
.btn-mini { padding: 4px 10px; font-size: 11px; border-radius: 5px; border: 1px solid #3f3f46; background: #27272a; color: #e4e4e7; cursor: pointer; }
.btn-mini:active { transform: scale(0.96); }
.btn-mini.primary { background: rgba(56, 117, 246, 0.25); border-color: #3875f6; color: #60a5fa; }
.btn-mini.danger { background: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.4); color: #f87171; }
.empty-tip { text-align: center; color: #71717a; font-size: 13px; padding: 20px 0; }
</style>
</head>
<body>
<div class="header">
  <div class="brand">
    <div class="logo-icon">★</div>
    <div class="brand-name">星流 StarStream</div>
  </div>
  <div class="badge"><div class="dot"></div>电脑极速互联</div>
</div>

<div class="card">
  <div class="card-title">手机无线推流到电脑下载</div>
  <div class="input-group">
    <label class="input-label">视频地址 (支持 B站、抖音、快手、小红书、M3U8直链):</label>
    <input type="text" id="urlInput" placeholder="长按粘贴视频分享链接或网页地址...">
  </div>
  <div class="input-group">
    <label class="input-label">保存名称 (选填，留空将自动联网解析标题):</label>
    <input type="text" id="nameInput" placeholder="默认自动解析">
  </div>
  <button class="btn btn-primary" id="pushBtn" onclick="pushTask()">立即推送到电脑下载</button>
  <div class="toast" id="toastMsg"></div>
</div>

<div class="card">
  <div class="card-title">电脑实时任务状态 (<span id="taskCount">0</span>)</div>
  <div id="taskList">
    <div class="empty-tip">正在同步电脑端任务...</div>
  </div>
</div>

<script>
async function pushTask() {
  const url = document.getElementById('urlInput').value.trim();
  const name = document.getElementById('nameInput').value.trim();
  const btn = document.getElementById('pushBtn');
  if (!url) {
    showToast('请输入有效的视频链接！', 'error');
    return;
  }
  btn.disabled = true;
  btn.innerText = '正在推送到电脑...';
  try {
    const resp = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url, title: name || 'video' })
    });
    const res = await resp.json();
    if (res.success) {
      showToast('已成功推送到电脑！正在自动开启解析与下载', 'success');
      document.getElementById('urlInput').value = '';
      document.getElementById('nameInput').value = '';
      loadTasks();
    } else {
      showToast(res.error || '推送失败，请检查链接', 'error');
    }
  } catch (e) {
    showToast('连接电脑失败: ' + e, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = '立即推送到电脑下载';
  }
}

async function taskAction(id, action) {
  try {
    await fetch('/api/tasks/' + id + '/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action })
    });
    loadTasks();
  } catch (e) {}
}

function showToast(text, type) {
  const t = document.getElementById('toastMsg');
  t.innerText = text;
  t.className = 'toast ' + type;
  setTimeout(() => { t.className = 'toast'; }, 5000);
}

let pollTimer = null;
let isDocumentVisible = true;

document.addEventListener('visibilitychange', () => {
  isDocumentVisible = !document.hidden;
  if (isDocumentVisible) {
    loadTasks();
  }
});

function scheduleNextPoll(intervalMs) {
  if (pollTimer) clearTimeout(pollTimer);
  pollTimer = setTimeout(loadTasks, intervalMs);
}

async function loadTasks() {
  if (!isDocumentVisible) {
    scheduleNextPoll(3000);
    return;
  }
  try {
    const resp = await fetch('/api/mobile/tasks');
    const res = await resp.json();
    if (res.success) {
      const tasks = res.tasks || [];
      document.getElementById('taskCount').innerText = res.total !== undefined ? res.total : tasks.length;
      renderTasks(tasks);
      const hasActive = tasks.some(t => t.status === 'downloading');
      scheduleNextPoll(hasActive ? 1500 : 4000);
      return;
    }
  } catch (e) {}
  scheduleNextPoll(4000);
}

function renderTasks(tasks) {
  const container = document.getElementById('taskList');
  if (!tasks || tasks.length === 0) {
    container.innerHTML = '<div class="empty-tip">暂无下载任务</div>';
    return;
  }
  let html = '';
  for (const t of tasks.slice(0, 25)) {
    const prog = (t.progress || 0).toFixed(1);
    const speed = t.speed || (t.status === 'downloading' ? '计算中...' : '');
    const stClass = 'st-' + (t.status || 'waiting');
    const stText = { downloading: '下载中', completed: '已完成', error: '失败', paused: '已暂停', waiting: '排队中' }[t.status] || t.status;
    html += `
      <div class="task-item">
        <div class="task-header">
          <div class="task-title" title="${t.title || 'video'}">${t.title || t.save_name || 'video'}</div>
          <span class="status-tag ${stClass}">${stText}</span>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" style="width: ${prog}%"></div>
        </div>
        <div class="task-meta">
          <span>进度: ${prog}%</span>
          <span>${speed ? '速度: ' + speed : ''}</span>
        </div>
        <div class="task-actions">
          ${t.status === 'downloading'
            ? `<button class="btn-mini" onclick="taskAction('${t.id}', 'pause')">暂停</button>`
            : (t.status === 'paused' || t.status === 'error' ? `<button class="btn-mini primary" onclick="taskAction('${t.id}', 'start')">开始</button>` : '')
          }
          <button class="btn-mini danger" onclick="taskAction('${t.id}', 'delete')">删除</button>
        </div>
      </div>
    `;
  }
  container.innerHTML = html;
}

loadTasks();
</script>
</body>
</html>
"""


class CatCatchHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 屏蔽默认标准输出刷屏，避免干扰控制台
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

    def _send_html_response(self, code, html_text):
        self.send_response(code)
        self._send_cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_text.encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        accept = self.headers.get("Accept", "")

        if path in ["/", "/web"]:
            if "application/json" in accept and "text/html" not in accept:
                self._send_status_json()
            else:
                self._send_html_response(200, MOBILE_HTML)
            return

        elif path == "/api/status":
            self._send_status_json()
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

        elif path == "/api/mobile/tasks":
            # 专为移动端无线扫码推流设计的超轻量级精简接口 (过滤庞大日志文本，解决手机 WiFi 轮询卡顿)
            tasks = task_manager.get_all_tasks()
            lite_tasks = []
            for t in tasks[:30]:
                lite_tasks.append({
                    "id": t.get("id"),
                    "title": t.get("title") or t.get("save_name") or "video",
                    "status": t.get("status", "waiting"),
                    "progress": round(float(t.get("progress") or 0.0), 1),
                    "speed": t.get("speed") or "",
                    "media_type": t.get("media_type") or "m3u8"
                })
            self._send_json_response(200, {
                "success": True,
                "tasks": lite_tasks,
                "total": len(tasks)
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

    def _send_status_json(self):
        ff_ok, ff_msg = is_ffmpeg_available()
        tasks = task_manager.get_all_tasks()
        active_count = sum(1 for t in tasks if t["status"] == "downloading")
        self._send_json_response(200, {
            "status": "ok",
            "app": "StarStream Downloader",
            "version": "3.1.0",
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

        # 智能全网逆向解析: 若为主流短视频平台分享链接，自动在后台提取无水印直链
        if any(d in url.lower() for d in ["douyin.com", "bilibili.com", "b23.tv", "kuaishou.com", "xiaohongshu.com"]):
            try:
                from .video_parser import parse_video_url
                p_res = parse_video_url(url)
                if p_res.get("success"):
                    url = p_res["url"]
                    if p_res.get("title") and (not title or title == "video"):
                        title = p_res["title"]
                    if p_res.get("media_type"):
                        media_type = p_res["media_type"]
                    if p_res.get("headers"):
                        headers.update(p_res["headers"])
            except Exception as e:
                print(f"[Server] 视频解析引擎跳过: {e}")

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
            "save_name": title,
            "headers": headers,
            "thread_count": thread_count,
            "proxy": final_proxy,
            "format": item.get("format", "mp4")
        }

        task_id = task_manager.add_task(task_info, auto_start=True)
        return task_id


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """多线程并发 HTTP 服务，彻底根除单线程阻塞导致局域网手机/插件通信卡死问题"""
    allow_reuse_address = True
    daemon_threads = True


class LocalServer:
    def __init__(self):
        self.server = None
        self._thread = None
        self.is_running = False

    def start(self):
        # 默认监听 0.0.0.0，使手机在同一 WiFi 局域网下可直接扫码推流访问
        host = config.get("server_host", "0.0.0.0")
        port = int(config.get("server_port", 18910))

        try:
            self.server = ThreadedHTTPServer((host, port), CatCatchHTTPHandler)
            self.server.timeout = 0.5
            self.is_running = True
            self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            # 兜底回退尝试 127.0.0.1
            try:
                self.server = ThreadedHTTPServer(("127.0.0.1", port), CatCatchHTTPHandler)
                self.server.timeout = 0.5
                self.is_running = True
                self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
                self._thread.start()
                return True
            except Exception:
                self.is_running = False
                return False

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None
            self.is_running = False


local_server = LocalServer()
