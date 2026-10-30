"""
CatCatch Downloader - Live Preview & Play While Downloading Engine
支持在 M3U8 / DASH 流媒体以及大文件下载过程中，极速无损封装已下载分片并直接起播预览
"""
import os
import re
import sys
import time
import shutil
import subprocess
from .config import config, get_temp_segments_dir
from .ffmpeg_engine import get_ffmpeg_path
from .task_manager import task_manager


def get_task_temp_dir(task_id):
    """获取指定任务专用的分片临时目录"""
    return os.path.join(get_temp_segments_dir(), f".tmp_{task_id}")


def find_media_segments(task_tmp_dir):
    """递归检索任务临时目录中已下载完成的媒体分片"""
    if not os.path.exists(task_tmp_dir):
        return []

    valid_exts = {".ts", ".m4s", ".mp4", ".aac", ".m4a"}
    segments = []

    for root, _, files in os.walk(task_tmp_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_exts and not f.startswith("preview_"):
                full_p = os.path.join(root, f)
                try:
                    sz = os.path.getsize(full_p)
                    # 过滤掉小于 1KB 的非有效媒体文件 (如元数据或空切片)
                    if sz > 1024:
                        segments.append(full_p)
                except Exception:
                    pass

    # 自然排序分片：优先按文件名中的数字序号排序，次选按修改时间
    def sort_key(path):
        fname = os.path.basename(path)
        numbers = re.findall(r'\d+', fname)
        if numbers:
            return (0, int(numbers[-1]))
        return (1, os.path.getmtime(path))

    segments.sort(key=sort_key)
    return segments


def generate_task_preview(task_id):
    """
    为指定任务极速生成即时可播放的预览视频片段 (MP4)
    返回: (success: bool, file_path_or_msg: str, detail_msg: str)
    """
    task = task_manager.get_task(task_id)
    if not task:
        return False, "", "未找到对应任务信息"

    media_type = task.get("media_type", "m3u8")
    status = task.get("status", "")

    # 1. 若任务已全部完成，直接播放最终输出文件
    out_file = task.get("output_file", "")
    if status == "completed" and out_file and os.path.exists(out_file):
        return True, out_file, "任务已全部下载完成，直接播放完整文件"

    # 2. M3U8 / 流媒体分片实时拼装预览
    if media_type == "m3u8":
        task_tmp_dir = get_task_temp_dir(task_id)
        segments = find_media_segments(task_tmp_dir)

        if not segments:
            return False, "", "当前尚未下载到有效分片数据，请稍候数秒后再试！"

        if len(segments) < 2 and status == "downloading":
            return False, "", f"当前仅下载了 {len(segments)} 个分片，需至少完成 2 个分片才能稳定起播预览！"

        # 选取前 30 个分片 (约 1~3 分钟的画面，足够快速预览音画质量且极速封装)
        preview_segs = segments[:35]

        # 编写 FFmpeg concat 清单文件
        preview_list_txt = os.path.join(task_tmp_dir, f"_preview_list_{task_id}.txt")
        preview_mp4 = os.path.join(task_tmp_dir, f"preview_{task_id}.mp4")

        try:
            with open(preview_list_txt, "w", encoding="utf-8") as f:
                for seg in preview_segs:
                    # 转义 Windows 路径反斜杠
                    safe_p = seg.replace("\\", "/")
                    f.write(f"file '{safe_p}'\n")

            ff_exe = get_ffmpeg_path()
            if not ff_exe or not os.path.exists(ff_exe):
                return False, "", "未检测到有效的 FFmpeg 引擎，无法合成预览切片"

            # 采用 -c copy 极速直通合并，耗时通常仅需 0.1~0.3 秒
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW

            cmd = [
                ff_exe, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", preview_list_txt,
                "-c", "copy",
                "-movflags", "+faststart",
                preview_mp4
            ]

            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                timeout=12
            )

            # 无论成功与否，清理临时的 txt 列表
            try:
                os.remove(preview_list_txt)
            except Exception:
                pass

            if os.path.exists(preview_mp4) and os.path.getsize(preview_mp4) > 1024 * 10:
                seg_count = len(preview_segs)
                return True, preview_mp4, f"已无损提取前 {seg_count} 个分片，成功生成极速预览视频！"
            else:
                err_msg = proc.stderr.decode("utf-8", errors="ignore")[:200] if proc.stderr else "切片合并失败"
                return False, "", f"预览文件生成失败: {err_msg}"

        except Exception as e:
            return False, "", f"生成预览异常: {e}"

    # 3. 普通 HTTP / MP4 视音频文件边下边播
    else:
        save_dir = task.get("save_dir") or config.get("save_dir")
        save_name = task.get("save_name") or "video"
        candidate_p = os.path.join(save_dir, f"{save_name}.mp4")

        # 检查是否有正在写入的文件
        if os.path.exists(candidate_p) and os.path.getsize(candidate_p) > 1024 * 1024 * 2:
            return True, candidate_p, "已定位正在下载的媒体流数据"
        else:
            return False, "", "文件下载进度不足 (需至少下载 2MB 数据)，请稍后再试！"


def play_task_preview(task_id):
    """一键生成并打开预览播放"""
    ok, video_path, msg = generate_task_preview(task_id)
    if ok and video_path and os.path.exists(video_path):
        try:
            os.startfile(video_path)
            return True, msg
        except Exception as e:
            return False, f"调用系统播放器失败: {e}\n视频文件保存在:\n{video_path}"
    return False, msg
