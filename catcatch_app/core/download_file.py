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

from .config import config, is_proxy_alive, detect_local_active_proxies, should_bypass_proxy, get_temp_segments_dir
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
    if not config.get("auto_convert_mp4", True) or not file_path or not os.path.exists(file_path):
        return file_path
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".ts", ".flv", ".webm", ".mkv", ".mov", ".avi"]:
        mp4_path = os.path.splitext(file_path)[0] + ".mp4"
        ff_exe = get_ffmpeg_path()
        if ff_exe:
            if on_log:
                on_log(f"检测到 {ext} 容器，正在自动调用内置 FFmpeg 转封装为标准 MP4 (支持极速秒播)...")
            try:
                cmd = [ff_exe, "-y", "-i", file_path, "-c", "copy", "-movflags", "+faststart", mp4_path]
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags, timeout=120)
                if res.returncode == 0 and os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                    if config.get("del_tmp_files", True):
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass
                    if on_log:
                        on_log(f"自动转封装成功: {os.path.basename(mp4_path)}")
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
        try:
            self._do_run()
        except Exception as e:
            if self.on_log:
                self.on_log(f"下载任务异常终止: {e}")
            if self.on_finished:
                self.on_finished(False, f"下载异常: {e}", "")

    def _do_run(self):
        url = self.task_data.get("url")
        save_dir = self.task_data.get("save_dir") or config.get("save_dir")
        save_name = self.task_data.get("save_name") or ""
        headers = self.task_data.get("headers", {})

        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req_headers.update({k: v for k, v in headers.items() if v})

        # 防盗链修补与短视频平台 Referer 智能补全
        if not req_headers.get("Referer"):
            ref = self.task_data.get("referer") or self.task_data.get("pageUrl")
            if ref:
                req_headers["Referer"] = ref
            elif any(d in url for d in ["douyinvod.com", "douyin.com", "snssdk.com", "iesdouyin.com"]):
                req_headers["Referer"] = "https://www.douyin.com/"
            elif any(d in url for d in ["bilivideo.com", "bilivideo.cn", "hdslb.com"]):
                req_headers["Referer"] = "https://www.bilibili.com/"
            elif any(d in url for d in ["kwaicdn.com", "kwai.net"]):
                req_headers["Referer"] = "https://www.kuaishou.com/"
            elif any(d in url for d in ["xhscdn.com"]):
                req_headers["Referer"] = "https://www.xiaohongshu.com/"
            elif "cdnplay.mom" in url:
                req_headers["Referer"] = "https://huangguo01.net/"

        if req_headers.get("Referer") and not req_headers.get("Origin"):
            try:
                ref_u = urlparse(req_headers["Referer"])
                if ref_u.scheme and ref_u.netloc:
                    req_headers["Origin"] = f"{ref_u.scheme}://{ref_u.netloc}"
            except Exception:
                pass

        os.makedirs(save_dir, exist_ok=True)

        if self.on_log:
            self.on_log(f"正在探测远程资源信息: {url}")

        from .config import detect_system_proxy, normalize_proxy_url
        task_p = (self.task_data.get("proxy") or "").strip()
        proxy = None
        if task_p.upper() in ["DIRECT", "NONE"]:
            proxy = None
        elif task_p.upper() in ["SYSTEM", "__SYSTEM__"]:
            sys_p = detect_system_proxy()
            proxy = sys_p if sys_p else None
        elif task_p.upper() in ["AUTO", "DEFAULT", "GLOBAL", ""] or not task_p:
            proxy = config.get_effective_proxy(validate=True) or detect_system_proxy() or None
        else:
            proxy = normalize_proxy_url(task_p)

        if proxy and proxy.lower() not in ["none", "direct", "system"]:
            if should_bypass_proxy(url):
                if self.on_log:
                    self.on_log("[智能分流] 目标为国内高速 CDN 节点，已自动切换极速直连模式（规避海外代理拦截与 IP 绑定报错）")
                proxy = None
            else:
                is_alive, check_msg = is_proxy_alive(proxy, timeout=0.5)
                if not is_alive:
                    if self.on_log:
                        self.on_log(f"[代理探活警告] 配置的代理 ({proxy}) 无法连通 ({check_msg})，正在自动搜寻可用代理...")
                    actives = detect_local_active_proxies()
                    if actives:
                        proxy = actives[0]["url"]
                        if self.on_log:
                            self.on_log(f"[代理智能切换] 自动切换为活跃在线代理: {proxy} ({actives[0]['name']})")
                    else:
                        sys_p = detect_system_proxy()
                        if sys_p and is_proxy_alive(sys_p, timeout=0.5)[0]:
                            proxy = sys_p
                            if self.on_log:
                                self.on_log(f"[代理智能切换] 自动切换为系统代理: {proxy}")
                        else:
                            if self.on_log:
                                self.on_log("[代理降级提示] 未发现其它活跃代理，尝试直连下载...")
                            proxy = None
        else:
            proxy = None
        self.session = get_requests_session(proxy)

        # 检查是否为 DASH 音视频双流任务 (如 B站 音画合一)
        audio_url = self.task_data.get("audio_url")
        if audio_url or self.task_data.get("media_type") == "bili_dash":
            if audio_url:
                self._download_dual_stream(url, audio_url, req_headers, save_dir, save_name)
                return
            elif self.on_log:
                self.on_log("[音画提示] 检测到单轨 DASH 流，正在按视频轨标准格式下载...")

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

        # 兜底探测: 针对部分不响应 HEAD 的国内 CDN 进行 Range 0-0 轻量嗅探
        if content_length <= 0:
            try:
                probe_headers = dict(req_headers)
                probe_headers["Range"] = "bytes=0-0"
                with self.session.get(url, headers=probe_headers, stream=True, timeout=8) as pr:
                    if pr.status_code in (200, 206):
                        accept_ranges = (pr.status_code == 206)
                        cr = pr.headers.get("Content-Range", "")
                        if "/" in cr:
                            tot_s = cr.split("/")[-1].strip()
                            if tot_s.isdigit():
                                content_length = int(tot_s)
                        if content_length <= 0:
                            cl = pr.headers.get("Content-Length", "")
                            if cl.isdigit() and pr.status_code == 200:
                                content_length = int(cl)
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

        # 确保短视频/直链文件具备标准音视频扩展名
        base_name, existing_ext = os.path.splitext(final_filename)
        valid_media_exts = {".mp4", ".flv", ".webm", ".mkv", ".ts", ".mov", ".m4a", ".mp3", ".aac", ".avi"}
        if existing_ext.lower() not in valid_media_exts:
            detected_ext = ""
            url_path_ext = os.path.splitext(urlparse(url).path)[1].lower()
            if url_path_ext in valid_media_exts:
                detected_ext = url_path_ext
            elif 'head_resp' in locals() and head_resp is not None and getattr(head_resp, "headers", None):
                ct = head_resp.headers.get("Content-Type", "").lower()
                if "video/mp4" in ct:
                    detected_ext = ".mp4"
                elif "video/webm" in ct:
                    detected_ext = ".webm"
                elif "video/x-flv" in ct:
                    detected_ext = ".flv"
                elif "video/quicktime" in ct:
                    detected_ext = ".mov"
                elif "video/mp2t" in ct:
                    detected_ext = ".ts"
                elif "audio/mpeg" in ct or "audio/mp3" in ct:
                    detected_ext = ".mp3"
                elif "audio/" in ct:
                    detected_ext = ".m4a"

            if not detected_ext:
                fmt = str(self.task_data.get("format", "mp4")).strip().lower()
                detected_ext = f".{fmt}" if not fmt.startswith(".") else fmt
                if detected_ext not in valid_media_exts:
                    detected_ext = ".mp4"

            final_filename = f"{final_filename}{detected_ext}"

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
        """多线程分块下载 (IDM 核心加速，支持单块断点重试与故障隔离)"""
        part_size = total_size // num_threads
        part_ranges = []
        for i in range(num_threads):
            start = i * part_size
            end = total_size - 1 if i == num_threads - 1 else (start + part_size - 1)
            part_ranges.append((start, end))

        part_files = [f"{self.output_file}.part{i}" for i in range(num_threads)]
        downloaded_bytes = [0] * num_threads
        chunk_errors = []
        lock = threading.Lock()

        last_time = time.time()
        last_downloaded = 0
        peak_speed = 0.0

        def download_chunk(idx, start_byte, end_byte):
            nonlocal last_time, last_downloaded, peak_speed
            part_path = part_files[idx]
            cur_start = start_byte

            # 校验断点已存在分片
            if os.path.exists(part_path):
                existing_bytes = os.path.getsize(part_path)
                if 0 < existing_bytes <= (end_byte - start_byte + 1):
                    cur_start = start_byte + existing_bytes
                    with lock:
                        downloaded_bytes[idx] = existing_bytes

            if cur_start > end_byte:
                return

            max_retries = 3
            mode = "ab" if cur_start > start_byte else "wb"

            for attempt in range(max_retries):
                if self._is_cancelled or self._is_paused:
                    return
                try:
                    chunk_headers = dict(headers)
                    chunk_headers["Range"] = f"bytes={cur_start}-{end_byte}"
                    with self.session.get(url, headers=chunk_headers, stream=True, timeout=25) as r:
                        if r.status_code not in (200, 206):
                            r.raise_for_status()
                        with open(part_path, mode) as f:
                            for chunk in r.iter_content(chunk_size=64 * 1024):
                                if self._is_cancelled or self._is_paused:
                                    return
                                if chunk:
                                    f.write(chunk)
                                    cur_start += len(chunk)
                                    with lock:
                                        downloaded_bytes[idx] += len(chunk)
                                        cur_total = sum(downloaded_bytes)
                                        now = time.time()
                                        if now - last_time >= 0.2:
                                            speed = (cur_total - last_downloaded) / (now - last_time)
                                            last_time = now
                                            last_downloaded = cur_total

                                            if speed > peak_speed:
                                                peak_speed = speed

                                            pct = (cur_total / total_size) * 100.0 if total_size > 0 else 0
                                            spd_str = f"{format_size(speed)}/s"
                                            eta_sec = int((total_size - cur_total) / speed) if speed > 0 else 0
                                            eta_str = f"{eta_sec // 60:02d}:{eta_sec % 60:02d}"

                                            if self.on_progress:
                                                self.on_progress(pct, spd_str, eta_str, cur_total, total_size)

                    if cur_start > end_byte:
                        return
                except Exception as e:
                    mode = "ab"
                    if attempt < max_retries - 1 and not (self._is_cancelled or self._is_paused):
                        time.sleep(1.0)
                    else:
                        with lock:
                            chunk_errors.append(str(e))
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
            err_detail = f"分块下载未完成: 已接收 {format_size(total_dl)} / 期望 {format_size(total_size)}"
            if chunk_errors:
                err_detail += f" (原因: {chunk_errors[-1]})"
            if self.on_finished:
                self.on_finished(False, err_detail, "")
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
        """单流极速下载 (支持断点重试与流保活)"""
        last_time = time.time()
        start_time = time.time()
        last_dl = 0
        cur_dl = 0
        peak_speed = 0.0

        tmp_out = f"{self.output_file}.tmp"
        max_retries = 3

        for attempt in range(max_retries):
            if self._is_cancelled or self._is_paused:
                break
            try:
                cur_headers = dict(headers)
                mode = "wb"
                if os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0 and attempt > 0:
                    cur_dl = os.path.getsize(tmp_out)
                    cur_headers["Range"] = f"bytes={cur_dl}-"
                    mode = "ab"

                with self.session.get(url, headers=cur_headers, stream=True, timeout=25) as r:
                    if r.status_code not in (200, 206):
                        r.raise_for_status()
                    if total_size <= 0:
                        cl = r.headers.get("Content-Length")
                        if cl and cl.isdigit():
                            total_size = int(cl) + (cur_dl if mode == "ab" else 0)

                    with open(tmp_out, mode) as f:
                        for chunk in r.iter_content(chunk_size=64 * 1024):
                            if self._is_cancelled or self._is_paused:
                                break
                            if chunk:
                                f.write(chunk)
                                cur_dl += len(chunk)
                                now = time.time()
                                if now - last_time >= 0.3:
                                    speed = (cur_dl - last_dl) / (now - last_time)
                                    last_time = now
                                    last_dl = cur_dl

                                    if speed > peak_speed:
                                        peak_speed = speed

                                    pct = (cur_dl / total_size) * 100.0 if total_size > 0 else 0
                                    spd_str = f"{format_size(speed)}/s"
                                    eta_sec = int((total_size - cur_dl) / speed) if (speed > 0 and total_size > 0) else 0
                                    eta_str = f"{eta_sec // 60:02d}:{eta_sec % 60:02d}"

                                    if self.on_progress:
                                        self.on_progress(pct, spd_str, eta_str, cur_dl, total_size)
                break
            except Exception as e:
                if attempt < max_retries - 1 and not (self._is_cancelled or self._is_paused):
                    if self.on_log:
                        self.on_log(f"网络连接中断，第 {attempt + 1} 次尝试自动断点续传: {e}")
                    time.sleep(1.5)
                else:
                    if os.path.exists(tmp_out):
                        try:
                            os.remove(tmp_out)
                        except Exception:
                            pass
                    if self.on_finished:
                        self.on_finished(False, f"下载失败: {e}", "")
                    return

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

    def _download_dual_stream(self, video_url, audio_url, req_headers, save_dir, save_name):
        """音画分离双流下载与 FFmpeg 极速无损合并封装 (针对 B站 等 DASH 音视频分离平台)"""
        clean_name = re.sub(r'[\\/*?:"<>|]', '_', save_name).strip()
        if not clean_name:
            clean_name = f"video_{int(time.time())}"
        if clean_name.lower().endswith(".mp4"):
            clean_name = clean_name[:-4]

        final_mp4 = os.path.join(save_dir, f"{clean_name}.mp4")
        self.output_file = final_mp4

        task_id = self.task_data.get("id") or str(int(time.time() * 1000))
        temp_dir = os.path.join(get_temp_segments_dir(), f"dual_{task_id}")
        os.makedirs(temp_dir, exist_ok=True)
        tmp_video = os.path.join(temp_dir, "video.m4s")
        tmp_audio = os.path.join(temp_dir, "audio.m4s")

        if self.on_log:
            self.on_log(f"[音画合一] 开始多轨双流并发任务: {clean_name}")
            self.on_log(f"[音画合一] 视频轨: {video_url[:80]}...")
            self.on_log(f"[音画合一] 音频轨: {audio_url[:80]}...")

        # 1. 下载视频轨 (0% -> 65%)
        if self.on_log:
            self.on_log("[音画合一] 正在高速下载 1080P/高清独立视频轨...")

        ok_v = self._download_track(video_url, req_headers, tmp_video, 0.0, 65.0, "视频轨")
        if not ok_v or self._is_cancelled or self._is_paused:
            if not (self._is_cancelled or self._is_paused) and self.on_finished:
                self.on_finished(False, "视频轨下载失败", "")
            return

        # 2. 下载音频轨 (65% -> 85%)
        if self.on_log:
            self.on_log("[音画合一] 正在下载高品质独立音频轨...")

        ok_a = self._download_track(audio_url, req_headers, tmp_audio, 65.0, 85.0, "音频轨")
        if not ok_a or self._is_cancelled or self._is_paused:
            if not (self._is_cancelled or self._is_paused) and self.on_finished:
                self.on_finished(False, "音频轨下载失败", "")
            return

        # 3. FFmpeg 无损混流封装 (85% -> 100%)
        ff_exe = get_ffmpeg_path()
        if not ff_exe or not os.path.exists(ff_exe):
            if self.on_finished:
                self.on_finished(False, "未找到 FFmpeg 组件，无法合并音视频", "")
            return

        if self.on_log:
            self.on_log("[音画合一] 音视频双轨已全部就绪，正在调用内置 FFmpeg 进行极速混流封装...")
        if self.on_progress:
            self.on_progress(90.0, "混流封装中", "00:02", 0, 0)

        cmd = [
            ff_exe, "-y",
            "-i", tmp_video,
            "-i", tmp_audio,
            "-c", "copy",
            "-movflags", "+faststart",
            final_mp4
        ]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags, timeout=120)
            if res.returncode == 0 and os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 0:
                try:
                    if os.path.exists(tmp_video): os.remove(tmp_video)
                    if os.path.exists(tmp_audio): os.remove(tmp_audio)
                    if os.path.exists(temp_dir): os.rmdir(temp_dir)
                except Exception:
                    pass

                final_size = os.path.getsize(final_mp4)
                if self.on_log:
                    self.on_log(f"[音画合一] 恭喜！音视频无损合并完成: {os.path.basename(final_mp4)} ({format_size(final_size)})")
                if self.on_progress:
                    self.on_progress(100.0, "完成", "", final_size, final_size)
                if self.on_finished:
                    self.on_finished(True, "下载完成", final_mp4)
            else:
                err_text = res.stderr.decode("utf-8", errors="ignore")[:300]
                if self.on_finished:
                    self.on_finished(False, f"FFmpeg 封装失败: {err_text}", "")
        except Exception as e:
            if self.on_finished:
                self.on_finished(False, f"调用 FFmpeg 异常: {e}", "")

    def _download_track(self, track_url, headers, out_path, prog_start, prog_end, track_name=""):
        """下载单个音视频轨道，支持多线程分块与单流重试"""
        if self._is_cancelled or self._is_paused:
            return False

        content_length = 0
        accept_ranges = False
        try:
            head_resp = self.session.head(track_url, headers=headers, allow_redirects=True, timeout=10)
            if head_resp.status_code < 400:
                content_length = int(head_resp.headers.get("Content-Length", 0))
                accept_ranges = "bytes" in head_resp.headers.get("Accept-Ranges", "").lower()
        except Exception:
            pass

        if content_length <= 0:
            try:
                probe_h = dict(headers)
                probe_h["Range"] = "bytes=0-0"
                with self.session.get(track_url, headers=probe_h, stream=True, timeout=8) as pr:
                    if pr.status_code in (200, 206):
                        accept_ranges = (pr.status_code == 206)
                        cr = pr.headers.get("Content-Range", "")
                        if "/" in cr:
                            tot_s = cr.split("/")[-1].strip()
                            if tot_s.isdigit():
                                content_length = int(tot_s)
                        if content_length <= 0:
                            cl = pr.headers.get("Content-Length", "")
                            if cl.isdigit() and pr.status_code == 200:
                                content_length = int(cl)
            except Exception:
                pass

        thread_num = int(self.task_data.get("thread_count", config.get("max_threads_per_task", 8)))
        if accept_ranges and content_length > 2 * 1024 * 1024 and thread_num > 1:
            return self._download_chunked_track(track_url, headers, out_path, content_length, thread_num, prog_start, prog_end, track_name)
        else:
            return self._download_single_stream_track(track_url, headers, out_path, content_length, prog_start, prog_end, track_name)

    def _download_chunked_track(self, url, headers, out_path, total_size, num_threads, prog_start, prog_end, track_name):
        """多线程分块下载音视频单轨"""
        part_size = total_size // num_threads
        part_ranges = []
        for i in range(num_threads):
            start = i * part_size
            end = total_size - 1 if i == num_threads - 1 else (start + part_size - 1)
            part_ranges.append((start, end))

        part_files = [f"{out_path}.part{i}" for i in range(num_threads)]
        downloaded_bytes = [0] * num_threads
        chunk_errors = []
        lock = threading.Lock()
        last_time = time.time()
        last_downloaded = 0

        def download_chunk(idx, start_byte, end_byte):
            nonlocal last_time, last_downloaded
            part_path = part_files[idx]
            cur_start = start_byte

            if os.path.exists(part_path):
                existing_bytes = os.path.getsize(part_path)
                if 0 < existing_bytes <= (end_byte - start_byte + 1):
                    cur_start = start_byte + existing_bytes
                    with lock:
                        downloaded_bytes[idx] = existing_bytes

            if cur_start > end_byte:
                return

            max_retries = 3
            mode = "ab" if cur_start > start_byte else "wb"
            for attempt in range(max_retries):
                if self._is_cancelled or self._is_paused:
                    return
                try:
                    chunk_headers = dict(headers)
                    chunk_headers["Range"] = f"bytes={cur_start}-{end_byte}"
                    with self.session.get(url, headers=chunk_headers, stream=True, timeout=25) as r:
                        if r.status_code not in (200, 206):
                            r.raise_for_status()
                        with open(part_path, mode) as f:
                            for chunk in r.iter_content(chunk_size=64 * 1024):
                                if self._is_cancelled or self._is_paused:
                                    return
                                if chunk:
                                    f.write(chunk)
                                    cur_start += len(chunk)
                                    with lock:
                                        downloaded_bytes[idx] += len(chunk)
                                        cur_total = sum(downloaded_bytes)
                                        now = time.time()
                                        if now - last_time >= 0.25:
                                            speed = (cur_total - last_downloaded) / (now - last_time)
                                            last_time = now
                                            last_downloaded = cur_total
                                            ratio = cur_total / total_size if total_size > 0 else 0
                                            mapped_pct = prog_start + ratio * (prog_end - prog_start)
                                            spd_str = f"{format_size(speed)}/s"
                                            eta_sec = int((total_size - cur_total) / speed) if speed > 0 else 0
                                            eta_str = f"{eta_sec // 60:02d}:{eta_sec % 60:02d}"
                                            if self.on_progress:
                                                self.on_progress(mapped_pct, spd_str, eta_str, cur_total, total_size)
                    if cur_start > end_byte:
                        return
                except Exception as e:
                    mode = "ab"
                    if attempt < max_retries - 1 and not (self._is_cancelled or self._is_paused):
                        time.sleep(1.0)
                    else:
                        with lock:
                            chunk_errors.append(str(e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            for idx, (s, e) in enumerate(part_ranges):
                executor.submit(download_chunk, idx, s, e)

        if self._is_cancelled or self._is_paused:
            for p in part_files:
                if os.path.exists(p):
                    try: os.remove(p)
                    except Exception: pass
            return False

        if sum(downloaded_bytes) < total_size:
            return False

        with open(out_path, "wb") as out_f:
            for p in part_files:
                if os.path.exists(p):
                    with open(p, "rb") as in_f:
                        while True:
                            buf = in_f.read(1024 * 1024)
                            if not buf: break
                            out_f.write(buf)
                    try: os.remove(p)
                    except Exception: pass
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0

    def _download_single_stream_track(self, url, headers, out_path, total_size, prog_start, prog_end, track_name):
        """单流平滑下载音视频单轨"""
        tmp_out = f"{out_path}.tmp"
        last_time = time.time()
        last_dl = 0
        cur_dl = 0
        max_retries = 3

        for attempt in range(max_retries):
            if self._is_cancelled or self._is_paused:
                break
            try:
                cur_headers = dict(headers)
                mode = "wb"
                if os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0 and attempt > 0:
                    cur_dl = os.path.getsize(tmp_out)
                    cur_headers["Range"] = f"bytes={cur_dl}-"
                    mode = "ab"

                with self.session.get(url, headers=cur_headers, stream=True, timeout=25) as r:
                    if r.status_code not in (200, 206):
                        r.raise_for_status()
                    if total_size <= 0:
                        cl = r.headers.get("Content-Length")
                        if cl and cl.isdigit():
                            total_size = int(cl) + (cur_dl if mode == "ab" else 0)

                    with open(tmp_out, mode) as f:
                        for chunk in r.iter_content(chunk_size=64 * 1024):
                            if self._is_cancelled or self._is_paused:
                                break
                            if chunk:
                                f.write(chunk)
                                cur_dl += len(chunk)
                                now = time.time()
                                if now - last_time >= 0.25:
                                    speed = (cur_dl - last_dl) / (now - last_time)
                                    last_time = now
                                    last_dl = cur_dl
                                    ratio = cur_dl / total_size if total_size > 0 else 0
                                    mapped_pct = prog_start + ratio * (prog_end - prog_start)
                                    spd_str = f"{format_size(speed)}/s"
                                    eta_sec = int((total_size - cur_dl) / speed) if (speed > 0 and total_size > 0) else 0
                                    eta_str = f"{eta_sec // 60:02d}:{eta_sec % 60:02d}"
                                    if self.on_progress:
                                        self.on_progress(mapped_pct, spd_str, eta_str, cur_dl, total_size)
                break
            except Exception as e:
                if attempt < max_retries - 1 and not (self._is_cancelled or self._is_paused):
                    time.sleep(1.0)
                else:
                    if os.path.exists(tmp_out):
                        try: os.remove(tmp_out)
                        except Exception: pass
                    return False

        if self._is_cancelled or self._is_paused:
            if os.path.exists(tmp_out):
                try: os.remove(tmp_out)
                except Exception: pass
            return False

        if os.path.exists(out_path):
            try: os.remove(out_path)
            except Exception: pass
        os.rename(tmp_out, out_path)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
