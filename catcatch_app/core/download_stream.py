"""
CatCatch Downloader - Stream Download Engine (M3U8 / DASH / Live)
支持 N_m3u8DL-RE / N_m3u8DL-CLI v3 调度与实时输出捕获，附带纯 Python 并发流媒体下载降级引擎
"""
import os
import re
import sys
import time
import shutil
import subprocess
import threading
from urllib.parse import urljoin, urlparse
import requests

from .config import config, find_nm3u8dl
from .ffmpeg_engine import get_ffmpeg_path, concat_ts_list


def get_requests_session(proxy=None):
    s = requests.Session()
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    else:
        s.trust_env = False
    return s


class StreamDownloadTask:
    def __init__(self, task_data, on_progress=None, on_log=None, on_finished=None):
        self.task_data = task_data
        self.on_progress = on_progress  # cb(percent, speed_str, eta_str, downloaded_bytes, total_bytes)
        self.on_log = on_log            # cb(line)
        self.on_finished = on_finished  # cb(success, message, output_file)
        
        self.process = None
        self._is_cancelled = False
        self._thread = None
        self.output_file = ""

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.terminate()
                time.sleep(0.3)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass

    def _run(self):
        # 优先使用 N_m3u8DL-RE
        engine_type = self.task_data.get("engine", config.get("stream_engine", "RE"))
        re_path = config.get("re_cli_path", "")
        v3_path = config.get("v3_cli_path", "")

        used_cli = ""
        if engine_type == "RE" and re_path and os.path.exists(re_path):
            used_cli = re_path
        elif engine_type == "V3" and v3_path and os.path.exists(v3_path):
            used_cli = v3_path
        elif re_path and os.path.exists(re_path):
            used_cli = re_path
        elif v3_path and os.path.exists(v3_path):
            used_cli = v3_path
        
        # 若此前记录失效，实时动态搜寻全盘与常用路径
        if not used_cli:
            found_exe, found_type = find_nm3u8dl(prefer="RE" if engine_type == "RE" else "V3")
            if found_exe and os.path.exists(found_exe):
                used_cli = found_exe
                if found_type == "RE":
                    config.set("re_cli_path", found_exe)
                else:
                    config.set("v3_cli_path", found_exe)

        if used_cli:
            self._run_cli(used_cli)
        else:
            if self.on_log:
                self.on_log("[提示] 未找到 N_m3u8DL 外部命令行工具，启动内置 Python M3U8 流媒体引擎...")
            self._run_internal_python()

    def _run_cli(self, cli_path):
        is_re = "RE" in os.path.basename(cli_path).upper()
        save_dir = self.task_data.get("save_dir") or config.get("save_dir")
        save_name = self.task_data.get("save_name") or "video"
        # 过滤非法字符
        save_name = re.sub(r'[\\/*?:"<>|]', '_', save_name).strip()
        url = self.task_data.get("url")

        os.makedirs(save_dir, exist_ok=True)
        self.output_file = os.path.join(save_dir, f"{save_name}.mp4")

        cmd = [cli_path, url]

        # 关联 ffmpeg
        ffmpeg_exe = get_ffmpeg_path()
        if is_re:
            cmd.extend(["--save-dir", save_dir])
            cmd.extend(["--save-name", save_name])
            if ffmpeg_exe:
                cmd.extend(["--ffmpeg-binary-path", ffmpeg_exe])
            
            thread_count = str(self.task_data.get("thread_count", config.get("max_threads_per_task", 16)))
            cmd.extend(["--thread-count", thread_count])

            if config.get("auto_convert_mp4", True):
                cmd.extend(["-M", "format=mp4"])

            if self.task_data.get("del_after_done", config.get("del_tmp_files", True)):
                cmd.append("--auto-select")
            
            # 请求头
            headers = self.task_data.get("headers", {})
            for k, v in headers.items():
                if v:
                    cmd.extend(["-H", f"{k}: {v}"])

            proxy = self.task_data.get("proxy") or config.get_effective_proxy()
            if proxy:
                cmd.extend(["--custom-proxy", proxy])
            elif config.get("proxy_mode", "none") == "none":
                cmd.extend(["--use-system-proxy", "false"])

            base_url = self.task_data.get("baseUrl")
            if base_url:
                cmd.extend(["--base-url", base_url])
        else:
            # V3 命令行语法
            cmd.extend(["--workDir", save_dir])
            cmd.extend(["--saveName", save_name])
            if self.task_data.get("del_after_done", config.get("del_tmp_files", True)):
                cmd.append("--enableDelAfterDone")
            
            headers = self.task_data.get("headers", {})
            header_strs = [f"{k}:{v}" for k, v in headers.items() if v]
            if header_strs:
                cmd.extend(["--headers", "|".join(header_strs)])

            proxy = self.task_data.get("proxy") or config.get_effective_proxy()
            if proxy:
                cmd.extend(["--proxyAddress", proxy])

        if self.on_log:
            self.on_log(f"启动下载引擎: {'N_m3u8DL-RE' if is_re else 'N_m3u8DL-CLI'}")
            self.on_log("命令: " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                creationflags=creationflags
            )

            # 正则匹配连续输出进度（适配 N_m3u8DL-RE 重定向无换行与 V3 换行模式）
            re_progress = re.compile(r"(\d+)/(\d+)\s+([\d\.]+)%\s+([-\d\.]+\s*[a-zA-Z/]+)\s+([0-9:]+|--:--:--)", re.I)
            pct_pattern = re.compile(r"(\d+(?:\.\d+)?)%")
            spd_pattern = re.compile(r"([\d\.]+\s*(?:KB|MB|GB|B|kbps|mbps|gbps|Bps|KBps|MBps|GBps)/s?)", re.I)

            def clean_speed_str(raw):
                s = raw.lstrip("-").strip()
                m = re.match(r"^([\d\.]+)\s*([KMGkmg]?B)ps$", s, re.I)
                if m:
                    return f"{m.group(1)} {m.group(2).upper()}/s"
                m2 = re.match(r"^([\d\.]+)\s*([KMGkmg]?B)/s$", s, re.I)
                if m2:
                    return f"{m2.group(1)} {m2.group(2).upper()}/s"
                return s

            buffer = ""
            while True:
                if self._is_cancelled:
                    break
                chunk = self.process.stdout.read(32)
                if not chunk:
                    if buffer.strip() and self.on_log:
                        self.on_log(buffer.strip())
                    break
                buffer += chunk

                # 优先匹配 RE 连续流输出进度
                matched_progress = False
                matches = list(re_progress.finditer(buffer))
                if matches:
                    matched_progress = True
                    last_m = matches[-1]
                    cur_parts = int(last_m.group(1))
                    tot_parts = int(last_m.group(2))
                    percent = float(last_m.group(3))
                    speed_str = clean_speed_str(last_m.group(4))
                    eta_str = last_m.group(5)
                    if eta_str == "--:--:--":
                        eta_str = ""

                    if self.on_progress:
                        self.on_progress(percent, speed_str, eta_str, cur_parts, tot_parts)

                    # 截断已处理的数据
                    buffer = buffer[last_m.end():]

                # 处理常规换行日志（启动探测、流选择等信息）
                while '\r' in buffer or '\n' in buffer:
                    idx_r = buffer.find('\r')
                    idx_n = buffer.find('\n')
                    if idx_r != -1 and (idx_n == -1 or idx_r < idx_n):
                        line = buffer[:idx_r]
                        buffer = buffer[idx_r + 1:]
                    else:
                        line = buffer[:idx_n]
                        buffer = buffer[idx_n + 1:]

                    line = line.strip()
                    if not line:
                        continue
                    if self.on_log:
                        self.on_log(line)

                    if not matched_progress:
                        pct_match = pct_pattern.search(line)
                        spd_match = spd_pattern.search(line)
                        if (pct_match or spd_match) and self.on_progress:
                            pct_val = float(pct_match.group(1)) if pct_match else 0.0
                            spd_val = clean_speed_str(spd_match.group(1)) if spd_match else ""
                            self.on_progress(pct_val, spd_val, "", 0, 0)

                if len(buffer) > 2048:
                    buffer = buffer[-512:]

            self.process.stdout.close()
            ret = self.process.wait()

            if self._is_cancelled:
                if self.on_finished:
                    self.on_finished(False, "任务已手动取消", "")
                return

            if ret == 0:
                # 寻找最终生成的输出文件（可能是 mp4, mkv, ts）
                actual_output = self._find_downloaded_file(save_dir, save_name)

                # 自动转封装为标准 MP4 (带 faststart 网页秒播)
                if config.get("auto_convert_mp4", True) and not actual_output.lower().endswith(".mp4") and os.path.exists(actual_output):
                    mp4_path = os.path.splitext(actual_output)[0] + ".mp4"
                    if self.on_log:
                        self.on_log("检测到非 MP4 容器，正在自动调用内置 FFmpeg 转封装为标准 MP4...")
                    try:
                        ff_exe = get_ffmpeg_path()
                        if ff_exe:
                            cmd_mux = [ff_exe, "-y", "-i", actual_output, "-c", "copy", "-movflags", "+faststart", mp4_path]
                            subprocess.run(cmd_mux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags, timeout=60)
                            if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                                if config.get("del_tmp_files", True):
                                    try:
                                        os.remove(actual_output)
                                    except Exception:
                                        pass
                                actual_output = mp4_path
                    except Exception as e:
                        if self.on_log:
                            self.on_log(f"自动转 MP4 提示: {e}")

                if self.on_progress:
                    self.on_progress(100.0, "完成", "", 0, 0)
                if self.on_finished:
                    self.on_finished(True, "下载并合并成功", actual_output)
            else:
                if self.on_finished:
                    self.on_finished(False, f"下载器退出代码异常: {ret}", "")

        except Exception as e:
            if self.on_finished:
                self.on_finished(False, f"下载执行失败: {e}", "")

    def _find_downloaded_file(self, save_dir, save_name):
        """匹配下载生成的视频文件"""
        for ext in [".mp4", ".mkv", ".ts", ".flv"]:
            candidate = os.path.join(save_dir, f"{save_name}{ext}")
            if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                return candidate
        # 查找包含 save_name 开头的文件
        try:
            for fname in os.listdir(save_dir):
                if fname.startswith(save_name):
                    full_p = os.path.join(save_dir, fname)
                    if os.path.isfile(full_p) and os.path.getsize(full_p) > 0:
                        return full_p
        except Exception:
            pass
        return os.path.join(save_dir, f"{save_name}.mp4")

    def _run_internal_python(self):
        """内置纯 Python M3U8 下载备用流程"""
        save_dir = self.task_data.get("save_dir") or config.get("save_dir")
        save_name = self.task_data.get("save_name") or "video"
        save_name = re.sub(r'[\\/*?:"<>|]', '_', save_name).strip()
        url = self.task_data.get("url")

        headers = self.task_data.get("headers", {})
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req_headers.update({k: v for k, v in headers.items() if v})

        tmp_dir = os.path.join(save_dir, f".tmp_{save_name}_{int(time.time())}")
        os.makedirs(tmp_dir, exist_ok=True)

        proxy = self.task_data.get("proxy") or config.get_effective_proxy()
        session = get_requests_session(proxy)

        try:
            if self.on_log:
                self.on_log(f"正在拉取 M3U8 清单: {url}")
            resp = session.get(url, headers=req_headers, timeout=15)
            if resp.status_code != 200:
                raise Exception(f"请求 M3U8 失败: HTTP {resp.status_code}")

            lines = resp.text.strip().splitlines()
            ts_urls = []
            base_url = self.task_data.get("baseUrl") or url

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                full_ts_url = urljoin(base_url, line)
                ts_urls.append(full_ts_url)

            if not ts_urls:
                raise Exception("未从 M3U8 中解析到任何分片 TS 地址")

            total_segments = len(ts_urls)
            if self.on_log:
                self.on_log(f"解析到 {total_segments} 个 TS 分片，开始多线程下载...")

            downloaded_count = 0
            ts_files = []
            lock = threading.Lock()

            def download_one(idx, ts_url):
                nonlocal downloaded_count
                if self._is_cancelled:
                    return
                ts_filename = os.path.join(tmp_dir, f"segment_{idx:05d}.ts")
                for retry in range(3):
                    try:
                        r = session.get(ts_url, headers=req_headers, timeout=15)
                        if r.status_code == 200:
                            with open(ts_filename, "wb") as f:
                                f.write(r.content)
                            with lock:
                                downloaded_count += 1
                                ts_files.append((idx, ts_filename))
                                pct = (downloaded_count / total_segments) * 95.0
                                if self.on_progress:
                                    self.on_progress(pct, "", "", downloaded_count, total_segments)
                            return
                    except Exception:
                        time.sleep(1)

            from concurrent.futures import ThreadPoolExecutor
            threads = int(self.task_data.get("thread_count", 16))
            with ThreadPoolExecutor(max_workers=threads) as executor:
                for idx, t_url in enumerate(ts_urls):
                    executor.submit(download_one, idx, t_url)

            if self._is_cancelled:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                if self.on_finished:
                    self.on_finished(False, "任务已手动取消", "")
                return

            # 按序号排序
            ts_files.sort(key=lambda x: x[0])
            file_list_txt = os.path.join(tmp_dir, "concat_list.txt")
            with open(file_list_txt, "w", encoding="utf-8") as f:
                for _, p in ts_files:
                    f.write(f"file '{p.replace('\\', '/')}'\n")

            out_mp4 = os.path.join(save_dir, f"{save_name}.mp4")
            if self.on_log:
                self.on_log("正在调用 FFmpeg 进行无损合并...")

            def finish_concat(success, msg):
                shutil.rmtree(tmp_dir, ignore_errors=True)
                if success:
                    if self.on_progress:
                        self.on_progress(100.0, "完成", "", total_segments, total_segments)
                    if self.on_finished:
                        self.on_finished(True, "内置引擎合并成功", out_mp4)
                else:
                    if self.on_finished:
                        self.on_finished(False, f"FFmpeg 合并失败: {msg}", "")

            concat_ts_list(file_list_txt, out_mp4, on_finished=finish_concat)

        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            if self.on_finished:
                self.on_finished(False, f"内置下载器异常: {e}", "")
