"""
CatCatch Downloader - Multi-Threaded Range Chunk Downloader (IDM Style)
用于 MP4 / FLV / WebM / MP3 / 文件等标准 HTTP(S) 直链的多线程分块并发高速下载
"""
import os
import re
import time
import threading
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor
import subprocess
import requests

from .config import config
from .ffmpeg_engine import get_ffmpeg_path


def format_size(bytes_val):
    if bytes_val <= 0:
        return "未知"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


def get_requests_session(proxy=None):
    s = requests.Session()
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    else:
        s.trust_env = False
    return s


def check_auto_convert_mp4(file_path, on_log=None):
    if not config.get("auto_convert_mp4", True) or not file_path:
        return file_path
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".ts", ".flv", ".webm", ".mkv"]:
        mp4_path = os.path.splitext(file_path)[0] + ".mp4"
        ff_exe = get_ffmpeg_path()
        if ff_exe:
            if on_log:
                on_log(f"检测到 {ext} 格式，正在自动调用内置 FFmpeg 转封装为标准 MP4...")
            try:
                cmd = [ff_exe, "-y", "-i", file_path, "-c", "copy", "-movflags", "+faststart", mp4_path]
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags, timeout=60)
                if res.returncode == 0 and os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                    if config.get("del_tmp_files", True):
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass
                    return mp4_path
            except Exception as e:
                if on_log:
                    on_log(f"自动转 MP4 提示: {e}")
    return file_path


