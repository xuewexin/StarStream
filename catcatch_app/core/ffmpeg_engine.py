"""
CatCatch Downloader - FFmpeg Engine
封装完整的 FFmpeg 多媒体处理能力（格式转换、无损合并、音视频混流、提取音频、无损剪辑、视频修复、媒体探测）
"""
import os
import re
import subprocess
import threading
import sys
from .config import config, ROOT_DIR


def get_ffmpeg_path():
    """获取有效的 ffmpeg 可执行文件路径 (多层动态搜寻与防失效保护)"""
    # 1. 优先检查配置中用户指定的有效绝对路径 (排除易失的 _MEI 临时目录)
    path = config.get("ffmpeg_path", "")
    if path and ("_MEI" not in path) and os.path.isfile(path):
        return os.path.abspath(path)

    # 2. 检查程序所在根目录 (ROOT_DIR, 即 exe 同级目录)
    local_ff = os.path.join(ROOT_DIR, "ffmpeg.exe")
    if os.path.isfile(local_ff):
        return os.path.abspath(local_ff)

    # 3. 检查 PyInstaller 打包内置环境 (_MEIPASS)
    _MEI = getattr(sys, '_MEIPASS', '')
    if _MEI:
        mei_ff = os.path.join(_MEI, "ffmpeg.exe")
        if os.path.isfile(mei_ff):
            return os.path.abspath(mei_ff)

    # 4. 全盘与系统 PATH 搜寻
    from .config import find_executable
    found = find_executable("ffmpeg.exe")
    if found:
        # 只有非临时目录才持久化保存
        if "_MEI" not in found and "AppData\\Local\\Temp" not in found:
            config.set("ffmpeg_path", found)
        return found
    return ""


def is_ffmpeg_available():
    """检测 ffmpeg 是否可用"""
    path = get_ffmpeg_path()
    if not path:
        return False, "未找到 ffmpeg.exe"

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.run(
            [path, "-version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            creationflags=creationflags
        )
        stdout_str = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
        stderr_str = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        out_text = stdout_str or stderr_str

        if proc.returncode == 0 or "ffmpeg version" in out_text.lower():
            first_line = out_text.splitlines()[0] if out_text else "FFmpeg 已就绪"
            return True, first_line
    except Exception as e:
        return False, str(e)
    return False, "FFmpeg 启动异常"


def probe_media_info(file_path):
    """
    使用 ffmpeg -i 解析视频文件的元数据信息
    返回字典: {duration: float, resolution: str, vcodec: str, acodec: str, bitrate: str, fps: str}
    """
    ffmpeg_exe = get_ffmpeg_path()
    info = {
        "duration": 0.0,
        "duration_str": "未知",
        "resolution": "未知",
        "vcodec": "未知",
        "acodec": "未知",
        "bitrate": "未知",
        "fps": "未知",
        "raw": ""
    }
    if not ffmpeg_exe or not os.path.exists(file_path):
        return info

    try:
        proc = subprocess.run(
            [ffmpeg_exe, "-hide_banner", "-i", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10
        )
        output = proc.stderr
        info["raw"] = output

        # 解析时长 Duration: 00:15:32.45, start: 0.000000, bitrate: 2450 kb/s
        dur_match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)", output)
        if dur_match:
            h, m, s = float(dur_match.group(1)), float(dur_match.group(2)), float(dur_match.group(3))
            total_sec = h * 3600 + m * 60 + s
            info["duration"] = total_sec
            info["duration_str"] = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

        # 解析比特率 bitrate: 2450 kb/s
        br_match = re.search(r"bitrate:\s*(\d+\s*kb/s)", output)
        if br_match:
            info["bitrate"] = br_match.group(1)

        # 解析视频流 Stream #0:0: Video: h264 (High), yuv420p, 1920x1080 [SAR 1:1 DAR 16:9], 25 fps
        v_match = re.search(r"Stream.*Video:\s*([a-zA-Z0-9_\(\)]+).*, (\d{3,5}x\d{3,5})", output)
        if v_match:
            info["vcodec"] = v_match.group(1)
            info["resolution"] = v_match.group(2)
        else:
            # 兼容其他流描述
            res_match = re.search(r"(\d{3,5}x\d{3,5})", output)
            if res_match:
                info["resolution"] = res_match.group(1)

        # 解析帧率
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", output)
        if fps_match:
            info["fps"] = fps_match.group(1)

        # 解析音频流 Stream #0:1: Audio: aac (LC), 44100 Hz, stereo, fltp, 128 kb/s
        a_match = re.search(r"Stream.*Audio:\s*([a-zA-Z0-9_\(\)]+)", output)
        if a_match:
            info["acodec"] = a_match.group(1)

    except Exception as e:
        info["raw"] = f"解析异常: {e}"

    return info


class FFmpegTask:
    """运行中的 FFmpeg 异步任务控制类"""
    def __init__(self, cmd, total_duration=0.0, on_progress=None, on_log=None, on_finished=None):
        self.cmd = cmd
        self.total_duration = total_duration
        self.on_progress = on_progress  # cb(percent, speed, out_time_str)
        self.on_log = on_log            # cb(line)
        self.on_finished = on_finished  # cb(success, message)
        self.process = None
        self._is_cancelled = False
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass

    def _run(self):
        ffmpeg_exe = get_ffmpeg_path()
        if not ffmpeg_exe:
            if self.on_finished:
                self.on_finished(False, "未找到 FFmpeg 可执行文件")
            return

        full_cmd = [ffmpeg_exe] + self.cmd
        if self.on_log:
            self.on_log("执行命令: " + " ".join(f'"{c}"' if " " in c else c for c in full_cmd))

        # Windows 下创建子进程时不弹出黑窗口
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self.process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                creationflags=creationflags
            )

            time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)")
            speed_pattern = re.compile(r"speed=\s*([\d\.]+x)")

            for line in iter(self.process.stdout.readline, ""):
                if self._is_cancelled:
                    break
                line = line.strip()
                if not line:
                    continue
                if self.on_log:
                    self.on_log(line)

                # 解析进度
                t_match = time_pattern.search(line)
                if t_match and self.total_duration > 0:
                    h, m, s = float(t_match.group(1)), float(t_match.group(2)), float(t_match.group(3))
                    cur_sec = h * 3600 + m * 60 + s
                    percent = min(100.0, (cur_sec / self.total_duration) * 100.0)
                    
                    sp_match = speed_pattern.search(line)
                    speed_str = sp_match.group(1) if sp_match else ""
                    time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

                    if self.on_progress:
                        self.on_progress(percent, speed_str, time_str)

            self.process.stdout.close()
            ret = self.process.wait()

            if self._is_cancelled:
                if self.on_finished:
                    self.on_finished(False, "任务已手动取消")
            elif ret == 0:
                if self.on_progress:
                    self.on_progress(100.0, "完成", "")
                if self.on_finished:
                    self.on_finished(True, "处理完成")
            else:
                if self.on_finished:
                    self.on_finished(False, f"FFmpeg 退出代码: {ret}")

        except Exception as e:
            if self.on_finished:
                self.on_finished(False, f"运行错误: {e}")


