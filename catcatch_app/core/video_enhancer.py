"""
CatCatch Downloader - Video Quality Enhancer & Local AI Upscaler
支持两种完全免费、本地离线、无次数限制的视频高清增强方案：
1. 极速清晰增强 (OpenCV 双边去噪 + Lanczos4 超采放大 + 自适应锐化 + FFmpeg 无损音轨回封)
2. 本地 AI 超分 (Real-ESRGAN ncnn-vulkan 开源本地 GPU 引擎，支持一键按需下载，离线无限次使用)
"""
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
import requests

from .config import config, ROOT_DIR, find_executable, get_temp_segments_dir
from .ffmpeg_engine import get_ffmpeg_path, probe_media_info

REALESRGAN_URLS = [
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
    "https://ghproxy.net/https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
]


def get_realesrgan_dir() -> str:
    return os.path.join(ROOT_DIR, "tools", "realesrgan")


def find_realesrgan_path() -> str:
    cfg_p = (config.get("realesrgan_path", "") or "").strip()
    if cfg_p and os.path.isfile(cfg_p):
        return os.path.abspath(cfg_p)

    local_tool = os.path.join(get_realesrgan_dir(), "realesrgan-ncnn-vulkan.exe")
    if os.path.isfile(local_tool):
        return os.path.abspath(local_tool)

    found = find_executable("realesrgan-ncnn-vulkan.exe")
    if found:
        return found
    return ""


