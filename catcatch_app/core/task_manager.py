"""
CatCatch Downloader - Task Manager
中央任务队列管理、并发控制、调度与持久化
"""
import os
import json
import time
import uuid
import threading
from PyQt5.QtCore import QObject, pyqtSignal

from .config import config, APP_DIR, TASKS_FILE, build_save_name, format_resolution, format_duration
from .download_stream import StreamDownloadTask
from .download_file import FileDownloadTask, format_size
from .ffmpeg_engine import probe_media_info
from .logger import record_download_error, diagnose_error

TASKS_DB_FILE = TASKS_FILE


class TaskManager(QObject):
    task_added = pyqtSignal(dict)
    task_updated = pyqtSignal(str, dict)
    task_status_changed = pyqtSignal(str, str)
    task_completed = pyqtSignal(str, str)
    task_failed = pyqtSignal(str, str)
    task_removed = pyqtSignal(str)
    global_speed_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._tasks = []
        self._active_workers = {}  # task_id -> task_instance
        self._lock = threading.Lock()
        self.load_tasks()

    def load_tasks(self):
        if os.path.exists(TASKS_DB_FILE):
            try:
                with open(TASKS_DB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        # 恢复时，将之前的下载中状态调整为已暂停
                        if item.get("status") in ["downloading", "waiting"]:
                            item["status"] = "paused"
                            item["speed"] = ""
                            item["eta"] = ""
                        self._tasks.append(item)
            except Exception as e:
                print(f"[TaskManager] 加载历史任务失败: {e}")

    def save_tasks(self):
        try:
            with open(TASKS_DB_FILE, "w", encoding="utf-8") as f:
                # 过滤只保留前 200 条
                saved_list = []
                for t in self._tasks[:200]:
                    copy_t = dict(t)
                    if copy_t.get("status") == "error":
                        if "logs" in copy_t and isinstance(copy_t["logs"], list):
                            copy_t["logs"] = copy_t["logs"][-60:]
                    else:
                        copy_t.pop("logs", None)
                    saved_list.append(copy_t)
                json.dump(saved_list, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[TaskManager] 保存历史任务失败: {e}")

    def add_task(self, task_info, auto_start=True):
        """
        添加新任务
        task_info: {
            url, title, media_type ('m3u8'|'mp4'|'audio'|'file'),
            save_dir, save_name, headers, format, proxy, thread_count
        }
        """
        task_id = str(uuid.uuid4())[:8]
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        media_type = task_info.get("media_type") or self._detect_media_type(task_info.get("url", ""))

        url = task_info.get("url", "").strip()
        is_blob = url.startswith("blob:")

        raw_title = task_info.get("title") or f"video_{task_id}"
        res_raw = task_info.get("resolution", "")
        dur_raw = task_info.get("duration", 0)
        res_formatted = format_resolution(res_raw)
        dur_formatted = format_duration(dur_raw)

        save_name = task_info.get("save_name")
        if not save_name:
            save_name = build_save_name(raw_title, res_formatted, dur_formatted)

        blob_err = "blob: 为浏览器临时内存对象，非网络地址。请播放视频后在插件列表中选择实际嗅探到的 m3u8 地址！"
        task = {
            "id": task_id,
            "url": url,
            "title": raw_title,
            "resolution": res_formatted,
            "duration": dur_formatted,
            "media_type": media_type,
            "save_dir": task_info.get("save_dir") or config.get("save_dir"),
            "save_name": save_name,
            "headers": task_info.get("headers", {}),
            "format": task_info.get("format", "mp4"),
            "proxy": task_info.get("proxy", ""),
            "thread_count": task_info.get("thread_count", config.get("max_threads_per_task", 16)),
            "status": "error" if is_blob else ("waiting" if auto_start else "paused"),
            "progress": 0.0,
            "speed": "失败" if is_blob else "",
            "eta": "--" if is_blob else "",
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "output_file": "",
            "error_msg": blob_err if is_blob else "",
            "error_reason": "无效地址 (blob: 临时内存流)" if is_blob else "",
            "error_hint": "blob: 是浏览器前端在内存中生成的临时流对象，并非实际网络资源地址。请在播放视频后选择嗅探到的 .m3u8 清单或 .mp4 直链下载。" if is_blob else "",
            "created_at": now,
            "logs": [f"[{now}] 任务初始化", f"[{now}] 检测到 blob: 内存流地址，已标记错误"] if is_blob else []
        }

        if is_blob:
            diag_title, diag_hint, log_p = record_download_error(task, blob_err, task["logs"])
            task["log_file"] = log_p

        with self._lock:
            self._tasks.insert(0, task)

        self.save_tasks()
        self.task_added.emit(task)

        if auto_start and not is_blob:
            self._schedule_next()

        return task_id

    def _detect_media_type(self, url):
        url_lower = url.lower().split("?")[0]
        if ".m3u8" in url_lower or ".mpd" in url_lower:
            return "m3u8"
        elif any(url_lower.endswith(ext) for ext in [".mp4", ".flv", ".webm", ".mkv", ".ts", ".avi", ".mov"]):
            return "video"
        elif any(url_lower.endswith(ext) for ext in [".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"]):
            return "audio"
        return "file"

    def get_task(self, task_id):
        with self._lock:
            for t in self._tasks:
                if t["id"] == task_id:
                    return t
        return None

    def get_all_tasks(self):
        with self._lock:
            return list(self._tasks)

    def start_task(self, task_id):
        task = self.get_task(task_id)
        if not task:
            return
        if task["status"] in ["downloading", "waiting"]:
            return
        task["status"] = "waiting"
        task["error_msg"] = ""
        self.task_status_changed.emit(task_id, "waiting")
        self._schedule_next()

    def pause_task(self, task_id):
        task = self.get_task(task_id)
        if not task:
            return
        worker = self._active_workers.get(task_id)
        if worker:
            worker.cancel()
            self._active_workers.pop(task_id, None)

        task["status"] = "paused"
        task["speed"] = ""
        task["eta"] = ""
        self.task_status_changed.emit(task_id, "paused")
        self.save_tasks()
        self._schedule_next()

    def remove_task(self, task_id, delete_file=False):
        self.pause_task(task_id)
        target_file = ""
        with self._lock:
            for i, t in enumerate(self._tasks):
                if t["id"] == task_id:
                    target_file = t.get("output_file")
                    self._tasks.pop(i)
                    break
        
        if delete_file and target_file and os.path.exists(target_file):
            try:
                os.remove(target_file)
            except Exception:
                pass

        self.save_tasks()
        self.task_removed.emit(task_id)
        self._schedule_next()

    def _schedule_next(self):
        max_concurrent = int(config.get("max_concurrent_tasks", 3))
        with self._lock:
            active_count = len(self._active_workers)
            if active_count >= max_concurrent:
                return

            # 寻找 waiting 状态任务
            for t in self._tasks:
                if t["status"] == "waiting" and t["id"] not in self._active_workers:
                    self._start_worker(t)
                    active_count += 1
                    if active_count >= max_concurrent:
                        break

    def _start_worker(self, task):
        task_id = task["id"]
        task["status"] = "downloading"
        self.task_status_changed.emit(task_id, "downloading")

        def on_prog(percent, speed_str, eta_str, cur_dl=0, tot_dl=0, cur_parts=0, tot_parts=0):
            task["progress"] = round(percent, 1)
            task["speed"] = speed_str
            task["eta"] = eta_str
            task["downloaded_bytes"] = cur_dl
            task["total_bytes"] = tot_dl
            task["cur_parts"] = cur_parts
            task["tot_parts"] = tot_parts
            self.task_updated.emit(task_id, task)

        def on_log(line):
            if "logs" not in task:
                task["logs"] = []
            task["logs"].append(line)
            if len(task["logs"]) > 200:
                task["logs"].pop(0)

        def on_fin(success, message, output_path):
            self._active_workers.pop(task_id, None)
            if success:
                task["status"] = "completed"
                task["progress"] = 100.0
                task["speed"] = "完成"
                task["eta"] = "--"
                task["output_file"] = output_path

                # 自动调用 FFmpeg 校验并补齐视频规格信息 (时长、真实分辨率、真实大小)
                if output_path and os.path.exists(output_path):
                    try:
                        file_sz = os.path.getsize(output_path)
                        if file_sz > 0:
                            task["total_bytes"] = file_sz
                            task["downloaded_bytes"] = file_sz
                        media_info = probe_media_info(output_path)
                        if not task.get("resolution") and media_info.get("resolution") != "未知":
                            task["resolution"] = format_resolution(media_info.get("resolution"))
                        if not task.get("duration") and media_info.get("duration_str") != "未知":
                            task["duration"] = media_info.get("duration_str")
                    except Exception as e:
                        print(f"[TaskManager] 探测媒体属性异常: {e}")

                self.task_completed.emit(task_id, output_path)
            else:
                if "手动取消" in message or task.get("status") == "paused":
                    task["status"] = "paused"
                    task["speed"] = "已暂停"
                    task["eta"] = "--"
                    task["error_msg"] = message
                else:
                    task["status"] = "error"
                    task["speed"] = "失败"
                    task["eta"] = "--"
                    task["error_msg"] = message

                    # 智能诊断出错根因并写入 Logs/ 错误日志
                    diag_title, diag_hint, log_p = record_download_error(task, message, task.get("logs", []))
                    task["error_reason"] = diag_title
                    task["error_hint"] = diag_hint
                    task["log_file"] = log_p

                    self.task_failed.emit(task_id, message)
            
            self.task_status_changed.emit(task_id, task["status"])
            self.save_tasks()
            self._schedule_next()

        if task["media_type"] == "m3u8":
            worker = StreamDownloadTask(task, on_progress=on_prog, on_log=on_log, on_finished=on_fin)
        else:
            worker = FileDownloadTask(task, on_progress=on_prog, on_log=on_log, on_finished=on_fin)

        self._active_workers[task_id] = worker
        worker.start()


# 单例任务管理器
task_manager = TaskManager()