def transcode(input_file, output_file, vcodec="copy", acodec="copy", crf=23, preset="fast", on_progress=None, on_log=None, on_finished=None):
    """万能音视频转码"""
    info = probe_media_info(input_file)
    total_dur = info.get("duration", 0.0)

    cmd = ["-y", "-i", input_file]
    if vcodec == "copy":
        cmd.extend(["-c:v", "copy"])
    else:
        cmd.extend(["-c:v", vcodec, "-crf", str(crf), "-preset", preset])

    if acodec == "copy":
        cmd.extend(["-c:a", "copy"])
    else:
        cmd.extend(["-c:a", acodec])

    cmd.extend(["-movflags", "+faststart", output_file])

    task = FFmpegTask(cmd, total_duration=total_dur, on_progress=on_progress, on_log=on_log, on_finished=on_finished)
    task.start()
    return task


def extract_audio(input_file, output_file, format_name="mp3", bitrate="192k", on_progress=None, on_log=None, on_finished=None):
    """极速提取音频"""
    info = probe_media_info(input_file)
    total_dur = info.get("duration", 0.0)

    cmd = ["-y", "-i", input_file, "-vn"]
    if format_name.lower() == "mp3":
        cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate])
    elif format_name.lower() == "m4a" or format_name.lower() == "aac":
        cmd.extend(["-c:a", "aac", "-b:a", bitrate])
    elif format_name.lower() == "wav":
        cmd.extend(["-c:a", "pcm_s16le"])
    elif format_name.lower() == "flac":
        cmd.extend(["-c:a", "flac"])
    else:
        cmd.extend(["-c:a", "copy"])

    cmd.append(output_file)

    task = FFmpegTask(cmd, total_duration=total_dur, on_progress=on_progress, on_log=on_log, on_finished=on_finished)
    task.start()
    return task


def mux_video_audio(video_file, audio_file, output_file, on_progress=None, on_log=None, on_finished=None):
    """无损音视频混流合成 (视频 + 音频 合并为单文件)"""
    info = probe_media_info(video_file)
    total_dur = info.get("duration", 0.0)

    cmd = [
        "-y",
        "-i", video_file,
        "-i", audio_file,
        "-c:v", "copy",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_file
    ]

    task = FFmpegTask(cmd, total_duration=total_dur, on_progress=on_progress, on_log=on_log, on_finished=on_finished)
    task.start()
    return task


def trim_media(input_file, output_file, start_str, end_or_duration_str, is_duration=False, copy_codec=True, on_progress=None, on_log=None, on_finished=None):
    """无损精准剪辑"""
    cmd = ["-y", "-ss", start_str, "-i", input_file]
    if is_duration:
        cmd.extend(["-t", end_or_duration_str])
    else:
        cmd.extend(["-to", end_or_duration_str])

    if copy_codec:
        cmd.extend(["-c", "copy", "-avoid_negative_ts", "make_zero"])
    else:
        cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-crf", "22"])

    cmd.append(output_file)

    task = FFmpegTask(cmd, total_duration=0.0, on_progress=on_progress, on_log=on_log, on_finished=on_finished)
    task.start()
    return task


def repair_media(input_file, output_file, on_progress=None, on_log=None, on_finished=None):
    """修复损坏或未闭合 moov 头的 MP4 / TS 文件"""
    info = probe_media_info(input_file)
    total_dur = info.get("duration", 0.0)

    cmd = [
        "-y",
        "-err_detect", "ignore_err",
        "-i", input_file,
        "-c", "copy",
        "-movflags", "+faststart",
        output_file
    ]

    task = FFmpegTask(cmd, total_duration=total_dur, on_progress=on_progress, on_log=on_log, on_finished=on_finished)
    task.start()
    return task


def concat_ts_list(file_list_txt, output_file, on_progress=None, on_log=None, on_finished=None):
    """通过 concat 分离器无损合并 ts 分片清单"""
    cmd = [
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", file_list_txt,
        "-c", "copy",
        "-movflags", "+faststart",
        output_file
    ]
    task = FFmpegTask(cmd, total_duration=0.0, on_progress=on_progress, on_log=on_log, on_finished=on_finished)
    task.start()
    return task