def download_realesrgan_engine(on_progress=None, on_finished=None):
    """后台下载并解压开源 Real-ESRGAN ncnn-vulkan Windows 独立包 (完全免费开源)"""
    def _worker():
        dest_dir = get_realesrgan_dir()
        os.makedirs(dest_dir, exist_ok=True)
        zip_path = os.path.join(dest_dir, "realesrgan_pkg.zip")
        proxy = config.get_effective_proxy(validate=True)
        proxies = {"http": proxy, "https": proxy} if (proxy and proxy != "direct") else None

        last_err = "下载失败"
        ok = False
        for url in REALESRGAN_URLS:
            try:
                if on_progress:
                    on_progress(5.0, f"正在连接开源镜像...")
                with requests.get(url, stream=True, proxies=proxies, timeout=25) as r:
                    if r.status_code != 200:
                        last_err = f"HTTP {r.status_code}"
                        continue
                    total = int(r.headers.get("Content-Length", 0) or 0)
                    done = 0
                    with open(zip_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=131072):
                            if not chunk:
                                continue
                            f.write(chunk)
                            done += len(chunk)
                            if total > 0 and on_progress:
                                pct = min(88.0, (done / total) * 88.0)
                                on_progress(pct, f"正在下载 AI 超分引擎 ({done // (1024*1024)}MB/{total // (1024*1024)}MB)...")
                ok = True
                break
            except Exception as e:
                last_err = str(e)
                continue

        if not ok or not os.path.exists(zip_path):
            if on_finished:
                on_finished(False, f"引擎下载失败: {last_err}")
            return

        try:
            if on_progress:
                on_progress(92.0, "正在解压模型与 Vulkan 引擎...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(dest_dir)
            try:
                os.remove(zip_path)
            except Exception:
                pass
            exe_path = find_realesrgan_path()
            if exe_path:
                config.set("realesrgan_path", exe_path)
                if on_progress:
                    on_progress(100.0, "就绪")
                if on_finished:
                    on_finished(True, exe_path)
            else:
                if on_finished:
                    on_finished(False, "解压完成但未找到 realesrgan-ncnn-vulkan.exe")
        except Exception as e:
            if on_finished:
                on_finished(False, f"解压失败: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


class VideoEnhanceTask(threading.Thread):
    """兼容 FFmpegToolboxDialog 的异步画质增强任务对象 (.cancel())"""
    def __init__(self, target_fn):
        super().__init__(daemon=True)
        self._target_fn = target_fn
        self._cancelled = False
        self.process = None

    def cancel(self):
        self._cancelled = True
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self):
        self._target_fn(self)


def _mux_video_with_original_audio(video_only_path: str, orig_path: str, final_output_path: str):
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        shutil.copy2(video_only_path, final_output_path)
        return True, "完成 (未找到 FFmpeg，输出纯视频)"

    os.makedirs(os.path.dirname(os.path.abspath(final_output_path)), exist_ok=True)
    cmd = [
        ffmpeg_exe, "-y",
        "-i", video_only_path,
        "-i", orig_path,
        "-map", "0:v:0",
        "-map", "1:a?",
        "-c", "copy",
        "-movflags", "+faststart",
        final_output_path
    ]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore", creationflags=flags)
    if proc.returncode == 0 and os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 0:
        return True, "画质增强并回封音轨完成"
    return False, f"FFmpeg 回封失败 (exit={proc.returncode})"


def enhance_video_fast(
    input_file: str,
    output_file: str,
    scale: int = 2,
    denoise: bool = True,
    sharpen: bool = True,
    on_progress=None,
    on_log=None,
    on_finished=None
):
    """极速清晰增强：双边去噪 + Lanczos4 超采放大 + 自适应边缘锐化"""
    def _worker(task_obj: VideoEnhanceTask):
        tmp_video = os.path.join(get_temp_segments_dir(), f".enh_fast_{int(time.time()*1000)}.mp4")
        os.makedirs(os.path.dirname(tmp_video), exist_ok=True)
        try:
            import cv2
            cap = cv2.VideoCapture(input_file)
            if not cap.isOpened():
                if on_finished:
                    on_finished(False, "无法读取视频文件")
                return

            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            if fps <= 0 or fps > 120:
                fps = 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if w <= 0 or h <= 0:
                cap.release()
                if on_finished:
                    on_finished(False, "无法获取视频分辨率")
                return

            sc = 2 if scale <= 2 else 4
            # 封顶 3840 防止 4x 超出普通编码限制
            if max(w, h) * sc > 3840:
                out_w = int(w * (3840.0 / max(w, h)))
                out_h = int(h * (3840.0 / max(w, h)))
            else:
                out_w, out_h = w * sc, h * sc
            out_w = out_w - (out_w % 2)
            out_h = out_h - (out_h % 2)

            if on_log:
                on_log(f"[极速清晰增强] {w}x{h} -> {out_w}x{out_h} @ {fps:.2f}fps (共 {total_frames} 帧)")

            writer = cv2.VideoWriter(tmp_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h))
            idx = 0
            t0 = time.time()
            while not task_obj.is_cancelled():
                ok, frame = cap.read()
                if not ok:
                    break
                if denoise:
                    frame = cv2.bilateralFilter(frame, 5, 35, 35)
                up = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)
                if sharpen:
                    blur = cv2.GaussianBlur(up, (0, 0), 1.1)
                    up = cv2.addWeighted(up, 1.32, blur, -0.32, 0)
                writer.write(up)
                idx += 1
                if idx % 15 == 0 and on_progress and total_frames > 0:
                    pct = min(92.0, (idx / total_frames) * 92.0)
                    elapsed = max(0.1, time.time() - t0)
                    fps_spd = idx / elapsed
                    eta_s = int((total_frames - idx) / max(0.1, fps_spd))
                    on_progress(pct, f"{fps_spd:.1f} fps", f"{eta_s}s")

            cap.release()
            writer.release()

            if task_obj.is_cancelled():
                if on_finished:
                    on_finished(False, "任务已手动取消")
                return

            if on_progress:
                on_progress(95.0, "音轨封装", "2s")
            if on_log:
                on_log("[FFmpeg] 正在无损合并原始音频轨道...")
            ok, msg = _mux_video_with_original_audio(tmp_video, input_file, output_file)
            if ok and on_progress:
                on_progress(100.0, "完成", "")
            if on_finished:
                on_finished(ok, msg)
        except Exception as e:
            if on_finished:
                on_finished(False, f"画质增强异常: {e}")
        finally:
            try:
                if os.path.exists(tmp_video):
                    os.remove(tmp_video)
            except Exception:
                pass

    task = VideoEnhanceTask(_worker)
    task.start()
    return task


