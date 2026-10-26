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

from .config import (
    config, find_nm3u8dl, get_temp_segments_dir,
    is_proxy_alive, detect_local_active_proxies
)
from .download_file import format_size
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
                if os.name == 'nt':
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                else:
                    self.process.terminate()
            except Exception:
                try:
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

        # 确保下载输出目录与分片缓存专用目录均存在
        os.makedirs(save_dir, exist_ok=True)
        temp_segments_dir = get_temp_segments_dir()
        os.makedirs(temp_segments_dir, exist_ok=True)
        self.output_file = os.path.join(save_dir, f"{save_name}.mp4")

        # 代理检测与自适应防断机制
        task_p = (self.task_data.get("proxy") or "").strip()
        if task_p.upper() in ["DIRECT", "NONE"]:
            proxy = ""
        elif task_p.upper() == "GLOBAL" or not task_p:
            proxy = config.get_effective_proxy()
        else:
            proxy = task_p

        if proxy and proxy.lower() not in ["none", "direct"]:
            is_alive, check_msg = is_proxy_alive(proxy)
            if not is_alive:
                if self.on_log:
                    self.on_log(f"[代理探活警告] 配置的代理 ({proxy}) 无法连通 ({check_msg})！正在搜寻本机在线代理...")
                actives = detect_local_active_proxies()
                if actives:
                    proxy = actives[0]["url"]
                    if self.on_log:
                        self.on_log(f"[代理智能切换] 自动切换为活跃本地代理: {proxy} ({actives[0]['name']})")
                else:
                    if self.on_log:
                        self.on_log(f"[代理降级提示] 未发现其它活跃代理，尝试直连下载...")
                    proxy = ""

        cmd = [cli_path, url]

        # 关联 ffmpeg 与准备专用任务分片临时目录
        ffmpeg_exe = get_ffmpeg_path()
        task_id = self.task_data.get("id") or str(int(time.time()))
        task_tmp_dir = os.path.join(temp_segments_dir, f".tmp_{task_id}")
        os.makedirs(task_tmp_dir, exist_ok=True)

        if is_re:
            cmd.extend(["--save-dir", save_dir])
            cmd.extend(["--save-name", save_name])
            # 将分片临时文件收拢存放到专用的单任务独立临时目录，避免根目录被多任务占用竞争
            cmd.extend(["--tmp-dir", task_tmp_dir])
            # 必须始终强制传递 --auto-select，彻底防止非控制台环境下因交互提示而崩溃
            cmd.append("--auto-select")
            cmd.append("--no-ansi-color")
            cmd.extend(["--download-retry-count", "3"])
            cmd.extend(["--http-request-timeout", "15"])

            if not self.task_data.get("del_after_done", config.get("del_tmp_files", True)):
                cmd.extend(["--del-after-done", "false"])

            if ffmpeg_exe:
                cmd.extend(["--ffmpeg-binary-path", ffmpeg_exe])
            
            thread_count = str(self.task_data.get("thread_count", config.get("max_threads_per_task", 16)))
            cmd.extend(["--thread-count", thread_count])

            if config.get("auto_convert_mp4", True):
                cmd.extend(["-M", "format=mp4"])
            
            # 请求头
            headers = self.task_data.get("headers", {})
            for k, v in headers.items():
                if v:
                    cmd.extend(["-H", f"{k}: {v}"])

            if proxy:
                cmd.extend(["--custom-proxy", proxy])
            elif config.get("proxy_mode", "none") == "none" or task_p.upper() in ["DIRECT", "NONE"]:
                cmd.extend(["--use-system-proxy", "false"])

            base_url = self.task_data.get("baseUrl")
            if base_url:
                cmd.extend(["--base-url", base_url])
        else:
            # V3 命令行语法
            cmd.extend(["--workDir", save_dir])
            cmd.extend(["--saveName", save_name])
            cmd.extend(["--tmpDir", task_tmp_dir])
            if self.task_data.get("del_after_done", config.get("del_tmp_files", True)):
                cmd.append("--enableDelAfterDone")
            
            headers = self.task_data.get("headers", {})
            header_strs = [f"{k}:{v}" for k, v in headers.items() if v]
            if header_strs:
                cmd.extend(["--headers", "|".join(header_strs)])

            if proxy:
                cmd.extend(["--proxyAddress", proxy])

        if self.on_log:
            self.on_log(f"启动下载引擎: {'N_m3u8DL-RE' if is_re else 'N_m3u8DL-CLI'}")
            self.on_log(f"分片存储目录: {task_tmp_dir}")
            self.on_log("命令: " + " ".join(f'"{c}"' if " " in c else c for c in cmd))

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            # 注意: 工作目录 cwd 必须设为 save_dir，绝对不能设为 task_tmp_dir 或 temp_segments_dir！
            # 否则 Windows 会锁定当前工作目录句柄，导致下载完成时下载器 SafeDeleteDir 抛出 IOException (being used by another process)
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=save_dir,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                creationflags=creationflags
            )

            ansi_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
            
            # 头部: 匹配已完成分片数/总分片数与进度百分比
            re_head = re.compile(r"(\d+)\s*/\s*(\d+)\s+([\d\.]+)%", re.I)

            # 实时下载速度: 必须包含 /s 或 ps 速率单位，绝不能将纯文件大小 (如 1.60GB) 误识别为速度
            re_spd = re.compile(r"([-\d\.]+\s*(?:[KMGTPkmgtp]?[iI]?[bB](?:/s|ps)|kbps|mbps|gbps|bps))", re.I)

            # 已下载文件大小: 匹配 1.60GB, 1.95GB, 500MB 等纯大小格式，且不带 /s 或 ps
            re_sz = re.compile(r"\b(\d+(?:\.\d+)?\s*(?:[KMGTPkmgtp]?[iI]?B))\b(?!\s*(?:/s|ps))", re.I)

            # 剩余时间: 必须为合法的 HH:MM:SS 或 MM:SS 时间格式
            re_eta = re.compile(r"((?:\d{1,2}:)?\d{1,2}:\d{2}|--:--:--)")

            pct_pattern = re.compile(r"(\d+(?:\.\d+)?)%")
            spd_pattern = re.compile(r"([\d\.]+\s*(?:[KMGTPkmgtp]?[iI]?[bB](?:/s|ps)|kbps|mbps|gbps|bps))", re.I)

            def clean_speed_str(raw):
                if not raw:
                    return ""
                s = raw.lstrip("-").strip()
                m = re.match(r"^([\d\.]+)\s*([KMGkmg]?B)ps$", s, re.I)
                if m:
                    return f"{m.group(1)} {m.group(2).upper()}/s"
                m2 = re.match(r"^([\d\.]+)\s*([KMGkmg]?B)/?s?$", s, re.I)
                if m2:
                    return f"{m2.group(1)} {m2.group(2).upper()}/s"
                return s

            def parse_speed_to_bps(raw):
                if not raw:
                    return 0
                s = raw.lstrip("-").strip()
                # 速度必须强制具有时间分母 (/s 或 ps)
                m = re.match(r"^([\d\.]+)\s*([KMGkmg]?)(?:i?[Bb])(?:/s|ps)$", s, re.I)
                if not m:
                    return 0
                val = float(m.group(1))
                unit = m.group(2).upper()
                factors = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}
                return int(val * factors.get(unit, 1))

            def parse_size_to_bytes(s):
                if not s:
                    return 0
                m = re.match(r"^([\d\.]+)\s*([KMGTkmgt]?i?B)$", s.strip(), re.I)
                if not m:
                    return 0
                val = float(m.group(1))
                unit = m.group(2).upper()
                factors = {
                    "B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4,
                    "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3
                }
                return int(val * factors.get(unit, 1))

            def clean_eta_str(raw):
                if not raw or raw == "--:--:--":
                    return ""
                s = raw.strip()
                if ":" in s:
                    parts = s.split(":")
                    if len(parts) == 2:
                        return f"00:{int(parts[0]):02d}:{int(parts[1]):02d}"
                    elif len(parts) == 3:
                        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
                return ""

            buffer = ""
            recent_lines = []
            last_log_time = 0
            last_logged_pct = -1.0
            last_sample_time = time.time()
            last_disk_bytes = 0
            cur_bytes = 0
            total_est_bytes = 0
            cur_parts = 0
            tot_parts = 0
            percent = 0.0
            smooth_bps = 0.0
            speed_str = ""
            eta_str = ""

            while True:
                if self._is_cancelled:
                    break
                chunk = self.process.stdout.read(64)
                if not chunk:
                    if buffer.strip() and self.on_log:
                        tail_line = ansi_pattern.sub('', buffer).strip()
                        if tail_line:
                            self.on_log(tail_line)
                            recent_lines.append(tail_line)
                    break
                buffer += chunk

                # 关键: 按 \r 和 \n 分割完整行，未收尾的片段留在 buffer 中，绝不发生中途截断
                last_delim = max(buffer.rfind('\r'), buffer.rfind('\n'))
                if last_delim == -1:
                    if len(buffer) > 4096:
                        lines_to_proc = [buffer]
                        buffer = ""
                    else:
                        continue
                else:
                    complete_block = buffer[:last_delim + 1]
                    buffer = buffer[last_delim + 1:]
                    lines_to_proc = re.split(r'[\r\n]+', complete_block)

                for raw_line in lines_to_proc:
                    line = ansi_pattern.sub('', raw_line).strip()
                    if not line:
                        continue

                    # 优先检测是否为分片进度行
                    m_head = re_head.search(line)
                    if m_head:
                        cur_parts = int(m_head.group(1))
                        tot_parts = int(m_head.group(2))
                        percent = float(m_head.group(3))
                        tail = line[m_head.end():]

                        m_sz = re_sz.search(tail)
                        m_spd = re_spd.search(tail)
                        m_eta = re_eta.search(tail)

                        raw_sz = (m_sz.group(1) or "").strip() if m_sz else ""
                        raw_sp = (m_spd.group(1) or "").strip() if m_spd else ""
                        raw_eta = (m_eta.group(1) or "").strip() if m_eta else ""

                        # 1. 解析已下载文件大小 (如 1.60GB)，绝不误判为速度
                        if raw_sz:
                            sz_val = parse_size_to_bytes(raw_sz)
                            if sz_val > 0:
                                cur_bytes = max(cur_bytes, sz_val)

                        # 2. 解析下载器上报的真实瞬时速度 (必须带 /s 或 ps)
                        re_bps = parse_speed_to_bps(raw_sp)
                        if re_bps > 1024:
                            if smooth_bps <= 0:
                                smooth_bps = float(re_bps)
                            else:
                                smooth_bps = 0.5 * re_bps + 0.5 * smooth_bps

                        # 3. 采样物理分片缓存目录，获取真实落盘字节并计算精准平滑实测网速
                        now = time.time()
                        dt = now - last_sample_time
                        if dt >= 0.8:
                            disk_sz = 0
                            try:
                                if os.path.exists(task_tmp_dir):
                                    with os.scandir(task_tmp_dir) as entries:
                                        disk_sz = sum(e.stat().st_size for e in entries if e.is_file())
                            except Exception:
                                pass

                            if disk_sz > 0:
                                cur_bytes = max(cur_bytes, disk_sz)

                            if last_disk_bytes > 0 and cur_bytes >= last_disk_bytes and dt > 0:
                                disk_bps = (cur_bytes - last_disk_bytes) / dt
                                if disk_bps > 1024:
                                    if smooth_bps <= 0:
                                        smooth_bps = disk_bps
                                    else:
                                        smooth_bps = 0.6 * disk_bps + 0.4 * smooth_bps

                            last_disk_bytes = cur_bytes
                            last_sample_time = now

                        # 4. 格式化最终展示的速度
                        if smooth_bps > 1024:
                            speed_str = f"{format_size(smooth_bps)}/s"
                        elif raw_sp:
                            speed_str = clean_speed_str(raw_sp)
                        else:
                            speed_str = "0.00 B/s"

                        # 5. 估算总大小
                        if cur_bytes > 0:
                            if tot_parts > 0 and cur_parts > 0:
                                total_est_bytes = int((cur_bytes / cur_parts) * tot_parts)
                            elif percent > 0:
                                total_est_bytes = int(cur_bytes / (percent / 100.0))

                        # 6. 动态平滑计算剩余时间，避免原生下载器单片波动导致的忽长忽短
                        if smooth_bps > 1024 and total_est_bytes > cur_bytes:
                            rem_bytes = total_est_bytes - cur_bytes
                            rem_sec = int(rem_bytes / smooth_bps)
                            if 0 <= rem_sec < 86400 * 7:
                                eta_str = f"{rem_sec // 3600:02d}:{(rem_sec % 3600) // 60:02d}:{rem_sec % 60:02d}"
                            else:
                                eta_str = clean_eta_str(raw_eta)
                        else:
                            eta_str = clean_eta_str(raw_eta)

                        if self.on_progress:
                            self.on_progress(percent, speed_str, eta_str, cur_bytes, total_est_bytes, cur_parts, tot_parts)

                        # 定时同步进度日志到日志面板（每隔 2.5 秒或进度前进），防止用户误以为卡死
                        if now - last_log_time >= 2.5 or (percent - last_logged_pct >= 5.0 and percent > 0):
                            last_log_time = now
                            last_logged_pct = percent
                            sp_disp = f" | 速度: {speed_str}" if speed_str else ""
                            eta_disp = f" | 剩余: {eta_str}" if eta_str else ""
                            sz_disp = f" | 已下: {format_size(cur_bytes)}" if cur_bytes > 0 else ""
                            p_line = f"[下载中] 已完成分片: {cur_parts}/{tot_parts} ({percent:.1f}%){sz_disp}{sp_disp}{eta_disp}"
                            recent_lines.append(p_line)
                            if len(recent_lines) > 100:
                                recent_lines.pop(0)
                            if self.on_log:
                                self.on_log(p_line)
                    else:
                        # 其它常规输出行（如初始化探测、流选择、转码、提示等）
                        recent_lines.append(line)
                        if len(recent_lines) > 100:
                            recent_lines.pop(0)
                        if self.on_log:
                            self.on_log(line)

                        pct_match = pct_pattern.search(line)
                        spd_match = spd_pattern.search(line)
                        if (pct_match or spd_match) and self.on_progress:
                            pct_val = float(pct_match.group(1)) if pct_match else 0.0
                            spd_val = clean_speed_str(spd_match.group(1)) if spd_match else ""
                            self.on_progress(pct_val, spd_val, "", cur_bytes, total_est_bytes, cur_parts, tot_parts)

            self.process.stdout.close()
            ret = self.process.wait()

            if self._is_cancelled:
                if self.on_finished:
                    self.on_finished(False, "任务已手动取消", "")
                return

            # 检测是否成功生成最终媒体文件
            actual_output = self._find_downloaded_file(save_dir, save_name)
            has_valid_output = actual_output and os.path.exists(actual_output) and os.path.getsize(actual_output) > 1024 * 1024

            if ret == 0 or has_valid_output:
                # 自动转封装为标准 MP4 (带 faststart 网页秒播)
                if config.get("auto_convert_mp4", True) and not actual_output.lower().endswith(".mp4") and os.path.exists(actual_output):
                    mp4_path = os.path.splitext(actual_output)[0] + ".mp4"
                    if self.on_log:
                        self.on_log("检测到非 MP4 容器，正在自动调用内置 FFmpeg 转封装为标准 MP4...")
                    try:
                        ff_exe = get_ffmpeg_path()
                        if ff_exe:
                            cmd_mux = [ff_exe, "-y", "-i", actual_output, "-c", "copy", "-movflags", "+faststart", mp4_path]
                            subprocess.run(cmd_mux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags, timeout=120)
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

                if ret != 0 and self.on_log:
                    self.on_log(f"[自动容错修复] 下载器进程退出码为 {ret} (清理分片目录时可能遇文件句柄竞争)，但已成功获取完整合并媒体文件: {actual_output}")

                # 清理单任务临时分片目录
                if os.path.exists(task_tmp_dir):
                    try:
                        shutil.rmtree(task_tmp_dir, ignore_errors=True)
                    except Exception:
                        pass

                if self.on_progress:
                    self.on_progress(100.0, "完成", "", 0, 0)
                if self.on_finished:
                    self.on_finished(True, "下载并合并成功", actual_output)
            else:
                err_summary = f"下载器退出代码异常: {ret}"
                warn_lines = [l for l in recent_lines if any(k in l for k in ["WARN", "ERROR", "FAIL", "403", "404", "401", "Exception"])]
                if warn_lines:
                    err_summary += f" ({warn_lines[-1]})"
                if self.on_finished:
                    self.on_finished(False, err_summary, "")

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

        temp_segments_dir = get_temp_segments_dir()
        tmp_dir = os.path.join(temp_segments_dir, f".tmp_{save_name}_{int(time.time())}")
        os.makedirs(tmp_dir, exist_ok=True)

        proxy = self.task_data.get("proxy") or config.get_effective_proxy()
        if proxy and proxy not in ["none", "direct"]:
            is_alive, check_msg = is_proxy_alive(proxy)
            if not is_alive:
                actives = detect_local_active_proxies()
                proxy = actives[0]["url"] if actives else None
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