class FileDownloadTask:
    def __init__(self, task_data, on_progress=None, on_log=None, on_finished=None):
        self.task_data = task_data
        self.on_progress = on_progress  # cb(percent, speed_str, eta_str, downloaded_bytes, total_bytes)
        self.on_log = on_log            # cb(line)
        self.on_finished = on_finished  # cb(success, message, output_file)
        
        self._is_cancelled = False
        self._is_paused = False
        self._thread = None
        self.output_file = ""

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._is_cancelled = True

    def pause(self):
        self._is_paused = True

    def _run(self):
        url = self.task_data.get("url")
        save_dir = self.task_data.get("save_dir") or config.get("save_dir")
        save_name = self.task_data.get("save_name") or ""
        headers = self.task_data.get("headers", {})

        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req_headers.update({k: v for k, v in headers.items() if v})

        os.makedirs(save_dir, exist_ok=True)

        if self.on_log:
            self.on_log(f"正在探测远程资源信息: {url}")

        proxy = self.task_data.get("proxy") or config.get_effective_proxy()
        self.session = get_requests_session(proxy)

        # 1. 探测资源头部信息
        content_length = 0
        accept_ranges = False
        final_filename = save_name

        try:
            head_resp = self.session.head(url, headers=req_headers, allow_redirects=True, timeout=10)
            if head_resp.status_code < 400:
                content_length = int(head_resp.headers.get("Content-Length", 0))
                accept_ranges = "bytes" in head_resp.headers.get("Accept-Ranges", "").lower()
                cd = head_resp.headers.get("Content-Disposition", "")
                if not final_filename and cd:
                    cd_match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)', cd)
                    if cd_match:
                        final_filename = unquote(cd_match.group(1))
        except Exception:
            pass

        # 若未指定文件名，从 URL 解析
        if not final_filename:
            parsed = urlparse(url)
            path_file = os.path.basename(parsed.path)
            if path_file and "." in path_file:
                final_filename = unquote(path_file)
            else:
                ext = self.task_data.get("format", "mp4")
                final_filename = f"video_{int(time.time())}.{ext}"

        final_filename = re.sub(r'[\\/*?:"<>|]', '_', final_filename).strip()
        self.output_file = os.path.join(save_dir, final_filename)

        if self.on_log:
            self.on_log(f"目标文件: {self.output_file}")
            self.on_log(f"文件大小: {format_size(content_length)} | 支持分块加速: {'是' if accept_ranges else '否'}")

        # 2. 选择下载策略：多线程分块 vs 单流直下
        thread_num = int(self.task_data.get("thread_count", config.get("max_threads_per_task", 8)))
        if accept_ranges and content_length > 2 * 1024 * 1024 and thread_num > 1:
            self._download_multithread(url, req_headers, content_length, thread_num)
        else:
            self._download_single(url, req_headers, content_length)

    def _download_multithread(self, url, headers, total_size, num_threads):
        """多线程分块下载 (IDM 核心加速)"""
        part_size = total_size // num_threads
        part_ranges = []
        for i in range(num_threads):
            start = i * part_size
            end = total_size - 1 if i == num_threads - 1 else (start + part_size - 1)
            part_ranges.append((start, end))

        part_files = [f"{self.output_file}.part{i}" for i in range(num_threads)]
        downloaded_bytes = [0] * num_threads
        lock = threading.Lock()

        last_time = time.time()
        last_downloaded = 0

        def download_chunk(idx, start_byte, end_byte):
            nonlocal last_time, last_downloaded
            chunk_headers = dict(headers)
            chunk_headers["Range"] = f"bytes={start_byte}-{end_byte}"
            part_path = part_files[idx]

            try:
                with self.session.get(url, headers=chunk_headers, stream=True, timeout=20) as r:
                    r.raise_for_status()
                    with open(part_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=64 * 1024):
                            if self._is_cancelled or self._is_paused:
                                return
                            if chunk:
                                f.write(chunk)
                                with lock:
                                    downloaded_bytes[idx] += len(chunk)
                                    cur_total = sum(downloaded_bytes)
                                    now = time.time()
                                    if now - last_time >= 0.2:
                                        speed = (cur_total - last_downloaded) / (now - last_time)
                                        last_time = now
                                        last_downloaded = cur_total

                                        pct = (cur_total / total_size) * 100.0 if total_size > 0 else 0
                                        spd_str = f"{format_size(speed)}/s"
                                        eta_sec = int((total_size - cur_total) / speed) if speed > 0 else 0
                                        eta_str = f"{eta_sec // 60:02d}:{eta_sec % 60:02d}"

                                        if self.on_progress:
                                            self.on_progress(pct, spd_str, eta_str, cur_total, total_size)
            except Exception as e:
                if self.on_log:
                    self.on_log(f"分块 {idx} 下载异常: {e}")

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            for idx, (s, e) in enumerate(part_ranges):
                executor.submit(download_chunk, idx, s, e)

        if self._is_cancelled or self._is_paused:
            for p in part_files:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            if self.on_finished:
                self.on_finished(False, "任务已暂停或取消", "")
            return

        # 检查是否全部下载完成
        total_dl = sum(downloaded_bytes)
        if total_dl < total_size:
            if self.on_finished:
                self.on_finished(False, f"下载未完成: 已接收 {format_size(total_dl)} / 期望 {format_size(total_size)}", "")
            return

        # 合并各分块文件
        if self.on_log:
            self.on_log("所有分块接收完毕，正在合并生成目标文件...")
        with open(self.output_file, "wb") as out_f:
            for p in part_files:
                if os.path.exists(p):
                    with open(p, "rb") as in_f:
                        while True:
                            buf = in_f.read(1024 * 1024)
                            if not buf:
                                break
                            out_f.write(buf)
                    try:
                        os.remove(p)
                    except Exception:
                        pass

        final_out = check_auto_convert_mp4(self.output_file, self.on_log)
        if self.on_progress:
            self.on_progress(100.0, "完成", "", total_size, total_size)
        if self.on_finished:
            self.on_finished(True, "下载完成", final_out)

    def _download_single(self, url, headers, total_size):
        """单流极速下载 (不支持 Range 或小于阈值)"""
        last_time = time.time()
        last_dl = 0
        cur_dl = 0

        tmp_out = f"{self.output_file}.tmp"

        try:
            with self.session.get(url, headers=headers, stream=True, timeout=20) as r:
                r.raise_for_status()
                with open(tmp_out, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if self._is_cancelled or self._is_paused:
                            break
                        if chunk:
                            f.write(chunk)
                            cur_dl += len(chunk)
                            now = time.time()
                            if now - last_time >= 0.5:
                                speed = (cur_dl - last_dl) / (now - last_time)
                                last_time = now
                                last_dl = cur_dl

                                pct = (cur_dl / total_size) * 100.0 if total_size > 0 else 0
                                spd_str = f"{format_size(speed)}/s"
                                eta_sec = int((total_size - cur_dl) / speed) if (speed > 0 and total_size > 0) else 0
                                eta_str = f"{eta_sec // 60:02d}:{eta_sec % 60:02d}"

                                if self.on_progress:
                                    self.on_progress(pct, spd_str, eta_str, cur_dl, total_size)

            if self._is_cancelled or self._is_paused:
                if os.path.exists(tmp_out):
                    try:
                        os.remove(tmp_out)
                    except Exception:
                        pass
                if self.on_finished:
                    self.on_finished(False, "任务已取消或暂停", "")
                return

            if os.path.exists(self.output_file):
                try:
                    os.remove(self.output_file)
                except Exception:
                    pass
            os.rename(tmp_out, self.output_file)

            final_out = check_auto_convert_mp4(self.output_file, self.on_log)
            if self.on_progress:
                self.on_progress(100.0, "完成", "", cur_dl, cur_dl)
            if self.on_finished:
                self.on_finished(True, "下载完成", final_out)

        except Exception as e:
            if os.path.exists(tmp_out):
                try:
                    os.remove(tmp_out)
                except Exception:
                    pass
            if self.on_finished:
                self.on_finished(False, f"下载失败: {e}", "")