def enhance_video_ai(
    input_file: str,
    output_file: str,
    scale: int = 2,
    model: str = "realesr-animevideov3",
    on_progress=None,
    on_log=None,
    on_finished=None
):
    """本地免费 AI 超分 (基于开源 Real-ESRGAN ncnn-vulkan 引擎)"""
    def _worker(task_obj: VideoEnhanceTask):
        exe_path = find_realesrgan_path()
        if not exe_path:
            if on_finished:
                on_finished(False, "尚未安装 Real-ESRGAN 开源引擎，请先点击「免费下载 AI 引擎」")
            return

        work_dir = os.path.join(get_temp_segments_dir(), f".enh_ai_{int(time.time()*1000)}")
        in_dir = os.path.join(work_dir, "in")
        out_dir = os.path.join(work_dir, "out")
        tmp_video = os.path.join(work_dir, "upscaled_video.mp4")
        os.makedirs(in_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        try:
            import cv2
            cap = cv2.VideoCapture(input_file)
            if not cap.isOpened():
                if on_finished:
                    on_finished(False, "无法打开输入视频")
                return
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            if fps <= 0 or fps > 120:
                fps = 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

            if on_log:
                on_log(f"[AI超分] 正在抽取视频帧 ({w}x{h}, {total_frames} 帧)...")

            frame_idx = 0
            while not task_obj.is_cancelled():
                ok, frame = cap.read()
                if not ok:
                    break
                frame_idx += 1
                cv2.imwrite(os.path.join(in_dir, f"f_{frame_idx:06d}.png"), frame)
                if frame_idx % 20 == 0 and on_progress and total_frames > 0:
                    on_progress(min(20.0, (frame_idx / total_frames) * 20.0), "抽帧中", "")
            cap.release()

            if task_obj.is_cancelled() or frame_idx == 0:
                if on_finished:
                    on_finished(False, "任务已取消" if task_obj.is_cancelled() else "未能提取视频帧")
                return

            sc = 2 if scale <= 2 else 4
            if model != "realesr-animevideov3" and sc != 4:
                # realesrgan-x4plus 仅支持 4x
                sc = 4
            if on_log:
                on_log(f"[Real-ESRGAN] 启动本地 Vulkan GPU AI 超分 (模型={model}, 放大={sc}x)...")

            cmd = [
                exe_path,
                "-i", in_dir,
                "-o", out_dir,
                "-n", model,
                "-s", str(sc),
                "-f", "png",
            ]
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            proc = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(exe_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=flags
            )
            task_obj.process = proc

            # 同时轮询输出帧数量显示真实进度
            while proc.poll() is None:
                if task_obj.is_cancelled():
                    proc.terminate()
                    if on_finished:
                        on_finished(False, "任务已手动取消")
                    return
                try:
                    done_cnt = len(os.listdir(out_dir))
                    if on_progress:
                        pct = 20.0 + min(65.0, (done_cnt / max(1, frame_idx)) * 65.0)
                        on_progress(pct, f"AI超分 {done_cnt}/{frame_idx}", "")
                except Exception:
                    pass
                time.sleep(0.5)

            out_files = sorted(f for f in os.listdir(out_dir) if f.endswith(".png"))
            if not out_files:
                err_txt = proc.stdout.read() if proc.stdout else ""
                if on_finished:
                    on_finished(False, f"Real-ESRGAN 执行失败 (请检查显卡是否支持 Vulkan): {err_txt[:180]}")
                return

            first_img = cv2.imread(os.path.join(out_dir, out_files[0]))
            uh, uw = first_img.shape[:2]
            if on_log:
                on_log(f"[AI超分] 正在合成超清视频 ({uw}x{uh} @ {fps:.2f}fps) 并回封原音轨...")

            writer = cv2.VideoWriter(tmp_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (uw, uh))
            for i, fn in enumerate(out_files):
                if task_obj.is_cancelled():
                    writer.release()
                    if on_finished:
                        on_finished(False, "任务已手动取消")
                    return
                img = cv2.imread(os.path.join(out_dir, fn))
                if img is not None:
                    writer.write(img)
                if i % 20 == 0 and on_progress:
                    on_progress(85.0 + min(10.0, (i / max(1, len(out_files))) * 10.0), "视频合成", "")
            writer.release()

            ok, msg = _mux_video_with_original_audio(tmp_video, input_file, output_file)
            if ok and on_progress:
                on_progress(100.0, "完成", "")
            if on_finished:
                on_finished(ok, msg)
        except Exception as e:
            if on_finished:
                on_finished(False, f"AI 超分异常: {e}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    task = VideoEnhanceTask(_worker)
    task.start()
    return task
